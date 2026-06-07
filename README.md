# oc-realestate-intel

Multi-agent LangGraph system over Orange County real estate + title data. Built around hybrid retrieval (Qdrant vector index + Neo4j ownership graph) and a Claude Sonnet 4.6 reasoning loop.

## What it does

Ask natural-language questions about Orange County parcels:

> "Show me everything Irvine Company owns within 92614."
> "Trace the title chain on 100 Pacific Coast Hwy back to 2015."
> "Compare 1 Park Plaza to recent sales within half a mile."

The system routes the query, retrieves grounded facts from a vector + graph + relational hybrid, and answers with APN-level citations.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                 FastAPI Gateway (/query)                     │
│  · POST /api/v1/query          one-shot JSON                 │
│  · GET  /api/v1/query/stream   SSE updates per node          │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│             LangGraph Supervisor                             │
│                                                              │
│   START → router ─┬─→ retrieval ───┐                        │
│                   │                 ├─→ summarize → END     │
│                   └─→ comparison ──┘                        │
│                                                              │
│   Tools: parcel_lookup, owner_holdings,                      │
│          comps_in_radius, title_chain                        │
└──────────────────────┬──────────────────────────────────────┘
                       │
   ┌──────────┬────────┴────────┬─────────────┐
   │          │                 │             │
┌──▼─────┐ ┌──▼──────┐  ┌──────▼─────┐  ┌────▼────┐
│ Qdrant │ │  Neo4j  │  │  Postgres  │  │ Claude  │
│ vector │ │  graph  │  │  cached    │  │ Sonnet  │
│ index  │ │ owners+ │  │  parcels + │  │  4.6    │
│        │ │ deeds   │  │ transfers  │  │         │
└────────┘ └─────────┘  └────────────┘  └─────────┘
```

## Quick start

```powershell
# 1. Start data stores
docker compose up -d

# 2. Configure
Copy-Item .env.example .env
# edit ANTHROPIC_API_KEY

# 3. Install
python -m venv .venv
.\.venv\Scripts\activate
pip install -e ".[dev,embeddings]"

# 4. Seed 2,000 real Irvine parcels from OC Public Works ArcGIS
python -m scripts.seed --recreate --limit 2000
# Or scope to a different area:
python -m scripts.seed --recreate --where "SITE_ADDRESS LIKE '%NEWPORT BEACH%'" --limit 5000

# 5. Run
uvicorn app.main:app --reload --port 8000
```

Then:

```bash
curl -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"query": "What does Irvine Company own in 92614?"}'
```

## Project layout

```
app/
  main.py                FastAPI app + lifespan hooks
  config.py              pydantic-settings
  agents/
    state.py             LangGraph AgentState TypedDict
    supervisor.py        StateGraph + router/retrieval/comparison/summarize nodes
    tools.py             @tool wrappers over service-layer queries
  routers/
    query.py             /query and /query/stream (SSE)
    health.py            /health
  services/
    db.py                Async Postgres session
    vector.py            Qdrant client (pluggable embedder)
    graph.py             Neo4j driver + Cypher queries
  ingestion/
    oc_assessor.py       Scraper stub (synthetic for now)
  models/
    parcel.py            SQLAlchemy: Parcel, TitleTransfer
  schemas/
    query.py             Request/response Pydantic models
scripts/
  seed.py                Seed all three data stores
tests/
  test_supervisor.py     Router classification + node wiring
  test_graph_normalize.py Owner-name normalization
```

## Roadmap

**Weekend 1 — Data + Retrieval**
- [x] Project skeleton + docker-compose
- [x] Pluggable embedder + Qdrant collection bootstrap
- [x] Neo4j schema + owner-name normalization
- [x] OC Public Works ArcGIS ingestion — 2,000 Irvine parcels seeded; 702k available
- [x] sentence-transformers (all-MiniLM-L6-v2) real embeddings
- [x] Hybrid retrieval: APN-regex fast path + dense vector fallback
- [ ] Owner ingestion (assessor data is paywalled — needs separate scrape or API)
- [ ] BM25 layer for proper-noun street searches

**Weekend 2 — Agents**
- [x] LangGraph supervisor with router/retrieval/comparison/summarize
- [x] Four tools wired to data layer
- [x] FastAPI /query + /query/stream (SSE)
- [x] APN-grounded citations (regex-extracted from answer text)
- [ ] LangSmith / Langfuse tracing
- [ ] Next.js 15 chat UI

**Weekend 3 — Eval + Polish**
- [ ] G-Eval scorecard via [evalkit](../evalkit) (faithfulness, answer relevance, citation precision)
- [ ] 30-question golden set; compare Sonnet 4.6 vs Opus 4.7 vs GPT-4o
- [ ] Loom demo + architecture diagram

## Technologies

`LangGraph` · `LangChain` · `Claude Sonnet 4.6` · `FastAPI` · `Qdrant` · `Neo4j` · `Postgres` · `SQLAlchemy 2 async` · `Pydantic v2` · `SSE` · `pytest-asyncio` · `sentence-transformers`

## License

MIT
