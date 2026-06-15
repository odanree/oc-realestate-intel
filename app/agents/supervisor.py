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

from app import observability
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

Classify the user's query into ONE intent and, when the intent is "portfolio",
extract the owner entity name (LLC, trust, person, or corporation) the user
is asking about.

Intents:
  lookup       — find a specific parcel by address or APN
  compare      — compare two or more parcels, or compare to recent comps
  summarize    — summarize a single parcel or its history
  title_chain  — trace ownership history / chain of title for a parcel
  portfolio    — list every parcel held by a named owner entity
                 ("What does X own?", "show all parcels held by X",
                  "X's holdings", "list everything Y owns")
  unknown      — query is not about real estate or is too vague

RULES — these are absolute:
1. NEVER invent intents outside the six listed above. If the query doesn't
   fit any of them, respond with {"intent": "unknown"} — do not stretch
   one of the other intents to cover an off-domain question.
2. Do NOT answer the user's query yourself. You are a classifier, not the
   answerer. Even if you know the answer, your job here is only to route.
3. Do NOT include any field other than "intent" and (for portfolio)
   "owner_name". No reasoning fields, no confidence scores, no
   explanations. Extra keys will break the downstream parser.
4. Do NOT emit prose, markdown, code fences, comments, or any text outside
   the JSON object. The response MUST be a single JSON object and nothing
   else.
5. Do NOT infer owner_name on non-portfolio intents. Adding owner_name to
   a "lookup" or "title_chain" response is forbidden — the downstream
   routing only honors owner_name when intent is "portfolio".

Respond with ONLY a single JSON object. Examples:
  {"intent": "lookup"}
  {"intent": "portfolio", "owner_name": "IRVINE COMPANY LLC"}
  {"intent": "title_chain"}
  {"intent": "unknown"}

For "portfolio" you MUST include owner_name. Use the exact entity name from
the query (uppercase trusts/LLCs are fine)."""


async def router_node(state: AgentState) -> AgentState:
    import json

    llm = _judge_llm()
    response = await llm.ainvoke([
        SystemMessage(content=ROUTER_SYSTEM),
        HumanMessage(content=state["query"]),
    ])
    raw = response.content.strip() if isinstance(response.content, str) else ""
    if raw.startswith("```"):
        parts = raw.split("```")
        if len(parts) >= 2:
            raw = parts[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()

    valid = {"lookup", "compare", "summarize", "title_chain", "portfolio", "unknown"}
    out: dict = {"intent": "unknown"}
    try:
        parsed = json.loads(raw)
        intent = parsed.get("intent", "unknown")
        if intent in valid:
            out["intent"] = intent
        if intent == "portfolio":
            owner = (parsed.get("owner_name") or "").strip()
            if owner:
                out["owner_name"] = owner
            else:
                # Router said portfolio but didn't name an owner — degrade gracefully.
                out["intent"] = "lookup"
    except (json.JSONDecodeError, AttributeError):
        # Tolerate the old single-word format too.
        single = raw.lower().strip()
        if single in valid:
            out["intent"] = single

    log.info(
        "router classified intent=%s owner=%r for query=%r",
        out["intent"], out.get("owner_name"), state["query"][:80],
    )
    observability.tag_trace(
        tags=[f"intent:{out['intent']}"],
        metadata={"owner_name": out.get("owner_name")},
    )
    return out


def route_after_router(
    state: AgentState,
) -> Literal["retrieval", "comparison", "end"]:
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
    """Hybrid retrieval with two fallback layers:

      1. APN regex fast-path → direct ID lookup (covers "What is parcel X?").
      2. BM25 + dense fused via RRF over the local seeded set.
      3. Live OC ArcGIS lookup → reaches all 702k OC parcels for addresses
         outside our seed. Adds ~500ms when triggered.
    """
    intent = state.get("intent", "lookup")
    query = state["query"]
    parcels: list[dict] = []
    graph_facts: list[dict] = []

    # Portfolio queries: skip vector search entirely, hit Neo4j directly.
    if intent == "portfolio":
        owner_name = state.get("owner_name") or query
        from app.agents.tools import owner_holdings
        holdings = await owner_holdings.ainvoke({"owner_name_or_apn": owner_name})
        for h in holdings:
            h["owner_source"] = "synthetic"
        observability.tag_trace(
            tags=["source:neo4j_owner_holdings"],
            metadata={"holdings_count": len(holdings)},
        )
        return {"parcels": holdings, "graph_facts": []}

    # 1. APN fast path.
    source = None
    mentioned_apns = _APN_PATTERN.findall(query)
    if mentioned_apns and intent in ("lookup", "summarize", "title_chain"):
        from app.services import vector
        for apn in mentioned_apns:
            hit = await vector.get_parcel_by_apn(apn)
            if hit:
                parcels.append(hit)
        if parcels:
            source = "apn_fast_path"

    # 2. Hybrid search over seeded set.
    if not parcels and intent in ("lookup", "summarize"):
        from app.agents.tools import parcel_lookup
        parcels = await parcel_lookup.ainvoke({"query": query, "top_k": 5})
        source = "hybrid_search"

    # 3. Live ArcGIS fallback — triggered when the query mentions a specific
    #    address (street-number + street-name) but the local hits don't actually
    #    include that street number. Hybrid search always returns top-k, so
    #    "no parcels" never fires; we need a relevance check.
    if intent in ("lookup", "summarize") and not _hits_match_address(query, parcels):
        live = await _live_fallback(query)
        if live:
            parcels = live
            source = "live_arcgis_fallback"

    if source:
        observability.tag_trace(
            tags=[f"source:{source}"],
            metadata={"parcels_count": len(parcels)},
        )

    if intent == "title_chain" and parcels:
        from app.agents.tools import title_chain
        apn = parcels[0].get("apn", "")
        if apn:
            graph_facts = await title_chain.ainvoke({"apn": apn, "limit": 20})

    # Backfill owner_source for any parcel that has owner data but no
    # provenance tag — pre-stamp data in Qdrant/Postgres predates the
    # owner_source field. Everything we have today is synthetic.
    for p in parcels:
        if p.get("owner") and not p.get("owner_source"):
            p["owner_source"] = "synthetic"

    return {"parcels": parcels, "graph_facts": graph_facts}


_ADDRESS_NUM_RE = re.compile(r"\b(\d{1,6})\s+([A-Za-z][\w]*)", re.IGNORECASE)


def _hits_match_address(query: str, parcels: list[dict]) -> bool:
    """True iff the query has no street-number pattern OR at least one local
    hit's address contains both the street number AND the next address token
    from the query. False → trigger live fallback.
    """
    match = _ADDRESS_NUM_RE.search(query)
    if not match:
        return True  # No address in query → local hits are fine as-is.
    street_num = match.group(1)
    next_token = match.group(2).upper()
    for p in parcels:
        addr = (p.get("address") or "").upper()
        if street_num in addr and next_token in addr:
            return True
    return False


async def _live_fallback(query: str) -> list[dict]:
    """Hit OC ArcGIS live and enrich the result with synthetic owner data.

    We don't write the result back to Qdrant/Postgres on this path —
    cache misses are deterministic so the same query re-hits ArcGIS.
    If a particular area becomes hot, expand the seed filter instead.
    """
    from app.ingestion.synthetic_owners import generate_for_parcels
    from app.services import live_arcgis

    try:
        raw = await live_arcgis.lookup_by_address(query, top_k=5)
    except Exception as e:
        log.warning("live ArcGIS fallback failed: %s", e)
        return []
    if not raw:
        return []
    # Tag each parcel so the answer can mark them as live (not from our seed).
    enriched = list(generate_for_parcels(raw))
    for p in enriched:
        p["source"] = "live"
    return enriched


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
   Plain factual prose or a tight table. That's it.
6. PROVENANCE: when the facts indicate `owner_source: synthetic` or
   `(SYNTHETIC OWNER DATA — illustrative only)`, your answer MUST end with
   a short italicized note saying owner / title-chain data is illustrative
   and not from authoritative records. Do not omit this when applicable."""


async def summarize_node(state: AgentState) -> AgentState:
    llm = _judge_llm()
    facts = _format_facts(state)
    response = await llm.ainvoke([
        SystemMessage(content=SUMMARIZE_SYSTEM),
        HumanMessage(content=f"=== USER QUESTION ===\n{state['query']}\n\n=== FACTS ===\n{facts}"),
    ])
    answer = response.content if isinstance(response.content, str) else str(response.content)
    provenance = _compute_provenance(
        state.get("parcels") or [], state.get("graph_facts") or []
    )
    # Disclaimer enforcement, URL allowlist, prompt-injection detection all
    # live in the governance node now (see ADR-0007). summarize just emits
    # the unguarded answer; governance gates it before END.
    citations = _citations_from_answer(answer, state.get("parcels") or [])
    return {"answer": answer, "citations": citations, "provenance": provenance}


# ---------------------------------------------------------------------------
# Provenance classification (consumed by governance.DisclaimerCheck)
# ---------------------------------------------------------------------------

from app.governance import CANONICAL_DISCLAIMER  # noqa: E402


def _compute_provenance(parcels: list[dict], graph_facts: list[dict]) -> dict:
    """Classify the owner-data provenance of the retrieved facts.

    - `synthetic` — all owner-bearing facts came from the deterministic generator.
    - `authoritative` — all came from a real provider (future state).
    - `mixed` — both kinds present in the same answer context.
    - `none` — no owner-bearing facts retrieved.

    The disclaimer string is the canonical italic line the answer should also
    contain; downstream callers read this field instead of parsing prose.
    The governance node consumes `disclaimer` to decide whether to enforce.
    """
    sources: set[str] = set()
    for p in parcels:
        if not p.get("owner"):
            continue
        src = p.get("owner_source")
        if src == "synthetic":
            sources.add("synthetic")
        elif src in ("attom", "parcelquest", "assessor"):
            sources.add("authoritative")
    # Title-chain transfers are synthetic today; flag them whenever present.
    if graph_facts:
        sources.add("synthetic")

    if not sources:
        return {"owner_data_source": "none", "disclaimer": None}
    if sources == {"synthetic"}:
        return {"owner_data_source": "synthetic", "disclaimer": CANONICAL_DISCLAIMER}
    if sources == {"authoritative"}:
        return {"owner_data_source": "authoritative", "disclaimer": None}
    return {"owner_data_source": "mixed", "disclaimer": CANONICAL_DISCLAIMER}


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
    any_synthetic = False
    for i, p in enumerate(state.get("parcels") or [], start=1):
        owner = p.get("owner") or "unknown"
        source = p.get("owner_source")
        if source == "synthetic" and p.get("owner"):
            any_synthetic = True
            source_tag = " (SYNTHETIC OWNER DATA — illustrative only)"
        else:
            source_tag = ""
        parts.append(
            f"[{i}] APN {p.get('apn', '?')} — {p.get('address', '?')} "
            f"in {p.get('city', '?')} | owner: {owner} ({p.get('owner_kind') or 'n/a'}){source_tag} "
            f"| year_built: {p.get('year_built') or 'unknown'}"
        )
    if state.get("graph_facts"):
        parts.append("\nTitle chain (most recent first; SYNTHETIC):")
        any_synthetic = True
        for g in state.get("graph_facts") or []:
            price = g.get("price")
            price_str = f"${price:,}" if price else "no price recorded"
            parts.append(
                f"  · {g.get('date', '?')} doc#{g.get('doc_number', '?')}: "
                f"{g.get('grantor', '?')} → {g.get('grantee', '?')} ({price_str})"
            )
    if any_synthetic:
        parts.append(
            "\nNOTE: owner names and title transfers above are synthetic "
            "(real OC assessor data is paywalled). Address, APN, and year-built "
            "are real. Per RULE 6, end your answer with an italic disclaimer."
        )
    return "\n".join(parts) or "(no facts retrieved)"


# ---------------------------------------------------------------------------
# Build graph
# ---------------------------------------------------------------------------


def build_graph():
    from app.governance import governance_node

    g: StateGraph = StateGraph(AgentState)
    g.add_node("router", router_node)
    g.add_node("retrieval", retrieval_node)
    g.add_node("comparison", comparison_node)
    g.add_node("summarize", summarize_node)
    g.add_node("governance", governance_node)

    g.add_edge(START, "router")
    g.add_conditional_edges(
        "router",
        route_after_router,
        {"retrieval": "retrieval", "comparison": "comparison", "end": END},
    )
    g.add_edge("retrieval", "summarize")
    g.add_edge("comparison", "summarize")
    g.add_edge("summarize", "governance")
    g.add_edge("governance", END)
    return g.compile()


# Compiled graph singleton — lazy because tests may swap dependencies.
_graph = None


def get_graph():
    global _graph
    if _graph is None:
        _graph = build_graph()
    return _graph


__all__ = ["AgentState", "ALL_TOOLS", "build_graph", "get_graph"]
