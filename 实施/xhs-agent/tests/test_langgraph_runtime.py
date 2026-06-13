from __future__ import annotations

from pathlib import Path

from langgraph.types import interrupt

from app.langgraph_runtime import run_graph_thread, resume_graph_thread


def test_run_graph_thread_interrupts_with_run_id_thread(tmp_path: Path, monkeypatch) -> None:
    from app import graph

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
    monkeypatch.setattr(graph, "human_review", lambda state: interrupt({"run_id": state.get("run_id")}))

    result = run_graph_thread(
        {"user_topic": "topic", "target_user": "user", "user_selected_format": "image_text"},
        run_id="run_runtime_interrupt",
        checkpoint_db_path=tmp_path / "runtime.sqlite3",
    )

    assert result.interrupted is True
    assert result.run_status == "waiting_review"
    assert result.config["configurable"]["thread_id"] == "run_runtime_interrupt"
    assert result.interrupt_payload["run_id"] == "run_runtime_interrupt"


def test_resume_graph_thread_uses_human_review_payload(tmp_path: Path, monkeypatch) -> None:
    from app import graph

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
    monkeypatch.setattr(graph, "publish_or_schedule", lambda state: {"publish_status": "success", "post_id": "post.md"})
    monkeypatch.setattr(graph, "review_performance", lambda state: {"review_summary": "reviewed"})
    monkeypatch.setattr(graph, "write_operation_memory", lambda state: {"operation_memory_written": True})

    run_graph_thread(
        {"user_topic": "topic", "target_user": "user", "user_selected_format": "image_text"},
        run_id="run_runtime_resume",
        checkpoint_db_path=tmp_path / "runtime.sqlite3",
    )
    result = resume_graph_thread(
        "run_runtime_resume",
        {"action": "approved", "feedback": "approved by user"},
        checkpoint_db_path=tmp_path / "runtime.sqlite3",
    )

    assert result.interrupted is False
    assert result.state["human_approved"] is True
    assert result.state["human_feedback"] == "approved by user"
    assert result.state["publish_status"] == "success"
    assert result.state["operation_memory_written"] is True
