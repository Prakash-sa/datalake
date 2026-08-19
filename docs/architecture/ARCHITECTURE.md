# System Architecture

A local-first desktop application for retrieval-augmented question answering over
a personal or team document library. Everything that matters — parsing,
embedding, indexing, retrieval — runs on the user's machine.

The repository also contains an Airflow ingestion pipeline for bulk server-side
loading. It is optional and independent of the desktop product; see
[PIPELINE_GUIDE](../operations/PIPELINE_GUIDE.md).

## Design principles

**No prerequisites for the core loop.** Importing and searching must work on a
machine with nothing installed. This drives the choice to embed in-process rather
than delegate to a model server.

**Answers must be traceable.** A response that cannot be tied back to a source
passage is not useful for the documents people actually search: contracts,
manuals, papers. Citations are validated rather than trusted.

**The renderer is untrusted.** It gets a narrow typed bridge, no filesystem, no
network client, and no secrets.

**Failures must be actionable.** Every error carries a structured code and a flag
for whether the user can fix it.

**Nothing leaves the machine.** No telemetry, no accounts, no remote calls except
an optional local model daemon.

## Runtime

```
┌─────────────────────────── Electron main ────────────────────────────┐
│  serves the UI over app://           spawns and supervises sidecar   │
│  owns the bearer token               native dialogs                  │
│  typed IPC channels                  CSP, navigation, permissions    │
└──────────────┬───────────────────────────────────┬───────────────────┘
               │ typed IPC                         │ spawn, /health poll
               ▼                                   ▼
┌──────────────────────────┐        ┌──────────────────────────────────┐
│  Renderer                │        │  Python sidecar (FastAPI)        │
│  Next.js static export   │        │  127.0.0.1, random port          │
│  sandboxed, no Node      │        │                                  │
│                          │        │  ONNX embeddings (in-process)    │
│  Query · Library         │        │  Chroma vectors                  │
│  Activity · Settings     │        │  SQLite catalog + FTS5           │
│  Diagnostics             │        │  ingestion job queue             │
└──────────────────────────┘        │  retrieval, fusion, citations    │
                                    └───────────────┬──────────────────┘
                                                    │ optional
                                                    ▼
                                            ┌───────────────┐
                                            │    Ollama     │
                                            │  generation   │
                                            └───────────────┘
```

The renderer never issues HTTP. It calls typed preload functions; Electron main
performs the loopback request with the token attached. Streaming works the same
way, with frames pushed to the renderer over a per-stream channel it never names.

## Storage

```
userData/
├── app.db            catalog, chunks, FTS index, settings, jobs, traces, evals
├── vector/chroma/    embeddings and chunk text
├── logs/             size-rotated, redacted
└── backups/          catalog snapshots
```

Four kinds of state are kept deliberately separate:

| Kind | Where | Why |
| --- | --- | --- |
| Document memory | Chroma | Vectors and immutable chunk text |
| Catalog memory | SQLite | Paths, hashes, versions, job state |
| Retrieval memory | SQLite FTS5 | Lexical index over chunk text |
| Evaluation memory | SQLite | Eval runs, query traces |

The SQLite schema is versioned and migrated forward on startup.

## Ingestion

```
queued → parsing → chunking → embedding → committing → complete
                                      ↳ failed / cancelled
```

Every transition is persisted, so progress survives a restart and the UI can show
per-document status with retry and cancel. A single worker drains the queue:
ingestion is I/O bound and Chroma expects one writer, so concurrency would add
risk without throughput.

Cancellation is checked at stage boundaries, so a cancelled import never leaves a
half-committed index. Only failed jobs are retried; a cancellation was
deliberate.

Supported formats are PDF, DOCX, Markdown, HTML, and text. Files are validated
by extension and size, hashed with SHA-256 for duplicate detection, normalised,
and split by a versioned recursive chunker.

## Retrieval

1. Embed the query locally.
2. Dense search over Chroma, over-fetching a candidate pool.
3. Lexical search over SQLite FTS5.
4. Fuse both rankings with reciprocal rank fusion.
5. Normalise scores into `[0, 1]`.
6. Assemble context to a token budget, best evidence first.
7. Generate with fenced, citable excerpts.
8. Validate every citation against the supplied chunks.

Dense retrieval alone misses exact identifiers; lexical alone misses paraphrase.
RRF needs no score calibration between them, which matters because cosine
similarity and BM25 are not comparable scales.

## Embeddings

| Provider | Runtime | Needs Ollama |
| --- | --- | --- |
| `local` (default) | all-MiniLM-L6-v2, 384-dim, ONNX Runtime | no |
| `ollama` | whatever the daemon serves | yes |

The model ships inside the bundle rather than downloading on first run, since
"offline" is untrue if the first launch needs a network.

Generation models are **discovered**, not assumed: the configured tag is a
preference, and if it is absent an installed generation model is selected and the
substitution reported. A hardcoded tag fails with a 404 on any machine that
pulled something else.

## Index fingerprints

Every write stamps the index with its embedding provider, model, digest, vector
width, chunker and parser versions, and a schema version.

A change to any of those means existing vectors cannot be compared with new
queries, so indexing refuses with `index_model_mismatch` and points at
`POST /jobs/rebuild`. A changed chunker or parser is advisory: retrieval
behaviour differs, but the vectors remain valid.

A Chroma collection fixes its vector width on first write, and that constraint
outlives its rows — an emptied index still rejects a different width. That case
is detected from the driver's own rejection and recovered automatically, since
nothing is at stake.

## Security boundary

- UI served over `app://`, never `file://`, under a restrictive CSP whose
  inline-script hashes are generated at build time
- Context isolation on, Node integration off, narrow preload surface
- Backend bound to loopback with a per-launch bearer token
- Electron fuses disable `RunAsNode`, `NODE_OPTIONS`, and inspector arguments
- Document text is untrusted; prompts fence it and the eval corpus includes
  injection fixtures
- Logs redact paths, tokens, and secrets, including inside tracebacks

The Playwright Electron suite asserts these rather than relying on documentation.

## Backend layering

```
api/routes  →  application  →  domain
                    ↑
              infrastructure
```

Dependencies point inward. `domain` holds entities, the job state machine, and
fingerprint comparison as pure logic. `infrastructure` adapts Chroma, Ollama,
ONNX, and SQLite. Composition happens in `lifespan` and `dependencies`, with no
module-level singletons.

Detail: [backend/ARCHITECTURE.md](../../backend/ARCHITECTURE.md).

## Known limitations

- Code signing and notarization are not done, so builds are unsigned
- An unresolved dependency licence conflict blocks binary distribution; see
  [THIRD_PARTY_NOTICES](../../THIRD_PARTY_NOTICES.md)
- Generation speed depends entirely on the local model and hardware; large models
  are impractical on CPU-only machines
- Retrieval quality baselines have not been measured against a large corpus
