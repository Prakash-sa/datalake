"""
SQLite catalog for local desktop memory.
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


SCHEMA_VERSION = 1


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
        with self._connect() as conn:
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
                conn.execute(
                    "INSERT INTO schema_migrations (version, applied_at) VALUES (?, ?)",
                    (SCHEMA_VERSION, datetime.utcnow().isoformat()),
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

    def upsert_document(self, document: Dict[str, Any], chunks: Iterable[Dict[str, Any]]) -> None:
        now = datetime.utcnow().isoformat()
        metadata_json = json.dumps(document.get("metadata", {}), sort_keys=True)
        chunk_list = list(chunks)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO documents (
                    id, source_path, title, source_hash, content_type, parser_version,
                    chunker_version, embedding_model, llm_model, indexed_at, updated_at, metadata_json
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
                        id, document_id, chunk_index, content, content_hash, metadata_json, created_at
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

    def get_document_by_hash(self, source_hash: str) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM documents WHERE source_hash = ?", (source_hash,)
            ).fetchone()
            return self._document_from_row(row) if row else None

    def list_documents(self) -> List[Dict[str, Any]]:
        with self._connect() as conn:
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

    def get_chunk_ids(self, document_id: str) -> List[str]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id FROM chunks WHERE document_id = ? ORDER BY chunk_index",
                (document_id,),
            ).fetchall()
            return [row["id"] for row in rows]

    def delete_document(self, document_id: str) -> bool:
        with self._connect() as conn:
            conn.execute("DELETE FROM chunks_fts WHERE document_id = ?", (document_id,))
            cursor = conn.execute("DELETE FROM documents WHERE id = ?", (document_id,))
            return cursor.rowcount > 0

    def record_eval_run(self, run_id: str, status: str, request: Dict[str, Any], result: Dict[str, Any]) -> None:
        with self._connect() as conn:
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
                    datetime.utcnow().isoformat(),
                ),
            )

    def set_setting(self, key: str, value: Any) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO settings (key, value_json, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value_json=excluded.value_json,
                    updated_at=excluded.updated_at
                """,
                (key, json.dumps(value, sort_keys=True), datetime.utcnow().isoformat()),
            )

    def get_setting(self, key: str, default: Any = None) -> Any:
        with self._connect() as conn:
            row = conn.execute("SELECT value_json FROM settings WHERE key = ?", (key,)).fetchone()
            return json.loads(row["value_json"]) if row else default

    @staticmethod
    def _document_from_row(row: sqlite3.Row) -> Dict[str, Any]:
        result = dict(row)
        result["metadata"] = json.loads(result.pop("metadata_json"))
        return result
