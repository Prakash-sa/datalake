"""In-process embeddings via ONNX Runtime.

Removes Ollama from the critical path for indexing and search: the model runs
inside the sidecar, so a fresh install can import documents and search them with
no external software present. Generated prose uses the local GGUF provider by
default; Ollama is available only as an optional alternate provider.

Uses all-MiniLM-L6-v2, the same model and artifacts Chroma ships as its default.
Output was verified identical to Chroma's own implementation (cosine 1.0), so
switching between them does not change retrieval behaviour.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from rag_backend.errors import EmbeddingError, ErrorCode

logger = logging.getLogger(__name__)

MODEL_NAME = "all-MiniLM-L6-v2"
DIMENSIONS = 384
# The model's trained context. Longer chunks are truncated rather than rejected,
# matching how the reference implementation behaves.
MAX_SEQUENCE_LENGTH = 256
MODEL_FILE = "model.onnx"
TOKENIZER_FILE = "tokenizer.json"


class LocalEmbeddings:
    """Sentence embeddings computed locally, with no network calls.

    Loading is deferred until first use so constructing the service stays cheap
    and a missing model surfaces as a structured error at embed time rather than
    preventing startup.
    """

    model_name = MODEL_NAME
    dimensions = DIMENSIONS

    def __init__(self, model_dir: str, threads: int | None = None) -> None:
        self.model_dir = Path(model_dir).expanduser()
        self._threads = threads
        self._session: Any = None
        self._tokenizer: Any = None

    # -- Loading --------------------------------------------------------------

    @property
    def is_available(self) -> bool:
        """Whether the model artifacts are present on disk."""
        return (self.model_dir / MODEL_FILE).is_file() and (
            self.model_dir / TOKENIZER_FILE
        ).is_file()

    def _load(self) -> None:
        if self._session is not None:
            return

        if not self.is_available:
            raise EmbeddingError(
                f"Local embedding model not found in {self.model_dir}. "
                "Run scripts/fetch_embedding_model.py to install it.",
                code=ErrorCode.MODEL_UNAVAILABLE,
            )

        try:
            import onnxruntime
            from tokenizers import Tokenizer
        except ImportError as e:  # pragma: no cover - dependency is declared
            raise EmbeddingError(
                f"Local embedding runtime unavailable: {e}",
                code=ErrorCode.MODEL_UNAVAILABLE,
            ) from e

        tokenizer = Tokenizer.from_file(str(self.model_dir / TOKENIZER_FILE))
        tokenizer.enable_truncation(max_length=MAX_SEQUENCE_LENGTH)
        tokenizer.enable_padding(pad_id=0, pad_token="[PAD]")

        options = onnxruntime.SessionOptions()
        if self._threads:
            # Bounded so indexing does not saturate a laptop's cores.
            options.intra_op_num_threads = self._threads

        self._tokenizer = tokenizer
        self._session = onnxruntime.InferenceSession(
            str(self.model_dir / MODEL_FILE),
            options,
            providers=["CPUExecutionProvider"],
        )
        logger.info("Local embedding model ready (%s, %d dims)", MODEL_NAME, DIMENSIONS)

    # -- Embedding ------------------------------------------------------------

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts into unit-length vectors."""
        if not texts:
            return []

        self._load()
        import numpy as np

        encodings = self._tokenizer.encode_batch(texts)
        input_ids = np.array([e.ids for e in encodings], dtype=np.int64)
        attention_mask = np.array([e.attention_mask for e in encodings], dtype=np.int64)

        inputs = {"input_ids": input_ids, "attention_mask": attention_mask}
        expected = {i.name for i in self._session.get_inputs()}
        if "token_type_ids" in expected:
            # Single-sequence input, so every token belongs to segment zero.
            inputs["token_type_ids"] = np.zeros_like(input_ids)

        try:
            hidden_state = self._session.run(None, inputs)[0]
        except Exception as e:
            raise EmbeddingError(
                f"Local embedding failed: {e}", code=ErrorCode.EMBEDDING_FAILED
            ) from e

        # Mean-pool over real tokens only; padding must not drag vectors toward
        # zero, which would make similarity depend on batch composition.
        mask = np.expand_dims(attention_mask, -1).astype(np.float32)
        pooled = (hidden_state * mask).sum(axis=1) / np.clip(mask.sum(axis=1), 1e-9, None)

        # Normalise so cosine distance and dot product agree, which is what the
        # Chroma collection's cosine space assumes.
        norms = np.clip(np.linalg.norm(pooled, axis=1, keepdims=True), 1e-12, None)
        return (pooled / norms).tolist()

    def embed_query(self, text: str) -> list[float]:
        """Embed a single text. Matches the interface langchain exposes."""
        return self.embed_documents([text])[0]

    # -- Diagnostics ----------------------------------------------------------

    def health(self) -> dict[str, Any]:
        """Report whether local embedding is usable."""
        return {
            "status": "ready" if self.is_available else "error",
            "provider": "local",
            "model": MODEL_NAME,
            "dimensions": DIMENSIONS,
            "model_dir": str(self.model_dir),
            "requires_external_software": False,
        }
