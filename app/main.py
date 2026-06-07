"""FastAPI entrypoint."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import health, query
from app.services import graph as graph_service
from app.services import vector as vector_service

logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Ensure data stores have their collections / constraints on startup."""
    try:
        await vector_service.ensure_collection()
        await graph_service.ensure_constraints()
    except Exception as e:
        log.warning("Startup data-store init failed (continuing anyway): %s", e)
    yield
    await graph_service.close()


app = FastAPI(
    title="oc-realestate-intel",
    version="0.1.0",
    description="Multi-agent LangGraph system over Orange County real estate + title data.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(query.router)
