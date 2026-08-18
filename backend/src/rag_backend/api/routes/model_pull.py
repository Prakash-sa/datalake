"""Streaming model download endpoint."""

from __future__ import annotations

import json
import threading
from collections.abc import Iterator
from typing import Any

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from rag_backend.api.routes.stream import SSE_HEADERS
from rag_backend.dependencies import RagServiceDep
from rag_backend.errors import RagError
from rag_backend.schemas import ModelPullRequest

router = APIRouter(prefix="/models", tags=["models"])


def _encode(event: dict[str, Any]) -> str:
    return f"data: {json.dumps(event, separators=(',', ':'))}\n\n"


@router.post("/pull/stream")
async def stream_pull_model(
    request: ModelPullRequest, rag_service: RagServiceDep
) -> StreamingResponse:
    """Pull a model, streaming download progress.

    Emits `progress` frames carrying Ollama's status and byte counts, then a
    terminal `done` or `error` frame. Disconnecting cancels the transfer.
    """
    cancel = threading.Event()

    def events() -> Iterator[str]:
        try:
            for record in rag_service.ollama.stream_pull_model(request.name, cancel=cancel):
                total = record.get("total") or 0
                completed = record.get("completed") or 0
                yield _encode(
                    {
                        "event": "progress",
                        "model": request.name,
                        "status": record.get("status", ""),
                        "completed": completed,
                        "total": total,
                        # Ollama reports byte counts only while a layer is
                        # transferring; other statuses have no meaningful percent.
                        "percent": round(completed / total * 100, 1) if total else None,
                    }
                )
            yield _encode({"event": "done", "model": request.name})
        except RagError as e:
            yield _encode({"event": "error", **e.to_dict()})
        finally:
            cancel.set()

    return StreamingResponse(events(), media_type="text/event-stream", headers=SSE_HEADERS)
