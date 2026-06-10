"""Generate short-video scripts.

The node prefers structured LLM output and falls back to the original template
logic when the model is unavailable or returns invalid JSON.
"""

from __future__ import annotations

import json
import re
from typing import Any

from app.config import load_settings
from app.rules import load_text_replacement_rules
from app.state import XHSState
from llm.client import LLMError, get_llm_client
from llm.prompts import build_json_prompt
from nodes.compliance_node import ABSOLUTE_WORDS, AVOID_PROMISE_WORDS, SAFETY_NOTE, SENSITIVE_TOPICS
from nodes.pattern_utils import structure_profile, successful_patterns


_TEXT_REPLACEMENT_RULES = load_text_replacement_rules()
PHRASE_REPLACEMENTS = dict(_TEXT_REPLACEMENT_RULES.get("phrase_replacements") or {})
ABSOLUTE_WORD_REPLACEMENTS = dict(_TEXT_REPLACEMENT_RULES.get("absolute_word_replacements") or {})
QUALITY_WORD_REPLACEMENTS = dict(_TEXT_REPLACEMENT_RULES.get("quality_word_replacements") or {})

REQUIRED_VIDEO_SCRIPT_FIELDS = {
    "title": str,
    "hook": str,
    "duration": str,
    "opening": str,
    "talking_points": list,
    "shot_plan": list,
    "subtitle_plan": list,
    "cover_text": str,
    "compliance_note": str,
}


def _format_pain_points(state: XHSState) -> list[str]:
    pain_points = state.get("pain_points") or []
    if not isinstance(pain_points, list):
        return [str(pain_points)]

    result = []
    for item in pain_points:
        if isinstance(item, dict):
            result.append(str(item.get("pain", "")))
        else:
            result.append(str(item))

    return [item for item in result if item]


def _format_comment_insights(state: XHSState) -> list[dict]:
    insights = state.get("comment_insights") or []
    if not isinstance(insights, list):
        return []

    result = []
    for item in insights:
        if not isinstance(item, dict):
            continue
        pain = str(item.get("pain") or "").strip()
        evidence_comments = item.get("evidence_comments") or []
        if not isinstance(evidence_comments, list):
            evidence_comments = []
        evidence_comments = [
            str(comment).strip()
            for comment in evidence_comments
            if str(comment).strip()
        ]
        if pain:
            result.append({"pain": pain, "evidence_comments": evidence_comments})
    return result


def _first_evidence(insights: list[dict]) -> str:
    for insight in insights:
        comments = insight.get("evidence_comments") or []
        if comments:
            return str(comments[0])
    return ""


def _replace_risky_words(text: str) -> str:
    result = text
    for word, replacement in sorted(PHRASE_REPLACEMENTS.items(), key=lambda item: len(item[0]), reverse=True):
        result = result.replace(word, replacement)
    for word, replacement in sorted(ABSOLUTE_WORD_REPLACEMENTS.items(), key=lambda item: len(item[0]), reverse=True):
        result = result.replace(word, replacement)
    for word, replacement in sorted(QUALITY_WORD_REPLACEMENTS.items(), key=lambda item: len(item[0]), reverse=True):
        result = result.replace(word, replacement)
    return _normalize_generated_text_spacing(result)


def _normalize_generated_text_spacing(text: str) -> str:
    lines = [line.strip() for line in text.splitlines()]
    result = "\n".join(lines)
    space_chars = r"[ \t\u00a0\u3000]+"
    result = re.sub(r"(?<=[\u4e00-\u9fff])[ \t\u00a0\u3000]{2,}(?=[\u4e00-\u9fff])", "，", result)
    result = re.sub(rf"(?<=[\u4e00-\u9fff]){space_chars}(?=[\u4e00-\u9fff])", "", result)
    result = re.sub(rf"{space_chars}([，。！？；：、])", r"\1", result)
    result = re.sub(rf"([，。！？；：、]){space_chars}(?=[\u4e00-\u9fff])", r"\1", result)
    return result


def _clean_generated_text(value: Any) -> Any:
    if isinstance(value, str):
        return _replace_risky_words(value).strip()
    if isinstance(value, list):
        return [_clean_generated_text(item) for item in value]
    if isinstance(value, dict):
        return {key: _clean_generated_text(item) for key, item in value.items()}
    return value


def _normalize_string_list(value: Any, min_items: int = 1) -> list[str]:
    if not isinstance(value, list):
        raise ValueError("expected list")
    result = [str(item).strip() for item in value if str(item).strip()]
    if len(result) < min_items:
        raise ValueError("list has too few items")
    return result


def _normalize_shot_plan(value: Any) -> list[dict]:
    if not isinstance(value, list):
        raise ValueError("shot_plan must be a list")

    shots = []
    for index, item in enumerate(value, start=1):
        if not isinstance(item, dict):
            raise ValueError("shot_plan item must be object")
        visual = str(item.get("visual") or "").strip()
        text = str(item.get("text") or "").strip()
        if not visual or not text:
            raise ValueError("shot_plan item missing visual/text")
        shots.append(
            {
                "scene": int(item.get("scene") or index),
                "visual": visual,
                "text": text,
            }
        )

    if len(shots) < 3:
        raise ValueError("shot_plan has too few items")
    return shots


def _validate_video_result(data: Any) -> dict:
    if not isinstance(data, dict):
        raise ValueError("LLM JSON root must be an object")

    script = data.get("video_script")
    if not isinstance(script, dict):
        raise ValueError("missing video_script object")

    for field, expected_type in REQUIRED_VIDEO_SCRIPT_FIELDS.items():
        if field not in script:
            raise ValueError(f"missing video_script field: {field}")
        if not isinstance(script[field], expected_type):
            raise ValueError(f"invalid video_script field type: {field}")

    result = {
        "video_script": {
            "title": str(script["title"]).strip(),
            "hook": str(script["hook"]).strip(),
            "duration": str(script["duration"]).strip(),
            "opening": str(script["opening"]).strip(),
            "talking_points": _normalize_string_list(script["talking_points"], min_items=3)[:5],
            "shot_plan": _normalize_shot_plan(script["shot_plan"])[:6],
            "subtitle_plan": _normalize_string_list(script["subtitle_plan"], min_items=3)[:6],
            "cover_text": str(script["cover_text"]).strip(),
            "compliance_note": str(script["compliance_note"]).strip(),
        },
        "tags": _normalize_string_list(data.get("tags"), min_items=3)[:10],
        "comment_call": str(data.get("comment_call") or "").strip(),
    }

    if not result["comment_call"]:
        raise ValueError("missing comment_call")
    return result


def _compact_profile(profile: dict) -> dict:
    return {
        "content_type": profile.get("content_type"),
        "label": profile.get("label"),
        "video_hook": profile.get("video_hook"),
        "video_points": profile.get("video_points"),
        "page_titles": profile.get("page_titles"),
        "cover_main": profile.get("cover_main"),
        "cover_sub": profile.get("cover_sub"),
    }


def _compact_successful_patterns(patterns: list[dict]) -> list[dict]:
    compacted = []
    for pattern in patterns[:3]:
        compacted.append(
            {
                "content_type": pattern.get("content_type"),
                "title": pattern.get("title"),
                "performance_score": pattern.get("performance_score"),
            }
        )
    return compacted


def _sensitive_source_text(state: XHSState) -> str:
    text_parts = [
        str(state.get("user_topic") or ""),
        str(state.get("target_user") or ""),
    ]
    text_parts.extend(_format_pain_points(state))
    for insight in _format_comment_insights(state):
        text_parts.append(str(insight.get("pain") or ""))
        text_parts.extend(str(comment) for comment in insight.get("evidence_comments") or [])
    return "\n".join(text_parts)


def _has_sensitive_context(state: XHSState) -> bool:
    text = _sensitive_source_text(state)
    return any(word in text for word in SENSITIVE_TOPICS)


def _has_generated_sensitive_claim(result: dict) -> bool:
    script = result.get("video_script") or {}
    text_parts = []
    if isinstance(script, dict):
        for value in script.values():
            text_parts.append(str(value))
    text_parts.append(" ".join(str(tag) for tag in result.get("tags") or []))
    text = "\n".join(text_parts)
    return any(word in text for word in SENSITIVE_TOPICS)


def _ensure_video_safety_note(state: XHSState, result: dict) -> dict:
    if not (_has_sensitive_context(state) or _has_generated_sensitive_claim(result)):
        return result

    script = dict(result.get("video_script") or {})
    note = str(script.get("compliance_note") or "")
    if SAFETY_NOTE not in note:
        script["compliance_note"] = f"{note} {SAFETY_NOTE}".strip() if note else SAFETY_NOTE
    result["video_script"] = script
    return result


def _build_video_prompt(
    state: XHSState,
    profile: dict,
    pain_points: list[str],
    comment_insights: list[dict],
    patterns: list[dict],
    primary_pain: str,
) -> list:
    topic = state["user_topic"]
    target_user = state.get("target_user") or "小红书目标用户"
    is_sensitive_topic = _has_sensitive_context(state)
    input_payload = {
        "topic": topic,
        "target_user": target_user,
        "content_type": profile.get("content_type"),
        "content_label": profile.get("label"),
        "primary_pain": primary_pain,
        "comment_insights": comment_insights[:5],
        "pain_points": pain_points[:5],
        "successful_patterns": _compact_successful_patterns(patterns),
        "preferred_structure": _compact_profile(profile),
        "forbidden_words": ABSOLUTE_WORDS,
        "avoid_promise_words": AVOID_PROMISE_WORDS,
        "is_sensitive_topic": is_sensitive_topic,
        "safety_note": SAFETY_NOTE if is_sensitive_topic else "",
    }

    return build_json_prompt("video_script_generation", input_payload)


def _llm_generate_video_script(
    state: XHSState,
    profile: dict,
    pain_points: list[str],
    comment_insights: list[dict],
    patterns: list[dict],
    primary_pain: str,
) -> dict:
    client = get_llm_client()
    if client.is_mock:
        raise LLMError("LLM is in mock mode")

    settings = load_settings()
    response = client.chat(
        messages=_build_video_prompt(
            state=state,
            profile=profile,
            pain_points=pain_points,
            comment_insights=comment_insights,
            patterns=patterns,
            primary_pain=primary_pain,
        ),
        temperature=0.4,
        max_tokens=settings.llm_video_max_tokens,
        response_format={"type": "json_object"},
    )
    data = json.loads(response.content)
    result = _validate_video_result(data)
    result = _clean_generated_text(result)
    result = _ensure_video_safety_note(state, result)
    result["content_type"] = profile.get("content_type")
    result["llm_generation"] = {
        "enabled": True,
        "provider_mode": response.provider_mode,
        "model": response.model,
        "usage": response.usage,
    }
    return result


def _template_generate_video_script(state: XHSState) -> dict:
    topic = state["user_topic"]
    target_user = state.get("target_user") or "小红书目标用户"
    content_type = state.get("content_type") or "knowledge_share"
    profile = structure_profile(state, content_type)
    pain_points = _format_pain_points(state)
    comment_insights = _format_comment_insights(state)
    base_talking_points = profile.get("video_points") or [
        "先说清楚最常见的误区",
        "再拆解正确处理顺序",
        "最后给出一个可执行的小清单",
    ]
    talking_points = list(base_talking_points)
    if comment_insights:
        talking_points = []
        for index, item in enumerate(comment_insights[:3]):
            prefix = base_talking_points[index] if index < len(base_talking_points) else "再补充一个问题"
            talking_points.append(f"{prefix}：{item['pain']}")
    elif pain_points:
        talking_points = []
        for index, pain in enumerate(pain_points[:3]):
            prefix = base_talking_points[index] if index < len(base_talking_points) else "再补充一个问题"
            talking_points.append(f"{prefix}：{pain}")

    primary_pain = talking_points[0] if talking_points else topic
    first_evidence = _first_evidence(comment_insights)

    hook_template = str(profile.get("video_hook") or "如果你也在纠结{topic}，先别急着照搬别人的方法。")
    hook = hook_template.format(
        topic=topic,
        primary_pain=primary_pain,
        first_evidence=first_evidence or primary_pain,
    )
    title_template = (profile.get("title_templates") or ["{topic}先别急着判断"])[0]
    title = str(title_template).format(topic=topic, primary_pain=primary_pain)
    page_titles = profile.get("page_titles") or ["先别急着判断", "评论高频问题", "判断顺序"]

    video_script = {
        "title": title,
        "hook": hook,
        "duration": "45-60s",
        "opening": f"很多{target_user}遇到{topic}时，真正卡住的是：{primary_pain}。",
        "talking_points": talking_points,
        "shot_plan": [
            {"scene": 1, "visual": "人物正面出镜", "text": f"{topic}{page_titles[0] if page_titles else '先别急着判断'}"},
            {"scene": 2, "visual": "列出评论高频问题", "text": primary_pain},
            {"scene": 3, "visual": "展示结构化清单", "text": page_titles[2] if len(page_titles) > 2 else "观察 → 判断 → 记录"},
        ],
        "subtitle_plan": [
            str(profile.get("cover_sub") or f"{topic}不要一上来就照搬").format(topic=topic, primary_pain=primary_pain),
            f"先看清楚：{primary_pain}",
            "再看反馈，下一次继续迭代",
        ],
        "cover_text": str(profile.get("cover_main") or "{topic}避坑提醒").format(topic=topic, primary_pain=primary_pain),
        "compliance_note": "内容仅作经验分享，具体情况建议结合自身实际判断。",
    }

    return {
        "content_type": profile.get("content_type"),
        "video_script": video_script,
        "tags": [topic, "小红书运营", "知识分享", "短视频脚本", str(profile.get("label") or "经验总结")],
        "comment_call": f"你在{topic}上最想先解决哪个问题？评论区告诉我。",
        "llm_generation": {
            "enabled": False,
            "provider_mode": "template",
            "model": None,
            "usage": {},
        },
    }


def generate_video_script(state: XHSState) -> dict:
    content_type = state.get("content_type") or "knowledge_share"
    profile = structure_profile(state, content_type)
    pain_points = _format_pain_points(state)
    comment_insights = _format_comment_insights(state)
    patterns = successful_patterns(state)
    topic = state["user_topic"]
    primary_pain = (
        comment_insights[0]["pain"]
        if comment_insights
        else (pain_points[0] if pain_points else topic)
    )

    try:
        return _llm_generate_video_script(
            state=state,
            profile=profile,
            pain_points=pain_points,
            comment_insights=comment_insights,
            patterns=patterns,
            primary_pain=primary_pain,
        )
    except (LLMError, ValueError, json.JSONDecodeError) as exc:
        fallback = _template_generate_video_script(state)
        fallback["llm_generation"] = {
            "enabled": False,
            "provider_mode": "fallback_template",
            "model": None,
            "usage": {},
            "error": str(exc),
        }
        return fallback
