"""Health, statistics, readiness, and diagnostics endpoints."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter

from rag_backend.dependencies import RagServiceDep
from rag_backend.schemas import HealthResponse, ReadinessResponse, StatsResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health_check(rag_service: RagServiceDep) -> dict[str, Any]:
    """Liveness probe for monitoring and orchestration."""
    return {
        "status": "healthy",
        "timestamp": datetime.now(UTC).isoformat(),
    }


@router.get("/stats", response_model=StatsResponse)
async def get_stats(rag_service: RagServiceDep) -> dict[str, Any]:
    """Engine statistics and index sizes."""
    return rag_service.get_stats()


@router.get("/readiness", response_model=ReadinessResponse)
async def get_readiness(rag_service: RagServiceDep) -> dict[str, Any]:
    """Report production operating capabilities."""
    return rag_service.get_readiness()


@router.get("/diagnostics")
async def get_diagnostics(rag_service: RagServiceDep) -> dict[str, Any]:
    """Local diagnostics for support and release smoke tests."""
    return rag_service.get_diagnostics()
