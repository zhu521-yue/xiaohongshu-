from __future__ import annotations

from pathlib import Path

from scripts import check_runtime_config
from scripts.check_runtime_config import check_profile


def test_local_profile_passes_with_default_development_settings(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("XHS_AGENT_API_TOKEN", raising=False)
    monkeypatch.setenv("XHS_AGENT_LOG_DIR", str(tmp_path / "logs"))
    monkeypatch.delenv("XHS_AGENT_RUN_STORE", raising=False)
    monkeypatch.delenv("XHS_AGENT_RUN_QUEUE", raising=False)
    monkeypatch.delenv("XHS_AGENT_MEMORY_STORE", raising=False)

    results = check_profile("local")

    assert not [result for result in results if result.level == "FAIL"]
    assert any(result.level == "WARN" and "auth disabled" in result.message for result in results)


def test_production_lite_fails_without_api_token(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("XHS_AGENT_API_TOKEN", raising=False)
    monkeypatch.setenv("XHS_AGENT_LOG_DIR", str(tmp_path / "logs"))

    results = check_profile("production-lite")

    assert any(
        result.level == "FAIL" and "XHS_AGENT_API_TOKEN" in result.message
        for result in results
    )


def test_sqlite_worker_profile_checks_sqlite_backends(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "xhs_agent.sqlite3"
    monkeypatch.setenv("XHS_AGENT_LOG_DIR", str(tmp_path / "logs"))
    monkeypatch.setenv("XHS_AGENT_RUN_STORE", "sqlite")
    monkeypatch.setenv("XHS_AGENT_RUN_DB_PATH", str(db_path))
    monkeypatch.setenv("XHS_AGENT_RUN_QUEUE", "sqlite")
    monkeypatch.setenv("XHS_AGENT_QUEUE_DB_PATH", str(db_path))
    monkeypatch.setenv("XHS_AGENT_MEMORY_STORE", "sqlite")
    monkeypatch.setenv("XHS_AGENT_MEMORY_DB_PATH", str(db_path))

    results = check_profile("sqlite-worker")

    assert not [result for result in results if result.level == "FAIL"]
    assert any("run queue backend: sqlite" in result.message for result in results)


def test_sqlite_worker_profile_matches_resolved_relative_and_absolute_db_paths(
    tmp_path: Path, monkeypatch
) -> None:
    project_root = tmp_path / "project"
    relative_db_path = Path("data") / "xhs_agent.sqlite3"
    absolute_db_path = project_root / relative_db_path

    monkeypatch.setattr(check_runtime_config, "PROJECT_ROOT", project_root)
    monkeypatch.setenv("XHS_AGENT_LOG_DIR", str(tmp_path / "logs"))
    monkeypatch.setenv("XHS_AGENT_RUN_STORE", "sqlite")
    monkeypatch.setenv("XHS_AGENT_RUN_DB_PATH", str(relative_db_path))
    monkeypatch.setenv("XHS_AGENT_RUN_QUEUE", "sqlite")
    monkeypatch.setenv("XHS_AGENT_QUEUE_DB_PATH", str(absolute_db_path))
    monkeypatch.setenv("XHS_AGENT_MEMORY_STORE", "sqlite")
    monkeypatch.setenv("XHS_AGENT_MEMORY_DB_PATH", str(absolute_db_path))

    results = check_profile("sqlite-worker")

    assert any(result.level == "PASS" and result.message == "run DB path and queue DB path match" for result in results)
    assert not any(
        result.level == "WARN" and "run DB path and queue DB path differ" in result.message
        for result in results
    )
