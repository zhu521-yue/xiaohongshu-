"""Helpers for applying successful operation patterns to generation nodes."""

from __future__ import annotations

from typing import Any, Dict, List

from app.rules import load_content_rules
from app.state import XHSState


_CONTENT_RULES = load_content_rules()
VALID_CONTENT_TYPES = set(_CONTENT_RULES.get("valid_content_types") or [])
DEFAULT_CONTENT_TYPE = str(_CONTENT_RULES.get("default_content_type") or "knowledge_share")
STRUCTURE_PROFILES = _CONTENT_RULES.get("structure_profiles") or {}


def safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def successful_patterns(state: XHSState) -> List[Dict[str, Any]]:
    patterns = state.get("successful_patterns") or []
    if not isinstance(patterns, list):
        return []

    result = []
    for pattern in patterns:
        if not isinstance(pattern, dict):
            continue
        score = safe_int(pattern.get("performance_score"))
        if score <= 0:
            continue
        content_type = str(pattern.get("content_type") or "")
        if content_type not in VALID_CONTENT_TYPES:
            continue
        result.append(
            {
                "content_type": content_type,
                "title": str(pattern.get("title") or ""),
                "performance_score": score,
                "pain_points": pattern.get("pain_points") or [],
            }
        )

    result.sort(key=lambda item: item["performance_score"], reverse=True)
    return result


def selected_structure_type(state: XHSState, fallback_type: str) -> str:
    for pattern in successful_patterns(state):
        return pattern["content_type"]
    if fallback_type in STRUCTURE_PROFILES:
        return fallback_type
    return DEFAULT_CONTENT_TYPE


def structure_profile(state: XHSState, fallback_type: str) -> Dict[str, Any]:
    structure_type = selected_structure_type(state, fallback_type)
    profile = dict(STRUCTURE_PROFILES.get(structure_type) or STRUCTURE_PROFILES[DEFAULT_CONTENT_TYPE])
    profile["content_type"] = structure_type
    return profile
