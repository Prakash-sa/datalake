# Privacy

This application is local-first. Documents you import are processed and stored on
your machine, and nothing about them is transmitted to any service operated by
this project.

There is no account, no API key, and no telemetry.

## What runs locally

| Stage | Where it runs |
| --- | --- |
| Parsing and chunking | In the application |
| Embedding | In the application, via ONNX Runtime |
| Vector storage | Chroma, on local disk |
| Catalog, settings, traces | SQLite, on local disk |
| Retrieval | In the application |
| Answer generation | A local Ollama daemon, if installed |

Because embeddings run in-process, importing and searching require no external
software and no network access.

## The one external component

Generated prose answers use [Ollama](https://ollama.com), which the user installs
separately and which listens on `http://127.0.0.1:11434` by default. Retrieved
document excerpts and the question are sent to that endpoint so it can write an
answer.

Ollama is optional. Without it the application still imports, searches, and
returns cited passages.

**If you change the Ollama endpoint to a remote address, document excerpts and
questions will be sent to that host.** The setting exists for people running a
model server on their own network; it moves data off the machine, so change it
deliberately.

## What is stored

Under the application's data directory:

```
app.db            catalog, settings, ingestion jobs, query traces, eval runs
vector/chroma/    embeddings and chunk text
logs/             rotated application logs
backups/          catalog snapshots
```

Query traces record a **hash** of the query, not the query itself, along with
prompt and retrieval versions, chunk identifiers, scores, latency, and status.
They exist to diagnose retrieval quality and never contain document text.

## Logs

Production logs are redacted. Filesystem paths, bearer tokens, and long hex
secrets are stripped from log messages and from rendered tracebacks, because a
filename alone can disclose what a private library contains.

Redaction applies to logs only. The interface still shows your real file paths,
since the Library and Activity views would be useless otherwise.

Development builds disable redaction, where full paths are what make an error
actionable.

## Deletion

Deleting a document removes its catalog row, its chunks, and its vectors
together. `POST /data/backup` snapshots the catalog before destructive
operations, and an import backs up the existing catalog first.

Uninstalling the application does not delete the data directory; remove it by
hand if you want the data gone.

## Telemetry

There is none, and none is planned. Adding any would require an explicit opt-in
and a change to this document.

Note that `langsmith` is present as a transitive dependency of LangChain. It is
inert unless configured with credentials, which this application never does.
