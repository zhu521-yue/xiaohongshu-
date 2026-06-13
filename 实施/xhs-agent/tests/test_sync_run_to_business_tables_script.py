from __future__ import annotations

import sqlite3
from pathlib import Path

from app.run_store import SQLiteRunStore
from scripts import sync_run_to_business_tables as script


def _record(run_id: str, *, status: str = "success") -> dict:
    state = {
        "user_topic": "小红书新手选题方法",
        "raw_notes": [{"id": f"note_{run_id}", "title": "补偿同步笔记"}],
        "collection_candidates": [{"rank": 1, "selected": True, "original_index": 0, "title": "补偿同步笔记"}],
        "raw_comments": [{"source_note_title": "补偿同步笔记", "content": "怎么补偿同步？"}],
        "analysis_report": {"summary": "补偿同步测试"},
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


def test_parser_accepts_run_id_limit_and_dry_run() -> None:
    args = script.build_parser().parse_args(["--run-id", "run_1", "--limit", "3", "--dry-run"])

    assert args.run_id == "run_1"
    assert args.limit == 3
    assert args.dry_run is True


def test_sync_runs_writes_success_records_and_skips_others(tmp_path: Path) -> None:
    db_path = tmp_path / "xhs_agent.sqlite3"

    summary = script.sync_runs(db_path, [_record("run_script_ok"), _record("run_script_skip", status="failed")])

    assert summary["synced"] == [{"run_id": "run_script_ok", "counts": {
        "raw_notes": 1,
        "collection_candidates": 1,
        "raw_comments": 1,
        "analysis_reports": 1,
        "drafts": 0,
        "creator_assets": 0,
        "creator_notes": 0,
        "performance_records": 0,
        "audit_events": 0,
    }}]
    assert summary["skipped"] == [{"run_id": "run_script_skip", "reason": "status is failed"}]
    assert summary["errors"] == []
    assert _count_rows(db_path, "raw_notes") == 1


def test_main_dry_run_does_not_write_business_rows(tmp_path: Path, monkeypatch, capsys) -> None:
    db_path = tmp_path / "xhs_agent.sqlite3"
    SQLiteRunStore(db_path).save(_record("run_script_dry"))
    monkeypatch.setenv("XHS_AGENT_RUN_STORE", "sqlite")
    monkeypatch.setenv("XHS_AGENT_RUN_DB_PATH", str(db_path))

    exit_code = script.main(["--run-id", "run_script_dry", "--dry-run"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert '"dry_run": true' in captured.out
    with sqlite3.connect(db_path) as connection:
        names = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
        }
    assert "raw_notes" not in names
