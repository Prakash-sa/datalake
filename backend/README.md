# rag-backend

The Python sidecar: document ingestion, embedding, retrieval, and answer
generation for the [Document RAG Engine](../README.md).

This file stays here because `pyproject.toml` declares it as the package readme.
Longer documentation lives under [`docs/`](../docs/INDEX.md):

- [Backend architecture](../docs/architecture/BACKEND.md) — layering, ingestion
  state machine, retrieval, fingerprints, streaming
- [API reference](../docs/reference/API_REFERENCE.md) — endpoints, error codes,
  streaming formats
- [Troubleshooting](../docs/operations/TROUBLESHOOTING.md)

## Layout

```
pyproject.toml       dependencies, lint, test, and build configuration
rag-backend.spec     PyInstaller bundle for the desktop sidecar
scripts/             build-time helpers, including the embedding model fetch
src/rag_backend/
  app.py             create_app() factory
  __main__.py        python -m rag_backend
  settings.py        environment-driven configuration
  lifespan.py        startup and shutdown wiring
  dependencies.py    FastAPI dependency providers
  api/routes/        one module per endpoint group
  application/       use cases: retrieval, citations, jobs, evals, data transfer
  domain/            entities, job state machine, index fingerprints
  infrastructure/    ONNX embeddings, Chroma, Ollama, SQLite catalog
tests/{unit,integration}/
```

## Development

```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -e '.[dev]'
python scripts/fetch_embedding_model.py   # bundled embedding model, ~91MB

pytest                    # tests
ruff check src tests      # lint
ruff format src tests     # format
mypy                      # types
python -m rag_backend     # run on $HOST:$PORT (default 127.0.0.1:8000)
```

From the repository root, `make setup-backend`, `make check`, and
`make backend-run` wrap the same commands.

## Configuration

Copy `.env.example` to `.env`, or set the variables directly. `ENV` selects a
profile (`development`, `testing`, `production`) supplying defaults; anything set
explicitly wins.

Set `RAG_API_TOKEN` to require `Authorization: Bearer <token>`. The desktop shell
generates one per launch; leave it unset for local use.

Every setting is documented in [`.env.example`](.env.example).
