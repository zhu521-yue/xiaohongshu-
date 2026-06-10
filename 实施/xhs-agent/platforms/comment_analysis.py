"""Rule-based comment insight extraction for M2.

This module turns raw comment samples into pain clusters with concrete
evidence comments. It stays deterministic before we introduce an LLM, so the
collector can be tested and explained step by step.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List

from app.rules import load_comment_insight_rules

_COMMENT_RULES = load_comment_insight_rules()
GENERIC_INSIGHT_RULES = list(_COMMENT_RULES.get("generic_insight_rules") or [])
DOMAIN_RULE_GROUPS = list(_COMMENT_RULES.get("domain_rule_groups") or [])


def _comment_text(comment: Dict[str, Any]) -> str:
    return str(comment.get("content") or "").strip()


QUESTION_OR_NEED_MARKERS = tuple(_COMMENT_RULES.get("question_or_need_markers") or [])
SYMPTOM_MARKERS = tuple(_COMMENT_RULES.get("symptom_markers") or [])
SOLUTION_STYLE_MARKERS = tuple(_COMMENT_RULES.get("solution_style_markers") or [])
NOISE_COMMENT_KEYWORDS = tuple(_COMMENT_RULES.get("noise_comment_keywords") or [])
LOW_VALUE_COMMENTS = {str(item).strip().lower() for item in _COMMENT_RULES.get("low_value_comments") or []}


def _normalize_comment(text: str) -> str:
    return re.sub(r"\s+", "", text).strip().lower()


def _is_noise_comment(text: str) -> bool:
    normalized = _normalize_comment(text)
    if not normalized:
        return True
    if normalized in LOW_VALUE_COMMENTS:
        return True
    if re.fullmatch(r"[\d+＋.。!！?？~～\s]+", text):
        return True
    return any(_normalize_comment(keyword) in normalized for keyword in NOISE_COMMENT_KEYWORDS)


def is_noise_comment_text(text: str) -> bool:
    return _is_noise_comment(text)


def _format_pain(rule: Dict[str, Any], topic: str) -> str:
    template = str(rule.get("pain_template") or rule.get("pain") or "").strip()
    return template.format(topic=topic) if template else f"用户围绕「{topic}」存在未归类困惑"


def _domain_matches(topic: str, group: Dict[str, Any]) -> bool:
    topic_keywords = group.get("topic_keywords") or []
    return any(str(keyword) and str(keyword) in topic for keyword in topic_keywords)


def _active_rules(topic: str) -> List[Dict[str, Any]]:
    rules: List[Dict[str, Any]] = []
    for group in DOMAIN_RULE_GROUPS:
        if not isinstance(group, dict) or not _domain_matches(topic, group):
            continue
        rules.extend(rule for rule in group.get("insight_rules") or [] if isinstance(rule, dict))
    rules.extend(rule for rule in GENERIC_INSIGHT_RULES if isinstance(rule, dict))
    return rules


def _evidence_score(text: str) -> int:
    score = 0
    if any(marker in text for marker in QUESTION_OR_NEED_MARKERS):
        score += 4
    if "？" in text or "?" in text:
        score += 3
    if any(marker in text for marker in SYMPTOM_MARKERS):
        score += 2
    if len(text) >= 60 and score > 0:
        score += 1
    if any(marker in text for marker in SOLUTION_STYLE_MARKERS):
        score -= 4
    return score


def _select_evidence(
    rule: Dict[str, Any],
    raw_comments: List[Dict[str, Any]],
    max_evidence: int,
    excluded_texts: set[str] | None = None,
) -> List[str]:
    candidates = []
    excluded_texts = excluded_texts or set()
    keywords = [str(keyword) for keyword in rule.get("keywords") or []]

    for index, comment in enumerate(raw_comments):
        text = _comment_text(comment)
        if not text or text in excluded_texts or _is_noise_comment(text):
            continue
        if any(keyword in text for keyword in keywords):
            score = _evidence_score(text)
            if score < -2:
                continue
            candidates.append((score, index, text))

    if not candidates:
        return []

    preferred_candidates = [item for item in candidates if item[0] >= 0]
    ranked_candidates = preferred_candidates or candidates
    ranked_candidates.sort(key=lambda item: (-item[0], item[1]))

    evidence = []
    used_texts = set()
    for _, _, text in ranked_candidates:
        if text in used_texts:
            continue
        evidence.append(text)
        used_texts.add(text)
        if len(evidence) >= max_evidence:
            break

    return evidence


def extract_comment_insights(
    topic: str,
    raw_comments: List[Dict[str, Any]],
    max_evidence_per_insight: int = 3,
) -> List[Dict[str, Any]]:
    insights: List[Dict[str, Any]] = []
    used_comments: set[str] = set()

    for rule in _active_rules(topic):
        evidence = _select_evidence(
            rule,
            raw_comments,
            max_evidence_per_insight,
            excluded_texts=used_comments,
        )
        for text in evidence:
            used_comments.add(text)

        if evidence:
            insights.append(
                {
                    "pain": _format_pain(rule, topic),
                    "evidence_comments": evidence,
                    "evidence_count": len(evidence),
                    "priority": len(insights) + 1,
                }
            )

    unmatched = []
    for comment in raw_comments:
        text = _comment_text(comment)
        if text and text not in used_comments and not _is_noise_comment(text):
            unmatched.append(text)
        if len(unmatched) >= max_evidence_per_insight:
            break

    if not insights and unmatched:
        insights.append(
            {
                "pain": f"用户围绕「{topic}」需要更具体的判断和操作建议",
                "evidence_comments": unmatched,
                "evidence_count": len(unmatched),
                "priority": 1,
            }
        )

    return insights


def insights_to_pain_points(
    topic: str,
    comment_insights: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    if not comment_insights:
        return [
            {
                "pain": f"需要更具体、可执行的「{topic}」经验说明",
                "evidence": "当前采集评论较少，先使用主题级默认痛点",
                "priority": 1,
            }
        ]

    pain_points = []
    for index, insight in enumerate(comment_insights, start=1):
        evidence_comments = insight.get("evidence_comments") or []
        evidence_text = "；".join(str(item) for item in evidence_comments[:2])
        pain_points.append(
            {
                "pain": str(insight.get("pain") or ""),
                "evidence": evidence_text or f"评论围绕「{topic}」展开",
                "priority": index,
            }
        )
    return pain_points
