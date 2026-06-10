"""Unified LLM client.

The project uses an OpenAI-compatible chat completion API so different model
providers can be swapped through .env without changing node code.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal

import requests

from app.config import load_settings


Role = Literal["system", "user", "assistant"]


@dataclass(frozen=True)
class ChatMessage:
    role: Role
    content: str


@dataclass(frozen=True)
class LLMResponse:
    content: str
    model: str
    provider_mode: str
    usage: Dict[str, Any] = field(default_factory=dict)
    request_id: str | None = None


class LLMError(RuntimeError):
    """Raised when a real LLM call fails."""


class LLMClient:
    def __init__(
        self,
        api_key: str | None,
        base_url: str | None,
        model_name: str,
        timeout_seconds: float = 60.0,
    ) -> None:
        self.api_key = (api_key or "").strip()
        self.base_url = (base_url or "").strip().rstrip("/")
        self.model_name = (model_name or "mock").strip()
        self.timeout_seconds = timeout_seconds

    @property
    def is_mock(self) -> bool:
        return self.model_name == "mock" or not self.api_key or not self.base_url

    def chat(
        self,
        messages: List[ChatMessage],
        temperature: float = 0.3,
        max_tokens: int = 1200,
        response_format: Dict[str, Any] | None = None,
    ) -> LLMResponse:
        if self.is_mock:
            return self._mock_chat(messages)

        payload = {
            "model": self.model_name,
            "messages": [
                {"role": message.role, "content": message.content}
                for message in messages
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if response_format:
            payload["response_format"] = response_format
        endpoint = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        try:
            response = requests.post(
                endpoint,
                headers=headers,
                json=payload,
                timeout=self.timeout_seconds,
            )
        except requests.RequestException as exc:
            raise LLMError(f"LLM request failed: {exc}") from exc

        if response.status_code >= 400:
            raise LLMError(
                f"LLM request failed with HTTP {response.status_code}: "
                f"{response.text[:500]}"
            )

        try:
            data = response.json()
        except ValueError as exc:
            raise LLMError("LLM response is not valid JSON") from exc

        choices = data.get("choices") or []
        if not choices:
            raise LLMError("LLM response has no choices")

        first_choice = choices[0]
        message = first_choice.get("message") or {}
        content = str(message.get("content") or "").strip()
        if not content:
            raise LLMError(
                "LLM response content is empty; "
                f"finish_reason={first_choice.get('finish_reason')}; "
                f"usage={data.get('usage') or {}}"
            )

        return LLMResponse(
            content=content,
            model=str(data.get("model") or self.model_name),
            provider_mode="openai_compatible",
            usage=data.get("usage") or {},
            request_id=response.headers.get("x-request-id"),
        )

    def _mock_chat(self, messages: List[ChatMessage]) -> LLMResponse:
        user_messages = [message.content for message in messages if message.role == "user"]
        last_user_message = user_messages[-1] if user_messages else ""
        preview = last_user_message.replace("\n", " ").strip()[:80]
        return LLMResponse(
            content=f"[mock llm] 已收到请求：{preview}",
            model="mock",
            provider_mode="mock",
            usage={"total_tokens": 0},
            request_id="mock",
        )


def get_llm_client() -> LLMClient:
    settings = load_settings()
    return LLMClient(
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
        model_name=settings.llm_model_name,
        timeout_seconds=settings.llm_timeout_seconds,
    )
