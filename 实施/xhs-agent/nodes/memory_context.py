"""Compact GraphRAG-style memory for downstream strategy and generation."""

from __future__ import annotations

from typing import Any

from app.rules import load_content_rules
from app.state import XHSState


_CONTENT_RULES = load_content_rules()
VALID_CONTENT_TYPES = set(_CONTENT_RULES.get("valid_content_types") or [])


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _safe_float(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _memory(state: XHSState) -> dict[str, Any]:
    return _as_dict(state.get("graphrag_memory"))


def _evidence_items(memory: dict[str, Any]) -> list[Any]:
    evidence = _as_list(memory.get("recall_evidence"))
    if evidence:
        return evidence
    return _as_list(memory.get("related_records"))


def has_memory_evidence(state: XHSState) -> bool:
    return bool(_evidence_items(_memory(state)))


def recommended_memory_content_type(state: XHSState, min_evidence_count: int = 1) -> str | None:
    memory = _memory(state)
    if len(_evidence_items(memory)) < min_evidence_count:
        return None

    for item in _as_list(memory.get("recommended_content_types")):
        item_dict = _as_dict(item)
        content_type = str(item_dict.get("content_type") or "")
        if content_type not in VALID_CONTENT_TYPES:
            continue
        if _safe_int(item_dict.get("count")) <= 0 and _safe_int(item_dict.get("max_score")) <= 0:
            continue
        return content_type
    return None


def _compact_recommendations(memory: dict[str, Any], limit: int) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for item in _as_list(memory.get("recommended_content_types")):
        item_dict = _as_dict(item)
        content_type = str(item_dict.get("content_type") or "")
        if content_type not in VALID_CONTENT_TYPES:
            continue
        result.append(
            {
                "content_type": content_type,
                "count": _safe_int(item_dict.get("count")),
                "average_score": round(_safe_float(item_dict.get("average_score")), 2),
                "max_score": _safe_int(item_dict.get("max_score")),
            }
        )
    return result[: max(0, int(limit))]


def _compact_pain_points(memory: dict[str, Any], limit: int) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for item in _as_list(memory.get("related_pain_points")):
        item_dict = _as_dict(item)
        pain = str(item_dict.get("pain") or "").strip()
        if not pain:
            continue
        result.append(
            {
                "pain": pain,
                "count": _safe_int(item_dict.get("count")),
                "max_score": _safe_int(item_dict.get("max_score")),
            }
        )
    return result[: max(0, int(limit))]


def _compact_evidence(memory: dict[str, Any], limit: int) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for item in _evidence_items(memory):
        item_dict = _as_dict(item)
        record_id = str(item_dict.get("record_id") or "").strip()
        title = str(item_dict.get("title") or "").strip()
        topic = str(item_dict.get("topic") or "").strip()
        if not record_id and not title and not topic:
            continue
        result.append(
            {
                "record_id": record_id,
                "topic": topic,
                "title": title,
                "content_type": str(item_dict.get("content_type") or ""),
                "performance_score": _safe_int(item_dict.get("performance_score")),
            }
        )
    return result[: max(0, int(limit))]


def _compact_similar_experiences(memory: dict[str, Any], limit: int) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for item in _as_list(memory.get("similar_experience_records")):
        item_dict = _as_dict(item)
        record_id = str(item_dict.get("record_id") or "").strip()
        title = str(item_dict.get("title") or "").strip()
        topic = str(item_dict.get("topic") or "").strip()
        if not record_id and not title and not topic:
            continue
        result.append(
            {
                "record_id": record_id,
                "topic": topic,
                "title": title,
                "content_type": str(item_dict.get("content_type") or ""),
                "performance_score": _safe_int(item_dict.get("performance_score")),
                "reason": str(item_dict.get("reason") or ""),
            }
        )
    return result[: max(0, int(limit))]


def _compact_semantic_recall(memory: dict[str, Any], limit: int) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for item in _as_list(memory.get("semantic_recall_records")):
        item_dict = _as_dict(item)
        record_id = str(item_dict.get("record_id") or "").strip()
        title = str(item_dict.get("title") or "").strip()
        topic = str(item_dict.get("topic") or "").strip()
        if not record_id and not title and not topic:
            continue
        result.append(
            {
                "record_id": record_id,
                "topic": topic,
                "title": title,
                "content_type": str(item_dict.get("content_type") or ""),
                "performance_score": _safe_int(item_dict.get("performance_score")),
                "embedding_model": str(item_dict.get("embedding_model") or ""),
                "embedding_dimensions": _safe_int(item_dict.get("embedding_dimensions")),
                "semantic_score": round(_safe_float(item_dict.get("semantic_score")), 4),
                "reason": str(item_dict.get("reason") or ""),
            }
        )
    return result[: max(0, int(limit))]


def _compact_compliance_risks(memory: dict[str, Any], limit: int) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for item in _as_list(memory.get("historical_compliance_risks")):
        item_dict = _as_dict(item)
        record_id = str(item_dict.get("record_id") or "").strip()
        reason = str(item_dict.get("reason") or "").strip()
        if not record_id and not reason:
            continue
        issues = [str(issue) for issue in _as_list(item_dict.get("issues")) if str(issue).strip()]
        result.append(
            {
                "record_id": record_id,
                "risk_level": str(item_dict.get("risk_level") or ""),
                "issues": issues,
                "reason": reason,
            }
        )
    return result[: max(0, int(limit))]


def _compact_recall_explanations(memory: dict[str, Any], limit: int) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for item in _as_list(memory.get("recall_explanations")):
        item_dict = _as_dict(item)
        explanation_type = str(item_dict.get("type") or "").strip()
        record_id = str(item_dict.get("record_id") or "").strip()
        reason = str(item_dict.get("reason") or "").strip()
        matched_terms = [str(term) for term in _as_list(item_dict.get("matched_terms")) if str(term).strip()]
        matched_fields = [str(field) for field in _as_list(item_dict.get("matched_fields")) if str(field).strip()]
        if not explanation_type and not record_id and not reason and not matched_terms:
            continue
        compact = {
            "type": explanation_type,
            "record_id": record_id,
            "matched_terms": matched_terms[:5],
            "matched_fields": matched_fields[:5],
            "reason": reason,
        }
        if explanation_type == "semantic_recall":
            compact.update(
                {
                    "embedding_model": str(item_dict.get("embedding_model") or ""),
                    "embedding_dimensions": _safe_int(item_dict.get("embedding_dimensions")),
                    "semantic_score": round(_safe_float(item_dict.get("semantic_score")), 4),
                }
            )
        result.append(compact)
    return result[: max(0, int(limit))]


def build_generation_memory_context(state: XHSState, limit: int = 3) -> dict[str, Any]:
    memory = _memory(state)
    recommendations = _compact_recommendations(memory, limit)
    pain_points = _compact_pain_points(memory, limit)
    evidence = _compact_evidence(memory, limit)
    similar_experiences = _compact_similar_experiences(memory, limit)
    semantic_recall = _compact_semantic_recall(memory, limit)
    compliance_risks = _compact_compliance_risks(memory, limit)
    explanations = _compact_recall_explanations(memory, limit)
    enabled = bool(
        recommendations
        or pain_points
        or evidence
        or similar_experiences
        or semantic_recall
        or compliance_risks
        or explanations
    )

    return {
        "enabled": enabled,
        "query": str(memory.get("query") or "") if enabled else "",
        "recommended_content_types": recommendations,
        "related_pain_points": pain_points,
        "recall_evidence": evidence,
        "semantic_recall_records": semantic_recall,
        "similar_experience_records": similar_experiences,
        "historical_compliance_risks": compliance_risks,
        "recall_explanations": explanations,
    }
