from __future__ import annotations

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
