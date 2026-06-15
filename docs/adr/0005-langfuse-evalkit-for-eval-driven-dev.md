# ADR-0005: Langfuse + evalkit for the eval-driven dev loop

- **Status:** Accepted
- **Date:** 2025-11-12
- **Deciders:** Danh Le

## Context

An LLM agent's behavior is not specified by its code alone. Prompts, model version, retrieval recall, and judge calibration each move the answer surface. A change that improves one query class can silently regress another. Without an automated scorecard, "did this PR make the agent better?" is a vibe call.

The agent also has a debugging problem distinct from a normal service: when a single query produces a bad answer, we need to see *which node* misbehaved — was it the router? Did retrieval return junk? Did summarize ignore a synthetic-data NOTE?

## Decision

Adopt **Langfuse** as the trace/score store and **evalkit** as the eval harness and judge interface. Wire them together so every eval case produces a Langfuse trace that carries its scores, tagged for filtering.

The dev loop becomes:

```
Production query → Langfuse trace (tagged intent / source)
                          ↓
              Filter low-score traces in dashboard
                          ↓
              Reproduce as eval case in evals/golden.yaml
                          ↓
              scripts/eval.py judges with evalkit → attaches scores to Langfuse
                          ↓
              Fix prompt or code → re-run → compare reports in evals/reports/
```

Scores attached: `faithfulness`, `answer_relevance`, `intent_accuracy`, `citation_precision`, `citation_recall`, `refusal_correctness`, plus user `thumbs_up`/`thumbs_down` from the UI feedback endpoint.

## Consequences

**Positive**
- The "is this PR an improvement" question becomes a number comparison: run the suite, diff the report. Three real bugs were found this way (hallucinated `ocassessor.gov` URL, speculative transfer characterization, judge missing graph_facts in context).
- One trace per query, with per-node spans, with scores attached, with intent/source tags — filtering by `scores.faithfulness < 8` in the Langfuse UI takes you directly to the failing run AND its underlying state.
- The thumbs feedback endpoint round-trips user signal into the same store, closing the loop between users and the eval set: low-thumbs traces become candidate golden cases.
- Cost is bounded (~$0.07/run for the 16-case suite). The cost ceiling is the *judge*, not the agent — we picked Sonnet 4.6 as judge because Opus showed no measurable lift on faithfulness at 4× the cost.

**Negative**
- Langfuse self-hosted is another stateful service in compose. We accepted that cost; the alternative is paying for the cloud tier.
- evalkit is a small custom-built library — bus factor and external visibility are both lower than something like RAGAS or Promptfoo. Picked because the prompt/judge interface fits cleanly with the per-node tracing.
- Judge calibration is a real risk. We ran a model sweep (Haiku / Sonnet / Opus) early and locked in Sonnet — but if the judge drifts (model version change, prompt rework), the scorecard moves under us. Mitigation: pin the judge model and version separately from the production model.

## Alternatives considered

- **RAGAS** — viable, broadly used. Rejected because it is RAG-shaped and our agent is multi-intent with non-RAG paths (portfolio is graph-only, title_chain joins retrieval + graph). Forcing every metric through a "context + question + answer" frame did not fit.
- **Promptfoo** — strong eval CLI but weaker on the trace-store side. We would still need Langfuse (or equivalent) for production traces, and gluing the two together is more code than evalkit + Langfuse directly.
- **Roll-our-own scorecard with print-to-CSV** — that is how the project started. It scales to ~3 cases and then becomes the bug surface.

## Links

- Implementation: `scripts/eval.py`, `scripts/sweep.py`, `app/observability.py`, `evals/golden.yaml`, `evals/reports/`
- Related: [ADR-0001](0001-langgraph-for-agent-orchestration.md)
