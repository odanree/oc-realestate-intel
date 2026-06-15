# ADR-0003: Neo4j for the owner / title-chain graph

- **Status:** Accepted
- **Date:** 2025-11-12
- **Deciders:** Danh Le

## Context

Two query shapes are graph-native, not table-native:

1. **Portfolio** — "What does FLORES FAMILY TR own?" Walk from an owner node to every parcel they hold, possibly through intermediary LLCs.
2. **Title chain** — "Show the title chain for 461-211-62." Order a sequence of transfer edges by date; surface grantor/grantee/price/doc-number at each hop.

Both queries are short-walk traversals with arbitrary join depth. Expressing them in SQL would mean either recursive CTEs or repeated joins on a transfers table. Performance is fine at our seed size — the cost is **query readability and the burden on every new contributor to keep the SQL straight**.

## Decision

Use **Neo4j** as a sidecar to Postgres. Owners, parcels, and transfer events are nodes; `OWNS`, `GRANTOR_OF`, `GRANTEE_OF` are edges. Postgres remains the system of record for parcel attributes; Neo4j is a derived projection rebuilt from the seed pipeline.

Cypher queries live in `app/services/graph.py`. The supervisor's retrieval node routes `intent=portfolio` directly to Neo4j (skipping vector search entirely) and routes `intent=title_chain` to Neo4j *after* a Qdrant APN lookup resolves the target parcel.

## Consequences

**Positive**
- `MATCH (o:Owner {name: $name})-[:OWNS]->(p:Parcel) RETURN p` reads exactly like the question it answers. Title-chain queries similarly read like the spec.
- Pattern-matching on ownership webs (LLC → trust → individual) is a one-line Cypher addition when we add multi-hop. Doing the same in SQL would mean a new recursive CTE per pattern.
- Schema is dictated by the questions, not by the source tables. We can model "transfer event" as a first-class node with attributes (price, doc number, date), which is awkward in a relational shape.

**Negative**
- Two databases to provision, back up, and reason about consistency between. Today the Neo4j projection is fully derivable from Postgres, so divergence is a re-seed away from being fixed — but this is real operational complexity.
- Neo4j Community Edition has no causal clustering. Production HA would require AuraDB or migration to Memgraph.
- `OWNS` and `transfer` data is currently synthetic — see [ADR-0004](0004-synthetic-owners-with-provenance-flagging.md). If a real owner provider is wired in, the graph rebuild path has to preserve provenance flags.

## Alternatives considered

- **Recursive CTEs on Postgres** — rejected. Works, but each new traversal pattern means non-trivial SQL and the query plans are opaque to non-DBAs. The friction would compound as we add owner-resolution features.
- **Memgraph** — viable. Pure Cypher, in-memory, faster. Not picked because Neo4j has the larger ecosystem (Bloom for visualization, the official Python driver, every Cypher tutorial online) and we are nowhere near needing Memgraph's perf envelope.
- **Property graph on top of Postgres (Apache AGE)** — rejected. The extension is young; we did not want to be the production validator for a new stack component when the alternative is a battle-tested DB.

## Links

- Implementation: `app/services/graph.py`, `app/ingestion/synthetic_owners.py`
- Related: [ADR-0004](0004-synthetic-owners-with-provenance-flagging.md)
