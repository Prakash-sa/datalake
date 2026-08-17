"""Runtime settings endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from rag_backend.dependencies import RagServiceDep
from rag_backend.schemas import SettingsResponse, SettingsUpdateRequest

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("", response_model=SettingsResponse)
async def get_settings(rag_service: RagServiceDep) -> dict[str, Any]:
    """Return local runtime settings."""
    return {"status": "success", "settings": rag_service.get_settings()}


@router.post("", response_model=SettingsResponse)
async def update_settings(
    request: SettingsUpdateRequest, rag_service: RagServiceDep
) -> dict[str, Any]:
    """Persist local runtime settings. Model changes apply on next restart."""
    result = rag_service.update_settings(request.model_dump(exclude_none=True))
    return {"status": result["status"], "settings": result["settings"]}
