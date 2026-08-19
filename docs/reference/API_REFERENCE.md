# API Reference

The backend is a local FastAPI service. In the desktop application it runs as a
sidecar bound to `127.0.0.1` on a random port, and the Electron main process
holds the bearer token — the renderer never talks to it directly.

Run it standalone with `make backend-run` (default `http://127.0.0.1:8000`).
Interactive docs are served at `/docs` when `DEBUG=true`.

- [Authentication](#authentication)
- [Errors](#errors)
- [Health and diagnostics](#health-and-diagnostics)
- [Documents](#documents)
- [Ingestion jobs](#ingestion-jobs)
- [Search and answers](#search-and-answers)
- [Models](#models)
- [Settings](#settings)
- [Data transfer](#data-transfer)
- [Evaluation](#evaluation)

## Authentication

When `RAG_API_TOKEN` is set, every request must carry it:

```
Authorization: Bearer <token>
```

The desktop shell generates a fresh token per launch. Leave the variable unset
for local development and the requirement is disabled.

## Errors

Failures carry a machine-readable code rather than an arbitrary message.

| Code | Meaning | HTTP |
| --- | --- | --- |
| `validation_failed` | Request did not satisfy the schema | 400 |
| `unsupported_format` | File type or path cannot be read | 415 |
| `document_not_found` | No such document | 404 |
| `parse_failed` | The file could not be parsed | 422 |
| `no_extractable_text` | Parsed, but contained no text | 422 |
| `model_unavailable` | Ollama unreachable, or the model is not installed | 503 |
| `embedding_failed` | The document could not be embedded | 502 |
| `generation_failed` | The model failed to produce an answer | 502 |
| `generation_timeout` | Generation exceeded its deadline | 504 |
| `retrieval_failed` | Search failed | 500 |
| `no_relevant_evidence` | Nothing relevant was retrieved | 200 |
| `index_model_mismatch` | The index was built by a different embedding model | 409 |
| `storage_unavailable` | The data directory is not writable | 503 |
| `cancelled` | The caller abandoned the request | 499 |

Errors also carry `actionable`, indicating whether the user can resolve the
problem themselves — by starting Ollama, pulling a model, or rebuilding the
index — rather than by retrying unchanged.

---

## Health and diagnostics

### `GET /health`

Liveness. Returns 503 until the RAG service has initialised.

```json
{ "status": "healthy", "timestamp": "2026-08-19T00:00:00+00:00" }
```

### `GET /stats`

Counters and index sizes.

```json
{
  "documents_indexed": 56, "queries_processed": 12, "errors": 0,
  "total_documents": 56, "catalog_documents": 3,
  "timestamp": "2026-08-19T00:00:00"
}
```

### `GET /readiness`

Capability report. Embeddings and generation are reported separately, so
"can I search" and "can I get a written answer" are distinguishable.

```json
{
  "status": "ready",
  "capabilities": {
    "embeddings": {
      "status": "ready", "provider": "local",
      "model": "all-MiniLM-L6-v2", "dimensions": 384,
      "requires_external_software": false
    },
    "generation": {
      "status": "ready", "model": "qwen3.5:latest",
      "configured_model": "qwen3:4b", "selection": "auto-selected",
      "installed_models": ["qwen3-embedding:0.6b", "qwen3.5:latest"]
    },
    "ollama": { "status": "ready", "missing_models": [] },
    "index": { "status": "match", "rebuild_required": false },
    "memory": { "status": "ready", "documents": 56 }
  }
}
```

`selection` explains how the generation model was chosen: `configured` when the
configured tag is installed, `configured-family` when another tag of the same
family was used, or `auto-selected` when something else was substituted.

### `GET /diagnostics`

Runtime versions, data paths, disk usage, storage writability, and stats. Never
includes document text or prompts.

---

## Documents

### `GET /documents`

Lists indexed source documents with parser, chunker, and embedding model
versions, plus chunk counts.

### `POST /documents/ingest`

Ingest local files **synchronously**. Prefer `POST /jobs` for anything that
should report progress.

```json
{ "paths": ["/Users/me/notes.pdf"], "force_reindex": false }
```

### `POST /documents/index`

Index already-prepared records. Each needs `id` and `content`.

```json
{ "documents": [{ "id": "doc-1", "content": "…", "metadata": {} }] }
```

Returns `index_model_mismatch` if the existing index was built by a different
embedding model.

### `DELETE /documents/{document_id}`

Removes the catalog row, its chunks, and its vectors together. 404 if unknown.

---

## Ingestion jobs

Imports run through a persisted state machine:

```
queued → parsing → chunking → embedding → committing → complete
                                      ↳ failed / cancelled
```

Progress survives a restart. Only failed jobs can be retried; a cancelled job
stays cancelled.

### `POST /jobs` → `202`

```json
{ "paths": ["/Users/me/report.pdf"], "force_reindex": false }
```

### `GET /jobs`

Newest first. Filter with `?status=failed&status=complete`, limit with `?limit=`.

```json
{
  "status": "success",
  "jobs": [{
    "id": "job_9f2…", "source_path": "/Users/me/report.pdf",
    "status": "complete", "chunks_total": 56, "chunks_done": 56,
    "attempts": 1, "error_code": null, "finished_at": "2026-08-19T00:00:00+00:00"
  }]
}
```

### `GET /jobs/{job_id}` · `POST /jobs/{job_id}/cancel` · `POST /jobs/{job_id}/retry`

Cancellation takes effect at the next stage boundary, so a cancelled import
never leaves a half-committed index.

### `POST /jobs/rebuild` → `202`

Recreates the vector collection and re-queues every catalogued document. Required
after an embedding-model change. Documents whose source file has moved are
returned in `missing_sources` rather than failing the request.

---

## Search and answers

### `POST /documents/search`

Hybrid retrieval without generation. Works with no Ollama installed.

```json
{ "query": "how are rankings merged?", "k": 5, "min_score": 0.0 }
```

```json
{
  "status": "success",
  "results": [{
    "id": "doc_a1b2_chunk_00003",
    "content": "…",
    "relevance_score": 0.94,
    "metadata": { "source_name": "notes.pdf", "retrieval_sources": "dense,fts" }
  }]
}
```

`retrieval_sources` shows which retrievers found the chunk.

### `POST /query`

Full pipeline: retrieve, budget the context, generate, validate citations.

```json
{
  "status": "success",
  "answer": "Rankings are merged with reciprocal rank fusion [S1].",
  "retrieved_documents": [ … ],
  "document_count": 3,
  "truncated_document_count": 2,
  "processing_time_seconds": 4.1,
  "citations": {
    "valid": true, "citation_count": 1,
    "cited_chunk_ids": ["doc_a1b2_chunk_00003"],
    "invalid_indices": [], "uncited_source_indices": [2, 3],
    "supplied_source_count": 3
  }
}
```

`status` is `degraded` with a `code` when generation was unavailable; the
response still carries retrieved, cited context. `truncated_document_count`
reports documents dropped to fit the context budget. `invalid_indices` lists
citations pointing outside the supplied sources.

### `POST /query/stream`

Same pipeline as server-sent events. Sources arrive before the first token so the
UI can render citations while the answer streams. Disconnecting cancels
generation.

```
data: {"event":"sources","documents":[…],"truncated_document_count":0}
data: {"event":"token","text":"Rankings "}
data: {"event":"done","status":"success","answer":"…","citations":{…}}
data: {"event":"error","code":"model_unavailable","actionable":true}
```

---

## Models

### `GET /models`

Installed models, the ones this backend requires, and anything missing.

### `POST /models/pull`

Blocking pull. Prefer the streaming form for anything user-facing.

### `POST /models/pull/stream`

Streams progress as SSE:

```
data: {"event":"progress","model":"qwen3:1.7b","status":"downloading",
       "completed":128000000,"total":1100000000,"percent":11.6}
data: {"event":"done","model":"qwen3:1.7b"}
```

`percent` is `null` for statuses that report no byte counts.

---

## Settings

### `GET /settings` · `POST /settings`

```json
{
  "ollama_url": "http://127.0.0.1:11434",
  "embedding_model": "qwen3-embedding:0.6b",
  "llm_model": "qwen3:4b",
  "temperature": 0.1,
  "model_profiles": { "light": { … }, "balanced": { … } }
}
```

Changes persist immediately but apply on restart, since models are constructed
once at startup. Changing the embedding model invalidates the index and requires
`POST /jobs/rebuild`.

---

## Data transfer

| Endpoint | Purpose |
| --- | --- |
| `POST /data/backup` | Snapshot the catalog via SQLite's backup API |
| `GET /data/backups` | List snapshots, newest first |
| `POST /data/export` | Write a portable `.zip` of the catalog and a manifest |
| `POST /data/import/inspect` | Read an archive's manifest without importing |
| `POST /data/import` | Restore a catalog, backing up the current one first |

Exports exclude vectors, which are reproducible from the sources and would
dominate the archive size, so an import reports `reindex_required: true`.

---

## Evaluation

### `POST /eval`

Deterministic release gating.

```json
{
  "k": 5,
  "cases": [{
    "id": "hybrid-retrieval",
    "query": "How are dense and lexical results combined?",
    "answer_contains": ["fusion"],
    "min_documents": 1,
    "min_relevance": 0.1,
    "relevant_chunk_ids": ["retrieval-hybrid"]
  }]
}
```

A case fails if required terms are missing, too few documents are retrieved,
relevance is below threshold, or the answer cites a source it was never given.

When any case declares `relevant_chunk_ids`, the response includes aggregate
`retrieval_metrics`: hit rate, recall, precision, nDCG at K, MRR, duplicate rate,
and empty-result rate.

Fixtures live in [`evals/`](../../evals/README.md).
