# Troubleshooting

Most problems surface as a structured error code in the interface. Look at
**Diagnostics** first: it reports the embedding provider, Ollama reachability,
disk space, and index state on one screen.

---

## Answers do not appear, but search works

Expected when Ollama is not running. Embeddings run in-process, so importing and
searching work regardless; only written answers need a generation model.

```bash
ollama serve
ollama pull qwen3:1.7b
```

The application selects whichever generation model you have installed, so the
tag does not need to match what is configured.

## `model_unavailable`

Either Ollama is unreachable, or no generation model is installed.

```bash
curl http://127.0.0.1:11434/api/tags   # reachable?
ollama list                            # anything installed?
```

If the daemon is running but the list contains only embedding models, pull a
generation model. Embedding-only models are excluded from selection because they
cannot produce text.

A `404` from Ollama means the requested tag does not exist; it is reported as
`model_unavailable` rather than a generation failure.

## `index_model_mismatch`

The index was built with a different embedding model. A Chroma collection fixes
its vector width on first write, so existing vectors cannot be compared with new
ones.

Rebuild from **Activity**, or:

```bash
curl -X POST http://127.0.0.1:8000/jobs/rebuild
```

This recreates the collection and re-queues every catalogued document, so the
original files must still be at their recorded paths. Anything moved is listed in
`missing_sources` and needs re-importing.

An **empty** index that reports a width conflict needs no action: the constraint
outlives deleted rows, and that case is recreated automatically on the next
import.

## `embedding_failed`

The document could not be embedded. Check the embedding provider in Diagnostics.

With the default local provider this usually means the bundled model is missing —
it is a build artifact, not committed:

```bash
make fetch-model
```

If `EMBEDDING_PROVIDER=ollama`, the daemon must be running and the embedding
model pulled.

## `unsupported_format`

Supported: PDF, DOCX, Markdown, HTML, plain text. The path must point at a
readable regular file. Encrypted or image-only PDFs contain no extractable text
and report `no_extractable_text`; OCR is not implemented.

## Import stays queued

The ingestion worker is started by the application. If jobs never leave `queued`
when running the backend by hand, confirm the process is alive and check the
logs — a worker that failed to start is logged at startup.

Cancelling takes effect at the next stage boundary rather than instantly, so an
import never leaves a half-committed index.

## Slow generation

Generation speed is entirely the local model and hardware. Large models on
CPU-only machines can take minutes per answer. Use a smaller model:

```bash
ollama pull qwen3:1.7b
```

Retrieval speed is unaffected — it does not use Ollama.

## The desktop window is blank

Almost always a build problem rather than a runtime one. The packaged UI is
served over `app://` under a CSP whose inline-script hashes are generated at
build time, so a stale build can leave scripts blocked and React unable to
hydrate.

```bash
make dist        # rebuilds the UI and regenerates the hashes
```

Run with `RAG_ENABLE_DEVTOOLS=true` to open developer tools in a packaged build.

## Backend unreachable from the app

Electron starts the sidecar itself and polls `/health`. If it never becomes
healthy, the sidecar failed to start; its output is prefixed `[rag-backend]` in
the terminal.

Running `make desktop` uses the backend virtualenv explicitly, because the shell's
`python3` may be the wrong version or lack the dependencies.

## Disk space

Diagnostics warns below 2 GB free. Indexing large documents needs room for both
the vectors and the SQLite catalog. Old catalog snapshots accumulate under
`backups/` and can be deleted.

---

## Reading the logs

Logs are written under the data directory in `logs/`, size-rotated, and
**redacted in production**: filesystem paths, bearer tokens, and long hex secrets
are stripped, including inside tracebacks. A path shown as `<path>` is redaction,
not corruption.

For full paths while debugging, run with `ENV=development`, which disables
redaction.

## Useful checks

```bash
curl http://127.0.0.1:8000/health        # is the backend alive
curl http://127.0.0.1:8000/readiness     # per-capability status
curl http://127.0.0.1:8000/diagnostics   # paths, disk, index counts
curl http://127.0.0.1:8000/jobs          # ingestion queue state
```

`readiness` reports embeddings and generation separately, which is the quickest
way to tell whether a problem affects search or only written answers.

## Container stack

```bash
make config      # render the merged compose configuration
make logs        # tail the running stack
make down        # stop everything
```

A service that will not start is usually a port conflict or an unset variable
that the production overlay requires.
