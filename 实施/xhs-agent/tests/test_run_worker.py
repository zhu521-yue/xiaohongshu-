from __future__ import annotations

import sqlite3
from pathlib import Path

from app.run_queue import SQLiteRunQueue
from scripts import run_worker


class FakeQueue:
    def __init__(self, run_id: str | None) -> None:
        self.run_id = run_id
        self.succeeded: list[tuple[str, str]] = []
        self.failed: list[tuple[str, str, str]] = []

    def claim_next(self, worker_id: str) -> str | None:
        run_id = self.run_id
        self.run_id = None
        return run_id

    def mark_succeeded(self, run_id: str, worker_id: str) -> None:
        self.succeeded.append((run_id, worker_id))

    def mark_failed(self, run_id: str, worker_id: str, error: str) -> bool:
        self.failed.append((run_id, worker_id, error))
        return True


class HeartbeatQueue(FakeQueue):
    def __init__(self, run_id: str | None) -> None:
        super().__init__(run_id)
        self.heartbeats: list[tuple[str, str]] = []

    def heartbeat(self, run_id: str, worker_id: str) -> bool:
        self.heartbeats.append((run_id, worker_id))
        return True


def test_run_worker_once_marks_success(monkeypatch) -> None:
    queue = FakeQueue("run_1")
    records = {"run_1": {"status": "success", "error": None}}

    def execute_run(run_id: str) -> None:
        records[run_id]["executed"] = True

    def load_run(run_id: str) -> dict:
        return records[run_id]

    did_work = run_worker.run_once(
        queue=queue,
        worker_id="worker-a",
        execute_run=execute_run,
        load_run=load_run,
    )

    assert did_work is True
    assert records["run_1"]["executed"] is True
    assert queue.succeeded == [("run_1", "worker-a")]
    assert queue.failed == []


def test_run_once_records_heartbeat_after_claim() -> None:
    queue = HeartbeatQueue("run_1")
    records = {"run_1": {"status": "success", "error": None}}

    did_work = run_worker.run_once(
        queue=queue,
        worker_id="worker-a",
        execute_run=lambda run_id: None,
        load_run=lambda run_id: records[run_id],
    )

    assert did_work is True
    assert queue.heartbeats == [("run_1", "worker-a")]


def test_run_worker_once_marks_failed_run_status(monkeypatch) -> None:
    queue = FakeQueue("run_1")
    records = {"run_1": {"status": "failed", "error": "graph failed"}}

    did_work = run_worker.run_once(
        queue=queue,
        worker_id="worker-a",
        execute_run=lambda run_id: None,
        load_run=lambda run_id: records[run_id],
    )

    assert did_work is True
    assert queue.succeeded == []
    assert queue.failed == [("run_1", "worker-a", "graph failed")]


def test_run_worker_once_returns_false_when_no_job() -> None:
    queue = FakeQueue(None)

    did_work = run_worker.run_once(
        queue=queue,
        worker_id="worker-a",
        execute_run=lambda run_id: None,
        load_run=lambda run_id: {},
    )

    assert did_work is False
    assert queue.succeeded == []
    assert queue.failed == []


class FakeLogger:
    def __init__(self) -> None:
        self.messages: list[tuple[str, str]] = []

    def info(self, message: str, *args) -> None:
        self.messages.append(("info", message % args if args else message))

    def warning(self, message: str, *args) -> None:
        self.messages.append(("warning", message % args if args else message))


def test_run_worker_once_logs_claim_and_success() -> None:
    queue = FakeQueue("run_1")
    logger = FakeLogger()
    records = {"run_1": {"status": "success", "error": None}}

    did_work = run_worker.run_once(
        queue=queue,
        worker_id="worker-a",
        execute_run=lambda run_id: None,
        load_run=lambda run_id: records[run_id],
        logger=logger,
    )

    assert did_work is True
    assert ("info", "worker_claimed run_id=run_1 worker_id=worker-a") in logger.messages
    assert ("info", "worker_succeeded run_id=run_1 worker_id=worker-a") in logger.messages


def test_run_worker_once_logs_failure() -> None:
    queue = FakeQueue("run_1")
    logger = FakeLogger()
    records = {"run_1": {"status": "failed", "error": "graph failed"}}

    did_work = run_worker.run_once(
        queue=queue,
        worker_id="worker-a",
        execute_run=lambda run_id: None,
        load_run=lambda run_id: records[run_id],
        logger=logger,
    )

    assert did_work is True
    assert ("warning", "worker_failed run_id=run_1 worker_id=worker-a error=graph failed") in logger.messages


def test_run_worker_once_records_queue_success_events(tmp_path: Path) -> None:
    db_path = tmp_path / "xhs_agent.sqlite3"
    queue = SQLiteRunQueue(
        db_path=db_path,
        list_runs=lambda limit: [{"run_id": "run_worker_event", "status": "queued"}],
        event_db_path=db_path,
    )
    queue.enqueue("run_worker_event")

    did_work = run_worker.run_once(
        queue=queue,
        worker_id="worker-a",
        execute_run=lambda run_id: None,
        load_run=lambda run_id: {"status": "success", "error": None},
    )

    with sqlite3.connect(db_path) as connection:
        event_types = [
            row[0]
            for row in connection.execute(
                "SELECT event_type FROM run_events WHERE run_id = ? ORDER BY created_at, event_type",
                ("run_worker_event",),
            ).fetchall()
    ]

    assert did_work is True
    assert event_types == [
        "queue_enqueued",
        "queue_claimed",
        "queue_heartbeat",
        "queue_succeeded",
    ]


def test_run_watchdog_once_marks_stale_jobs() -> None:
    class WatchdogQueue(FakeQueue):
        def __init__(self) -> None:
            super().__init__(None)
            self.watchdog_kwargs: dict | None = None

        def mark_stale_running_as_timed_out(self, **kwargs):
            self.watchdog_kwargs = kwargs
            return ["run_1"]

    queue = WatchdogQueue()

    timed_out = run_worker.run_watchdog_once(queue, max_seconds=60, worker_id="watchdog")

    assert timed_out == ["run_1"]
    assert queue.watchdog_kwargs is not None
    assert queue.watchdog_kwargs["max_seconds"] == 60
    assert queue.watchdog_kwargs["worker_id"] == "watchdog"
