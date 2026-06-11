from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

from app.config import PROJECT_ROOT, load_settings


SENSITIVE_KEY_PARTS = (
    "token",
    "api_key",
    "key",
    "secret",
    "cookie",
    "authorization",
    "password",
)


def _is_sensitive_key(key: str) -> bool:
    normalized = key.lower()
    return any(part in normalized for part in SENSITIVE_KEY_PARTS)


def redact_sensitive(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: "<redacted>" if _is_sensitive_key(str(key)) else redact_sensitive(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact_sensitive(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_sensitive(item) for item in value)
    return value


def safe_log_dict(payload: dict[str, Any]) -> dict[str, Any]:
    redacted = redact_sensitive(payload)
    return redacted if isinstance(redacted, dict) else {}


def _resolve_log_dir(path_value: str) -> Path:
    path = Path(path_value)
    return path if path.is_absolute() else PROJECT_ROOT / path


def configure_logging(service_name: str) -> logging.Logger:
    settings = load_settings()
    log_dir = _resolve_log_dir(settings.log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger(f"xhs_agent.{service_name}")
    logger.setLevel(getattr(logging, settings.log_level, logging.INFO))
    logger.propagate = False

    log_path = log_dir / f"{service_name}.log"
    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )

    current_file_handler: RotatingFileHandler | None = None
    for handler in logger.handlers[:]:
        if not isinstance(handler, RotatingFileHandler):
            continue
        if (
            getattr(handler, "baseFilename", None) == str(log_path)
            and current_file_handler is None
        ):
            current_file_handler = handler
            continue
        logger.removeHandler(handler)
        handler.close()

    if current_file_handler is None:
        file_handler = RotatingFileHandler(
            log_path,
            maxBytes=max(1024, settings.log_max_bytes),
            backupCount=max(0, settings.log_backup_count),
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    else:
        current_file_handler.setFormatter(formatter)

    current_stream_handler: logging.StreamHandler | None = None
    for handler in logger.handlers[:]:
        if not isinstance(handler, logging.StreamHandler) or isinstance(
            handler, RotatingFileHandler
        ):
            continue
        if current_stream_handler is None:
            current_stream_handler = handler
            continue
        logger.removeHandler(handler)
        handler.close()

    if current_stream_handler is None:
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)
    else:
        current_stream_handler.setFormatter(formatter)

    return logger
