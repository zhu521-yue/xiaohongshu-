from __future__ import annotations

from pathlib import Path

import pytest

from app import api
from app.run_store import LocalRunStore
from memory import operation_store
from nodes import publish_node


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
    monkeypatch.setattr(publish_node, "OUTPUT_DIR", tmp_path / "markdown_exports")
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
    assert record["summary"]["memory_context_summary"] == {
        "enabled": False,
        "query": "",
        "graph_record_count": 0,
        "recommended_content_type_count": 0,
        "recall_evidence_count": 0,
        "semantic_recall_count": 0,
        "semantic_embedding_model": "",
        "semantic_embedding_dimensions": 0,
        "similar_experience_count": 0,
        "historical_compliance_risk_count": 0,
        "recall_explanation_count": 0,
        "recall_explanations": [],
    }
    assert record["state"]["review_required"] is True


def test_approve_run_resumes_graph_without_direct_node_calls(isolated_langgraph_api) -> None:
    record = api.create_run(
        {
            "topic": "小红书新手选题方法",
            "target_user": "内容创作新手",
            "format": "image_text",
            "engine": "langgraph",
            "collect_limit": 1,
        }
    )

    reviewed = api.approve_run(record["run_id"], {"feedback": "approved"})

    assert reviewed["summary"]["run_status"] == "published"
    assert reviewed["summary"]["publish_status"] == "success"
    assert reviewed["state"]["operation_memory_written"] is True


def test_api_no_longer_exposes_legacy_direct_creator_publish_helpers() -> None:
    legacy_names = [
        "_publish_creator_private_if_requested",
        "_creator_publish_not_requested",
        "_creator_publish_failed",
        "_creator_publish_success",
        "_build_creator_image_text_draft",
        "_creator_images_from_state",
    ]

    assert [name for name in legacy_names if hasattr(api, name)] == []


def test_reject_run_resumes_graph_to_rejected_state(isolated_langgraph_api) -> None:
    record = api.create_run(
        {
            "topic": "小红书新手选题方法",
            "target_user": "内容创作新手",
            "format": "image_text",
            "engine": "langgraph",
            "collect_limit": 1,
        }
    )

    rejected = api.reject_run(record["run_id"], {"feedback": "needs rewrite"})

    assert rejected["summary"]["run_status"] == "rejected"
    assert rejected["summary"]["publish_status"] == "rejected"
    assert rejected["state"]["operation_memory_written"] is False
    assert rejected["review_action"] == "rejected"
