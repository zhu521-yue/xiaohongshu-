# 这个节点只做策略选择，不负责内容创作

from app.rules import load_strategy_rules
from app.state import XHSState


_STRATEGY_RULES = load_strategy_rules()
AVOID_MISTAKE_KEYWORDS = tuple(_STRATEGY_RULES.get("avoid_mistake_keywords") or [])
STEP_TUTORIAL_KEYWORDS = tuple(_STRATEGY_RULES.get("step_tutorial_keywords") or [])
VALID_CONTENT_TYPES = set(_STRATEGY_RULES.get("valid_content_types") or [])
DEFAULT_CONTENT_TYPE = str(_STRATEGY_RULES.get("default_content_type") or "knowledge_share")
DEFAULT_CONTENT_FORMAT = str(_STRATEGY_RULES.get("default_content_format") or "image_text")


def _choose_content_format(state: XHSState) -> str:
    content_format = state.get("user_selected_format") or state.get("content_format") or DEFAULT_CONTENT_FORMAT

    if content_format not in ("image_text", "video"):
        raise ValueError("content_format must be image_text or video")

    return content_format


def _pain_points_text(state: XHSState) -> str:
    pain_points = state.get("pain_points") or []
    chunks = [str(state.get("user_topic", ""))]

    if isinstance(pain_points, list):
        for item in pain_points:
            if isinstance(item, dict):
                chunks.append(str(item.get("pain", "")))
                chunks.append(str(item.get("evidence", "")))
            else:
                chunks.append(str(item))
    else:
        chunks.append(str(pain_points))

    return " ".join(chunks)


def _safe_int(value: object) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _choose_content_type(state: XHSState) -> str:
    text = _pain_points_text(state)

    if any(keyword in text for keyword in AVOID_MISTAKE_KEYWORDS):
        return "avoid_mistakes"

    if any(keyword in text for keyword in STEP_TUTORIAL_KEYWORDS):
        return "step_tutorial"

    successful_patterns = state.get("successful_patterns") or []
    if isinstance(successful_patterns, list):
        for pattern in successful_patterns:
            if not isinstance(pattern, dict):
                continue
            if _safe_int(pattern.get("performance_score")) <= 0:
                continue
            pattern_type = str(pattern.get("content_type") or "")
            if pattern_type in VALID_CONTENT_TYPES:
                return pattern_type

    return DEFAULT_CONTENT_TYPE


def decide_content_strategy(state: XHSState) -> dict:
    content_type = _choose_content_type(state)
    content_format = _choose_content_format(state)

    if state.get("account_stage", "cold_start") == "cold_start" and content_type == "soft_ad":
        content_type = DEFAULT_CONTENT_TYPE

    if not state.get("allow_soft_ad", False) and content_type == "soft_ad":
        content_type = DEFAULT_CONTENT_TYPE

    return {
        "content_type": content_type,
        "content_format": content_format,
    }
