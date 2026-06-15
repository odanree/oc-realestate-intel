from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)


class Citation(BaseModel):
    apn: str | None = None
    address: str | None = None


class Provenance(BaseModel):
    """Structured provenance signal for downstream agent callers.

    Lifts the synthetic/authoritative distinction out of the prose answer so
    MCP callers cannot accidentally strip it by ignoring the answer text.
    """

    owner_data_source: Literal["synthetic", "authoritative", "mixed", "none"]
    disclaimer: str | None = None


class QueryResponse(BaseModel):
    answer: str
    intent: str
    citations: list[Citation] = []
    provenance: Provenance | None = None
    # Langfuse trace id — None when tracing is disabled. UI uses this to
    # attach thumbs-up/down feedback to the same trace.
    trace_id: str | None = None


class FeedbackRequest(BaseModel):
    trace_id: str = Field(..., min_length=1)
    score: float = Field(..., ge=-1.0, le=1.0, description="1.0=thumbs up, -1.0=thumbs down")
    comment: str | None = Field(default=None, max_length=500)
