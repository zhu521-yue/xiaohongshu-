from app.state import XHSState
from memory.operation_store import operation_memory_path


def reject_publish(state: XHSState) -> dict:
    topic = state.get("user_topic") or "Untitled topic"
    feedback = state.get("human_feedback") or "Human review rejected the draft."
    return {
        "run_status": "rejected",
        "publish_status": "rejected",
        "post_id": None,
        "operation_memory_written": False,
        "operation_memory_path": str(operation_memory_path()),
        "review_summary": f'Topic "{topic}" was rejected by human review. Draft was not saved.',
        "next_action": f"Regenerate after applying human feedback: {feedback}",
        "review_generation": {
            "enabled": False,
            "provider_mode": "manual_review",
            "model": None,
            "usage": {},
        },
    }
