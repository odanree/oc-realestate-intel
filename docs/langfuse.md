# Langfuse observability

Tracing is opt-in. Without keys, `app/observability.py` returns a no-op handler and the runtime cost is zero.

## Setup

1. Sign up at [langfuse.com](https://langfuse.com) — free tier is 50k events/mo, plenty for development. US cloud: `https://us.cloud.langfuse.com`. EU cloud: `https://cloud.langfuse.com`.
2. Create a project, open **Settings → API keys**, copy the public + secret.
3. Drop them in `.env`:

```
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_HOST=https://us.cloud.langfuse.com
```

(Both `LANGFUSE_HOST` and `LANGFUSE_BASE_URL` work — the config accepts either.)

4. Restart the API. Every `/api/v1/query` invocation now produces a trace.

## What you get on each trace

| Field | Source |
|---|---|
| **name** | `oci.query` (or `eval.<case_id>` for eval runs) |
| **tags** | `intent:lookup\|compare\|summarize\|title_chain\|portfolio\|unknown` + `source:apn_fast_path\|hybrid_search\|live_arcgis_fallback\|neo4j_owner_holdings` |
| **metadata** | `query`, `parcels_count`, `owner_name` (for portfolio), `holdings_count`, `eval_case_id` (for eval runs) |
| **observations** | Span per LangGraph node (router → retrieval → summarize) and a child generation span per Claude call with input/output, tokens, latency, cost |

## What you can do with it

### Filter by tag

In the traces list, use the **Trace Tags** filter in the left sidebar:

- `source:live_arcgis_fallback` — every query the local seed didn't cover ("cache miss" rate)
- `intent:portfolio` — owner-search queries that went to Neo4j directly
- `intent:unknown` — out-of-domain queries (gibberish or non-real-estate)
- `eval` — only traces from `scripts/eval.py`, separated from production
- `source:apn_fast_path` — APN-lookup queries (the cheapest/fastest path)

### Filter by score

`scripts/eval.py` attaches `faithfulness`, `answer_relevance`, `intent_accuracy`, `citation_recall`, `citation_precision`, `refusal_correctness` as Langfuse scores on each eval trace.

In the **Scores** view, filter `faithfulness < 8` and you'll get exactly the runs the judge flagged as ungrounded. Click in → see the agent's node-by-node trace that produced the failing answer.

### User feedback

The chat UI has a 👍 / 👎 row under each answer. Click → `POST /api/v1/feedback` → Langfuse `create_score(name="user_feedback", value=±1)` on the matching trace. Filter by `user_feedback = -1` to find queries users marked as bad.

## Implementation notes

This took three iterations to get right — worth recording so you don't repeat the mistakes:

1. **Use `start_as_current_observation`, not `start_observation`.** The non-as-current variant returns a span but doesn't enter it as the active OpenTelemetry context. The LangChain CallbackHandler creates its own spans in whatever context is active — without our outer span as the current context, the callback creates an entirely separate trace, and all the LangGraph node spans orphan into it.

2. **Langfuse v4 has no `update_current_trace` method.** It existed in v3, removed in v4. The supported v4 path is to set OTel span attributes prefixed `langfuse.trace.*` on the active span; the Langfuse OTel exporter maps them to trace-level fields at flush time. Code-wise: `from opentelemetry.trace import get_current_span; get_current_span().set_attribute("langfuse.trace.tags", json.dumps(["..."]))`.

3. **`set_attribute` overwrites; accumulate first.** Two `tag_trace` calls (router stamps `intent:lookup`, retrieval stamps `source:apn_fast_path`) means only the last survives, because each call overwrites the attribute value. Accumulate the tags in a `contextvars.ContextVar` during the trace span, flush the merged set onto the OTel attribute once at span exit.

All three are now handled in [`app/observability.py`](../app/observability.py).
