"""Application startup and shutdown.

Replaces the previous module-level ``rag_service`` global and its
``initialize_rag_service`` setter. The service is built once on startup and
stored on ``app.state``, which keeps it out of import-time state and lets tests
inject a double.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from rag_backend.application.chat_service import ChatService
from rag_backend.application.data_transfer import DataTransferService
from rag_backend.application.eval_service import EvalService
from rag_backend.application.ingestion_jobs import IngestionJobService
from rag_backend.application.rag_service import DocumentRAGService
from rag_backend.settings import Settings

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Build the RAG service on startup and release it on shutdown."""
    settings: Settings = app.state.settings
    app.state.rag_service = None
    app.state.eval_service = None
    app.state.job_service = None
    app.state.data_service = None
    app.state.chat_service = None

    try:
        rag_service = DocumentRAGService(
            ollama_url=settings.ollama_url,
            embedding_model=settings.embedding_model,
            llm_model=settings.llm_model,
            temperature=settings.llm_temperature,
            chroma_path=settings.chroma_path,
            app_db_path=settings.resolved_app_db_path,
            embedding_provider=settings.embedding_provider,
            local_embedding_model_dir=settings.resolved_local_embedding_model_dir,
            generation_provider=settings.generation_provider,
            local_llm_model_path=settings.resolved_local_llm_model_path,
        )
        app.state.rag_service = rag_service
        app.state.eval_service = EvalService(rag_service)
        job_service = IngestionJobService(rag_service)
        # The application owns the single ingestion worker; enqueueing does
        # not spawn one.
        job_service.start()
        app.state.job_service = job_service
        app.state.data_service = DataTransferService(rag_service)
        app.state.chat_service = ChatService(rag_service)
        logger.info("RAG service initialized successfully")
    except Exception as e:
        # Start anyway so /health can report 503 and the desktop shell can
        # surface a diagnosable error instead of a dead process.
        logger.error("Failed to initialize RAG service: %s", e, exc_info=True)

    try:
        yield
    finally:
        # Stop the ingestion worker before tearing down the services it uses.
        job_service = app.state.job_service
        if job_service is not None:
            job_service.shutdown()
        rag_service = app.state.rag_service
        if rag_service is not None:
            rag_service.shutdown()
        app.state.rag_service = None
        app.state.eval_service = None
        app.state.job_service = None
        app.state.data_service = None
        app.state.chat_service = None
        logger.info("RAG service shut down")
