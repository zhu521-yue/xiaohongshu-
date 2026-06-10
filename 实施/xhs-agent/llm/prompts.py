"""Build LLM chat prompts from external prompt templates."""

from __future__ import annotations

import json
from typing import Any

from app.rules import load_llm_prompts
from llm.client import ChatMessage


def _require_string(template: dict[str, Any], key: str, template_name: str) -> str:
    value = template.get(key)
    if not isinstance(value, str) or not value.strip():
        raise RuntimeError(f"Prompt template {template_name!r} missing string field: {key}")
    return value


def get_prompt_template(template_name: str) -> dict[str, Any]:
    templates = load_llm_prompts()
    template = templates.get(template_name)
    if not isinstance(template, dict):
        raise RuntimeError(f"Missing LLM prompt template: {template_name}")
    return template


def build_json_prompt(template_name: str, input_payload: dict[str, Any]) -> list[ChatMessage]:
    template = get_prompt_template(template_name)
    expected_json = template.get("expected_json")
    if not isinstance(expected_json, dict):
        raise RuntimeError(f"Prompt template {template_name!r} missing expected_json object")

    system_prompt = _require_string(template, "system", template_name)
    user_template = _require_string(template, "user_template", template_name)
    user_prompt = user_template.format(
        expected_json=json.dumps(expected_json, ensure_ascii=False, indent=2),
        input_payload=json.dumps(input_payload, ensure_ascii=False, indent=2),
    )

    return [
        ChatMessage(role="system", content=system_prompt),
        ChatMessage(role="user", content=user_prompt),
    ]
