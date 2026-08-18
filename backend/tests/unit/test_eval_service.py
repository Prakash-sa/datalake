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


class _StubRag:
    """Returns a canned query result and records the eval run."""

    def __init__(self, result: dict):
        self._result = result
        self.catalog = self
        self.recorded: list[dict] = []

    def query_documents(self, user_query, k=5, min_score=None):
        return self._result

    def record_eval_run(self, run_id, status, request, result):
        self.recorded.append({"status": status, "result": result})


def _case(**kwargs) -> EvalCase:
    return EvalCase(id=kwargs.pop("id", "c1"), query=kwargs.pop("query", "q"), **kwargs)


def test_invalid_citations_fail_the_case():
    # A hallucinated citation must not pass a release gate.
    graded = grade_case(
        _case(min_documents=1),
        {
            "status": "success",
            "answer": "Answer [S9].",
            "retrieved_documents": [{"id": "c1", "relevance_score": 0.9}],
            "citations": {"valid": False, "citation_count": 0},
        },
    )

    assert graded["citations_valid"] is False
    assert graded["passed"] is False


def test_graded_case_reports_retrieved_chunk_ids():
    graded = grade_case(
        _case(min_documents=1),
        {
            "status": "success",
            "answer": "ok [S1]",
            "retrieved_documents": [
                {"id": "a", "relevance_score": 0.9},
                {"id": "b", "relevance_score": 0.5},
            ],
        },
    )

    assert graded["retrieved_chunk_ids"] == ["a", "b"]


def test_retrieval_metrics_are_computed_for_cases_with_ground_truth():
    from rag_backend.application.eval_service import EvalService

    rag = _StubRag(
        {
            "status": "success",
            "answer": "ok [S1]",
            "retrieved_documents": [
                {"id": "a", "relevance_score": 0.9},
                {"id": "z", "relevance_score": 0.4},
            ],
        }
    )

    response = EvalService(rag).run([_case(relevant_chunk_ids=["a"])], k=2)

    metrics = response["retrieval_metrics"]
    assert metrics["hit_rate_at_2"] == 1.0
    assert metrics["mrr"] == 1.0
    assert metrics["query_count"] == 1.0


def test_metrics_are_omitted_when_no_case_declares_ground_truth():
    from rag_backend.application.eval_service import EvalService

    rag = _StubRag({"status": "success", "answer": "ok", "retrieved_documents": [{"id": "a"}]})

    response = EvalService(rag).run([_case()], k=5)

    assert response["retrieval_metrics"] == {}


def test_run_is_persisted_with_its_pass_status():
    from rag_backend.application.eval_service import EvalService

    rag = _StubRag({"status": "success", "answer": "ok", "retrieved_documents": [{"id": "a"}]})

    EvalService(rag).run([_case(min_documents=99)], k=5)

    assert rag.recorded[0]["status"] == "failed"
