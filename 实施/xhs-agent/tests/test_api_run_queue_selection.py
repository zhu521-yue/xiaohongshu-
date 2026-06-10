from __future__ import annotations

from pathlib import Path

from app import api
from app.run_queue import LocalRunQueue, SQLiteRunQueue


def reset_api_queue() -> None:
    api.RUN_QUEUE_SERVICE = None


def test_api_uses_local_run_queue_by_default(monkeypatch) -> None:
    monkeypatch.delenv("XHS_AGENT_RUN_QUEUE", raising=False)
    monkeypatch.delenv("XHS_AGENT_QUEUE_DB_PATH", raising=False)
    reset_api_queue()

    queue = api._run_queue_service()

    assert isinstance(queue, LocalRunQueue)
    reset_api_queue()


def test_api_uses_sqlite_run_queue_when_configured(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "queue.sqlite3"
    monkeypatch.setenv("XHS_AGENT_RUN_QUEUE", "sqlite")
    monkeypatch.setenv("XHS_AGENT_QUEUE_DB_PATH", str(db_path))
    monkeypatch.setenv("XHS_AGENT_QUEUE_MAX_ATTEMPTS", "4")
    monkeypatch.setenv("XHS_AGENT_QUEUE_LOCK_TIMEOUT_SECONDS", "7")
    reset_api_queue()

    queue = api._run_queue_service()

    assert isinstance(queue, SQLiteRunQueue)
    queue.enqueue("run_api_queue_selection")
    assert db_path.exists()
    assert queue.status()["queued_run_ids"] == ["run_api_queue_selection"]
    reset_api_queue()
