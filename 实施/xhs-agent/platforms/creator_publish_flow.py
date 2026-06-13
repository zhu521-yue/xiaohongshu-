from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from platforms import creator as creator_platform

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CREATOR_ASSETS_DIR = PROJECT_ROOT / "data" / "creator_assets"
MIN_CREATOR_IMAGE_BYTES = 8


def publish_creator_private_if_requested(state: dict[str, Any]) -> dict[str, Any]:
    if state.get("creator_publish_requested") is not True:
        return creator_publish_not_requested()

    mode = creator_platform.creator_mode()
    if state.get("content_format") != "image_text":
        return creator_publish_failed("creator publishing is image_text only in M19b")

    try:
        draft = build_creator_image_text_draft(state, mode=mode)
        result = creator_platform.publish_private_image_text(draft, human_confirmed=True)
    except Exception as exc:
        return creator_publish_failed(str(exc))

    if result.get("ok") is True:
        return creator_publish_success(result)
    return creator_publish_failed(str(result.get("error") or "creator publish failed"))


def creator_publish_not_requested() -> dict[str, Any]:
    return {
        "creator_publish_requested": False,
        "creator_publish_status": "not_requested",
        "creator_publish_mode": creator_platform.creator_mode(),
        "creator_note_id": None,
        "creator_publish_error": None,
        "creator_publish_result": {},
    }


def creator_publish_failed(error: str, *, requested: bool = True) -> dict[str, Any]:
    mode = creator_platform.creator_mode()
    sanitized_error = sanitize_creator_error(error)
    return {
        "creator_publish_requested": requested,
        "creator_publish_status": "failed",
        "creator_publish_mode": mode,
        "creator_note_id": None,
        "creator_publish_error": sanitized_error,
        "creator_publish_result": {
            "ok": False,
            "mode": mode,
            "platform": "xhs_creator",
            "error": sanitized_error,
        },
    }


def creator_publish_success(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "creator_publish_requested": True,
        "creator_publish_status": "success",
        "creator_publish_mode": str(result.get("mode") or creator_platform.creator_mode()),
        "creator_note_id": result.get("note_id"),
        "creator_publish_error": None,
        "creator_publish_result": {
            "ok": result.get("ok") is True,
            "mode": result.get("mode"),
            "platform": result.get("platform"),
            "visibility": result.get("visibility"),
            "note_id": result.get("note_id"),
            "error": result.get("error"),
        },
    }


def build_creator_image_text_draft(state: dict[str, Any], *, mode: str) -> dict[str, Any]:
    fallback_title = state.get("user_topic") or "Untitled note"
    title = str((state.get("titles") or [fallback_title])[0]).strip()
    desc = creator_description_from_state(state)
    return {
        "title": title,
        "desc": desc or title,
        "images": creator_images_from_state(state, mode=mode),
        "topics": [str(tag).strip().lstrip("#") for tag in state.get("tags") or [] if str(tag).strip()],
    }


def creator_description_from_state(state: dict[str, Any]) -> str:
    parts = [str(state.get("body") or "").strip()]
    tags = [str(tag).strip().lstrip("#") for tag in state.get("tags") or [] if str(tag).strip()]
    if tags:
        parts.append(" ".join(f"#{tag}" for tag in tags))
    comment_call = str(state.get("comment_call") or "").strip()
    if comment_call:
        parts.append(comment_call)
    return "\n\n".join(part for part in parts if part).strip()


def creator_images_from_state(state: dict[str, Any], *, mode: str) -> list[Any]:
    images = state.get("creator_image_bytes") or state.get("creator_images") or []
    if isinstance(images, list) and images:
        if mode == "mock":
            return images
        return [_valid_image_bytes(image) for image in images]

    file_bytes = creator_image_file_bytes_from_state(state)
    if file_bytes:
        return file_bytes

    if mode == "mock":
        return [b"mock-image-bytes"]
    raise ValueError("creator publishing requires image bytes in state when CREATOR_MODE=spider_xhs")


def creator_image_file_bytes_from_state(state: dict[str, Any]) -> list[bytes]:
    files = state.get("creator_image_files") or []
    if not isinstance(files, list) or not files:
        return []
    return [_valid_image_file(path_value) for path_value in files]


def _valid_image_file(path_value: Any) -> bytes:
    path = resolve_creator_asset_path(path_value)
    if not path.exists() or not path.is_file():
        raise ValueError(f"creator asset file not found: {path}")
    return _valid_image_bytes(path.read_bytes())


def _valid_image_bytes(image: Any) -> bytes:
    if not isinstance(image, (bytes, bytearray, memoryview)):
        raise ValueError("creator publishing requires image bytes in state when CREATOR_MODE=spider_xhs")
    payload = bytes(image)
    if not is_supported_creator_image_bytes(payload):
        raise ValueError("creator publishing requires valid image bytes in state when CREATOR_MODE=spider_xhs")
    return payload


def resolve_creator_asset_path(path_value: Any) -> Path:
    raw_path = str(path_value or "").strip()
    if not raw_path:
        raise ValueError("creator asset path is empty")

    path = Path(raw_path)
    if not path.is_absolute():
        path = PROJECT_ROOT / path

    resolved = path.resolve()
    asset_root = CREATOR_ASSETS_DIR.resolve()
    if resolved != asset_root and asset_root not in resolved.parents:
        raise ValueError("creator asset path must stay inside creator asset directory")
    return resolved


def is_supported_creator_image_bytes(payload: bytes) -> bool:
    if len(payload) < MIN_CREATOR_IMAGE_BYTES:
        return False
    if payload.startswith((b"\x89PNG\r\n\x1a\n", b"\xff\xd8\xff", b"GIF87a", b"GIF89a", b"BM")):
        return True
    return payload.startswith(b"RIFF") and len(payload) >= 12 and payload[8:12] == b"WEBP"


def sanitize_creator_error(error: Any) -> str:
    text = str(error)
    replacements = [
        r"(?i)\bauthorization\s*[:=]\s*Bearer\s+[^\s,;]+",
        r"(?i)\b(cookie|token|password|api[_-]?key|apikey|authorization)\s*[:=]\s*[^\s,;]+",
        r"(?i)([\"'])(cookie|token|password|api[_-]?key|apikey|authorization)\1\s*:\s*([\"']).*?\3",
    ]
    for pattern in replacements:
        text = re.sub(pattern, _redacted_creator_error_match, text)
    return re.sub(r"(?i)(cookie=\[REDACTED\])(?:;\s*[^,\s;=]+=[^,\s;]+)+", r"\1", text)


def _redacted_creator_error_match(match: re.Match[str]) -> str:
    if match.lastindex and match.lastindex >= 2 and match.group(2):
        quote = match.group(1)
        return f"{quote}{match.group(2)}{quote}: {quote}[REDACTED]{quote}"
    key = match.group(1) if match.lastindex else "authorization"
    return f"{key}=[REDACTED]"
