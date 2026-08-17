"""Ollama model management endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, status

from rag_backend.dependencies import RagServiceDep
from rag_backend.schemas import ModelListResponse, ModelPullRequest

router = APIRouter(prefix="/models", tags=["models"])


@router.get("", response_model=ModelListResponse)
async def list_models(rag_service: RagServiceDep) -> dict[str, Any]:
    """List installed and required Ollama models."""
    return rag_service.list_ollama_models()


@router.post("/pull")
async def pull_model(request: ModelPullRequest, rag_service: RagServiceDep) -> dict[str, Any]:
    """Pull a local Ollama model."""
    result = rag_service.pull_ollama_model(request.name)
    if result.get("status") == "error":
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=result.get("error"))
    return result
