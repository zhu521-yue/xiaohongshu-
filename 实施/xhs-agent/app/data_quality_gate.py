"""Deterministic RAG eligibility gate for collected run data."""

from __future__ import annotations

from typing import Any

from app.rules import load_data_quality_rules


def _to_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _rag_rules() -> dict[str, Any]:
    rules = load_data_quality_rules().get("rag_gate")
    return rules if isinstance(rules, dict) else {}


def _selected_count(state: dict[str, Any], sample_selection: dict[str, Any]) -> int:
    selected_count = _to_int(sample_selection.get("selected_count"))
    if selected_count > 0:
        return selected_count
    return sum(
        1
        for item in _list(state.get("collection_candidates"))
        if isinstance(item, dict) and item.get("selected")
    )


def _evidence_count(state: dict[str, Any], comment_quality: dict[str, Any]) -> int:
    evidence_count = _to_int(comment_quality.get("evidence_count"))
    if evidence_count > 0:
        return evidence_count
    count = 0
    for insight in _list(state.get("comment_insights")):
        if not isinstance(insight, dict):
            continue
        comments = _list(insight.get("evidence_comments"))
        count += len(comments) or _to_int(insight.get("evidence_count"))
    return count


def evaluate_rag_eligibility(state: dict[str, Any]) -> dict[str, Any]:
    rules = _rag_rules()
    analysis_report = _dict(state.get("analysis_report"))
    sample_selection = _dict(analysis_report.get("sample_selection"))
    comment_quality = _dict(analysis_report.get("comment_quality"))
    confidence = _dict(analysis_report.get("pain_point_confidence"))

    selected_count = _selected_count(state, sample_selection)
    raw_comments_count = _to_int(comment_quality.get("raw_comments_count")) or len(_list(state.get("raw_comments")))
    evidence_count = _evidence_count(state, comment_quality)

    comment_errors = _list(state.get("comment_fetch_errors"))
    penalty = _to_int(rules.get("comment_fetch_error_penalty"))
    score = max(0, min(100, _to_int(confidence.get("score")) - (penalty if comment_errors else 0)))

    blocking_reasons: list[str] = []
    reasons: list[str] = []

    if selected_count < _to_int(rules.get("min_selected_candidates")):
        blocking_reasons.append("入选候选不足")
    else:
        reasons.append("已有入选候选")

    if raw_comments_count < _to_int(rules.get("min_raw_comments")):
        blocking_reasons.append("评论样本较少")
    else:
        reasons.append("评论样本达到最低要求")

    if evidence_count < _to_int(rules.get("min_evidence_count")):
        blocking_reasons.append("痛点证据不足")
    else:
        reasons.append("痛点证据达到最低要求")

    if score < _to_int(rules.get("min_score")):
        blocking_reasons.append("痛点可信度分数不足")

    if comment_errors:
        reasons.append("部分评论抓取失败")
        if bool(rules.get("block_on_comment_fetch_errors")):
            blocking_reasons.append("评论抓取失败")

    eligible = not blocking_reasons
    return {
        "eligible": eligible,
        "level": "eligible" if eligible else "blocked",
        "score": score,
        "reasons": reasons,
        "blocking_reasons": blocking_reasons,
        "recommended_action": (
            "可以进入后续 RAG 入库候选。"
            if eligible
            else "重新采集更多候选和评论后再进入 RAG 入库。"
        ),
    }
