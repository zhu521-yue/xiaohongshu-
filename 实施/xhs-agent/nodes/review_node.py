"""Review generated content and recorded performance.

The main graph reaches this node immediately after draft generation, when real
platform metrics usually do not exist yet. In that case the node keeps a cheap
template summary. When performance data is available, it tries to produce a
structured LLM review and falls back to deterministic rules on failure.
"""

from __future__ import annotations

import json
from typing import Any

from app.config import load_settings
from app.rules import load_performance_weights
from app.state import XHSState
from llm.client import LLMError, get_llm_client
from llm.prompts import build_json_prompt


EMPTY_PERFORMANCE = {
    "views": None,
    "likes": None,
    "collects": None,
    "comments": None,
    "follows": None,
}

PERFORMANCE_WEIGHTS = load_performance_weights()

REQUIRED_REVIEW_FIELDS = {
    "review_summary": str,
    "next_action": str,
    "reuse_decision": str,
    "key_learning": str,
}


def _safe_int(value: Any) -> int:
    if value is None or value == "":
        return 0
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _performance_score(performance_data: dict[str, Any] | None) -> int:
    if not performance_data:
        return 0
    return sum(
        _safe_int(performance_data.get(name)) * weight
        for name, weight in PERFORMANCE_WEIGHTS.items()
    )


def _has_performance_data(performance_data: dict[str, Any] | None) -> bool:
    if not performance_data:
        return False
    return any(_safe_int(performance_data.get(name)) > 0 for name in PERFORMANCE_WEIGHTS)


def _format_pain_points(value: Any, limit: int = 5) -> list[dict]:
    if not isinstance(value, list):
        return []

    result = []
    for item in value[:limit]:
        if isinstance(item, dict):
            result.append(
                {
                    "pain": str(item.get("pain") or ""),
                    "evidence": str(item.get("evidence") or ""),
                    "priority": item.get("priority"),
                }
            )
        else:
            result.append({"pain": str(item), "evidence": "", "priority": None})
    return result


def _format_comment_insights(value: Any, limit: int = 5) -> list[dict]:
    if not isinstance(value, list):
        return []

    result = []
    for item in value[:limit]:
        if not isinstance(item, dict):
            continue
        evidence_comments = item.get("evidence_comments") or []
        if not isinstance(evidence_comments, list):
            evidence_comments = []
        result.append(
            {
                "pain": str(item.get("pain") or ""),
                "evidence_comments": [str(comment) for comment in evidence_comments[:3]],
                "evidence_count": item.get("evidence_count"),
                "priority": item.get("priority"),
            }
        )
    return result


def _template_review_for_record(record: dict[str, Any], reason: str | None = None) -> dict:
    performance_data = record.get("performance_data") or {}
    score = _performance_score(performance_data)
    title = record.get("title") or record.get("topic") or "未命名内容"

    if not _has_performance_data(performance_data):
        review_summary = f"《{title}》已进入运营记忆，但还没有录入真实表现数据。"
        next_action = "发布后录入曝光、点赞、收藏、评论和关注数据，再判断是否值得复用。"
    else:
        likes = _safe_int(performance_data.get("likes"))
        collects = _safe_int(performance_data.get("collects"))
        comments = _safe_int(performance_data.get("comments"))
        follows = _safe_int(performance_data.get("follows"))

        strengths = []
        if collects >= likes and collects > 0:
            strengths.append("收藏表现相对更强，说明内容有工具性或可复查价值")
        if comments > 0:
            strengths.append("评论有反馈，可继续追问用户具体卡点")
        if follows > 0:
            strengths.append("带来关注，说明账号标签可能被用户认可")
        if not strengths:
            strengths.append("已有基础互动，可继续用同类主题验证")

        review_summary = f"《{title}》表现分 {score}。{'；'.join(strengths)}。"
        next_action = "下次同类主题优先复用该内容的痛点切入和结构，但继续用新评论验证选题。"

    review_generation = {
        "enabled": False,
        "provider_mode": "template",
        "model": None,
        "usage": {},
    }
    if reason:
        review_generation["error"] = reason

    return {
        "review_summary": review_summary,
        "next_action": next_action,
        "review_generation": review_generation,
    }


def _record_payload(record: dict[str, Any]) -> dict:
    performance_data = record.get("performance_data") or {}
    return {
        "topic": record.get("topic"),
        "target_user": record.get("target_user"),
        "title": record.get("title"),
        "content_type": record.get("content_type"),
        "content_format": record.get("content_format"),
        "pain_points": _format_pain_points(record.get("pain_points")),
        "comment_insights": _format_comment_insights(record.get("comment_insights")),
        "performance_data": {
            "views": _safe_int(performance_data.get("views")),
            "likes": _safe_int(performance_data.get("likes")),
            "collects": _safe_int(performance_data.get("collects")),
            "comments": _safe_int(performance_data.get("comments")),
            "follows": _safe_int(performance_data.get("follows")),
        },
        "performance_score": _performance_score(performance_data),
        "operator_notes": record.get("operator_notes"),
    }


def _validate_review_result(data: Any) -> dict:
    if not isinstance(data, dict):
        raise ValueError("LLM JSON root must be an object")

    for field, expected_type in REQUIRED_REVIEW_FIELDS.items():
        if field not in data:
            raise ValueError(f"missing field: {field}")
        if not isinstance(data[field], expected_type):
            raise ValueError(f"invalid field type: {field}")

    review_summary = str(data["review_summary"]).strip()
    next_action = str(data["next_action"]).strip()
    if not review_summary or not next_action:
        raise ValueError("review_summary/next_action cannot be empty")

    return {
        "review_summary": review_summary,
        "next_action": next_action,
        "reuse_decision": str(data["reuse_decision"]).strip(),
        "key_learning": str(data["key_learning"]).strip(),
    }


def _build_review_prompt(record: dict[str, Any]) -> list:
    input_payload = _record_payload(record)

    return build_json_prompt("operation_review", input_payload)


def _llm_review_record(record: dict[str, Any]) -> dict:
    performance_data = record.get("performance_data") or {}
    if not _has_performance_data(performance_data):
        raise LLMError("No performance data available")

    client = get_llm_client()
    if client.is_mock:
        raise LLMError("LLM is in mock mode")

    settings = load_settings()
    response = client.chat(
        messages=_build_review_prompt(record),
        temperature=0.2,
        max_tokens=settings.llm_review_max_tokens,
        response_format={"type": "json_object"},
    )
    result = _validate_review_result(json.loads(response.content))
    result["review_generation"] = {
        "enabled": True,
        "provider_mode": response.provider_mode,
        "model": response.model,
        "usage": response.usage,
        "reuse_decision": result.pop("reuse_decision"),
        "key_learning": result.pop("key_learning"),
    }
    return result


def build_operation_review(record: dict[str, Any]) -> dict:
    """Build a review for an operation memory record.

    This is also used by scripts/record_performance.py through
    memory.operation_store, so performance recording and graph review share the
    same review semantics.
    """

    try:
        return _llm_review_record(record)
    except (LLMError, ValueError, json.JSONDecodeError) as exc:
        return _template_review_for_record(record, reason=str(exc))


def review_performance(state: XHSState) -> dict:
    topic = state.get("user_topic", "未命名主题")
    content_type = state.get("content_type", "unknown")
    content_format = state.get("content_format", "unknown")
    publish_status = state.get("publish_status", "pending")

    performance_data = state.get("performance_data") or EMPTY_PERFORMANCE.copy()

    if publish_status == "success" and _has_performance_data(performance_data):
        record_like_state = {
            "topic": topic,
            "target_user": state.get("target_user"),
            "title": (state.get("titles") or [topic])[0],
            "content_type": content_type,
            "content_format": content_format,
            "pain_points": state.get("pain_points"),
            "comment_insights": state.get("comment_insights"),
            "performance_data": performance_data,
        }
        review = build_operation_review(record_like_state)
        return {
            "performance_data": performance_data,
            "review_summary": review["review_summary"],
            "next_action": review["next_action"],
            "review_generation": review.get("review_generation"),
        }

    if publish_status == "success":
        review_summary = (
            f"主题「{topic}」的 {content_format} 草稿已生成，"
            f"内容类型为 {content_type}。当前还没有真实平台表现数据。"
        )
        next_action = "人工检查 Markdown 草稿，确认后手动发布，并在发布后录入表现数据。"
        reason = "No performance data available"
    else:
        review_summary = (
            f"主题「{topic}」尚未进入发布或保存环节，"
            "当前无法进行真实表现复盘。"
        )
        next_action = "先完成合规审核和人工确认，再生成待发布草稿。"
        reason = "Draft is not saved or published"

    return {
        "performance_data": performance_data,
        "review_summary": review_summary,
        "next_action": next_action,
        "review_generation": {
            "enabled": False,
            "provider_mode": "template",
            "model": None,
            "usage": {},
            "error": reason,
        },
    }
