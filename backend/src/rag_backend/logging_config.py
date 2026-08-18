"""Centralised logging setup: redaction, rotation, and retention.

Library modules must only call ``logging.getLogger(__name__)``. Handler, level,
and filter configuration happens once, here, at application startup.

The privacy policy promises that document content never leaves the machine and
is not written to logs. Paths are the subtle case: no log call interpolates one
directly, but exception messages carry them (``No extractable text found in
/Users/someone/medical results.pdf``), and a filename alone can be sensitive.
Redaction therefore operates on the formatted message rather than on call sites.
"""

from __future__ import annotations

import logging
import logging.handlers
import re
from pathlib import Path

LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

DEFAULT_MAX_BYTES = 5 * 1024 * 1024
DEFAULT_BACKUP_COUNT = 3
LOG_FILENAME = "rag-backend.log"

PATH_PLACEHOLDER = "<path>"
TOKEN_PLACEHOLDER = "<redacted>"

# POSIX absolute paths (/Users/x/y.pdf) and Windows paths (C:\Users\x\y.pdf).
# Requires at least one separator so a bare "/" or a URL path is left alone.
_POSIX_PATH = re.compile(r"(?<![\w:/])/(?:[^\s/\\:*?\"<>|]+/)+[^\s/\\:*?\"<>|]*")
_WINDOWS_PATH = re.compile(r"[A-Za-z]:\\(?:[^\s\\/:*?\"<>|]+\\)*[^\s\\/:*?\"<>|]*")

# Bearer tokens and long hex secrets that must never reach a log file.
_BEARER = re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._\-]+")
_HEX_SECRET = re.compile(r"\b[0-9a-f]{32,}\b")


def redact(message: str) -> str:
    """Strip filesystem paths and credentials from a log message."""
    message = _BEARER.sub(f"Bearer {TOKEN_PLACEHOLDER}", message)
    message = _HEX_SECRET.sub(TOKEN_PLACEHOLDER, message)
    message = _WINDOWS_PATH.sub(PATH_PLACEHOLDER, message)
    return _POSIX_PATH.sub(PATH_PLACEHOLDER, message)


class RedactingFilter(logging.Filter):
    """Rewrites each record's formatted message in place.

    Formatting happens here rather than in a Formatter so that redaction also
    covers exception text, which is where paths actually leak.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        original = record.getMessage()
        redacted = redact(original)
        if redacted != original:
            # Replace args too, or %-formatting would re-insert the raw values.
            record.msg = redacted
            record.args = None

        if record.exc_info:
            # Render the traceback now so its text can be redacted, then drop
            # the structured exception to stop the handler re-rendering it.
            formatted = logging.Formatter().formatException(record.exc_info)
            record.msg = f"{record.getMessage()}\n{redact(formatted)}"
            record.args = None
            record.exc_info = None
            record.exc_text = None
        return True


def configure_logging(
    level: str = "INFO",
    *,
    redact_logs: bool = True,
    log_dir: str | None = None,
    max_bytes: int = DEFAULT_MAX_BYTES,
    backup_count: int = DEFAULT_BACKUP_COUNT,
) -> None:
    """Configure root logging for the process.

    ``log_dir`` enables a size-rotating file handler, bounding disk use at
    ``max_bytes * (backup_count + 1)``. Redaction is on by default and is
    disabled only in development, where full paths are what make an error
    actionable.
    """
    handlers: list[logging.Handler] = [logging.StreamHandler()]

    if log_dir:
        directory = Path(log_dir).expanduser()
        try:
            directory.mkdir(parents=True, exist_ok=True)
            handlers.append(
                logging.handlers.RotatingFileHandler(
                    directory / LOG_FILENAME,
                    maxBytes=max_bytes,
                    backupCount=backup_count,
                    encoding="utf-8",
                )
            )
        except OSError:
            # A read-only or missing data directory must not stop the app from
            # starting; console logging still works.
            logging.getLogger(__name__).warning(
                "Could not open the log directory; file logging is disabled"
            )

    formatter = logging.Formatter(LOG_FORMAT)
    redacting = RedactingFilter()
    for handler in handlers:
        handler.setFormatter(formatter)
        if redact_logs:
            handler.addFilter(redacting)

    logging.basicConfig(level=level.upper(), handlers=handlers, force=True)
