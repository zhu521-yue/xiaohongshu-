"""Pugongying (蒲公英) platform adapter for KOL/darwin matching.

Follows the same mock/real pattern as platforms/creators.py.
Stage 2 (M6) uses this for KOL matching and invite in soft-ad workflow.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")

PLATFORM = "pugongying"


def _mode() -> str:
    return os.getenv("PUGONGYING_MODE", "mock").strip().lower() or "mock"


def _validate_mode(mode: str) -> None:
    if mode not in {"mock", "spider_xhs"}:
        raise ValueError(f"Unsupported PUGONGYING_MODE: {mode}")


def check_pugongying_runtime() -> dict:
    mode = _mode()
    try:
        _validate_mode(mode)
    except ValueError as exc:
        return {"ok": False, "mode": mode, "platform": PLATFORM, "error": str(exc)}

    if mode == "mock":
        return {"ok": True, "mode": mode, "platform": PLATFORM}

    cookies = (os.getenv("XHS_PUGONGYING_COOKIES") or "").strip()
    if not cookies:
        return {
            "ok": False,
            "mode": mode,
            "platform": PLATFORM,
            "error": "XHS_PUGONGYING_COOKIES is required when PUGONGYING_MODE=spider_xhs",
        }
    return {"ok": True, "mode": mode, "platform": PLATFORM}


_MOCK_DARWINS = [
    {
        "darwin_id": "mock_darwin_001",
        "nickname": "樱桃妈妈育儿记",
        "fans_level": "10w-50w",
        "content_tags": ["母婴", "辅食", "育儿好物"],
        "price_range": "¥3000-8000/条",
        "notes_count": 320,
        "avg_interaction": 1500,
    },
    {
        "darwin_id": "mock_darwin_002",
        "nickname": "小明爸爸爱带娃",
        "fans_level": "5w-10w",
        "content_tags": ["母婴", "亲子", "宝宝成长"],
        "price_range": "¥1500-4000/条",
        "notes_count": 180,
        "avg_interaction": 800,
    },
    {
        "darwin_id": "mock_darwin_003",
        "nickname": "营养师Lily",
        "fans_level": "10w-50w",
        "content_tags": ["辅食营养", "科学育儿", "好物评测"],
        "price_range": "¥5000-12000/条",
        "notes_count": 450,
        "avg_interaction": 2200,
    },
    {
        "darwin_id": "mock_darwin_004",
        "nickname": "新手妈妈成长手册",
        "fans_level": "1w-5w",
        "content_tags": ["母婴", "新手妈妈", "好物推荐"],
        "price_range": "¥500-1500/条",
        "notes_count": 95,
        "avg_interaction": 400,
    },
    {
        "darwin_id": "mock_darwin_005",
        "nickname": "学姐育儿笔记",
        "fans_level": "5w-10w",
        "content_tags": ["育儿知识", "母婴好物", "经验分享"],
        "price_range": "¥2000-5000/条",
        "notes_count": 210,
        "avg_interaction": 1200,
    },
]


def search_darwin(topic: str, limit: int = 5) -> list[dict]:
    mode = _mode()
    _validate_mode(mode)

    clean_topic = str(topic or "").strip()
    if not clean_topic:
        raise ValueError("topic is required")

    if mode == "mock":
        results = []
        for darwin in _MOCK_DARWINS:
            tags_text = " ".join(darwin.get("content_tags") or [])
            nickname = darwin.get("nickname") or ""
            if any(char in tags_text or char in nickname for char in clean_topic if len(char) > 1):
                results.append(dict(darwin))
        if not results:
            results = [dict(_MOCK_DARWINS[0])]
        return results[: max(1, int(limit))]

    return []


def get_darwin_detail(darwin_id: str) -> dict:
    mode = _mode()
    _validate_mode(mode)

    clean_id = str(darwin_id or "").strip()
    if not clean_id:
        raise ValueError("darwin_id is required")

    if mode == "mock":
        for darwin in _MOCK_DARWINS:
            if darwin.get("darwin_id") == clean_id:
                return dict(darwin)
        raise ValueError(f"Darwin not found: {clean_id}")

    return {}


def send_invite(darwin_id: str, message: str = "") -> dict:
    mode = _mode()
    _validate_mode(mode)

    clean_id = str(darwin_id or "").strip()
    if not clean_id:
        raise ValueError("darwin_id is required")

    if mode == "mock":
        digest = hashlib.sha1(f"{clean_id}:{message}".encode("utf-8")).hexdigest()[:12]
        return {
            "ok": True,
            "mode": "mock",
            "platform": PLATFORM,
            "invite_id": f"mock_invite_{digest}",
            "darwin_id": clean_id,
            "message_sent": bool(str(message or "").strip()),
        }

    return {"ok": False, "error": "Real pugongying not implemented"}
