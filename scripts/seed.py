"""Seed Postgres + Qdrant + Neo4j with the synthetic ingestion sample."""

from __future__ import annotations

import asyncio
import logging

from app.config import settings
from app.ingestion.oc_assessor import stream_parcels
from app.services import graph as graph_service
from app.services import vector as vector_service

logging.basicConfig(level=settings.log_level)
log = logging.getLogger(__name__)


async def main() -> None:
    await vector_service.ensure_collection()
    await graph_service.ensure_constraints()

    async for p in stream_parcels():
        embed_text = f"{p['address']} {p['city']} {p['zip']} {p.get('owner', '')}"
        await vector_service.upsert_parcel(p["apn"], embed_text, p)
        log.info("Seeded %s — %s", p["apn"], p["address"])

    await graph_service.close()


if __name__ == "__main__":
    asyncio.run(main())
