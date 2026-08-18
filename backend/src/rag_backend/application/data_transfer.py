"""Export, import, and backup of local data.

The plan requires a way to move a library between machines, and a backup taken
before any schema-changing update. Exports are a single zip holding the catalog
database and a manifest; vectors are deliberately excluded because they are
reproducible from the sources and would multiply the archive size.
"""

from __future__ import annotations

import json
import logging
import shutil
import sqlite3
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from rag_backend.errors import ErrorCode, RagError, ValidationError

logger = logging.getLogger(__name__)

EXPORT_FORMAT_VERSION = 1
MANIFEST_NAME = "manifest.json"
CATALOG_NAME = "catalog.db"


class DataTransferService:
    """Creates and restores local data archives."""

    def __init__(self, rag_service: Any) -> None:
        self._rag = rag_service
        self._catalog = rag_service.catalog

    # -- Backup ---------------------------------------------------------------

    def backup(self, destination_dir: str | None = None) -> dict[str, Any]:
        """Snapshot the catalog database.

        Uses SQLite's backup API rather than copying the file, so a snapshot
        taken while the app is running is guaranteed consistent.
        """
        db_path = Path(self._rag.app_db_path)
        target_dir = Path(destination_dir or db_path.parent / "backups").expanduser()
        target_dir.mkdir(parents=True, exist_ok=True)

        # Microseconds, because two backups in the same second would otherwise
        # resolve to the same filename and the first would be lost.
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S_%fZ")
        target = target_dir / f"catalog-{stamp}.db"

        try:
            source = sqlite3.connect(str(db_path))
            try:
                destination = sqlite3.connect(str(target))
                try:
                    source.backup(destination)
                finally:
                    destination.close()
            finally:
                source.close()
        except (sqlite3.Error, OSError) as e:
            raise RagError(f"Backup failed: {e}", code=ErrorCode.STORAGE_UNAVAILABLE) from e

        return {
            "status": "success",
            "path": str(target),
            "size_bytes": target.stat().st_size,
            "created_at": datetime.now(UTC).isoformat(),
        }

    # -- Export ---------------------------------------------------------------

    def export(self, destination: str) -> dict[str, Any]:
        """Write a portable archive of the catalog."""
        target = Path(destination).expanduser()
        if target.suffix != ".zip":
            raise ValidationError("Export destination must end in .zip")
        target.parent.mkdir(parents=True, exist_ok=True)

        snapshot = self.backup(destination_dir=str(target.parent))
        snapshot_path = Path(snapshot["path"])

        documents = self._catalog.list_documents()
        manifest = {
            "format_version": EXPORT_FORMAT_VERSION,
            "exported_at": datetime.now(UTC).isoformat(),
            "document_count": len(documents),
            "index_fingerprint": self._rag.stored_fingerprint(),
            # Sources are referenced, not embedded: an archive that inlined
            # every original file could be enormous.
            "source_paths": [doc["source_path"] for doc in documents],
        }

        try:
            with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
                archive.writestr(MANIFEST_NAME, json.dumps(manifest, indent=2))
                archive.write(snapshot_path, CATALOG_NAME)
        except OSError as e:
            raise RagError(f"Export failed: {e}", code=ErrorCode.STORAGE_UNAVAILABLE) from e
        finally:
            snapshot_path.unlink(missing_ok=True)

        return {
            "status": "success",
            "path": str(target),
            "size_bytes": target.stat().st_size,
            "document_count": len(documents),
        }

    # -- Import ---------------------------------------------------------------

    def inspect(self, source: str) -> dict[str, Any]:
        """Read an archive's manifest without importing it."""
        archive_path = Path(source).expanduser()
        if not archive_path.is_file():
            raise ValidationError(f"Archive not found: {source}")

        try:
            with zipfile.ZipFile(archive_path) as archive:
                names = set(archive.namelist())
                if MANIFEST_NAME not in names or CATALOG_NAME not in names:
                    raise ValidationError("Archive is missing its manifest or catalog")
                manifest = json.loads(archive.read(MANIFEST_NAME))
        except zipfile.BadZipFile as e:
            raise ValidationError(f"Not a readable archive: {e}") from e

        if manifest.get("format_version") != EXPORT_FORMAT_VERSION:
            raise ValidationError(
                f"Unsupported export format {manifest.get('format_version')}; "
                f"expected {EXPORT_FORMAT_VERSION}"
            )
        return {"status": "success", "manifest": manifest}

    def import_archive(self, source: str) -> dict[str, Any]:
        """Restore a catalog from an archive, backing up the current one first.

        Vectors are not restored, so imported documents must be reindexed from
        their sources. That is reported rather than done implicitly, since
        reindexing can take a long time.
        """
        inspected = self.inspect(source)
        manifest = inspected["manifest"]

        db_path = Path(self._rag.app_db_path)
        safety = self.backup()

        staged = db_path.with_name(db_path.name + ".import")
        try:
            with zipfile.ZipFile(Path(source).expanduser()) as archive:
                staged.write_bytes(archive.read(CATALOG_NAME))

            # Restore through SQLite's backup API rather than overwriting the
            # file. The catalog runs in WAL mode, so replacing the bytes under a
            # live connection leaves a stale -wal that is replayed over the
            # restored data.
            source_conn = sqlite3.connect(str(staged))
            try:
                destination = sqlite3.connect(str(db_path))
                try:
                    source_conn.backup(destination)
                finally:
                    destination.close()
            finally:
                source_conn.close()
        except (OSError, sqlite3.Error) as e:
            raise RagError(f"Import failed: {e}", code=ErrorCode.STORAGE_UNAVAILABLE) from e
        finally:
            staged.unlink(missing_ok=True)

        return {
            "status": "success",
            "document_count": manifest.get("document_count", 0),
            "backup_path": safety["path"],
            "restart_required": True,
            "reindex_required": True,
        }

    # -- Housekeeping ---------------------------------------------------------

    def list_backups(self) -> list[dict[str, Any]]:
        """List available catalog snapshots, newest first."""
        backup_dir = Path(self._rag.app_db_path).parent / "backups"
        if not backup_dir.is_dir():
            return []

        entries = [
            {
                "path": str(path),
                "size_bytes": path.stat().st_size,
                "created_at": datetime.fromtimestamp(path.stat().st_mtime, UTC).isoformat(),
            }
            for path in backup_dir.glob("catalog-*.db")
        ]
        return sorted(entries, key=lambda item: item["created_at"], reverse=True)

    @staticmethod
    def free_space_bytes(path: str) -> int:
        """Free space on the volume holding ``path``."""
        return shutil.disk_usage(Path(path).parent).free
