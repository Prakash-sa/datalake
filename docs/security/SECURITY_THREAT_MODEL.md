# Security Threat Model

## Assets

- Documents the user imports, and the text extracted from them
- Chunks, embeddings, and source metadata
- SQLite catalog: paths, hashes, settings, job state, query traces, eval history
- Chroma vector index
- The per-launch backend bearer token

## Trust boundaries

| Component | Trust | Capabilities |
| --- | --- | --- |
| Renderer | Untrusted | Typed preload functions only. No Node, filesystem, shell, or HTTP client. Never holds the token. |
| Electron main | Trusted | Owns the sidecar, the token, native dialogs, protocol, CSP, navigation, permissions. |
| Python sidecar | Trusted | Bound to `127.0.0.1` on a random port, bearer token required when launched by Electron. |
| Ollama | Semi-trusted, optional | Contacted only at its configured URL. Receives excerpts and questions when generating. |
| Document text | **Untrusted data** | Must never be treated as instructions. |

## Risks and controls

| Risk | Control |
| --- | --- |
| Prompt injection via imported documents | Excerpts fenced between explicit delimiters, model told they are data; injection fixtures in the eval corpus |
| An answer citing a source it never saw | Citations validated against the chunks actually supplied; invalid ones reported, not rendered |
| Backend exposed to the network | Binds to loopback, random port, per-launch bearer token |
| Renderer-to-main IPC abuse | Fixed set of typed functions, sender validated, arguments filtered; no generic bridge |
| Code injection into the renderer | `app://` protocol rather than `file://`, restrictive CSP with build-time inline-script hashes, no `unsafe-inline` |
| Tampering with packaged code | Electron fuses disable `RunAsNode`, `NODE_OPTIONS`, and inspector arguments, and require loading from the asar |
| Path traversal or hostile files | Extension, size, and regular-file validation; archive members rejected if absolute or parent-relative |
| Document content leaking through logs | Paths, tokens, and long hex secrets stripped from messages and rendered tracebacks in production |
| Traces disclosing queries | Queries stored as SHA-256 hashes with chunk ids, scores, and timings — never raw text |
| Querying across incompatible embeddings | Index fingerprints refuse a mismatched index and require a rebuild |
| Data sent off the machine unnoticed | Embeddings run in-process; Ollama is optional and loopback by default. A remote `OLLAMA_URL` sends excerpts to that host — documented in [PRIVACY](PRIVACY.md) |

The IPC boundary and renderer isolation are asserted by the Playwright Electron
suite, not only documented.

## Residual risks

- A user who points `OLLAMA_URL` at a remote host sends document excerpts there.
  This is deliberate configuration, surfaced in Settings and Diagnostics.
- The bundled embedding model is trusted as distributed. Its archive is verified
  against a published SHA-256, but the weights themselves are not independently
  audited.
- Generation quality and refusal behaviour depend on whichever model the user
  installed; the prompt defends against injection but cannot guarantee it.
- Chroma and its dependencies run in-process with full access to the data
  directory.

## Release blockers

- [ ] Signed and notarized macOS artifacts
- [ ] Signed Windows installer and sidecar executable
- [ ] Packaged smoke tests on clean macOS, Windows, and Linux machines
- [ ] Resolve the licence conflict in [THIRD_PARTY_NOTICES](../../THIRD_PARTY_NOTICES.md)

Completed since this document was first written: prompt-injection eval fixtures,
citation validation, log redaction, Electron fuses, CSP inline-script hashes,
index fingerprinting, and SHA-256 checksums with SBOM generation in CI.
