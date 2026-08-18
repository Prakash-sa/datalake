"""Console entry point: ``python -m rag_backend``.

Also the PyInstaller entry script for the packaged desktop sidecar. Uvicorn is
handed the already-constructed app rather than an import string, because the
frozen bundle has no importable module path to resolve.
"""

from __future__ import annotations

from rag_backend.app import create_app
from rag_backend.logging_config import configure_logging
from rag_backend.settings import get_settings


def main() -> None:
    """Run the API server."""
    import uvicorn

    settings = get_settings()
    configure_logging(
        settings.log_level,
        redact_logs=settings.log_redact,
        log_dir=settings.resolved_log_dir,
        max_bytes=settings.log_max_bytes,
        backup_count=settings.log_backup_count,
    )

    uvicorn.run(
        create_app(settings),
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    main()
