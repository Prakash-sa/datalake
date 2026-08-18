"""Log redaction and rotation."""

from __future__ import annotations

import logging

import pytest

from rag_backend.logging_config import (
    LOG_FILENAME,
    PATH_PLACEHOLDER,
    TOKEN_PLACEHOLDER,
    RedactingFilter,
    configure_logging,
    redact,
)


class TestRedact:
    def test_strips_a_posix_path(self):
        result = redact("No extractable text found in /Users/sam/medical results.pdf")

        assert "/Users/sam" not in result
        assert PATH_PLACEHOLDER in result

    def test_strips_a_windows_path(self):
        result = redact(r"Failed to read C:\Users\sam\taxes.docx")

        assert "sam" not in result
        assert PATH_PLACEHOLDER in result

    def test_strips_the_filename_not_just_the_directory(self):
        # A filename alone can be sensitive, so the whole path goes.
        result = redact("Parsed /home/sam/divorce-settlement.pdf")

        assert "divorce-settlement" not in result

    def test_strips_a_bearer_token(self):
        result = redact("Authorization: Bearer abc123DEF456.token-value")

        assert "abc123DEF456" not in result
        assert TOKEN_PLACEHOLDER in result

    def test_strips_a_long_hex_secret(self):
        secret = "a" * 40
        result = redact(f"token={secret}")

        assert secret not in result

    def test_leaves_ordinary_messages_alone(self):
        message = "RAG service ready (embedding=qwen3-embedding:0.6b, llm=qwen3:4b)"

        assert redact(message) == message

    def test_leaves_urls_alone(self):
        # The Ollama endpoint is configuration, not private data, and is needed
        # to diagnose connection failures.
        message = "Ollama readiness failed for http://127.0.0.1:11434"

        assert "127.0.0.1:11434" in redact(message)

    def test_preserves_surrounding_text(self):
        result = redact("Ingestion failed for /a/b/c.pdf after 2 attempts")

        assert result.startswith("Ingestion failed for ")
        assert result.endswith(" after 2 attempts")


class TestRedactingFilter:
    def _record(self, msg, args=(), exc_info=None) -> logging.LogRecord:
        return logging.LogRecord("test", logging.ERROR, __file__, 1, msg, args, exc_info)

    def test_redacts_a_formatted_message(self):
        record = self._record("Failed: %s", ("/Users/sam/file.pdf",))

        RedactingFilter().filter(record)

        assert "/Users/sam" not in record.getMessage()

    def test_clears_args_so_formatting_cannot_reinsert_the_path(self):
        record = self._record("Failed: %s", ("/Users/sam/file.pdf",))

        RedactingFilter().filter(record)

        assert record.args is None

    def test_redacts_paths_inside_exception_text(self):
        # This is the real leak: no call site interpolates a path, but the
        # exceptions they log contain them.
        try:
            raise ValueError("No extractable text found in /Users/sam/secret.pdf")
        except ValueError:
            import sys

            record = self._record("File ingestion failed", exc_info=sys.exc_info())

        RedactingFilter().filter(record)
        rendered = record.getMessage()

        assert "/Users/sam" not in rendered
        assert "ValueError" in rendered

    def test_always_keeps_the_record(self):
        record = self._record("anything")

        assert RedactingFilter().filter(record) is True


class TestConfigureLogging:
    @pytest.fixture(autouse=True)
    def _restore_logging(self):
        yield
        logging.basicConfig(force=True)

    def test_writes_a_rotating_log_file(self, tmp_path):
        configure_logging("INFO", log_dir=str(tmp_path))
        logging.getLogger("test").info("hello")

        assert (tmp_path / LOG_FILENAME).is_file()

    def test_redacts_what_reaches_the_file(self, tmp_path):
        configure_logging("INFO", log_dir=str(tmp_path), redact_logs=True)
        logging.getLogger("test").error("Failed: /Users/sam/private.pdf")

        contents = (tmp_path / LOG_FILENAME).read_text()
        assert "/Users/sam" not in contents
        assert PATH_PLACEHOLDER in contents

    def test_redaction_can_be_disabled_for_development(self, tmp_path):
        configure_logging("INFO", log_dir=str(tmp_path), redact_logs=False)
        logging.getLogger("test").error("Failed: /Users/sam/private.pdf")

        assert "/Users/sam" in (tmp_path / LOG_FILENAME).read_text()

    def test_rotation_bounds_total_disk_use(self, tmp_path):
        configure_logging("INFO", log_dir=str(tmp_path), max_bytes=1024, backup_count=2)
        logger = logging.getLogger("test")
        for index in range(500):
            logger.info("padding line %d %s", index, "x" * 100)

        logs = list(tmp_path.glob(f"{LOG_FILENAME}*"))
        # Active file plus at most backup_count rotations.
        assert 1 < len(logs) <= 3

    def test_an_unwritable_log_directory_does_not_stop_startup(self, tmp_path):
        blocker = tmp_path / "logs"
        blocker.write_text("I am a file, not a directory", encoding="utf-8")

        configure_logging("INFO", log_dir=str(blocker))
        logging.getLogger("test").info("still works")

    def test_console_logging_works_without_a_log_directory(self):
        configure_logging("INFO")
        logging.getLogger("test").info("console only")

        assert logging.getLogger().handlers
