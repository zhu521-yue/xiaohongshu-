from __future__ import annotations

import base64
from pathlib import Path

import pytest

from platforms import openai_image


PNG_BYTES = b"\x89PNG\r\n\x1a\nfake-png"


class FakeResponse:
    def __init__(self, status_code: int, payload: dict, text: str = "") -> None:
        self.status_code = status_code
        self._payload = payload
        self.text = text

    def json(self) -> dict:
        return self._payload


class FakeSession:
    def __init__(self, response: FakeResponse) -> None:
        self.response = response
        self.calls: list[dict] = []

    def post(self, endpoint: str, *, headers: dict, json: dict, timeout: float) -> FakeResponse:
        self.calls.append(
            {
                "endpoint": endpoint,
                "headers": headers,
                "json": json,
                "timeout": timeout,
            }
        )
        return self.response


def test_load_image_settings_reads_openai_env(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "image-key")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://api.openai.example/v1")
    monkeypatch.setenv("OPENAI_IMAGE_MODEL", "gpt-image-2")
    monkeypatch.setenv("OPENAI_IMAGE_SIZE", "1024x1536")
    monkeypatch.setenv("OPENAI_IMAGE_QUALITY", "high")
    monkeypatch.setenv("OPENAI_IMAGE_FORMAT", "png")

    settings = openai_image.load_image_settings()

    assert settings.api_key == "image-key"
    assert settings.base_url == "https://api.openai.example/v1"
    assert settings.model == "gpt-image-2"
    assert settings.size == "1024x1536"
    assert settings.quality == "high"
    assert settings.output_format == "png"


def test_build_image_prompt_uses_run_content() -> None:
    run = {
        "content": {
            "titles": ["小红书新手选题，别踩这3个坑！"],
            "cover_texts": ["选题避坑指南"],
            "body": "先看评论里的真实问题，再匹配账号定位。",
            "image_page_plan": [
                {"page": 1, "title": "先别急着判断", "text": "不要只看点赞和收藏"},
                {"page": 2, "title": "正确顺序", "text": "评论问题 -> 互动质量 -> 账号定位"},
            ],
        }
    }

    prompt = openai_image.build_image_prompt(run)

    assert "小红书竖版封面图" in prompt
    assert "小红书新手选题，别踩这3个坑" in prompt
    assert "选题避坑指南" in prompt
    assert "评论问题 -> 互动质量 -> 账号定位" in prompt


def test_generate_image_posts_to_openai_and_decodes_base64() -> None:
    encoded = base64.b64encode(PNG_BYTES).decode("ascii")
    session = FakeSession(FakeResponse(200, {"data": [{"b64_json": encoded}]}))
    settings = openai_image.OpenAIImageSettings(
        api_key="image-key",
        base_url="https://api.openai.example/v1",
        model="gpt-image-2",
        size="1024x1536",
        quality="high",
        output_format="png",
        timeout_seconds=30.0,
    )

    result = openai_image.generate_image(settings, "生成一张封面", session=session)

    assert result.image_bytes == PNG_BYTES
    assert result.model == "gpt-image-2"
    assert session.calls[0]["endpoint"] == "https://api.openai.example/v1/images/generations"
    assert session.calls[0]["headers"]["Authorization"] == "Bearer image-key"
    assert session.calls[0]["json"]["model"] == "gpt-image-2"
    assert session.calls[0]["json"]["prompt"] == "生成一张封面"
    assert session.calls[0]["json"]["size"] == "1024x1536"
    assert session.calls[0]["json"]["quality"] == "high"
    assert session.calls[0]["json"]["output_format"] == "png"


def test_generate_image_redacts_api_key_from_http_error() -> None:
    leaked_text = (
        '{"error":{"message":"Incorrect API key provided: '
        'sk-secret1234567890abcdef"}}'
    )
    session = FakeSession(FakeResponse(401, {}, text=leaked_text))
    settings = openai_image.OpenAIImageSettings(
        api_key="sk-secret1234567890abcdef",
        base_url="https://api.openai.example/v1",
        model="gpt-image-2",
    )

    with pytest.raises(openai_image.OpenAIImageError) as exc_info:
        openai_image.generate_image(settings, "cover prompt", session=session)

    message = str(exc_info.value)
    assert "sk-secret1234567890abcdef" not in message
    assert "sk-" not in message
    assert "[REDACTED_OPENAI_KEY]" in message


def test_generate_image_raises_on_missing_base64() -> None:
    session = FakeSession(FakeResponse(200, {"data": [{}]}))
    settings = openai_image.OpenAIImageSettings(
        api_key="image-key",
        base_url="https://api.openai.example/v1",
        model="gpt-image-2",
    )

    with pytest.raises(openai_image.OpenAIImageError, match="b64_json"):
        openai_image.generate_image(settings, "生成一张封面", session=session)


def test_save_generated_image_stays_under_output_dir(tmp_path: Path) -> None:
    path = openai_image.save_generated_image(
        run_id="run_image_001",
        image_bytes=PNG_BYTES,
        output_root=tmp_path,
    )

    assert path.parent == tmp_path / "run_image_001"
    assert path.suffix == ".png"
    assert path.read_bytes() == PNG_BYTES
