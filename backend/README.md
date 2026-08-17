# RAG Query Engine — Backend

Local-first FastAPI sidecar providing semantic search and grounded question
answering over locally ingested documents. Runs either as a container service or
as a PyInstaller-packaged sidecar launched by the Electron shell.

## Layout

```
backend/
├── pyproject.toml            # dependencies, lint, test, and build config
├── rag-backend.spec          # PyInstaller bundle definition
├── src/rag_backend/
│   ├── app.py                # create_app() application factory
│   ├── __main__.py           # `python -m rag_backend` entry point
│   ├── settings.py           # environment-driven configuration
│   ├── lifespan.py           # startup/shutdown, builds the RAG service
│   ├── dependencies.py       # FastAPI dependency providers
│   ├── logging_config.py
│   ├── middleware/           # bearer-token auth for the desktop sidecar
│   ├── api/routes/           # one module per endpoint group
│   ├── schemas/              # request/response models
│   ├── domain/               # entities and value objects
│   ├── application/          # use cases: RAG, ingestion, retrieval, evals
│   └── infrastructure/       # Chroma, Ollama, and SQLite catalog adapters
└── tests/
    ├── conftest.py           # app fixtures backed by a stub service
    ├── unit/
    └── integration/
```

Dependencies flow inward only: `api` → `application` → `domain`, with
`infrastructure` supplying adapters that the application layer depends on.

## Development

```bash
uv venv --python 3.12 && source .venv/bin/activate
uv pip install -e '.[dev]'

pytest                    # tests
ruff check src tests      # lint
ruff format src tests     # format
mypy                      # type check

python -m rag_backend     # run the API on $HOST:$PORT (default 127.0.0.1:8000)
```

From the repository root, `make backend-test`, `make lint`, and `make backend-run`
wrap the same commands.

## Configuration

Copy `.env.example` to `.env` and adjust. Every value is also settable as a plain
environment variable. `ENV` selects a profile (`development`, `testing`,
`production`) that supplies defaults; any variable you set explicitly wins over
the profile.

Set `RAG_API_TOKEN` to require `Authorization: Bearer <token>` on every request.
The Electron shell generates one per launch; leave it unset for local container
use.

## Endpoints

| Method | Path                 | Purpose                                  |
| ------ | -------------------- | ---------------------------------------- |
| GET    | `/health`            | Liveness; 503 until the service is ready |
| GET    | `/stats`             | Counters and index sizes                 |
| GET    | `/readiness`         | Capability and dependency report         |
| GET    | `/diagnostics`       | Local support diagnostics                |
| GET    | `/models`            | Installed and required Ollama models     |
| POST   | `/models/pull`       | Pull an Ollama model                     |
| GET    | `/settings`          | Read runtime settings                    |
| POST   | `/settings`          | Persist runtime settings                 |
| POST   | `/documents/index`   | Index in-memory documents                |
| POST   | `/documents/ingest`  | Ingest local files by path               |
| GET    | `/documents`         | List catalog documents                   |
| DELETE | `/documents/{id}`    | Delete a document and its chunks         |
| POST   | `/documents/search`  | Hybrid dense + lexical search            |
| POST   | `/query`             | Full RAG pipeline with citations         |
| POST   | `/eval`              | Deterministic release-gating evals       |

Interactive docs are served at `/docs` only when `DEBUG=true`.
