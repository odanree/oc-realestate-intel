"""
LangGraph supervisor: routes a user query through Router → Retrieval → Comparison → Summarize.

Topology:

    START → router ─┬─→ retrieval ───┐
                    │                 ├─→ summarize → END
                    └─→ comparison ──┘

The router classifies intent; comparison only runs when the query is multi-parcel.
"""

from __future__ import annotations

import logging
import re
from typing import Literal

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph

from app.agents.state import AgentState
from app.agents.tools import ALL_TOOLS
from app.config import settings

log = logging.getLogger(__name__)


def _judge_llm() -> ChatAnthropic:
    return ChatAnthropic(
        model=settings.anthropic_model,
        api_key=settings.anthropic_api_key,
        max_tokens=2048,
        streaming=True,
    )


# ---------------------------------------------------------------------------
# Router: classifies user intent
# ---------------------------------------------------------------------------

ROUTER_SYSTEM = """You are a router for an Orange County real-estate intelligence agent.
Classify the user's query into ONE intent:

  lookup       — find a specific parcel by address/APN/owner name
  compare      — compare two or more parcels, or compare a parcel to recent comps
  summarize    — summarize a single parcel, its history, or its owner's portfolio
  title_chain  — trace ownership history / chain of title for a parcel
  unknown      — query is not about real estate or is too vague

Respond with ONLY the single-word intent."""


async def router_node(state: AgentState) -> AgentState:
    llm = _judge_llm()
    response = await llm.ainvoke([
        SystemMessage(content=ROUTER_SYSTEM),
        HumanMessage(content=state["query"]),
    ])
    intent_raw = response.content.strip().lower() if isinstance(response.content, str) else ""
    valid = {"lookup", "compare", "summarize", "title_chain", "unknown"}
    intent = intent_raw if intent_raw in valid else "unknown"
    log.info("router classified intent=%s for query=%r", intent, state["query"][:80])
    return {"intent": intent}


def route_after_router(state: AgentState) -> Literal["retrieval", "comparison", "end"]:
    intent = state.get("intent", "unknown")
    if intent == "unknown":
        return "end"
    if intent == "compare":
        return "comparison"
    return "retrieval"


# ---------------------------------------------------------------------------
# Retrieval: hybrid Qdrant + Neo4j lookup
# ---------------------------------------------------------------------------


async def retrieval_node(state: AgentState) -> AgentState:
    """Hybrid retrieval — APN match goes through direct lookup; otherwise dense."""
    intent = state.get("intent", "lookup")
    query = state["query"]
    parcels: list[dict] = []
    graph_facts: list[dict] = []

    # Fast path: query mentions an APN → look it up exactly, skip semantic search.
    mentioned_apns = _APN_PATTERN.findall(query)
    if mentioned_apns and intent in ("lookup", "summarize", "title_chain"):
        from app.services import vector
        for apn in mentioned_apns:
            hit = await vector.get_parcel_by_apn(apn)
            if hit:
                parcels.append(hit)

    if not parcels and intent in ("lookup", "summarize"):
        from app.agents.tools import parcel_lookup
        parcels = await parcel_lookup.ainvoke({"query": query, "top_k": 5})

    if intent == "title_chain" and parcels:
        from app.agents.tools import title_chain
        apn = parcels[0].get("apn", "")
        if apn:
            graph_facts = await title_chain.ainvoke({"apn": apn, "limit": 20})

    return {"parcels": parcels, "graph_facts": graph_facts}


# ---------------------------------------------------------------------------
# Comparison: only runs for multi-parcel queries
# ---------------------------------------------------------------------------


async def comparison_node(state: AgentState) -> AgentState:
    """Fetch a target parcel + comps for side-by-side analysis."""
    from app.agents.tools import comps_in_radius, parcel_lookup

    targets = await parcel_lookup.ainvoke({"query": state["query"], "top_k": 1})
    comps: list[dict] = []
    if targets:
        apn = targets[0].get("apn", "")
        if apn:
            comps = await comps_in_radius.ainvoke({"apn": apn, "radius_miles": 0.5, "top_k": 10})
    return {"parcels": targets + comps}


# ---------------------------------------------------------------------------
# Summarize: turn retrieved facts into a grounded natural-language answer
# ---------------------------------------------------------------------------

SUMMARIZE_SYSTEM = """You are an Orange County real-estate analyst.

RULES — these are absolute:
1. Answer using ONLY the retrieved facts. Do not speculate, infer motivation,
   guess transaction types ("arm's-length", "inter-family", "gift"), or
   characterize transfers beyond what the data literally says.
2. Cite parcels by APN.
3. If the retrieved facts do not contain the answer, say so plainly.
4. NEVER invent URLs, phone numbers, agency websites, or external resources.
   You may name "the OC Assessor's office" or "the OC Clerk-Recorder's office"
   as places to look, but never describe what they do or supply a URL.
5. No marketing language, no boilerplate, no "key observations" headers.
   Plain factual prose or a tight table. That's it."""


async def summarize_node(state: AgentState) -> AgentState:
    llm = _judge_llm()
    facts = _format_facts(state)
    response = await llm.ainvoke([
        SystemMessage(content=SUMMARIZE_SYSTEM),
        HumanMessage(content=f"=== USER QUESTION ===\n{state['query']}\n\n=== FACTS ===\n{facts}"),
    ])
    answer = response.content if isinstance(response.content, str) else str(response.content)
    citations = _citations_from_answer(answer, state.get("parcels") or [])
    return {"answer": answer, "citations": citations}


# APN format: three groups of digits separated by hyphens (e.g. 934-21-145, 461-211-62).
_APN_PATTERN = re.compile(r"\b\d{3}-\d{2,3}-\d{2,4}\b")


def _citations_from_answer(answer: str, retrieved: list[dict]) -> list[dict]:
    """Only cite parcels whose APN actually appears in the answer text.

    Falls back to all retrieved parcels if the model didn't reference any APNs
    (e.g. when the answer is a refusal / no-match response).
    """
    mentioned = set(_APN_PATTERN.findall(answer))
    if not mentioned:
        return []
    return [
        {"apn": p["apn"], "address": p.get("address")}
        for p in retrieved
        if p.get("apn") in mentioned
    ]


def _format_facts(state: AgentState) -> str:
    parts: list[str] = []
    for i, p in enumerate(state.get("parcels") or [], start=1):
        owner = p.get("owner") or "unknown"
        parts.append(
            f"[{i}] APN {p.get('apn', '?')} — {p.get('address', '?')} "
            f"in {p.get('city', '?')} | owner: {owner} ({p.get('owner_kind') or 'n/a'}) "
            f"| year_built: {p.get('year_built') or 'unknown'}"
        )
    if state.get("graph_facts"):
        parts.append("\nTitle chain (most recent first):")
        for g in state.get("graph_facts") or []:
            price = g.get("price")
            price_str = f"${price:,}" if price else "no price recorded"
            parts.append(
                f"  · {g.get('date', '?')} doc#{g.get('doc_number', '?')}: "
                f"{g.get('grantor', '?')} → {g.get('grantee', '?')} ({price_str})"
            )
    return "\n".join(parts) or "(no facts retrieved)"


# ---------------------------------------------------------------------------
# Build graph
# ---------------------------------------------------------------------------


def build_graph():
    g: StateGraph = StateGraph(AgentState)
    g.add_node("router", router_node)
    g.add_node("retrieval", retrieval_node)
    g.add_node("comparison", comparison_node)
    g.add_node("summarize", summarize_node)

    g.add_edge(START, "router")
    g.add_conditional_edges(
        "router",
        route_after_router,
        {"retrieval": "retrieval", "comparison": "comparison", "end": END},
    )
    g.add_edge("retrieval", "summarize")
    g.add_edge("comparison", "summarize")
    g.add_edge("summarize", END)
    return g.compile()


# Compiled graph singleton — lazy because tests may swap dependencies.
_graph = None


def get_graph():
    global _graph
    if _graph is None:
        _graph = build_graph()
    return _graph


__all__ = ["AgentState", "ALL_TOOLS", "build_graph", "get_graph"]
