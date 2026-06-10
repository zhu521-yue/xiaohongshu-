from __future__ import annotations

from pathlib import Path

from app import api
from memory import operation_store
from scripts import run_worker


def reset_api_services() -> None:
    api.RUN_STORE = None
    api.RUN_QUEUE_SERVICE = None
    operation_store.MEMORY_BACKEND = None


def test_sqlite_queue_worker_processes_submitted_mock_run(
    tmp_path: Path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "xhs_agent.sqlite3"
    monkeypatch.setenv("XHS_AGENT_RUN_STORE", "sqlite")
    monkeypatch.setenv("XHS_AGENT_RUN_DB_PATH", str(db_path))
    monkeypatch.setenv("XHS_AGENT_RUN_QUEUE", "sqlite")
    monkeypatch.setenv("XHS_AGENT_QUEUE_DB_PATH", str(db_path))
    monkeypatch.setenv("XHS_AGENT_MEMORY_STORE", "sqlite")
    monkeypatch.setenv("XHS_AGENT_MEMORY_DB_PATH", str(db_path))
    monkeypatch.setenv("COLLECTOR_MODE", "mock")
    monkeypatch.setenv("LLM_MODEL_NAME", "mock")
    reset_api_services()

    submitted = api.submit_run(
        {
            "topic": "小红书新手选题方法",
            "target_user": "内容创作新手",
            "format": "image_text",
            "engine": "local",
            "approve": False,
            "collect_limit": 3,
        }
    )

    assert submitted["status"] == "queued"
    assert api.queue_status()["queued_run_ids"] == [submitted["run_id"]]

    did_work = run_worker.run_once(
        queue=api._run_queue_service(),
        worker_id="test-worker",
    )

    loaded = api._load_run(submitted["run_id"])
    assert did_work is True
    assert loaded is not None
    assert loaded["status"] == "success"
    assert api.queue_status()["queued_count"] == 0
    assert api.queue_status()["running_count"] == 0
    reset_api_services()
