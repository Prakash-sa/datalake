# ADR 0001: Local-First Desktop RAG

## Status

Accepted

## Context

The project needs a desktop local RAG application for macOS, Windows, and Linux. Imported documents may contain private or proprietary content.

## Decision

Use Electron for the desktop shell, a Python FastAPI sidecar for ingestion/retrieval, SQLite for local catalog memory, Chroma for vectors, and Ollama as a local prerequisite.

Electron main owns file dialogs, backend lifecycle, and backend authentication. The renderer stays sandboxed and accesses functionality through typed preload APIs.

## Consequences

- The primary installer does not bundle model weights.
- The app can work offline after models are available locally.
- Cross-platform packaging must build native Python sidecars per target OS.
- Local privacy depends on not configuring remote model endpoints.
