"""Queue event helpers backed by the structured run timeline."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from app.run_events import record_run_event


LOGGER = logging.getLogger("xhs_agent.queue_events")

_EVENT_STATUS = {
    "queue_enqueued": "queued",
    "queue_claimed": "running",
    "queue_reclaimed": "running",
    "queue_heartbeat": "running",
    "queue_requeued": "queued",
    "queue_succeeded": "succeeded",
    "queue_failed": "failed",
    "queue_cancelled": "cancelled",
    "queue_timed_out": "timed_out",
}

_EVENT_MESSAGE = {
    "queue_enqueued": "queue job enqueued",
    "queue_claimed": "queue job claimed",
    "queue_reclaimed": "stale queue job reclaimed",
    "queue_heartbeat": "queue worker heartbeat",
    "queue_requeued": "queue job requeued",
    "queue_succeeded": "queue job succeeded",
    "queue_failed": "queue job failed",
    "queue_cancelled": "queue job cancelled",
    "queue_timed_out": "queue job timed out",
}


def record_queue_event(
    db_path: str | Path,
    *,
    run_id: str,
    event_type: str,
    worker_id: str | None = None,
    attempts: int | None = None,
    max_attempts: int | None = None,
    message: str | None = None,
    error: str | None = None,
    created_at: str | None = None,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Record one queue transition as a run timeline event."""

    event_payload: dict[str, Any] = {}
    if worker_id:
        event_payload["worker_id"] = worker_id
    if attempts is not None:
        event_payload["attempts"] = int(attempts)
    if max_attempts is not None:
        event_payload["max_attempts"] = int(max_attempts)
    if payload:
        event_payload.update(payload)

    return record_run_event(
        db_path,
        run_id=run_id,
        event_type=event_type,
        node_name="sqlite_queue",
        status=_EVENT_STATUS.get(event_type, "queue"),
        message=message or _EVENT_MESSAGE.get(event_type),
        error=error,
        payload=event_payload,
        created_at=created_at,
    )


def record_queue_event_safely(
    db_path: str | Path | None,
    *,
    run_id: str,
    event_type: str,
    worker_id: str | None = None,
    attempts: int | None = None,
    max_attempts: int | None = None,
    message: str | None = None,
    error: str | None = None,
    payload: dict[str, Any] | None = None,
) -> bool:
    """Best-effort queue event recording; queue state changes must not fail on observability."""

    if db_path is None:
        return False
    try:
        record_queue_event(
            db_path,
            run_id=run_id,
            event_type=event_type,
            worker_id=worker_id,
            attempts=attempts,
            max_attempts=max_attempts,
            message=message,
            error=error,
            payload=payload,
        )
    except Exception as exc:
        LOGGER.warning(
            "queue_event_record_failed run_id=%s event_type=%s error=%s",
            run_id,
            event_type,
            exc,
        )
        return False
    return True
