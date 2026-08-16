# Security Policy

## Supported Versions

The `main` branch is the supported development line until release tags are introduced.

## Reporting a Vulnerability

Open a private security advisory when repository hosting supports it, or contact the maintainer directly. Do not include secrets, production data, or proprietary documents in public issues.

## Operational Guidance

- Treat indexed documents and Chroma volumes as sensitive data.
- Keep `ALLOWED_ORIGINS` restricted in production.
- Do not expose Ollama, MinIO, Chroma data directories, or generated desktop builds with embedded secrets.
- Rotate credentials if `.env` files, MinIO keys, logs, or document payloads are accidentally shared.
