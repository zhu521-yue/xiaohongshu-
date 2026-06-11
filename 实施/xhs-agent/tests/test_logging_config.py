from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

import pytest

from app.logging_config import configure_logging, redact_sensitive, safe_log_dict


@pytest.fixture(autouse=True)
def clean_api_logger_handlers():
    logger = logging.getLogger("xhs_agent.api")
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
        handler.close()

    yield

    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
        handler.close()


def _file_handlers(logger: logging.Logger) -> list[RotatingFileHandler]:
    return [
        handler
        for handler in logger.handlers
        if isinstance(handler, RotatingFileHandler)
    ]


def _standalone_stream_handlers(logger: logging.Logger) -> list[logging.StreamHandler]:
    return [
        handler
        for handler in logger.handlers
        if isinstance(handler, logging.StreamHandler)
        and not isinstance(handler, RotatingFileHandler)
    ]


def test_redact_sensitive_masks_nested_secret_values() -> None:
    payload = {
        "api_key": "key-value",
        "nested": {
            "cookie": "cookie-value",
            "normal": "visible",
        },
        "items": [
            {"authorization": "Bearer abc"},
            {"topic": "小红书新手选题方法"},
        ],
    }

    redacted = redact_sensitive(payload)

    assert redacted["api_key"] == "<redacted>"
    assert redacted["nested"]["cookie"] == "<redacted>"
    assert redacted["nested"]["normal"] == "visible"
    assert redacted["items"][0]["authorization"] == "<redacted>"
    assert redacted["items"][1]["topic"] == "小红书新手选题方法"


def test_safe_log_dict_keeps_non_sensitive_values() -> None:
    result = safe_log_dict({"run_id": "run_1", "token": "secret"})

    assert result == {"run_id": "run_1", "token": "<redacted>"}


def test_configure_logging_adds_file_and_standalone_stream_handlers(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("XHS_AGENT_LOG_DIR", str(tmp_path))
    monkeypatch.setenv("XHS_AGENT_LOG_LEVEL", "INFO")
    monkeypatch.setenv("XHS_AGENT_LOG_MAX_BYTES", "4096")
    monkeypatch.setenv("XHS_AGENT_LOG_BACKUP_COUNT", "1")

    logger = configure_logging("api")

    assert len(_file_handlers(logger)) == 1
    assert len(_standalone_stream_handlers(logger)) == 1


def test_configure_logging_repeated_same_dir_does_not_duplicate_handlers(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("XHS_AGENT_LOG_DIR", str(tmp_path))
    monkeypatch.setenv("XHS_AGENT_LOG_LEVEL", "INFO")
    monkeypatch.setenv("XHS_AGENT_LOG_MAX_BYTES", "4096")
    monkeypatch.setenv("XHS_AGENT_LOG_BACKUP_COUNT", "1")

    first_logger = configure_logging("api")
    second_logger = configure_logging("api")

    assert first_logger is second_logger
    assert len(_file_handlers(second_logger)) == 1
    assert len(_standalone_stream_handlers(second_logger)) == 1


def test_configure_logging_changed_dir_replaces_stale_file_handler(
    tmp_path: Path, monkeypatch
) -> None:
    first_log_dir = tmp_path / "first"
    second_log_dir = tmp_path / "second"

    monkeypatch.setenv("XHS_AGENT_LOG_DIR", str(first_log_dir))
    monkeypatch.setenv("XHS_AGENT_LOG_LEVEL", "INFO")
    monkeypatch.setenv("XHS_AGENT_LOG_MAX_BYTES", "4096")
    monkeypatch.setenv("XHS_AGENT_LOG_BACKUP_COUNT", "1")
    configure_logging("api")

    monkeypatch.setenv("XHS_AGENT_LOG_DIR", str(second_log_dir))
    logger = configure_logging("api")

    file_handlers = _file_handlers(logger)
    assert len(file_handlers) == 1
    assert file_handlers[0].baseFilename == str(second_log_dir / "api.log")
    assert len(_standalone_stream_handlers(logger)) == 1


def test_configure_logging_writes_to_service_log(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("XHS_AGENT_LOG_DIR", str(tmp_path))
    monkeypatch.setenv("XHS_AGENT_LOG_LEVEL", "INFO")
    monkeypatch.setenv("XHS_AGENT_LOG_MAX_BYTES", "4096")
    monkeypatch.setenv("XHS_AGENT_LOG_BACKUP_COUNT", "1")

    logger = configure_logging("api")
    logger.info("guardrail log check")

    log_path = tmp_path / "api.log"
    assert log_path.exists()
    assert "guardrail log check" in log_path.read_text(encoding="utf-8")
    assert logger.level == logging.INFO
