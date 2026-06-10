from __future__ import annotations

from pathlib import Path

import pytest

from app.run_store import LocalRunStore, SQLiteRunStore


def sample_record(run_id: str, created_at: str, status: str = "queued") -> dict:
    return {
        "run_id": run_id,
        "status": status,
        "created_at": created_at,
        "updated_at": created_at,
        "started_at": None,
        "finished_at": None,
        "request": {
            "topic": f"topic-{run_id}",
            "target_user": "内容创作新手",
            "format": "image_text",
            "engine": "langgraph",
        },
        "summary": {
            "content_format": "image_text",
            "content_type": "step_tutorial",
            "pain_points_count": 1,
        },
        "content": {
            "titles": ["标题A", "标题B"],
            "body": "正文",
            "tags": ["小红书", "选题"],
        },
        "insights": {
            "pain_points": [{"pain": "不知道怎么开始", "priority": 1}],
            "comment_fetch_errors": [],
        },
        "state": {
            "user_topic": "小红书新手选题方法",
            "human_approved": False,
        },
        "paths": {
            "post_id": None,
            "collection_path": None,
            "operation_memory_path": None,
        },
        "error": None,
        "approved_at": "2026-06-10T12:00:00",
        "reviewed_at": "2026-06-10T12:01:00",
        "review_action": "approved",
    }


def test_sqlite_run_store_saves_and_loads_complex_record(tmp_path: Path) -> None:
    store = SQLiteRunStore(tmp_path / "runs.sqlite3")
    record = sample_record("run_001", "2026-06-10T10:00:00", status="success")

    store.save(record)

    loaded = store.load("run_001")
    assert loaded == record


def test_sqlite_run_store_overwrites_existing_run(tmp_path: Path) -> None:
    store = SQLiteRunStore(tmp_path / "runs.sqlite3")
    first = sample_record("run_001", "2026-06-10T10:00:00", status="queued")
    second = sample_record("run_001", "2026-06-10T10:00:00", status="success")
    second["summary"]["operation_memory_written"] = True

    store.save(first)
    store.save(second)

    loaded = store.load("run_001")
    assert loaded == second


def test_sqlite_run_store_lists_recent_runs_by_created_at_desc(tmp_path: Path) -> None:
    store = SQLiteRunStore(tmp_path / "runs.sqlite3")
    store.save(sample_record("run_old", "2026-06-10T09:00:00"))
    store.save(sample_record("run_new", "2026-06-10T11:00:00"))
    store.save(sample_record("run_mid", "2026-06-10T10:00:00"))

    records = store.list(limit=2)

    assert [record["run_id"] for record in records] == ["run_new", "run_mid"]


def test_sqlite_run_store_missing_run_returns_none(tmp_path: Path) -> None:
    store = SQLiteRunStore(tmp_path / "runs.sqlite3")

    assert store.load("run_missing") is None


def test_sqlite_run_store_rejects_missing_run_id(tmp_path: Path) -> None:
    store = SQLiteRunStore(tmp_path / "runs.sqlite3")
    record = sample_record("run_001", "2026-06-10T10:00:00")
    record["run_id"] = ""

    with pytest.raises(ValueError, match="run record missing run_id"):
        store.save(record)


def test_local_run_store_still_saves_loads_and_overwrites(tmp_path: Path) -> None:
    store = LocalRunStore(tmp_path / "api_runs")
    first = sample_record("run_001", "2026-06-10T10:00:00", status="queued")
    second = sample_record("run_001", "2026-06-10T10:00:00", status="success")

    store.save(first)
    store.save(second)

    assert store.load("run_001") == second
