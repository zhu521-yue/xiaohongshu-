from __future__ import annotations

from pathlib import Path

import pytest

from app import api
from app.run_store import LocalRunStore
from memory import operation_store


def _reset_services() -> None:
    api.RUN_STORE = None
    api.RUN_QUEUE_SERVICE = None
    operation_store.MEMORY_BACKEND = None


@pytest.fixture()
def isolated_api(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("XHS_AGENT_RUN_STORE", "json")
    monkeypatch.setenv("XHS_AGENT_RUN_QUEUE", "local")
    monkeypatch.setenv("XHS_AGENT_MEMORY_STORE", "json")
    monkeypatch.setenv("CREATOR_MODE", "mock")
    monkeypatch.setenv("LLM_MODEL_NAME", "mock")
    monkeypatch.setattr(api, "RUN_STORE", LocalRunStore(tmp_path / "runs", json_default=api._json_default))
    monkeypatch.setattr(api, "RUNS_DIR", tmp_path / "runs")
    monkeypatch.setattr(
        operation_store,
        "MEMORY_BACKEND",
        operation_store.JsonOperationMemoryBackend(tmp_path / "operation_history.json"),
    )
    monkeypatch.setattr(api.publish_node, "OUTPUT_DIR", tmp_path / "markdown_exports")
    yield tmp_path
    _reset_services()


def _operation_state(*, post_id: str = "output/post.md", creator_note_id: str = "mock_note_001") -> dict:
    return {
        "post_id": post_id,
        "publish_status": "success",
        "publish_time": "2026-06-11T10:00:00",
        "creator_publish_requested": True,
        "creator_publish_status": "success",
        "creator_publish_mode": "mock",
        "creator_note_id": creator_note_id,
        "user_topic": "小红书新手选题方法",
        "target_user": "内容创作新手",
        "account_stage": "cold_start",
        "content_type": "step_tutorial",
        "content_format": "image_text",
        "titles": ["选题三步法"],
        "collection_path": None,
        "pain_points": [{"pain": "不知道怎么选题", "evidence": "不会选题", "priority": 1}],
        "comment_insights": [],
        "performance_data": {},
        "review_summary": "草稿已生成。",
        "next_action": "发布后录入表现数据。",
        "review_generation": {"enabled": False, "provider_mode": "template"},
    }


def test_list_creator_notes_returns_adapter_result(isolated_api, monkeypatch) -> None:
    expected = {
        "ok": True,
        "mode": "mock",
        "platform": "xhs_creator",
        "notes": [{"note_id": "mock_note_001", "title": "Mock note", "visibility": "private"}],
    }

    def fake_list_published_notes(limit: int = 20) -> dict:
        assert limit == 5
        return expected

    monkeypatch.setattr(api.creator_platform, "list_published_notes", fake_list_published_notes)

    result = api.list_creator_notes(limit=5)

    assert result == {"creator_notes": expected}


def test_record_performance_can_match_creator_note_id(isolated_api) -> None:
    saved = operation_store.upsert_record_from_state(_operation_state())

    result = api.record_performance(
        {
            "creator_note_id": "mock_note_001",
            "views": 1000,
            "likes": 50,
            "collects": 20,
            "comments": 8,
            "follows": 3,
        }
    )

    updated = result["updated_record"]
    assert updated["record_id"] == saved["record_id"]
    assert updated["creator_note_id"] == "mock_note_001"
    assert updated["status"] == "performance_recorded"
    assert updated["performance_score"] > 0
    assert updated["performance_data"]["views"] == 1000


def test_record_performance_requires_post_id_or_creator_note_id(isolated_api) -> None:
    with pytest.raises(ValueError, match="post_id or creator_note_id"):
        api.record_performance({"views": 1})
