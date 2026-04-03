"""
FastAPI application factory and startup configuration.
"""
from __future__ import annotations

import logging
import sys

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.endpoints import router
from app.core.config import settings

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    stream=sys.stdout,
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------

def create_app() -> FastAPI:
    app = FastAPI(
        title="SQL-Gen AI API",
        description=(
            "Natural-language SQL agent for school data, "
            "secured with JWT and per-school row-level security."
        ),
        version="1.0.0",
        docs_url="/docs" if settings.APP_ENV != "production" else None,
        redoc_url="/redoc" if settings.APP_ENV != "production" else None,
    )

    # CORS – tighten origins in production
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if settings.APP_ENV != "production" else [],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(router)

    @app.on_event("startup")
    async def _startup():
        logger.info("Starting SQL-Gen API (env=%s)", settings.APP_ENV)
        # Eagerly initialise the DB connection pool and LangGraph
        from app.db.mysql import get_sql_database
        from app.engine.graph import get_graph

        get_sql_database()
        get_graph()
        logger.info("Startup complete.")

    @app.get("/health", tags=["ops"])
    async def health():
        return {"status": "ok", "env": settings.APP_ENV}

    return app


# Module-level app instance (used by Gunicorn / Uvicorn)
app = create_app()
