from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from app import api, graph
from app.run_store import SQLiteRunStore


def _event_rows(db_path: Path, run_id: str) -> list[sqlite3.Row]:
    with sqlite3.connect(db_path) as connection:
        connection.row_factory = sqlite3.Row
        return connection.execute(
            "SELECT * FROM run_events WHERE run_id = ? ORDER BY created_at, event_type, node_name",
            (run_id,),
        ).fetchall()


def _patch_successful_local_nodes(monkeypatch) -> None:
    monkeypatch.setattr(graph, "load_user_input", lambda state: {"loaded": True})
    monkeypatch.setattr(graph, "check_account_stage", lambda state: {"account_stage": "cold_start"})
    monkeypatch.setattr(graph, "retrieve_graphrag_memory", lambda state: {"retrieved_memory": []})
    monkeypatch.setattr(graph, "analyze_topic_and_pain_points", lambda state: {"pain_points": []})
    monkeypatch.setattr(
        graph,
        "decide_content_strategy",
        lambda state: {"content_format": "image_text", "content_type": "step_tutorial"},
    )
    monkeypatch.setattr(graph, "generate_image_text", lambda state: {"titles": ["事件测试标题"]})
    monkeypatch.setattr(graph, "check_compliance", lambda state: {"compliance_risk_level": "low"})
    monkeypatch.setattr(graph, "human_review", lambda state: {"human_approved": False})
    monkeypatch.setattr(graph, "review_performance", lambda state: {"review_summary": "待发布"})
    monkeypatch.setattr(graph, "write_operation_memory", lambda state: {"operation_memory_written": False})


def test_run_local_graph_records_node_finished_events(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "xhs_agent.sqlite3"
    _patch_successful_local_nodes(monkeypatch)

    result = graph.run_local_graph(
        {"user_topic": "小红书新手选题方法"},
        run_id="run_graph_events",
        event_db_path=db_path,
    )

    assert result["titles"] == ["事件测试标题"]
    events = _event_rows(db_path, "run_graph_events")
    node_names = [row["node_name"] for row in events if row["event_type"] == "node_finished"]
    assert node_names == [
        "load_user_input",
        "check_account_stage",
        "analyze_topic_and_pain_points",
        "retrieve_graphrag_memory",
        "decide_content_strategy",
        "generate_image_text",
        "check_compliance",
        "human_review",
        "review_performance",
        "write_operation_memory",
    ]
    assert all(row["duration_ms"] >= 0 for row in events)


def test_run_local_graph_records_node_failed_event(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "xhs_agent.sqlite3"
    _patch_successful_local_nodes(monkeypatch)

    def fail_node(state: dict) -> dict:
        raise RuntimeError("collector failed")

    monkeypatch.setattr(graph, "analyze_topic_and_pain_points", fail_node)

    with pytest.raises(RuntimeError, match="collector failed"):
        graph.run_local_graph(
            {"user_topic": "小红书新手选题方法"},
            run_id="run_graph_failed",
            event_db_path=db_path,
        )

    events = _event_rows(db_path, "run_graph_failed")
    failed = [row for row in events if row["event_type"] == "node_failed"]
    assert len(failed) == 1
    assert failed[0]["node_name"] == "analyze_topic_and_pain_points"
    assert failed[0]["status"] == "failed"
    assert "collector failed" in failed[0]["error"]


def test_run_langgraph_records_node_events(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "xhs_agent.sqlite3"
    monkeypatch.setenv("XHS_AGENT_RUN_STORE", "sqlite")
    monkeypatch.setenv("XHS_AGENT_RUN_DB_PATH", str(db_path))
    monkeypatch.setenv("XHS_AGENT_DB_SCHEMA", "foundation")
    monkeypatch.setenv("XHS_AGENT_BUSINESS_TABLES_ENABLED", "true")
    monkeypatch.setattr(api, "RUN_STORE", SQLiteRunStore(db_path, json_default=api._json_default))
    monkeypatch.setattr(api, "RUNTIME_CHECKPOINT_DB_PATH", db_path, raising=False)
    monkeypatch.setattr(graph, "load_user_input", lambda state: {"run_status": "running"})
    monkeypatch.setattr(graph, "check_account_stage", lambda state: {"account_stage": "cold_start"})
    monkeypatch.setattr(graph, "retrieve_graphrag_memory", lambda state: {"retrieved_memory": []})
    monkeypatch.setattr(graph, "analyze_topic_and_pain_points", lambda state: {"pain_points": []})
    monkeypatch.setattr(
        graph,
        "decide_content_strategy",
        lambda state: {"content_format": "image_text", "content_type": "step_tutorial"},
    )
    monkeypatch.setattr(graph, "generate_image_text", lambda state: {"titles": ["T"], "body": "B"})
    monkeypatch.setattr(graph, "check_compliance", lambda state: {"compliance_risk_level": "low"})

    record = api.create_run({"topic": "topic", "format": "image_text", "engine": "langgraph"})

    events = _event_rows(db_path, record["run_id"])
    assert any(
        row["event_type"] == "node_finished" and row["node_name"] == "generate_image_text"
        for row in events
    )
    assert any(
        row["event_type"] == "node_interrupted" and row["node_name"] == "human_review"
        for row in events
    )
