"""Local safety guardrails for real platform operations."""

from __future__ import annotations

import os
import random
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from app.json_store import read_json_file, write_json_atomic


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_GUARDRAIL_PATH = PROJECT_ROOT / "data" / "platform_guardrails.json"
GUARDRAIL_LOCK = threading.Lock()

RISK_CONTROL_KEYWORDS = (
    "风控",
    "频繁",
    "验证",
    "安全",
    "限制",
    "blocked",
    "captcha",
    "risk",
)


class PlatformOperationBlocked(RuntimeError):
    """Raised when a real platform operation is blocked by local guardrails."""


def _now() -> datetime:
    return datetime.now()


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return default


def _guardrail_path() -> Path:
    value = os.getenv("XHS_PLATFORM_GUARDRAIL_PATH")
    if value:
        path = Path(value)
        if not path.is_absolute():
            return PROJECT_ROOT / path
        return path
    return DEFAULT_GUARDRAIL_PATH


def _date_key(now: datetime | None = None) -> str:
    return (now or _now()).date().isoformat()


def _empty_state() -> dict[str, Any]:
    return {"creator_publish": {}}


def _load_state() -> dict[str, Any]:
    return read_json_file(_guardrail_path(), default=_empty_state(), expected_type=dict)


def _save_state(state: dict[str, Any]) -> None:
    write_json_atomic(_guardrail_path(), state)


def _creator_state_for_today(state: dict[str, Any], now: datetime | None = None) -> dict[str, Any]:
    today = _date_key(now)
    creator_state = state.setdefault("creator_publish", {})
    if creator_state.get("date") != today:
        creator_state.clear()
        creator_state.update(
            {
                "date": today,
                "success_count": 0,
                "stopped": False,
                "stop_reason": None,
                "updated_at": (now or _now()).isoformat(timespec="seconds"),
            }
        )
    return creator_state


def creator_daily_limit() -> int:
    """Return the configured creator daily publish limit, capped to one digit."""

    configured = _env_int("XHS_CREATOR_DAILY_LIMIT", 3)
    return max(0, min(configured, 9))


def check_creator_publish_allowed(now: datetime | None = None) -> dict[str, Any]:
    with GUARDRAIL_LOCK:
        state = _load_state()
        creator_state = _creator_state_for_today(state, now=now)
        limit = creator_daily_limit()
        count = int(creator_state.get("success_count") or 0)

        if creator_state.get("stopped") is True:
            reason = str(creator_state.get("stop_reason") or "creator publishing stopped")
            return {
                "allowed": False,
                "reason": reason,
                "date": creator_state.get("date"),
                "success_count": count,
                "daily_limit": limit,
            }

        if count >= limit:
            return {
                "allowed": False,
                "reason": f"creator daily limit reached: {count}/{limit}",
                "date": creator_state.get("date"),
                "success_count": count,
                "daily_limit": limit,
            }

        return {
            "allowed": True,
            "reason": None,
            "date": creator_state.get("date"),
            "success_count": count,
            "daily_limit": limit,
        }


def ensure_creator_publish_allowed(now: datetime | None = None) -> None:
    result = check_creator_publish_allowed(now=now)
    if result.get("allowed") is not True:
        raise PlatformOperationBlocked(str(result.get("reason") or "creator publishing blocked"))


def sleep_before_creator_publish() -> None:
    min_delay = _env_float("XHS_CREATOR_MIN_DELAY_SECONDS", _env_float("XHS_MIN_DELAY_SECONDS", 2.0))
    max_delay = _env_float("XHS_CREATOR_MAX_DELAY_SECONDS", _env_float("XHS_MAX_DELAY_SECONDS", 5.0))
    if max_delay < min_delay:
        max_delay = min_delay
    if max_delay <= 0:
        return
    time.sleep(random.uniform(max(0.0, min_delay), max_delay))


def record_creator_publish_success(now: datetime | None = None) -> dict[str, Any]:
    with GUARDRAIL_LOCK:
        state = _load_state()
        creator_state = _creator_state_for_today(state, now=now)
        creator_state["success_count"] = int(creator_state.get("success_count") or 0) + 1
        creator_state["updated_at"] = (now or _now()).isoformat(timespec="seconds")
        _save_state(state)
        return dict(creator_state)


def record_creator_publish_failure(reason: str, now: datetime | None = None) -> dict[str, Any]:
    with GUARDRAIL_LOCK:
        state = _load_state()
        creator_state = _creator_state_for_today(state, now=now)
        creator_state["stopped"] = True
        creator_state["stop_reason"] = str(reason or "creator publish failed").strip()
        creator_state["updated_at"] = (now or _now()).isoformat(timespec="seconds")
        _save_state(state)
        return dict(creator_state)


def _text_values(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        values: list[str] = []
        for child in value.values():
            values.extend(_text_values(child))
        return values
    if isinstance(value, (list, tuple, set)):
        values = []
        for child in value:
            values.extend(_text_values(child))
        return values
    return [str(value)]


def is_risk_control_response(value: Any) -> bool:
    text = " ".join(_text_values(value)).lower()
    return any(keyword.lower() in text for keyword in RISK_CONTROL_KEYWORDS)

