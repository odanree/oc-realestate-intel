# oc-realestate-intel

**Multi-agent LangGraph system over Orange County real-estate + title data.** Hybrid retrieval (BM25 + dense + RRF), live fallback over the full 702k-parcel OC ArcGIS layer, a 5-intent supervisor, evalkit-judged faithfulness, and Langfuse end-to-end tracing — every retrieval path tagged, every answer fact-grounded, every assertion provenance-flagged when the underlying source is synthetic.

`LangGraph` · `LangChain` · `Claude Sonnet 4.6` · `FastAPI` · `SSE` · `Qdrant` (dense + BM25) · `Neo4j` · `Postgres` · `Pydantic v2` · `sentence-transformers` · `Next.js 16` · `React 19` · `Tailwind 4` · `Langfuse` · `evalkit`

| | |
|---|---|
| **Faithfulness** (LLM-judged, 16 cases) | **9.94 / 10** |
| **Citation precision / recall / refusal** | 1.00 each |
| **Model picked by data** | Sonnet 4.6 (Opus offered no measurable lift) |
| **Eval cost / run** | ~$0.07 |

---

## Try it

```powershell
docker compose up -d                                 # Postgres + Qdrant + Neo4j
python -m venv .venv && .\.venv\Scripts\activate
pip install -e ".[dev,embeddings]"
Copy-Item .env.example .env                          # add ANTHROPIC_API_KEY
python -m scripts.seed --recreate --limit 2000       # 2k real Irvine parcels
uvicorn app.main:app --reload --port 8003

cd web && npm install && npm run dev                 # http://localhost:3003
```

Optional Langfuse setup is in [docs/langfuse.md](docs/langfuse.md) — drop two keys in `.env` and every query produces a tagged trace with token counts, latency, costs, and judge scores.

---

## Screenshots

<!--
Add these three screenshots (PNG, ~1200px wide) into docs/screenshots/:
  1. chat-ui.png        — the chat UI showing a query + answer + agent trace timeline + citation chips
  2. langfuse-trace.png — a single Langfuse trace waterfall (router → retrieval → summarize → ChatAnthropic)
  3. langfuse-filtered.png — the traces list filtered by tag (e.g. intent:portfolio)
-->

| Chat UI streaming | Langfuse trace waterfall |
|---|---|
| ![Chat UI](docs/screenshots/chat-ui.png) | ![Langfuse trace](docs/screenshots/langfuse-trace.png) |

| Tag filter: every `intent:portfolio` query |
|---|
| ![Tag filter](docs/screenshots/langfuse-filtered.png) |

---

## How it works

### System architecture

```mermaid
graph TB
    User([User]) -->|natural-language query| Web[Next.js 16 chat UI]
    Web -->|SSE stream| API[FastAPI gateway]
    API --> Sup[LangGraph supervisor]

    Sup -->|router + summarize LLM| Claude[(Claude Sonnet 4.6)]
    Sup --> Hybrid{Hybrid retrieval}

    Hybrid -->|APN regex match| QdrantID[(Qdrant<br>retrieve by ID)]
    Hybrid -->|street + semantic| QdrantHy[(Qdrant<br>dense + BM25 RRF)]
    Hybrid -->|owner name| Neo4j[(Neo4j<br>owner graph)]
    Hybrid -.->|local miss| Live[OC ArcGIS<br>live FeatureServer]

    QdrantID --> Pg[(Postgres<br>cached parcels)]
    QdrantHy --> Pg
    Neo4j --> Pg
    Live --> Pg

    API -.->|trace + tags + scores| LF[(Langfuse)]
    Eval[scripts/eval.py via evalkit] -.->|trace + scores| LF
```

### Agent flow

```mermaid
graph LR
    START([START]) --> R{router}
    R -->|unknown| END([END])
    R -->|compare| Cmp[comparison]
    R -->|lookup / summarize<br>title_chain / portfolio| Ret[retrieval]
    Ret --> Sum[summarize]
    Cmp --> Sum
    Sum --> END
```

The router emits structured JSON `{intent, owner_name?}` and tags the trace with `intent:<value>`. The retrieval node then picks one of four sub-paths and tags `source:<value>`:

| `intent` | Retrieval path | Why |
|---|---|---|
| `lookup` / `summarize` / `title_chain` with APN in query | Qdrant `retrieve(by_id)` | Fast O(1) lookup; semantic search is wrong for IDs |
| `lookup` / `summarize` with address | BM25 + dense via Qdrant RRF | Sparse rescues proper nouns; dense rescues paraphrases |
| `portfolio` | Neo4j `owner_holdings` | The graph IS the right data structure here |
| Any of the above with no local match | Live OC ArcGIS FeatureServer | Reaches the full 702k parcels |

The live fallback uses a relevance heuristic — hybrid search _always_ returns top-k, so `if not parcels:` never fires for out-of-seed addresses. Instead we check whether the query's house-number actually appears in any returned parcel's address, and only then hit the live API.

### Eval-driven dev loop

```mermaid
graph LR
    Q[Production query] -->|tagged trace| LF[(Langfuse)]
    Golden[16-case golden set] --> Eval[scripts/eval.py]
    Eval -->|tagged eval traces| LF
    Eval -->|judge: Sonnet 4.6| Scores[faithfulness<br>answer_relevance]
    Scores -->|attach to trace| LF
    Eval -->|markdown report| Reports[evals/reports/]
    UI[Chat UI thumbs] -->|user_feedback| LF
    LF -->|filter low scores| Diag[Diagnose]
    Diag --> Fix[Prompt + code fix]
    Fix --> Eval
```

The eval has surfaced three real bugs so far — a hallucinated URL, speculative transfer characterization, and a bug in the eval itself where the judge wasn't receiving the title chain as context. Each fix is in git history with the before/after report. See [`evals/reports/`](evals/reports/).

---

## What's interesting

- **Hybrid retrieval that actually works on proper nouns.** Pure dense retrieval kept finding "Irvine Ave in Newport Beach" when the user asked for "Bridgeport Rd in Irvine" — the token `Irvine` is everywhere, the rarer `Bridgeport` doesn't carry enough similarity weight. Adding Qdrant's BM25 sparse vectors + Reciprocal Rank Fusion fixed it; the sparse leg rescues exact-token queries that dense drops.

- **Live ArcGIS fallback with a relevance heuristic.** Hybrid search always returns top-k by similarity, not threshold, so `if not parcels:` never fires for out-of-seed addresses. The retrieval node checks "did any returned parcel's address actually contain the query's house number?" If no, fall back to the live OC Public Works FeatureServer (~500ms cache miss), enrich with synthetic owner data, return.

- **Provenance flagging end-to-end.** The OC public ArcGIS layers redact owner names — real assessor data is behind a $3k/yr paywall (ParcelQuest, ATTOM, etc.). So owners are synthetic, deterministically generated per-APN. Crucially, every parcel carries `owner_source: "synthetic"`, the summarize prompt appends an italic disclaimer when synthetic data is in the context, and the UI shows an amber `synthetic` chip in the side panel. When a real provider is wired in, flip the tag and the disclaimer disappears automatically.

- **Model selection by data, not vibes.** Ran the 16-case suite against Haiku 4.5 / Sonnet 4.6 / Opus 4.7 with a fixed judge:

  | metric | Haiku 4.5 | Sonnet 4.6 | Opus 4.7 |
  |---|---|---|---|
  | `intent_accuracy` | 1.00 | 0.94 | 1.00 |
  | `faithfulness` | 9.78 | **9.91** | 9.84 |
  | `answer_relevance` | 6.44 | **6.88** | 6.81 |

  Opus underperformed Sonnet on both judge-scored dimensions. Picked Sonnet. Haiku is a viable cost-down option (lags by ~0.4 on relevance, matches Opus on routing).

- **Langfuse + evalkit bridge.** Every eval case produces a Langfuse trace tagged `eval` + `case:<id>`; faithfulness, answer_relevance, intent_accuracy, citation_recall, citation_precision, refusal_correctness all attach as Langfuse scores on the same trace. Filter `scores.faithfulness < 8` in the dashboard → drill straight to the specific run + the agent's actual node-by-node trace that scored poorly. That's the eval-driven debugging loop with a UI on it.

- **Three bugs the eval caught:**
  1. Agent invented `ocassessor.gov` → tightened prompt against external resources.
  2. Title chain answers characterized transfers ("arm's-length", "inter-family") → tightened prompt against speculation.
  3. Judge was getting parcels but not graph_facts as context → it correctly flagged every title-chain claim as ungrounded → fixed the eval's context formatter. Faithfulness 8.46 → 9.96.

---

## Project layout

```
app/
  agents/       LangGraph supervisor + tools + state
  routers/      /query (JSON + SSE), /feedback, /health
  services/     vector (Qdrant), graph (Neo4j), db (Postgres), live_arcgis
  ingestion/    arcgis_parcels (real), synthetic_owners (placeholder for paywall)
  observability.py     Langfuse callback factory + tag accumulator
  config.py     pydantic-settings
scripts/
  seed.py       OC ArcGIS → Postgres + Qdrant + Neo4j
  eval.py       Run golden set, score with evalkit, attach to Langfuse
  sweep.py      Model comparison across Haiku/Sonnet/Opus
evals/
  golden.yaml             16-case spec
  reports/*.md            Per-run reports (latest, sweep, provenance debug)
web/
  src/app/components/     Chat / AgentTrace / ParcelList / TitleChain
  src/lib/api.ts          SSE parser + feedback POST
tests/                    37 tests covering routing, normalization, sparse vectors, citations, synthetic chains, fallback heuristic
```

---

## Roadmap

- [x] Real OC ArcGIS ingestion (2k Irvine seed; 702k live-fallback reachable)
- [x] Hybrid retrieval (BM25 + dense + RRF + APN fast-path)
- [x] Owner + title-chain graph with synthetic provenance flagging
- [x] 5-intent LangGraph supervisor (lookup, compare, summarize, title_chain, portfolio)
- [x] FastAPI + SSE + Next.js streaming UI with thumbs feedback
- [x] evalkit-powered 16-case scorecard
- [x] Model comparison sweep
- [x] Langfuse observability (tags, scores, trace-id round-trip)
- [ ] Real owner provider (ATTOM / ParcelQuest swap path; interface is provider-agnostic)
- [ ] 30+ case eval coverage
- [ ] Public deployment (Vercel + Railway + managed DBs)
- [ ] Loom architecture walkthrough

---

## License

MIT
