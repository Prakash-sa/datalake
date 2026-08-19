# Security Policy

## Supported versions

The `main` branch is the supported line until release tags are introduced.

## Reporting a vulnerability

Open a private security advisory where repository hosting supports it, or contact
the maintainer directly. Please do not include secrets, production data, or
proprietary documents in public issues.

## Security model

The desktop application is designed so the renderer is the least trusted part:

- The UI is served over a custom `app://` protocol, not `file://`, under a
  restrictive Content Security Policy. Inline-script hashes are generated at
  build time so the policy never needs `unsafe-inline`.
- The renderer runs with context isolation on and Node integration off. It has no
  filesystem, shell, or subprocess access.
- The preload exposes a fixed set of typed functions. There is no general
  `send` or `invoke` bridge, and the renderer never holds the backend token.
- The backend sidecar binds to `127.0.0.1` on a random port and requires a bearer
  token generated fresh on every launch.
- Electron fuses disable `RunAsNode`, `NODE_OPTIONS`, and inspector arguments in
  packaged builds, and require application code to load from the asar.

These properties are asserted by the Playwright Electron suite, not just
documented.

## Untrusted input

Imported document text is treated as untrusted. Prompts fence retrieved excerpts
between explicit delimiters and instruct the model that instructions inside them
are data. The eval corpus includes prompt-injection fixtures.

Generated citations are validated against the chunks actually supplied to the
model, so an answer cannot reference a source that was never retrieved.

## Operational guidance

- Treat the data directory — catalog, vectors, and backups — as sensitive.
- Keep `ALLOWED_ORIGINS` restricted when running the backend as a service.
- Do not expose Ollama, Chroma, or the backend beyond loopback.
- Point `OLLAMA_URL` at a remote host only deliberately; doing so sends document
  excerpts to that host.
- When running the Airflow stack, change the default MinIO and Airflow
  credentials before exposing it beyond localhost.
- Rotate credentials if `.env` files, logs, or document payloads are shared.

## Known issues

`THIRD_PARTY_NOTICES.md` records an unresolved licence conflict that affects
binary distribution. It is a compliance matter rather than a vulnerability, but
it blocks releasing builds.
