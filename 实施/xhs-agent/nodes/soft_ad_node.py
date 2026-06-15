"""Soft-ad content generation node for stage 2.

Follows the same LLM-first + template-fallback pattern as content_node.py.
Generates image-text content that naturally embeds product information with
compliance disclaimers.
"""

from __future__ import annotations

import json
from typing import Any

from app.rules import load_content_rules, load_text_replacement_rules
from app.state import XHSState
from llm.client import LLMError, get_llm_client
from llm.prompts import build_json_prompt
from nodes.compliance_node import ABSOLUTE_WORDS, AVOID_PROMISE_WORDS
from nodes.memory_context import build_generation_memory_context


_CONTENT_RULES = load_content_rules()
_STRUCTURE_PROFILES = _CONTENT_RULES.get("structure_profiles") or {}
_SOFT_AD_PROFILE = _STRUCTURE_PROFILES.get("soft_ad") or {}

REQUIRED_FIELDS = {
    "titles": list,
    "cover_texts": list,
    "body": str,
    "image_page_plan": list,
    "image_prompts": list,
    "tags": list,
    "comment_call": str,
    "ad_disclaimer": str,
}


def _format_pain_points(state: XHSState) -> list[str]:
    pain_points = state.get("pain_points") or []
    if not isinstance(pain_points, list):
        return [str(pain_points)]
    result = []
    for item in pain_points:
        if isinstance(item, dict):
            text = str(item.get("pain", ""))
        else:
            text = str(item)
        if text.strip():
            result.append(text.strip())
    return result


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
        evidence_comments = [str(c).strip() for c in evidence_comments if str(c).strip()]
        if pain:
            result.append({"pain": pain, "evidence_comments": evidence_comments})
    return result


def _normalize_string_list(value: Any, min_items: int = 1) -> list[str]:
    if not isinstance(value, list):
        raise ValueError("expected list")
    result = [str(item).strip() for item in value if str(item).strip()]
    if len(result) < min_items:
        raise ValueError("list has too few items")
    return result


def _normalize_page_plan(value: Any) -> list[dict]:
    if not isinstance(value, list):
        raise ValueError("image_page_plan must be a list")
    pages = []
    for index, item in enumerate(value, start=1):
        if not isinstance(item, dict):
            raise ValueError("image_page_plan item must be object")
        title = str(item.get("title") or "").strip()
        text = str(item.get("text") or "").strip()
        if not title or not text:
            raise ValueError("image_page_plan item missing title/text")
        pages.append({
            "page": int(item.get("page") or index),
            "title": title,
            "text": text,
        })
    if len(pages) < 3:
        raise ValueError("image_page_plan has too few pages")
    return pages


def _validate_soft_ad_result(data: Any) -> dict:
    if not isinstance(data, dict):
        raise ValueError("LLM JSON root must be an object")

    for field, expected_type in REQUIRED_FIELDS.items():
        if field not in data:
            raise ValueError(f"missing field: {field}")
        if not isinstance(data[field], expected_type):
            raise ValueError(f"invalid field type: {field}")

    return {
        "titles": _normalize_string_list(data["titles"], min_items=2)[:5],
        "cover_texts": _normalize_string_list(data["cover_texts"], min_items=2)[:4],
        "body": str(data["body"]).strip(),
        "image_page_plan": _normalize_page_plan(data["image_page_plan"])[:6],
        "image_prompts": _normalize_string_list(data["image_prompts"], min_items=1)[:4],
        "tags": _normalize_string_list(data["tags"], min_items=3)[:10],
        "comment_call": str(data["comment_call"]).strip(),
        "ad_disclaimer": str(data.get("ad_disclaimer") or _SOFT_AD_PROFILE.get("ad_disclaimer", "")).strip(),
    }


def _build_soft_ad_prompt(state: XHSState) -> list:
    topic = state["user_topic"]
    target_user = state.get("target_user") or "小红书目标用户"
    pain_points = _format_pain_points(state)
    comment_insights = _format_comment_insights(state)
    product_info = state.get("product_info") or {}
    selling_points = state.get("product_selling_points") or []
    pain_match = state.get("product_pain_match") or []
    primary_pain = pain_points[0] if pain_points else topic

    input_payload = {
        "topic": topic,
        "target_user": target_user,
        "content_type": "soft_ad",
        "content_label": _SOFT_AD_PROFILE.get("label", "好物分享"),
        "primary_pain": primary_pain,
        "comment_insights": comment_insights[:5],
        "pain_points": pain_points[:5],
        "product_name": product_info.get("name", ""),
        "product_selling_points": selling_points,
        "product_pain_match": pain_match[:5],
        "memory_context": build_generation_memory_context(state),
        "preferred_structure": {
            "label": _SOFT_AD_PROFILE.get("label"),
            "body_heading": _SOFT_AD_PROFILE.get("body_heading"),
            "soft_ad_heading": _SOFT_AD_PROFILE.get("soft_ad_heading"),
            "action_heading": _SOFT_AD_PROFILE.get("action_heading"),
            "action_steps": _SOFT_AD_PROFILE.get("action_steps"),
            "page_titles": _SOFT_AD_PROFILE.get("page_titles"),
            "ad_disclaimer": _SOFT_AD_PROFILE.get("ad_disclaimer"),
        },
        "forbidden_words": ABSOLUTE_WORDS,
        "avoid_promise_words": AVOID_PROMISE_WORDS,
    }

    return build_json_prompt("soft_ad_generation", input_payload)


def _llm_generate_soft_ad(state: XHSState) -> dict:
    client = get_llm_client()
    if client.is_mock:
        raise LLMError("LLM is in mock mode")

    response = client.chat(
        messages=_build_soft_ad_prompt(state),
        temperature=0.4,
        max_tokens=5000,
        response_format={"type": "json_object"},
    )
    data = json.loads(response.content)
    result = _validate_soft_ad_result(data)
    result["content_type"] = "soft_ad"
    result["llm_generation"] = {
        "enabled": True,
        "provider_mode": response.provider_mode,
        "model": response.model,
        "usage": response.usage,
    }
    return result


def _template_generate_soft_ad(state: XHSState) -> dict:
    topic = state["user_topic"]
    target_user = state.get("target_user") or "小红书目标用户"
    pain_points = _format_pain_points(state)
    comment_insights = _format_comment_insights(state)
    product_info = state.get("product_info") or {}
    product_name = product_info.get("name") or state.get("user_product_name") or "这个产品"
    selling_points = state.get("product_selling_points") or []
    primary_pain = (
        comment_insights[0]["pain"] if comment_insights
        else (pain_points[0] if pain_points else topic)
    )

    titles = [
        f"{topic}用到的一个好东西，先讲清楚再决定要不要试",
        f"关于{topic}，我最近试了一个思路：{product_name}",
        f"{primary_pain}，后来发现可以这样解决",
    ]

    cover_texts = [
        f"{topic}好物思路",
        "先看清楚再决定",
        "别盲买，先往下看",
    ]

    body_lines = [
        f"这篇笔记适合：{target_user}",
        "",
        f"今天聊的是：{topic}",
        "",
        "评论里最集中的问题是：",
    ]

    if comment_insights:
        for index, insight in enumerate(comment_insights[:3], start=1):
            body_lines.append(f"{index}. {insight['pain']}")
    elif pain_points:
        for index, pain in enumerate(pain_points[:3], start=1):
            body_lines.append(f"{index}. {pain}")

    body_lines.extend([
        "",
        f"我用到的一个东西帮了大忙：{product_name}",
        "",
        f"它是怎么帮到我的：{selling_points[0] if selling_points else '解决了我一直在纠结的问题'}",
        "",
        "建议你先按下面顺序判断：",
        "1. 先看自己的具体场景和问题是否对得上。",
        "2. 再去了解这个产品具体能做什么、不能做什么。",
        "3. 最后决定要不要试，不要因为种草盲买。",
        "",
        "本内容包含商业合作信息，请理性种草。",
    ])

    image_page_plan = [
        {"page": 1, "title": f"{topic}：先讲问题", "text": "评论里的真实困惑"},
        {"page": 2, "title": "产品思路", "text": f"{product_name}帮了大忙"},
        {"page": 3, "title": "理性提醒", "text": "别盲买，先判断"},
    ]

    return {
        "content_type": "soft_ad",
        "titles": titles,
        "cover_texts": cover_texts,
        "body": "\n".join(body_lines),
        "image_page_plan": image_page_plan,
        "image_prompts": [f"{topic}好物分享封面，干净清爽", "产品使用场景图"],
        "tags": [topic, "好物分享", "理性种草", product_name],
        "comment_call": f"你在{topic}上最纠结的是哪一步？评论区告诉我。",
        "ad_disclaimer": "本内容包含商业合作信息，请理性种草。",
        "llm_generation": {
            "enabled": False,
            "provider_mode": "template",
            "model": None,
            "usage": {},
        },
    }


def generate_soft_ad(state: XHSState) -> dict:
    try:
        return _llm_generate_soft_ad(state)
    except (LLMError, ValueError, json.JSONDecodeError) as exc:
        fallback = _template_generate_soft_ad(state)
        fallback["llm_generation"] = {
            "enabled": False,
            "provider_mode": "fallback_template",
            "model": None,
            "usage": {},
            "error": str(exc),
        }
        return fallback
