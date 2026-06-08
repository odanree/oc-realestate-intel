from __future__ import annotations

from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)


class Citation(BaseModel):
    apn: str | None = None
    address: str | None = None


class QueryResponse(BaseModel):
    answer: str
    intent: str
    citations: list[Citation] = []
    # Langfuse trace id — None when tracing is disabled. UI uses this to
    # attach thumbs-up/down feedback to the same trace.
    trace_id: str | None = None


class FeedbackRequest(BaseModel):
    trace_id: str = Field(..., min_length=1)
    score: float = Field(..., ge=-1.0, le=1.0, description="1.0=thumbs up, -1.0=thumbs down")
    comment: str | None = Field(default=None, max_length=500)
