"""Multi-turn conversations over the document library.

Wraps retrieval and generation in a conversation: prior turns inform both what
is retrieved and how the answer reads, and every turn is persisted so a
conversation survives a restart.

The single-shot `/query` endpoint remains for scripted use; this is what the
interface talks to.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from rag_backend.application.citations import validate_citations
from rag_backend.application.prompts import (
    CHAT_ANSWER_TEMPLATE,
    CHAT_PROMPT_VERSION,
    build_context,
    build_retrieval_query,
    render_history,
    select_context_documents,
)
from rag_backend.application.rag_service import DocumentRAGService
from rag_backend.errors import CancelledError, ErrorCode, RagError, RetrievalError

logger = logging.getLogger(__name__)

# A conversation is named from its opening question until the user renames it.
TITLE_MAX_LENGTH = 60


def derive_title(question: str) -> str:
    """A readable conversation title taken from the first question."""
    cleaned = " ".join(question.split())
    if len(cleaned) <= TITLE_MAX_LENGTH:
        return cleaned or "New conversation"
    return cleaned[: TITLE_MAX_LENGTH - 1].rstrip() + "…"


class ChatService:
    """Runs conversation turns and keeps their history."""

    def __init__(self, rag_service: DocumentRAGService) -> None:
        self._rag = rag_service
        self._catalog = rag_service.catalog

    # -- Conversations --------------------------------------------------------

    def list_conversations(self, limit: int = 50) -> list[dict[str, Any]]:
        return self._catalog.list_conversations(limit=limit)

    def get_conversation(self, conversation_id: str) -> dict[str, Any] | None:
        return self._catalog.get_conversation(conversation_id)

    def rename_conversation(self, conversation_id: str, title: str) -> bool:
        return self._catalog.rename_conversation(conversation_id, title.strip())

    def delete_conversation(self, conversation_id: str) -> bool:
        return self._catalog.delete_conversation(conversation_id)

    def _ensure_conversation(self, conversation_id: str | None, question: str) -> str:
        """Return an existing conversation id, or start one named after the question."""
        if conversation_id and self._catalog.get_conversation(conversation_id):
            return conversation_id

        new_id = f"conv_{uuid4().hex}"
        self._catalog.create_conversation(new_id, derive_title(question))
        return new_id

    # -- Turns ----------------------------------------------------------------

    def stream_turn(
        self,
        question: str,
        conversation_id: str | None = None,
        k: int = 5,
        min_score: float | None = None,
        cancel: threading.Event | None = None,
    ) -> Iterator[dict[str, Any]]:
        """Run one conversation turn, yielding events as it progresses.

        Events, in order:
          {"event": "conversation", "conversation_id": ..., "title": ...}
          {"event": "sources", "documents": [...]}
          {"event": "token", "text": "..."}                       (repeated)
          {"event": "done", "answer": ..., "citations": {...}}
          {"event": "error", "code": ..., "error": ...}            (terminal)

        The conversation is announced first so a new one appears in the sidebar
        before the answer starts arriving.
        """
        started = datetime.now()
        question = question.strip()

        conversation_id = self._ensure_conversation(conversation_id, question)
        conversation = self._catalog.get_conversation(conversation_id) or {}
        history = conversation.get("messages", [])

        yield {
            "event": "conversation",
            "conversation_id": conversation_id,
            "title": conversation.get("title", ""),
        }

        # Persist the question before answering, so a failed or cancelled turn
        # still leaves the conversation readable.
        self._catalog.add_message(
            f"msg_{uuid4().hex}", conversation_id, "user", question
        )

        try:
            documents = self._rag.search_documents(
                build_retrieval_query(question, history), k=k, min_score=min_score
            )
        except Exception as e:
            logger.error("Retrieval failed: %s", e, exc_info=True)
            yield {"event": "error", **RetrievalError(str(e)).to_dict()}
            return

        context_docs = select_context_documents(
            documents, token_budget=self._rag.context_token_budget
        )
        yield {
            "event": "sources",
            "documents": context_docs,
            "truncated_document_count": len(documents) - len(context_docs),
        }

        prompt = CHAT_ANSWER_TEMPLATE.format(
            context=build_context(context_docs) if context_docs else "(no documents matched)",
            history=render_history(history),
            query=question,
        )

        parts: list[str] = []
        try:
            for token in self._rag.ollama.stream_generate(
                prompt,
                model=self._rag.llm_model,
                temperature=self._rag.temperature,
                cancel=cancel,
            ):
                parts.append(token)
                yield {"event": "token", "text": token}
        except RagError as e:
            self._record_answer(conversation_id, "".join(parts), context_docs, error=e.code)
            yield {"event": "error", **e.to_dict()}
            return

        if cancel is not None and cancel.is_set():
            self._record_answer(
                conversation_id, "".join(parts), context_docs, error=ErrorCode.CANCELLED
            )
            yield {"event": "error", **CancelledError("Generation cancelled").to_dict()}
            return

        answer = "".join(parts).strip()
        citations = validate_citations(answer, context_docs)
        elapsed = (datetime.now() - started).total_seconds()

        message = self._record_answer(conversation_id, answer, context_docs, citations)
        self._rag.stats["queries_processed"] += 1

        yield {
            "event": "done",
            "status": "success",
            "conversation_id": conversation_id,
            "message_id": message["id"],
            "answer": answer,
            "retrieved_documents": context_docs,
            "citations": citations,
            "processing_time_seconds": round(elapsed, 2),
        }

    def _record_answer(
        self,
        conversation_id: str,
        answer: str,
        documents: list[dict[str, Any]],
        citations: dict[str, Any] | None = None,
        error: ErrorCode | None = None,
    ) -> dict[str, Any]:
        """Persist the assistant's turn, including a partial one."""
        return self._catalog.add_message(
            f"msg_{uuid4().hex}",
            conversation_id,
            "assistant",
            answer,
            citations=citations or {},
            model={
                "llm_model": self._rag.llm_model,
                "embedding_model": getattr(
                    self._rag.embeddings, "model_name", self._rag.embedding_model
                ),
                "prompt_version": CHAT_PROMPT_VERSION,
                "source_count": len(documents),
                "recorded_at": datetime.now(UTC).isoformat(),
                **({"error_code": str(error)} if error else {}),
            },
        )
