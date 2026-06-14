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


def test_run_graph_thread_retrieves_memory_after_insights(tmp_path: Path, monkeypatch) -> None:
    from app import graph

    captured = {}
    pain_points = [{"pain": "不知道「小红书新手选题方法」从哪里开始，需要清晰的入门步骤"}]

    def retrieve_with_current_context(state: dict) -> dict:
        captured["pain_points"] = state.get("pain_points")
        return {
            "retrieved_memory": [],
            "graphrag_memory": {
                "query": state.get("user_topic"),
                "recall_explanations": [
                    {
                        "type": "similar_experience",
                        "record_id": "op_seed",
                        "matched_terms": [pain_points[0]["pain"]],
                        "matched_fields": ["pain_points"],
                        "reason": "当前痛点与历史记录相似。",
                    }
                ],
            },
        }

    monkeypatch.setattr(graph, "load_user_input", lambda state: {"run_status": "running"})
    monkeypatch.setattr(graph, "check_account_stage", lambda state: {"account_stage": "cold_start"})
    monkeypatch.setattr(
        graph,
        "analyze_topic_and_pain_points",
        lambda state: {"pain_points": pain_points, "comment_insights": []},
    )
    monkeypatch.setattr(graph, "retrieve_graphrag_memory", retrieve_with_current_context)
    monkeypatch.setattr(
        graph,
        "decide_content_strategy",
        lambda state: {"content_format": "image_text", "content_type": "step_tutorial"},
    )
    monkeypatch.setattr(graph, "generate_image_text", lambda state: {"titles": ["T"], "body": "B"})
    monkeypatch.setattr(graph, "check_compliance", lambda state: {"compliance_risk_level": "low"})

    result = run_graph_thread(
        {
            "user_topic": "小红书新手选题方法",
            "target_user": "user",
            "user_selected_format": "image_text",
        },
        run_id="run_runtime_memory_after_insights",
        checkpoint_db_path=tmp_path / "runtime.sqlite3",
    )

    assert result.interrupted is True
    assert captured["pain_points"] == pain_points
    assert result.state["graphrag_memory"]["recall_explanations"][0]["record_id"] == "op_seed"


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


def test_reject_resume_finishes_inside_graph(tmp_path: Path, monkeypatch) -> None:
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

    run_graph_thread(
        {"user_topic": "topic", "target_user": "user", "user_selected_format": "image_text"},
        run_id="run_runtime_reject",
        checkpoint_db_path=tmp_path / "runtime.sqlite3",
    )
    result = resume_graph_thread(
        "run_runtime_reject",
        {"action": "rejected", "feedback": "needs rewrite"},
        checkpoint_db_path=tmp_path / "runtime.sqlite3",
    )

    assert result.state["run_status"] == "rejected"
    assert result.state["publish_status"] == "rejected"
    assert result.state["operation_memory_written"] is False
    assert "needs rewrite" in result.state["human_feedback"]
    assert result.state["review_generation"]["provider_mode"] == "manual_review"


def test_creator_publish_runs_inside_graph(tmp_path: Path, monkeypatch) -> None:
    from app import graph
    from platforms import creator as creator_platform

    calls = []
    monkeypatch.setattr(graph, "load_user_input", lambda state: {"run_status": "running"})
    monkeypatch.setattr(graph, "check_account_stage", lambda state: {"account_stage": "cold_start"})
    monkeypatch.setattr(graph, "retrieve_graphrag_memory", lambda state: {"retrieved_memory": []})
    monkeypatch.setattr(graph, "analyze_topic_and_pain_points", lambda state: {"pain_points": []})
    monkeypatch.setattr(
        graph,
        "decide_content_strategy",
        lambda state: {"content_format": "image_text", "content_type": "step_tutorial"},
    )
    monkeypatch.setattr(graph, "generate_image_text", lambda state: {"titles": ["T"], "body": "B", "tags": ["xhs"]})
    monkeypatch.setattr(graph, "check_compliance", lambda state: {"compliance_risk_level": "low"})
    monkeypatch.setattr(graph, "publish_or_schedule", lambda state: {"publish_status": "success", "post_id": "post.md"})
    monkeypatch.setattr(graph, "review_performance", lambda state: {"review_summary": "reviewed"})
    monkeypatch.setattr(graph, "write_operation_memory", lambda state: {"operation_memory_written": True})
    monkeypatch.setattr(
        creator_platform,
        "publish_private_image_text",
        lambda draft, human_confirmed: calls.append((draft, human_confirmed)) or {
            "ok": True,
            "mode": "mock",
            "platform": "xhs_creator",
            "visibility": "private",
            "note_id": "mock_private_note",
        },
    )

    run_graph_thread(
        {"user_topic": "topic", "target_user": "user", "user_selected_format": "image_text"},
        run_id="run_runtime_creator",
        checkpoint_db_path=tmp_path / "runtime.sqlite3",
    )
    result = resume_graph_thread(
        "run_runtime_creator",
        {
            "action": "approved",
            "feedback": "approved",
            "creator_publish": True,
            "creator_publish_private": True,
            "creator_human_confirmed": True,
        },
        checkpoint_db_path=tmp_path / "runtime.sqlite3",
    )

    assert len(calls) == 1
    assert result.state["creator_publish_status"] == "success"
    assert result.state["creator_note_id"] == "mock_private_note"
