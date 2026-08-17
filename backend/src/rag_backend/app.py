"""FastAPI application factory."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from rag_backend import __version__
from rag_backend.api import api_router
from rag_backend.lifespan import lifespan
from rag_backend.logging_config import configure_logging
from rag_backend.middleware import BearerTokenMiddleware
from rag_backend.settings import Settings, get_settings


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build a configured FastAPI application.

    Accepting settings makes the app constructible in tests without touching
    process environment variables.
    """
    settings = settings or get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(
        title="Document RAG Engine",
        description="Local-first REST API for semantic search and document analysis",
        version=__version__,
        # Interactive docs expose the full schema; keep them off in production.
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
        lifespan=lifespan,
    )
    app.state.settings = settings

    if settings.api_token:
        app.add_middleware(BearerTokenMiddleware, token=settings.api_token)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["*"],
        max_age=settings.cors_cache_max_age,
    )

    app.include_router(api_router)
    return app


app = create_app()
