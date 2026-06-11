"""Creator platform adapter.

This module is the only place that should know about Spider_XHS creator APIs.
M19a keeps publishing explicit and private-only.
"""

from __future__ import annotations

import hashlib
import os
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
VENDOR_ROOT = PROJECT_ROOT / "vendor" / "Spider_XHS"
VENDOR_NODE_MODULES = VENDOR_ROOT / "node_modules"
load_dotenv(PROJECT_ROOT / ".env")

PLATFORM = "xhs_creator"
VISIBILITY_PRIVATE = "private"
MAX_IMAGE_COUNT = 15


def _mode() -> str:
    return os.getenv("CREATOR_MODE", "mock").strip().lower() or "mock"


def creator_mode() -> str:
    return _mode()


def _creator_cookies() -> str:
    return (os.getenv("XHS_CREATOR_COOKIES") or os.getenv("CREATOR_COOKIES") or "").strip()


def _validate_mode(mode: str) -> None:
    if mode not in {"mock", "spider_xhs"}:
        raise ValueError(f"Unsupported CREATOR_MODE: {mode}")


def _normalize_topics(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    topics = []
    for item in value:
        text = str(item or "").strip()
        if text:
            topics.append(text)
    return topics


def _validate_private_image_text_draft(draft: dict[str, Any], *, human_confirmed: bool) -> dict[str, Any]:
    if human_confirmed is not True:
        raise ValueError("human_confirmed=True is required for creator publishing")

    title = str(draft.get("title") or "").strip()
    desc = str(draft.get("desc") or "").strip()
    images = draft.get("images") or []
    if not title:
        raise ValueError("title is required")
    if not desc:
        raise ValueError("desc is required")
    if not isinstance(images, list) or not images:
        raise ValueError("images must contain at least one image")
    if len(images) > MAX_IMAGE_COUNT:
        raise ValueError(f"images cannot contain more than {MAX_IMAGE_COUNT} items")

    return {
        "title": title,
        "desc": desc,
        "images": images,
        "topics": _normalize_topics(draft.get("topics")),
    }


def _mock_private_note_id(title: str, desc: str) -> str:
    digest = hashlib.sha1(f"{title}\n{desc}".encode("utf-8")).hexdigest()[:12]
    return f"mock_private_{digest}"


def _mock_publish_private_image_text(draft: dict[str, Any]) -> dict[str, Any]:
    return {
        "ok": True,
        "mode": "mock",
        "platform": PLATFORM,
        "visibility": VISIBILITY_PRIVATE,
        "note_id": _mock_private_note_id(draft["title"], draft["desc"]),
        "raw": {
            "title": draft["title"],
            "desc": draft["desc"],
            "topics": draft["topics"],
            "image_count": len(draft["images"]),
        },
    }


def _ensure_vendor_importable() -> None:
    if not VENDOR_ROOT.exists():
        raise RuntimeError(f"Spider_XHS vendor directory not found: {VENDOR_ROOT}")

    vendor_path = str(VENDOR_ROOT)
    if vendor_path not in sys.path:
        sys.path.insert(0, vendor_path)

    if VENDOR_NODE_MODULES.exists():
        node_modules_path = str(VENDOR_NODE_MODULES)
        existing_node_path = os.environ.get("NODE_PATH", "")
        node_paths = [item for item in existing_node_path.split(os.pathsep) if item]
        if node_modules_path not in node_paths:
            os.environ["NODE_PATH"] = os.pathsep.join([node_modules_path, *node_paths])


@contextmanager
def _vendor_working_directory():
    _ensure_vendor_importable()
    previous_cwd = Path.cwd()
    os.chdir(VENDOR_ROOT)
    try:
        yield
    finally:
        os.chdir(previous_cwd)


def _load_creator_api():
    _ensure_vendor_importable()
    from apis.xhs_creator_apis import XHS_Creator_Apis

    return XHS_Creator_Apis()


def _extract_note_id(raw: Any, fallback_seed: str) -> str:
    candidates: list[Any] = []
    if isinstance(raw, dict):
        data = raw.get("data")
        candidates.extend([raw.get("note_id"), raw.get("id")])
        if isinstance(data, dict):
            candidates.extend([data.get("note_id"), data.get("id"), data.get("noteId")])
    for candidate in candidates:
        text = str(candidate or "").strip()
        if text:
            return text
    digest = hashlib.sha1(fallback_seed.encode("utf-8")).hexdigest()[:12]
    return f"creator_private_{digest}"


def _spider_publish_private_image_text(draft: dict[str, Any]) -> dict[str, Any]:
    cookies = _creator_cookies()
    if not cookies:
        raise RuntimeError("XHS_CREATOR_COOKIES is required when CREATOR_MODE=spider_xhs")

    note_info = {
        "title": draft["title"],
        "desc": draft["desc"],
        "postTime": None,
        "location": None,
        "type": 1,
        "media_type": "image",
        "topics": draft["topics"],
        "images": draft["images"],
    }
    with _vendor_working_directory():
        success, msg, raw = _load_creator_api().post_note(note_info, cookies)
    if not success:
        return {
            "ok": False,
            "mode": "spider_xhs",
            "platform": PLATFORM,
            "visibility": VISIBILITY_PRIVATE,
            "error": str(msg),
            "raw": raw,
        }
    return {
        "ok": True,
        "mode": "spider_xhs",
        "platform": PLATFORM,
        "visibility": VISIBILITY_PRIVATE,
        "note_id": _extract_note_id(raw, f"{draft['title']}\n{draft['desc']}"),
        "raw": raw,
    }


def publish_private_image_text(draft: dict[str, Any], *, human_confirmed: bool) -> dict[str, Any]:
    mode = _mode()
    _validate_mode(mode)
    normalized = _validate_private_image_text_draft(draft, human_confirmed=human_confirmed)
    if mode == "mock":
        return _mock_publish_private_image_text(normalized)
    return _spider_publish_private_image_text(normalized)


def _normalize_note(raw: Any, index: int) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return {
            "note_id": f"unknown_{index}",
            "title": "",
            "visibility": "",
            "raw": raw,
        }
    note_id = str(raw.get("note_id") or raw.get("id") or raw.get("noteId") or f"unknown_{index}")
    title = str(raw.get("title") or raw.get("display_title") or raw.get("name") or "")
    visibility = str(raw.get("visibility") or raw.get("type") or raw.get("privacy_type") or "")
    return {
        "note_id": note_id,
        "title": title,
        "visibility": visibility,
        "raw": raw,
    }


def _mock_list_published_notes(limit: int) -> dict[str, Any]:
    notes = [
        {
            "note_id": "mock_note_001",
            "title": "Mock private note 1",
            "visibility": VISIBILITY_PRIVATE,
            "raw": {"note_id": "mock_note_001", "title": "Mock private note 1"},
        },
        {
            "note_id": "mock_note_002",
            "title": "Mock private note 2",
            "visibility": VISIBILITY_PRIVATE,
            "raw": {"note_id": "mock_note_002", "title": "Mock private note 2"},
        },
    ]
    return {
        "ok": True,
        "mode": "mock",
        "platform": PLATFORM,
        "notes": notes[:limit],
    }


def _spider_list_published_notes(limit: int) -> dict[str, Any]:
    cookies = _creator_cookies()
    if not cookies:
        return {
            "ok": False,
            "mode": "spider_xhs",
            "platform": PLATFORM,
            "error": "XHS_CREATOR_COOKIES is required when CREATOR_MODE=spider_xhs",
            "notes": [],
        }
    with _vendor_working_directory():
        success, msg, raw_notes = _load_creator_api().get_all_publish_note_info(cookies)
    if not success:
        return {
            "ok": False,
            "mode": "spider_xhs",
            "platform": PLATFORM,
            "error": str(msg),
            "notes": [],
        }
    notes = [_normalize_note(item, index) for index, item in enumerate((raw_notes or [])[:limit], start=1)]
    return {
        "ok": True,
        "mode": "spider_xhs",
        "platform": PLATFORM,
        "notes": notes,
    }


def list_published_notes(limit: int = 20) -> dict[str, Any]:
    mode = _mode()
    _validate_mode(mode)
    safe_limit = max(0, int(limit))
    if mode == "mock":
        return _mock_list_published_notes(safe_limit)
    return _spider_list_published_notes(safe_limit)


def check_creator_runtime() -> dict[str, Any]:
    mode = _mode()
    try:
        _validate_mode(mode)
    except ValueError as exc:
        return {"ok": False, "mode": mode, "platform": PLATFORM, "error": str(exc)}

    if mode == "mock":
        return {"ok": True, "mode": mode, "platform": PLATFORM}

    if not _creator_cookies():
        return {
            "ok": False,
            "mode": mode,
            "platform": PLATFORM,
            "error": "XHS_CREATOR_COOKIES is required when CREATOR_MODE=spider_xhs",
        }
    try:
        _load_creator_api()
    except Exception as exc:
        return {"ok": False, "mode": mode, "platform": PLATFORM, "error": str(exc)}
    return {"ok": True, "mode": mode, "platform": PLATFORM}
