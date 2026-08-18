"""Vector index fingerprints.

The plan requires that vectors produced by different embedding models are never
queried together. Every index therefore records what produced it, and a
mismatch is reported rather than silently returning nonsense similarities.

Pure comparison logic with no I/O, so the rules are testable directly.
"""

from __future__ import annotations

from typing import Any

#: Bumped when the on-disk vector layout changes in a way that needs a rebuild.
INDEX_SCHEMA_VERSION = 1

#: Fields that, if changed, invalidate every existing vector.
REBUILD_FIELDS = (
    "embedding_provider",
    "embedding_model",
    "embedding_digest",
    "embedding_dimensions",
    "index_schema_version",
)

#: Fields that change retrieval behaviour but not the vectors themselves.
ADVISORY_FIELDS = ("chunker_version", "parser_version")


def build_fingerprint(
    embedding_model: str,
    embedding_digest: str | None,
    chunker_version: str,
    parser_version: str,
    embedding_provider: str = "local",
    embedding_dimensions: int | None = None,
) -> dict[str, Any]:
    """Describe the configuration that produced an index."""
    return {
        "embedding_provider": embedding_provider,
        "embedding_dimensions": embedding_dimensions,
        "embedding_model": embedding_model,
        "embedding_digest": embedding_digest,
        "chunker_version": chunker_version,
        "parser_version": parser_version,
        "index_schema_version": INDEX_SCHEMA_VERSION,
    }


def compare(stored: dict[str, Any] | None, current: dict[str, Any]) -> dict[str, Any]:
    """Compare a stored fingerprint against the running configuration.

    ``rebuild_required`` means existing vectors cannot be trusted.
    ``advisory`` means retrieval changed but the vectors are still valid.

    An unknown stored digest is not treated as a mismatch: an index built while
    Ollama was unreachable has no digest to compare, and forcing a rebuild for
    that would be worse than proceeding.
    """
    if not stored:
        return {
            "status": "unknown",
            "rebuild_required": False,
            "changed": [],
            "advisory_changed": [],
        }

    changed = []
    for field in REBUILD_FIELDS:
        old, new = stored.get(field), current.get(field)
        # Unknown values on either side cannot prove a mismatch: an index
        # built while Ollama was unreachable records no digest, and the Ollama
        # provider does not know its dimensions until it embeds.
        if field in ("embedding_digest", "embedding_dimensions") and (not old or not new):
            continue
        if old != new:
            changed.append(field)

    advisory = [
        field
        for field in ADVISORY_FIELDS
        if stored.get(field) is not None and stored.get(field) != current.get(field)
    ]

    return {
        "status": "mismatch" if changed else ("advisory" if advisory else "match"),
        "rebuild_required": bool(changed),
        "changed": changed,
        "advisory_changed": advisory,
    }
