"""Qianfan (千帆) platform adapter for product selection.

Follows the same mock/real pattern as platforms/creators.py.
Stage 2 (M6) uses this to look up products for soft-ad content.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")

PLATFORM = "qianfan"


def _mode() -> str:
    return os.getenv("QIANFAN_MODE", "mock").strip().lower() or "mock"


def _validate_mode(mode: str) -> None:
    if mode not in {"mock", "spider_xhs"}:
        raise ValueError(f"Unsupported QIANFAN_MODE: {mode}")


def check_qianfan_runtime() -> dict:
    mode = _mode()
    try:
        _validate_mode(mode)
    except ValueError as exc:
        return {"ok": False, "mode": mode, "platform": PLATFORM, "error": str(exc)}

    if mode == "mock":
        return {"ok": True, "mode": mode, "platform": PLATFORM}

    cookies = (os.getenv("XHS_QIANFAN_COOKIES") or "").strip()
    if not cookies:
        return {
            "ok": False,
            "mode": mode,
            "platform": PLATFORM,
            "error": "XHS_QIANFAN_COOKIES is required when QIANFAN_MODE=spider_xhs",
        }
    return {"ok": True, "mode": mode, "platform": PLATFORM}


_MOCK_PRODUCTS = [
    {
        "product_id": "mock_prod_001",
        "name": "智能辅食机",
        "category": "母婴小家电",
        "price_range": "¥299-599",
        "selling_points": ["一键蒸煮搅拌", "定时预约", "多档调速", "易清洗"],
        "shop_name": "母婴优选旗舰店",
    },
    {
        "product_id": "mock_prod_002",
        "name": "宝宝餐椅",
        "category": "母婴用品",
        "price_range": "¥159-399",
        "selling_points": ["可折叠收纳", "多档高度调节", "安全绑带", "易擦洗材质"],
        "shop_name": "嘉也母婴官方店",
    },
    {
        "product_id": "mock_prod_003",
        "name": "婴儿指甲剪套装",
        "category": "母婴护理",
        "price_range": "¥29-89",
        "selling_points": ["圆头防夹肉", "LED照明", "静音设计", "新生儿可用"],
        "shop_name": "贝亲官方旗舰店",
    },
]


def search_product(keyword: str, limit: int = 3) -> list[dict]:
    mode = _mode()
    _validate_mode(mode)

    clean_keyword = str(keyword or "").strip()
    if not clean_keyword:
        raise ValueError("keyword is required")

    if mode == "mock":
        results = []
        for product in _MOCK_PRODUCTS:
            name = product.get("name") or ""
            if clean_keyword in name or any(
                char in name for char in clean_keyword if len(char) > 1
            ):
                results.append(dict(product))
        return results[: max(1, int(limit))] if results else [_MOCK_PRODUCTS[0]][: max(1, int(limit))]

    return []


def get_product_detail(product_id: str) -> dict:
    mode = _mode()
    _validate_mode(mode)

    clean_id = str(product_id or "").strip()
    if not clean_id:
        raise ValueError("product_id is required")

    if mode == "mock":
        for product in _MOCK_PRODUCTS:
            if product.get("product_id") == clean_id:
                return dict(product)
        raise ValueError(f"Product not found: {clean_id}")

    return {}
