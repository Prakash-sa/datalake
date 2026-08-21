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


def _sse_events(body: str) -> list[dict]:
    import json

    return [
        json.loads(line[len("data: ") :]) for line in body.splitlines() if line.startswith("data: ")
    ]


def test_stream_endpoint_emits_sse_frames(client, stub_rag_service):
    def fake_stream(user_query, k=5, min_score=None, answer_mode="balanced", cancel=None):
        yield {"event": "sources", "documents": [], "truncated_document_count": 0}
        yield {"event": "token", "text": "hi"}
        yield {"event": "done", "status": "success", "answer": "hi"}

    stub_rag_service.stream_query_documents = fake_stream

    response = client.post("/query/stream", json={"query": "rag", "k": 3})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    events = _sse_events(response.text)
    assert [e["event"] for e in events] == ["sources", "token", "done"]


def test_stream_endpoint_validates_its_request(client):
    response = client.post("/query/stream", json={"query": "", "k": 3})

    assert response.status_code == 422


def test_stream_endpoint_is_in_the_openapi_schema(client):
    assert "/query/stream" in client.get("/openapi.json").json()["paths"]


def test_enqueue_returns_accepted_with_queued_jobs(client):
    response = client.post("/jobs", json={"paths": ["/tmp/a.md", "/tmp/b.md"]})

    assert response.status_code == 202
    jobs = response.json()["jobs"]
    assert len(jobs) == 2
    assert all(job["status"] == "queued" for job in jobs)


def test_enqueue_rejects_an_empty_path_list(client):
    assert client.post("/jobs", json={"paths": []}).status_code == 422


def test_jobs_can_be_listed_and_filtered(client):
    client.post("/jobs", json={"paths": ["/tmp/a.md"]})

    assert len(client.get("/jobs").json()["jobs"]) == 1
    assert client.get("/jobs", params={"status": "complete"}).json()["jobs"] == []


def test_unknown_job_returns_404(client):
    assert client.get("/jobs/nope").status_code == 404
    assert client.post("/jobs/nope/cancel").status_code == 404
    assert client.post("/jobs/nope/retry").status_code == 404


def test_job_can_be_cancelled(client):
    job_id = client.post("/jobs", json={"paths": ["/tmp/a.md"]}).json()["jobs"][0]["id"]

    response = client.post(f"/jobs/{job_id}/cancel")

    assert response.status_code == 200
    assert response.json()["job"]["status"] == "cancelled"


def test_job_endpoints_are_in_the_openapi_schema(client):
    paths = client.get("/openapi.json").json()["paths"]
    for expected in ("/jobs", "/jobs/{job_id}", "/jobs/{job_id}/cancel", "/jobs/{job_id}/retry"):
        assert expected in paths


def test_model_pull_stream_emits_progress_and_done(client, stub_rag_service):
    class StubOllama:
        def stream_pull_model(self, name, cancel=None):
            yield {"status": "downloading", "completed": 25, "total": 100}
            yield {"status": "success"}

    stub_rag_service.ollama = StubOllama()

    response = client.post("/models/pull/stream", json={"name": "qwen3:4b"})

    assert response.status_code == 200
    events = _sse_events(response.text)
    assert [e["event"] for e in events] == ["progress", "progress", "done"]
    assert events[0]["percent"] == 25.0
    # No byte counts on that record, so percent is absent rather than zero.
    assert events[1]["percent"] is None


def test_model_pull_stream_is_in_the_openapi_schema(client):
    assert "/models/pull/stream" in client.get("/openapi.json").json()["paths"]


def test_backup_endpoint_returns_a_path(client):
    response = client.post("/data/backup")

    assert response.status_code == 200
    assert response.json()["path"]


def test_backups_can_be_listed(client):
    assert client.get("/data/backups").json()["backups"] == []


def test_export_requires_a_destination(client):
    assert client.post("/data/export", json={}).status_code == 422


def test_export_returns_the_written_path(client):
    response = client.post("/data/export", json={"destination": "/tmp/lib.zip"})

    assert response.status_code == 200
    assert response.json()["path"] == "/tmp/lib.zip"


def test_import_reports_that_a_reindex_is_needed(client):
    response = client.post("/data/import", json={"source": "/tmp/lib.zip"})

    assert response.status_code == 200
    assert response.json()["reindex_required"] is True


def test_data_endpoints_are_in_the_openapi_schema(client):
    paths = client.get("/openapi.json").json()["paths"]
    for expected in (
        "/data/backup",
        "/data/backups",
        "/data/export",
        "/data/import",
        "/jobs/rebuild",
    ):
        assert expected in paths
