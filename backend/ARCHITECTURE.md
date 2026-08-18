# Backend Architecture

The backend follows a clean/hexagonal layering. Dependencies point inward: outer
layers know about inner ones, never the reverse.

```
              ┌─────────────────────────────────┐
              │  api/routes/                    │  HTTP controllers
              │  middleware/                    │
              └───────────────┬─────────────────┘
                              │ depends on
              ┌───────────────▼─────────────────┐
              │  application/                   │  use cases
              │  rag_service, eval_service,     │
              │  ingestion_service, retrieval   │
              └───────────────┬─────────────────┘
                              │ depends on
              ┌───────────────▼─────────────────┐
              │  domain/                        │  entities, no I/O
              └─────────────────────────────────┘
                              ▲ implements ports for
              ┌───────────────┴─────────────────┐
              │  infrastructure/                │  adapters
              │  ChromaVectorStore, OllamaClient│
              │  CatalogStore                   │
              └─────────────────────────────────┘
```

## Layers

### `domain/`

Entities and value objects (`Document`, `SearchResult`, `QueryResult`,
`EngineStats`) as plain dataclasses with validation in `__post_init__`, plus
`jobs.py`, which defines the ingestion state machine and its legal transitions.
No framework imports, no I/O.

### `application/`

Use cases and orchestration.

| Module                 | Responsibility                                            |
| ---------------------- | --------------------------------------------------------- |
| `rag_service.py`       | Facade owning runtime state; indexing, search, query       |
| `ingestion_service.py` | File parsing, normalisation, and chunking                  |
| `retrieval.py`         | Reciprocal-rank fusion — pure functions, no I/O            |
| `prompts.py`           | Versioned prompt templates and context rendering           |
| `eval_service.py`      | Deterministic release-gating checks and retrieval metrics  |
| `ingestion_jobs.py`    | Persistent job queue and single background worker          |
| `citations.py`         | Citation parsing and range validation - pure functions     |
| `metrics.py`           | Hit rate, recall, MRR, nDCG - pure functions                |

`retrieval.py` and `prompts.py` hold no state, so ranking and prompt behaviour
are testable without a running Ollama or a populated index.

### `infrastructure/`

Adapters for everything external.

| Module             | Wraps                                                   |
| ------------------ | ------------------------------------------------------- |
| `vector_store.py`  | Chroma persistent collection; metadata normalisation     |
| `ollama_client.py` | Ollama REST API over `urllib` (keeps the bundle small)   |
| `catalog_store.py` | SQLite catalog, FTS index, query traces, eval runs       |

### `schemas/`

Pydantic request and response models. These are the wire contract and are
deliberately separate from `domain/` entities, so the API can evolve without
reshaping the core model.

### `api/routes/`

One module per endpoint group: `health`, `models`, `settings`, `documents`,
`search`, `stream`, `evals`. Each exports a `router`; `routes/__init__.py`
aggregates them into a single `api_router`.

Handlers stay thin — validate, delegate, map results to HTTP status codes. Logic
that needs testing belongs in `application/`.

## Composition

There are no module-level singletons. Wiring happens explicitly:

- `settings.py` — immutable, environment-driven configuration. The `ENV` profile
  supplies defaults; explicitly set variables override them.
- `lifespan.py` — builds `DocumentRAGService` on startup and stores it on
  `app.state`. If construction fails the app still starts so `/health` can report
  503 rather than the process dying.
- `dependencies.py` — `RagServiceDep` / `EvalServiceDep` resolve the service per
  request and raise 503 when it is unavailable.
- `app.py` — `create_app(settings)` factory. Accepting settings means tests can
  build an app without touching process environment variables.

Middleware order matters: CORS is registered last so it wraps the auth
middleware, letting preflight `OPTIONS` requests through before token checks.

## Ingestion jobs

Imports run through a persisted state machine:

```text
queued -> parsing -> chunking -> embedding -> committing -> complete
                                          \-> failed / cancelled
```

Every transition is written to SQLite, so progress survives a restart and the UI
can render per-document status, actionable error codes, retry, and cancel.
Transitions are validated in `domain/jobs.py` as pure logic.

A single worker thread drains the queue. Ingestion is I/O bound on Ollama and
Chroma, and Chroma expects one writer, so concurrency would add risk without
throughput. The application owns the worker: `lifespan` starts it and stops it,
and `enqueue()` deliberately does not spawn one, which keeps the queue drivable
synchronously in tests.

Cancellation is checked at stage boundaries, so a cancelled import stops between
stages rather than leaving a half-committed index. Only failed jobs can be
retried; a cancelled job stays cancelled, since stopping it was deliberate.

## Streaming

`POST /query/stream` runs the same pipeline as `/query` but emits server-sent
events:

```text
{"event":"sources","documents":[...],"truncated_document_count":n}
{"event":"token","text":"..."}                     (repeated)
{"event":"done","answer":"...","citations":{...}}
{"event":"error","code":"model_unavailable",...}   (terminal)
```

Sources arrive before the first token so the UI can render citations while the
answer streams. Disconnecting sets a cancellation event that the Ollama client
checks between chunks, so abandoning a request stops generation rather than
leaving the model producing an answer nobody will read.

Failures carry a structured `code` from `rag_backend.errors`, separating
"retrieval failed" from "model unavailable" from "no relevant evidence", and
flagging whether the user can act on it.

## Entry points

| Context          | Command                                   |
| ---------------- | ----------------------------------------- |
| Local / Electron | `python -m rag_backend`                   |
| Dev container    | `uvicorn rag_backend.app:app --reload`    |
| Prod container   | `gunicorn rag_backend.app:app -k uvicorn.workers.UvicornWorker` |
| Desktop sidecar  | PyInstaller bundle from `rag-backend.spec` |

## Retrieval pipeline

1. Embed the query via Ollama.
2. Dense search in Chroma over an over-fetched candidate pool
   (`candidate_pool_size`), filtered by `min_score`.
3. Lexical search over the SQLite FTS index.
4. Fuse both rankings with RRF and normalise scores into `[0, 1]`.
5. Render the top `k` chunks as fenced, citable `[S1]` excerpts.
6. Generate an answer; if the LLM is unavailable, degrade to returning context
   rather than failing the request.
7. Record a privacy-safe trace: the query is hashed and no content is stored.

## Adding a feature

**New endpoint** — add schemas to `schemas/`, a handler to the relevant
`api/routes/` module, and the logic to `application/`. Register the router in
`routes/__init__.py` only if you added a new module.

**New external service** — add an adapter under `infrastructure/`, inject it in
`DocumentRAGService.__init__`, and keep the HTTP details out of `application/`.

**New setting** — add a field to `Settings` with its `alias` matching the
environment variable, and document it in `.env.example`.

## Testing

```bash
pytest                 # everything
pytest tests/unit      # pure logic, no external services
pytest tests/integration
```

`tests/conftest.py` provides a `client` fixture backed by a stub service, so
route behaviour is verifiable without Ollama or Chroma running.
