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

Then either curl:

```bash
curl -X POST http://localhost:8003/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"query": "Who owns parcel 461-211-62?"}'
```

…or launch the chat UI:

```powershell
cd web
npm install
npm run dev      # http://localhost:3003
```

The UI streams the agent's progress node-by-node — router → retrieval → summarize — and renders retrieved parcels + title chain in a side panel.

### Optional: Langfuse tracing

Tracing is opt-in. Sign up at [langfuse.com](https://langfuse.com) (free tier — 50k events/mo), grab a project's public + secret keys, drop them into `.env`:

```
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_HOST=https://us.cloud.langfuse.com   # or https://cloud.langfuse.com for EU
```

Restart the API. Every `/api/v1/query` invocation now produces a trace with one span per LangGraph node (router → retrieval → summarize) and a child generation span per Claude API call with token counts + latency.

Leaving the keys blank disables tracing — `app/observability.py` returns a no-op handler and there's zero runtime cost.

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
  test_sparse.py         Tokenizer + BM25 sparse vector building
  test_synthetic_owners.py  Synthetic title-chain invariants
  test_citations.py      APN extraction from answer text
web/
  src/app/
    page.tsx             Server component: header + Chat shell
    components/
      Chat.tsx           Streaming chat client component
      AgentTrace.tsx     Per-node status timeline
      ParcelList.tsx     Retrieved parcels side panel
      TitleChain.tsx     Title-chain side panel
    lib/api.ts           SSE stream parser (custom — no extra deps)
```

## Roadmap

**Weekend 1 — Data + Retrieval**
- [x] Project skeleton + docker-compose
- [x] Pluggable embedder + Qdrant collection bootstrap
- [x] Neo4j schema + owner-name normalization
- [x] OC Public Works ArcGIS ingestion — 2,000 Irvine parcels seeded; 702k available
- [x] sentence-transformers (all-MiniLM-L6-v2) real embeddings
- [x] Hybrid retrieval: APN-regex fast path → BM25 + dense fused via Reciprocal Rank Fusion
- [x] Synthetic owner + title-chain generator (assessor data is paywalled — see `app/ingestion/synthetic_owners.py` for the swap path to a real provider)
- [x] Neo4j seeding: Owner ↔ Parcel ↔ TRANSFERRED graph with temporally-consistent chains

**Weekend 2 — Agents**
- [x] LangGraph supervisor with router/retrieval/comparison/summarize
- [x] Four tools wired to data layer
- [x] FastAPI /query + /query/stream (SSE)
- [x] APN-grounded citations (regex-extracted from answer text)
- [x] Next.js 16 + React 19 + Tailwind 4 chat UI with live agent trace
- [x] Langfuse observability (opt-in via env vars; agent path traced)

**Weekend 3 — Eval + Polish**
- [x] [evalkit](../evalkit) integration: G-Eval faithfulness + answer relevance via LLM-as-judge
- [x] 16-case golden set + programmatic intent/citation/refusal metrics
- [x] Markdown report generator, `make eval` target
- [x] Model comparison sweep: Haiku 4.5 vs Sonnet 4.6 vs Opus 4.7 (`make sweep`)
- [ ] Expand to 30+ cases
- [ ] Loom demo + architecture diagram

## Model selection — what the data said

Ran the 16-case golden set against three Claude models, fixed judge (Sonnet 4.6):

| metric | `claude-haiku-4-5-20251001` | `claude-sonnet-4-6` | `claude-opus-4-7` |
|---|---|---|---|
| `intent_accuracy` | **1.00** | 0.94 | **1.00** |
| `citation_recall` | 1.00 | 1.00 | 1.00 |
| `citation_precision` | 1.00 | 1.00 | 1.00 |
| `refusal_correctness` | 1.00 | 1.00 | 1.00 |
| `faithfulness` | 9.78 | **9.91** | 9.84 |
| `answer_relevance` | 6.44 | **6.88** | 6.81 |

**Picked Sonnet 4.6** as the production model. Opus offered no measurable lift on faithfulness or answer relevance — it actually slightly underperformed Sonnet on both judge-scored dimensions. Haiku is viable as a cost-down option if needed (lags Sonnet by ~0.4 points on relevance), and notably matched Opus on intent routing. See [`evals/reports/`](evals/reports/) for the full sweep.

## Eval results

16-case golden set, judged by Claude Sonnet 4.6 via [evalkit](../evalkit).

| metric | score |
|---|---|
| `intent_accuracy` | 0.94 |
| `citation_recall` | 1.00 |
| `citation_precision` | 1.00 |
| `refusal_correctness` | 1.00 |
| `faithfulness` | **9.94** / 10 |
| `answer_relevance` | 6.81 / 10 |
| total judge cost | $0.07 |

Findings the eval surfaced as the system evolved:

1. **First run** — Faithfulness 9.54. Agent invented a URL (`ocassessor.gov`) on
   owner queries. Tightened the summarize prompt to forbid invented external
   resources.
2. **Owner data added** — Faithfulness dropped to 8.46 because the title-chain
   answers picked up speculation ("may indicate an arm's-length transaction").
   Added explicit "no interpretation, no characterization" rules to the prompt.
3. **Bug in the eval itself** — Faithfulness still 8.69 because the judge wasn't
   getting `graph_facts` as part of its context, so it correctly flagged
   every title-chain fact as ungrounded. Fixed `_format_context`; faithfulness
   jumped to **9.96**.

See [`evals/reports/`](evals/reports/) for full per-case detail.

## Technologies

`LangGraph` · `LangChain` · `Claude Sonnet 4.6` · `FastAPI` · `Qdrant` · `Neo4j` · `Postgres` · `SQLAlchemy 2 async` · `Pydantic v2` · `SSE` · `pytest-asyncio` · `sentence-transformers`

## License

MIT
