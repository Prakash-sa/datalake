"""Retrieval quality metrics for the eval suite.

Pure functions over ranked id lists, so retrieval quality can be scored against
the checked-in fixture corpus without Ollama running. All functions take
``retrieved`` in rank order (best first) and ``relevant`` as the ground-truth set.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence


def hit_rate_at_k(retrieved: Sequence[str], relevant: Iterable[str], k: int) -> float:
    """1.0 if any relevant document appears in the top K, else 0.0."""
    relevant_set = set(relevant)
    if not relevant_set:
        return 0.0
    return 1.0 if any(item in relevant_set for item in retrieved[:k]) else 0.0


def recall_at_k(retrieved: Sequence[str], relevant: Iterable[str], k: int) -> float:
    """Fraction of all relevant documents found in the top K."""
    relevant_set = set(relevant)
    if not relevant_set:
        return 0.0
    found = sum(1 for item in set(retrieved[:k]) if item in relevant_set)
    return found / len(relevant_set)


def precision_at_k(retrieved: Sequence[str], relevant: Iterable[str], k: int) -> float:
    """Fraction of the top K that is relevant."""
    if k <= 0:
        return 0.0
    window = retrieved[:k]
    if not window:
        return 0.0
    relevant_set = set(relevant)
    return sum(1 for item in window if item in relevant_set) / len(window)


def reciprocal_rank(retrieved: Sequence[str], relevant: Iterable[str]) -> float:
    """1/rank of the first relevant document, or 0.0 if none appears."""
    relevant_set = set(relevant)
    for rank, item in enumerate(retrieved, start=1):
        if item in relevant_set:
            return 1.0 / rank
    return 0.0


def mean_reciprocal_rank(
    results: Iterable[tuple[Sequence[str], Iterable[str]]],
) -> float:
    """Mean of per-query reciprocal ranks."""
    scores = [reciprocal_rank(retrieved, relevant) for retrieved, relevant in results]
    return sum(scores) / len(scores) if scores else 0.0


def dcg_at_k(retrieved: Sequence[str], relevant: Iterable[str], k: int) -> float:
    """Discounted cumulative gain with binary relevance."""
    relevant_set = set(relevant)
    return sum(
        1.0 / math.log2(rank + 1)
        for rank, item in enumerate(retrieved[:k], start=1)
        if item in relevant_set
    )


def ndcg_at_k(retrieved: Sequence[str], relevant: Iterable[str], k: int) -> float:
    """DCG normalised against the best achievable ordering."""
    relevant_set = set(relevant)
    if not relevant_set:
        return 0.0
    ideal = sum(1.0 / math.log2(rank + 1) for rank in range(1, min(len(relevant_set), k) + 1))
    if ideal == 0.0:
        return 0.0
    return dcg_at_k(retrieved, relevant_set, k) / ideal


def duplicate_rate(retrieved: Sequence[str]) -> float:
    """Fraction of results that repeat an earlier id."""
    if not retrieved:
        return 0.0
    return 1.0 - (len(set(retrieved)) / len(retrieved))


def summarize(
    results: Sequence[tuple[Sequence[str], Iterable[str]]], k: int = 5
) -> dict[str, float]:
    """Aggregate every metric across a set of queries."""
    if not results:
        return {
            f"hit_rate_at_{k}": 0.0,
            f"recall_at_{k}": 0.0,
            f"precision_at_{k}": 0.0,
            f"ndcg_at_{k}": 0.0,
            "mrr": 0.0,
            "duplicate_rate": 0.0,
            "empty_result_rate": 0.0,
            "query_count": 0.0,
        }

    materialized = [(list(retrieved), set(relevant)) for retrieved, relevant in results]
    count = len(materialized)

    def mean(values: Iterable[float]) -> float:
        collected = list(values)
        return sum(collected) / len(collected) if collected else 0.0

    return {
        f"hit_rate_at_{k}": mean(hit_rate_at_k(r, g, k) for r, g in materialized),
        f"recall_at_{k}": mean(recall_at_k(r, g, k) for r, g in materialized),
        f"precision_at_{k}": mean(precision_at_k(r, g, k) for r, g in materialized),
        f"ndcg_at_{k}": mean(ndcg_at_k(r, g, k) for r, g in materialized),
        "mrr": mean_reciprocal_rank(materialized),
        "duplicate_rate": mean(duplicate_rate(r) for r, _ in materialized),
        "empty_result_rate": sum(1 for r, _ in materialized if not r) / count,
        "query_count": float(count),
    }
