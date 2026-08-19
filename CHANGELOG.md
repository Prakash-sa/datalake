# Changelog

Notable changes to this project. The format loosely follows
[Keep a Changelog](https://keepachangelog.com/).

## Unreleased

### Added

- **Local embeddings.** `all-MiniLM-L6-v2` runs in-process through ONNX Runtime,
  so importing and searching require no external software. The model ships in
  the bundle rather than downloading on first run.
- **Streaming answers** over server-sent events, with cancellation. Sources are
  emitted before the first token so citations render while the answer streams.
- **Citation validation.** Generated `[S1]` markers are checked against the
  chunks actually supplied to the model; a citation outside that set is reported
  rather than rendered.
- **Context budgeting.** Retrieved chunks are assembled to a token budget,
  dropping the weakest evidence first and reporting what was truncated.
- **Persistent ingestion queue** with a state machine, per-document progress,
  retry, and cancellation that takes effect at stage boundaries.
- **Index fingerprints.** Every write records the embedding provider, model,
  digest, vector width, and chunker and parser versions, so an incompatible
  index is refused with a remedy instead of returning meaningless scores.
- **Export, import, and backup** of the catalog, using SQLite's backup API.
- **Retrieval metrics** — hit rate, recall, precision, nDCG, MRR, duplicate and
  empty-result rates — computed against the fixture corpus.
- **Desktop views**: first-run setup, Library, Activity, Settings, Diagnostics.
- **Structured error codes** with HTTP mapping and an actionable flag.
- **Log redaction and rotation.** Paths, tokens, and secrets are stripped from
  messages and rendered tracebacks in production.
- **Electron hardening**: `app://` protocol, CSP with build-time inline-script
  hashes, fuses disabling `RunAsNode` and `NODE_OPTIONS`, and a narrow preload.
- **Tests**: 254 backend, 48 frontend, and 5 Playwright tests driving the real
  Electron shell.

### Changed

- Generation models are discovered from what Ollama has installed rather than
  assumed from configuration.
- The interface no longer blocks on Ollama; it gates only on embeddings, which
  is the sole hard requirement.
- Repository flattened from a single-product monorepo to `backend/`, `frontend/`,
  and `evals/` at the root.
- Compose consolidated into a base file plus dev, prod, and Airflow overlays.
- Backend became an installable `src/` layout package with `pyproject.toml` as
  the single dependency source and a `uv.lock`.

### Fixed

- Embedding failures no longer misalign indexed content. Ids were appended
  before embedding, so a failure left content paired with the wrong vector.
- Imports no longer fail against an emptied index whose vector width is still
  constrained by the collection record.
- A 404 from Ollama is reported as `model_unavailable` rather than a generation
  failure, since the remedy is pulling a model.
- The packaged application hydrates. Its CSP blocked Next's inline scripts, so
  the window rendered as inert HTML.
- An unreachable sidecar no longer leaves the interface waiting forever.
- `CatalogStore` no longer leaks a SQLite connection per call.
- Backups taken in the same second no longer overwrite each other.

### Removed

- `minio` and `prometheus-client` backend dependencies, which nothing imported.
- Documentation describing the previous Airflow-centric architecture.

### Known issues

- Code signing and notarization are not configured; builds are unsigned.
- An unresolved dependency licence conflict blocks binary distribution. See
  [THIRD_PARTY_NOTICES](THIRD_PARTY_NOTICES.md).
