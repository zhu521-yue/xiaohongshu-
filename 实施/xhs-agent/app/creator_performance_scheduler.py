"""Long-running scheduler for creator note performance sync.

The scheduler stays separate from the sync service: it handles rounds,
sleeping, failure limits, and summaries, while each round delegates to
the existing batch sync entry point.
"""

from __future__ import annotations

from typing import Any, Callable


SyncRunner = Callable[..., dict[str, Any]]
Sleep = Callable[[float], None]


def _clean_targets(targets: list[dict[str, Any]]) -> list[dict[str, str]]:
    clean_targets: list[dict[str, str]] = []
    for target in targets:
        if not isinstance(target, dict):
            continue
        creator_note_id = str(target.get("creator_note_id") or "").strip()
        run_id = str(target.get("run_id") or "").strip()
        if creator_note_id:
            clean_targets.append({"creator_note_id": creator_note_id})
        elif run_id:
            clean_targets.append({"run_id": run_id})
    if not clean_targets:
        raise ValueError("Missing required targets")
    return clean_targets


def _as_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _as_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _round_from_result(round_index: int, result: dict[str, Any]) -> dict[str, Any]:
    if result.get("synced") is True:
        total = 1
        succeeded = 1
        failed = 0
    else:
        total = max(0, _as_int(result.get("total"), 0))
        succeeded = max(0, _as_int(result.get("succeeded"), 0))
        failed = max(0, _as_int(result.get("failed"), 0))
    return {
        "round_index": round_index,
        "ok": failed == 0,
        "total": total,
        "succeeded": succeeded,
        "failed": failed,
        "result": result,
    }


def _failed_round(round_index: int, target_count: int, error: Exception) -> dict[str, Any]:
    return {
        "round_index": round_index,
        "ok": False,
        "total": target_count,
        "succeeded": 0,
        "failed": target_count,
        "error": str(error),
    }


def run_creator_performance_sync_schedule(
    *,
    targets: list[dict[str, Any]],
    sync_runner: SyncRunner,
    sleep: Sleep,
    schedule_interval_seconds: float = 1800.0,
    max_rounds: int | None = None,
    max_consecutive_failed_rounds: int = 3,
    limit: int = 50,
    wait: bool = False,
    attempts: int = 5,
    status_interval_seconds: float = 2.0,
    notes: str | None = None,
) -> dict[str, Any]:
    clean_targets = _clean_targets(targets)
    round_limit = None if max_rounds is None else max(1, _as_int(max_rounds, 1))
    failure_limit = max(1, _as_int(max_consecutive_failed_rounds, 3))
    schedule_interval = max(0.0, _as_float(schedule_interval_seconds, 1800.0))

    rounds: list[dict[str, Any]] = []
    total_succeeded = 0
    total_failed = 0
    consecutive_failed_rounds = 0
    stopped_reason = ""

    round_index = 0
    while round_limit is None or round_index < round_limit:
        round_index += 1
        try:
            result = sync_runner(
                targets=clean_targets,
                limit=max(0, _as_int(limit, 50)),
                wait=bool(wait),
                attempts=max(1, _as_int(attempts, 5)),
                interval_seconds=max(0.0, _as_float(status_interval_seconds, 2.0)),
                notes=notes,
            )
            round_summary = _round_from_result(round_index, result)
        except Exception as exc:
            round_summary = _failed_round(round_index, len(clean_targets), exc)

        rounds.append(round_summary)
        total_succeeded += _as_int(round_summary.get("succeeded"), 0)
        total_failed += _as_int(round_summary.get("failed"), 0)
        if round_summary.get("ok") is True:
            consecutive_failed_rounds = 0
        else:
            consecutive_failed_rounds += 1

        if consecutive_failed_rounds >= failure_limit:
            stopped_reason = "failure_limit"
            break
        if round_limit is not None and round_index >= round_limit:
            stopped_reason = "max_rounds"
            break

        sleep(schedule_interval)

    return {
        "ok": total_failed == 0,
        "targets": clean_targets,
        "completed_rounds": len(rounds),
        "total_succeeded": total_succeeded,
        "total_failed": total_failed,
        "consecutive_failed_rounds": consecutive_failed_rounds,
        "stopped_reason": stopped_reason or "stopped",
        "rounds": rounds,
    }
