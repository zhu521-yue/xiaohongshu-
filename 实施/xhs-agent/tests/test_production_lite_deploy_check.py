from scripts import check_production_lite_deploy as deploy_check


def test_deploy_check_fails_without_api_token(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv("XHS_AGENT_API_TOKEN", raising=False)
    monkeypatch.setenv("XHS_AGENT_LOG_DIR", str(tmp_path / "logs"))
    monkeypatch.setenv("XHS_AGENT_RUN_STORE", "sqlite")
    monkeypatch.setenv("XHS_AGENT_RUN_QUEUE", "sqlite")
    monkeypatch.setenv("XHS_AGENT_MEMORY_STORE", "sqlite")
    monkeypatch.setenv("XHS_AGENT_DB_SCHEMA", "foundation")
    monkeypatch.setenv("XHS_AGENT_BUSINESS_TABLES_ENABLED", "true")
    monkeypatch.setenv("XHS_AGENT_RUN_DB_PATH", str(tmp_path / "xhs.sqlite3"))
    monkeypatch.setenv("XHS_AGENT_QUEUE_DB_PATH", str(tmp_path / "xhs.sqlite3"))
    monkeypatch.setenv("XHS_AGENT_MEMORY_DB_PATH", str(tmp_path / "xhs.sqlite3"))

    result = deploy_check.check_deployment(backup_dir=tmp_path / "backups")

    assert result["ok"] is False
    assert any(item["level"] == "FAIL" and "API token" in item["message"] for item in result["checks"])


def test_deploy_check_passes_sqlite_baseline(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "xhs.sqlite3"
    monkeypatch.setenv("XHS_AGENT_API_TOKEN", "secret-token")
    monkeypatch.setenv("XHS_AGENT_LOG_DIR", str(tmp_path / "logs"))
    monkeypatch.setenv("XHS_AGENT_RUN_STORE", "sqlite")
    monkeypatch.setenv("XHS_AGENT_RUN_QUEUE", "sqlite")
    monkeypatch.setenv("XHS_AGENT_MEMORY_STORE", "sqlite")
    monkeypatch.setenv("XHS_AGENT_DB_SCHEMA", "foundation")
    monkeypatch.setenv("XHS_AGENT_BUSINESS_TABLES_ENABLED", "true")
    monkeypatch.setenv("XHS_AGENT_RUN_DB_PATH", str(db_path))
    monkeypatch.setenv("XHS_AGENT_QUEUE_DB_PATH", str(db_path))
    monkeypatch.setenv("XHS_AGENT_MEMORY_DB_PATH", str(db_path))
    monkeypatch.setenv("LLM_API_KEY", "llm-key")
    monkeypatch.setenv("XHS_COOKIES_PC", "cookie-value")

    result = deploy_check.check_deployment(backup_dir=tmp_path / "backups")

    assert result["ok"] is True
    assert (tmp_path / "backups").exists()
