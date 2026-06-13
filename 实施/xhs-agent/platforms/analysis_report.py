"""Deterministic collection analysis report helpers."""

from __future__ import annotations

from typing import Any


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _to_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _candidate_title(candidate: dict[str, Any]) -> str:
    return str(candidate.get("title") or "").strip()


def _selected_candidates(candidates: list[Any]) -> list[dict[str, Any]]:
    return [item for item in candidates if isinstance(item, dict) and item.get("selected")]


def _evidence_count(comment_insights: list[Any]) -> int:
    count = 0
    for insight in comment_insights:
        if not isinstance(insight, dict):
            continue
        comments = insight.get("evidence_comments")
        if isinstance(comments, list):
            count += len(comments)
            continue
        count += _to_int(insight.get("evidence_count"))
    return count


def _comment_quality_level(raw_comments_count: int, evidence_count: int, has_errors: bool) -> str:
    if raw_comments_count >= 20 and evidence_count >= 5 and not has_errors:
        return "high"
    if raw_comments_count >= 5 and evidence_count >= 2:
        return "medium"
    return "low"


def _confidence_score(
    *,
    evidence_count: int,
    pain_point_count: int,
    selected_count: int,
    has_errors: bool,
    candidate_count: int,
    raw_comments_count: int,
) -> int:
    score = min(evidence_count * 12, 48)
    score += min(pain_point_count * 10, 30)
    score += min(selected_count * 6, 18)
    if has_errors:
        score -= 15
    score = max(0, min(score, 100))
    if candidate_count <= 0 or raw_comments_count <= 0:
        score = min(score, 45)
    return score


def _confidence_level(score: int) -> str:
    if score >= 70:
        return "high"
    if score >= 45:
        return "medium"
    return "low"


def _question_count(comment_insights: list[Any], raw_comments: list[Any]) -> int:
    texts: list[str] = []
    for insight in comment_insights:
        if isinstance(insight, dict):
            texts.extend(str(item) for item in _as_list(insight.get("evidence_comments")))
    for comment in raw_comments:
        if isinstance(comment, dict):
            texts.append(str(comment.get("content") or ""))
    return sum(text.count("?") + text.count("？") for text in texts)


def _combined_text(
    topic: str,
    candidates: list[Any],
    raw_notes: list[Any],
    comment_insights: list[Any],
    pain_points: list[Any],
) -> str:
    chunks = [topic]
    for candidate in candidates:
        if isinstance(candidate, dict):
            chunks.append(str(candidate.get("title") or ""))
    for note in raw_notes:
        if isinstance(note, dict):
            chunks.append(str(note.get("title") or ""))
            chunks.append(str(note.get("desc") or ""))
    for insight in comment_insights:
        if isinstance(insight, dict):
            chunks.append(str(insight.get("pain") or ""))
            chunks.extend(str(item) for item in _as_list(insight.get("evidence_comments")))
    for pain in pain_points:
        if isinstance(pain, dict):
            chunks.append(str(pain.get("pain") or ""))
            chunks.append(str(pain.get("evidence") or ""))
    return " ".join(chunks)


def _content_structure_hint(
    topic: str,
    candidates: list[Any],
    raw_notes: list[Any],
    comment_insights: list[Any],
    pain_points: list[Any],
    raw_comments: list[Any],
) -> dict[str, str]:
    text = _combined_text(topic, candidates, raw_notes, comment_insights, pain_points)
    if any(marker in text for marker in ("坑", "避开", "误区")):
        return {
            "recommended_type": "avoid_mistakes",
            "reason": "样本和痛点中出现避坑或误区信号，适合用避坑结构降低理解成本。",
        }
    if _question_count(comment_insights, raw_comments) >= 2 or "问题" in text:
        return {
            "recommended_type": "qa_education",
            "reason": "评论证据中提问较多，适合用问答结构集中回应用户疑问。",
        }
    if any(marker in text for marker in ("步骤", "怎么", "方法", "从哪里开始")):
        return {
            "recommended_type": "step_tutorial",
            "reason": "评论和样本中出现步骤、方法或起步困惑，适合用步骤教程结构。",
        }
    return {
        "recommended_type": "knowledge_share",
        "reason": "当前样本更适合先做知识分享，帮助用户建立基础判断。",
    }


def _risks(
    *,
    candidate_count: int,
    raw_comments_count: int,
    evidence_count: int,
    has_errors: bool,
) -> list[str]:
    risks: list[str] = []
    if candidate_count <= 0:
        risks.append("候选池为空")
    elif candidate_count < 3:
        risks.append("候选样本较少")
    if raw_comments_count < 5:
        risks.append("评论样本较少")
    if evidence_count < 2:
        risks.append("痛点证据不足")
    if has_errors:
        risks.append("部分评论抓取失败")
    return risks


def build_analysis_report(
    *,
    topic: str,
    collection_candidates: list[dict[str, Any]] | None = None,
    raw_notes: list[dict[str, Any]] | None = None,
    raw_comments: list[dict[str, Any]] | None = None,
    comment_insights: list[dict[str, Any]] | None = None,
    pain_points: list[dict[str, Any]] | None = None,
    comment_fetch_errors: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    candidates = _as_list(collection_candidates)
    notes = _as_list(raw_notes)
    comments = _as_list(raw_comments)
    insights = _as_list(comment_insights)
    pains = _as_list(pain_points)
    errors = _as_list(comment_fetch_errors)

    selected = _selected_candidates(candidates)
    selected_titles = [_candidate_title(candidate) for candidate in selected if _candidate_title(candidate)]
    scores = [_to_int(candidate.get("score")) for candidate in candidates if isinstance(candidate, dict)]
    candidate_count = len(candidates)
    selected_count = len(selected)
    raw_comments_count = len(comments)
    evidence_count = _evidence_count(insights)
    pain_point_count = len(pains)
    has_errors = bool(errors)

    quality_level = _comment_quality_level(raw_comments_count, evidence_count, has_errors)
    confidence_score = _confidence_score(
        evidence_count=evidence_count,
        pain_point_count=pain_point_count,
        selected_count=selected_count,
        has_errors=has_errors,
        candidate_count=candidate_count or len(notes),
        raw_comments_count=raw_comments_count,
    )
    confidence_level = _confidence_level(confidence_score)
    risks = _risks(
        candidate_count=candidate_count,
        raw_comments_count=raw_comments_count,
        evidence_count=evidence_count,
        has_errors=has_errors,
    )

    if selected_count:
        selection_reason = f"从 {candidate_count} 个候选中选出 {selected_count} 个高相关样本。"
    elif candidate_count:
        selection_reason = f"候选池有 {candidate_count} 个样本，但没有明确入选标记。"
    else:
        selection_reason = "当前没有候选池数据，样本来源可信度较低。"

    if quality_level == "high":
        quality_reason = "评论样本和痛点证据都较充足。"
    elif quality_level == "medium":
        quality_reason = "评论样本可用，但仍需要更多证据提升稳定性。"
    else:
        quality_reason = "评论或证据样本不足，适合先低置信度使用。"

    if confidence_level == "high":
        confidence_reason = "痛点有多条评论证据和入选样本支撑。"
    elif confidence_level == "medium":
        confidence_reason = "痛点有一定证据支撑，但仍需补充样本。"
    else:
        confidence_reason = "痛点主要依赖少量评论或兜底信息。"

    return {
        "sample_selection": {
            "candidate_count": candidate_count,
            "selected_count": selected_count,
            "top_score": max(scores) if scores else 0,
            "selected_titles": selected_titles[:5],
            "selection_reason": selection_reason,
        },
        "comment_quality": {
            "raw_comments_count": raw_comments_count,
            "insight_count": len(insights),
            "pain_point_count": pain_point_count,
            "evidence_count": evidence_count,
            "quality_level": quality_level,
            "quality_reason": quality_reason,
        },
        "pain_point_confidence": {
            "level": confidence_level,
            "score": confidence_score,
            "reason": confidence_reason,
        },
        "content_structure_hint": _content_structure_hint(topic, candidates, notes, insights, pains, comments),
        "risks": risks,
        "summary": (
            f"候选 {candidate_count} 个，入选 {selected_count} 个，评论质量 {quality_level}，"
            f"痛点可信度 {confidence_level}。"
        ),
    }
