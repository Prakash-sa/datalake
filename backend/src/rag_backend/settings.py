"""Application settings loaded from the environment.

Replaces the previous ``ConfigManager``, whose ``from_env`` classmethods mutated
class-level state in place. Settings are now an immutable, per-process object:
the ``ENV`` profile supplies defaults, and any explicitly set environment
variable overrides them.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict

Environment = Literal["development", "testing", "production"]

# Per-profile defaults. An explicitly exported environment variable always wins.
_PROFILE_DEFAULTS: dict[str, dict[str, str]] = {
    "development": {
        "DEBUG": "true",
        "LOG_LEVEL": "DEBUG",
        "WORKERS": "1",
        "ALLOWED_ORIGINS": "*",
        "LOG_REDACT": "false",
    },
    "testing": {
        "DEBUG": "true",
        "LOG_LEVEL": "DEBUG",
        "QUERY_TIMEOUT": "5",
    },
    "production": {
        "DEBUG": "false",
        "LOG_LEVEL": "INFO",
        "WORKERS": "4",
    },
}


class Settings(BaseSettings):
    """Runtime configuration for the RAG backend."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        frozen=True,
    )

    env: Environment = Field(default="production", alias="ENV")
    debug: bool = Field(default=False, alias="DEBUG")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    # HTTP server
    host: str = Field(default="127.0.0.1", alias="HOST")
    port: int = Field(default=8000, ge=1, le=65535, alias="PORT")
    workers: int = Field(default=4, ge=1, alias="WORKERS")

    # The Electron shell generates this token per launch and passes it to the
    # sidecar; when unset (e.g. plain docker compose) auth is disabled.
    api_token: str | None = Field(default=None, alias="RAG_API_TOKEN")

    # CORS. Kept as a raw string because pydantic-settings parses list-typed
    # fields as JSON, which would reject the documented comma-separated form.
    allowed_origins_raw: str = Field(default="http://localhost:3000", alias="ALLOWED_ORIGINS")
    cors_cache_max_age: int = Field(default=600, ge=0, alias="CORS_CACHE_MAX_AGE")

    # RAG engine
    ollama_url: str = Field(default="http://127.0.0.1:11434", alias="OLLAMA_URL")
    embedding_model: str = Field(default="qwen3-embedding:0.6b", alias="EMBEDDING_MODEL")
    llm_model: str = Field(default="qwen3:4b", alias="LLM_MODEL")
    llm_temperature: float = Field(default=0.1, ge=0.0, le=1.0, alias="LLM_TEMPERATURE")

    # Embeddings. "local" runs in-process via ONNX and needs no external
    # software; "ollama" delegates to the daemon. Switching invalidates the
    # index, which the fingerprint enforces.
    embedding_provider: Literal["local", "ollama"] = Field(
        default="local", alias="EMBEDDING_PROVIDER"
    )
    local_embedding_model_dir: str | None = Field(default=None, alias="LOCAL_EMBEDDING_MODEL_DIR")

    # Local storage
    chroma_path: str = Field(default="./chroma_db", alias="CHROMA_PATH")
    app_data_dir: str = Field(default=".", alias="APP_DATA_DIR")
    app_db_path: str | None = Field(default=None, alias="APP_DB_PATH")

    # Logging. Redaction is disabled in development, where full paths are what
    # make an error actionable.
    log_dir: str | None = Field(default=None, alias="LOG_DIR")
    log_max_bytes: int = Field(default=5 * 1024 * 1024, ge=1024, alias="LOG_MAX_BYTES")
    log_backup_count: int = Field(default=3, ge=0, alias="LOG_BACKUP_COUNT")
    log_redact: bool = Field(default=True, alias="LOG_REDACT")

    # Resource limits
    max_documents: int = Field(default=10_000, ge=1, alias="MAX_DOCUMENTS")
    max_query_length: int = Field(default=1_000, ge=1, alias="MAX_QUERY_LENGTH")
    max_results: int = Field(default=100, ge=1, alias="MAX_RESULTS")
    query_timeout: int = Field(default=30, ge=1, alias="QUERY_TIMEOUT")

    @computed_field  # type: ignore[prop-decorator]
    @property
    def allowed_origins(self) -> list[str]:
        """CORS origins parsed from the comma-separated environment value."""
        return [o.strip() for o in self.allowed_origins_raw.split(",") if o.strip()]

    @computed_field  # type: ignore[prop-decorator]
    @property
    def resolved_local_embedding_model_dir(self) -> str:
        """Where the bundled ONNX embedding model lives.

        Defaults beside the package so a PyInstaller bundle and a source
        checkout resolve the same way.
        """
        if self.local_embedding_model_dir:
            return self.local_embedding_model_dir
        return str(Path(__file__).resolve().parent / "models" / "all-MiniLM-L6-v2")

    @computed_field  # type: ignore[prop-decorator]
    @property
    def resolved_log_dir(self) -> str:
        """Log directory, defaulting to ``<APP_DATA_DIR>/logs``."""
        if self.log_dir:
            return self.log_dir
        return str(Path(self.app_data_dir) / "logs")

    @computed_field  # type: ignore[prop-decorator]
    @property
    def resolved_app_db_path(self) -> str:
        """Catalog database path, defaulting to ``<APP_DATA_DIR>/app.db``."""
        if self.app_db_path:
            return self.app_db_path
        return str(Path(self.app_data_dir) / "app.db")


def build_settings() -> Settings:
    """Build settings, layering profile defaults under the real environment."""
    env = os.getenv("ENV", "production")
    defaults = _PROFILE_DEFAULTS.get(env, _PROFILE_DEFAULTS["production"])
    overrides = {key: value for key, value in defaults.items() if key not in os.environ}
    return Settings(**overrides)  # type: ignore[arg-type]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide settings singleton."""
    return build_settings()
