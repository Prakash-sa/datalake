"""Structured error codes.

The plan requires distinguishing "retrieval failed", "model unavailable", and
"no relevant evidence" instead of surfacing arbitrary exception strings. Callers
match on ``code``; ``message`` is for humans and must never contain document
text, prompts, or file paths.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any


class ErrorCode(StrEnum):
    """Stable, machine-readable failure reasons."""

    # Input
    VALIDATION_FAILED = "validation_failed"
    UNSUPPORTED_FORMAT = "unsupported_format"
    DOCUMENT_NOT_FOUND = "document_not_found"

    # Ingestion
    PARSE_FAILED = "parse_failed"
    NO_EXTRACTABLE_TEXT = "no_extractable_text"

    # Dependencies
    MODEL_UNAVAILABLE = "model_unavailable"
    EMBEDDING_FAILED = "embedding_failed"
    GENERATION_FAILED = "generation_failed"
    GENERATION_TIMEOUT = "generation_timeout"

    # Retrieval
    RETRIEVAL_FAILED = "retrieval_failed"
    NO_RELEVANT_EVIDENCE = "no_relevant_evidence"

    # Storage
    STORAGE_UNAVAILABLE = "storage_unavailable"
    INDEX_MODEL_MISMATCH = "index_model_mismatch"

    # Lifecycle
    CANCELLED = "cancelled"
    INTERNAL_ERROR = "internal_error"


# Errors the caller can resolve by acting (starting Ollama, pulling a model,
# freeing disk) rather than by retrying the same request unchanged.
ACTIONABLE_CODES = frozenset(
    {
        ErrorCode.MODEL_UNAVAILABLE,
        ErrorCode.STORAGE_UNAVAILABLE,
        ErrorCode.INDEX_MODEL_MISMATCH,
        ErrorCode.UNSUPPORTED_FORMAT,
    }
)

# Maps an error code to the HTTP status the API should return.
_HTTP_STATUS: dict[ErrorCode, int] = {
    ErrorCode.VALIDATION_FAILED: 400,
    ErrorCode.UNSUPPORTED_FORMAT: 415,
    ErrorCode.DOCUMENT_NOT_FOUND: 404,
    ErrorCode.PARSE_FAILED: 422,
    ErrorCode.NO_EXTRACTABLE_TEXT: 422,
    ErrorCode.MODEL_UNAVAILABLE: 503,
    ErrorCode.EMBEDDING_FAILED: 502,
    ErrorCode.GENERATION_FAILED: 502,
    ErrorCode.GENERATION_TIMEOUT: 504,
    ErrorCode.RETRIEVAL_FAILED: 500,
    ErrorCode.NO_RELEVANT_EVIDENCE: 200,
    ErrorCode.STORAGE_UNAVAILABLE: 503,
    ErrorCode.INDEX_MODEL_MISMATCH: 409,
    ErrorCode.CANCELLED: 499,
    ErrorCode.INTERNAL_ERROR: 500,
}


class RagError(Exception):
    """Base error carrying a structured code and a safe message."""

    code: ErrorCode = ErrorCode.INTERNAL_ERROR

    def __init__(
        self,
        message: str,
        *,
        code: ErrorCode | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        if code is not None:
            self.code = code
        self.details = details or {}

    @property
    def http_status(self) -> int:
        """HTTP status this error maps to."""
        return _HTTP_STATUS.get(self.code, 500)

    @property
    def actionable(self) -> bool:
        """Whether the user can resolve this by taking an action."""
        return self.code in ACTIONABLE_CODES

    def to_dict(self) -> dict[str, Any]:
        """Serialise for an API response body."""
        payload: dict[str, Any] = {
            "status": "error",
            "code": str(self.code),
            "error": self.message,
            "actionable": self.actionable,
        }
        if self.details:
            payload["details"] = self.details
        return payload


class ValidationError(RagError):
    code = ErrorCode.VALIDATION_FAILED


class ModelUnavailableError(RagError):
    code = ErrorCode.MODEL_UNAVAILABLE


class EmbeddingError(RagError):
    code = ErrorCode.EMBEDDING_FAILED


class GenerationError(RagError):
    code = ErrorCode.GENERATION_FAILED


class GenerationTimeoutError(RagError):
    code = ErrorCode.GENERATION_TIMEOUT


class RetrievalError(RagError):
    code = ErrorCode.RETRIEVAL_FAILED


class StorageUnavailableError(RagError):
    code = ErrorCode.STORAGE_UNAVAILABLE


class IndexModelMismatchError(RagError):
    code = ErrorCode.INDEX_MODEL_MISMATCH


class CancelledError(RagError):
    code = ErrorCode.CANCELLED


# Substrings Ollama and its clients emit when the daemon is unreachable or the
# model is missing. Used to turn opaque client exceptions into a code the UI can
# act on.
_MODEL_UNAVAILABLE_HINTS = (
    "failed to connect to ollama",
    "connection refused",
    "model not found",
    "no such model",
    "try pulling it first",
)


def classify_ollama_exception(exc: Exception) -> ErrorCode:
    """Map an Ollama client exception to a structured code."""
    text = str(exc).lower()
    if isinstance(exc, TimeoutError) or "timeout" in text or "timed out" in text:
        return ErrorCode.GENERATION_TIMEOUT
    if any(hint in text for hint in _MODEL_UNAVAILABLE_HINTS):
        return ErrorCode.MODEL_UNAVAILABLE
    return ErrorCode.GENERATION_FAILED
