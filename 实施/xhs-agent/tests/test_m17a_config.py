from __future__ import annotations

from app.config import load_settings


def test_guardrail_settings_default_to_development_safe_values(monkeypatch) -> None:
    monkeypatch.delenv("XHS_AGENT_API_TOKEN", raising=False)
    monkeypatch.delenv("XHS_AGENT_LOG_DIR", raising=False)
    monkeypatch.delenv("XHS_AGENT_LOG_LEVEL", raising=False)
    monkeypatch.delenv("XHS_AGENT_LOG_MAX_BYTES", raising=False)
    monkeypatch.delenv("XHS_AGENT_LOG_BACKUP_COUNT", raising=False)

    settings = load_settings()

    assert settings.api_token is None
    assert settings.log_dir == "data/logs"
    assert settings.log_level == "INFO"
    assert settings.log_max_bytes == 1048576
    assert settings.log_backup_count == 5


def test_guardrail_settings_read_environment(monkeypatch) -> None:
    monkeypatch.setenv("XHS_AGENT_API_TOKEN", "secret-token")
    monkeypatch.setenv("XHS_AGENT_LOG_DIR", "tmp/logs")
    monkeypatch.setenv("XHS_AGENT_LOG_LEVEL", "debug")
    monkeypatch.setenv("XHS_AGENT_LOG_MAX_BYTES", "2048")
    monkeypatch.setenv("XHS_AGENT_LOG_BACKUP_COUNT", "2")

    settings = load_settings()

    assert settings.api_token == "secret-token"
    assert settings.log_dir == "tmp/logs"
    assert settings.log_level == "DEBUG"
    assert settings.log_max_bytes == 2048
    assert settings.log_backup_count == 2
