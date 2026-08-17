# Production Plan: Cross-Platform Local RAG Desktop App

The project has the beginnings of an Electron interface and persistent RAG backend, but it is not yet installable as a self-contained desktop application. The most important architectural change is to make Electron own the complete application lifecycle: UI, Python backend process, local data directories, Ollama connectivity, upgrades, and shutdown.

## 1. Target Product Definition

The production application should provide this workflow:

1. User installs a signed desktop application.
2. Application checks whether Ollama is available locally.
3. First-run setup selects and downloads compatible generation and embedding models.
4. User imports PDF, DOCX, TXT, Markdown, or HTML documents.
5. Documents are parsed, chunked, embedded, and indexed locally.
6. User asks questions and receives streamed, source-cited answers.
7. Documents, indexes, conversations, settings, and evaluation history persist between restarts.
8. After models are downloaded, normal operation requires no internet connection.
9. The application updates safely without losing user data.
10. No document content leaves the machine unless the user explicitly enables a remote provider.

Recommended initial platform support:

| Platform | Architectures | Packages |
|---|---|---|
| macOS 13+ | Apple Silicon and Intel | Separate signed/notarized DMG and ZIP |
| Windows 10 22H2+, Windows 11 | x64 initially | Signed NSIS EXE |
| Linux | x64, Ubuntu 22.04/24.04 baseline | AppImage and DEB |
| Windows ARM64 | Later | Add only after Ollama and dependency validation |
| Linux ARM64 | Later | Add after native dependency and model testing |

Separate macOS ARM64 and x64 artifacts are safer than a universal package because the Python backend and Chroma dependencies contain architecture-specific binaries.

## 2. Current Production Blockers

The current Electron process loads `http://localhost:3000`, but nothing starts a production Next.js server inside the packaged application. Consequently, a built installer will normally open a blank or failed page. See [main.js](</Users/prakashsaini/Documents/Projects/Data Engineer/datalake-project/apps/rag-query-engine/frontend/electron/main.js:4>).

The frontend also calls a fixed backend at `http://localhost:8000`, but Electron does not package, start, monitor, or stop that backend. See [page.tsx](</Users/prakashsaini/Documents/Projects/Data Engineer/datalake-project/apps/rag-query-engine/frontend/app/page.tsx:81>).

Other P0 blockers include:

- Backend defaults to `0.0.0.0`, exposing it to the local network.
- Desktop data uses a relative `./chroma_db` path.
- No authentication exists between Electron and the backend.
- Ollama availability and required models are not checked.
- Document picker, parser, chunker, deletion, and reindex primitives now exist; remaining work is richer progress UI, cancellation, and parser coverage hardening.
- Retrieved chunk content is no longer truncated before answer generation.
- Search errors become empty results, making outages look like “no documents found.”
- The timeout argument is unused.
- Readiness now tests Ollama model availability and local storage writability.
- Python dependencies use broad `>=` constraints and are not reproducible.
- Tests are commented out in [requirements.txt](</Users/prakashsaini/Documents/Projects/Data Engineer/datalake-project/apps/rag-query-engine/backend/requirements.txt:27>).
- Current evals only check string presence, document count, and maximum similarity.
- No signing, notarization, updater, icons, release workflow, SBOM, or installer testing exists.
- The README still mixes an older Trino/SQL product description with the active document-RAG implementation.

## 3. Recommended Runtime Architecture

```text
Electron main process
├── Serves packaged static UI through app://
├── Owns native file dialogs and application menus
├── Starts and monitors Python RAG sidecar
├── Generates an ephemeral backend authentication token
├── Proxies typed IPC calls to the sidecar
├── Detects Ollama and manages model setup
├── Owns update checks and application shutdown
└── Resolves OS-specific data and log directories

Sandboxed renderer
├── React/Next UI
├── No Node.js access
├── No direct filesystem access
├── No arbitrary HTTP backend access
└── Narrow, typed preload API only

Python sidecar
├── Document ingestion and parsing
├── Persistent job queue
├── Chroma vector index
├── SQLite catalog, conversations, settings, and eval history
├── Retrieval and generation pipeline
└── Loop/evaluation instrumentation

Ollama
├── Installed separately
├── Bound to loopback
├── Downloads models during first-run setup
└── Performs local embeddings and generation
```

### UI packaging

Keep Next.js for now, but configure `output: "export"` and serve the generated static output through an Electron custom `app://` protocol.

Do not run `next start` inside the production desktop application. The current UI does not require server-side rendering, and bundling a Next server adds startup, port, lifecycle, and security complexity.

Do not use `file://`. Electron recommends custom protocols as part of its security guidance. Continue using `contextIsolation`, renderer sandboxing, and disabled Node integration, while adding navigation controls, CSP, permission handlers, IPC sender validation, and URL allowlisting. [Electron’s security checklist](https://www.electronjs.org/docs/latest/tutorial/security) explicitly recommends these controls.

### Backend packaging

Use:

- Python 3.12 or one explicitly selected supported version.
- `pyproject.toml` and `uv.lock` for reproducible dependencies.
- PyInstaller `onedir` builds generated natively on each target OS.
- `electron-builder.extraResources` to place the sidecar outside `app.asar`.
- A single backend process and single Chroma writer.

Do not use:

- Gunicorn with four workers for desktop.
- Docker or Docker Compose as the desktop runtime.
- MinIO, Redis, PostgreSQL, Prometheus, or Grafana in the desktop package.
- PyInstaller `onefile` initially; extraction slows startup and often creates antivirus friction.
- A system Python installation.

The sidecar should:

1. Bind only to `127.0.0.1`.
2. Select an available random port.
3. Print a machine-readable readiness handshake to Electron.
4. Require a random 256-bit bearer token generated on every launch.
5. Receive its data directory and Ollama endpoint as explicit CLI arguments.
6. Shut down when Electron exits.
7. Be force-terminated after a bounded graceful-shutdown timeout.
8. Never write secrets or document content to stdout.

Prefer routing renderer operations through typed Electron IPC. Electron main can hold the backend token and make loopback requests. The renderer should not receive a general-purpose HTTP client or arbitrary IPC capability.

## 4. Ollama and Model Strategy

### Recommended first release

Treat Ollama as a managed prerequisite, not an installer payload.

The application should:

- Detect `http://127.0.0.1:11434`.
- Validate that the endpoint is genuinely Ollama.
- List locally available models.
- Show model download size before pulling.
- Stream model-pull progress.
- Allow retry, cancellation, and endpoint reconfiguration.
- Store the selected model names through local settings; digest capture remains a release-blocking follow-up.
- Detect when a model has changed and an index needs rebuilding.
- Support preinstalled models for offline environments.

Do not bundle Ollama or model weights in the main installer initially. That would increase artifact size substantially and couple application releases to GPU runtimes, model updates, hardware support, and third-party model licenses.

Recommended model profiles:

| Profile | Generation | Embedding | Intended hardware |
|---|---|---|---|
| Light | `qwen3:1.7b` | `qwen3-embedding:0.6b` | CPU and lower-memory systems |
| Balanced | `qwen3:4b` | `qwen3-embedding:0.6b` | Default desktop profile |
| Quality | User-selected 8B-class model | `qwen3-embedding:0.6b` or larger | Higher-memory GPU systems |

Ollama currently recommends models including `embeddinggemma` and `qwen3-embedding` for RAG embeddings. See the [Ollama embedding documentation](https://docs.ollama.com/capabilities/embeddings) and [Qwen3 embedding model information](https://ollama.com/library/qwen3-embedding).

Model names should be configurable. Every distributed recommendation must have its license recorded in `THIRD_PARTY_NOTICES.md`; the application’s MIT license does not automatically apply to downloaded models.

### Later standalone mode

If a completely one-click, no-prerequisite installation becomes mandatory, create a separate “managed inference runtime” project. Evaluate a bundled `llama.cpp` server or platform-specific Ollama distribution. Keep that work separate from the first GA release because it materially changes installer size, hardware support, updates, and licensing.

## 5. Local Data and Memory Design

Use `app.getPath("userData")` instead of relative paths. Electron resolves the correct location on every OS.

Recommended layout:

```text
userData/
├── app.db
├── vector/
│   └── chroma/
├── workspaces/
├── logs/
├── backups/
├── cache/
└── settings.json
```

Use four distinct forms of memory:

- Document memory: Chroma vectors and immutable chunk text.
- Catalog memory: SQLite documents, paths, hashes, parser versions, indexing jobs, and collection membership.
- Conversation memory: SQLite conversations, messages, citations, model digest, and prompt version.
- Evaluation memory: eval definitions, runs, metrics, failures, and feedback.

The SQLite schema should include migrations from the first public release. Never modify persistent schemas without a migration and rollback or backup strategy.

Every vector index must record:

- Embedding model name and digest.
- Embedding dimensions.
- Chunking algorithm version.
- Chunk size and overlap.
- Parser version.
- Index schema version.
- Source document hash.

Changing the embedding model or vector dimensions must create a new index or require a controlled full reindex. Never query vectors generated by different embedding models in the same collection.

Provide:

- Export and import.
- Backup before schema migration.
- Rebuild-index operation.
- Delete-document operation that removes catalog, chunks, vectors, and cached content.
- Optional “delete all local data” flow with explicit confirmation.
- Uninstall behavior that preserves data by default.

## 6. Document Ingestion

The current API expects already prepared `id` and `content` fields. A production local RAG application needs a complete ingestion pipeline.

First-release formats:

- PDF using PyMuPDF.
- DOCX using `python-docx`.
- TXT and Markdown using standard decoding with charset detection.
- HTML with scripts/styles removed before text extraction.

Defer OCR, scanned PDFs, archives, email, spreadsheets, and web crawling until after GA.

The ingestion pipeline should:

1. Validate extension, MIME signature, file size, and readable status.
2. Reject devices, sockets, invalid symlinks, and unsupported files.
3. Compute a SHA-256 source hash.
4. Detect duplicates and changed files.
5. Parse into page/section-aware text.
6. Normalize whitespace without destroying paragraph boundaries.
7. Split with a versioned recursive, token-budget-aware chunker.
8. Preserve document, page, heading, and chunk metadata.
9. Batch embeddings through Ollama.
10. Commit catalog and vector updates transactionally where possible.
11. Persist progress and failures.
12. Support cancellation and resumable retry.

Do not accept ZIP ingestion initially; archive bombs and nested formats add unnecessary risk.

Add a persistent indexing job state machine:

```text
queued → parsing → chunking → embedding → committing → complete
                                      └→ failed / cancelled
```

The UI needs progress by document, estimated remaining work, actionable errors, retry, delete, and reindex controls.

## 7. Retrieval and Answer Pipeline

Replace the single dense-vector query with:

1. Query normalization.
2. Dense retrieval from Chroma.
3. Lexical retrieval using SQLite FTS5.
4. Reciprocal-rank fusion.
5. Duplicate and near-duplicate suppression.
6. Optional lightweight reranking later.
7. Context assembly within a configured token budget.
8. Grounded generation with explicit source identifiers.
9. Citation validation before displaying the answer.

Do not add an LLM reranker to the default pipeline initially. It increases latency and memory consumption before the baseline retrieval quality is known.

Implementation status: dense Chroma retrieval, SQLite FTS5 lexical retrieval, reciprocal-rank fusion, source-delimited prompts, and privacy-safe local query traces are implemented. Remaining release work includes streaming, cancellation, citation validation, richer retrieval metrics, and prompt-injection fixtures.

Required answer behavior:

- Stream generation tokens.
- Display source title, page/section, excerpt, and relevance.
- Emit citations such as `[S1]`, backed by known retrieved chunks.
- State clearly when evidence is insufficient.
- Never claim a source that was not sent to the model.
- Allow generation cancellation.
- Separate “retrieval failed,” “model unavailable,” and “no relevant evidence.”
- Enforce real request timeouts and cancellation through the Ollama call.
- Use structured error codes instead of arbitrary exception strings.

Document text is untrusted. The prompt must delimit source content and instruct the model that commands inside documents are data, not system instructions. Add prompt-injection fixtures to the eval suite.

Consider replacing LangChain with direct `httpx` calls to the Ollama API. The current application uses only embedding and generation calls; removing LangChain would reduce dependency size and packaging complexity. Do not perform this removal until parity tests cover the current behavior.

## 8. Configuration Model

### Build-time configuration

Move Electron packaging into `electron-builder.yml`.

Implementation status: packaging configuration now lives in `frontend/electron-builder.yml` with `asar`, explicit artifacts, extra sidecar resources, AppImage and DEB targets, and draft GitHub publish settings.

Required configuration:

| Setting | Recommendation |
|---|---|
| `appId` | Stable reverse-DNS identifier owned by the project |
| `productName` | Final user-facing product name |
| `asar` | `true` |
| `extraResources` | Platform-specific Python sidecar |
| `protocols` | Custom `app://` protocol |
| `artifactName` | Include product, version, OS, and architecture |
| `compression` | `maximum` for releases |
| `directories.buildResources` | Icons, entitlements, installer assets |
| `publish` | Public GitHub Releases initially |
| `generateUpdatesFilesForAllChannels` | Enable when beta/stable channels exist |

### Runtime configuration

Store normal settings in SQLite or `settings.json`, not `.env.production`.

Recommended defaults:

| Setting | Default |
|---|---|
| Ollama URL | `http://127.0.0.1:11434` |
| Generation model | Balanced profile selection |
| Embedding model | `qwen3-embedding:0.6b` |
| Temperature | `0.1` for grounded factual answers |
| Retrieval candidates | 20 |
| Final context chunks | 5–8, determined through evals |
| Minimum score | Derived through corpus evaluation, not hardcoded blindly |
| Chunk size | Versioned preset, tuned through evals |
| Chunk overlap | 10–20% starting range |
| Backend host | Always `127.0.0.1` |
| Backend port | Random per launch |
| Backend workers | 1 |
| Telemetry | Off |
| Crash reporting | Off until explicit consent exists |
| Log retention | 7–14 days with size rotation |

Environment variables should remain development and CI overrides only. Never put secrets in `NEXT_PUBLIC_*` values because those are compiled into renderer code.

## 9. Electron Security

The existing context isolation and sandbox settings are correct foundations, but complete the security boundary with:

- Restrictive CSP.
- Custom local protocol.
- Deny all unexpected permission requests.
- Deny navigation away from the packaged application.
- Allow external links only after parsing and allowlisting `https:` URLs.
- Never pass unsanitized URLs to `shell.openExternal`.
- Validate IPC sender, channel, arguments, and response types.
- Expose one preload function per supported operation.
- No generic `send`, `invoke`, filesystem, shell, or subprocess bridge.
- Disable DevTools in production unless enabled with an explicit diagnostic flag.
- Apply Electron fuses to disable unnecessary runtime capabilities.
- Prevent multiple app instances.
- Set secure temporary-file permissions.
- Redact paths, prompts, answers, and document text from production logs.
- Perform dependency and packaged-artifact scanning.
- Keep Electron on a supported release line.

Implementation status: the desktop shell now serves a CSP on `app://local`, validates IPC senders, denies permissions, restricts navigation and external URLs, prevents multiple app instances, and gates DevTools in production.

Electron specifically warns against exposing general Electron APIs through `contextBridge`; preload APIs should filter every argument. See [context isolation guidance](https://www.electronjs.org/docs/latest/tutorial/context-isolation).

## 10. Desktop UX Requirements

The current query screen should become an operational desktop application with these views:

- First-run setup: Ollama detection, model selection, model download, storage location.
- Library: imported documents, status, size, pages, chunks, last indexed time.
- Import flow: native file picker, drag/drop, progress, errors.
- Chat/query: streaming response, citations, cancellation, follow-up questions.
- Sources: open source document at page when possible.
- Activity: active and failed indexing jobs.
- Settings: model profiles, retrieval settings, data location, log export.
- Diagnostics: app/backend/Ollama versions, model digests, database health, free disk space.
- Eval: local eval suite execution and regression comparison.
- About/update: version, license, third-party notices, update channel.

Handle these states explicitly:

- Ollama absent.
- Ollama stopped after startup.
- Required model absent.
- Model download interrupted.
- Insufficient disk space.
- Corrupt or password-protected document.
- Index migration required.
- Backend crash and automatic bounded restart.
- Unsupported GPU or CPU-only performance.
- Index created with a different embedding model.

## 11. Loop Engineering

“Loop Engineering” should be an actual quality-improvement system, not a readiness label.

For every local query, record a privacy-safe trace:

- Query ID and timestamp.
- Prompt template version.
- Generation and embedding model digests.
- Index and chunker versions.
- Retrieved chunk IDs and scores.
- Retrieval, time-to-first-token, generation, and total latency.
- Citation count.
- Cancellation or error reason.
- Optional user thumbs-up/down and feedback.

Keep this trace local by default. Do not record raw document content in logs or send telemetry to a hosted service.

The operating loop should be:

```text
User query
→ local trace
→ feedback or detected failure
→ promote failure to eval case
→ adjust parser/chunker/retrieval/prompt
→ run eval suite
→ compare against baseline
→ release only without unacceptable regression
```

Version every prompt and retrieval configuration so a regression can be reproduced.

## 12. Evaluation Program

The current `answer_contains` endpoint is useful only as a smoke test. Expand evaluation into four layers.

### Deterministic unit tests

- Parser output and metadata.
- Chunk boundaries.
- Hashing and deduplication.
- Index migration.
- Score conversion.
- Rank fusion.
- Context-budget enforcement.
- Citation parsing and validation.
- Configuration validation.
- Error mapping.

These tests must not require Ollama.

### Retrieval evaluation

Build a checked-in fixture corpus with expected relevant chunks and measure:

- Hit rate at K.
- Recall at K.
- Mean reciprocal rank.
- nDCG.
- Duplicate rate.
- Empty-result rate.
- Retrieval latency.

### Answer evaluation

Measure:

- Required fact coverage.
- Citation correctness.
- Citation completeness.
- Unsupported-claim rate.
- Refusal when evidence is absent.
- Prompt-injection resistance.
- Answer consistency across repeated runs.

Use deterministic checks as release gates. An LLM judge may provide supplemental analysis, but should not be the only release gate.

### Desktop and performance evaluation

- Fresh install.
- First-run setup.
- Model download interruption/recovery.
- Import/query/restart persistence.
- Upgrade from previous release.
- Backend crash recovery.
- Uninstall behavior.
- CPU-only testing.
- GPU testing where available.
- Large corpus and low-disk-space tests.
- Memory usage over repeated imports and queries.

Maintain reference hardware profiles and compare every release against the previous stable version. Gate on regression relative to measured baselines rather than invented performance numbers.

## 13. Automated Test Stack

Use:

- `pytest`, `pytest-asyncio`, and `httpx` for backend tests.
- `ruff` for Python linting and formatting.
- `mypy` or Pyright for backend type checking.
- Vitest and React Testing Library for renderer tests.
- Playwright Electron mode for packaged-app workflows.
- Spectron should not be used; it is obsolete.
- `npm audit`, `pip-audit`, and OSV scanning.
- CodeQL for JavaScript/TypeScript and Python.
- SBOM generation in CycloneDX or SPDX format.

CI test levels:

| Trigger | Tests |
|---|---|
| Every pull request | Lint, types, unit tests, deterministic fixture eval |
| Main branch | Integration tests and packaged smoke tests |
| Nightly | Ollama/model-backed eval and performance suite |
| Version tag | Full platform matrix, signing, installer tests, upgrade tests |

## 14. Packaging and Release CI

Build every operating system on its native GitHub Actions runner. Do not expect a single macOS machine to produce trustworthy signed artifacts for every platform. electron-builder explicitly warns that macOS signing only works on macOS and native dependencies may require target-platform builds. See its [multi-platform build guidance](https://www.electron.build/docs/features/multi-platform-build/).

Release matrix:

- `macos-latest`: ARM64 and x64 sidecars, signed DMG/ZIP, notarization.
- `windows-latest`: x64 sidecar, signed NSIS installer.
- `ubuntu-22.04`: x64 sidecar, AppImage and DEB.
- Separate unsigned pull-request packages from signed tag releases.
- Retain packaged smoke-test logs and checksums.
- Publish only after all matrix jobs and eval gates pass.

### macOS

Required:

- Apple Developer Program membership.
- Developer ID Application certificate.
- Hardened Runtime.
- Minimum necessary entitlements.
- Notarization through an App Store Connect API key.
- Stapled notarization ticket.
- Validation with `codesign`, `spctl`, and clean-machine installation.

macOS notarization must run on macOS, and signed applications are required for automatic updates. See [electron-builder macOS signing](https://www.electron.build/docs/features/code-signing/code-signing-mac/) and [notarization guidance](https://www.electron.build/docs/notarization/).

### Windows

Use a signed NSIS installer initially. Choose one:

- Azure Artifact Signing for direct distribution.
- A CA-issued OV certificate.
- Microsoft Store MSIX later if Store distribution is desired.
- SignPath Foundation if the open-source project qualifies.

Do not distribute unsigned public installers. Microsoft documents that unsigned applications receive strong SmartScreen warnings, while Store MSIX packages are signed by Microsoft. See [Windows code-signing options](https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/code-signing-options).

Sign:

- Installer.
- Main executable.
- Python backend executable.
- Any other shipped executable or DLL where the signing workflow supports it.

Timestamp every signature and preserve the same publisher identity across releases.

### Linux

Ship both AppImage and DEB:

- AppImage for portable use.
- DEB for Ubuntu/Debian users and managed installations.
- Build on the oldest supported Linux baseline to avoid newer glibc dependencies.
- Test X11 and Wayland.
- Publish SHA-256 checksums and signed release manifests.
- Add RPM only after demand exists.

## 15. Updates

Use `electron-updater` with public GitHub Releases for macOS and Windows.

Required behavior:

- Stable and beta channels.
- Check after startup delay, not before the UI is usable.
- Show download progress.
- Never install while indexing is committing data.
- Back up before schema-changing updates.
- Install on explicit user action or clean shutdown.
- Roll back or display recovery instructions when startup migration fails.
- Verify signed update metadata and artifacts.

Electron’s built-in updater supports macOS and Windows, but not Linux; Linux generally relies on package managers or platform-specific flows. See [Electron autoUpdater](https://www.electronjs.org/docs/latest/api/auto-updater/). For Linux, provide update notification and direct users to the new AppImage or signed package repository.

## 16. Open-Source Readiness

Retain MIT only after completing a dependency and model-license review.

Add or correct:

- Accurate root README focused on the local RAG product.
- Architecture decision records.
- Developer setup for all three operating systems.
- Release and signing documentation.
- Threat model.
- Privacy policy stating local-data behavior.
- `THIRD_PARTY_NOTICES.md`.
- Model-license manifest.
- Code of Conduct.
- Issue and pull-request templates.
- Supported-version policy.
- DCO or CLA decision.
- Changelog generated from conventional commits.
- Security vulnerability process.
- SBOM attached to each release.
- SHA-256 checksums and build provenance.
- Dependency update automation.

Implementation status: threat model, privacy policy, release/signing docs, ADR, Code of Conduct, issue templates, PR template, CodeQL/dependency-audit workflow, and SBOM workflow are present. Remaining work includes model-license manifest details, checksum publishing in release automation, dependency update automation, and DCO/CLA decision.

Do not claim “production ready,” “private,” or “offline” until packaged binaries and clean-machine tests prove those properties.

## 17. Work Sequence

### Phase 0: Product and repository cleanup

- Resolve the SQL/Trino versus document-RAG identity conflict.
- Remove or archive unused and syntactically broken backend implementations.
- Define supported OS versions, file formats, and hardware profiles.
- Establish versioning and architecture decision records.

Exit gate: one documented product and one active implementation path.

### Phase 1: Desktop runtime foundation

- Static-export the Next UI.
- Add custom Electron protocol.
- Package Python sidecars.
- Implement sidecar lifecycle, handshake, random port, and token.
- Move data into `userData`.
- Implement real liveness/readiness checks.
- Add process shutdown and crash recovery.

Exit gate: packaged unsigned app starts, queries the backend, restarts cleanly, and works without development servers.

### Phase 2: Ingestion and memory

- Add SQLite schema and migrations.
- Implement parsers, chunker, hashing, job queue, and Chroma integration.
- Build document library and import progress UI.
- Add delete, retry, rebuild, export, and backup.

Exit gate: documents survive restart and can be safely reindexed or removed.

### Phase 3: RAG quality

- Add hybrid retrieval.
- Add model/index fingerprints.
- Add context budgeting and streaming.
- Add citations, insufficient-evidence behavior, and prompt-injection defenses.
- Implement cancellation and real timeouts.

Exit gate: fixture corpus meets initial retrieval and citation baselines.

### Phase 4: Production UX and configuration

- Build first-run model setup.
- Add model download progress and hardware profiles.
- Complete settings, diagnostics, recovery, and update UI.
- Add accessibility and keyboard navigation checks.

Exit gate: a new user can install, configure, import, and query without terminal commands.

### Phase 5: Security and privacy

- Harden Electron IPC, CSP, protocols, navigation, and permissions.
- Add loopback authentication.
- Redact logs.
- Add dependency scans, threat model, and privacy controls.
- Apply Electron fuses.

Exit gate: security checklist and automated scans pass.

### Phase 6: Eval and testing

- Implement unit, integration, retrieval, answer, performance, and desktop tests.
- Add local trace and feedback loop.
- Establish reference baselines and release gates.
- Test upgrade and migration paths.

Exit gate: CI blocks measurable quality, security, and packaging regressions.

### Phase 7: Signed releases

- Add native CI matrix.
- Configure Apple signing/notarization.
- Configure Windows signing.
- Sign Linux manifests.
- Add updater and release channels.
- Publish checksums, SBOM, provenance, and notices.

Exit gate: clean machines on every supported platform install, run, update, and preserve data successfully.

## 18. Definition of Done

The application is production ready only when all of these are true:

- No development server, Docker container, system Python, or terminal command is required.
- Backend and Ollama are reachable only through loopback.
- macOS and Windows artifacts are signed; macOS is notarized.
- Linux artifacts have signed checksums.
- Fresh install, upgrade, rollback/recovery, and uninstall are tested.
- A user can import documents and get source-cited answers.
- Data, conversations, settings, and indexes survive restart.
- Model and embedding changes trigger controlled reindexing.
- Normal operation is offline after model acquisition.
- No document content is transmitted or logged without explicit consent.
- Eval, security, dependency, and packaged-app test gates pass.
- Every release includes SBOM, third-party notices, checksums, and changelog.
- The repository documentation accurately describes what is shipped.

For one experienced engineer, this is approximately 8–12 engineering weeks to a credible public beta, excluding certificate identity verification, extensive model benchmarking, and later OCR or fully bundled inference work. The P0 critical path is Phase 0 through Phase 3; signing and release automation should begin early because Apple and Windows identity setup can take external processing time.
