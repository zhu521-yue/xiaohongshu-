"""M1 本地流程执行器。

这个文件先不接真正的 LangGraph，只模拟 LangGraph 的核心机制：
每个节点读取 state，返回 updates，然后把 updates 合并回 state。
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any, Callable

from app.run_events import record_run_event
from app.state import XHSState

from nodes.compliance_node import check_compliance, revise_content_for_compliance
from nodes.content_node import generate_image_text
from nodes.human_review_node import human_review
from nodes.input_node import load_user_input
from nodes.insight_node import analyze_topic_and_pain_points
from nodes.memory_node import retrieve_graphrag_memory, write_operation_memory
from nodes.publish_node import publish_or_schedule
from nodes.review_node import review_performance
from nodes.stage_node import check_account_stage
from nodes.strategy_node import decide_content_strategy
from nodes.video_node import generate_video_script
from routers.compliance_router import route_compliance_result
from routers.content_format_router import route_content_format
from routers.review_router import route_human_review


def _merge_state(state: XHSState, updates: dict) -> XHSState:
    next_state = dict(state)
    next_state.update(updates)
    return next_state


def run_local_graph(
    initial_state: XHSState,
    *,
    run_id: str | None = None,
    event_db_path: str | Path | None = None,
) -> XHSState:
    state = dict(initial_state)

    for node_name, node in (
        ("load_user_input", load_user_input),
        ("check_account_stage", check_account_stage),
        ("retrieve_graphrag_memory", retrieve_graphrag_memory),
        ("analyze_topic_and_pain_points", analyze_topic_and_pain_points),
        ("decide_content_strategy", decide_content_strategy),
    ):
        state = _run_node(
            state,
            node,
            node_name=node_name,
            run_id=run_id,
            event_db_path=event_db_path,
        )

    if state.get("content_format") == "video":
        state = _run_node(
            state,
            generate_video_script,
            node_name="generate_video_script",
            run_id=run_id,
            event_db_path=event_db_path,
        )
    else:
        state = _run_node(
            state,
            generate_image_text,
            node_name="generate_image_text",
            run_id=run_id,
            event_db_path=event_db_path,
        )

    state = _run_node(
        state,
        check_compliance,
        node_name="check_compliance",
        run_id=run_id,
        event_db_path=event_db_path,
    )
    if state.get("compliance_risk_level") == "medium":
        state = _run_node(
            state,
            revise_content_for_compliance,
            node_name="revise_content_for_compliance",
            run_id=run_id,
            event_db_path=event_db_path,
        )
    state = _run_node(
        state,
        human_review,
        node_name="human_review",
        run_id=run_id,
        event_db_path=event_db_path,
    )

    if state.get("human_approved") is True:
        state = _run_node(
            state,
            publish_or_schedule,
            node_name="publish_or_schedule",
            run_id=run_id,
            event_db_path=event_db_path,
        )

    state = _run_node(
        state,
        review_performance,
        node_name="review_performance",
        run_id=run_id,
        event_db_path=event_db_path,
    )
    state = _run_node(
        state,
        write_operation_memory,
        node_name="write_operation_memory",
        run_id=run_id,
        event_db_path=event_db_path,
    )

    return state


def _run_node(
    state: XHSState,
    node: Callable[[XHSState], dict],
    *,
    node_name: str,
    run_id: str | None,
    event_db_path: str | Path | None,
) -> XHSState:
    started_at = _now_iso()
    start = perf_counter()
    try:
        updates = node(state)
    except Exception as exc:
        finished_at = _now_iso()
        _record_node_event(
            run_id,
            event_db_path,
            event_type="node_failed",
            node_name=node_name,
            status="failed",
            error=str(exc),
            started_at=started_at,
            finished_at=finished_at,
            duration_ms=_duration_ms(start),
        )
        raise

    finished_at = _now_iso()
    _record_node_event(
        run_id,
        event_db_path,
        event_type="node_finished",
        node_name=node_name,
        status="success",
        started_at=started_at,
        finished_at=finished_at,
        duration_ms=_duration_ms(start),
        payload={"updates": sorted(str(key) for key in (updates or {}).keys())},
    )
    return _merge_state(state, updates)


def _record_node_event(
    run_id: str | None,
    event_db_path: str | Path | None,
    **kwargs: Any,
) -> None:
    if not run_id or event_db_path is None:
        return
    record_run_event(event_db_path, run_id=run_id, **kwargs)


def _duration_ms(start: float) -> int:
    return max(0, int((perf_counter() - start) * 1000))


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def build_langgraph():
    from langgraph.graph import END, START, StateGraph

    graph = StateGraph(XHSState)

    graph.add_node("load_user_input", load_user_input)
    graph.add_node("check_account_stage", check_account_stage)
    graph.add_node("retrieve_graphrag_memory", retrieve_graphrag_memory)
    graph.add_node("analyze_topic_and_pain_points", analyze_topic_and_pain_points)
    graph.add_node("decide_content_strategy", decide_content_strategy)
    graph.add_node("generate_image_text", generate_image_text)
    graph.add_node("generate_video_script", generate_video_script)
    graph.add_node("check_compliance", check_compliance)
    graph.add_node("revise_content_for_compliance", revise_content_for_compliance)
    graph.add_node("human_review", human_review)
    graph.add_node("publish_or_schedule", publish_or_schedule)
    graph.add_node("review_performance", review_performance)
    graph.add_node("write_operation_memory", write_operation_memory)

    graph.add_edge(START, "load_user_input")
    graph.add_edge("load_user_input", "check_account_stage")
    graph.add_edge("check_account_stage", "retrieve_graphrag_memory")
    graph.add_edge("retrieve_graphrag_memory", "analyze_topic_and_pain_points")
    graph.add_edge("analyze_topic_and_pain_points", "decide_content_strategy")

    graph.add_conditional_edges(
        "decide_content_strategy",
        route_content_format,
        {
            "generate_image_text": "generate_image_text",
            "generate_video_script": "generate_video_script",
            "error_handler": END,
        },
    )

    graph.add_edge("generate_image_text", "check_compliance")
    graph.add_edge("generate_video_script", "check_compliance")

    graph.add_conditional_edges(
        "check_compliance",
        route_compliance_result,
        {
            "human_review": "human_review",
            "revise_content": "revise_content_for_compliance",
            "stop_publish": END,
            "error_handler": END,
        },
    )

    graph.add_edge("revise_content_for_compliance", "human_review")

    graph.add_conditional_edges(
        "human_review",
        route_human_review,
        {
            "publish_or_schedule": "publish_or_schedule",
            "wait_human_review": "review_performance",
        },
    )

    graph.add_edge("publish_or_schedule", "review_performance")
    graph.add_edge("review_performance", "write_operation_memory")
    graph.add_edge("write_operation_memory", END)

    return graph.compile()


def run_langgraph(initial_state: XHSState) -> XHSState:
    app = build_langgraph()
    return app.invoke(initial_state)
