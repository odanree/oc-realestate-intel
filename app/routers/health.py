from __future__ import annotations

from fastapi import APIRouter

# Caddy only forwards /api/* to oci-api in production, so the public-facing
# health probe must live under that prefix. The bare /health alias stays for
# docker-compose healthchecks and direct curl on the API container.
router = APIRouter(tags=["health"])


@router.get("/health")
@router.get("/api/v1/health")
async def health() -> dict:
    return {"status": "ok"}
