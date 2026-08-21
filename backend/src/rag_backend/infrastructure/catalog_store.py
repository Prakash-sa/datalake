"""
SQLite catalog for local desktop memory.
"""

import json
import sqlite3
from collections.abc import Iterable
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 2


class CatalogStore:
    """Persist document catalog, chunks, settings, conversations, and eval runs."""

    def __init__(self, db_path: str):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._migrate()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        return conn

    def _migrate(self) -> None:
        with closing(self._connect()) as conn, conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version INTEGER PRIMARY KEY,
                    applied_at TEXT NOT NULL
                )
                """
            )
            current = conn.execute(
                "SELECT COALESCE(MAX(version), 0) AS version FROM schema_migrations"
            ).fetchone()["version"]
            if current < 1:
                self._create_v1(conn)
                self._record_migration(conn, 1)
                current = 1
            if current < 2:
                self._create_v2(conn)
                self._record_migration(conn, 2)
                current = 2
            if current < 3:
                self._create_v3(conn)
                self._record_migration(conn, 3)

    @staticmethod
    def _record_migration(conn: sqlite3.Connection, version: int) -> None:
        conn.execute(
            "INSERT INTO schema_migrations (version, applied_at) VALUES (?, ?)",
            (version, datetime.now(UTC).isoformat()),
        )

    @staticmethod
    def _create_v1(conn: sqlite3.Connection) -> None:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS documents (
                id TEXT PRIMARY KEY,
                source_path TEXT NOT NULL,
                title TEXT NOT NULL,
                source_hash TEXT NOT NULL,
                content_type TEXT NOT NULL,
                parser_version TEXT NOT NULL,
                chunker_version TEXT NOT NULL,
                embedding_model TEXT NOT NULL,
                llm_model TEXT NOT NULL,
                indexed_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                metadata_json TEXT NOT NULL
            );

            CREATE UNIQUE INDEX IF NOT EXISTS idx_documents_source_hash
            ON documents(source_hash);

            CREATE TABLE IF NOT EXISTS chunks (
                id TEXT PRIMARY KEY,
                document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
                chunk_index INTEGER NOT NULL,
                content TEXT NOT NULL,
                content_hash TEXT NOT NULL,
                metadata_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_chunks_document_id
            ON chunks(document_id);

            CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts
            USING fts5(id UNINDEXED, document_id UNINDEXED, content);

            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                citations_json TEXT NOT NULL,
                model_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS eval_runs (
                id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                request_json TEXT NOT NULL,
                result_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value_json TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """
        )

    @staticmethod
    def _create_v2(conn: sqlite3.Connection) -> None:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS query_traces (
                id TEXT PRIMARY KEY,
                query_hash TEXT NOT NULL,
                prompt_version TEXT NOT NULL,
                retrieval_version TEXT NOT NULL,
                embedding_model TEXT NOT NULL,
                llm_model TEXT NOT NULL,
                chunk_ids_json TEXT NOT NULL,
                scores_json TEXT NOT NULL,
                latency_json TEXT NOT NULL,
                status TEXT NOT NULL,
                error_code TEXT,
                created_at TEXT NOT NULL
            );
            """
        )

    @staticmethod
    def _create_v3(conn: sqlite3.Connection) -> None:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS ingestion_jobs (
                id TEXT PRIMARY KEY,
                source_path TEXT NOT NULL,
                document_id TEXT,
                status TEXT NOT NULL,
                error_code TEXT,
                error TEXT,
                attempts INTEGER NOT NULL DEFAULT 0,
                chunks_total INTEGER NOT NULL DEFAULT 0,
                chunks_done INTEGER NOT NULL DEFAULT 0,
                force_reindex INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                finished_at TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_jobs_status
                ON ingestion_jobs (status, created_at);
            """
        )

    def upsert_document(self, document: dict[str, Any], chunks: Iterable[dict[str, Any]]) -> None:
        now = datetime.now(UTC).isoformat()
        metadata_json = json.dumps(document.get("metadata", {}), sort_keys=True)
        chunk_list = list(chunks)
        with closing(self._connect()) as conn, conn:
            conn.execute(
                """
                INSERT INTO documents (
                    id, source_path, title, source_hash, content_type,
                    parser_version, chunker_version, embedding_model, llm_model,
                    indexed_at, updated_at, metadata_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    source_path=excluded.source_path,
                    title=excluded.title,
                    source_hash=excluded.source_hash,
                    content_type=excluded.content_type,
                    parser_version=excluded.parser_version,
                    chunker_version=excluded.chunker_version,
                    embedding_model=excluded.embedding_model,
                    llm_model=excluded.llm_model,
                    updated_at=excluded.updated_at,
                    metadata_json=excluded.metadata_json
                """,
                (
                    document["id"],
                    document["source_path"],
                    document["title"],
                    document["source_hash"],
                    document["content_type"],
                    document["parser_version"],
                    document["chunker_version"],
                    document["embedding_model"],
                    document["llm_model"],
                    now,
                    now,
                    metadata_json,
                ),
            )
            conn.execute("DELETE FROM chunks_fts WHERE document_id = ?", (document["id"],))
            conn.execute("DELETE FROM chunks WHERE document_id = ?", (document["id"],))
            for chunk in chunk_list:
                chunk_metadata_json = json.dumps(chunk.get("metadata", {}), sort_keys=True)
                conn.execute(
                    """
                    INSERT INTO chunks (
                        id, document_id, chunk_index, content, content_hash,
                        metadata_json, created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        chunk["id"],
                        document["id"],
                        chunk["chunk_index"],
                        chunk["content"],
                        chunk["content_hash"],
                        chunk_metadata_json,
                        now,
                    ),
                )
                conn.execute(
                    "INSERT INTO chunks_fts (id, document_id, content) VALUES (?, ?, ?)",
                    (chunk["id"], document["id"], chunk["content"]),
                )

    def get_document_by_hash(self, source_hash: str) -> dict[str, Any] | None:
        with closing(self._connect()) as conn, conn:
            row = conn.execute(
                "SELECT * FROM documents WHERE source_hash = ?", (source_hash,)
            ).fetchone()
            return self._document_from_row(row) if row else None

    def list_documents(self) -> list[dict[str, Any]]:
        with closing(self._connect()) as conn, conn:
            rows = conn.execute(
                """
                SELECT d.*, COUNT(c.id) AS chunk_count
                FROM documents d
                LEFT JOIN chunks c ON c.document_id = d.id
                GROUP BY d.id
                ORDER BY d.updated_at DESC
                """
            ).fetchall()
            return [self._document_from_row(row) for row in rows]

    def get_chunk_ids(self, document_id: str) -> list[str]:
        with closing(self._connect()) as conn, conn:
            rows = conn.execute(
                "SELECT id FROM chunks WHERE document_id = ? ORDER BY chunk_index",
                (document_id,),
            ).fetchall()
            return [row["id"] for row in rows]

    def search_fts(self, query: str, limit: int = 20) -> list[dict[str, Any]]:
        terms = [term for term in query.replace('"', " ").split() if len(term) > 1]
        if not terms:
            return []
        expression = " OR ".join(f'"{term}"' for term in terms[:8])
        with closing(self._connect()) as conn, conn:
            rows = conn.execute(
                """
                SELECT c.id, c.document_id, c.chunk_index, c.content, c.metadata_json,
                       bm25(chunks_fts) AS rank
                FROM chunks_fts
                JOIN chunks c ON c.id = chunks_fts.id
                WHERE chunks_fts MATCH ?
                ORDER BY rank
                LIMIT ?
                """,
                (expression, limit),
            ).fetchall()
            return [
                {
                    "id": row["id"],
                    "document_id": row["document_id"],
                    "chunk_index": row["chunk_index"],
                    "content": row["content"],
                    "metadata": json.loads(row["metadata_json"]),
                    "rank": float(row["rank"]),
                }
                for row in rows
            ]

    def delete_document(self, document_id: str) -> bool:
        with closing(self._connect()) as conn, conn:
            conn.execute("DELETE FROM chunks_fts WHERE document_id = ?", (document_id,))
            cursor = conn.execute("DELETE FROM documents WHERE id = ?", (document_id,))
            return cursor.rowcount > 0

    def record_eval_run(
        self, run_id: str, status: str, request: dict[str, Any], result: dict[str, Any]
    ) -> None:
        with closing(self._connect()) as conn, conn:
            conn.execute(
                """
                INSERT INTO eval_runs (id, status, request_json, result_json, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    status,
                    json.dumps(request, sort_keys=True),
                    json.dumps(result, sort_keys=True),
                    datetime.now(UTC).isoformat(),
                ),
            )

    def record_query_trace(self, trace: dict[str, Any]) -> None:
        with closing(self._connect()) as conn, conn:
            conn.execute(
                """
                INSERT INTO query_traces (
                    id, query_hash, prompt_version, retrieval_version, embedding_model, llm_model,
                    chunk_ids_json, scores_json, latency_json, status, error_code, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    trace["id"],
                    trace["query_hash"],
                    trace["prompt_version"],
                    trace["retrieval_version"],
                    trace["embedding_model"],
                    trace["llm_model"],
                    json.dumps(trace.get("chunk_ids", [])),
                    json.dumps(trace.get("scores", [])),
                    json.dumps(trace.get("latency", {}), sort_keys=True),
                    trace["status"],
                    trace.get("error_code"),
                    datetime.now(UTC).isoformat(),
                ),
            )

    def set_setting(self, key: str, value: Any) -> None:
        with closing(self._connect()) as conn, conn:
            conn.execute(
                """
                INSERT INTO settings (key, value_json, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value_json=excluded.value_json,
                    updated_at=excluded.updated_at
                """,
                (key, json.dumps(value, sort_keys=True), datetime.now(UTC).isoformat()),
            )

    def get_setting(self, key: str, default: Any = None) -> Any:
        with closing(self._connect()) as conn, conn:
            row = conn.execute("SELECT value_json FROM settings WHERE key = ?", (key,)).fetchone()
            return json.loads(row["value_json"]) if row else default

    @staticmethod
    def _document_from_row(row: sqlite3.Row) -> dict[str, Any]:
        result = dict(row)
        result["metadata"] = json.loads(result.pop("metadata_json"))
        return result

    # -- Ingestion jobs -------------------------------------------------------

    def create_job(
        self, job_id: str, source_path: str, force_reindex: bool = False
    ) -> dict[str, Any]:
        """Enqueue a new ingestion job."""
        now = datetime.now(UTC).isoformat()
        with closing(self._connect()) as conn, conn:
            conn.execute(
                """
                INSERT INTO ingestion_jobs (
                    id, source_path, status, force_reindex, created_at, updated_at
                )
                VALUES (?, ?, 'queued', ?, ?, ?)
                """,
                (job_id, source_path, int(force_reindex), now, now),
            )
        job = self.get_job(job_id)
        assert job is not None
        return job

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        """Fetch a single job, or None when it does not exist."""
        with closing(self._connect()) as conn, conn:
            row = conn.execute("SELECT * FROM ingestion_jobs WHERE id = ?", (job_id,)).fetchone()
        return self._job_from_row(row) if row else None

    def list_jobs(
        self, statuses: Iterable[str] | None = None, limit: int = 100
    ) -> list[dict[str, Any]]:
        """List jobs newest first, optionally filtered by status."""
        query = "SELECT * FROM ingestion_jobs"
        params: list[Any] = []
        status_list = list(statuses or [])
        if status_list:
            placeholders = ",".join("?" for _ in status_list)
            query += f" WHERE status IN ({placeholders})"
            params.extend(status_list)
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        with closing(self._connect()) as conn, conn:
            rows = conn.execute(query, params).fetchall()
        return [self._job_from_row(row) for row in rows]

    def update_job(self, job_id: str, **fields: Any) -> dict[str, Any] | None:
        """Patch a job's mutable columns and bump updated_at."""
        allowed = {
            "status",
            "document_id",
            "error_code",
            "error",
            "attempts",
            "chunks_total",
            "chunks_done",
            "finished_at",
        }
        updates = {key: value for key, value in fields.items() if key in allowed}
        if not updates:
            return self.get_job(job_id)

        updates["updated_at"] = datetime.now(UTC).isoformat()
        assignments = ", ".join(f"{key} = ?" for key in updates)
        with closing(self._connect()) as conn, conn:
            conn.execute(
                f"UPDATE ingestion_jobs SET {assignments} WHERE id = ?",
                (*updates.values(), job_id),
            )
        return self.get_job(job_id)

    def delete_job(self, job_id: str) -> bool:
        """Remove a job record. Returns False when it did not exist."""
        with closing(self._connect()) as conn, conn:
            cursor = conn.execute("DELETE FROM ingestion_jobs WHERE id = ?", (job_id,))
        return cursor.rowcount > 0

    @staticmethod
    def _job_from_row(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "source_path": row["source_path"],
            "document_id": row["document_id"],
            "status": row["status"],
            "error_code": row["error_code"],
            "error": row["error"],
            "attempts": row["attempts"],
            "chunks_total": row["chunks_total"],
            "chunks_done": row["chunks_done"],
            "force_reindex": bool(row["force_reindex"]),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "finished_at": row["finished_at"],
        }

    # -- Conversations --------------------------------------------------------

    def create_conversation(self, conversation_id: str, title: str) -> dict[str, Any]:
        """Start a conversation."""
        now = datetime.now(UTC).isoformat()
        with closing(self._connect()) as conn, conn:
            conn.execute(
                "INSERT INTO conversations (id, title, created_at, updated_at) VALUES (?, ?, ?, ?)",
                (conversation_id, title, now, now),
            )
        return {
            "id": conversation_id,
            "title": title,
            "created_at": now,
            "updated_at": now,
            "message_count": 0,
        }

    def list_conversations(self, limit: int = 50) -> list[dict[str, Any]]:
        """Conversations most recently updated first."""
        with closing(self._connect()) as conn, conn:
            rows = conn.execute(
                """
                SELECT c.*, COUNT(m.id) AS message_count
                FROM conversations c
                LEFT JOIN messages m ON m.conversation_id = c.id
                GROUP BY c.id
                ORDER BY c.updated_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [
            {
                "id": r["id"],
                "title": r["title"],
                "created_at": r["created_at"],
                "updated_at": r["updated_at"],
                "message_count": r["message_count"],
            }
            for r in rows
        ]

    def get_conversation(self, conversation_id: str) -> dict[str, Any] | None:
        """A conversation with its messages in order."""
        with closing(self._connect()) as conn, conn:
            row = conn.execute(
                "SELECT * FROM conversations WHERE id = ?", (conversation_id,)
            ).fetchone()
            if row is None:
                return None
            messages = conn.execute(
                "SELECT * FROM messages WHERE conversation_id = ? ORDER BY created_at, id",
                (conversation_id,),
            ).fetchall()

        return {
            "id": row["id"],
            "title": row["title"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "messages": [self._message_from_row(m) for m in messages],
        }

    def add_message(
        self,
        message_id: str,
        conversation_id: str,
        role: str,
        content: str,
        citations: dict[str, Any] | None = None,
        model: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Append a message and mark the conversation as updated."""
        now = datetime.now(UTC).isoformat()
        with closing(self._connect()) as conn, conn:
            conn.execute(
                """
                INSERT INTO messages (
                    id, conversation_id, role, content,
                    citations_json, model_json, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    message_id,
                    conversation_id,
                    role,
                    content,
                    json.dumps(citations or {}),
                    json.dumps(model or {}),
                    now,
                ),
            )
            conn.execute(
                "UPDATE conversations SET updated_at = ? WHERE id = ?",
                (now, conversation_id),
            )
        return {
            "id": message_id,
            "conversation_id": conversation_id,
            "role": role,
            "content": content,
            "citations": citations or {},
            "model": model or {},
            "created_at": now,
        }

    def rename_conversation(self, conversation_id: str, title: str) -> bool:
        """Set a conversation's title."""
        with closing(self._connect()) as conn, conn:
            cursor = conn.execute(
                "UPDATE conversations SET title = ?, updated_at = ? WHERE id = ?",
                (title, datetime.now(UTC).isoformat(), conversation_id),
            )
        return cursor.rowcount > 0

    def delete_conversation(self, conversation_id: str) -> bool:
        """Delete a conversation and its messages."""
        with closing(self._connect()) as conn, conn:
            cursor = conn.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))
        return cursor.rowcount > 0

    @staticmethod
    def _message_from_row(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "conversation_id": row["conversation_id"],
            "role": row["role"],
            "content": row["content"],
            "citations": json.loads(row["citations_json"] or "{}"),
            "model": json.loads(row["model_json"] or "{}"),
            "created_at": row["created_at"],
        }
