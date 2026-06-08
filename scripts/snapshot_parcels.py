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


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--where",
        default=(
            "(SITE_ADDRESS LIKE '%IRVINE%' "
            "OR SITE_ADDRESS LIKE '%NEWPORT BEACH%' "
            "OR SITE_ADDRESS LIKE '%ANAHEIM%' "
            "OR SITE_ADDRESS LIKE '% ORANGE%')"
        ),
    )
    parser.add_argument("--limit", type=int, default=10000)
    parser.add_argument("--out", default="data/oc-parcels.json.gz")
    args = parser.parse_args()

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    parcels: list[dict] = []
    async for p in stream_parcels(where=args.where, limit=args.limit):
        parcels.append(p)
        if len(parcels) % 500 == 0:
            log.info("fetched %d parcels", len(parcels))

    log.info("writing %d parcels to %s", len(parcels), out_path)
    with gzip.open(out_path, "wt", encoding="utf-8") as f:
        json.dump(parcels, f)
    log.info("done. %s is %.1f KB", out_path, out_path.stat().st_size / 1024)


if __name__ == "__main__":
    asyncio.run(main())
