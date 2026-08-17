"""Tests for citation extraction and validation."""

from __future__ import annotations

from rag_backend.application.citations import extract_citation_indices, validate_citations


def _docs(count: int) -> list[dict]:
    return [{"id": f"chunk-{i}", "content": "text"} for i in range(1, count + 1)]


def test_extracts_single_citation():
    assert extract_citation_indices("The limit is 30s [S1].") == [1]


def test_extracts_multiple_citations_in_order_of_first_use():
    assert extract_citation_indices("[S2] then [S1] then [S2] again") == [2, 1]


def test_extracts_grouped_citations():
    assert extract_citation_indices("Both agree [S1, S3].") == [1, 3]
    assert extract_citation_indices("Both agree [S1; S2].") == [1, 2]


def test_extracts_multi_digit_citations():
    assert extract_citation_indices("See [S12].") == [12]


def test_ignores_text_without_citations():
    assert extract_citation_indices("No sources were relevant.") == []
    assert extract_citation_indices("") == []


def test_valid_when_every_citation_is_in_range():
    report = validate_citations("Answer [S1] and [S2].", _docs(3))

    assert report["valid"] is True
    assert report["cited_chunk_ids"] == ["chunk-1", "chunk-2"]
    assert report["citation_count"] == 2
    assert report["uncited_source_indices"] == [3]


def test_invalid_when_citing_a_source_that_was_never_supplied():
    # The model invented [S5] having been given only three sources.
    report = validate_citations("Answer [S5].", _docs(3))

    assert report["valid"] is False
    assert report["invalid_indices"] == [5]
    assert report["cited_chunk_ids"] == []


def test_zero_index_is_invalid():
    report = validate_citations("Answer [S0].", _docs(3))

    assert report["valid"] is False
    assert report["invalid_indices"] == [0]


def test_uncited_answer_is_still_valid():
    # Refusing to answer without evidence must not count as a citation failure.
    report = validate_citations("The excerpts do not contain enough evidence.", _docs(2))

    assert report["valid"] is True
    assert report["citation_count"] == 0
    assert report["uncited_source_indices"] == [1, 2]


def test_mixed_valid_and_invalid_citations_report_both():
    report = validate_citations("Answer [S1] and [S9].", _docs(2))

    assert report["valid"] is False
    assert report["cited_chunk_ids"] == ["chunk-1"]
    assert report["invalid_indices"] == [9]
