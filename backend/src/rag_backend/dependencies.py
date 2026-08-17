"""FastAPI dependency providers."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, Request, status

from rag_backend.application.eval_service import EvalService
from rag_backend.application.rag_service import DocumentRAGService
from rag_backend.settings import Settings


def get_settings(request: Request) -> Settings:
    """Return the settings bound to this application instance."""
    return request.app.state.settings


def get_rag_service(request: Request) -> DocumentRAGService:
    """Return the initialized RAG service, or 503 while it is unavailable."""
    service = getattr(request.app.state, "rag_service", None)
    if service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="RAG service unavailable",
        )
    return service


def get_eval_service(request: Request) -> EvalService:
    """Return the eval service, or 503 while it is unavailable."""
    service = getattr(request.app.state, "eval_service", None)
    if service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="RAG service unavailable",
        )
    return service


SettingsDep = Annotated[Settings, Depends(get_settings)]
RagServiceDep = Annotated[DocumentRAGService, Depends(get_rag_service)]
EvalServiceDep = Annotated[EvalService, Depends(get_eval_service)]
