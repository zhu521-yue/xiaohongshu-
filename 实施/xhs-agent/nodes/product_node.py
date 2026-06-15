"""Product selection node for stage 2 soft-ad workflow.

Reads user-provided product info, calls Qianfan mock adapter for product search,
and matches product selling points to user pain points.
"""

from __future__ import annotations

from app.state import XHSState
from platforms.qianfan import search_product


def _pain_texts(pain_points: list) -> list[str]:
    texts = []
    for item in (pain_points or []):
        if isinstance(item, dict):
            pain = str(item.get("pain") or "").strip()
            if pain:
                texts.append(pain)
        elif isinstance(item, str):
            text = item.strip()
            if text:
                texts.append(text)
    return texts


def _match_pain_to_selling_points(
    pain_points: list,
    selling_points: list[str],
) -> list[dict]:
    pains = _pain_texts(pain_points)
    matches = []
    for pain in pains:
        for sp in selling_points:
            score = 0
            pain_chars = set(pain)
            sp_chars = set(sp)
            common = pain_chars & sp_chars
            if common:
                score = len(common)
            if any(word in pain for word in sp[:2]) or any(word in sp for word in pain[:2]):
                score += 3
            if score > 0:
                matches.append({
                    "pain": pain,
                    "selling_point": sp,
                    "score": score,
                })
    matches.sort(key=lambda m: m["score"], reverse=True)
    return matches[:10]


def select_product(state: XHSState) -> dict:
    product_name = str(state.get("user_product_name") or "").strip()
    if not product_name:
        raise ValueError(
            "user_product_name is required for soft_ad content. "
            "Please provide a product name in the input."
        )

    user_selling = str(state.get("user_product_selling_points") or "").strip()
    topic = str(state.get("user_topic") or "")

    search_results = search_product(product_name, limit=3)
    if not search_results:
        raise ValueError(f"No products found for: {product_name}")

    product = search_results[0]
    selling_points = list(product.get("selling_points") or [])

    if user_selling:
        selling_points.insert(0, user_selling)

    product_info = {
        "product_id": product.get("product_id"),
        "name": product.get("name"),
        "category": product.get("category"),
        "price_range": product.get("price_range"),
        "shop_name": product.get("shop_name"),
        "source": "qianfan_mock",
    }

    pain_points = state.get("pain_points") or []
    pain_match = _match_pain_to_selling_points(pain_points, selling_points)

    return {
        "product_info": product_info,
        "product_selling_points": selling_points,
        "product_pain_match": pain_match,
    }
