"""Creator note performance sync service.

The service is intentionally dependency-injected so platform reads, run
loading, and performance recording stay behind existing application
boundaries. This keeps HTTP handlers and CLI scripts thin.
"""

from __future__ import annotations

from typing import Any, Callable


METRIC_KEYS = ("views", "likes", "collects", "comments", "follows")

RunLoader = Callable[[str], dict[str, Any] | None]
StatusReader = Callable[..., dict[str, Any]]
PerformanceRecorder = Callable[[dict[str, Any]], dict[str, Any]]


def _safe_int(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def _state_from_run(run_record: dict[str, Any]) -> dict[str, Any]:
    state = run_record.get("state")
    return state if isinstance(state, dict) else {}


def _summary_from_run(run_record: dict[str, Any]) -> dict[str, Any]:
    summary = run_record.get("summary")
    return summary if isinstance(summary, dict) else {}


def resolve_creator_note_id(
    *,
    creator_note_id: str = "",
    run_id: str = "",
    run_loader: RunLoader | None = None,
) -> dict[str, str]:
    clean_creator_note_id = str(creator_note_id or "").strip()
    clean_run_id = str(run_id or "").strip()
    if clean_creator_note_id:
        return {
            "creator_note_id": clean_creator_note_id,
            "run_id": clean_run_id,
            "source": "request",
        }
    if not clean_run_id:
        raise ValueError("Missing required field: creator_note_id or run_id")
    if run_loader is None:
        raise ValueError("run_loader is required when resolving creator_note_id from run_id")

    run_record = run_loader(clean_run_id)
    if not isinstance(run_record, dict):
        raise ValueError(f"Run not found: {clean_run_id}")

    state_note_id = str(_state_from_run(run_record).get("creator_note_id") or "").strip()
    if state_note_id:
        return {
            "creator_note_id": state_note_id,
            "run_id": clean_run_id,
            "source": "run_state",
        }

    summary_note_id = str(_summary_from_run(run_record).get("creator_note_id") or "").strip()
    if summary_note_id:
        return {
            "creator_note_id": summary_note_id,
            "run_id": clean_run_id,
            "source": "run_summary",
        }

    raise ValueError(f"Run has no creator_note_id: {clean_run_id}")


def _creator_note_status(status_response: dict[str, Any]) -> dict[str, Any]:
    status = status_response.get("creator_note_status")
    if isinstance(status, dict):
        return status
    return status_response if isinstance(status_response, dict) else {}


def build_performance_payload(
    *,
    creator_note_id: str,
    creator_note_status: dict[str, Any],
    notes: str | None = None,
) -> dict[str, Any]:
    if creator_note_status.get("ok") is not True or creator_note_status.get("status") != "synced":
        status = str(creator_note_status.get("status") or "unknown")
        raise ValueError(f"creator note is not synced: {status}")

    metrics = creator_note_status.get("metrics_snapshot")
    metrics = metrics if isinstance(metrics, dict) else {}
    payload: dict[str, Any] = {
        "creator_note_id": str(
            creator_note_status.get("creator_note_id") or creator_note_id
        ).strip(),
    }
    for key in METRIC_KEYS:
        payload[key] = _safe_int(metrics.get(key))

    clean_notes = str(notes or "").strip()
    if clean_notes:
        payload["notes"] = clean_notes
    return payload


def sync_creator_note_performance(
    *,
    creator_note_id: str = "",
    run_id: str = "",
    limit: int = 50,
    wait: bool = False,
    attempts: int = 5,
    interval_seconds: float = 2.0,
    notes: str | None = None,
    run_loader: RunLoader | None = None,
    status_reader: StatusReader,
    performance_recorder: PerformanceRecorder,
) -> dict[str, Any]:
    target = resolve_creator_note_id(
        creator_note_id=creator_note_id,
        run_id=run_id,
        run_loader=run_loader,
    )
    status_response = status_reader(
        creator_note_id=target["creator_note_id"],
        limit=max(0, int(limit)),
        wait=bool(wait),
        attempts=max(1, int(attempts)),
        interval_seconds=max(0.0, float(interval_seconds)),
    )
    note_status = _creator_note_status(status_response)
    payload = build_performance_payload(
        creator_note_id=target["creator_note_id"],
        creator_note_status=note_status,
        notes=notes,
    )
    performance_result = performance_recorder(payload)
    return {
        "synced": True,
        "resolved_target": target,
        "creator_note_status": note_status,
        "performance_payload": payload,
        "performance_result": performance_result,
    }
