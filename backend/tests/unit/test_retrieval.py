"""Tests for hybrid retrieval ranking."""

from __future__ import annotations

from rag_backend.application.retrieval import candidate_pool_size, fuse_results


def _item(doc_id: str, content: str = "text") -> dict:
    return {"id": doc_id, "content": content, "metadata": {}, "relevance_score": 0.0}


def test_fuse_results_returns_empty_for_no_input():
    assert fuse_results([], []) == []


def test_fuse_results_normalizes_scores_into_unit_range():
    fused = fuse_results([_item("a"), _item("b")], [_item("c")])

    assert {item["id"] for item in fused} == {"a", "b", "c"}
    assert all(0.0 <= item["relevance_score"] <= 1.0 for item in fused)
    assert fused[0]["relevance_score"] == 1.0


def test_fuse_results_ranks_documents_found_by_both_retrievers_highest():
    dense = [_item("shared"), _item("dense-only")]
    lexical = [_item("shared"), _item("lexical-only")]

    fused = fuse_results(dense, lexical)

    assert fused[0]["id"] == "shared"
    assert fused[0]["metadata"]["retrieval_sources"] == "dense,fts"


def test_fuse_results_is_sorted_descending():
    fused = fuse_results([_item("a"), _item("b"), _item("c")], [_item("c")])

    scores = [item["relevance_score"] for item in fused]
    assert scores == sorted(scores, reverse=True)


def test_candidate_pool_never_exceeds_collection_size():
    assert candidate_pool_size(k=5, collection_count=3) == 3
    assert candidate_pool_size(k=5, collection_count=100) == 20
    assert candidate_pool_size(k=50, collection_count=1000) == 200
