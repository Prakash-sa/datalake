"""Chroma persistent vector store adapter."""

from __future__ import annotations

import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import chromadb

from rag_backend.errors import IndexModelMismatchError

logger = logging.getLogger(__name__)

# Chroma reports a width conflict only when the write is attempted, and the
# declared width is not reliably readable beforehand across versions. The
# message is therefore the authoritative signal.
_DIMENSION_ERROR = re.compile(
    r"expecting embedding with dimension of (\d+), got (\d+)", re.IGNORECASE
)

COLLECTION_NAME = "documents"
# Cosine distance keeps `similarity = 1 - distance` in the [0, 1] range.
COLLECTION_METADATA = {"hnsw:space": "cosine"}


def normalize_metadata(metadata: dict[str, Any] | None) -> dict[str, Any]:
    """Reduce metadata to the primitive values Chroma accepts.

    Chroma rejects nested structures and ``None``; non-primitives are stringified
    and empty values dropped.
    """
    normalized: dict[str, Any] = {}
    for key, value in (metadata or {}).items():
        if value is None:
            continue
        if isinstance(value, (str, int, float, bool)):
            normalized[str(key)] = value
        else:
            normalized[str(key)] = str(value)
    return normalized


class ChromaVectorStore:
    """Persistent Chroma collection holding document chunk embeddings."""

    def __init__(self, path: str) -> None:
        self.path = path
        Path(self.path).mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(path=self.path)
        self._collection = self._client.get_or_create_collection(
            name=COLLECTION_NAME, metadata=COLLECTION_METADATA
        )
        logger.info("Chroma collection '%s' ready at %s", COLLECTION_NAME, self.path)

    def dimension(self) -> int | None:
        """Width of the vectors already stored, or None when empty.

        Read from the data rather than from recorded metadata, so it is correct
        even for an index written before fingerprints existed.
        """
        try:
            if self._collection.count() == 0:
                return None
            sample = self._collection.peek(limit=1)
        except Exception as e:
            logger.debug("Could not determine collection dimension: %s", e)
            return None

        embeddings = sample.get("embeddings") if sample else None
        if embeddings is None or len(embeddings) == 0:
            return None
        first = embeddings[0]
        return len(first) if first is not None else None

    def reset(self) -> None:
        """Drop and recreate the collection.

        A collection's vector dimension is fixed when its first embedding is
        written, so changing embedding model cannot be resolved by overwriting
        rows. The collection itself has to be recreated.
        """
        try:
            self._client.delete_collection(COLLECTION_NAME)
        except Exception as e:
            # Chroma raises when the collection is already absent, which is the
            # desired end state anyway.
            logger.debug("Collection delete during reset: %s", e)

        self._collection = self._client.get_or_create_collection(
            name=COLLECTION_NAME, metadata=COLLECTION_METADATA
        )
        logger.info("Vector collection '%s' reset", COLLECTION_NAME)

    def count(self) -> int:
        """Number of indexed chunks."""
        return self._collection.count()

    def upsert(
        self,
        ids: list[str],
        contents: list[str],
        metadatas: list[dict[str, Any]],
        embeddings: list[list[float]],
    ) -> None:
        """Insert or replace chunks by id."""
        if not ids:
            return
        # Chroma's stubs describe narrower numpy-flavoured types than the plain
        # lists it accepts at runtime.
        try:
            self._collection.upsert(
                ids=ids,
                documents=contents,
                metadatas=metadatas,  # type: ignore[arg-type]
                embeddings=embeddings,  # type: ignore[arg-type]
            )
        except Exception as e:
            match = _DIMENSION_ERROR.search(str(e))
            if not match:
                raise
            # Surface a structured error naming both widths, so the caller can
            # decide between recreating an empty collection and asking for a
            # rebuild, rather than parsing a driver message itself.
            expected, received = int(match.group(1)), int(match.group(2))
            raise IndexModelMismatchError(
                f"The existing index holds {expected}-dimension vectors but the "
                f"current embedding model produces {received}. "
                "Rebuild the index to continue.",
                details={"expected_dimensions": expected, "received_dimensions": received},
            ) from e

    def delete(self, ids: list[str]) -> None:
        """Delete chunks by id."""
        if not ids:
            return
        self._collection.delete(ids=ids)

    def query(self, embedding: list[float], n_results: int) -> list[dict[str, Any]]:
        """Nearest-neighbour search, returning similarity-scored chunks."""
        results = self._collection.query(
            query_embeddings=[embedding],  # type: ignore[arg-type]
            n_results=n_results,
            include=["documents", "metadatas", "distances"],
        )

        # Chroma omits any field that was not requested, so treat a missing
        # block as an empty result rather than indexing into None.
        documents = results["documents"] or [[]]
        metadatas = results["metadatas"] or [[]]
        distances = results["distances"] or [[]]

        matches: list[dict[str, Any]] = []
        # Parallel result arrays must align; a mismatch would silently pair
        # content with the wrong score.
        for content, metadata, distance in zip(
            documents[0], metadatas[0], distances[0], strict=True
        ):
            matches.append(
                {
                    "id": (metadata or {}).get("id", "doc"),
                    "content": content,
                    "metadata": metadata,
                    "similarity": 1 - distance,
                }
            )
        return matches

    def check_storage(self) -> dict[str, Any]:
        """Verify the persistence directory exists and is writable."""
        try:
            directory = Path(self.path)
            directory.mkdir(parents=True, exist_ok=True)
            probe = directory / ".readiness_check"
            probe.write_text(datetime.now().isoformat(), encoding="utf-8")
            probe.unlink(missing_ok=True)
            return {
                "status": "ready",
                "provider": "chroma",
                "persistent_path": str(directory),
                "writable": True,
            }
        except OSError as e:
            logger.warning("Chroma storage readiness failed: %s", e)
            return {
                "status": "error",
                "provider": "chroma",
                "persistent_path": self.path,
                "writable": False,
                "error": str(e),
            }
