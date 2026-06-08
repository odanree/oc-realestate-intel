"""
Run the golden eval set against the LangGraph agent and score with evalkit.

Two flavors of metrics:

  Programmatic (fast, deterministic)
    - intent_accuracy        — router classification matches expected_intent
    - citation_recall        — every must_cite APN appears in citations
    - citation_precision     — no must_not_cite APN appears
    - refusal_correctness    — must_refuse cases produce no-data answers

  LLM-judged (via evalkit, slow, ~$0.001 per question per metric)
    - faithfulness           — answer claims are grounded in retrieved parcels
    - answer_relevance       — answer addresses the question

Usage:
    python -m scripts.eval                 # full suite, markdown to stdout
    python -m scripts.eval --no-llm-judge  # skip LLM metrics (free + fast)
    python -m scripts.eval --out evals/reports/$(date +%F).md
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import re
from datetime import datetime
from pathlib import Path

import yaml
from evalkit import AnswerRelevance, AnthropicProvider, Evaluator, Faithfulness

from app.agents.supervisor import get_graph
from app.config import settings

logging.basicConfig(level=logging.WARNING)
# Silence Neo4j schema-warning chatter — the graph is intentionally empty in v0.
logging.getLogger("neo4j.notifications").setLevel(logging.ERROR)
logging.getLogger("httpx").setLevel(logging.WARNING)
log = logging.getLogger(__name__)

REFUSAL_TRIGGERS = (
    "do not contain",
    "does not contain",
    "don't contain",
    "doesn't contain",
    "cannot confirm",
    "can't confirm",
    "no data",
    "not available",
    "not populated",
    "no record",
    "no information",
    "i cannot",
    "i can't",
    "do not include",
    "does not include",
    "not identified",  # 2026-06-07: missed by initial run
    "not specified",
    "not present",
    "not in the available",
    "not in the retrieved",
    "no facts",         # "no facts were retrieved" / "no facts found"
    "no title chain",
    "no chain",
)

_APN_RE = re.compile(r"\b\d{3}-\d{2,3}-\d{2,4}\b")


def _is_refusal(answer: str) -> bool:
    low = answer.lower()
    return any(trigger in low for trigger in REFUSAL_TRIGGERS)


async def _run_case(graph, case: dict) -> dict:
    """Invoke the agent on one case; return the case + agent outputs."""
    state = await graph.ainvoke({"query": case["query"]})
    answer = state.get("answer", "")
    intent = state.get("intent", "unknown")
    citations = state.get("citations") or []
    cited_apns = {c.get("apn") for c in citations if c.get("apn")}
    parcels = state.get("parcels") or []
    graph_facts = state.get("graph_facts") or []
    return {
        **case,
        "answer": answer,
        "intent": intent,
        "cited_apns": cited_apns,
        "parcels": parcels,
        "graph_facts": graph_facts,
    }


def _score_programmatic(row: dict) -> dict:
    """Deterministic metrics — no LLM calls."""
    expected_intent = row.get("expected_intent")
    must_cite = set(row.get("must_cite") or [])
    must_not_cite = set(row.get("must_not_cite") or [])

    intent_ok = (row["intent"] == expected_intent) if expected_intent else None

    cite_recall = None
    if must_cite:
        hits = must_cite & row["cited_apns"]
        cite_recall = len(hits) / len(must_cite)

    cite_precision = None
    if must_not_cite:
        cite_precision = 1.0 if not (must_not_cite & row["cited_apns"]) else 0.0

    refusal_ok = None
    if row.get("must_refuse"):
        refusal_ok = 1.0 if _is_refusal(row["answer"]) else 0.0

    return {
        "intent_accuracy": intent_ok,
        "citation_recall": cite_recall,
        "citation_precision": cite_precision,
        "refusal_correctness": refusal_ok,
    }


def _format_context(parcels: list[dict], graph_facts: list[dict] | None = None) -> str:
    """Build the context block passed to evalkit's Faithfulness judge.

    Must mirror what the agent's summarize_node sees as ground truth —
    parcels AND any title-chain rows from the graph. Without graph_facts,
    the judge correctly flags every title-chain claim as hallucinated.
    """
    if not parcels and not graph_facts:
        return "(no facts retrieved)"
    lines: list[str] = []
    any_synthetic = False
    for p in parcels or []:
        source = p.get("owner_source")
        if source == "synthetic" and p.get("owner"):
            any_synthetic = True
            tag = " (synthetic owner)"
        else:
            tag = ""
        lines.append(
            f"APN {p.get('apn', '?')} — {p.get('address', '?')} "
            f"in {p.get('city', '?')} | owner={p.get('owner') or 'unknown'}{tag} "
            f"({p.get('owner_kind') or 'n/a'}) | year_built={p.get('year_built') or 'unknown'}"
        )
    if graph_facts:
        lines.append("Title chain (most recent first; synthetic):")
        any_synthetic = True
        for g in graph_facts:
            price = g.get("price")
            price_str = f"${price:,}" if price else "no price"
            lines.append(
                f"  - {g.get('date', '?')} doc#{g.get('doc_number', '?')}: "
                f"{g.get('grantor', '?')} -> {g.get('grantee', '?')} ({price_str})"
            )
    if any_synthetic:
        lines.append(
            "NOTE: owner names and title transfers above are synthetic, not from "
            "authoritative records. The answer is expected to flag this with a "
            "disclaimer; that disclaimer IS grounded in the source data and must "
            "not be penalized as a hallucination."
        )
    return "\n".join(lines)


async def _score_llm(evaluator: Evaluator, row: dict) -> dict:
    """LLM-judged metrics via evalkit."""
    context = _format_context(row["parcels"], row.get("graph_facts"))
    result = evaluator.score(
        prompt=row["query"],
        completion=row["answer"] or "(empty)",
        context=context,
        metrics=[Faithfulness(), AnswerRelevance()],
    )
    return {
        "faithfulness": result.values.get("faithfulness"),
        "answer_relevance": result.values.get("answer_relevance"),
        "cost_usd": result.cost_usd,
        "judge_notes": result.reasoning,
    }


def _aggregate(rows: list[dict]) -> dict:
    """Mean over non-None values for each metric."""
    keys = [
        "intent_accuracy",
        "citation_recall",
        "citation_precision",
        "refusal_correctness",
        "faithfulness",
        "answer_relevance",
    ]
    out = {}
    for k in keys:
        vals = [r[k] for r in rows if r.get(k) is not None]
        out[k] = round(sum(vals) / len(vals), 3) if vals else None
    out["total_cost_usd"] = round(sum(r.get("cost_usd") or 0 for r in rows), 4)
    return out


def _render_markdown(
    rows: list[dict],
    summary: dict,
    judge_model: str,
    agent_model: str | None = None,
) -> str:
    md: list[str] = []
    md.append("# oc-realestate-intel eval report")
    md.append("")
    md.append(f"- generated: {datetime.utcnow().isoformat()}Z")
    if agent_model:
        md.append(f"- agent model: `{agent_model}`")
    md.append(f"- judge model: `{judge_model}`")
    md.append(f"- cases: {len(rows)}")
    md.append(f"- total judge cost: ${summary['total_cost_usd']:.4f}")
    md.append("")
    md.append("## Summary")
    md.append("")
    md.append("| metric | score |")
    md.append("|---|---|")
    for k in (
        "intent_accuracy",
        "citation_recall",
        "citation_precision",
        "refusal_correctness",
        "faithfulness",
        "answer_relevance",
    ):
        v = summary.get(k)
        s = f"{v:.2f}" if isinstance(v, float) else "—"
        md.append(f"| `{k}` | {s} |")
    md.append("")
    md.append("## Per-case detail")
    md.append("")
    for r in rows:
        md.append(f"### `{r['id']}` — intent `{r['intent']}` (expected `{r.get('expected_intent', '—')}`)")
        md.append(f"**Query:** {r['query']}")
        md.append("")
        md.append(f"**Answer:**\n> {r['answer'].strip().replace(chr(10), chr(10) + '> ')}")
        md.append("")
        if r.get("cited_apns"):
            md.append(f"**Citations:** {', '.join(sorted(r['cited_apns']))}")
        scores = []
        for k in (
            "intent_accuracy",
            "citation_recall",
            "citation_precision",
            "refusal_correctness",
            "faithfulness",
            "answer_relevance",
        ):
            v = r.get(k)
            if v is None:
                continue
            scores.append(f"{k}={v:.2f}" if isinstance(v, float) else f"{k}={v}")
        if scores:
            md.append(f"**Scores:** {' · '.join(scores)}")
        md.append("")
    return "\n".join(md)


async def run_eval(
    cases: list[dict],
    judge_model: str,
    use_llm_judge: bool = True,
) -> tuple[list[dict], dict]:
    """Run the eval suite once. Returns (per-case rows, summary)."""
    graph = get_graph()

    rows: list[dict] = []
    print(f"Running {len(cases)} cases...", flush=True)
    for i, case in enumerate(cases, 1):
        result = await _run_case(graph, case)
        result.update(_score_programmatic(result))
        rows.append(result)
        print(f"  [{i}/{len(cases)}] {case['id']}", flush=True)

    if use_llm_judge:
        evaluator = Evaluator(
            judge=judge_model,
            provider=AnthropicProvider(api_key=settings.anthropic_api_key),
            max_tokens=512,
        )
        print(f"Scoring with evalkit ({judge_model})...", flush=True)
        for i, row in enumerate(rows, 1):
            row.update(await _score_llm(evaluator, row))
            print(f"  [{i}/{len(rows)}] {row['id']} ({row.get('cost_usd', 0):.4f} USD)", flush=True)

    return rows, _aggregate(rows)


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--golden", default="evals/golden.yaml")
    parser.add_argument("--no-llm-judge", action="store_true")
    parser.add_argument("--out", default=None, help="Write markdown to this path")
    parser.add_argument("--json", action="store_true", help="Print JSON summary to stdout")
    parser.add_argument(
        "--agent-model",
        default=None,
        help="Override agent model (e.g. claude-opus-4-7). Default: settings.anthropic_model.",
    )
    args = parser.parse_args()

    if args.agent_model:
        # Override the agent model used by the supervisor _judge_llm()
        # and force the cached graph to rebuild.
        import app.config
        import app.agents.supervisor as sup
        app.config.settings.anthropic_model = args.agent_model
        sup._graph = None

    cases = yaml.safe_load(Path(args.golden).read_text(encoding="utf-8"))
    graph = get_graph()

    # Run the eval — judge stays on a fixed Sonnet so model-vs-model comparisons
    # are apples-to-apples even when --agent-model overrides the agent model.
    judge_model = "claude-sonnet-4-6"
    rows, summary = await run_eval(cases, judge_model, use_llm_judge=not args.no_llm_judge)
    agent_model = args.agent_model or settings.anthropic_model
    report = _render_markdown(rows, summary, judge_model=judge_model, agent_model=agent_model)

    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(report, encoding="utf-8")
        print(f"Report written to {args.out}")

    if args.json:
        print(json.dumps(summary, indent=2))
    elif not args.out:
        print()
        print(report)


if __name__ == "__main__":
    asyncio.run(main())
