"""Tests for environment-driven settings."""

from __future__ import annotations

from rag_backend.settings import Settings, build_settings


def test_allowed_origins_parses_comma_separated_value():
    settings = Settings(ALLOWED_ORIGINS="http://a.test, http://b.test ,")

    assert settings.allowed_origins == ["http://a.test", "http://b.test"]


def test_app_db_path_defaults_under_app_data_dir():
    settings = Settings(APP_DATA_DIR="/tmp/ragdata")

    assert settings.resolved_app_db_path == "/tmp/ragdata/app.db"


def test_explicit_app_db_path_wins():
    settings = Settings(APP_DATA_DIR="/tmp/ragdata", APP_DB_PATH="/custom/app.db")

    assert settings.resolved_app_db_path == "/custom/app.db"


def test_development_profile_supplies_defaults(monkeypatch):
    monkeypatch.setenv("ENV", "development")
    monkeypatch.delenv("LOG_LEVEL", raising=False)
    monkeypatch.delenv("WORKERS", raising=False)

    settings = build_settings()

    assert settings.debug is True
    assert settings.log_level == "DEBUG"
    assert settings.workers == 1


def test_explicit_environment_variable_overrides_profile_default(monkeypatch):
    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("LOG_LEVEL", "WARNING")

    settings = build_settings()

    assert settings.log_level == "WARNING"


def test_debug_accepts_profile_words_from_shell_environment(monkeypatch):
    monkeypatch.setenv("DEBUG", "release")

    settings = build_settings()

    assert settings.debug is False


def test_settings_are_immutable():
    settings = Settings()

    try:
        settings.port = 9999
    except Exception:
        return
    raise AssertionError("Settings should be frozen")
