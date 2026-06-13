"""Structured run event timeline writer."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.database_schema import initialize_foundation_schema


def record_run_event(
    db_path: str | Path,
    *,
    run_id: str,
    event_type: str,
    node_name: str | None = None,
    status: str | None = None,
    message: str | None = None,
    error: str | None = None,
    started_at: str | None = None,
    finished_at: str | None = None,
    duration_ms: int | None = None,
    payload: dict[str, Any] | None = None,
    created_at: str | None = None,
) -> dict[str, Any]:
    """Upsert one structured run event and return the stored row payload."""

    clean_run_id = str(run_id or "").strip()
    clean_event_type = str(event_type or "").strip()
    if not clean_run_id:
        raise ValueError("run_id is required")
    if not clean_event_type:
        raise ValueError("event_type is required")

    timestamp = created_at or finished_at or started_at or _now_iso()
    row = {
        "event_id": _event_id(clean_run_id, clean_event_type, node_name, timestamp),
        "run_id": clean_run_id,
        "event_type": clean_event_type,
        "node_name": node_name,
        "status": status,
        "message": message,
        "error": error,
        "started_at": started_at,
        "finished_at": finished_at,
        "duration_ms": int(duration_ms or 0),
        "payload_json": _json_dumps(payload or {}),
        "created_at": timestamp,
    }

    path = initialize_foundation_schema(db_path)
    with sqlite3.connect(path, timeout=30) as connection:
        connection.execute("PRAGMA busy_timeout = 5000")
        connection.execute(
            """
            INSERT INTO run_events (
                event_id, run_id, event_type, node_name, status, message,
                error, started_at, finished_at, duration_ms, payload_json,
                created_at
            )
            VALUES (
                :event_id, :run_id, :event_type, :node_name, :status,
                :message, :error, :started_at, :finished_at, :duration_ms,
                :payload_json, :created_at
            )
            ON CONFLICT(event_id) DO UPDATE SET
                run_id = excluded.run_id,
                event_type = excluded.event_type,
                node_name = excluded.node_name,
                status = excluded.status,
                message = excluded.message,
                error = excluded.error,
                started_at = excluded.started_at,
                finished_at = excluded.finished_at,
                duration_ms = excluded.duration_ms,
                payload_json = excluded.payload_json,
                created_at = excluded.created_at
            """,
            row,
        )
    return row


def _event_id(run_id: str, event_type: str, node_name: str | None, created_at: str) -> str:
    digest = hashlib.sha256(
        "|".join((run_id, event_type, str(node_name or ""), created_at)).encode("utf-8")
    ).hexdigest()[:12]
    return f"evt_{digest}"


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")
