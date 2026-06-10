"""JSON operation memory store for M3.

This is the first durable memory layer. It records generated drafts, manual
performance data, review summaries, and simple reusable patterns before the
project upgrades to GraphRAG.
"""

from __future__ import annotations

import hashlib
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.json_store import read_json_file, write_json_atomic
from app.rules import load_performance_weights


MEMORY_ROOT = Path(__file__).resolve().parent
HISTORY_PATH = MEMORY_ROOT / "operation_history.json"
HISTORY_VERSION = 1


EMPTY_HISTORY = {
    "version": HISTORY_VERSION,
    "updated_at": None,
    "records": [],
}


PERFORMANCE_WEIGHTS = load_performance_weights()
HISTORY_LOCK = threading.RLock()


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _safe_int(value: Any) -> int:
    if value is None or value == "":
        return 0
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def performance_score(performance_data: Dict[str, Any] | None) -> int:
    if not performance_data:
        return 0
    return sum(
        _safe_int(performance_data.get(name)) * weight
        for name, weight in PERFORMANCE_WEIGHTS.items()
    )


def has_performance_data(performance_data: Dict[str, Any] | None) -> bool:
    if not performance_data:
        return False
    return any(_safe_int(performance_data.get(name)) > 0 for name in PERFORMANCE_WEIGHTS)


def load_history(path: Path = HISTORY_PATH) -> Dict[str, Any]:
    with HISTORY_LOCK:
        data = read_json_file(path, default=EMPTY_HISTORY, expected_type=dict)

    if not isinstance(data, dict):
        return dict(EMPTY_HISTORY)

    records = data.get("records")
    if not isinstance(records, list):
        records = []

    return {
        "version": data.get("version") or HISTORY_VERSION,
        "updated_at": data.get("updated_at"),
        "records": records,
    }


def save_history(history: Dict[str, Any], path: Path = HISTORY_PATH) -> Path:
    with HISTORY_LOCK:
        history["version"] = HISTORY_VERSION
        history["updated_at"] = _now_iso()
        history.setdefault("records", [])
        return write_json_atomic(path, history)


def _record_id_from_post_id(post_id: str) -> str:
    digest = hashlib.sha1(post_id.encode("utf-8")).hexdigest()[:12]
    return f"op_{digest}"


def _first_title(state: Dict[str, Any]) -> str:
    titles = state.get("titles") or []
    if isinstance(titles, list) and titles:
        return str(titles[0])
    return str(state.get("user_topic") or "未命名内容")


def _compact_pain_points(pain_points: Any, limit: int = 5) -> List[Dict[str, Any]]:
    if not isinstance(pain_points, list):
        return []

    compacted = []
    for item in pain_points[:limit]:
        if isinstance(item, dict):
            compacted.append(
                {
                    "pain": str(item.get("pain") or ""),
                    "evidence": str(item.get("evidence") or ""),
                    "priority": item.get("priority"),
                }
            )
        else:
            compacted.append({"pain": str(item), "evidence": "", "priority": None})
    return compacted


def _compact_comment_insights(comment_insights: Any, limit: int = 5) -> List[Dict[str, Any]]:
    if not isinstance(comment_insights, list):
        return []

    compacted = []
    for item in comment_insights[:limit]:
        if not isinstance(item, dict):
            continue
        evidence_comments = item.get("evidence_comments") or []
        if not isinstance(evidence_comments, list):
            evidence_comments = []
        compacted.append(
            {
                "pain": str(item.get("pain") or ""),
                "evidence_comments": [str(comment) for comment in evidence_comments[:3]],
                "evidence_count": item.get("evidence_count"),
                "priority": item.get("priority"),
            }
        )
    return compacted


def record_from_state(state: Dict[str, Any]) -> Dict[str, Any]:
    post_id = str(state.get("post_id") or "").strip()
    record_id = _record_id_from_post_id(post_id or _now_iso())
    performance_data = state.get("performance_data") or {}

    return {
        "record_id": record_id,
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
        "status": "draft_saved" if post_id else "draft_pending",
        "topic": str(state.get("user_topic") or ""),
        "target_user": str(state.get("target_user") or ""),
        "account_stage": state.get("account_stage"),
        "content_type": state.get("content_type"),
        "content_format": state.get("content_format"),
        "title": _first_title(state),
        "titles": [str(item) for item in state.get("titles") or []],
        "post_id": post_id or None,
        "publish_status": state.get("publish_status"),
        "publish_time": state.get("publish_time"),
        "collection_path": state.get("collection_path"),
        "pain_points": _compact_pain_points(state.get("pain_points")),
        "comment_insights": _compact_comment_insights(state.get("comment_insights")),
        "performance_data": performance_data,
        "performance_score": performance_score(performance_data),
        "review_summary": state.get("review_summary") or "",
        "next_action": state.get("next_action") or "",
        "review_generation": state.get("review_generation") or {},
    }


def upsert_record_from_state(state: Dict[str, Any], path: Path = HISTORY_PATH) -> Dict[str, Any]:
    with HISTORY_LOCK:
        history = load_history(path)
        records = history.setdefault("records", [])
        new_record = record_from_state(state)
        post_id = new_record.get("post_id")

        existing_index: Optional[int] = None
        if post_id:
            for index, record in enumerate(records):
                if isinstance(record, dict) and record.get("post_id") == post_id:
                    existing_index = index
                    break

        if existing_index is None:
            records.append(new_record)
            saved_record = new_record
        else:
            existing = records[existing_index]
            created_at = existing.get("created_at") if isinstance(existing, dict) else None
            merged = {**existing, **new_record}
            merged["created_at"] = created_at or new_record["created_at"]
            merged["updated_at"] = _now_iso()
            records[existing_index] = merged
            saved_record = merged

        save_history(history, path)
        return saved_record


def _topic_relevance(topic: str, record: Dict[str, Any]) -> int:
    topic = topic.strip()
    if not topic:
        return 0

    haystack_parts = [
        record.get("topic"),
        record.get("title"),
        record.get("content_type"),
        record.get("content_format"),
        record.get("review_summary"),
        record.get("next_action"),
    ]
    for pain in record.get("pain_points") or []:
        if isinstance(pain, dict):
            haystack_parts.append(pain.get("pain"))
            haystack_parts.append(pain.get("evidence"))

    haystack = " ".join(str(part or "") for part in haystack_parts)

    if topic and topic in haystack:
        return 100
    if record.get("topic") and str(record.get("topic")) in topic:
        return 80

    score = 0
    for char in set(topic):
        if char.strip() and char in haystack:
            score += 1
    return score


HEALTH_TOPIC_KEYWORDS = (
    "\u5b9d\u5b9d",  # baby
    "\u5a74\u513f",  # infant
    "\u5b69\u5b50",  # child
    "\u6e7f\u75b9",  # eczema
    "\u70ed\u75b9",  # heat rash
    "\u76ae\u75b9",  # rash
    "\u75b9\u5b50",  # rash
    "\u8fc7\u654f",  # allergy
    "\u53d1\u70e7",  # fever
    "\u9ad8\u70e7",  # high fever
    "\u533b\u751f",  # doctor
    "\u5c31\u533b",  # seek medical care
    "\u7528\u836f",  # medication
    "\u64e6\u836f",  # apply medicine
    "\u8bca\u65ad",  # diagnosis
    "\u6bcd\u4e73",  # breast milk
)


CROSS_DOMAIN_HEALTH_PATTERNS = (
    "\u5bf9\u62a4\u7406\u65b9\u6cd5\u5b58\u5728\u7591\u95ee",  # doubt nursing/care advice
    "\u62a4\u7406\u65b9\u5411",  # care direction
    "\u5b9d\u5b9d\u6e7f\u75b9",  # baby eczema
    "\u6e7f\u75b9",  # eczema
    "\u70ed\u75b9",  # heat rash
    "\u76ae\u75b9",  # rash
    "\u75b9\u5b50",  # rash
    "\u64e6\u836f",  # apply medicine
    "\u7528\u836f",  # medication
    "\u5c31\u533b",  # seek medical care
    "\u8bca\u65ad",  # diagnosis
    "\u4e0d\u66ff\u4ee3\u4e13\u4e1a\u8bca\u65ad",  # not medical diagnosis
)


def _topic_is_health_related(topic: str) -> bool:
    normalized = str(topic or "")
    return any(keyword in normalized for keyword in HEALTH_TOPIC_KEYWORDS)


def _iter_text_values(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        texts: List[str] = []
        for child in value.values():
            texts.extend(_iter_text_values(child))
        return texts
    if isinstance(value, list):
        texts = []
        for child in value:
            texts.extend(_iter_text_values(child))
        return texts
    return []


def _record_has_cross_domain_health_pollution(topic: str, record: Dict[str, Any]) -> bool:
    if _topic_is_health_related(topic):
        return False

    fields_to_scan = {
        "topic": record.get("topic"),
        "title": record.get("title"),
        "titles": record.get("titles"),
        "pain_points": record.get("pain_points"),
        "comment_insights": record.get("comment_insights"),
        "review_summary": record.get("review_summary"),
        "next_action": record.get("next_action"),
    }
    haystack = " ".join(_iter_text_values(fields_to_scan))
    return any(pattern in haystack for pattern in CROSS_DOMAIN_HEALTH_PATTERNS)


def find_relevant_records(topic: str, limit: int = 5, path: Path = HISTORY_PATH) -> List[Dict[str, Any]]:
    history = load_history(path)
    scored_records = []
    for record in history.get("records") or []:
        if not isinstance(record, dict):
            continue
        if _record_has_cross_domain_health_pollution(topic, record):
            continue
        relevance = _topic_relevance(topic, record)
        if relevance <= 0:
            continue
        scored_records.append((relevance, performance_score(record.get("performance_data")), record))

    scored_records.sort(
        key=lambda item: (item[0], item[1], str(item[2].get("updated_at") or "")),
        reverse=True,
    )
    return [item[2] for item in scored_records[:limit]]


def successful_patterns_from_records(records: List[Dict[str, Any]], limit: int = 3) -> List[Dict[str, Any]]:
    candidates = []
    for record in records:
        if not isinstance(record, dict):
            continue
        score = performance_score(record.get("performance_data"))
        if score <= 0:
            continue
        candidates.append((score, record))

    candidates.sort(key=lambda item: item[0], reverse=True)

    patterns = []
    for score, record in candidates[:limit]:
        patterns.append(
            {
                "record_id": record.get("record_id"),
                "topic": record.get("topic"),
                "title": record.get("title"),
                "content_type": record.get("content_type"),
                "content_format": record.get("content_format"),
                "performance_score": score,
                "performance_data": record.get("performance_data") or {},
                "review_summary": record.get("review_summary") or "",
                "next_action": record.get("next_action") or "",
                "pain_points": record.get("pain_points") or [],
            }
        )
    return patterns


def find_successful_patterns(topic: str, limit: int = 3, path: Path = HISTORY_PATH) -> List[Dict[str, Any]]:
    records = find_relevant_records(topic, limit=20, path=path)
    return successful_patterns_from_records(records, limit=limit)


def build_review_summary(record: Dict[str, Any]) -> tuple[str, str]:
    review = build_review_result(record)
    return review["review_summary"], review["next_action"]


def _template_review_summary(record: Dict[str, Any]) -> tuple[str, str]:
    performance_data = record.get("performance_data") or {}
    score = performance_score(performance_data)
    title = record.get("title") or record.get("topic") or "未命名内容"

    if not has_performance_data(performance_data):
        return (
            f"《{title}》已进入运营记忆，但还没有录入真实表现数据。",
            "发布后录入曝光、点赞、收藏、评论和关注数据，再判断是否值得复用。",
        )

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
    return review_summary, next_action


def build_review_result(record: Dict[str, Any]) -> Dict[str, Any]:
    try:
        from nodes.review_node import build_operation_review

        return build_operation_review(record)
    except Exception as exc:
        review_summary, next_action = _template_review_summary(record)
        return {
            "review_summary": review_summary,
            "next_action": next_action,
            "review_generation": {
                "enabled": False,
                "provider_mode": "template",
                "model": None,
                "usage": {},
                "error": str(exc),
            },
        }


def update_record_performance(
    post_id: str,
    performance_data: Dict[str, Any],
    published_url: str | None = None,
    notes: str | None = None,
    path: Path = HISTORY_PATH,
) -> Dict[str, Any]:
    with HISTORY_LOCK:
        history = load_history(path)
        records = history.setdefault("records", [])

        target = None
        for record in records:
            if isinstance(record, dict) and record.get("post_id") == post_id:
                target = record
                break

        if target is None:
            raise ValueError(f"No operation memory record found for post_id: {post_id}")

        clean_performance = {
            "views": _safe_int(performance_data.get("views")),
            "likes": _safe_int(performance_data.get("likes")),
            "collects": _safe_int(performance_data.get("collects")),
            "comments": _safe_int(performance_data.get("comments")),
            "follows": _safe_int(performance_data.get("follows")),
        }

        target["performance_data"] = clean_performance
        target["performance_score"] = performance_score(clean_performance)
        target["status"] = "performance_recorded"
        target["updated_at"] = _now_iso()
        if published_url:
            target["published_url"] = published_url
        if notes:
            target["operator_notes"] = notes

        review = build_review_result(target)
        target["review_summary"] = review["review_summary"]
        target["next_action"] = review["next_action"]
        target["review_generation"] = review.get("review_generation")

        save_history(history, path)
        return target
