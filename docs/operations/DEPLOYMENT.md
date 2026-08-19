# Deployment

There are two ways to run this project. They are independent.

| | For | Entry point |
| --- | --- | --- |
| **Desktop application** | Individuals searching their own documents | `make desktop`, or a packaged installer |
| **Container stack** | A shared backend, or the Airflow ingestion pipeline | `make up` |

Most users want the desktop application. The container stack exists for
server-side bulk ingestion and for running the API as a service.

---

## Desktop application

### From source

```bash
make setup      # backend venv, embedding model, frontend dependencies
make desktop
```

Electron starts the Python sidecar itself, binding it to `127.0.0.1` on a random
port with a bearer token generated for that launch.

### Building an installer

```bash
make dist
```

This builds the static UI, generates the CSP hashes for its inline scripts,
packages the sidecar with PyInstaller, and produces platform artifacts through
electron-builder.

Build each platform on its own runner. macOS signing only works on macOS, and
the sidecar contains architecture-specific binaries, so cross-building is not
reliable. `.github/workflows/desktop-release.yml` runs the matrix.

> **Before distributing builds**, resolve the licence conflict recorded in
> [THIRD_PARTY_NOTICES](../../THIRD_PARTY_NOTICES.md). Signing and notarization
> are also not yet configured, so current artifacts are unsigned.

### Data location

The application stores everything under the OS user-data directory:

| Platform | Path |
| --- | --- |
| macOS | `~/Library/Application Support/rag-query-frontend/` |
| Windows | `%APPDATA%\rag-query-frontend\` |
| Linux | `~/.config/rag-query-frontend/` |

Uninstalling does not remove it.

---

## Container stack

```bash
cp compose/.env.example compose/.env
make up                 # base stack with development overrides
make up-prod            # production overlay, detached
make up-airflow         # base stack plus the Airflow pipeline
make down
```

Compose is organised as a base file plus overlays, so service definitions are not
duplicated:

| File | Contents |
| --- | --- |
| `compose/compose.yml` | Ollama, MinIO, Chroma, backend, frontend |
| `compose/compose.dev.yml` | Source mounting for reload |
| `compose/compose.prod.yml` | Hardened image, restart policy, resource limits |
| `compose/compose.airflow.yml` | Postgres, Redis, Airflow services |

`make config` renders the merged configuration without starting anything, which
is also what CI validates.

### Production overlay

The production overlay requires several variables to be set explicitly and will
refuse to start without them:

```
ALLOWED_ORIGINS       exact origins, never "*"
NEXT_PUBLIC_API_URL   address the browser will use
MINIO_ROOT_USER       not the default
MINIO_ROOT_PASSWORD   not the default
```

It builds `Dockerfile.prod`: a multi-stage image running Gunicorn with Uvicorn
workers as a non-root user.

### Backend configuration

Every value is an environment variable; see
[`backend/.env.example`](../../backend/.env.example). The ones that matter most:

| Variable | Default | Notes |
| --- | --- | --- |
| `ENV` | `production` | Profile supplying defaults; explicit variables win |
| `HOST` | `127.0.0.1` | Keep on loopback unless deliberately serving |
| `EMBEDDING_PROVIDER` | `local` | `local` needs no external software |
| `OLLAMA_URL` | `http://127.0.0.1:11434` | Remote values send excerpts off the machine |
| `RAG_API_TOKEN` | unset | When set, every request must present it |
| `LOG_REDACT` | `true` | Strips paths and secrets from logs |

---

## Backups

```bash
curl -X POST http://127.0.0.1:8000/data/backup      # snapshot the catalog
curl -X POST http://127.0.0.1:8000/data/export \
  -H 'Content-Type: application/json' \
  -d '{"destination":"/path/library.zip"}'
```

Snapshots use SQLite's backup API, so one taken while the service is running is
consistent. Exports exclude vectors, which are reproducible from the sources, so
an import reports that a reindex is required.

Back up before any upgrade that changes the schema. An import backs up the
existing catalog automatically.

---

## Upgrades

The SQLite schema migrates forward on startup. The vector index does not: if an
upgrade changes the embedding model, indexing refuses with
`index_model_mismatch` and `POST /jobs/rebuild` recreates the collection from the
catalogued sources.

Source files must still be at their recorded paths for a rebuild; anything moved
is reported in `missing_sources` and needs re-importing.
