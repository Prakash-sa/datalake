# Security Threat Model

## Assets

- Local documents imported by the user.
- Extracted chunks, embeddings, and source metadata.
- SQLite catalog at `app.db`.
- Chroma vector index under the application data directory.
- Ollama model selections and runtime settings.
- Query traces and eval history.

## Trust Boundaries

- Electron renderer is untrusted UI code and has no Node.js or filesystem access.
- Electron main owns native file dialogs, backend lifecycle, and backend bearer token.
- Python backend only binds to `127.0.0.1` and requires a per-launch bearer token when started by Electron.
- Ollama is a local prerequisite and is contacted only through its configured loopback URL.
- Imported document text is untrusted data and must not be treated as instructions.

## Primary Risks

- Prompt injection through imported documents.
- Exposing the backend to the local network.
- Renderer-to-main IPC abuse.
- Path traversal or unsupported file ingestion.
- Leaking document text through logs, telemetry, crash reports, or issue reports.
- Shipping unsigned or tampered installers.
- Mixing vector indexes created with incompatible embedding models.

## Current Controls

- Backend defaults to `127.0.0.1`.
- Electron generates a random per-launch backend token.
- Renderer API access is limited to typed preload functions.
- Electron denies unexpected permissions and navigation.
- Static UI is served over a custom `app://` protocol with CSP.
- File ingestion validates file type, size, and regular-file status.
- Query traces store hashes, chunk IDs, scores, and timings, not raw document content.

## Release Blockers

- Signed and notarized macOS artifacts.
- Signed Windows installer and backend executable.
- SHA-256 checksums and SBOM attached to releases.
- Packaged app smoke tests on clean macOS, Windows, and Linux machines.
- Prompt-injection eval fixtures and citation validation gates.
