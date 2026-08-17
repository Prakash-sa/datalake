"""Tests for retrieval quality metrics."""

from __future__ import annotations

import math

from rag_backend.application.metrics import (
    dcg_at_k,
    duplicate_rate,
    hit_rate_at_k,
    mean_reciprocal_rank,
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
    reciprocal_rank,
    summarize,
)


def test_hit_rate_is_binary():
    assert hit_rate_at_k(["a", "b", "c"], {"c"}, 3) == 1.0
    assert hit_rate_at_k(["a", "b", "c"], {"z"}, 3) == 0.0


def test_hit_rate_respects_the_k_cutoff():
    assert hit_rate_at_k(["a", "b", "c"], {"c"}, 2) == 0.0


def test_recall_counts_the_fraction_of_relevant_found():
    assert recall_at_k(["a", "b"], {"a", "b", "c", "d"}, 5) == 0.5
    assert recall_at_k(["a", "b", "c"], {"a"}, 5) == 1.0


def test_recall_ignores_duplicates_in_the_result_list():
    assert recall_at_k(["a", "a", "a"], {"a", "b"}, 5) == 0.5


def test_precision_measures_the_returned_window():
    assert precision_at_k(["a", "z", "y", "x"], {"a"}, 4) == 0.25
    assert precision_at_k([], {"a"}, 5) == 0.0


def test_reciprocal_rank_uses_the_first_relevant_position():
    assert reciprocal_rank(["z", "a"], {"a"}) == 0.5
    assert reciprocal_rank(["a", "z"], {"a"}) == 1.0
    assert reciprocal_rank(["y", "z"], {"a"}) == 0.0


def test_mean_reciprocal_rank_averages_queries():
    result = mean_reciprocal_rank([(["a"], {"a"}), (["z", "b"], {"b"})])

    assert result == (1.0 + 0.5) / 2


def test_mean_reciprocal_rank_of_nothing_is_zero():
    assert mean_reciprocal_rank([]) == 0.0


def test_dcg_discounts_by_position():
    assert dcg_at_k(["a"], {"a"}, 3) == 1.0
    assert dcg_at_k(["z", "a"], {"a"}, 3) == 1.0 / math.log2(3)


def test_ndcg_is_one_for_a_perfect_ranking():
    assert ndcg_at_k(["a", "b"], {"a", "b"}, 5) == 1.0


def test_ndcg_penalizes_a_worse_ordering():
    perfect = ndcg_at_k(["a", "b", "z"], {"a", "b"}, 3)
    worse = ndcg_at_k(["z", "a", "b"], {"a", "b"}, 3)

    assert worse < perfect
    assert 0.0 < worse < 1.0


def test_ndcg_without_relevant_documents_is_zero():
    assert ndcg_at_k(["a"], set(), 3) == 0.0


def test_duplicate_rate_detects_repeats():
    assert duplicate_rate(["a", "b", "c"]) == 0.0
    assert duplicate_rate(["a", "a", "b", "b"]) == 0.5
    assert duplicate_rate([]) == 0.0


def test_summarize_reports_every_metric():
    summary = summarize([(["a", "z"], {"a"}), (["y", "b"], {"b"})], k=2)

    assert summary["query_count"] == 2.0
    assert summary["hit_rate_at_2"] == 1.0
    assert summary["mrr"] == (1.0 + 0.5) / 2
    assert summary["empty_result_rate"] == 0.0


def test_summarize_tracks_empty_results():
    summary = summarize([([], {"a"}), (["a"], {"a"})], k=5)

    assert summary["empty_result_rate"] == 0.5
    assert summary["hit_rate_at_5"] == 0.5


def test_summarize_of_nothing_is_all_zero():
    summary = summarize([], k=5)

    assert summary["query_count"] == 0.0
    assert summary["mrr"] == 0.0
