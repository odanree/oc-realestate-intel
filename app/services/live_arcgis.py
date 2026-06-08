"""
Live OC ArcGIS lookup — fallback for parcels outside the seeded set.

Cache miss path: hybrid retrieval over the local Qdrant + Postgres index
returns nothing → supervisor falls back here to hit the live OC Public Works
ArcGIS FeatureServer directly.

Cost: ~300-700ms per call, depending on ArcGIS load. We don't cache the
result in Qdrant/Postgres on this path — that'd require both an embedding
roundtrip and a transactional write. If a query is repeated often enough
to matter, the right answer is to expand the seed filter.
"""

from __future__ import annotations

import logging
import re

import httpx

from app.ingestion.arcgis_parcels import BASE_URL, OUT_FIELDS, _normalize

log = logging.getLogger(__name__)


def _escape(s: str) -> str:
    """ArcGIS uses single-quoted strings; double-up any embedded apostrophes."""
    return s.replace("'", "''")


def _likely_address(query: str) -> str | None:
    """Pull an address-shaped substring from a free-text query.

    Examples that should match:
      "find parcel for address 470 s alpine rd orange, ca"  → "470 s alpine rd orange"
      "what is at 73 Bridgeport Rd Irvine?"                  → "73 Bridgeport Rd Irvine"
      "Who owns 100 Pacific Coast Hwy?"                       → "100 Pacific Coast Hwy"

    We require: leading digit-run + at least one word before the next sentence
    boundary or ", ca" / "?" / end of string.
    """
    pattern = re.compile(
        r"(\d{1,6}\s+[A-Za-z][\w\s]+?)(?:\s*,?\s*(?:ca|california)\b|[?!.,]|$)",
        re.IGNORECASE,
    )
    match = pattern.search(query)
    if not match:
        return None
    return match.group(1).strip()


async def lookup_by_address(query: str, top_k: int = 5, timeout_s: float = 8.0) -> list[dict]:
    """Try to extract an address from `query` and look it up via OC ArcGIS.

    Returns up to `top_k` matching parcels normalized to our internal shape,
    or [] if no address could be parsed or no records matched.
    """
    address = _likely_address(query)
    if not address:
        return []

    # ArcGIS LIKE supports % wildcards but is case-sensitive. The dataset
    # stores addresses in upper case, so we uppercase the query.
    needle = address.upper()
    # Drop common noise tokens that aren't actually part of the address.
    for noise in (" CA", ", CA", ", CALIFORNIA"):
        needle = needle.replace(noise, "")
    needle = needle.strip()
    if not needle:
        return []

    where = f"SITE_ADDRESS LIKE '%{_escape(needle)}%'"
    params = {
        "where": where,
        "outFields": OUT_FIELDS,
        "returnGeometry": "false",
        "resultRecordCount": top_k,
        "orderByFields": "OBJECTID",
        "f": "json",
    }

    log.info("live ArcGIS lookup: needle=%r", needle)
    async with httpx.AsyncClient(verify=False, timeout=timeout_s) as client:
        r = await client.get(BASE_URL, params=params)
        r.raise_for_status()
        data = r.json()

    if "error" in data:
        log.warning("ArcGIS error on fallback: %s", data["error"])
        return []

    parcels: list[dict] = []
    for feat in data.get("features", []):
        p = _normalize(feat.get("attributes", {}))
        if p is not None:
            parcels.append(p)
    log.info("live ArcGIS lookup returned %d parcels for needle=%r", len(parcels), needle)
    return parcels
