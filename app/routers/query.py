"""
/query endpoint — both JSON (one-shot) and SSE (streaming intent + answer).
"""

from __future__ import annotations

import asyncio
import json
import logging

from fastapi import APIRouter
from sse_starlette.sse import EventSourceResponse

from app.agents.supervisor import get_graph
from app.schemas.query import Citation, QueryRequest, QueryResponse

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["query"])


@router.post("/query", response_model=QueryResponse)
async def query(req: QueryRequest) -> QueryResponse:
    """Synchronous one-shot query."""
    graph = get_graph()
    final = await graph.ainvoke({"query": req.query})
    return QueryResponse(
        answer=final.get("answer", ""),
        intent=final.get("intent", "unknown"),
        citations=[Citation(**c) for c in final.get("citations", [])],
    )


@router.get("/query/stream")
async def query_stream(q: str) -> EventSourceResponse:
    """SSE stream — emits intent, retrieval count, then incremental answer tokens."""
    graph = get_graph()

    async def event_gen():
        try:
            async for chunk in graph.astream({"query": q}, stream_mode="updates"):
                # Each chunk is {node_name: state_delta}
                for node, delta in chunk.items():
                    yield {
                        "event": node,
                        "data": json.dumps(_serializable(delta)),
                    }
                await asyncio.sleep(0)  # cooperative yield
            yield {"event": "done", "data": "{}"}
        except Exception as e:
            log.exception("query stream failed")
            yield {"event": "error", "data": json.dumps({"error": str(e)})}

    return EventSourceResponse(event_gen())


def _serializable(delta: dict) -> dict:
    """Strip non-JSON-serializable fields (e.g. LangChain messages) from a state delta."""
    out: dict = {}
    for k, v in delta.items():
        if k == "messages":
            continue
        out[k] = v
    return out
