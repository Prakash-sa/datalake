"""Citation extraction and validation.

The plan requires that an answer never claim a source that was not sent to the
model. Generated `[S1]` markers are therefore parsed and checked against the
chunks that actually went into the prompt; anything outside that range is a
hallucinated citation and is reported rather than rendered.
"""

from __future__ import annotations

import re
from typing import Any

# Matches [S1], [S12], and grouped forms like [S1, S3] or [S1; S2].
_CITATION_PATTERN = re.compile(r"\[\s*S\s*(\d+(?:\s*[,;]\s*S?\s*\d+)*)\s*\]", re.IGNORECASE)
_INDEX_PATTERN = re.compile(r"\d+")


def extract_citation_indices(answer: str) -> list[int]:
    """Return the 1-based source indices cited in an answer, in order of first use."""
    seen: list[int] = []
    for match in _CITATION_PATTERN.finditer(answer or ""):
        for raw in _INDEX_PATTERN.findall(match.group(1)):
            index = int(raw)
            if index not in seen:
                seen.append(index)
    return seen


def validate_citations(answer: str, documents: list[dict[str, Any]]) -> dict[str, Any]:
    """Check an answer's citations against the chunks supplied to the model.

    Returns the cited chunk ids, any invalid indices, and which supplied sources
    went uncited. ``valid`` is False only when a citation points outside the
    supplied range, which is the case that would mislead a reader.
    """
    cited = extract_citation_indices(answer)
    supplied = len(documents)

    valid_indices = [i for i in cited if 1 <= i <= supplied]
    invalid_indices = [i for i in cited if i < 1 or i > supplied]
    uncited = [i for i in range(1, supplied + 1) if i not in valid_indices]

    return {
        "valid": not invalid_indices,
        "cited_indices": cited,
        "cited_chunk_ids": [documents[i - 1].get("id") for i in valid_indices],
        "invalid_indices": invalid_indices,
        "uncited_source_indices": uncited,
        "citation_count": len(valid_indices),
        "supplied_source_count": supplied,
    }
