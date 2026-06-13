from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
import sqlite3

from app.run_queue import SQLiteRunQueue


def sample_runs(status_by_id: dict[str, str]):
    def _list_runs(limit: int) -> list[dict]:
        return [
            {
                "run_id": run_id,
                "status": status,
                "created_at": f"2026-06-10T10:00:0{index}",
            }
            for index, (run_id, status) in enumerate(status_by_id.items())
        ][:limit]

    return _list_runs


def test_sqlite_queue_enqueues_once_and_reports_status(tmp_path: Path) -> None:
    queue = SQLiteRunQueue(
        db_path=tmp_path / "queue.sqlite3",
        list_runs=sample_runs({"run_1": "queued"}),
    )

    queue.enqueue("run_1")
    queue.enqueue("run_1")

    status = queue.status()
    assert status["worker_backend"] == "sqlite"
    assert status["queued_count"] == 1
    assert status["queued_run_ids"] == ["run_1"]
    assert status["running_count"] == 0
    assert status["failed_count"] == 0


def test_sqlite_queue_claims_one_job_and_locks_it(tmp_path: Path) -> None:
    queue = SQLiteRunQueue(
        db_path=tmp_path / "queue.sqlite3",
        list_runs=sample_runs({"run_1": "queued", "run_2": "queued"}),
    )
    queue.enqueue("run_1")
    queue.enqueue("run_2")

    first = queue.claim_next("worker-a")
    second = queue.claim_next("worker-b")

    assert first == "run_1"
    assert second == "run_2"
    status = queue.status()
    assert status["queued_count"] == 0
    assert status["running_count"] == 2
    assert status["running_run_ids"] == ["run_1", "run_2"]


def test_sqlite_queue_claim_sets_initial_heartbeat(tmp_path: Path) -> None:
    queue = SQLiteRunQueue(
        db_path=tmp_path / "queue.sqlite3",
        list_runs=sample_runs({"run_1": "queued"}),
    )
    queue.enqueue("run_1")

    assert queue.claim_next("worker-a") == "run_1"

    status = queue.status()
    assert status["jobs"][0]["heartbeat_at"]


def test_sqlite_queue_locked_job_is_not_claimed_twice(tmp_path: Path) -> None:
    queue = SQLiteRunQueue(
        db_path=tmp_path / "queue.sqlite3",
        list_runs=sample_runs({"run_1": "queued"}),
    )
    queue.enqueue("run_1")

    assert queue.claim_next("worker-a") == "run_1"
    assert queue.claim_next("worker-b") is None


def test_sqlite_queue_mark_succeeded_removes_job_from_active_status(tmp_path: Path) -> None:
    queue = SQLiteRunQueue(
        db_path=tmp_path / "queue.sqlite3",
        list_runs=sample_runs({"run_1": "queued"}),
    )
    queue.enqueue("run_1")
    assert queue.claim_next("worker-a") == "run_1"

    queue.mark_succeeded("run_1", "worker-a")

    status = queue.status()
    assert status["queued_count"] == 0
    assert status["running_count"] == 0
    assert status["failed_count"] == 0


def test_sqlite_queue_mark_failed_requeues_before_max_attempts(tmp_path: Path) -> None:
    queue = SQLiteRunQueue(
        db_path=tmp_path / "queue.sqlite3",
        list_runs=sample_runs({"run_1": "queued"}),
        max_attempts=2,
    )
    queue.enqueue("run_1")
    assert queue.claim_next("worker-a") == "run_1"

    terminal = queue.mark_failed("run_1", "worker-a", "first failure")

    assert terminal is False
    status = queue.status()
    assert status["queued_run_ids"] == ["run_1"]
    assert status["failed_count"] == 0


def test_sqlite_queue_mark_failed_terminal_after_max_attempts(tmp_path: Path) -> None:
    queue = SQLiteRunQueue(
        db_path=tmp_path / "queue.sqlite3",
        list_runs=sample_runs({"run_1": "queued"}),
        max_attempts=1,
    )
    queue.enqueue("run_1")
    assert queue.claim_next("worker-a") == "run_1"

    terminal = queue.mark_failed("run_1", "worker-a", "terminal failure")

    assert terminal is True
    status = queue.status()
    assert status["queued_count"] == 0
    assert status["running_count"] == 0
    assert status["failed_count"] == 1
    assert status["failed_run_ids"] == ["run_1"]


def test_sqlite_queue_stale_running_job_can_be_reclaimed(tmp_path: Path) -> None:
    queue = SQLiteRunQueue(
        db_path=tmp_path / "queue.sqlite3",
        list_runs=sample_runs({"run_1": "running"}),
        lock_timeout_seconds=1,
        max_attempts=3,
    )
    queue.enqueue("run_1")
    assert queue.claim_next("worker-a") == "run_1"

    stale_locked_at = (datetime.now() - timedelta(seconds=5)).isoformat(timespec="seconds")
    with queue._connect() as connection:
        connection.execute(
            "UPDATE run_queue_jobs SET locked_at = ? WHERE run_id = ?",
            (stale_locked_at, "run_1"),
        )

    assert queue.claim_next("worker-b") == "run_1"


def _event_rows(db_path: Path, run_id: str) -> list[sqlite3.Row]:
    with sqlite3.connect(db_path) as connection:
        connection.row_factory = sqlite3.Row
        return connection.execute(
            "SELECT * FROM run_events WHERE run_id = ? ORDER BY created_at, event_type",
            (run_id,),
        ).fetchall()


def test_sqlite_queue_records_queue_events_when_enabled(tmp_path: Path) -> None:
    db_path = tmp_path / "queue.sqlite3"
    queue = SQLiteRunQueue(
        db_path=db_path,
        list_runs=sample_runs({"run_1": "queued"}),
        max_attempts=2,
        event_db_path=db_path,
    )

    queue.enqueue("run_1")
    assert queue.claim_next("worker-a") == "run_1"
    terminal = queue.mark_failed("run_1", "worker-a", "first failure")
    assert terminal is False
    assert queue.claim_next("worker-b") == "run_1"
    queue.mark_succeeded("run_1", "worker-b")

    event_types = [row["event_type"] for row in _event_rows(db_path, "run_1")]
    assert event_types == [
        "queue_enqueued",
        "queue_claimed",
        "queue_requeued",
        "queue_claimed",
        "queue_succeeded",
    ]


def test_sqlite_queue_records_stale_reclaim_event(tmp_path: Path) -> None:
    db_path = tmp_path / "queue.sqlite3"
    queue = SQLiteRunQueue(
        db_path=db_path,
        list_runs=sample_runs({"run_1": "running"}),
        lock_timeout_seconds=1,
        max_attempts=3,
        event_db_path=db_path,
    )
    queue.enqueue("run_1")
    assert queue.claim_next("worker-a") == "run_1"

    stale_locked_at = (datetime.now() - timedelta(seconds=5)).isoformat(timespec="seconds")
    with queue._connect() as connection:
        connection.execute(
            "UPDATE run_queue_jobs SET locked_at = ?, locked_by = ? WHERE run_id = ?",
            (stale_locked_at, "worker-a", "run_1"),
        )

    assert queue.claim_next("worker-b") == "run_1"

    event_types = [row["event_type"] for row in _event_rows(db_path, "run_1")]
    assert "queue_reclaimed" in event_types


def test_sqlite_queue_status_includes_job_details(tmp_path: Path) -> None:
    queue = SQLiteRunQueue(
        db_path=tmp_path / "queue.sqlite3",
        list_runs=sample_runs({"run_1": "queued"}),
        max_attempts=2,
    )
    queue.enqueue("run_1")
    assert queue.claim_next("worker-a") == "run_1"

    status = queue.status()

    assert status["jobs"] == [
        {
            "run_id": "run_1",
            "status": "running",
            "attempts": 1,
            "max_attempts": 2,
            "locked_by": "worker-a",
            "heartbeat_at": status["jobs"][0]["heartbeat_at"],
            "last_error": None,
        }
    ]


def test_sqlite_queue_heartbeat_updates_running_job_and_records_event(tmp_path: Path) -> None:
    db_path = tmp_path / "queue.sqlite3"
    queue = SQLiteRunQueue(
        db_path=db_path,
        list_runs=sample_runs({"run_1": "queued"}),
        event_db_path=db_path,
    )
    queue.enqueue("run_1")
    assert queue.claim_next("worker-a") == "run_1"

    changed = queue.heartbeat("run_1", "worker-a")

    assert changed is True
    status = queue.status()
    assert status["jobs"][0]["heartbeat_at"]
    event_types = [row["event_type"] for row in _event_rows(db_path, "run_1")]
    assert "queue_heartbeat" in event_types


def test_sqlite_queue_heartbeat_rejects_different_worker(tmp_path: Path) -> None:
    queue = SQLiteRunQueue(
        db_path=tmp_path / "queue.sqlite3",
        list_runs=sample_runs({"run_1": "queued"}),
    )
    queue.enqueue("run_1")
    assert queue.claim_next("worker-a") == "run_1"

    changed = queue.heartbeat("run_1", "worker-b")

    assert changed is False


def test_sqlite_queue_cancel_marks_job_and_records_event(tmp_path: Path) -> None:
    db_path = tmp_path / "queue.sqlite3"
    queue = SQLiteRunQueue(
        db_path=db_path,
        list_runs=sample_runs({"run_1": "queued"}),
        event_db_path=db_path,
    )
    queue.enqueue("run_1")

    changed = queue.cancel("run_1", worker_id="operator", reason="user cancelled")

    status = queue.status()
    assert changed is True
    assert status["cancelled_count"] == 1
    assert status["cancelled_run_ids"] == ["run_1"]
    assert status["jobs"][0]["status"] == "cancelled"
    assert status["jobs"][0]["last_error"] == "user cancelled"
    event_types = [row["event_type"] for row in _event_rows(db_path, "run_1")]
    assert event_types == ["queue_enqueued", "queue_cancelled"]


def test_sqlite_queue_mark_timed_out_marks_job_and_records_event(tmp_path: Path) -> None:
    db_path = tmp_path / "queue.sqlite3"
    queue = SQLiteRunQueue(
        db_path=db_path,
        list_runs=sample_runs({"run_1": "running"}),
        event_db_path=db_path,
    )
    queue.enqueue("run_1")
    assert queue.claim_next("worker-a") == "run_1"

    changed = queue.mark_timed_out("run_1", worker_id="watchdog", reason="run exceeded timeout")

    status = queue.status()
    assert changed is True
    assert status["timed_out_count"] == 1
    assert status["timed_out_run_ids"] == ["run_1"]
    assert status["jobs"][0]["status"] == "timed_out"
    assert status["jobs"][0]["last_error"] == "run exceeded timeout"
    event_types = [row["event_type"] for row in _event_rows(db_path, "run_1")]
    assert event_types == ["queue_enqueued", "queue_claimed", "queue_timed_out"]


def test_sqlite_queue_watchdog_marks_expired_heartbeat_timed_out(tmp_path: Path) -> None:
    db_path = tmp_path / "queue.sqlite3"
    queue = SQLiteRunQueue(
        db_path=db_path,
        list_runs=sample_runs({"run_1": "running"}),
        event_db_path=db_path,
    )
    queue.enqueue("run_1")
    assert queue.claim_next("worker-a") == "run_1"
    old_time = (datetime.now() - timedelta(seconds=120)).isoformat(timespec="seconds")
    with queue._connect() as connection:
        connection.execute(
            "UPDATE run_queue_jobs SET heartbeat_at = ? WHERE run_id = ?",
            (old_time, "run_1"),
        )

    timed_out = queue.mark_stale_running_as_timed_out(
        max_seconds=60,
        worker_id="watchdog",
        reason="watchdog heartbeat timeout",
    )

    assert timed_out == ["run_1"]
    status = queue.status()
    assert status["timed_out_run_ids"] == ["run_1"]


def test_sqlite_queue_watchdog_keeps_fresh_heartbeat_running(tmp_path: Path) -> None:
    queue = SQLiteRunQueue(
        db_path=tmp_path / "queue.sqlite3",
        list_runs=sample_runs({"run_1": "running"}),
    )
    queue.enqueue("run_1")
    assert queue.claim_next("worker-a") == "run_1"

    timed_out = queue.mark_stale_running_as_timed_out(max_seconds=60, worker_id="watchdog")

    assert timed_out == []
    assert queue.status()["running_run_ids"] == ["run_1"]
