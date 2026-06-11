from __future__ import annotations

import logging
from pathlib import Path

from app.logging_config import configure_logging, redact_sensitive, safe_log_dict


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
