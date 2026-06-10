"""Check LLM configuration and make one chat call."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.config import load_settings  # noqa: E402
from llm.client import ChatMessage, LLMError, get_llm_client  # noqa: E402


def _mask_base_url(base_url: str | None) -> str:
    if not base_url:
        return ""
    return base_url.rstrip("/")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Check OpenAI-compatible LLM connectivity.")
    parser.add_argument(
        "--prompt",
        default="请用一句中文回复：LLM 连接测试成功。",
        help="Prompt used for the test request.",
    )
    parser.add_argument(
        "--require-real",
        action="store_true",
        help="Fail if current config resolves to mock mode.",
    )
    parser.add_argument(
        "--json-output",
        action="store_true",
        help="Request response_format={type: json_object} and validate JSON mode.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    settings = load_settings()
    client = get_llm_client()

    config_summary = {
        "llm_model_name": settings.llm_model_name,
        "llm_base_url": _mask_base_url(settings.llm_base_url),
        "llm_api_key_present": bool(settings.llm_api_key),
        "llm_timeout_seconds": settings.llm_timeout_seconds,
        "provider_mode": "mock" if client.is_mock else "openai_compatible",
    }
    print(json.dumps({"config": config_summary}, ensure_ascii=False, indent=2))

    if args.require_real and client.is_mock:
        print("LLM is in mock mode. Fill LLM_BASE_URL, LLM_API_KEY, and LLM_MODEL_NAME first.")
        return 2

    try:
        if args.json_output:
            messages = [
                ChatMessage(role="system", content="你是一个 JSON 连通性测试助手。必须只输出 JSON。"),
                ChatMessage(
                    role="user",
                    content='请输出 JSON 对象：{"status":"ok","message":"LLM JSON 连接测试成功"}',
                ),
            ]
            response = client.chat(
                messages=messages,
                temperature=0.1,
                max_tokens=200,
                response_format={"type": "json_object"},
            )
            json.loads(response.content)
        else:
            response = client.chat(
                messages=[
                    ChatMessage(role="system", content="你是一个简洁的连通性测试助手。"),
                    ChatMessage(role="user", content=args.prompt),
                ],
                temperature=0.1,
                max_tokens=200,
            )
    except LLMError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2))
        return 1

    print(
        json.dumps(
            {
                "ok": True,
                "response": {
                    "content": response.content,
                    "model": response.model,
                    "provider_mode": response.provider_mode,
                    "usage": response.usage,
                    "request_id": response.request_id,
                },
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
