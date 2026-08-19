"""Choosing a generation model from what Ollama actually has installed.

Hardcoding a tag means the app fails with a 404 on any machine that pulled
something else. The configured name is treated as a preference: if it is
present it wins, otherwise an installed generation model is used and the
substitution is reported.

Pure functions, so selection is testable without a daemon.
"""

from __future__ import annotations

# Substrings that identify an embedding model. These cannot generate text, so
# selecting one would produce a confusing failure at query time rather than a
# clear one at startup.
EMBEDDING_HINTS = ("embed", "minilm", "bge-", "gte-", "e5-")

# Families preferred when nothing is configured, best first. Anything installed
# but unlisted is still usable; this only decides ordering.
PREFERRED_FAMILIES = (
    "qwen3",
    "qwen2.5",
    "llama3",
    "mistral",
    "phi",
    "gemma",
)


def family_of(name: str) -> str:
    """The part of a tag before the colon, e.g. ``qwen3`` from ``qwen3:4b``."""
    return name.split(":", 1)[0]


def is_embedding_model(name: str) -> bool:
    """Whether a tag names an embedding model rather than a generator."""
    lowered = name.lower()
    return any(hint in lowered for hint in EMBEDDING_HINTS)


def generation_candidates(installed: list[str]) -> list[str]:
    """Installed models that can generate text, best first."""
    usable = [name for name in installed if not is_embedding_model(name)]

    def rank(name: str) -> tuple[int, str]:
        family = family_of(name).lower()
        for index, preferred in enumerate(PREFERRED_FAMILIES):
            if family.startswith(preferred):
                return (index, name)
        # Unlisted families sort after known ones but remain selectable.
        return (len(PREFERRED_FAMILIES), name)

    return sorted(usable, key=rank)


def select_generation_model(installed: list[str], preferred: str | None) -> tuple[str | None, str]:
    """Pick a generation model and explain the choice.

    Returns the chosen tag, or None when nothing usable is installed, together
    with a reason suitable for logging and for the readiness report.
    """
    if preferred and preferred in installed:
        return preferred, "configured"

    # A bare family name should be satisfied by any of its tags, mirroring how
    # readiness treats required models.
    if preferred:
        family = family_of(preferred)
        for name in generation_candidates(installed):
            if family_of(name) == family:
                return name, "configured-family"

    candidates = generation_candidates(installed)
    if not candidates:
        return None, "none-installed"

    return candidates[0], "auto-selected" if preferred else "auto-selected-default"
