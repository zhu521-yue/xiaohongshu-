from __future__ import annotations

from pathlib import Path

from app import api
from app.run_store import LocalRunStore, SQLiteRunStore


def reset_api_store() -> None:
    api.RUN_STORE = None


def test_api_uses_local_run_store_by_default(monkeypatch) -> None:
    monkeypatch.delenv("XHS_AGENT_RUN_STORE", raising=False)
    monkeypatch.delenv("XHS_AGENT_RUN_DB_PATH", raising=False)
    reset_api_store()

    store = api._run_store()

    assert isinstance(store, LocalRunStore)
    reset_api_store()


def test_api_uses_sqlite_run_store_when_configured(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "runs.sqlite3"
    monkeypatch.setenv("XHS_AGENT_RUN_STORE", "sqlite")
    monkeypatch.setenv("XHS_AGENT_RUN_DB_PATH", str(db_path))
    reset_api_store()

    store = api._run_store()

    assert isinstance(store, SQLiteRunStore)
    record = {
        "run_id": "run_from_api_selection",
        "status": "queued",
        "created_at": "2026-06-10T10:00:00",
        "updated_at": "2026-06-10T10:00:00",
        "started_at": None,
        "finished_at": None,
        "request": {"topic": "小红书新手选题方法"},
        "summary": {},
        "content": {},
        "insights": {},
        "state": {},
        "paths": {},
        "error": None,
    }
    store.save(record)
    assert db_path.exists()
    assert store.load("run_from_api_selection") == record
    reset_api_store()
