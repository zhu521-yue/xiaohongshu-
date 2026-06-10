import json
import re
from typing import Any

from app.config import load_settings
from app.rules import load_content_rules, load_text_replacement_rules
from app.state import XHSState
from llm.client import LLMError, get_llm_client
from llm.prompts import build_json_prompt
from nodes.compliance_node import ABSOLUTE_WORDS, AVOID_PROMISE_WORDS, SAFETY_NOTE, SENSITIVE_TOPICS
from nodes.pattern_utils import structure_profile, successful_patterns



_CONTENT_RULES = load_content_rules()
CONTENT_TYPE_LABELS = {
    key: str(value.get("label") or key)
    for key, value in (_CONTENT_RULES.get("structure_profiles") or {}).items()
    if isinstance(value, dict)
}

def _format_pain_points(state:XHSState)->list[str]:
    pain_points = state.get("pain_points") or []
    if not isinstance(pain_points, list):
        return [str(pain_points)]
    
    result = []
    for item in pain_points:
        if isinstance(item,dict):
            result.append(str(item.get("pain","")))
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
        evidence_comments = [str(comment).strip() for comment in evidence_comments if str(comment).strip()]
        if pain:
            result.append({"pain": pain, "evidence_comments": evidence_comments})
    return result


def _first_evidence(insights: list[dict]) -> str:
    for insight in insights:
        comments = insight.get("evidence_comments") or []
        if comments:
            return str(comments[0])
    return ""


_TEXT_REPLACEMENT_RULES = load_text_replacement_rules()
PHRASE_REPLACEMENTS = dict(_TEXT_REPLACEMENT_RULES.get("phrase_replacements") or {})
ABSOLUTE_WORD_REPLACEMENTS = dict(_TEXT_REPLACEMENT_RULES.get("absolute_word_replacements") or {})
QUALITY_WORD_REPLACEMENTS = dict(_TEXT_REPLACEMENT_RULES.get("quality_word_replacements") or {})


REQUIRED_IMAGE_TEXT_FIELDS = {
    "titles": list,
    "cover_texts": list,
    "body": str,
    "image_page_plan": list,
    "image_prompts": list,
    "tags": list,
    "comment_call": str,
}


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
    text_parts = [
        str(result.get("body") or ""),
        " ".join(str(tag) for tag in result.get("tags") or []),
    ]
    text = "\n".join(text_parts)
    return any(word in text for word in SENSITIVE_TOPICS)


def _ensure_safety_note(state: XHSState, result: dict) -> dict:
    if not (_has_sensitive_context(state) or _has_generated_sensitive_claim(result)):
        return result

    body = str(result.get("body") or "")
    if SAFETY_NOTE not in body:
        result["body"] = "\n".join([body.rstrip(), "", "发布前提醒：", SAFETY_NOTE])
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
        pages.append(
            {
                "page": int(item.get("page") or index),
                "title": title,
                "text": text,
            }
        )

    if len(pages) < 3:
        raise ValueError("image_page_plan has too few pages")
    return pages


def _validate_image_text_result(data: Any) -> dict:
    if not isinstance(data, dict):
        raise ValueError("LLM JSON root must be an object")

    for field, expected_type in REQUIRED_IMAGE_TEXT_FIELDS.items():
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
    }


def _compact_profile(profile: dict) -> dict:
    return {
        "content_type": profile.get("content_type"),
        "label": profile.get("label"),
        "body_heading": profile.get("body_heading"),
        "action_heading": profile.get("action_heading"),
        "action_steps": profile.get("action_steps"),
        "page_titles": profile.get("page_titles"),
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


def _build_image_text_prompt(
    state: XHSState,
    profile: dict,
    content_label: str,
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
        "content_label": content_label,
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

    return build_json_prompt("image_text_generation", input_payload)


def _llm_generate_image_text(
    state: XHSState,
    profile: dict,
    content_label: str,
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
        messages=_build_image_text_prompt(
            state=state,
            profile=profile,
            content_label=content_label,
            pain_points=pain_points,
            comment_insights=comment_insights,
            patterns=patterns,
            primary_pain=primary_pain,
        ),
        temperature=0.4,
        max_tokens=settings.llm_image_text_max_tokens,
        response_format={"type": "json_object"},
    )
    data = json.loads(response.content)
    result = _validate_image_text_result(data)
    result = _clean_generated_text(result)
    result = _ensure_safety_note(state, result)
    result["content_type"] = profile.get("content_type")
    result["llm_generation"] = {
        "enabled": True,
        "provider_mode": response.provider_mode,
        "model": response.model,
        "usage": response.usage,
    }
    return result


def _template_generate_image_text(state:XHSState)->dict:
    topic = state["user_topic"]                                                                                                                              
    target_user = state.get("target_user") or "小红书目标用户"                                                                                               
    content_type = state.get("content_type") or "knowledge_share"                                                                                            
    profile = structure_profile(state, content_type)
    content_label = profile.get("label") or CONTENT_TYPE_LABELS.get(content_type, "知识分享")
    pain_points = _format_pain_points(state)                                                                                                                 
    comment_insights = _format_comment_insights(state)
    patterns = successful_patterns(state)
    primary_pain = comment_insights[0]["pain"] if comment_insights else (pain_points[0] if pain_points else topic)
    first_evidence = _first_evidence(comment_insights)
    context_note = (
        "这篇是根据评论区高频问题整理的，不替代诊断，只帮你先把判断顺序理清楚。"
        if _has_sensitive_context(state)
        else "这篇是根据评论区高频问题整理的，先帮你把判断顺序和操作步骤理清楚。"
    )
                                                                                                                                                             
    titles = [
        str(template).format(topic=topic, primary_pain=primary_pain)
        for template in profile.get("title_templates", [])
    ]
    if patterns:
        titles.append(f"{topic}这次先按评论高频问题看")
    else:
        titles.append(f"我把评论里问得最多的{topic}问题整理好了")
                                                                                                                                                             
    cover_texts = [                                                                                                                                          
        str(profile.get("cover_main") or "{topic}知识卡片").format(topic=topic, primary_pain=primary_pain),
        f"{content_label}｜一篇讲清楚",                                                                                                                      
        str(profile.get("cover_sub") or "先收藏，再慢慢看").format(topic=topic, primary_pain=primary_pain),
    ]                                                                                                                                                        
                                                                                                                                                             
    body_lines = [                                                                                                                                           
        f"这篇笔记适合：{target_user}",                                                                                                                      
        "",                                                                                                                                                  
        f"今天聊的是：{topic}",                                                                                                                              
        "",                                                                                                                                                  
        context_note,
    ]                                                                                                                                                        

    if first_evidence:
        body_lines.extend(["", f"有用户会这样问：{first_evidence}"])

    body_lines.extend(["", str(profile.get("body_heading") or "评论里最集中的困惑是：")])

    if comment_insights:
        for index, insight in enumerate(comment_insights[:4], start=1):
            body_lines.append(f"{index}. {insight['pain']}")
            evidence_comments = insight.get("evidence_comments") or []
            for evidence in evidence_comments[:2]:
                body_lines.append(f"   - 评论证据：{evidence}")
    else:
        for index, pain in enumerate(pain_points, start=1):
            body_lines.append(f"{index}. {pain}")
                                                                                                                                                             
    body_lines.extend(["", str(profile.get("action_heading") or "建议你先按下面这个顺序处理：")])
    for index, step in enumerate(profile.get("action_steps") or [], start=1):
        body_lines.append(f"{index}. {step}")
    body_lines.extend(
        [
            "",
            "以上内容仅作经验分享，具体情况建议结合自身实际判断。",
        ]
    )
                                                                                                                                                             
    page_titles = profile.get("page_titles") or []
    page_texts = profile.get("page_texts") or []
    image_page_plan = []
    for index, title in enumerate(page_titles[:4], start=1):
        text = page_texts[index - 1] if index - 1 < len(page_texts) else primary_pain
        image_page_plan.append(
            {
                "page": index,
                "title": f"{topic}：{str(title).format(topic=topic, primary_pain=primary_pain)}" if index == 1 else str(title).format(topic=topic, primary_pain=primary_pain),
                "text": str(text).format(topic=topic, primary_pain=primary_pain),
            }
        )
                                                                                                                                                             
    image_prompts = [                                                                                                               
        f"小红书封面图，主题是{topic}，干净清爽，适合知识分享账号",
        f"信息图风格，展示{topic}的评论高频困惑、{content_label}结构和处理提醒",
    ]                                                                                                                                                        
                                                                                                                                                             
    tags = [topic, "小红书运营", "知识分享", content_label, "经验总结"]                
                                                                                                                                                             
    return {                                                                                                                                                 
        "content_type": profile.get("content_type"),
        "titles": titles,                                                                                                                                    
        "cover_texts": cover_texts,                                                                                                                          
        "body": "\n".join(body_lines),                                                                                                                       
        "image_page_plan": image_page_plan,                                                                                                                  
        "image_prompts": image_prompts,                                                                                                                      
        "tags": tags,                                                                                                                                        
        "comment_call": f"你在{topic}上最困惑的是哪一步？评论区告诉我。",                                                                                    
        "llm_generation": {
            "enabled": False,
            "provider_mode": "template",
            "model": None,
            "usage": {},
        },
    } 


def generate_image_text(state:XHSState)->dict:
    content_type = state.get("content_type") or "knowledge_share"
    profile = structure_profile(state, content_type)
    content_label = profile.get("label") or CONTENT_TYPE_LABELS.get(content_type, "知识分享")
    pain_points = _format_pain_points(state)
    comment_insights = _format_comment_insights(state)
    patterns = successful_patterns(state)
    topic = state["user_topic"]
    primary_pain = comment_insights[0]["pain"] if comment_insights else (pain_points[0] if pain_points else topic)

    try:
        return _llm_generate_image_text(
            state=state,
            profile=profile,
            content_label=content_label,
            pain_points=pain_points,
            comment_insights=comment_insights,
            patterns=patterns,
            primary_pain=primary_pain,
        )
    except (LLMError, ValueError, json.JSONDecodeError) as exc:
        fallback = _template_generate_image_text(state)
        fallback["llm_generation"] = {
            "enabled": False,
            "provider_mode": "fallback_template",
            "model": None,
            "usage": {},
            "error": str(exc),
        }
        return fallback
