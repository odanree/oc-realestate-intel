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
