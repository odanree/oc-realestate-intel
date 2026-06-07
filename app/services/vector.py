"""
Qdrant client wrapper — hybrid (dense + sparse) parcel search.

Collection layout:
  Named vectors:
    "dense"  — all-MiniLM-L6-v2 384-d cosine vector
    "sparse" — bag-of-tokens with server-side IDF (BM25-style)

Hybrid search uses Qdrant's `prefetch` + Reciprocal Rank Fusion (RRF).
The sparse vector rescues proper-noun queries that pure dense retrieval
drops (e.g. "Bridgeport Rd" — dense ranks "Irvine Ave" higher because
"Irvine" appears in many parcels and "Bridgeport" doesn't carry enough
similarity weight).

The embedder is pluggable: default is a zero stub so the system can boot
without a model download. Switch to sentence-transformers via
`enable_embeddings()`.
"""

from __future__ import annotations

import hashlib
import logging
import re
from collections import Counter
from typing import Protocol

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    Distance,
    Fusion,
    FusionQuery,
    Modifier,
    PointStruct,
    Prefetch,
    SparseVector,
    SparseVectorParams,
    VectorParams,
)

from app.config import settings

log = logging.getLogger(__name__)

VECTOR_SIZE = 384  # all-MiniLM-L6-v2 dimension
DENSE = "dense"
SPARSE = "sparse"

_TOKEN_RE = re.compile(r"[A-Za-z0-9]+")


class Embedder(Protocol):
    def embed(self, text: str) -> list[float]: ...


class _ZeroEmbedder:
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


# ---------------------------------------------------------------------------
# Sparse vector building (BM25-style with server-side IDF)
# ---------------------------------------------------------------------------


def _tokenize(text: str) -> list[str]:
    return [t.lower() for t in _TOKEN_RE.findall(text)]


def _token_index(token: str) -> int:
    """Stable 31-bit index for a token. Collisions are negligible for our
    vocab size (~10k tokens vs 2B buckets — birthday-bound is ~50k before
    50% collision probability).
    """
    digest = hashlib.sha256(token.encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big") >> 1  # keep 31 bits, non-negative


def _to_sparse(text: str) -> SparseVector:
    counts = Counter(_tokenize(text))
    if not counts:
        # Qdrant rejects empty sparse vectors; send a single zero-weight term.
        return SparseVector(indices=[0], values=[0.0])
    indices: list[int] = []
    values: list[float] = []
    for token, count in counts.items():
        indices.append(_token_index(token))
        values.append(float(count))
    return SparseVector(indices=indices, values=values)


# ---------------------------------------------------------------------------
# Collection management
# ---------------------------------------------------------------------------


def _vectors_config() -> dict:
    return {DENSE: VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE)}


def _sparse_config() -> dict:
    return {SPARSE: SparseVectorParams(modifier=Modifier.IDF)}


async def ensure_collection() -> None:
    client = _get_client()
    collections = await client.get_collections()
    if settings.qdrant_collection not in {c.name for c in collections.collections}:
        await client.create_collection(
            collection_name=settings.qdrant_collection,
            vectors_config=_vectors_config(),
            sparse_vectors_config=_sparse_config(),
        )
        log.info("Created Qdrant collection %s (dense + sparse)", settings.qdrant_collection)


async def recreate_collection() -> None:
    """Drop and recreate the collection — used by `seed --recreate`."""
    client = _get_client()
    try:
        await client.delete_collection(collection_name=settings.qdrant_collection)
    except Exception as e:
        log.info("delete_collection skipped: %s", e)
    await client.create_collection(
        collection_name=settings.qdrant_collection,
        vectors_config=_vectors_config(),
        sparse_vectors_config=_sparse_config(),
    )
    log.info("Recreated Qdrant collection %s (dense + sparse)", settings.qdrant_collection)


# ---------------------------------------------------------------------------
# Upsert + retrieve
# ---------------------------------------------------------------------------


async def upsert_parcel(apn: str, text: str, payload: dict) -> None:
    client = _get_client()
    point = PointStruct(
        id=_apn_to_int(apn),
        vector={
            DENSE: _embedder.embed(text),
            SPARSE: _to_sparse(text),
        },
        payload={**payload, "apn": apn},
    )
    await client.upsert(collection_name=settings.qdrant_collection, points=[point])


async def get_parcel_by_apn(apn: str) -> dict | None:
    """Direct lookup by APN — bypasses vector search entirely."""
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


# ---------------------------------------------------------------------------
# Hybrid search (dense + sparse fused via RRF)
# ---------------------------------------------------------------------------


async def search_parcels(query: str, top_k: int = 5) -> list[dict]:
    """Hybrid search: dense + sparse, fused via Reciprocal Rank Fusion."""
    client = _get_client()
    result = await client.query_points(
        collection_name=settings.qdrant_collection,
        prefetch=[
            Prefetch(query=_embedder.embed(query), using=DENSE, limit=top_k * 4),
            Prefetch(query=_to_sparse(query), using=SPARSE, limit=top_k * 4),
        ],
        query=FusionQuery(fusion=Fusion.RRF),
        limit=top_k,
        with_payload=True,
    )
    return [hit.payload or {} for hit in result.points]


async def comps_in_radius(apn: str, radius_miles: float = 0.5, top_k: int = 10) -> list[dict]:
    """Find comparable nearby parcels. Stub: filters by city in payload until
    lat/lng indexing lands."""
    target = await get_parcel_by_apn(apn)
    if not target:
        return []
    city = target.get("city")
    if not city:
        return []

    from qdrant_client.models import FieldCondition, Filter, MatchValue

    client = _get_client()
    result = await client.query_points(
        collection_name=settings.qdrant_collection,
        query=_embedder.embed(target.get("address") or ""),
        using=DENSE,
        query_filter=Filter(must=[FieldCondition(key="city", match=MatchValue(value=city))]),
        limit=top_k + 1,
        with_payload=True,
    )
    return [
        hit.payload or {}
        for hit in result.points
        if (hit.payload or {}).get("apn") != apn
    ][:top_k]


def _apn_to_int(apn: str) -> int:
    """Qdrant point IDs must be int or UUID — APNs are hyphenated digits."""
    return int(apn.replace("-", "").replace(" ", "") or "0")
