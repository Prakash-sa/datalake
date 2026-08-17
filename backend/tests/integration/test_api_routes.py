"""Route wiring, validation, and status-code contract tests."""

from __future__ import annotations


def test_health_reports_healthy_when_service_is_up(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_health_reports_503_before_the_service_initializes(unready_client):
    response = unready_client.get("/health")

    assert response.status_code == 503


def test_stats_returns_the_declared_schema(client):
    response = client.get("/stats")

    assert response.status_code == 200
    body = response.json()
    assert body["total_documents"] == 3
    assert body["catalog_documents"] == 1


def test_readiness_is_exposed(client):
    assert client.get("/readiness").status_code == 200


def test_documents_listing_is_empty_by_default(client):
    response = client.get("/documents")

    assert response.status_code == 200
    assert response.json()["documents"] == []


def test_deleting_an_unknown_document_returns_404(client):
    response = client.delete("/documents/does-not-exist")

    assert response.status_code == 404


def test_search_returns_scored_results(client):
    response = client.post("/documents/search", json={"query": "rag", "k": 3})

    assert response.status_code == 200
    results = response.json()["results"]
    assert results[0]["id"] == "chunk-1"


def test_search_rejects_an_empty_query(client):
    response = client.post("/documents/search", json={"query": "", "k": 3})

    assert response.status_code == 422


def test_search_rejects_k_above_the_limit(client):
    response = client.post("/documents/search", json={"query": "rag", "k": 500})

    assert response.status_code == 422


def test_index_rejects_documents_missing_required_fields(client):
    response = client.post("/documents/index", json={"documents": [{"id": "only-id"}]})

    assert response.status_code == 422


def test_openapi_schema_builds(client):
    response = client.get("/openapi.json")

    assert response.status_code == 200
    paths = response.json()["paths"]
    for expected in ("/health", "/stats", "/documents", "/documents/search", "/query", "/eval"):
        assert expected in paths
