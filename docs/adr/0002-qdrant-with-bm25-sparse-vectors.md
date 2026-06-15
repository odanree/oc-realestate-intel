# ADR-0002: Qdrant with BM25 + dense sparse vectors over pgvector

- **Status:** Accepted
- **Date:** 2025-11-12
- **Deciders:** Danh Le

## Context

Parcel queries fall into three shapes:

1. **APN lookup** — "What is parcel 461-211-62?" Exact ID, no semantic search needed.
2. **Address search** — "Find parcels on Bridgeport Rd in Irvine." Proper nouns dominate; one wrong token swap wrecks the result.
3. **Description search** — "Single-family homes built before 1970 near the bay." Paraphrase-heavy; semantic similarity wins.

Pure dense retrieval failed shape (2): the embedding model treated `Irvine` as a strong signal because it appears in thousands of parcel descriptions, and ranked "Irvine Ave, Newport Beach" above "Bridgeport Rd, Irvine" — the user's actual target. The rare token `Bridgeport` did not carry enough cosine weight to overcome it.

Postgres is already in the stack as the parcel cache, so `pgvector` was the cheap default.

## Decision

Use **Qdrant** for the vector store with **named vectors**: one dense (sentence-transformers `all-MiniLM-L6-v2`) and one sparse (Qdrant-native BM25). Fuse at query time with **Reciprocal Rank Fusion** (RRF). The retrieval node also short-circuits to `retrieve(by_id)` when an APN regex matches the query — that path does not touch search at all.

## Consequences

**Positive**
- Sparse leg rescues exact-token queries. Bridgeport-vs-Irvine, the originating failure case, now ranks correctly.
- RRF is hyperparameter-free between the two retrievers — no weight tuning per query class.
- Qdrant's `prefer_grpc=True` mode keeps p95 latency under 40ms at our seed size; we are not the bottleneck.
- APN fast-path bypasses search entirely. `retrieve(by_id)` is O(1) and was wrong to leave on the hybrid path; semantic search of an ID returns garbage.

**Negative**
- Two indexes to maintain. Re-seed has to populate both vector types or hybrid queries silently degrade to dense-only.
- Operationally heavier than pgvector — separate process, separate volume, separate health check. For a single-node deployment this is acceptable; at scale we would re-evaluate.
- Sentence-transformers inference adds ~80MB of model weights to the container and CPU embedding latency of ~25ms per query. Acceptable for our QPS.

## Alternatives considered

- **pgvector only** — rejected after the Bridgeport failure. Adding BM25 to Postgres means `pg_trgm` or `tsvector` on a separate column with manual fusion code; we would be rebuilding what Qdrant ships.
- **Elasticsearch / OpenSearch** — rejected. The BM25 story is excellent but the vector story lags Qdrant on quantization and named-vector support, and the operational footprint is much larger than we need.
- **Vespa / Weaviate** — not evaluated. Qdrant's named-vectors + Python client + low resource floor were sufficient.

## Links

- Implementation: `app/services/vector.py`, `app/agents/supervisor.py` (retrieval node)
- Evidence: 16-case eval moved from intermittent address misses to 1.00 citation precision after the sparse leg was added.
