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

    record = upsert_record_from_state(state)

    return {
        "next_action": next_action,
        "operation_record_id": record.get("record_id"),
        "operation_memory_path": str(operation_memory_path()),
        "operation_memory_written": True,
    }
