"""Deterministic retrieval and answer-grounding checks used for release gating.

Grading rules live here rather than in the ``/eval`` route so they can be unit
tested without an HTTP client, and so retrieval metrics can be aggregated across
a batch.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from rag_backend.application.citations import validate_citations
from rag_backend.application.metrics import summarize
from rag_backend.application.rag_service import DocumentRAGService
from rag_backend.schemas.requests import EvalCase


def grade_case(case: EvalCase, result: dict[str, Any]) -> dict[str, Any]:
    """Grade one query result against a case's expectations."""
    documents = result.get("retrieved_documents", [])
    answer = (result.get("answer") or "").lower()

    missing_terms = [term for term in (case.answer_contains or []) if term.lower() not in answer]
    max_relevance = max((doc.get("relevance_score", 0.0) for doc in documents), default=0.0)

    # Prefer the citation report the pipeline already produced; recompute only
    # when grading a result that predates it.
    citations = result.get("citations") or validate_citations(result.get("answer") or "", documents)

    answer_contains_passed = not missing_terms
    min_documents_passed = len(documents) >= case.min_documents
    min_relevance_passed = max_relevance >= case.min_relevance
    citations_valid = bool(citations.get("valid", True))

    return {
        "id": case.id,
        "passed": (
            answer_contains_passed
            and min_documents_passed
            and min_relevance_passed
            and citations_valid
            and result.get("status") != "error"
        ),
        "answer_contains_passed": answer_contains_passed,
        "min_documents_passed": min_documents_passed,
        "min_relevance_passed": min_relevance_passed,
        "document_count": len(documents),
        "max_relevance": max_relevance,
        "missing_terms": missing_terms,
        "processing_time_seconds": result.get("processing_time_seconds", 0.0),
        "retrieved_chunk_ids": [doc.get("id", "") for doc in documents],
        "citation_count": citations.get("citation_count", 0),
        "citations_valid": citations_valid,
    }


class EvalService:
    """Runs eval batches against the RAG pipeline and records each run."""

    def __init__(self, rag_service: DocumentRAGService) -> None:
        self._rag = rag_service

    def run(self, cases: list[EvalCase], k: int = 5) -> dict[str, Any]:
        """Execute every case, grade it, and persist the run to the catalog."""
        results = []
        # Only cases carrying ground truth can contribute to retrieval metrics.
        scored: list[tuple[list[str], set[str]]] = []

        for case in cases:
            result = self._rag.query_documents(
                user_query=case.query, k=k, min_score=case.min_relevance
            )
            graded = grade_case(case, result)
            results.append(graded)

            if case.relevant_chunk_ids:
                scored.append((graded["retrieved_chunk_ids"], set(case.relevant_chunk_ids)))

        passed_cases = sum(1 for result in results if result["passed"])
        response = {
            "status": "success",
            "passed": passed_cases == len(cases),
            "total_cases": len(cases),
            "passed_cases": passed_cases,
            "results": results,
            "retrieval_metrics": summarize(scored, k=k) if scored else {},
        }

        self._rag.catalog.record_eval_run(
            run_id=f"eval_{uuid4().hex}",
            status="passed" if response["passed"] else "failed",
            request={"cases": [case.model_dump() for case in cases], "k": k},
            result=response,
        )
        return response
