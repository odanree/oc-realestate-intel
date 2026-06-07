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
    return {
        **case,
        "answer": answer,
        "intent": intent,
        "cited_apns": cited_apns,
        "parcels": parcels,
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


def _format_context(parcels: list[dict]) -> str:
    """Build the context block passed to evalkit's Faithfulness judge."""
    if not parcels:
        return "(no parcels retrieved)"
    lines = []
    for p in parcels:
        lines.append(
            f"APN {p.get('apn', '?')} — {p.get('address', '?')} "
            f"in {p.get('city', '?')} | owner={p.get('owner') or 'unknown'} | "
            f"year_built={p.get('year_built') or 'unknown'}"
        )
    return "\n".join(lines)


async def _score_llm(evaluator: Evaluator, row: dict) -> dict:
    """LLM-judged metrics via evalkit."""
    context = _format_context(row["parcels"])
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


def _render_markdown(rows: list[dict], summary: dict, judge_model: str) -> str:
    md: list[str] = []
    md.append("# oc-realestate-intel eval report")
    md.append("")
    md.append(f"- generated: {datetime.utcnow().isoformat()}Z")
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


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--golden", default="evals/golden.yaml")
    parser.add_argument("--no-llm-judge", action="store_true")
    parser.add_argument("--out", default=None, help="Write markdown to this path")
    parser.add_argument("--json", action="store_true", help="Print JSON summary to stdout")
    args = parser.parse_args()

    cases = yaml.safe_load(Path(args.golden).read_text(encoding="utf-8"))
    graph = get_graph()

    rows: list[dict] = []
    print(f"Running {len(cases)} cases...", flush=True)
    for i, case in enumerate(cases, 1):
        result = await _run_case(graph, case)
        result.update(_score_programmatic(result))
        rows.append(result)
        print(f"  [{i}/{len(cases)}] {case['id']}", flush=True)

    if not args.no_llm_judge:
        # Pass the key explicitly — pydantic-settings loads .env into `settings`
        # but doesn't propagate to os.environ, which evalkit's default reads.
        evaluator = Evaluator(
            judge=settings.anthropic_model,
            provider=AnthropicProvider(api_key=settings.anthropic_api_key),
            max_tokens=512,
        )
        print(f"Scoring with evalkit ({settings.anthropic_model})...", flush=True)
        for i, row in enumerate(rows, 1):
            row.update(await _score_llm(evaluator, row))
            print(f"  [{i}/{len(rows)}] {row['id']} ({row.get('cost_usd', 0):.4f} USD)", flush=True)

    summary = _aggregate(rows)
    report = _render_markdown(rows, summary, settings.anthropic_model)

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
