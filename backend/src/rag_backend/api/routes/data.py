"""Export, import, and backup endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from rag_backend.dependencies import DataServiceDep
from rag_backend.errors import RagError
from rag_backend.schemas import DataExportRequest, DataImportRequest

router = APIRouter(prefix="/data", tags=["data"])


def _handle(operation) -> Any:
    """Run a transfer operation, mapping its error code to an HTTP status."""
    try:
        return operation()
    except RagError as e:
        raise HTTPException(status_code=e.http_status, detail=e.to_dict()) from e


@router.post("/backup")
async def create_backup(data_service: DataServiceDep) -> dict[str, Any]:
    """Snapshot the catalog database."""
    return _handle(data_service.backup)


@router.get("/backups")
async def list_backups(data_service: DataServiceDep) -> dict[str, Any]:
    """List available catalog snapshots, newest first."""
    return {"status": "success", "backups": data_service.list_backups()}


@router.post("/export")
async def export_data(request: DataExportRequest, data_service: DataServiceDep) -> dict[str, Any]:
    """Write a portable archive of the catalog."""
    return _handle(lambda: data_service.export(request.destination))


@router.post("/import/inspect")
async def inspect_archive(
    request: DataImportRequest, data_service: DataServiceDep
) -> dict[str, Any]:
    """Read an archive's manifest without importing it."""
    return _handle(lambda: data_service.inspect(request.source))


@router.post("/import")
async def import_data(request: DataImportRequest, data_service: DataServiceDep) -> dict[str, Any]:
    """Restore a catalog from an archive, backing up the current one first."""
    return _handle(lambda: data_service.import_archive(request.source))
