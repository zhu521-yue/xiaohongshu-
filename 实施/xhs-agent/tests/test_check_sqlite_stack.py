from __future__ import annotations

import json
from pathlib import Path

from app import api
from memory import operation_store
from scripts import check_sqlite_stack


def reset_services() -> None:
    api.RUN_STORE = None
    api.RUN_QUEUE_SERVICE = None
    operation_store.MEMORY_BACKEND = None


def test_run_sqlite_stack_smoke_processes_mock_run_and_records_business_events(
    tmp_path: Path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "xhs_agent.sqlite3"
    monkeypatch.setenv("XHS_AGENT_LOG_DIR", str(tmp_path / "logs"))
    reset_services()

    result = check_sqlite_stack.run_sqlite_stack_smoke(
        db_path=db_path,
        worker_id="smoke-worker",
        watchdog_worker_id="smoke-watchdog",
        topic="小红书新手选题方法",
        target_user="内容创作新手",
        content_format="image_text",
        engine="local",
        collect_limit=2,
    )

    assert result["ok"] is True
    assert result["run"]["status"] == "success"
    assert result["queue"]["queued_count"] == 0
    assert result["queue"]["running_count"] == 0
    assert result["watchdog"]["timed_out_run_ids"] == []
    assert result["business_run"]["counts"]["run_events"] >= 4
    assert result["business_run"]["counts"]["raw_notes"] >= 1
    assert "queue_heartbeat" in result["event_types"]
    reset_services()


def test_run_sqlite_stack_smoke_restores_environment(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("XHS_AGENT_RUN_STORE", "json")
    monkeypatch.setenv("COLLECTOR_MODE", "spider_xhs")
    reset_services()

    check_sqlite_stack.run_sqlite_stack_smoke(
        db_path=tmp_path / "xhs_agent.sqlite3",
        worker_id="smoke-worker",
        watchdog_worker_id="smoke-watchdog",
    )

    assert check_sqlite_stack.os.getenv("XHS_AGENT_RUN_STORE") == "json"
    assert check_sqlite_stack.os.getenv("COLLECTOR_MODE") == "spider_xhs"
    reset_services()


def test_main_prints_json_summary(tmp_path: Path, capsys) -> None:
    exit_code = check_sqlite_stack.main(
        [
            "--db-path",
            str(tmp_path / "xhs_agent.sqlite3"),
            "--worker-id",
            "smoke-worker",
            "--watchdog-worker-id",
            "smoke-watchdog",
            "--engine",
            "local",
        ]
    )

    output = capsys.readouterr().out
    assert exit_code == 0
    assert '"ok": true' in output
    assert '"status": "success"' in output


def test_main_without_db_path_uses_workspace_data_temp_dir(capsys) -> None:
    exit_code = check_sqlite_stack.main(["--engine", "local"])

    data = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert data["ok"] is True
    assert str(Path(data["db_path"])).startswith(str(check_sqlite_stack.ROOT / "data"))
