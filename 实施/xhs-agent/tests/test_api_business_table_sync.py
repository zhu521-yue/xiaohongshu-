from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from app import api


def _reset_api_services() -> None:
    api.RUN_STORE = None
    api.RUN_QUEUE_SERVICE = None


@pytest.fixture()
def sqlite_api(tmp_path: Path, monkeypatch) -> Path:
    db_path = tmp_path / "xhs_agent.sqlite3"
    monkeypatch.setenv("XHS_AGENT_RUN_STORE", "sqlite")
    monkeypatch.setenv("XHS_AGENT_RUN_DB_PATH", str(db_path))
    monkeypatch.setenv("XHS_AGENT_RUN_QUEUE", "local")
    monkeypatch.setenv("XHS_AGENT_BUSINESS_TABLES_ENABLED", "true")
    _reset_api_services()
    yield db_path
    _reset_api_services()


def _business_record(run_id: str = "run_auto_sync", *, status: str = "success") -> dict:
    state = {
        "user_topic": "小红书新手选题方法",
        "raw_notes": [
            {
                "id": "note_auto_001",
                "title": "自动同步测试笔记",
                "note_url": "https://example.test/note/auto?xsec_token=secret",
                "likes": 9,
                "comments": 2,
            }
        ],
        "collection_candidates": [
            {
                "rank": 1,
                "selected": True,
                "original_index": 0,
                "title": "自动同步测试笔记",
                "score": 101,
            }
        ],
        "raw_comments": [{"source_note_title": "自动同步测试笔记", "content": "第一步怎么做？"}],
        "analysis_report": {
            "sample_selection": {"candidate_count": 1, "selected_count": 1},
            "comment_quality": {"raw_comments_count": 1, "quality_level": "low"},
            "pain_point_confidence": {"level": "low", "score": 20},
            "summary": "自动同步测试",
        },
    }
    return {
        "run_id": run_id,
        "status": status,
        "created_at": "2026-06-12T10:00:00",
        "updated_at": "2026-06-12T10:01:00",
        "started_at": "2026-06-12T10:00:00",
        "finished_at": "2026-06-12T10:01:00" if status == "success" else None,
        "request": {"topic": "小红书新手选题方法"},
        "summary": {},
        "content": {},
        "insights": {},
        "state": state if status == "success" else {},
        "paths": {},
        "error": None,
    }


def _count_rows(db_path: Path, table: str) -> int:
    with sqlite3.connect(db_path) as connection:
        return int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])


def _event_types(db_path: Path, run_id: str) -> list[str]:
    with sqlite3.connect(db_path) as connection:
        return [
            row[0]
            for row in connection.execute(
                "SELECT event_type FROM run_events WHERE run_id = ? ORDER BY created_at, event_type",
                (run_id,),
            ).fetchall()
        ]


def test_save_success_run_auto_syncs_business_tables(sqlite_api: Path) -> None:
    api._save_run(_business_record())

    loaded = api._load_run("run_auto_sync")

    assert loaded is not None
    assert loaded["summary"]["business_table_sync_status"] == "success"
    assert loaded["summary"]["business_table_sync_counts"] == {
        "raw_notes": 1,
        "collection_candidates": 1,
        "raw_comments": 1,
        "analysis_reports": 1,
        "drafts": 0,
        "creator_assets": 0,
        "creator_notes": 0,
        "performance_records": 0,
        "audit_events": 0,
    }
    assert _count_rows(sqlite_api, "raw_notes") == 1
    assert _count_rows(sqlite_api, "collection_candidates") == 1
    assert _count_rows(sqlite_api, "raw_comments") == 1
    assert _count_rows(sqlite_api, "analysis_reports") == 1


def test_save_non_success_run_does_not_auto_sync(sqlite_api: Path) -> None:
    api._save_run(_business_record("run_auto_sync_queued", status="queued"))

    assert _count_rows(sqlite_api, "raw_notes") == 0
    assert _event_types(sqlite_api, "run_auto_sync_queued") == ["queued"]


def test_disabled_business_table_sync_keeps_success_run_in_runs_only(
    tmp_path: Path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "xhs_agent.sqlite3"
    monkeypatch.setenv("XHS_AGENT_RUN_STORE", "sqlite")
    monkeypatch.setenv("XHS_AGENT_RUN_DB_PATH", str(db_path))
    monkeypatch.setenv("XHS_AGENT_RUN_QUEUE", "local")
    monkeypatch.setenv("XHS_AGENT_BUSINESS_TABLES_ENABLED", "false")
    _reset_api_services()

    api._save_run(_business_record("run_auto_sync_disabled"))

    loaded = api._load_run("run_auto_sync_disabled")
    with sqlite3.connect(db_path) as connection:
        names = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
        }
    assert loaded is not None
    assert "business_table_sync_status" not in loaded["summary"]
    assert "raw_notes" not in names
    _reset_api_services()


def test_business_table_sync_failure_does_not_block_run_save(
    sqlite_api: Path,
    monkeypatch,
) -> None:
    def fail_sync(*args, **kwargs):
        raise RuntimeError("cookie=secret should be hidden")

    monkeypatch.setattr(api, "sync_run_business_tables", fail_sync)

    api._save_run(_business_record("run_auto_sync_failure"))

    loaded = api._load_run("run_auto_sync_failure")
    assert loaded is not None
    assert loaded["status"] == "success"
    assert loaded["summary"]["business_table_sync_status"] == "failed"
    assert "secret" not in loaded["summary"]["business_table_sync_error"]


def test_get_business_run_snapshot_requires_sqlite_run_store(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("XHS_AGENT_RUN_STORE", "json")
    monkeypatch.setenv("XHS_AGENT_RUN_QUEUE", "local")
    _reset_api_services()

    with pytest.raises(ValueError, match="SQLite run store"):
        api.get_business_run_snapshot("run_json_store")

    _reset_api_services()


def test_get_business_run_snapshot_returns_auto_synced_tables(sqlite_api: Path) -> None:
    api._save_run(_business_record())

    result = api.get_business_run_snapshot("run_auto_sync")

    assert result["business_run"]["run_id"] == "run_auto_sync"
    assert result["business_run"]["counts"]["raw_notes"] == 1
    assert result["business_run"]["counts"]["collection_candidates"] == 1
    assert result["business_run"]["raw_notes"][0]["title"] == "自动同步测试笔记"


def test_save_run_records_lifecycle_events_when_business_tables_enabled(sqlite_api: Path) -> None:
    queued = _business_record("run_event_auto", status="queued")
    running = dict(queued, status="running", started_at="2026-06-12T10:00:30")
    success = _business_record("run_event_auto", status="success")

    api._save_run(queued)
    api._save_run(running)
    api._save_run(success)

    assert _event_types(sqlite_api, "run_event_auto") == ["queued", "running", "success"]
    snapshot = api.get_business_run_snapshot("run_event_auto")["business_run"]
    assert snapshot["counts"]["run_events"] == 3


def test_create_local_run_passes_event_context_to_local_graph(sqlite_api: Path, monkeypatch) -> None:
    captured: dict = {}

    def fake_local_graph(initial_state: dict, *, run_id: str, event_db_path: Path) -> dict:
        captured["initial_state"] = initial_state
        captured["run_id"] = run_id
        captured["event_db_path"] = event_db_path
        return {
            **initial_state,
            "content_format": "image_text",
            "content_type": "step_tutorial",
            "titles": ["本地事件上下文"],
            "body": "正文",
            "compliance_risk_level": "low",
        }

    monkeypatch.setattr(api, "run_local_graph", fake_local_graph)

    record = api.create_run(
        {
            "topic": "小红书新手选题方法",
            "engine": "local",
            "approve": False,
        }
    )

    assert captured["run_id"] == record["run_id"]
    assert captured["event_db_path"] == sqlite_api
    assert captured["initial_state"]["user_topic"] == "小红书新手选题方法"
