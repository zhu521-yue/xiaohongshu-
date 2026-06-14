from __future__ import annotations

from nodes import memory_node


def test_retrieve_graphrag_memory_includes_graph_view(monkeypatch) -> None:
    records = [{"record_id": "op_graph", "topic": "小红书选题"}]
    captured: dict = {}

    monkeypatch.setattr(memory_node, "find_relevant_records", lambda topic, limit=5: records)
    monkeypatch.setattr(memory_node, "find_successful_patterns", lambda topic, limit=3: [])

    def fake_query(records_arg, *, topic: str, limit: int = 20, **kwargs) -> dict:
        captured["records"] = records_arg
        captured["topic"] = topic
        captured["limit"] = limit
        return {"query": topic, "graph": {"record_count": len(records_arg)}}

    monkeypatch.setattr(memory_node, "query_memory_graph", fake_query, raising=False)

    result = memory_node.retrieve_graphrag_memory({"user_topic": "小红书选题"})

    assert result["retrieved_memory"] == records
    assert result["graphrag_memory"] == {"query": "小红书选题", "graph": {"record_count": 1}}
    assert captured == {"records": records, "topic": "小红书选题", "limit": 5}


def test_write_operation_memory_skips_when_rag_eligibility_blocked(monkeypatch) -> None:
    called = {"upsert": False}

    def fake_upsert(state):
        called["upsert"] = True
        return {"record_id": "op_should_not_write"}

    monkeypatch.setattr(memory_node, "upsert_record_from_state", fake_upsert)

    result = memory_node.write_operation_memory(
        {
            "publish_status": "success",
            "next_action": "重新采集更多评论。",
            "rag_eligibility": {
                "eligible": False,
                "level": "blocked",
                "score": 35,
                "blocking_reasons": ["评论样本较少", "痛点证据不足"],
                "recommended_action": "重新采集更多候选和评论后再进入 RAG 入库。",
            },
        }
    )

    assert called["upsert"] is False
    assert result["operation_memory_written"] is False
    assert result["operation_memory_skip_reason"] == "rag_eligibility_blocked"
    assert result["operation_memory_skip_detail"] == {
        "level": "blocked",
        "score": 35,
        "blocking_reasons": ["评论样本较少", "痛点证据不足"],
        "recommended_action": "重新采集更多候选和评论后再进入 RAG 入库。",
    }


def test_write_operation_memory_allows_legacy_state_without_rag_eligibility(monkeypatch) -> None:
    captured = {}

    def fake_upsert(state):
        captured["state"] = state
        return {"record_id": "op_legacy"}

    monkeypatch.setattr(memory_node, "upsert_record_from_state", fake_upsert)

    result = memory_node.write_operation_memory(
        {
            "publish_status": "success",
            "next_action": "发布后录入表现数据。",
        }
    )

    assert captured["state"]["publish_status"] == "success"
    assert result["operation_memory_written"] is True
    assert result["operation_record_id"] == "op_legacy"
    assert "operation_memory_skip_reason" not in result


def test_retrieve_graphrag_memory_passes_current_context(monkeypatch) -> None:
    captured: dict = {}

    monkeypatch.setattr(memory_node, "find_relevant_records", lambda topic, limit=5: [], raising=False)
    monkeypatch.setattr(memory_node, "find_successful_patterns", lambda topic, limit=3: [], raising=False)

    def fake_query(records_arg, *, topic: str, limit: int = 20, **kwargs) -> dict:
        captured["records"] = records_arg
        captured["topic"] = topic
        captured["limit"] = limit
        captured["kwargs"] = kwargs
        return {"query": topic, "similar_experience_records": []}

    monkeypatch.setattr(memory_node, "query_memory_graph", fake_query, raising=False)

    state = {
        "user_topic": "小红书选题",
        "pain_points": [{"pain": "担心踩坑浪费时间"}],
        "comment_insights": [{"pain": "不知道从哪里开始"}],
        "compliance_risk_level": "medium",
        "compliance_issues": ["内容中包含绝对词：一定"],
    }

    memory_node.retrieve_graphrag_memory(state)

    assert captured["topic"] == "小红书选题"
    assert captured["limit"] == 5
    assert captured["kwargs"]["pain_points"] == state["pain_points"]
    assert captured["kwargs"]["comment_insights"] == state["comment_insights"]
    assert captured["kwargs"]["compliance_risk_level"] == "medium"
    assert captured["kwargs"]["compliance_issues"] == state["compliance_issues"]
