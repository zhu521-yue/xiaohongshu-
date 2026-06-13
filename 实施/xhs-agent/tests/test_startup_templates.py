from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read_script(name: str) -> str:
    return (ROOT / "scripts" / name).read_text(encoding="utf-8")


def test_startup_templates_exist() -> None:
    for name in (
        "start_local_api.ps1",
        "start_sqlite_api.ps1",
        "start_sqlite_worker.ps1",
        "start_sqlite_stack.ps1",
        "check_sqlite_stack_health.ps1",
        "stop_sqlite_stack.ps1",
        "tail_sqlite_stack_logs.ps1",
    ):
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


def test_sqlite_stack_template_orchestrates_runtime_processes() -> None:
    script = read_script("start_sqlite_stack.ps1")

    assert "CheckOnly" in script
    assert "Start-Process" in script
    assert "-WindowStyle Hidden" in script
    assert "run_api.py" in script
    assert "run_worker.py" in script
    assert "--watchdog-loop" in script
    assert "run_creator_performance_scheduler.py" in script
    assert "XHS_AGENT_RUN_DB_PATH" in script
    assert "XHS_AGENT_QUEUE_DB_PATH" in script
    assert "XHS_AGENT_MEMORY_DB_PATH" in script
    assert "CREATOR_MODE" in script


def test_sqlite_stack_template_supports_scheduler_targets_and_toggles() -> None:
    script = read_script("start_sqlite_stack.ps1")

    assert "CreatorNoteId" in script
    assert "RunId" in script
    assert "StartScheduler" in script
    assert "NoApi" in script
    assert "NoWorker" in script
    assert "NoWatchdog" in script
    assert "--creator-note-id" in script
    assert "--run-id" in script
    assert "--schedule-interval-seconds" in script
    assert "--max-consecutive-failed-rounds" in script


def test_sqlite_stack_health_script_checks_config_api_queue_and_processes() -> None:
    script = read_script("check_sqlite_stack_health.ps1")

    assert "ConfigOnly" in script
    assert "check_runtime_config.py" in script
    assert "/health" in script
    assert "/queue" in script
    assert "Invoke-RestMethod" in script
    assert "Get-CimInstance" in script
    assert "run_api.py" in script
    assert "run_worker.py" in script
    assert "run_creator_performance_scheduler.py" in script


def test_sqlite_stack_stop_script_is_dry_run_by_default() -> None:
    script = read_script("stop_sqlite_stack.ps1")

    assert "Apply" in script
    assert "Stop-Process" in script
    assert "Get-CimInstance" in script
    assert "run_api.py" in script
    assert "run_worker.py" in script
    assert "run_creator_performance_scheduler.py" in script
    assert "if ($Apply)" in script


def test_sqlite_stack_log_tail_script_reads_known_logs() -> None:
    script = read_script("tail_sqlite_stack_logs.ps1")

    assert "LogDir" in script
    assert "Tail" in script
    assert "Get-Content" in script
    assert "api.log" in script
    assert "worker.log" in script
    assert "scheduler.log" in script
