"""Load business rules from JSON configuration files."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RULES_ROOT = PROJECT_ROOT / "config"


def _read_json_config(filename: str) -> dict[str, Any]:
    path = RULES_ROOT / filename
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError as exc:
        raise RuntimeError(f"Missing rule config: {path}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Invalid rule config JSON: {path}") from exc

    if not isinstance(data, dict):
        raise RuntimeError(f"Rule config root must be an object: {path}")
    return data


@lru_cache(maxsize=None)
def load_content_rules() -> dict[str, Any]:
    return _read_json_config("content_structures.json")


@lru_cache(maxsize=None)
def load_compliance_rules() -> dict[str, Any]:
    return _read_json_config("compliance_rules.json")


@lru_cache(maxsize=None)
def load_strategy_rules() -> dict[str, Any]:
    return _read_json_config("strategy_rules.json")


@lru_cache(maxsize=None)
def load_comment_insight_rules() -> dict[str, Any]:
    return _read_json_config("comment_insight_rules.json")


@lru_cache(maxsize=None)
def load_text_replacement_rules() -> dict[str, Any]:
    return _read_json_config("text_replacements.json")


@lru_cache(maxsize=None)
def load_performance_rules() -> dict[str, Any]:
    return _read_json_config("performance_rules.json")


@lru_cache(maxsize=None)
def load_llm_prompts() -> dict[str, Any]:
    return _read_json_config("llm_prompts.json")


def load_performance_weights() -> dict[str, int]:
    rules = load_performance_rules()
    weights = rules.get("performance_weights")
    if not isinstance(weights, dict):
        raise RuntimeError("performance_weights must be an object")
    return {str(key): int(value) for key, value in weights.items()}
