"""Operation memory nodes.

M3 uses a JSON history file as the first durable memory layer. Later this can
be replaced by GraphRAG without changing the rest of the graph.
"""

from app.state import XHSState
from app.memory_graph import query_memory_graph
from memory.operation_store import (
    find_relevant_records,
    find_successful_patterns,
    operation_memory_path,
    upsert_record_from_state,
)


def _rag_skip_detail(rag_eligibility: object) -> dict:
    if not isinstance(rag_eligibility, dict):
        return {}
    return {
        "level": rag_eligibility.get("level") or "",
        "score": rag_eligibility.get("score") or 0,
        "blocking_reasons": rag_eligibility.get("blocking_reasons") or [],
        "recommended_action": rag_eligibility.get("recommended_action") or "",
    }


def _is_rag_blocked(state: XHSState) -> bool:
    rag_eligibility = state.get("rag_eligibility")
    return isinstance(rag_eligibility, dict) and rag_eligibility.get("eligible") is False


def retrieve_graphrag_memory(state: XHSState) -> dict:
    topic = state.get("user_topic", "")
    retrieved_memory = find_relevant_records(topic, limit=5)
    successful_patterns = find_successful_patterns(topic, limit=3)
    graphrag_memory = query_memory_graph(retrieved_memory, topic=topic, limit=5)

    return {
        "retrieved_memory": retrieved_memory,
        "successful_patterns": successful_patterns,
        "graphrag_memory": graphrag_memory,
    }


def write_operation_memory(state: XHSState) -> dict:
    next_action = state.get("next_action") or "发布后录入表现数据，再进行复盘。"

    if state.get("publish_status") != "success":
        return {
            "next_action": next_action,
            "operation_memory_path": str(operation_memory_path()),
            "operation_memory_written": False,
        }

    if _is_rag_blocked(state):
        return {
            "next_action": next_action,
            "operation_memory_path": str(operation_memory_path()),
            "operation_memory_written": False,
            "operation_memory_skip_reason": "rag_eligibility_blocked",
            "operation_memory_skip_detail": _rag_skip_detail(state.get("rag_eligibility")),
        }

    record = upsert_record_from_state(state)

    return {
        "next_action": next_action,
        "operation_record_id": record.get("record_id"),
        "operation_memory_path": str(operation_memory_path()),
        "operation_memory_written": True,
    }
