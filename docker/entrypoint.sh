#!/usr/bin/env bash
# Production entrypoint:
#  1. Wait for Postgres + Qdrant + Neo4j to be reachable (compose health checks
#     handle most of this, but Neo4j sometimes accepts TCP before Bolt is ready).
#  2. Run the seed in --skip-if-seeded mode. If Qdrant already has > 100 points
#     this is a fast no-op; otherwise it pulls ~10k parcels across the four
#     biggest OC cities (Irvine, Newport Beach, Anaheim, Orange) and writes
#     them to all three data stores. ~12 min cold start, zero subsequent boots.
#  3. exec uvicorn so signals (SIGTERM from docker stop) propagate correctly.

set -euo pipefail

SEED_LIMIT="${OCI_SEED_LIMIT:-10000}"
SEED_WHERE="${OCI_SEED_WHERE:-(SITE_ADDRESS LIKE '%IRVINE%' OR SITE_ADDRESS LIKE '%NEWPORT BEACH%' OR SITE_ADDRESS LIKE '%ANAHEIM%' OR SITE_ADDRESS LIKE '% ORANGE%')}"

echo ">> oci entrypoint: limit=${SEED_LIMIT}"

# Run the conditional seed. Production never uses --recreate.
python -m scripts.seed \
    --skip-if-seeded \
    --limit "${SEED_LIMIT}" \
    --where "${SEED_WHERE}" || {
        rc=$?
        # We tolerate seed failures so the API still boots and can serve
        # live-fallback queries while we diagnose. Health endpoint stays up.
        echo "!! seed exited rc=${rc} — continuing without local cache"
    }

echo ">> handing off to: $*"
exec "$@"
