"""
Orange County Assessor scraper — stub.

The real implementation will fetch from the OC Assessor public lookup,
parse the HTML, and yield Parcel records. For now it returns synthetic
records so the downstream pipeline can be exercised end-to-end.

TODO:
  - Replace _SYNTHETIC with httpx GET to https://www.ocgov.com/assessor/...
  - Parse with BeautifulSoup, respect rate limits (0.5 req/sec).
  - Persist via SessionLocal in batches of 100.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator

log = logging.getLogger(__name__)

_SYNTHETIC = [
    {
        "apn": "934-21-145",
        "address": "100 Pacific Coast Hwy",
        "city": "Newport Beach",
        "zip": "92660",
        "owner": "IRVINE COMPANY LLC",
        "owner_kind": "llc",
        "use_code": "Commercial",
        "assessed_value": 12_500_000,
    },
    {
        "apn": "456-78-901",
        "address": "1 Park Plaza",
        "city": "Irvine",
        "zip": "92614",
        "owner": "SMITH FAMILY TR",
        "owner_kind": "trust",
        "use_code": "Single Family",
        "assessed_value": 1_850_000,
    },
]


async def stream_parcels(zip_code: str | None = None) -> AsyncIterator[dict]:
    for p in _SYNTHETIC:
        if zip_code and p["zip"] != zip_code:
            continue
        yield p
