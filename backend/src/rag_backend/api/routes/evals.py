"""Release-gating eval endpoint."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from rag_backend.dependencies import EvalServiceDep
from rag_backend.schemas import EvalRequest, EvalResponse

router = APIRouter(tags=["evals"])


@router.post("/eval", response_model=EvalResponse)
async def run_eval(request: EvalRequest, eval_service: EvalServiceDep) -> dict[str, Any]:
    """Run deterministic retrieval and answer checks for release gating."""
    return eval_service.run(cases=request.cases, k=request.k)
