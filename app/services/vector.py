"""
Qdrant client wrapper — parcel embeddings + sales comps.

The embedder is intentionally pluggable: default is a stub that returns zeros
so the rest of the system can be developed without a model download.
Switch to sentence-transformers via `enable_embeddings()`.
"""

from __future__ import annotations

import logging
from typing import Protocol

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from app.config import settings

log = logging.getLogger(__name__)

VECTOR_SIZE = 384  # all-MiniLM-L6-v2 dimension


class Embedder(Protocol):
    def embed(self, text: str) -> list[float]: ...


class _ZeroEmbedder:
    """Placeholder that lets the system run without a real model."""

    def embed(self, text: str) -> list[float]:
        return [0.0] * VECTOR_SIZE


_embedder: Embedder = _ZeroEmbedder()
_client: AsyncQdrantClient | None = None


def enable_embeddings() -> None:
    """Swap the zero embedder for sentence-transformers."""
    global _embedder
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer("all-MiniLM-L6-v2")

    class _STEmbedder:
        def embed(self, text: str) -> list[float]:
            return model.encode(text, normalize_embeddings=True).tolist()

    _embedder = _STEmbedder()


def _get_client() -> AsyncQdrantClient:
    global _client
    if _client is None:
        _client = AsyncQdrantClient(url=settings.qdrant_url)
    return _client


async def ensure_collection() -> None:
    client = _get_client()
    collections = await client.get_collections()
    if settings.qdrant_collection not in {c.name for c in collections.collections}:
        await client.create_collection(
            collection_name=settings.qdrant_collection,
            vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
        )
        log.info("Created Qdrant collection %s", settings.qdrant_collection)


async def recreate_collection() -> None:
    """Drop and recreate the collection — used by `seed --recreate`."""
    client = _get_client()
    try:
        await client.delete_collection(collection_name=settings.qdrant_collection)
    except Exception as e:
        log.info("delete_collection skipped: %s", e)
    await client.create_collection(
        collection_name=settings.qdrant_collection,
        vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
    )
    log.info("Recreated Qdrant collection %s", settings.qdrant_collection)


async def upsert_parcel(apn: str, text: str, payload: dict) -> None:
    client = _get_client()
    vector = _embedder.embed(text)
    point = PointStruct(id=_apn_to_int(apn), vector=vector, payload={**payload, "apn": apn})
    await client.upsert(collection_name=settings.qdrant_collection, points=[point])


async def get_parcel_by_apn(apn: str) -> dict | None:
    """Direct lookup by APN — bypasses vector search."""
    client = _get_client()
    point_id = _apn_to_int(apn)
    try:
        points = await client.retrieve(
            collection_name=settings.qdrant_collection,
            ids=[point_id],
            with_payload=True,
        )
    except Exception as e:
        log.warning("retrieve(%s) failed: %s", apn, e)
        return None
    return points[0].payload if points else None


async def search_parcels(query: str, top_k: int = 5) -> list[dict]:
    client = _get_client()
    vector = _embedder.embed(query)
    result = await client.query_points(
        collection_name=settings.qdrant_collection,
        query=vector,
        limit=top_k,
    )
    return [hit.payload or {} for hit in result.points]


async def comps_in_radius(apn: str, radius_miles: float = 0.5, top_k: int = 10) -> list[dict]:
    """Find nearby recent sales. Stub: filters by zip in payload until lat/lng indexing lands."""
    client = _get_client()
    # Resolve target parcel to find its zip / neighborhood
    targets = await search_parcels(apn, top_k=1)
    if not targets:
        return []
    zip_code = targets[0].get("zip")
    if not zip_code:
        return []

    from qdrant_client.models import FieldCondition, Filter, MatchValue

    result = await client.query_points(
        collection_name=settings.qdrant_collection,
        query=_embedder.embed(f"recent sale {zip_code}"),
        query_filter=Filter(
            must=[FieldCondition(key="zip", match=MatchValue(value=zip_code))]
        ),
        limit=top_k,
    )
    return [
        hit.payload or {}
        for hit in result.points
        if (hit.payload or {}).get("apn") != apn
    ]


def _apn_to_int(apn: str) -> int:
    """Qdrant point IDs must be int or UUID — APNs are hyphenated digits."""
    return int(apn.replace("-", "").replace(" ", "") or "0")
