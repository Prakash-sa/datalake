"""FastAPI dependency providers."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, Request, status

from rag_backend.application.chat_service import ChatService
from rag_backend.application.data_transfer import DataTransferService
from rag_backend.application.eval_service import EvalService
from rag_backend.application.ingestion_jobs import IngestionJobService
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


def get_job_service(request: Request) -> IngestionJobService:
    """Return the ingestion job service, or 503 while it is unavailable."""
    service = getattr(request.app.state, "job_service", None)
    if service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="RAG service unavailable",
        )
    return service


def get_data_service(request: Request) -> DataTransferService:
    """Return the data transfer service, or 503 while it is unavailable."""
    service = getattr(request.app.state, "data_service", None)
    if service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="RAG service unavailable",
        )
    return service


def get_chat_service(request: Request) -> ChatService:
    """Return the chat service, or 503 while it is unavailable."""
    service = getattr(request.app.state, "chat_service", None)
    if service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="RAG service unavailable",
        )
    return service


SettingsDep = Annotated[Settings, Depends(get_settings)]
RagServiceDep = Annotated[DocumentRAGService, Depends(get_rag_service)]
EvalServiceDep = Annotated[EvalService, Depends(get_eval_service)]
JobServiceDep = Annotated[IngestionJobService, Depends(get_job_service)]
DataServiceDep = Annotated[DataTransferService, Depends(get_data_service)]
ChatServiceDep = Annotated[ChatService, Depends(get_chat_service)]
