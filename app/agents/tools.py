"""
LangGraph tools (LangChain @tool decorated) wrapping data-layer queries.

Each tool is a thin adapter over a service module so the same logic is
testable without LangGraph in the loop.
"""

from __future__ import annotations

from langchain_core.tools import tool

from app.services import graph, vector


@tool
async def parcel_lookup(query: str, top_k: int = 5) -> list[dict]:
    """Look up parcels by free-text query (address, legal description, owner name).

    Uses Qdrant hybrid retrieval over embedded parcel records.
    """
    return await vector.search_parcels(query, top_k=top_k)


@tool
async def owner_holdings(owner_name_or_apn: str) -> list[dict]:
    """List every parcel held by an owner entity (person, trust, or LLC).

    Resolves common entity variants ("THE SMITH FAMILY TRUST" ≈ "SMITH FAMILY TR")
    via the Neo4j owner graph.
    """
    return await graph.owner_holdings(owner_name_or_apn)


@tool
async def comps_in_radius(apn: str, radius_miles: float = 0.5, top_k: int = 10) -> list[dict]:
    """Find comparable recent sales within a radius of the given parcel APN."""
    return await vector.comps_in_radius(apn, radius_miles=radius_miles, top_k=top_k)


@tool
async def title_chain(apn: str, limit: int = 20) -> list[dict]:
    """Return the chain of recorded title transfers for a parcel, most recent first."""
    return await graph.title_chain(apn, limit=limit)


ALL_TOOLS = [parcel_lookup, owner_holdings, comps_in_radius, title_chain]
