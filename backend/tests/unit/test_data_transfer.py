"""Export, import, and backup of local data."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from rag_backend.application.data_transfer import (
    CATALOG_NAME,
    EXPORT_FORMAT_VERSION,
    MANIFEST_NAME,
    DataTransferService,
)
from rag_backend.application.ingestion_jobs import IngestionJobService
from rag_backend.application.rag_service import DocumentRAGService
from rag_backend.errors import ValidationError


class StubEmbeddings:
    def embed_query(self, content: str) -> list[float]:
        return [float(len(content) % 5)] * 8


@pytest.fixture
def rag(tmp_path) -> DocumentRAGService:
    service = DocumentRAGService(
        chroma_path=str(tmp_path / "chroma"), app_db_path=str(tmp_path / "app.db")
    )
    service.embeddings = StubEmbeddings()
    return service


@pytest.fixture
def data(rag) -> DataTransferService:
    return DataTransferService(rag)


@pytest.fixture
def indexed(rag, tmp_path):
    source = tmp_path / "notes.md"
    source.write_text("# Notes\n\nLocal storage matters.", encoding="utf-8")
    jobs = IngestionJobService(rag)
    job = jobs.enqueue(str(source))
    jobs.process_job(job["id"])
    return source


def test_backup_writes_a_snapshot(data, indexed):
    result = data.backup()

    assert result["status"] == "success"
    assert Path(result["path"]).is_file()
    assert result["size_bytes"] > 0


def test_backup_snapshot_is_a_readable_database(data, indexed):
    import sqlite3

    result = data.backup()
    conn = sqlite3.connect(result["path"])
    try:
        count = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
    finally:
        conn.close()

    assert count == 1


def test_backups_are_listed_newest_first(data, indexed):
    data.backup()
    data.backup()

    backups = data.list_backups()

    assert len(backups) >= 2
    assert backups == sorted(backups, key=lambda b: b["created_at"], reverse=True)


def test_export_produces_an_archive_with_manifest_and_catalog(data, indexed, tmp_path):
    target = tmp_path / "library.zip"

    result = data.export(str(target))

    assert result["document_count"] == 1
    with zipfile.ZipFile(target) as archive:
        assert set(archive.namelist()) == {MANIFEST_NAME, CATALOG_NAME}
        manifest = json.loads(archive.read(MANIFEST_NAME))
    assert manifest["format_version"] == EXPORT_FORMAT_VERSION
    assert manifest["document_count"] == 1


def test_export_records_the_index_fingerprint(data, rag, indexed, tmp_path):
    target = tmp_path / "library.zip"
    data.export(str(target))

    with zipfile.ZipFile(target) as archive:
        manifest = json.loads(archive.read(MANIFEST_NAME))

    assert manifest["index_fingerprint"]["embedding_model"] == rag.embedding_model


def test_export_removes_its_temporary_snapshot(data, indexed, tmp_path):
    target = tmp_path / "library.zip"
    before = len(data.list_backups())

    data.export(str(target))

    # The snapshot taken to build the archive must not accumulate as a backup.
    assert len(data.list_backups()) == before


def test_export_rejects_a_non_zip_destination(data, tmp_path):
    with pytest.raises(ValidationError):
        data.export(str(tmp_path / "library.tar"))


def test_inspect_reads_the_manifest_without_importing(data, indexed, tmp_path):
    target = tmp_path / "library.zip"
    data.export(str(target))

    result = data.inspect(str(target))

    assert result["manifest"]["document_count"] == 1


def test_inspect_rejects_a_missing_archive(data, tmp_path):
    with pytest.raises(ValidationError):
        data.inspect(str(tmp_path / "absent.zip"))


def test_inspect_rejects_a_file_that_is_not_an_archive(data, tmp_path):
    bogus = tmp_path / "bogus.zip"
    bogus.write_text("not a zip", encoding="utf-8")

    with pytest.raises(ValidationError):
        data.inspect(str(bogus))


def test_inspect_rejects_an_unsupported_format_version(data, tmp_path):
    archive = tmp_path / "old.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr(MANIFEST_NAME, json.dumps({"format_version": 999}))
        zf.writestr(CATALOG_NAME, b"")

    with pytest.raises(ValidationError, match="Unsupported export format"):
        data.inspect(str(archive))


def test_import_restores_documents_from_an_archive(rag, data, indexed, tmp_path):
    target = tmp_path / "library.zip"
    data.export(str(target))

    # Wipe the live catalog, then restore it.
    document_id = rag.catalog.list_documents()[0]["id"]
    rag.catalog.delete_document(document_id)
    assert rag.catalog.list_documents() == []

    result = data.import_archive(str(target))

    assert result["status"] == "success"
    assert result["reindex_required"] is True
    assert len(rag.catalog.list_documents()) == 1


def test_import_backs_up_the_current_catalog_first(data, indexed, tmp_path):
    target = tmp_path / "library.zip"
    data.export(str(target))

    result = data.import_archive(str(target))

    # An import overwrites the database, so the previous state must survive.
    assert Path(result["backup_path"]).is_file()
