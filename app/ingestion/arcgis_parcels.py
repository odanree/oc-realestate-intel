"""
Orange County (CA) parcels ingestion from the public OCPW ArcGIS FeatureServer.

Endpoint: https://www.ocgis.com/arcpub/rest/services/Map_Layers/Parcels/MapServer/0

The layer has 702k+ parcels but only a sparse schema (no owner / sale price)
because owner data is paywalled at the assessor. We get APN, address, year_built,
and bedroom count — enough for hybrid retrieval and routing demos.

We page through results using `resultOffset` (1000 records per page, server cap).
Server certificates intermittently use intermediate chains, so we tolerate
that with verify=False in dev. Switch to a pinned CA bundle for production.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator

import httpx

log = logging.getLogger(__name__)

BASE_URL = (
    "https://www.ocgis.com/arcpub/rest/services/Map_Layers/Parcels/MapServer/0/query"
)
PAGE_SIZE = 1000  # server-enforced cap
OUT_FIELDS = "SITE_ADDRESS,ASSESSMENT_NO,YEAR_BUILT,NBR_BEDROOMS"


async def stream_parcels(
    where: str = "1=1",
    limit: int | None = None,
    timeout_s: float = 30.0,
) -> AsyncIterator[dict]:
    """Yield parcel dicts from the OC ArcGIS FeatureServer.

    Args:
        where: ArcGIS SQL-like WHERE clause. Examples:
            "1=1"                                       — everything
            "SITE_ADDRESS LIKE '%IRVINE%'"              — Irvine parcels
            "SITE_ADDRESS LIKE '%NEWPORT BEACH%'"       — Newport Beach
        limit: Stop after this many records.
        timeout_s: per-request timeout.
    """
    offset = 0
    yielded = 0

    async with httpx.AsyncClient(verify=False, timeout=timeout_s) as client:
        while True:
            params = {
                "where": where,
                "outFields": OUT_FIELDS,
                "returnGeometry": "false",
                "resultRecordCount": PAGE_SIZE,
                "resultOffset": offset,
                "orderByFields": "OBJECTID",
                "f": "json",
            }
            r = await client.get(BASE_URL, params=params)
            r.raise_for_status()
            data = r.json()

            if "error" in data:
                raise RuntimeError(f"ArcGIS error: {data['error']}")

            features = data.get("features", [])
            if not features:
                log.info("ingestion done: yielded=%d from offset=%d", yielded, offset)
                return

            for feat in features:
                attrs = feat.get("attributes", {})
                parcel = _normalize(attrs)
                if parcel is None:
                    continue
                yield parcel
                yielded += 1
                if limit is not None and yielded >= limit:
                    return

            offset += PAGE_SIZE
            log.info("ingestion: offset=%d yielded=%d", offset, yielded)


def _normalize(attrs: dict) -> dict | None:
    """Map ArcGIS field names to our internal schema."""
    apn = (attrs.get("ASSESSMENT_NO") or "").strip()
    if not apn:
        return None
    address = (attrs.get("SITE_ADDRESS") or "").strip()
    if not address:
        return None

    city, zip_code = _parse_city(address)
    year_built = attrs.get("YEAR_BUILT") or None
    try:
        year_built = int(year_built) if year_built else None
    except (TypeError, ValueError):
        year_built = None

    return {
        "apn": apn,
        "address": address,
        "city": city,
        "zip": zip_code,
        "year_built": year_built,
        "bedrooms": attrs.get("NBR_BEDROOMS") or None,
        # Owner data is paywalled at the assessor — left blank for now.
        "owner": None,
        "owner_kind": None,
    }


def _parse_city(address: str) -> tuple[str, str]:
    """Best-effort city extraction. Addresses arrive as e.g.:
       "2060 W CATALPA AVE ANAHEIM"
       "102 IRVINE COVE DR LAGUNA BEACH"
       "1 IRVINE PARK RD " (no city)
    The trailing token (or two) is the city. No zip in this dataset.
    """
    tokens = address.strip().split()
    if len(tokens) < 2:
        return "", ""

    # Two-word cities (Laguna Beach, Newport Beach, Mission Viejo, Santa Ana, etc.)
    two_word_cities = {
        "LAGUNA BEACH", "NEWPORT BEACH", "MISSION VIEJO", "SANTA ANA",
        "HUNTINGTON BEACH", "DANA POINT", "FOUNTAIN VALLEY", "GARDEN GROVE",
        "BUENA PARK", "COSTA MESA", "ALISO VIEJO", "LADERA RANCH",
        "LA HABRA", "LA PALMA", "LAKE FOREST", "RANCHO SANTA MARGARITA",
        "SAN CLEMENTE", "SAN JUAN CAPISTRANO", "SEAL BEACH", "VILLA PARK",
        "YORBA LINDA",
    }
    tail2 = " ".join(tokens[-2:]).upper()
    if tail2 in two_word_cities:
        return tail2, ""

    return tokens[-1].upper(), ""
