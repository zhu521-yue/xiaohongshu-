from __future__ import annotations

from pathlib import Path

import pytest

from memory import operation_store as store


def sample_state(post_id: str, topic: str = "小红书新手选题方法") -> dict:
    return {
        "post_id": post_id,
        "publish_status": "success",
        "publish_time": "2026-06-10T10:00:00",
        "user_topic": topic,
        "target_user": "内容创作新手",
        "account_stage": "cold_start",
        "content_type": "step_tutorial",
        "content_format": "image_text",
        "titles": ["选题三步法", "新手选题步骤"],
        "collection_path": None,
        "pain_points": [
            {
                "pain": f"对「{topic}」是否真实可行存在怀疑，需要可信案例和边界说明",
                "evidence": "真的可以做到吗？需要干货",
                "priority": 1,
            }
        ],
        "comment_insights": [
            {
                "pain": f"对「{topic}」是否真实可行存在怀疑，需要可信案例和边界说明",
                "evidence_comments": ["真的可以做到吗？需要干货"],
                "evidence_count": 1,
                "priority": 1,
            }
        ],
        "performance_data": {},
        "review_summary": "草稿已生成。",
        "next_action": "发布后录入表现数据。",
        "review_generation": {"enabled": False, "provider_mode": "template"},
    }


@pytest.fixture()
def sqlite_memory(tmp_path: Path, monkeypatch):
    db_path = tmp_path / "memory.sqlite3"
    monkeypatch.setenv("XHS_AGENT_MEMORY_STORE", "sqlite")
    monkeypatch.setenv("XHS_AGENT_MEMORY_DB_PATH", str(db_path))
    monkeypatch.setenv("LLM_MODEL_NAME", "mock")
    store.MEMORY_BACKEND = None
    yield db_path
    store.MEMORY_BACKEND = None


def test_sqlite_operation_memory_upserts_and_loads_history(sqlite_memory: Path) -> None:
    first = store.upsert_record_from_state(sample_state("output/post.md"))
    second_state = sample_state("output/post.md")
    second_state["titles"] = ["更新后的标题"]
    second = store.upsert_record_from_state(second_state)

    history = store.load_history()

    assert sqlite_memory.exists()
    assert first["record_id"] == second["record_id"]
    assert len(history["records"]) == 1
    assert history["records"][0]["title"] == "更新后的标题"
    assert history["records"][0]["created_at"] == first["created_at"]


def test_sqlite_operation_memory_finds_relevant_records(sqlite_memory: Path) -> None:
    store.upsert_record_from_state(sample_state("output/topic.md", topic="小红书新手选题方法"))
    store.upsert_record_from_state(sample_state("output/other.md", topic="宝宝湿疹护理"))

    records = store.find_relevant_records("小红书新手选题方法", limit=5)

    assert [record["topic"] for record in records] == ["小红书新手选题方法"]


def test_sqlite_operation_memory_successful_patterns_use_performance(sqlite_memory: Path) -> None:
    state = sample_state("output/scored.md")
    state["performance_data"] = {"views": 1000, "likes": 50, "collects": 20, "comments": 8, "follows": 3}
    saved = store.upsert_record_from_state(state)

    patterns = store.find_successful_patterns("小红书新手选题方法", limit=3)

    assert len(patterns) == 1
    assert patterns[0]["record_id"] == saved["record_id"]
    assert patterns[0]["performance_score"] > 0


def test_sqlite_operation_memory_updates_performance(sqlite_memory: Path) -> None:
    saved = store.upsert_record_from_state(sample_state("output/performance.md"))

    updated = store.update_record_performance(
        post_id="output/performance.md",
        performance_data={"views": 1000, "likes": 50, "collects": 20, "comments": 8, "follows": 3},
        published_url="https://example.com/note",
        notes="manual note",
    )

    assert updated["record_id"] == saved["record_id"]
    assert updated["status"] == "performance_recorded"
    assert updated["performance_score"] > 0
    assert updated["published_url"] == "https://example.com/note"
    assert updated["operator_notes"] == "manual note"
    assert store.load_history()["records"][0]["performance_score"] == updated["performance_score"]


def test_sqlite_operation_memory_filters_cross_domain_health_pollution(sqlite_memory: Path) -> None:
    polluted = sample_state("output/polluted.md", topic="小红书新手选题方法")
    polluted["pain_points"] = [{"pain": "对护理方法存在疑问，担心建议不靠谱", "evidence": "旧脏数据", "priority": 1}]
    store.upsert_record_from_state(polluted)
    store.upsert_record_from_state(sample_state("output/clean.md", topic="小红书新手选题方法"))

    records = store.find_relevant_records("小红书新手选题方法", limit=5)

    assert [record["post_id"] for record in records] == ["output/clean.md"]


def test_json_operation_memory_still_loads_and_saves_explicit_path(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("XHS_AGENT_MEMORY_STORE", "json")
    store.MEMORY_BACKEND = None
    path = tmp_path / "operation_history.json"
    history = {"version": 1, "updated_at": None, "records": [store.record_from_state(sample_state("output/json.md"))]}

    store.save_history(history, path=path)
    loaded = store.load_history(path=path)

    assert loaded["records"][0]["post_id"] == "output/json.md"
    store.MEMORY_BACKEND = None
