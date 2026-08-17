"""Tests for eval case grading."""

from __future__ import annotations

from rag_backend.application.eval_service import grade_case
from rag_backend.schemas.requests import EvalCase


def _result(answer: str, scores: list[float], status: str = "success") -> dict:
    return {
        "status": status,
        "answer": answer,
        "retrieved_documents": [
            {"id": f"c{i}", "relevance_score": score} for i, score in enumerate(scores)
        ],
        "processing_time_seconds": 0.5,
    }


def test_case_passes_when_all_expectations_met():
    case = EvalCase(
        id="c1", query="what is rrf", answer_contains=["fusion"], min_documents=1, min_relevance=0.5
    )

    graded = grade_case(case, _result("Reciprocal rank FUSION combines rankings", [0.8]))

    assert graded["passed"] is True
    assert graded["missing_terms"] == []
    assert graded["max_relevance"] == 0.8


def test_answer_matching_is_case_insensitive():
    case = EvalCase(id="c1", query="q", answer_contains=["Citations"])

    graded = grade_case(case, _result("answer with citations [S1]", [0.9]))

    assert graded["answer_contains_passed"] is True


def test_missing_terms_fail_the_case():
    case = EvalCase(id="c1", query="q", answer_contains=["chroma", "sqlite"])

    graded = grade_case(case, _result("mentions chroma only", [0.9]))

    assert graded["passed"] is False
    assert graded["missing_terms"] == ["sqlite"]


def test_insufficient_documents_fail_the_case():
    case = EvalCase(id="c1", query="q", min_documents=3)

    graded = grade_case(case, _result("answer", [0.9]))

    assert graded["min_documents_passed"] is False
    assert graded["passed"] is False


def test_relevance_below_threshold_fails_the_case():
    case = EvalCase(id="c1", query="q", min_relevance=0.75)

    graded = grade_case(case, _result("answer", [0.4, 0.6]))

    assert graded["min_relevance_passed"] is False
    assert graded["max_relevance"] == 0.6


def test_errored_query_fails_even_when_checks_pass():
    case = EvalCase(id="c1", query="q", min_documents=0)

    graded = grade_case(case, _result("", [], status="error"))

    assert graded["passed"] is False


def test_no_documents_yields_zero_max_relevance():
    case = EvalCase(id="c1", query="q", min_documents=0)

    graded = grade_case(case, _result("answer", []))

    assert graded["max_relevance"] == 0.0
