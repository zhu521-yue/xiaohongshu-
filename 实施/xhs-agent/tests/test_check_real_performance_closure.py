from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from app import api
from memory import operation_store
from scripts import check_real_performance_closure as script


def _reset_services() -> None:
    api.RUN_STORE = None
    api.RUN_QUEUE_SERVICE = None
    operation_store.MEMORY_BACKEND = None


def _run_record(run_id: str, creator_note_id: str) -> dict:
    state = {
        "post_id": f"output/{run_id}.md",
        "creator_note_id": creator_note_id,
        "publish_status": "success",
        "publish_time": "2026-06-13T10:00:00",
        "creator_publish_requested": True,
        "creator_publish_status": "success",
        "creator_publish_mode": "spider_xhs",
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


def _write_run(runs_dir: Path, record: dict) -> None:
    runs_dir.mkdir(parents=True, exist_ok=True)
    (runs_dir / f"{record['run_id']}.json").write_text(
        json.dumps(record, ensure_ascii=False),
        encoding="utf-8",
    )


def _performance_count(db_path: Path) -> int:
    with sqlite3.connect(db_path) as connection:
        row = connection.execute("SELECT COUNT(*) FROM performance_records").fetchone()
    return int(row[0])


def test_real_performance_closure_check_imports_run_and_writes_business_record(
    tmp_path: Path,
    monkeypatch,
) -> None:
    run_id = "run_real_check"
    creator_note_id = "creator_note_real_check"
    db_path = tmp_path / "closure.sqlite3"
    runs_dir = tmp_path / "api_runs"
    _write_run(runs_dir, _run_record(run_id, creator_note_id))

    def fake_list_published_notes(limit: int = 20) -> dict:
        assert limit == 5
        return {
            "ok": True,
            "source": "creator_v2",
            "notes": [
                {
                    "note_id": creator_note_id,
                    "title": "title",
                    "metrics": {"views": 321, "likes": 12, "collects": 8, "comments": 3, "follows": 1},
                }
            ],
        }

    monkeypatch.setattr(script.creator_platform, "list_published_notes", fake_list_published_notes)
    _reset_services()

    result = script.run_real_performance_closure_check(
        run_id=run_id,
        creator_note_id=creator_note_id,
        db_path=db_path,
        runs_dir=runs_dir,
        limit=5,
        use_platform_metrics=True,
    )

    assert result["ok"] is True
    assert result["platform_note"]["found"] is True
    assert result["business_sync"]["status"] == "success"
    assert result["business_counts"]["performance_records"] == 1
    assert result["checks"]["memory_updated"] is True
    assert result["checks"]["run_state_synced"] is True
    assert result["checks"]["performance_record_written"] is True
    assert result["performance_record"]["views"] == 321
    assert _performance_count(db_path) == 1
    _reset_services()


def test_main_accepts_runs_dir_and_prints_json(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    run_id = "run_real_check_cli"
    creator_note_id = "creator_note_real_check_cli"
    db_path = tmp_path / "closure_cli.sqlite3"
    runs_dir = tmp_path / "api_runs"
    _write_run(runs_dir, _run_record(run_id, creator_note_id))

    def fake_list_published_notes(limit: int = 20) -> dict:
        return {
            "ok": True,
            "source": "creator_v2",
            "notes": [{"note_id": creator_note_id, "metrics": {"views": 99}}],
        }

    monkeypatch.setattr(script.creator_platform, "list_published_notes", fake_list_published_notes)
    _reset_services()

    exit_code = script.main(
        [
            "--run-id",
            run_id,
            "--creator-note-id",
            creator_note_id,
            "--db-path",
            str(db_path),
            "--runs-dir",
            str(runs_dir),
            "--use-platform-metrics",
        ]
    )
    data = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert data["ok"] is True
    assert data["performance_record"]["views"] == 99
    _reset_services()
