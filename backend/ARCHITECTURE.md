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
| `data_transfer.py`     | Export, import, and backup of local data                   |
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

## Logging

`logging_config.py` owns handler, level, and filter setup; library modules only
call `logging.getLogger(__name__)`.

Output is redacted in production. No call site interpolates a document path, but
the exceptions they log carry them — `No extractable text found in
/Users/sam/medical results.pdf` — and a filename alone can be sensitive.
Redaction therefore rewrites the formatted message, including rendered
tracebacks, replacing filesystem paths, bearer tokens, and long hex secrets.
URLs are deliberately preserved, since the Ollama endpoint is configuration and
is needed to diagnose connection failures.

This applies to logs only. The API still returns real paths, because the Library
and Activity views must show users their own files.

A size-rotating file handler writes to `<APP_DATA_DIR>/logs`, bounding disk use
at `LOG_MAX_BYTES * (LOG_BACKUP_COUNT + 1)`. An unwritable log directory is
logged and skipped rather than preventing startup.

## Embeddings

Two providers share one interface, selected by `EMBEDDING_PROVIDER`:

| Provider | Runtime | Needs Ollama |
| --- | --- | --- |
| `local` (default) | all-MiniLM-L6-v2, 384-dim, ONNX Runtime in-process | no |
| `ollama` | whatever model the daemon serves | yes |

The local provider is what removes the external prerequisite. Importing and
searching work on a machine with nothing installed; Ollama is needed only for
generated prose, and `query_documents` already degrades to returning cited
context when it is absent. Readiness reports embeddings as a capability separate
from Ollama, so "can I search" and "can I get an answer" are distinguishable.
The desktop UI gates on the former only: first-run setup presents Ollama as an
optional enhancement and lets the user proceed without it.

The model ships inside the sidecar rather than being fetched on first run, which
is what makes the offline claim true. `scripts/fetch_embedding_model.py` installs
it at build time, verifying the archive against a published SHA-256. A bundle
missing its model falls back to Ollama rather than failing to start.

Output was verified identical to Chroma's own ONNX implementation (cosine 1.0),
so the two are interchangeable. Pooling ignores padding, so a vector does not
depend on what else shared its batch.

## Index fingerprints

Every write to the vector store stamps the index with the configuration that
produced it: embedding model, model digest, chunker and parser versions, and an
index schema version. `domain/fingerprint.py` compares that stamp against the
running configuration as pure logic.

A changed embedding provider, model, digest, dimension count, or schema
version means existing vectors
cannot be compared against new queries, so `rebuild_required` is set and
`/jobs/rebuild` re-queues every catalogued document. A changed chunker or parser
is advisory: retrieval behaviour differs, but existing vectors remain valid.

A Chroma collection's vector width is fixed when its first embedding is
written, so a model change cannot be resolved by overwriting rows: the
collection has to be recreated. Indexing therefore checks compatibility before
embedding and refuses with `index_model_mismatch` and a remedy, rather than
letting a dimension error surface from inside the driver.

Compatibility is decided from the vectors themselves, not only from the recorded
fingerprint. An index written before fingerprints existed has none to compare
against, which is the ordinary upgrade case, and a provider may not know its own
width until it has embedded once. The stored collection is therefore measured
directly, and the vectors about to be written are checked against it immediately
before the upsert. An empty index adopts
the new configuration silently, since nothing is at risk. `/jobs/rebuild` resets
the collection and re-queues every catalogued document.

Digests matter because a tag can be repointed at new weights without its name
changing. An unknown digest on either side is not treated as a mismatch, since
an index built while Ollama was unreachable has none to record.

## Data transfer

`data_transfer.py` snapshots the catalog with SQLite's backup API rather than
copying the file, so a snapshot taken while the app is running is consistent.
Exports are a zip holding that snapshot plus a manifest; vectors are excluded
because they are reproducible from the sources and would dominate the size.

Import restores through the same backup API rather than overwriting the database
file. The catalog runs in WAL mode, so replacing the bytes under a live
connection leaves a stale `-wal` that SQLite replays over the restored data. The
current catalog is backed up first, and the caller is told a reindex is needed,
since vectors are not part of the archive.

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

`POST /models/pull/stream` uses the same framing for model downloads, emitting
`progress` frames with Ollama's status and byte counts. A pull can take many
minutes, so a buffered response would leave first-run setup with no signal.

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
