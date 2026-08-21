# Deployment

There are two ways to run this project. They are independent.

| | For | Entry point |
| --- | --- | --- |
| **Desktop application** | Individuals searching their own documents | `make desktop`, or a packaged installer |
| **Ingestion pipeline** | Bulk server-side loading from object storage | `make up-airflow` |

Most users want the desktop application. The pipeline is optional and
independent of it.

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

Build each platform on its own runner. The sidecar contains
architecture-specific binaries, so cross-building is not reliable.
`.github/workflows/desktop-release.yml` runs the matrix.

> **Before distributing builds**, provide the release-only GGUF model URL and
> checksum, then review [THIRD_PARTY_NOTICES](../../THIRD_PARTY_NOTICES.md). Code
> signing is optional for early GitHub Releases, but unsigned builds must be
> labelled as tester builds. See [Releasing](#releasing).

### Releasing

GitHub Releases can host unsigned artifacts. The workflow attaches downloadable
macOS, Windows, and Linux builds to `rag-desktop-vMAJOR.MINOR.PATCH` tags after
the native matrix passes.

**Gates.** Backend tests, frontend typecheck and export, eval fixtures, and an
Electron build on each native runner must pass, with SBOM and SHA-256 checksums
generated and dependency and model licences reviewed. The release workflow also
requires `LOCAL_LLM_GGUF_URL` and `LOCAL_LLM_GGUF_SHA256` so the bundled local
generation model is reproducible and license-reviewed. Tester releases may set
`ALLOW_MISSING_LOCAL_LLM=1` to publish without bundled written-answer generation;
import and search still work, and users can switch written-answer generation to
Ollama in Settings.

**Unsigned early releases.** Allowed for friends, testers, developers, portfolio
downloads, and open-source previews. macOS Gatekeeper may require System Settings
-> Privacy & Security -> Open Anyway. Windows SmartScreen may require More info
-> Run anyway. Release notes must say this plainly.

**macOS.** Build on macOS. Sign with a Developer ID Application certificate,
enable Hardened Runtime, notarize through App Store Connect, and staple the
ticket when moving beyond tester releases. The workflow uses `CSC_LINK`,
`CSC_KEY_PASSWORD`, `APPLE_API_KEY`, `APPLE_API_KEY_ID`, and `APPLE_API_ISSUER`
when present. Validate signed builds with `codesign`, `spctl`, and an install on
a clean machine.

**Windows.** Build on Windows. Sign the NSIS installer and the shipped
executables, including the Python sidecar where practical. Timestamp every
signature and keep the publisher identity stable across releases. The workflow
uses `CSC_LINK` and `CSC_KEY_PASSWORD` when present.

**Linux.** Build AppImage and DEB on the oldest supported Ubuntu baseline and
publish SHA-256 checksums. Electron's auto-updater does not cover Linux, so ship
update instructions instead.

**Versioning.** SemVer, tagged `rag-desktop-vMAJOR.MINOR.PATCH`.

### Data location

The application stores everything under the OS user-data directory:

| Platform | Path |
| --- | --- |
| macOS | `~/Library/Application Support/rag-query-frontend/` |
| Windows | `%APPDATA%\rag-query-frontend\` |
| Linux | `~/.config/rag-query-frontend/` |

Uninstalling does not remove it.

---

## Ingestion pipeline

Docker is used for one thing: the optional Airflow pipeline that loads documents
in bulk from object storage. The desktop application uses none of it.

```bash
cp compose/.env.example compose/.env
make up-airflow      # Ollama, MinIO, Chroma, Postgres, Redis, Airflow
make down
make logs
```

`make config` renders the merged configuration without starting anything, which
is what CI validates.

Details: [PIPELINE_GUIDE](PIPELINE_GUIDE.md).

### Running the backend as a service

There is no container image for the backend. To run it as a service rather than
as a desktop sidecar, install the package and run it directly:

```bash
pip install ./backend
python -m rag_backend      # honours HOST, PORT, and the rest of .env.example
```

Bind it to loopback and set `RAG_API_TOKEN` unless it is behind something that
authenticates for it.


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
