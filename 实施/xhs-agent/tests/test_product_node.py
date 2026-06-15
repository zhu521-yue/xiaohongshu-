"""Test product_node for M6 stage 2."""
from __future__ import annotations

import pytest
from nodes.product_node import select_product


def test_select_product_basic(monkeypatch):
    monkeypatch.setattr(
        "nodes.product_node.search_product",
        lambda keyword, limit=3: [
            {
                "product_id": "mock_prod_001",
                "name": "智能辅食机",
                "price_range": "¥299-599",
                "selling_points": ["一键蒸煮搅拌", "定时预约"],
            }
        ]
    )

    result = select_product({
        "user_topic": "宝宝辅食",
        "user_product_name": "辅食机",
        "user_product_selling_points": "一键操作，省时间",
        "pain_points": [
            {"pain": "做辅食太费时间", "evidence": "评论多次提到时间不够", "priority": 1}
        ],
    })

    assert isinstance(result.get("product_info"), dict)
    assert result["product_info"]["product_id"] == "mock_prod_001"
    assert len(result.get("product_selling_points") or []) > 0
    assert len(result.get("product_pain_match") or []) > 0


def test_select_product_missing_name_raises():
    with pytest.raises(ValueError, match="user_product_name"):
        select_product({
            "user_topic": "宝宝辅食",
            "user_product_name": "",
            "user_product_selling_points": "",
            "pain_points": [],
        })


def test_select_product_only_name_no_selling_points(monkeypatch):
    monkeypatch.setattr(
        "nodes.product_node.search_product",
        lambda keyword, limit=3: [
            {
                "product_id": "mock_prod_002",
                "name": "宝宝餐椅",
                "price_range": "¥159-399",
                "selling_points": ["可折叠", "多档调节"],
            }
        ]
    )

    result = select_product({
        "user_topic": "宝宝餐椅",
        "user_product_name": "宝宝餐椅",
        "user_product_selling_points": "",
        "pain_points": [],
    })

    assert result["product_info"]["product_id"] == "mock_prod_002"
    assert result["product_selling_points"] == ["可折叠", "多档调节"]


def test_product_pain_match_scoring(monkeypatch):
    monkeypatch.setattr(
        "nodes.product_node.search_product",
        lambda keyword, limit=3: [
            {
                "product_id": "mock_prod_001",
                "name": "辅食机",
                "price_range": "¥299-599",
                "selling_points": ["一键操作", "省时省力", "多档调速"],
            }
        ]
    )

    result = select_product({
        "user_topic": "宝宝辅食",
        "user_product_name": "辅食机",
        "user_product_selling_points": "",
        "pain_points": [
            {"pain": "做辅食太费时间", "evidence": "时间不够", "priority": 1},
            {"pain": "不知道该买哪种工具", "evidence": "选择困难", "priority": 2},
        ],
    })

    matches = result.get("product_pain_match") or []
    assert len(matches) > 0
    for match in matches:
        assert "pain" in match
        assert "selling_point" in match
        assert "score" in match
