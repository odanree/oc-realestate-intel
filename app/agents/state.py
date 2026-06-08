"""Shared LangGraph state schema."""

from __future__ import annotations

from typing import Annotated, Literal, TypedDict

from langgraph.graph.message import add_messages


class AgentState(TypedDict, total=False):
    """State threaded through the supervisor + child agents."""

    # Conversation history (LangGraph appends via add_messages reducer)
    messages: Annotated[list, add_messages]

    # User query (verbatim)
    query: str

    # Router classification
    intent: Literal[
        "lookup", "compare", "summarize", "title_chain", "portfolio", "unknown"
    ]
    # Owner entity extracted by the router for portfolio-intent queries.
    owner_name: str

    # Retrieval results
    parcels: list[dict]
    documents: list[dict]
    graph_facts: list[dict]

    # Final answer + citations
    answer: str
    citations: list[dict]

    # Cost / token bookkeeping
    input_tokens: int
    output_tokens: int
