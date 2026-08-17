# Contributing

## Development Setup

Run `make help` to see every available target.

1. Install dependencies:
   ```bash
   make setup            # backend venv (editable, with dev extras) + frontend deps
   ```
2. Start the supporting services (Ollama, MinIO, Chroma):
   ```bash
   cp compose/.env.example compose/.env
   make up
   ```
3. Run the pieces you are working on:
   ```bash
   make backend-run      # FastAPI on 127.0.0.1:8000
   make frontend-run     # Next.js dev server on :3000
   make desktop          # Electron shell against the dev server
   ```
4. Build a local desktop package:
   ```bash
   make dist
   ```

## Quality Bar

Before opening a pull request:

```bash
make check              # lint + format check + type check + tests
```

- New behavior needs tests. Pure logic belongs in `backend/tests/unit/`;
  request/response contracts belong in `backend/tests/integration/`.
- Keep retrieval and prompt changes covered by deterministic `/eval` cases.
- Keep desktop changes compatible with the web UI; Electron should wrap the app,
  not fork product behavior.
- Do not commit local model files, Chroma data, `.env` files, logs, or generated
  desktop installers.
- Prefer small pull requests with a clear test plan, and screenshots for UI changes.

Optional but recommended:

```bash
pre-commit install      # runs ruff, whitespace, and secret checks on commit
```

## Project Layout

| Path | Contents |
| --- | --- |
| `backend/` | FastAPI service (`src/rag_backend/`) and its tests |
| `frontend/` | Next.js web UI and Electron desktop shell |
| `evals/` | Deterministic eval fixtures and the eval guide |
| `compose/` | Base compose stack plus dev/prod/airflow overlays |
| `infra/airflow/` | Airflow image and ingestion DAGs |
| `ops/scripts/` | Operational shell scripts |
| `docs/` | Architecture, reference, operations, and security docs |

Backend layering is documented in [backend/ARCHITECTURE.md](backend/ARCHITECTURE.md).

## Pull Request Checklist

- `make check` passes.
- The backend starts and `/health` returns healthy.
- `/readiness` reports loop engineering, memory, eval, and open-source capabilities.
- Electron launches with `make desktop`.
- Desktop packaging includes the PyInstaller sidecar in `backend/dist`.
- New configuration is documented in `backend/.env.example` or
  `compose/.env.example`, whichever consumes it.
