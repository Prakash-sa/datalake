"""Server-sent-events endpoint for streaming answers."""

from __future__ import annotations

import json
import threading
from collections.abc import Iterator
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from rag_backend.dependencies import RagServiceDep
from rag_backend.schemas import DocumentQueryRequest

router = APIRouter(tags=["search"])

SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    # Disables proxy buffering, which would otherwise defeat streaming.
    "X-Accel-Buffering": "no",
}


def _encode(event: dict[str, Any]) -> str:
    """Encode one event as an SSE frame."""
    return f"data: {json.dumps(event, separators=(',', ':'))}\n\n"


@router.post("/query/stream")
async def stream_query(
    request: DocumentQueryRequest,
    http_request: Request,
    rag_service: RagServiceDep,
) -> StreamingResponse:
    """Stream a grounded answer as it is generated.

    Emits `sources`, then `token` frames, then a terminal `done` or `error`
    frame. Disconnecting cancels generation rather than leaving the model
    running for an answer nobody will read.
    """
    cancel = threading.Event()

    def events() -> Iterator[str]:
        try:
            for event in rag_service.stream_query_documents(
                user_query=request.query,
                k=request.k,
                min_score=request.min_score,
                cancel=cancel,
            ):
                yield _encode(event)
        finally:
            # Covers both normal completion and the client hanging up; the
            # generator is closed either way.
            cancel.set()

    return StreamingResponse(events(), media_type="text/event-stream", headers=SSE_HEADERS)
