from __future__ import annotations

from pathlib import Path

import pytest

from app import api
from app.run_store import LocalRunStore
from memory import operation_store


@pytest.fixture()
def isolated_langgraph_api(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("XHS_AGENT_RUN_STORE", "json")
    monkeypatch.setenv("XHS_AGENT_RUN_QUEUE", "local")
    monkeypatch.setenv("XHS_AGENT_MEMORY_STORE", "json")
    monkeypatch.setenv("LLM_MODEL_NAME", "mock")
    monkeypatch.setenv("COLLECTOR_MODE", "mock")
    monkeypatch.setattr(api, "RUN_STORE", LocalRunStore(tmp_path / "runs", json_default=api._json_default))
    monkeypatch.setattr(api, "RUNS_DIR", tmp_path / "runs")
    monkeypatch.setattr(api, "RUN_QUEUE_SERVICE", None)
    monkeypatch.setattr(api, "RUNTIME_CHECKPOINT_DB_PATH", tmp_path / "runtime.sqlite3", raising=False)
    monkeypatch.setattr(
        operation_store,
        "MEMORY_BACKEND",
        operation_store.JsonOperationMemoryBackend(tmp_path / "operation_history.json"),
    )
    monkeypatch.setattr(api.publish_node, "OUTPUT_DIR", tmp_path / "markdown_exports")
    yield tmp_path
    api.RUN_STORE = None
    api.RUN_QUEUE_SERVICE = None
    operation_store.MEMORY_BACKEND = None


def test_create_run_langgraph_waits_for_review(isolated_langgraph_api) -> None:
    record = api.create_run(
        {
            "topic": "小红书新手选题方法",
            "target_user": "内容创作新手",
            "format": "image_text",
            "engine": "langgraph",
            "collect_limit": 1,
        }
    )

    assert record["status"] == "success"
    assert record["summary"]["run_status"] == "waiting_review"
    assert record["summary"]["publish_status"] == "pending"
    assert record["summary"]["human_approved"] is False
    assert record["state"]["review_required"] is True
