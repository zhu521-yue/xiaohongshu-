from langgraph.types import interrupt

from app.state import XHSState


def human_review(state: XHSState) -> dict:
    risk_level = state.get("compliance_risk_level", "low")
    if risk_level == "high":
        return {
            "review_action": "rejected",
            "human_approved": False,
            "human_feedback": "合规风险高，人工审核不通过。",
            "publish_status": "rejected",
            "run_status": "rejected",
        }

    if state.get("human_approved") is True:
        return {
            "review_action": "approved",
            "human_approved": True,
            "human_feedback": state.get("human_feedback") or "人工审核通过。",
            "publish_status": "pending",
        }

    resume_value = interrupt(_review_payload(state))
    if not isinstance(resume_value, dict):
        raise ValueError("human review resume payload must be a dict")

    action = str(resume_value.get("action") or "").strip().lower()
    feedback = str(resume_value.get("feedback") or "").strip()
    if action == "approved":
        return {
            "review_action": "approved",
            "human_approved": True,
            "human_feedback": feedback or "人工审核通过。",
            "publish_status": "pending",
            "creator_publish_requested": bool(resume_value.get("creator_publish")),
            "creator_publish_private": bool(resume_value.get("creator_publish_private")),
            "creator_human_confirmed": bool(resume_value.get("creator_human_confirmed")),
        }
    if action == "rejected":
        return {
            "review_action": "rejected",
            "human_approved": False,
            "human_feedback": feedback or "人工审核不通过。",
            "publish_status": "rejected",
        }
    raise ValueError("human review action must be approved or rejected")


def _review_payload(state: XHSState) -> dict:
    return {
        "run_id": state.get("run_id"),
        "user_topic": state.get("user_topic"),
        "content_format": state.get("content_format"),
        "titles": state.get("titles") or [],
        "body": state.get("body") or "",
        "video_script": state.get("video_script") or {},
        "tags": state.get("tags") or [],
        "compliance_risk_level": state.get("compliance_risk_level"),
        "compliance_issues": state.get("compliance_issues") or [],
    }
