"""Ingestion job endpoints: enqueue, inspect, cancel, retry."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query, status

from rag_backend.dependencies import JobServiceDep
from rag_backend.schemas import (
    JobEnqueueRequest,
    JobListResponse,
    JobResponse,
)

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.post("", response_model=JobListResponse, status_code=status.HTTP_202_ACCEPTED)
async def enqueue_jobs(request: JobEnqueueRequest, job_service: JobServiceDep) -> dict[str, Any]:
    """Queue one job per path and return them immediately.

    Ingestion runs in the background; poll `GET /jobs` for progress.
    """
    jobs = [
        job_service.enqueue(path, force_reindex=request.force_reindex) for path in request.paths
    ]
    return {"status": "accepted", "jobs": jobs}


@router.get("", response_model=JobListResponse)
async def list_jobs(
    job_service: JobServiceDep,
    job_status: list[str] | None = Query(default=None, alias="status"),
    limit: int = Query(default=100, ge=1, le=500),
) -> dict[str, Any]:
    """List jobs newest first, optionally filtered by status."""
    return {
        "status": "success",
        "jobs": job_service.list_jobs(statuses=job_status, limit=limit),
    }


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(job_id: str, job_service: JobServiceDep) -> dict[str, Any]:
    """Fetch a single job."""
    job = job_service.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return {"status": "success", "job": job}


@router.post("/{job_id}/cancel", response_model=JobResponse)
async def cancel_job(job_id: str, job_service: JobServiceDep) -> dict[str, Any]:
    """Cancel a queued or running job at the next stage boundary."""
    job = job_service.cancel(job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return {"status": "success", "job": job}


@router.post("/{job_id}/retry", response_model=JobResponse)
async def retry_job(job_id: str, job_service: JobServiceDep) -> dict[str, Any]:
    """Return a failed job to the queue. Cancelled jobs are not resumed."""
    job = job_service.retry(job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return {"status": "success", "job": job}
