# ADR 0001: Local-First Desktop RAG

## Status

Accepted. Amended — see *Revisions*.

## Context

The product needs to answer questions over documents that may be private or
proprietary: contracts, medical records, internal reports. Sending that content
to a hosted service is unacceptable to the intended users, and requiring an
account or API key is friction they will not accept.

## Decision

Build a desktop application in which everything runs locally:

- **Electron** for the shell, owning the sidecar lifecycle, native dialogs, and
  the security boundary.
- **Next.js static export** for the UI, served over a custom `app://` protocol.
  No server-side rendering is needed, and bundling a Node server would add
  startup, port, and lifecycle complexity.
- **Python FastAPI sidecar** for ingestion and retrieval, bound to loopback with
  a per-launch bearer token.
- **SQLite** for the catalog, settings, job state, and the FTS5 lexical index.
- **Chroma** for vectors.

The renderer is treated as untrusted: sandboxed, no Node integration, and access
only through a narrow typed preload surface.

## Consequences

- Packaging must build a native Python sidecar per target OS.
- Privacy depends on not pointing the model endpoint at a remote host.
- Cross-platform signing and notarization become a prerequisite for distribution.

## Revisions

### Embeddings moved in-process

Originally Ollama was a hard prerequisite for both embedding and generation,
which meant a new user could do nothing until they installed and configured
separate software.

Embeddings now run inside the sidecar through ONNX Runtime, using
`all-MiniLM-L6-v2` bundled in the installer. Importing and searching therefore
require nothing external. Ollama remains optional and is used only for written
answers, which degrade to returning cited passages when it is absent.

Consequences:

- The installer grows by roughly 90 MB.
- Vector width changed from 1024 to 384, so any index built under the previous
  arrangement must be rebuilt. This is detected and reported rather than left to
  fail.
- The model's licence must be recorded, since weights are now distributed.

### Generation models are discovered

A configured model tag failed with a 404 on any machine that had pulled
something else. The configured name is now a preference; if it is absent, an
installed generation model is selected and the substitution reported.
