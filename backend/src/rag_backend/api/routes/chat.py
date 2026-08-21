"""Conversational endpoints: multi-turn chat over the document library."""

from __future__ import annotations

import json
import threading
from collections.abc import Iterator
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse

from rag_backend.api.routes.stream import SSE_HEADERS
from rag_backend.dependencies import ChatServiceDep
from rag_backend.schemas import (
    ChatRequest,
    ConversationListResponse,
    ConversationRenameRequest,
    ConversationResponse,
)

router = APIRouter(tags=["chat"])


def _encode(event: dict[str, Any]) -> str:
    return f"data: {json.dumps(event, separators=(',', ':'))}\n\n"


@router.post("/chat/stream")
async def stream_chat(
    request: ChatRequest,
    http_request: Request,
    chat_service: ChatServiceDep,
) -> StreamingResponse:
    """Run one conversation turn, streaming the reply.

    Omit `conversation_id` to start a new conversation; the id of the one used
    is announced in the first frame. Disconnecting cancels generation.
    """
    cancel = threading.Event()

    def events() -> Iterator[str]:
        try:
            for event in chat_service.stream_turn(
                question=request.message,
                conversation_id=request.conversation_id,
                k=request.k,
                min_score=request.min_score,
                cancel=cancel,
            ):
                yield _encode(event)
        finally:
            cancel.set()

    return StreamingResponse(events(), media_type="text/event-stream", headers=SSE_HEADERS)


@router.get("/conversations", response_model=ConversationListResponse)
async def list_conversations(
    chat_service: ChatServiceDep,
    limit: int = Query(default=50, ge=1, le=200),
) -> dict[str, Any]:
    """Conversations, most recently updated first."""
    return {"status": "success", "conversations": chat_service.list_conversations(limit)}


@router.get("/conversations/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(conversation_id: str, chat_service: ChatServiceDep) -> dict[str, Any]:
    """A conversation with its full message history."""
    conversation = chat_service.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    return {"status": "success", "conversation": conversation}


@router.post("/conversations/{conversation_id}/rename")
async def rename_conversation(
    conversation_id: str,
    request: ConversationRenameRequest,
    chat_service: ChatServiceDep,
) -> dict[str, Any]:
    """Retitle a conversation."""
    if not chat_service.rename_conversation(conversation_id, request.title):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    return {"status": "success", "id": conversation_id, "title": request.title}


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str, chat_service: ChatServiceDep) -> dict[str, Any]:
    """Delete a conversation and every message in it."""
    if not chat_service.delete_conversation(conversation_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    return {"status": "success", "id": conversation_id}
