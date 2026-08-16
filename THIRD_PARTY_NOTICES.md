# Third-Party Notices

This project uses third-party open-source software and local model runtimes.

## Application Dependencies

- Electron: desktop application runtime.
- Next.js, React, and Tailwind CSS: frontend application framework and styling.
- FastAPI and Uvicorn: backend HTTP API runtime.
- Chroma: local vector storage.
- LangChain and langchain-ollama: local RAG orchestration.
- Ollama: local model runtime, installed separately by the user.

Dependency licenses must be reviewed before public binary distribution. Generate a complete notice file from locked dependency manifests as part of the release process.

## Models

Model weights are not distributed in this repository. If the desktop app recommends or downloads models, record each model name, source, version or digest, and license here before release.
