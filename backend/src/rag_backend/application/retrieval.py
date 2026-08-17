"""Hybrid retrieval ranking.

Pure functions with no I/O, so ranking behaviour is testable without a running
Ollama daemon or a populated Chroma collection.
"""

from __future__ import annotations

from typing import Any

# Standard reciprocal-rank-fusion damping constant.
RRF_K = 60

RETRIEVAL_VERSION = "dense-fts-rrf-v1"


def fuse_results(
    dense_ranked: list[dict[str, Any]], lexical_ranked: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Fuse dense and lexical rankings with reciprocal rank fusion.

    Scores are normalised against the top-ranked entry so the result stays in
    the [0, 1] range the API contract promises.
    """
    fused: dict[str, dict[str, Any]] = {}

    for source, ranked in (("dense", dense_ranked), ("fts", lexical_ranked)):
        for rank, item in enumerate(ranked, start=1):
            entry = fused.setdefault(
                item["id"],
                {**item, "relevance_score": 0.0, "retrieval_sources": []},
            )
            entry["relevance_score"] += 1.0 / (RRF_K + rank)
            entry["retrieval_sources"].append(source)

    if not fused:
        return []

    max_score = max(item["relevance_score"] for item in fused.values()) or 1.0
    results = []
    for item in fused.values():
        item["relevance_score"] = round(float(item["relevance_score"] / max_score), 3)
        item["metadata"] = {
            **(item.get("metadata") or {}),
            "retrieval_sources": ",".join(sorted(set(item["retrieval_sources"]))),
        }
        results.append(item)

    return sorted(results, key=lambda item: item["relevance_score"], reverse=True)


def candidate_pool_size(k: int, collection_count: int) -> int:
    """Over-fetch before fusion so lexical hits can outrank weak dense hits."""
    return min(max(k * 4, 20), collection_count)
