"""
One-shot: snapshot OC parcels from the public ArcGIS endpoint to a gzipped
JSON file in the repo. Production containers read from this snapshot
because the Hetzner VPS can't reach www.ocgis.com (geo-blocked).

Usage (run from your dev machine which CAN reach ArcGIS):

    python -m scripts.snapshot_parcels                              # default 10k
    python -m scripts.snapshot_parcels --limit 20000
    python -m scripts.snapshot_parcels --out data/oc-parcels.json.gz

Then commit data/oc-parcels.json.gz. The prod entrypoint will load from it.
"""

from __future__ import annotations

import argparse
import asyncio
import gzip
import json
import logging
from pathlib import Path

from app.ingestion.arcgis_parcels import stream_parcels

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)


# Default per-city quotas. ArcGIS returns results in OBJECTID order, and
# Anaheim parcels happen to have low OBJECTIDs — a flat OR'd WHERE with one
# 10k LIMIT returns ~9900 Anaheim and almost zero of everything else. So we
# query each city independently with its own quota and concat.
DEFAULT_QUOTAS = {
    "IRVINE": 3000,
    "NEWPORT BEACH": 2500,
    "ANAHEIM": 2500,
    "ORANGE": 2000,  # uses "% ORANGE%" to match end-of-address only
}


def _where_for(city: str) -> str:
    # The leading space anchors to end-of-address for ORANGE so we don't pick
    # up "ORANGE BLOSSOM CIRCLE" in other cities.
    pattern = f"% {city}" if city == "ORANGE" else f"%{city}%"
    return f"SITE_ADDRESS LIKE '{pattern}'"


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--quotas",
        default=",".join(f"{c}={n}" for c, n in DEFAULT_QUOTAS.items()),
        help="Comma-separated CITY=count quotas (e.g. IRVINE=3000,ORANGE=2000).",
    )
    parser.add_argument("--out", default="data/oc-parcels.json.gz")
    args = parser.parse_args()

    quotas: dict[str, int] = {}
    for item in args.quotas.split(","):
        city, _, n = item.partition("=")
        quotas[city.strip()] = int(n)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    parcels: list[dict] = []
    seen_apns: set[str] = set()
    for city, quota in quotas.items():
        log.info("fetching %s (quota=%d)", city, quota)
        before = len(parcels)
        async for p in stream_parcels(where=_where_for(city), limit=quota):
            apn = p.get("apn")
            if apn and apn not in seen_apns:
                seen_apns.add(apn)
                parcels.append(p)
        log.info("  -> %s added %d parcels (total=%d)",
                 city, len(parcels) - before, len(parcels))

    log.info("writing %d parcels to %s", len(parcels), out_path)
    with gzip.open(out_path, "wt", encoding="utf-8") as f:
        json.dump(parcels, f)
    log.info("done. %s is %.1f KB", out_path, out_path.stat().st_size / 1024)


if __name__ == "__main__":
    asyncio.run(main())
