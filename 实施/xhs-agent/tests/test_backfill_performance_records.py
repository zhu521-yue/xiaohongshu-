from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from app import api
from memory import operation_store
from scripts import backfill_performance_records as script


def _reset_services() -> None:
    api.RUN_STORE = None
    api.RUN_QUEUE_SERVICE = None
    operation_store.MEMORY_BACKEND = None


@pytest.fixture()
def sqlite_business_env(tmp_path: Path, monkeypatch) -> Path:
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


def _state(*, post_id: str = "output/backfill.md", creator_note_id: str = "note_backfill") -> dict:
    return {
        "post_id": post_id,
        "creator_note_id": creator_note_id,
        "publish_status": "success",
        "publish_time": "2026-06-13T10:00:00",
        "creator_publish_requested": True,
        "creator_publish_status": "success",
        "creator_publish_mode": "mock",
        "user_topic": "topic",
        "target_user": "target",
        "account_stage": "cold_start",
        "content_type": "step_tutorial",
        "content_format": "image_text",
        "titles": ["title"],
        "pain_points": [],
        "comment_insights": [],
        "performance_data": {},
        "performance_score": 0,
        "review_summary": "waiting",
        "next_action": "record performance",
        "review_generation": {"enabled": False, "provider_mode": "template"},
    }


def _run_from_record(record: dict, *, run_id: str = "run_backfill") -> dict:
    state = {
        **_state(post_id=record["post_id"], creator_note_id=record["creator_note_id"]),
        "operation_record_id": record["record_id"],
    }
    return {
        "run_id": run_id,
        "status": "success",
        "created_at": "2026-06-13T10:00:00",
        "updated_at": "2026-06-13T10:01:00",
        "started_at": "2026-06-13T10:00:00",
        "finished_at": "2026-06-13T10:01:00",
        "request": {"topic": "topic", "format": "image_text"},
        "summary": api._state_summary(state),
        "content": api._content_payload(state),
        "insights": api._insight_payload(state),
        "state": state,
        "paths": {"post_id": state["post_id"], "operation_memory_path": None, "collection_path": None},
        "error": None,
    }


def _record_historical_performance(record: dict, *, views: int = 100) -> dict:
    return operation_store.update_record_performance(
        post_id=record["post_id"],
        creator_note_id=record["creator_note_id"],
        performance_data={"views": views, "likes": 10, "collects": 5, "comments": 2, "follows": 1},
        notes="historical performance",
    )


def _performance_count(db_path: Path) -> int:
    with sqlite3.connect(db_path) as connection:
        row = connection.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type = 'table' AND name = 'performance_records'"
        ).fetchone()
        if int(row[0]) == 0:
            return 0
        count = connection.execute("SELECT COUNT(*) FROM performance_records").fetchone()
    return int(count[0])


def test_backfill_dry_run_reports_candidate_without_writing(sqlite_business_env: Path) -> None:
    record = operation_store.upsert_record_from_state(_state())
    api._save_run(_run_from_record(record))
    updated = _record_historical_performance(record, views=123)

    result = script.backfill_performance_records(dry_run=True)

    assert result["dry_run"] is True
    assert result["processed"] == [
        {
            "record_id": updated["record_id"],
            "post_id": updated["post_id"],
            "creator_note_id": updated["creator_note_id"],
            "dry_run": True,
        }
    ]
    assert result["skipped"] == []
    assert result["errors"] == []
    assert _performance_count(sqlite_business_env) == 0


def test_backfill_limit_zero_processes_no_candidates(sqlite_business_env: Path) -> None:
    record = operation_store.upsert_record_from_state(_state())
    api._save_run(_run_from_record(record))
    _record_historical_performance(record, views=123)

    result = script.backfill_performance_records(dry_run=True, limit=0)

    assert result["processed"] == []
    assert result["errors"] == []
    assert _performance_count(sqlite_business_env) == 0


def test_backfill_apply_updates_run_state_and_business_records(sqlite_business_env: Path) -> None:
    record = operation_store.upsert_record_from_state(_state())
    api._save_run(_run_from_record(record))
    updated = _record_historical_performance(record, views=456)

    result = script.backfill_performance_records(dry_run=False)

    assert result["errors"] == []
    assert result["skipped"] == []
    assert result["processed"][0]["record_id"] == updated["record_id"]
    assert result["processed"][0]["run_id"] == "run_backfill"
    assert result["processed"][0]["business_sync"]["status"] == "success"

    loaded = api._load_run("run_backfill")
    assert loaded is not None
    assert loaded["state"]["performance_data"]["views"] == 456
    assert loaded["summary"]["performance_score"] == updated["performance_score"]
    assert _performance_count(sqlite_business_env) == 1


def test_backfill_apply_skips_record_without_matching_success_run(sqlite_business_env: Path) -> None:
    record = operation_store.upsert_record_from_state(
        _state(post_id="output/orphan.md", creator_note_id="note_orphan")
    )
    updated = _record_historical_performance(record, views=88)

    result = script.backfill_performance_records(dry_run=False)

    assert result["processed"] == []
    assert result["errors"] == []
    assert result["skipped"] == [
        {
            "record_id": updated["record_id"],
            "reason": "matching success run not found",
            "business_sync": {"status": "skipped", "reason": "matching success run not found"},
        }
    ]
    assert _performance_count(sqlite_business_env) == 0


def test_backfill_apply_is_idempotent(sqlite_business_env: Path) -> None:
    record = operation_store.upsert_record_from_state(_state())
    api._save_run(_run_from_record(record))
    _record_historical_performance(record, views=321)

    first = script.backfill_performance_records(dry_run=False)
    second = script.backfill_performance_records(dry_run=False)

    assert first["processed"][0]["business_sync"]["status"] == "success"
    assert second["processed"][0]["business_sync"]["status"] == "success"
    assert _performance_count(sqlite_business_env) == 1
