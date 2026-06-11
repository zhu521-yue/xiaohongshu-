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

from app.logging_config import redact_sensitive
from platforms import platform_guardrails


PROJECT_ROOT = Path(__file__).resolve().parents[1]
VENDOR_ROOT = PROJECT_ROOT / "vendor" / "Spider_XHS"
VENDOR_NODE_MODULES = VENDOR_ROOT / "node_modules"
load_dotenv(PROJECT_ROOT / ".env")

PLATFORM = "xhs_creator"
VISIBILITY_PRIVATE = "private"
MAX_IMAGE_COUNT = 15
CREATOR_POSTED_NOTES_V2_API = "/api/galaxy/v2/creator/note/user/posted"
CREATOR_LIST_MAX_PAGES = 5


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
    runtime = check_creator_runtime()
    if runtime.get("ok") is not True:
        return {
            "ok": False,
            "mode": "spider_xhs",
            "platform": PLATFORM,
            "visibility": VISIBILITY_PRIVATE,
            "error": str(runtime.get("error") or "creator runtime check failed"),
            "raw": runtime,
        }

    platform_guardrails.ensure_creator_publish_allowed()
    platform_guardrails.sleep_before_creator_publish()

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
    try:
        with _vendor_working_directory():
            success, msg, raw = _load_creator_api().post_note(note_info, _creator_cookies())
    except Exception as exc:
        platform_guardrails.record_creator_publish_failure(str(exc))
        raise

    if not success:
        platform_guardrails.record_creator_publish_failure(str(msg or "creator publish returned success=False"))
        return {
            "ok": False,
            "mode": "spider_xhs",
            "platform": PLATFORM,
            "visibility": VISIBILITY_PRIVATE,
            "error": str(msg),
            "raw": raw,
        }
    platform_guardrails.record_creator_publish_success()
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
            "raw": redact_sensitive(raw),
        }
    note_id = str(raw.get("note_id") or raw.get("id") or raw.get("noteId") or f"unknown_{index}")
    title = str(raw.get("title") or raw.get("displayTitle") or raw.get("display_title") or raw.get("name") or "")
    visibility = str(raw.get("visibility") or raw.get("type") or raw.get("privacy_type") or "")
    return {
        "note_id": note_id,
        "title": title,
        "visibility": visibility,
        "raw": redact_sensitive(raw),
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


def _request_creator_posted_notes_v2(cookies_str: str, page: int) -> dict[str, Any]:
    with _vendor_working_directory():
        import requests
        from xhs_utils.cookie_util import trans_cookies
        from xhs_utils.http_util import REQUEST_TIMEOUT
        from xhs_utils.xhs_creator_util import generate_xsc, get_common_headers
        from xhs_utils.xhs_util import splice_str

        cookies = trans_cookies(cookies_str)
        a1 = str(cookies.get("a1") or "").strip()
        if not a1:
            raise ValueError("creator cookie missing a1")

        splice_api = splice_str(CREATOR_POSTED_NOTES_V2_API, {"tab": "1", "page": str(page)})
        headers = get_common_headers()
        headers["Host"] = "creator.xiaohongshu.com"
        headers["referer"] = "https://creator.xiaohongshu.com/publish/publish?source=official&from=menu&target=image"
        headers["sec-fetch-site"] = "same-origin"
        headers.update(generate_xsc(a1, splice_api))

        response = requests.get(
            f"https://creator.xiaohongshu.com{splice_api}",
            headers=headers,
            cookies=cookies,
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        if not response.text.strip():
            raise ValueError("creator v2 list returned empty body")
        return response.json()


def _is_success_payload(payload: dict[str, Any]) -> bool:
    return payload.get("success") is True or payload.get("code") in (0, "0")


def _extract_creator_v2_page(payload: dict[str, Any]) -> tuple[list[Any], int]:
    data = payload.get("data") if isinstance(payload, dict) else {}
    if not isinstance(data, dict):
        data = {}
    notes = data.get("notes")
    if not isinstance(notes, list):
        notes = payload.get("notes") if isinstance(payload.get("notes"), list) else []
    page = data.get("page", payload.get("page", -1))
    try:
        next_page = int(page)
    except (TypeError, ValueError):
        next_page = -1
    return notes, next_page


def _spider_list_published_notes_v2(cookies: str, limit: int) -> tuple[bool, str, list[Any]]:
    notes: list[Any] = []
    page = 0
    for _ in range(CREATOR_LIST_MAX_PAGES):
        payload = _request_creator_posted_notes_v2(cookies, page)
        if not isinstance(payload, dict) or not _is_success_payload(payload):
            msg = "creator v2 list returned success=False"
            if isinstance(payload, dict):
                msg = str(payload.get("msg") or payload.get("message") or msg)
            return False, msg, notes
        page_notes, next_page = _extract_creator_v2_page(payload)
        notes.extend(page_notes)
        if len(notes) >= limit or next_page == -1:
            return True, "success", notes[:limit]
        page = next_page
    return True, "success", notes[:limit]


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

    source = "creator_v2"
    try:
        success, msg, raw_notes = _spider_list_published_notes_v2(cookies, limit)
    except Exception as exc:
        success, msg, raw_notes = False, f"creator v2 list failed: {exc}", []

    if not success:
        v2_msg = msg
        try:
            with _vendor_working_directory():
                success, msg, raw_notes = _load_creator_api().get_all_publish_note_info(cookies)
            source = "spider_vendor"
        except Exception as exc:
            msg = f"{v2_msg}; legacy creator list failed: {exc}"
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
        "source": source,
        "notes": notes,
    }


def _safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _visibility_label(raw: dict[str, Any], fallback: str) -> str:
    permission_msg = str(raw.get("permission_msg") or "").strip()
    if permission_msg:
        return permission_msg
    permission_code = raw.get("permission_code")
    if permission_code == 1 or str(permission_code) == "1":
        return VISIBILITY_PRIVATE
    return fallback or ""


def _status_from_note(note: dict[str, Any]) -> dict[str, Any]:
    raw = note.get("raw") if isinstance(note.get("raw"), dict) else {}
    return {
        "ok": True,
        "status": "synced",
        "creator_note_id": note.get("note_id"),
        "title": note.get("title") or "",
        "visibility": note.get("visibility") or "",
        "visibility_label": _visibility_label(raw, str(note.get("visibility") or "")),
        "platform_type": raw.get("type") or note.get("visibility") or "",
        "permission_code": raw.get("permission_code"),
        "tab_status": raw.get("tab_status"),
        "metrics_snapshot": {
            "views": _safe_int(raw.get("view_count")),
            "likes": _safe_int(raw.get("likes")),
            "collects": _safe_int(raw.get("collected_count")),
            "comments": _safe_int(raw.get("comments_count")),
        },
        "raw": redact_sensitive(raw),
    }


def get_published_note_status(creator_note_id: str, limit: int = 50) -> dict[str, Any]:
    clean_note_id = str(creator_note_id or "").strip()
    if not clean_note_id:
        return {
            "ok": False,
            "status": "not_found",
            "creator_note_id": "",
            "error": "creator_note_id is required",
        }

    list_result = list_published_notes(limit=max(0, int(limit)))
    if list_result.get("ok") is not True:
        return {
            "ok": False,
            "status": "unavailable",
            "creator_note_id": clean_note_id,
            "error": str(list_result.get("error") or "creator notes unavailable"),
            "raw": redact_sensitive(list_result),
        }

    for note in list_result.get("notes") or []:
        if isinstance(note, dict) and str(note.get("note_id") or "") == clean_note_id:
            return _status_from_note(note)

    return {
        "ok": False,
        "status": "not_found",
        "creator_note_id": clean_note_id,
        "error": f"creator note not found: {clean_note_id}",
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
