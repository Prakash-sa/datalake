# Airflow Ingestion Pipeline

An optional server-side pipeline for loading documents in bulk from object
storage. It is **independent of the desktop application**, which does its own
ingestion through a local job queue and needs none of this.

Use this when documents arrive in a bucket and should be indexed on a schedule
rather than imported by hand.

## What it does

```
MinIO bucket
    ↓  fetch new objects
Parse and chunk
    ↓  embed
Ollama or the local embedding model
    ↓  upsert
Chroma collection
    ↓
Validate and report
```

The DAG lives at
[`infra/airflow/dags/rag_vector_db_ingestion_dag.py`](../../infra/airflow/dags/rag_vector_db_ingestion_dag.py).

## Running it

```bash
cp compose/.env.example compose/.env
make up-airflow
```

This starts the base stack plus Postgres, Redis, and the Airflow scheduler,
worker, triggerer, and webserver.

| Service | URL |
| --- | --- |
| Airflow | http://localhost:9093 |
| MinIO console | http://localhost:9001 |
| Backend API | http://localhost:8000 |

Credentials come from `compose/.env`. **The defaults are development
placeholders.** Change `AIRFLOW_ADMIN_PASSWORD`, `MINIO_ROOT_USER`, and
`MINIO_ROOT_PASSWORD` before exposing this beyond localhost.

## Loading documents

1. Open the MinIO console and create the bucket named by `MINIO_BUCKET_NAME`.
2. Upload documents.
3. Trigger `document_rag_ingestion_pipeline` in Airflow, or wait for its
   schedule.
4. Watch the task log; the final task reports how many chunks were indexed.

## Configuration

Set in `compose/.env`, consumed by `compose.airflow.yml`:

| Variable | Purpose |
| --- | --- |
| `AIRFLOW_UID` | Match your host UID on Linux to avoid root-owned log files |
| `AIRFLOW_ADMIN_USER` / `_PASSWORD` | Web login |
| `AIRFLOW_FERNET_KEY` | Encrypts stored connections; generate one for anything real |
| `MINIO_ROOT_USER` / `_PASSWORD` | Object storage credentials |

Generate a Fernet key with:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

## Embedding consistency

The pipeline and the application must embed with the **same model**, or their
vectors cannot be compared and search across them is meaningless.

The desktop application defaults to the in-process `all-MiniLM-L6-v2` at 384
dimensions. If the pipeline writes to a collection the application also reads,
configure it to match; otherwise the application will detect the mismatch and
refuse to index until the collection is rebuilt.

## Troubleshooting

**Tasks stay queued** — the worker or scheduler is not healthy. `make logs`, then
look at `airflow-scheduler` and `airflow-worker`.

**Permission errors on logs** — set `AIRFLOW_UID` to your host UID and restart.

**Embedding failures** — the DAG installs its own dependencies through
`_PIP_ADDITIONAL_REQUIREMENTS`; first run is slow while they install.

**Nothing to fetch** — confirm the bucket name matches and objects are a
supported type.
