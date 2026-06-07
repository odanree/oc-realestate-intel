"""
Seed Postgres + Qdrant with real OC parcels from the public ArcGIS endpoint.

Usage:
    python -m scripts.seed                        # default: 2000 Irvine parcels
    python -m scripts.seed --where "1=1" --limit 5000
    python -m scripts.seed --where "SITE_ADDRESS LIKE '%NEWPORT BEACH%'"
    python -m scripts.seed --no-embeddings        # skip real embeddings (faster)

Neo4j is not seeded yet because the ArcGIS parcel layer doesn't expose
owner data — that lives behind the assessor paywall. The Neo4j-backed tools
(owner_holdings, title_chain) will return [] until that data source lands.
"""

from __future__ import annotations

import argparse
import asyncio
import logging

from sqlalchemy import select

from app.config import settings
from app.ingestion.arcgis_parcels import stream_parcels
from app.models.parcel import Base, Parcel
from app.services import vector as vector_service
from app.services.db import SessionLocal, engine

logging.basicConfig(level=settings.log_level)
log = logging.getLogger(__name__)


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--where",
        default="SITE_ADDRESS LIKE '%IRVINE%'",
        help="ArcGIS WHERE clause. Default: Irvine parcels.",
    )
    parser.add_argument("--limit", type=int, default=2000)
    parser.add_argument("--no-embeddings", action="store_true", help="Use zero embedder")
    parser.add_argument("--recreate", action="store_true", help="Drop & recreate parcels table")
    args = parser.parse_args()

    if not args.no_embeddings:
        log.info("Loading sentence-transformers (first run will download model)...")
        vector_service.enable_embeddings()

    async with engine.begin() as conn:
        if args.recreate:
            await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    if args.recreate:
        await vector_service.recreate_collection()
    else:
        await vector_service.ensure_collection()

    upserted = 0
    async with SessionLocal() as session:
        async for p in stream_parcels(where=args.where, limit=args.limit):
            await _upsert_parcel(session, p)
            await _upsert_qdrant(p)
            upserted += 1
            if upserted % 200 == 0:
                await session.commit()
                log.info("upserted=%d", upserted)
        await session.commit()

    log.info("seed complete: upserted=%d parcels", upserted)


async def _upsert_parcel(session, p: dict) -> None:
    existing = await session.execute(select(Parcel).where(Parcel.apn == p["apn"]))
    row = existing.scalar_one_or_none()
    if row is None:
        session.add(Parcel(
            apn=p["apn"],
            address=p["address"],
            city=p.get("city") or "",
            zip=p.get("zip") or "",
            owner=p.get("owner"),
            owner_kind=p.get("owner_kind"),
            year_built=p.get("year_built"),
        ))
    else:
        row.address = p["address"]
        row.city = p.get("city") or ""
        row.year_built = p.get("year_built")


async def _upsert_qdrant(p: dict) -> None:
    text = f"{p['address']} {p.get('city') or ''}".strip()
    await vector_service.upsert_parcel(p["apn"], text, p)


if __name__ == "__main__":
    asyncio.run(main())
