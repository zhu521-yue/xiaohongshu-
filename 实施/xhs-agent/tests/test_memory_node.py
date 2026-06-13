from __future__ import annotations

from nodes import memory_node


def test_retrieve_graphrag_memory_includes_graph_view(monkeypatch) -> None:
    records = [{"record_id": "op_graph", "topic": "小红书选题"}]
    captured: dict = {}

    monkeypatch.setattr(memory_node, "find_relevant_records", lambda topic, limit=5: records)
    monkeypatch.setattr(memory_node, "find_successful_patterns", lambda topic, limit=3: [])

    def fake_query(records_arg, *, topic: str, limit: int = 20) -> dict:
        captured["records"] = records_arg
        captured["topic"] = topic
        captured["limit"] = limit
        return {"query": topic, "graph": {"record_count": len(records_arg)}}

    monkeypatch.setattr(memory_node, "query_memory_graph", fake_query, raising=False)

    result = memory_node.retrieve_graphrag_memory({"user_topic": "小红书选题"})

    assert result["retrieved_memory"] == records
    assert result["graphrag_memory"] == {"query": "小红书选题", "graph": {"record_count": 1}}
    assert captured == {"records": records, "topic": "小红书选题", "limit": 5}
