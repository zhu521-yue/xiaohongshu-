from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from app import api
from app.run_store import LocalRunStore, SQLiteRunStore
from memory import operation_store
from nodes import publish_node


def _reset_services() -> None:
    api.RUN_STORE = None
    api.RUN_QUEUE_SERVICE = None
    operation_store.MEMORY_BACKEND = None


@pytest.fixture()
def isolated_api(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("XHS_AGENT_RUN_STORE", "json")
    monkeypatch.setenv("XHS_AGENT_RUN_QUEUE", "local")
    monkeypatch.setenv("XHS_AGENT_MEMORY_STORE", "json")
    monkeypatch.setenv("CREATOR_MODE", "mock")
    monkeypatch.setenv("LLM_MODEL_NAME", "mock")
    monkeypatch.setattr(api, "RUN_STORE", LocalRunStore(tmp_path / "runs", json_default=api._json_default))
    monkeypatch.setattr(api, "RUNS_DIR", tmp_path / "runs")
    monkeypatch.setattr(
        operation_store,
        "MEMORY_BACKEND",
        operation_store.JsonOperationMemoryBackend(tmp_path / "operation_history.json"),
    )
    monkeypatch.setattr(publish_node, "OUTPUT_DIR", tmp_path / "markdown_exports")
    yield tmp_path
    _reset_services()


@pytest.fixture()
def sqlite_business_api(tmp_path: Path, monkeypatch) -> Path:
    db_path = tmp_path / "xhs_agent.sqlite3"
    monkeypatch.setenv("XHS_AGENT_RUN_STORE", "sqlite")
    monkeypatch.setenv("XHS_AGENT_RUN_DB_PATH", str(db_path))
    monkeypatch.setenv("XHS_AGENT_RUN_QUEUE", "local")
    monkeypatch.setenv("XHS_AGENT_MEMORY_STORE", "sqlite")
    monkeypatch.setenv("XHS_AGENT_MEMORY_DB_PATH", str(db_path))
    monkeypatch.setenv("XHS_AGENT_DB_SCHEMA", "foundation")
    monkeypatch.setenv("XHS_AGENT_BUSINESS_TABLES_ENABLED", "true")
    monkeypatch.setenv("CREATOR_MODE", "mock")
    monkeypatch.setenv("LLM_MODEL_NAME", "mock")
    _reset_services()
    yield db_path
    _reset_services()


def _operation_state(*, post_id: str = "output/post.md", creator_note_id: str = "mock_note_001") -> dict:
    return {
        "post_id": post_id,
        "publish_status": "success",
        "publish_time": "2026-06-11T10:00:00",
        "creator_publish_requested": True,
        "creator_publish_status": "success",
        "creator_publish_mode": "mock",
        "creator_note_id": creator_note_id,
        "user_topic": "小红书新手选题方法",
        "target_user": "内容创作新手",
        "account_stage": "cold_start",
        "content_type": "step_tutorial",
        "content_format": "image_text",
        "titles": ["选题三步法"],
        "collection_path": None,
        "pain_points": [{"pain": "不知道怎么选题", "evidence": "不会选题", "priority": 1}],
        "comment_insights": [],
        "performance_data": {},
        "review_summary": "草稿已生成。",
        "next_action": "发布后录入表现数据。",
        "review_generation": {"enabled": False, "provider_mode": "template"},
    }


def _successful_run_from_operation(record: dict, *, run_id: str = "run_perf_sync") -> dict:
    state = {
        **_operation_state(
            post_id=record.get("post_id") or "output/post.md",
            creator_note_id=record.get("creator_note_id") or "mock_note_001",
        ),
        "operation_record_id": record["record_id"],
        "operation_memory_written": True,
        "performance_data": {},
        "performance_score": 0,
        "review_summary": "发布后等待表现。",
        "next_action": "录入表现后复盘。",
    }
    return {
        "run_id": run_id,
        "status": "success",
        "created_at": "2026-06-13T10:00:00",
        "updated_at": "2026-06-13T10:01:00",
        "started_at": "2026-06-13T10:00:00",
        "finished_at": "2026-06-13T10:01:00",
        "request": {"topic": state["user_topic"], "format": "image_text"},
        "summary": api._state_summary(state),
        "content": api._content_payload(state),
        "insights": api._insight_payload(state),
        "state": state,
        "paths": {"post_id": state["post_id"], "operation_memory_path": None, "collection_path": None},
        "error": None,
    }


def _performance_rows(db_path: Path) -> list[sqlite3.Row]:
    with sqlite3.connect(db_path) as connection:
        connection.row_factory = sqlite3.Row
        table_exists = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'performance_records'"
        ).fetchone()
        if table_exists is None:
            return []
        return connection.execute("SELECT * FROM performance_records").fetchall()


def test_list_creator_notes_returns_adapter_result(isolated_api, monkeypatch) -> None:
    expected = {
        "ok": True,
        "mode": "mock",
        "platform": "xhs_creator",
        "notes": [{"note_id": "mock_note_001", "title": "Mock note", "visibility": "private"}],
    }

    def fake_list_published_notes(limit: int = 20) -> dict:
        assert limit == 5
        return expected

    monkeypatch.setattr(api.creator_platform, "list_published_notes", fake_list_published_notes)

    result = api.list_creator_notes(limit=5)

    assert result == {"creator_notes": expected}


def test_get_creator_note_status_returns_adapter_result(isolated_api, monkeypatch) -> None:
    expected = {
        "ok": True,
        "status": "synced",
        "creator_note_id": "mock_note_001",
        "visibility_label": "仅自己可见",
    }

    def fake_status(creator_note_id: str, limit: int = 50) -> dict:
        assert creator_note_id == "mock_note_001"
        assert limit == 50
        return expected

    monkeypatch.setattr(api.creator_platform, "get_published_note_status", fake_status)

    result = api.get_creator_note_status("mock_note_001")

    assert result == {"creator_note_status": expected}


def test_get_creator_note_status_can_wait_for_platform_sync(isolated_api, monkeypatch) -> None:
    expected = {
        "ok": True,
        "status": "synced",
        "creator_note_id": "mock_note_001",
        "attempts": 2,
        "waited_seconds": 1.0,
    }

    def fake_wait_status(
        creator_note_id: str,
        limit: int = 50,
        attempts: int = 5,
        interval_seconds: float = 2.0,
    ) -> dict:
        assert creator_note_id == "mock_note_001"
        assert limit == 30
        assert attempts == 4
        assert interval_seconds == 0.5
        return expected

    monkeypatch.setattr(api.creator_platform, "wait_for_published_note_status", fake_wait_status)

    result = api.get_creator_note_status(
        "mock_note_001",
        limit=30,
        wait=True,
        attempts=4,
        interval_seconds=0.5,
    )

    assert result == {"creator_note_status": expected}


def test_record_performance_can_match_creator_note_id(isolated_api) -> None:
    saved = operation_store.upsert_record_from_state(_operation_state())

    result = api.record_performance(
        {
            "creator_note_id": "mock_note_001",
            "views": 1000,
            "likes": 50,
            "collects": 20,
            "comments": 8,
            "follows": 3,
        }
    )

    updated = result["updated_record"]
    assert updated["record_id"] == saved["record_id"]
    assert updated["creator_note_id"] == "mock_note_001"
    assert updated["status"] == "performance_recorded"
    assert updated["performance_score"] > 0
    assert updated["performance_data"]["views"] == 1000
    assert result["business_sync"]["status"] == "skipped"
    assert result["business_sync"]["reason"] == "business tables require sqlite run store"


def test_record_performance_syncs_sqlite_run_and_business_table(sqlite_business_api: Path) -> None:
    saved = operation_store.upsert_record_from_state(_operation_state())
    api._save_run(_successful_run_from_operation(saved))

    result = api.record_performance(
        {
            "creator_note_id": "mock_note_001",
            "views": 1000,
            "likes": 50,
            "collects": 20,
            "comments": 8,
            "follows": 3,
            "notes": "首轮表现复盘",
        }
    )

    assert result["business_sync"]["status"] == "success"
    assert result["business_sync"]["run_id"] == "run_perf_sync"
    assert result["business_sync"]["counts"]["performance_records"] == 1

    loaded = api._load_run("run_perf_sync")
    assert loaded is not None
    assert loaded["state"]["performance_data"]["views"] == 1000
    assert loaded["state"]["performance_score"] == result["updated_record"]["performance_score"]
    assert loaded["summary"]["performance_score"] == result["updated_record"]["performance_score"]
    assert loaded["summary"]["business_table_sync_status"] == "success"

    rows = _performance_rows(sqlite_business_api)
    assert len(rows) == 1
    assert rows[0]["operation_record_id"] == saved["record_id"]
    assert rows[0]["creator_note_id"] == "mock_note_001"
    assert rows[0]["views"] == 1000
    assert rows[0]["likes"] == 50
    assert rows[0]["collects"] == 20
    assert rows[0]["comments"] == 8
    assert rows[0]["follows"] == 3


def test_record_performance_keeps_memory_update_when_no_matching_sqlite_run(
    sqlite_business_api: Path,
) -> None:
    operation_store.upsert_record_from_state(_operation_state(creator_note_id="orphan_note_001"))

    result = api.record_performance({"creator_note_id": "orphan_note_001", "views": 12})

    assert result["updated_record"]["status"] == "performance_recorded"
    assert result["business_sync"]["status"] == "skipped"
    assert result["business_sync"]["reason"] == "matching success run not found"
    assert _performance_rows(sqlite_business_api) == []


def test_record_performance_business_sync_failure_is_sanitized(
    sqlite_business_api: Path,
    monkeypatch,
) -> None:
    saved = operation_store.upsert_record_from_state(_operation_state())
    api._save_run(_successful_run_from_operation(saved, run_id="run_perf_sync_failure"))

    def fail_save(record: dict) -> None:
        raise RuntimeError("cookie=secret-token should not leak")

    monkeypatch.setattr(api, "_save_run", fail_save)

    result = api.record_performance({"creator_note_id": "mock_note_001", "views": 100})

    assert result["updated_record"]["status"] == "performance_recorded"
    assert result["business_sync"]["status"] == "failed"
    assert "secret-token" not in result["business_sync"]["reason"]
    assert "cookie=[REDACTED]" in result["business_sync"]["reason"]


def test_record_performance_requires_post_id_or_creator_note_id(isolated_api) -> None:
    with pytest.raises(ValueError, match="post_id or creator_note_id"):
        api.record_performance({"views": 1})
