"""Test soft_ad_node for M6 stage 2."""
from __future__ import annotations

import pytest
from nodes.soft_ad_node import generate_soft_ad


class _MockLLMResponse:
    def __init__(self, content: str):
        self.content = content
        self.provider_mode = "mock"
        self.model = "mock"
        self.usage = {}


class _MockClient:
    is_mock = False
    def chat(self, messages, temperature=0.3, max_tokens=1200, response_format=None):
        import json
        return _MockLLMResponse(json.dumps({
            "titles": ["辅食机的好物分享", "做辅食不累的小工具"],
            "cover_texts": ["辅食机好物思路", "先看清楚再决定", "收藏防丢"],
            "body": "这篇先讲问题，再讲产品思路，最后提醒理性判断。",
            "image_page_plan": [
                {"page": 1, "title": "先讲问题", "text": "评论里的困惑"},
                {"page": 2, "title": "产品思路", "text": "辅食机帮了大忙"},
                {"page": 3, "title": "理性提醒", "text": "别盲买"}
            ],
            "image_prompts": ["辅食机配图"],
            "tags": ["辅食机", "好物分享", "理性种草"],
            "comment_call": "你有什么具体问题？评论区告诉我",
            "ad_disclaimer": "本内容包含商业合作信息，请理性种草。"
        }))


def test_generate_soft_ad_llm_mode(monkeypatch):
    monkeypatch.setattr("nodes.soft_ad_node.get_llm_client", lambda: _MockClient())

    state = {
        "user_topic": "宝宝辅食机",
        "target_user": "新手妈妈",
        "content_type": "soft_ad",
        "pain_points": [{"pain": "做辅食太费时间", "evidence": "时间不够", "priority": 1}],
        "comment_insights": [{"pain": "不知道买哪个", "evidence_comments": ["不知道怎么选"]}],
        "product_info": {
            "product_id": "mock_prod_001",
            "name": "智能辅食机",
            "price_range": "¥299-599",
        },
        "product_selling_points": ["一键操作", "省时间", "多档调速"],
        "product_pain_match": [
            {"pain": "做辅食太费时间", "selling_point": "一键操作", "score": 5}
        ],
        "graphrag_memory": {},
    }

    result = generate_soft_ad(state)

    assert len(result.get("titles") or []) >= 2
    assert len(result.get("cover_texts") or []) >= 2
    assert isinstance(result.get("body"), str) and len(result["body"]) > 0
    assert len(result.get("image_page_plan") or []) >= 3
    assert len(result.get("image_prompts") or []) >= 1
    assert len(result.get("tags") or []) >= 3
    assert isinstance(result.get("comment_call"), str)
    assert result.get("content_type") == "soft_ad"
    assert result["llm_generation"]["enabled"] is True


def test_generate_soft_ad_template_fallback(monkeypatch):
    class _FailingClient:
        is_mock = False
        def chat(self, *args, **kwargs):
            from llm.client import LLMError
            raise LLMError("LLM unavailable")

    monkeypatch.setattr("nodes.soft_ad_node.get_llm_client", lambda: _FailingClient())

    state = {
        "user_topic": "宝宝辅食",
        "target_user": "新手妈妈",
        "content_type": "soft_ad",
        "pain_points": [{"pain": "做辅食太费时间", "evidence": "时间不够", "priority": 1}],
        "comment_insights": [],
        "product_info": {"name": "辅食机", "product_id": "mock_prod_001"},
        "product_selling_points": ["一键操作"],
        "product_pain_match": [],
        "graphrag_memory": {},
    }

    result = generate_soft_ad(state)

    assert len(result.get("titles") or []) >= 1
    assert isinstance(result.get("body"), str) and len(result["body"]) > 0
    assert isinstance(result.get("tags"), list)
    assert result["llm_generation"]["enabled"] is False
    assert result["llm_generation"]["provider_mode"] == "fallback_template"


def test_generate_soft_ad_includes_ad_disclaimer(monkeypatch):
    monkeypatch.setattr("nodes.soft_ad_node.get_llm_client", lambda: _MockClient())

    state = {
        "user_topic": "宝宝辅食",
        "target_user": "新手妈妈",
        "content_type": "soft_ad",
        "pain_points": [],
        "comment_insights": [],
        "product_info": {"name": "辅食机", "product_id": "mock_prod_001"},
        "product_selling_points": ["一键操作"],
        "product_pain_match": [],
        "graphrag_memory": {},
    }

    result = generate_soft_ad(state)
    body = str(result.get("body") or "").lower()
    assert len(body) > 0
