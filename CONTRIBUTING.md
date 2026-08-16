# Contributing

## Development Setup

1. Start the backend dependencies from `rag-query-engine`:
   ```bash
   docker-compose up --build
   ```
2. Run the frontend:
   ```bash
   cd rag-query-engine/frontend
   npm install
   npm run dev
   ```
3. Run the desktop shell:
   ```bash
   npm run electron:dev
   ```
4. Build a local desktop package:
   ```bash
   python3 -m pip install pyinstaller
   npm run dist
   ```

## Quality Bar

- Keep API behavior covered by deterministic checks through `/eval` when retrieval or prompt behavior changes.
- Keep desktop changes compatible with the web UI; Electron should wrap the app, not fork product behavior.
- Do not commit local model files, Chroma data, `.env` files, logs, or generated desktop installers.
- Prefer small pull requests with a clear test plan and screenshots for UI changes.

## Pull Request Checklist

- The backend starts and `/health` returns healthy.
- `/readiness` reports loop engineering, memory, eval, and open-source capabilities.
- Frontend TypeScript and lint checks pass.
- Electron launches with `npm run electron:dev`.
- Desktop packaging includes the PyInstaller sidecar in `rag-query-engine/backend/dist`.
- New configuration is documented in README or `.env.production`.
