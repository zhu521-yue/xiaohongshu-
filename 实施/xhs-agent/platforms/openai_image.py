"""OpenAI image generation helper for creator assets."""

from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import datetime
import os
from pathlib import Path
import re
from typing import Any, Protocol

from dotenv import load_dotenv
import requests

from app.config import PROJECT_ROOT


load_dotenv(PROJECT_ROOT / ".env")


class HTTPSession(Protocol):
    def post(
        self,
        endpoint: str,
        *,
        headers: dict[str, str],
        json: dict[str, Any],
        timeout: float,
    ) -> Any:
        ...


@dataclass(frozen=True)
class OpenAIImageSettings:
    api_key: str
    base_url: str = "https://api.openai.com/v1"
    model: str = "gpt-image-2"
    size: str = "1024x1536"
    quality: str | None = None
    output_format: str | None = "png"
    timeout_seconds: float = 180.0


@dataclass(frozen=True)
class GeneratedImage:
    image_bytes: bytes
    model: str
    provider_mode: str
    usage: dict[str, Any]
    raw_metadata: dict[str, Any]


class OpenAIImageError(RuntimeError):
    """Raised when image generation fails."""


def load_image_settings() -> OpenAIImageSettings:
    api_key = (os.getenv("OPENAI_API_KEY") or "").strip()
    base_url = (os.getenv("OPENAI_BASE_URL") or "https://api.openai.com/v1").strip().rstrip("/")
    model = (
        os.getenv("OPENAI_IMAGE_MODEL")
        or os.getenv("GPT_IMAGE_MODEL")
        or "gpt-image-2"
    ).strip()
    size = (os.getenv("OPENAI_IMAGE_SIZE") or "1024x1536").strip()
    quality = (os.getenv("OPENAI_IMAGE_QUALITY") or "").strip() or None
    output_format = (os.getenv("OPENAI_IMAGE_FORMAT") or "png").strip() or None
    timeout_seconds = _env_float("OPENAI_IMAGE_TIMEOUT_SECONDS", 180.0)
    return OpenAIImageSettings(
        api_key=api_key,
        base_url=base_url,
        model=model,
        size=size,
        quality=quality,
        output_format=output_format,
        timeout_seconds=timeout_seconds,
    )


def build_image_prompt(run: dict[str, Any]) -> str:
    content = run.get("content") or {}
    titles = _string_list(content.get("titles"))
    cover_texts = _string_list(content.get("cover_texts"))
    body = str(content.get("body") or "").strip()
    page_plan = content.get("image_page_plan") or []
    image_prompts = _string_list(content.get("image_prompts"))

    title = titles[0] if titles else str(content.get("title") or "小红书内容封面").strip()
    cover = cover_texts[0] if cover_texts else title
    plan_lines: list[str] = []
    if isinstance(page_plan, list):
        for item in page_plan[:4]:
            if not isinstance(item, dict):
                continue
            item_title = str(item.get("title") or "").strip()
            item_text = str(item.get("text") or "").strip()
            if item_title or item_text:
                plan_lines.append(f"- {item_title}: {item_text}".strip())

    prompt_parts = [
        "生成一张小红书竖版封面图，比例 3:4，适合私密发布链路验证。",
        "风格：干净、明亮、信息图感，中文排版清晰，不要二维码、不要水印、不要平台 Logo、不要夸张营销承诺。",
        f"主标题：{title}",
        f"封面重点文案：{cover}",
    ]
    if body:
        prompt_parts.append(f"正文要点：{body[:260]}")
    if plan_lines:
        prompt_parts.append("页面信息结构：\n" + "\n".join(plan_lines))
    if image_prompts:
        prompt_parts.append("原始图片提示参考：" + "；".join(image_prompts[:2]))
    prompt_parts.append("画面中可以包含简洁卡片、步骤编号、便签、箭头或灯泡元素，整体不要像广告海报。")
    return "\n".join(prompt_parts)


def generate_image(
    settings: OpenAIImageSettings,
    prompt: str,
    *,
    session: HTTPSession | None = None,
) -> GeneratedImage:
    if not settings.api_key:
        raise OpenAIImageError("OPENAI_API_KEY is required for image generation")
    if not settings.base_url:
        raise OpenAIImageError("OPENAI_BASE_URL is required for image generation")
    if not settings.model:
        raise OpenAIImageError("OPENAI_IMAGE_MODEL is required for image generation")

    payload: dict[str, Any] = {
        "model": settings.model,
        "prompt": prompt,
        "size": settings.size,
    }
    if settings.quality:
        payload["quality"] = settings.quality
    if settings.output_format:
        payload["output_format"] = settings.output_format

    client = session or requests
    endpoint = f"{settings.base_url.rstrip('/')}/images/generations"
    headers = {
        "Authorization": f"Bearer {settings.api_key}",
        "Content-Type": "application/json",
    }

    try:
        response = client.post(
            endpoint,
            headers=headers,
            json=payload,
            timeout=settings.timeout_seconds,
        )
    except requests.RequestException as exc:
        raise OpenAIImageError(f"OpenAI image request failed: {exc}") from exc

    if response.status_code >= 400:
        safe_text = _redact_sensitive_text(str(response.text), settings.api_key)[:500]
        raise OpenAIImageError(
            f"OpenAI image request failed with HTTP {response.status_code}: "
            f"{safe_text}"
        )

    try:
        data = response.json()
    except ValueError as exc:
        raise OpenAIImageError("OpenAI image response is not valid JSON") from exc

    image_items = data.get("data") or []
    if not image_items or not isinstance(image_items[0], dict):
        raise OpenAIImageError("OpenAI image response has no data item")

    encoded = str(image_items[0].get("b64_json") or "").strip()
    if not encoded:
        raise OpenAIImageError("OpenAI image response data item has no b64_json")
    try:
        image_bytes = base64.b64decode(encoded, validate=True)
    except ValueError as exc:
        raise OpenAIImageError("OpenAI image response b64_json is invalid") from exc
    if not image_bytes.startswith(b"\x89PNG") and not image_bytes.startswith(b"\xff\xd8"):
        raise OpenAIImageError("OpenAI image response is not PNG or JPEG bytes")

    return GeneratedImage(
        image_bytes=image_bytes,
        model=str(data.get("model") or settings.model),
        provider_mode="openai_images",
        usage=data.get("usage") or {},
        raw_metadata={
            "created": data.get("created"),
            "revised_prompt": image_items[0].get("revised_prompt"),
        },
    )


def save_generated_image(
    *,
    run_id: str,
    image_bytes: bytes,
    output_root: Path | None = None,
) -> Path:
    safe_run_id = _safe_path_part(run_id)
    root = output_root or PROJECT_ROOT / "data" / "generated_assets"
    output_dir = root / safe_run_id
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = output_dir / f"{timestamp}_openai_cover.png"
    path.write_bytes(image_bytes)
    return path


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item or "").strip()]


def _safe_path_part(value: str) -> str:
    text = str(value or "").strip()
    safe = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in text)
    return safe or "run"


def _redact_sensitive_text(text: str, *secrets: str) -> str:
    redacted = str(text or "")
    for secret in secrets:
        secret_text = str(secret or "").strip()
        if secret_text:
            redacted = redacted.replace(secret_text, "[REDACTED_OPENAI_KEY]")
    return re.sub(r"sk-[A-Za-z0-9_\-\*]+", "[REDACTED_OPENAI_KEY]", redacted)


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return default
