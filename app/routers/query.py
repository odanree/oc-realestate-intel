"""
/query endpoint — both JSON (one-shot) and SSE (streaming intent + answer).
"""

from __future__ import annotations

import asyncio
import json
import logging

from fastapi import APIRouter
from sse_starlette.sse import EventSourceResponse

from app import observability
from app.agents.supervisor import get_graph
from app.schemas.query import (
    Citation,
    FeedbackRequest,
    QueryRequest,
    QueryResponse,
)

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["query"])


@router.post("/query", response_model=QueryResponse)
async def query(req: QueryRequest) -> QueryResponse:
    """Synchronous one-shot query."""
    graph = get_graph()
    config = _trace_config(req.query)
    with observability.trace_span("oci.query", {"query": req.query}) as trace_id:
        final = await graph.ainvoke({"query": req.query}, config=config)
    return QueryResponse(
        answer=final.get("answer", ""),
        intent=final.get("intent", "unknown"),
        citations=[Citation(**c) for c in final.get("citations", [])],
        trace_id=trace_id,
    )


@router.get("/query/stream")
async def query_stream(q: str) -> EventSourceResponse:
    """SSE stream — emits intent, retrieval count, then incremental answer tokens."""
    graph = get_graph()
    config = _trace_config(q)

    async def event_gen():
        try:
            with observability.trace_span("oci.query", {"query": q}) as trace_id:
                async for chunk in graph.astream({"query": q}, stream_mode="updates", config=config):
                    for node, delta in chunk.items():
                        yield {
                            "event": node,
                            "data": json.dumps(_serializable(delta)),
                        }
                    await asyncio.sleep(0)
                yield {"event": "trace", "data": json.dumps({"trace_id": trace_id})}
                yield {"event": "done", "data": "{}"}
        except Exception as e:
            log.exception("query stream failed")
            yield {"event": "error", "data": json.dumps({"error": str(e)})}

    return EventSourceResponse(event_gen())


@router.post("/feedback")
async def feedback(req: FeedbackRequest) -> dict:
    """Attach a user thumbs-up/down to a Langfuse trace.

    Returns 200 with {ok: true} whether or not tracing is enabled —
    a thumbs click should never error the UI. When tracing is disabled
    the call is silently dropped.
    """
    observability.create_score(
        trace_id=req.trace_id,
        name="user_feedback",
        value=req.score,
        comment=req.comment,
    )
    return {"ok": True}


def _serializable(delta: dict) -> dict:
    """Strip non-JSON-serializable fields (e.g. LangChain messages) from a state delta."""
    out: dict = {}
    for k, v in delta.items():
        if k == "messages":
            continue
        out[k] = v
    return out


def _trace_config(query: str) -> dict:
    """Attach Langfuse callbacks + a friendly trace name. No-op if disabled."""
    callbacks = observability.callbacks()
    if not callbacks:
        return {}
    return {
        "callbacks": callbacks,
        "run_name": "oci.query",
        "metadata": {"query": query[:200]},
    }
