from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

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
