# Privacy Policy

This project is designed as a local-first RAG desktop application.

## Local Data

Imported documents, extracted text chunks, embeddings, query traces, settings, and eval history are stored on the user's machine. By default they are not sent to a hosted service by this application.

## Model Runtime

The app uses a local Ollama endpoint by default: `http://127.0.0.1:11434`. If a user configures a remote endpoint, document-derived prompts and queries may be sent to that endpoint.

## Telemetry

Telemetry and crash reporting are off by default. Do not add remote telemetry without an explicit opt-in flow and documentation update.

## Logs

Production logs must not include raw document text, prompts, answers, secrets, or bearer tokens. Diagnostic exports should redact local file paths unless the user explicitly chooses to share them.

## Data Deletion

Deleting a document should remove catalog rows, text chunks, vector entries, and cached metadata for that document. Uninstall behavior should preserve user data by default unless the user explicitly deletes local data.
