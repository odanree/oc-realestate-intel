"""
Seed Postgres + Qdrant + Neo4j with OC parcels.

Parcels come from the public OC Public Works ArcGIS endpoint (real data,
702k available, address + APN + year_built).

Owners come from a SYNTHETIC generator (real assessor data is paywalled —
see app/ingestion/synthetic_owners.py for why and how to swap in a real
provider).

Usage:
    python -m scripts.seed                        # default: 2000 Irvine parcels
    python -m scripts.seed --where "1=1" --limit 5000
    python -m scripts.seed --where "SITE_ADDRESS LIKE '%NEWPORT BEACH%'"
    python -m scripts.seed --no-embeddings        # skip real embeddings (faster)
    python -m scripts.seed --no-graph             # skip Neo4j seed
"""

from __future__ import annotations

import argparse
import asyncio
import logging

from sqlalchemy import select

from app.config import settings
from app.ingestion.arcgis_parcels import stream_parcels
from app.ingestion.synthetic_owners import generate_for_parcels
from app.models.parcel import Base, Parcel
from app.services import graph as graph_service
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
    parser.add_argument("--no-graph", action="store_true", help="Skip Neo4j seed")
    parser.add_argument("--recreate", action="store_true", help="Drop & recreate everything")
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

    if not args.no_graph:
        await graph_service.ensure_constraints()
        if args.recreate:
            await graph_service.clear_graph()

    upserted = 0

    async def consume(stream):
        nonlocal upserted
        async with SessionLocal() as session:
            async for enriched in stream:
                await _upsert_parcel(session, enriched)
                await _upsert_qdrant(enriched)
                if not args.no_graph:
                    await graph_service.upsert_parcel_with_chain(enriched)
                upserted += 1
                if upserted % 200 == 0:
                    await session.commit()
                    log.info("upserted=%d", upserted)
            await session.commit()

    await consume(_enrich(stream_parcels(where=args.where, limit=args.limit)))

    await graph_service.close()
    log.info("seed complete: upserted=%d parcels", upserted)


async def _enrich(parcel_stream):
    """Wrap raw parcels with synthetic owner + title-chain data.

    We buffer in small batches so the synthetic generator (which uses
    a shared LLC pool for cross-parcel reuse) sees enough records to
    create realistic multi-parcel-LLC patterns.
    """
    batch: list[dict] = []
    async for p in parcel_stream:
        batch.append(p)
        if len(batch) >= 50:
            for enriched in generate_for_parcels(batch):
                yield enriched
            batch.clear()
    if batch:
        for enriched in generate_for_parcels(batch):
            yield enriched


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
        row.owner = p.get("owner")
        row.owner_kind = p.get("owner_kind")


async def _upsert_qdrant(p: dict) -> None:
    text = f"{p['address']} {p.get('city') or ''}".strip()
    await vector_service.upsert_parcel(p["apn"], text, p)


if __name__ == "__main__":
    asyncio.run(main())
