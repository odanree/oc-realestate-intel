"""
Model-comparison sweep — run the eval suite against multiple agent models
and emit a side-by-side report.

The JUDGE is fixed (Sonnet 4.6) so all rows are scored consistently —
swapping the judge would conflate "agent quality" with "judge calibration."
We're measuring the agent.

Usage:
    python -m scripts.sweep                         # default 3 Claude models
    python -m scripts.sweep --models claude-sonnet-4-6,claude-haiku-4-5-20251001
    python -m scripts.sweep --out evals/reports/sweep-2026-06-07.md

Estimated cost: ~$0.10 (Haiku) + ~$0.10 (Sonnet) + ~$0.50 (Opus) plus
judge cost (~$0.05 per model) = ~$0.85 for the default 3-model sweep.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
from datetime import datetime
from pathlib import Path

import yaml

import app.agents.supervisor as supervisor
from app.config import settings
from scripts.eval import run_eval

logging.basicConfig(level=logging.WARNING)
logging.getLogger("neo4j.notifications").setLevel(logging.ERROR)
logging.getLogger("httpx").setLevel(logging.WARNING)
log = logging.getLogger(__name__)

DEFAULT_MODELS = [
    "claude-haiku-4-5-20251001",
    "claude-sonnet-4-6",
    "claude-opus-4-7",
]

JUDGE_MODEL = "claude-sonnet-4-6"

METRICS = [
    "intent_accuracy",
    "citation_recall",
    "citation_precision",
    "refusal_correctness",
    "faithfulness",
    "answer_relevance",
]


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--golden", default="evals/golden.yaml")
    parser.add_argument("--models", default=",".join(DEFAULT_MODELS),
                        help="Comma-separated agent model IDs")
    parser.add_argument("--out", default=None)
    parser.add_argument("--no-llm-judge", action="store_true",
                        help="Skip LLM-judged metrics (fast preview)")
    args = parser.parse_args()

    cases = yaml.safe_load(Path(args.golden).read_text(encoding="utf-8"))
    models = [m.strip() for m in args.models.split(",") if m.strip()]

    print(f"Sweeping {len(models)} agent models × {len(cases)} cases (judge: {JUDGE_MODEL})")
    print(f"Models: {', '.join(models)}\n")

    by_model: dict[str, dict] = {}
    for model in models:
        print(f"=== agent={model} ===")
        # Swap the model the supervisor's _judge_llm() reads, then force
        # the cached LangGraph to rebuild on next get_graph() call.
        settings.anthropic_model = model
        supervisor._graph = None

        rows, summary = await run_eval(cases, JUDGE_MODEL, use_llm_judge=not args.no_llm_judge)
        by_model[model] = {"rows": rows, "summary": summary}
        print()

    report = _render(by_model, cases, judge_model=JUDGE_MODEL)

    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(report, encoding="utf-8")
        print(f"Sweep report written to {args.out}")
    else:
        print()
        print(report)


def _render(by_model: dict, cases: list[dict], judge_model: str) -> str:
    md: list[str] = []
    md.append("# oc-realestate-intel model comparison sweep")
    md.append("")
    md.append(f"- generated: {datetime.utcnow().isoformat()}Z")
    md.append(f"- judge model: `{judge_model}` (fixed across all runs)")
    md.append(f"- cases: {len(cases)}")
    md.append("")

    md.append("## Aggregate scores")
    md.append("")
    md.append("| metric | " + " | ".join(f"`{m}`" for m in by_model) + " |")
    md.append("|---|" + "|".join("---" for _ in by_model) + "|")
    for k in METRICS:
        cells = []
        for m in by_model:
            v = by_model[m]["summary"].get(k)
            cells.append(f"{v:.2f}" if isinstance(v, float) else "—")
        md.append(f"| `{k}` | " + " | ".join(cells) + " |")
    cost_row = ["$" + f"{by_model[m]['summary']['total_cost_usd']:.4f}" for m in by_model]
    md.append("| judge cost | " + " | ".join(cost_row) + " |")
    md.append("")

    # Per-case breakdown of faithfulness + answer_relevance — the noisiest dims.
    md.append("## Per-case faithfulness × model")
    md.append("")
    md.append("| case | " + " | ".join(f"`{m}`" for m in by_model) + " |")
    md.append("|---|" + "|".join("---" for _ in by_model) + "|")
    case_ids = [c["id"] for c in cases]
    rows_by_model = {m: {r["id"]: r for r in by_model[m]["rows"]} for m in by_model}
    for cid in case_ids:
        cells = []
        for m in by_model:
            r = rows_by_model[m].get(cid, {})
            v = r.get("faithfulness")
            cells.append(f"{v:.1f}" if isinstance(v, float) else "—")
        md.append(f"| {cid} | " + " | ".join(cells) + " |")
    md.append("")

    md.append("## Per-case answer_relevance × model")
    md.append("")
    md.append("| case | " + " | ".join(f"`{m}`" for m in by_model) + " |")
    md.append("|---|" + "|".join("---" for _ in by_model) + "|")
    for cid in case_ids:
        cells = []
        for m in by_model:
            r = rows_by_model[m].get(cid, {})
            v = r.get("answer_relevance")
            cells.append(f"{v:.1f}" if isinstance(v, float) else "—")
        md.append(f"| {cid} | " + " | ".join(cells) + " |")
    md.append("")

    return "\n".join(md)


if __name__ == "__main__":
    asyncio.run(main())
