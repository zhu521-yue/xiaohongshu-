from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from app import api


@pytest.fixture()
def sqlite_api(tmp_path: Path, monkeypatch):
    db_path = tmp_path / "xhs_agent.sqlite3"
    monkeypatch.setenv("XHS_AGENT_RUN_STORE", "sqlite")
    monkeypatch.setenv("XHS_AGENT_RUN_QUEUE", "sqlite")
    monkeypatch.setenv("XHS_AGENT_RUN_DB_PATH", str(db_path))
    monkeypatch.setenv("XHS_AGENT_QUEUE_DB_PATH", str(db_path))
    monkeypatch.setenv("XHS_AGENT_DB_SCHEMA", "foundation")
    monkeypatch.setenv("XHS_AGENT_BUSINESS_TABLES_ENABLED", "true")
    api.RUN_STORE = None
    api.RUN_QUEUE_SERVICE = None
    yield db_path
    api.RUN_STORE = None
    api.RUN_QUEUE_SERVICE = None


def _event_types(db_path: Path, run_id: str) -> list[str]:
    with sqlite3.connect(db_path) as connection:
        return [
            row[0]
            for row in connection.execute(
                "SELECT event_type FROM run_events WHERE run_id = ? ORDER BY created_at, event_type",
                (run_id,),
            ).fetchall()
        ]


def _submit_queued_run() -> dict:
    return api.submit_run(
        {
            "topic": "小红书新手选题方法",
            "target_user": "内容创作新手",
            "format": "image_text",
            "engine": "local",
            "collect_limit": 1,
        }
    )


def test_cancel_run_marks_run_and_queue(sqlite_api: Path) -> None:
    record = _submit_queued_run()

    cancelled = api.cancel_run(record["run_id"], {"reason": "user cancelled"})

    assert cancelled["status"] == "cancelled"
    assert cancelled["error"] == "user cancelled"
    queue = api.queue_status()
    assert queue["cancelled_run_ids"] == [record["run_id"]]
    assert "queue_cancelled" in _event_types(sqlite_api, record["run_id"])
    assert "cancelled" in _event_types(sqlite_api, record["run_id"])


def test_timeout_run_marks_run_and_queue(sqlite_api: Path) -> None:
    record = _submit_queued_run()
    queue = api._run_queue_service()
    assert queue.claim_next("worker-a") == record["run_id"]

    timed_out = api.timeout_run(record["run_id"], {"reason": "manual timeout"})

    assert timed_out["status"] == "timed_out"
    assert timed_out["error"] == "manual timeout"
    queue_status = api.queue_status()
    assert queue_status["timed_out_run_ids"] == [record["run_id"]]
    assert "queue_timed_out" in _event_types(sqlite_api, record["run_id"])
    assert "timed_out" in _event_types(sqlite_api, record["run_id"])


def test_cancel_run_rejects_completed_run(sqlite_api: Path) -> None:
    record = _submit_queued_run()
    api._finish_run(record, status="success", state={"user_topic": "完成任务"})

    with pytest.raises(ValueError, match="cannot control completed run"):
        api.cancel_run(record["run_id"], {"reason": "too late"})
