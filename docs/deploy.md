# Deploying oc-realestate-intel to portfolio-infra

This project ships as four containers (api, web, qdrant, neo4j) inside the shared portfolio-infra docker-compose, fronted by Caddy at `oci.danhle.net` (or whatever `$DOMAIN` is set to). Postgres is reused from the shared `portfolio-postgres` instance.

## One-time setup on the VPS (65.108.243.192)

These steps only need to run once — the second push onwards is fully automated by the deploy.yml workflow.

```bash
# 1. Clone the repo where the docker-compose build context expects it.
cd /opt && git clone https://github.com/odanree/oc-realestate-intel.git

# 2. Drop the per-project secrets into the portfolio-infra .env (next to
#    the existing PORTFOLIO_DB_PASSWORD etc.):
cat >> /opt/portfolio-infra/.env <<'EOF'
OCI_NEO4J_PASSWORD=<strong-password>
OCI_ANTHROPIC_API_KEY=<sk-ant-...>
OCI_LANGFUSE_PUBLIC_KEY=<pk-lf-... or blank to disable>
OCI_LANGFUSE_SECRET_KEY=<sk-lf-... or blank to disable>
OCI_LANGFUSE_HOST=https://us.cloud.langfuse.com
EOF

# 3. Create the oci database in shared Postgres. The init-db SQL only runs
#    on a fresh postgres volume — for an already-running instance we have
#    to create the DB manually:
docker exec -it portfolio-postgres psql -U postgres -c "CREATE DATABASE oci;"
docker exec -it portfolio-postgres psql -U postgres -c \
    "GRANT ALL PRIVILEGES ON DATABASE oci TO portfolio_user;"
docker exec -it portfolio-postgres psql -U postgres -d oci -c \
    "GRANT ALL ON SCHEMA public TO portfolio_user;"

# 4. Add the DNS A record. In your DNS provider:
#       oci.danhle.net  →  65.108.243.192
#    Caddy will request a Let's Encrypt cert automatically on first request.

# 5. Pull the latest portfolio-infra and rebuild (or just push to master and
#    let GitHub Actions do it).
cd /opt/portfolio-infra && git pull
docker compose up -d --build oci-qdrant oci-neo4j oci-api oci-web
docker compose up -d caddy   # picks up the new oci.{DOMAIN} block
```

## What happens on first boot

`oci-api` runs the `docker/entrypoint.sh` script, which:

1. Probes Qdrant for an existing parcels collection. If it has > 100 points, the seed is a fast no-op — `--skip-if-seeded` exits 0.
2. On a fresh volume, runs `scripts.seed` with the production WHERE clause (Irvine + Newport Beach + Anaheim + Orange) and `--limit 10000`. This takes ~12 minutes on first boot — most of it sentence-transformers embedding on CPU. The Anthropic and Qdrant calls are tiny by comparison.
3. `exec`s uvicorn so docker-stop signals propagate cleanly.

The seed is wrapped in `|| true` — if it fails (ArcGIS outage, etc.), the API still boots so live-fallback queries can serve any address in OC. Health endpoint stays up.

## Continuous deploy

The workflow at `portfolio-infra/.github/workflows/deploy.yml` watches the master branches of:

- `/opt/portfolio-infra`
- `/opt/sec-financial-intelligence`
- `/opt/jd-role-classifier`
- `/opt/parking-enforcement-detector`
- `/opt/oc-realestate-intel` ← us

A push to any of them ssh's into the VPS, pulls the changed repo, and rebuilds only the affected compose services. For us that's `oci-api` and `oci-web` (any push to this repo rebuilds both — they share a repo, separating per-subdir is not worth the workflow complexity).

To force a full rebuild from anywhere: dispatch the workflow manually with `rebuild_all: true`.

## Smoke test after deploy

```bash
curl -sS https://oci.danhle.net/api/v1/health
# {"status":"ok"}

curl -sS -X POST https://oci.danhle.net/api/v1/query \
     -H "Content-Type: application/json" \
     -d '{"query": "Who owns parcel 461-211-62?"}' | jq
# Expect: answer, intent=lookup, citations=[{"apn":"461-211-62", ...}],
# trace_id (if Langfuse keys set).
```

Then open https://oci.danhle.net in a browser — the chat UI should load and stream.

## Troubleshooting

**Seed never finishes / hangs on download** — sentence-transformers model is baked into the API image at build time (`pip install -e ".[embeddings]"` + `python -c "SentenceTransformer('all-MiniLM-L6-v2')"`). If the build skipped it, container logs will show a HuggingFace download. Rebuild with `--no-cache`.

**Neo4j tools return [] for known parcels** — Neo4j takes a few seconds longer than Postgres/Qdrant to accept Bolt connections. The entrypoint doesn't explicitly wait for it; if you see graph queries failing right after a deploy, just `docker compose restart oci-api` once Neo4j is ready.

**SSE stream cuts off** — Caddy's `flush_interval -1` directive (in the Caddyfile block) is required for SSE. If the chat UI hangs after a query, check that block hasn't been altered.

**Anthropic 401** — `OCI_ANTHROPIC_API_KEY` not loaded. `docker compose config oci-api | grep ANTHROPIC` should show the actual key. If it shows the literal `${OCI_ANTHROPIC_API_KEY}`, the var isn't in `.env`.

**Disk filling up** — the qdrant + neo4j volumes grow with seeded data. ~250 MB for 10k parcels combined. `docker system df` to check.
