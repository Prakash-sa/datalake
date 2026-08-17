"""Tests for context assembly and token budgeting."""

from __future__ import annotations

from rag_backend.application.prompts import (
    build_context,
    estimate_tokens,
    select_context_documents,
)


def _doc(doc_id: str, size: int = 100, score: float = 0.9) -> dict:
    return {"id": doc_id, "content": "x" * size, "relevance_score": score}


def test_estimate_tokens_scales_with_length():
    assert estimate_tokens("") == 0
    assert estimate_tokens("abcd") == 1
    assert estimate_tokens("a" * 4000) == 1000


def test_all_documents_kept_when_within_budget():
    docs = [_doc("a"), _doc("b"), _doc("c")]

    assert select_context_documents(docs, token_budget=10_000) == docs


def test_documents_are_dropped_from_the_tail_when_over_budget():
    docs = [_doc("a", 4000), _doc("b", 4000), _doc("c", 4000)]

    selected = select_context_documents(docs, token_budget=1500)

    # Ranked best-first, so the weakest evidence is what gets dropped.
    assert [d["id"] for d in selected] == ["a"]


def test_top_document_is_kept_even_when_it_alone_exceeds_the_budget():
    # Otherwise an oversized chunk would produce an empty context and a
    # spurious "no evidence" answer.
    docs = [_doc("huge", 40_000), _doc("small", 100)]

    selected = select_context_documents(docs, token_budget=10)

    assert [d["id"] for d in selected] == ["huge"]


def test_empty_input_selects_nothing():
    assert select_context_documents([], token_budget=1000) == []


def test_build_context_numbers_sources_from_one():
    context = build_context([_doc("a"), _doc("b")])

    assert "[S1 | chunk_id=a" in context
    assert "[S2 | chunk_id=b" in context


def test_build_context_renumbers_after_truncation():
    # Indices must match the truncated list, or citations resolve to the wrong
    # chunk.
    docs = [_doc("a", 4000), _doc("b", 4000)]
    selected = select_context_documents(docs, token_budget=1200)

    context = build_context(selected)

    assert "[S1 | chunk_id=a" in context
    assert "chunk_id=b" not in context
