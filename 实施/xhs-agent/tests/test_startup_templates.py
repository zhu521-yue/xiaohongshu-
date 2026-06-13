from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read_script(name: str) -> str:
    return (ROOT / "scripts" / name).read_text(encoding="utf-8")


def test_startup_templates_exist() -> None:
    for name in ("start_local_api.ps1", "start_sqlite_api.ps1", "start_sqlite_worker.ps1"):
        assert (ROOT / "scripts" / name).exists()


def test_templates_support_check_only_and_content_share_python() -> None:
    for name in ("start_local_api.ps1", "start_sqlite_api.ps1", "start_sqlite_worker.ps1"):
        script = read_script(name)
        assert "CheckOnly" in script
        assert "XHS_AGENT_PYTHON" in script
        assert "ContentShare" in script
        assert "check_runtime_config.py" in script


def test_sqlite_templates_share_one_db_path() -> None:
    for name in ("start_sqlite_api.ps1", "start_sqlite_worker.ps1"):
        script = read_script(name)
        assert "XHS_AGENT_RUN_STORE" in script
        assert "XHS_AGENT_RUN_QUEUE" in script
        assert "XHS_AGENT_MEMORY_STORE" in script
        assert "XHS_AGENT_RUN_DB_PATH" in script
        assert "XHS_AGENT_QUEUE_DB_PATH" in script
        assert "XHS_AGENT_MEMORY_DB_PATH" in script
        assert "sqlite-worker" in script


def test_sqlite_worker_template_supports_watchdog_and_heartbeat_config() -> None:
    script = read_script("start_sqlite_worker.ps1")

    assert "Watchdog" in script
    assert "XHS_AGENT_QUEUE_HEARTBEAT_INTERVAL_SECONDS" in script
    assert "XHS_AGENT_QUEUE_HEARTBEAT_TIMEOUT_SECONDS" in script
    assert "--watchdog-loop" in script
