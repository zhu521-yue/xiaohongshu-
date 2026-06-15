"""Test Pugongying platform adapter."""
from __future__ import annotations

import pytest
from platforms import pugongying


def test_search_darwin_returns_list():
    result = pugongying.search_darwin("婴儿辅食")
    assert isinstance(result, list)
    assert len(result) >= 1
    for item in result:
        assert isinstance(item, dict)
        assert "darwin_id" in item
        assert "nickname" in item
        assert "fans_level" in item
        assert "content_tags" in item
        assert "price_range" in item


def test_search_darwin_empty_keyword_raises():
    with pytest.raises(ValueError):
        pugongying.search_darwin("")


def test_get_darwin_detail_returns_dict():
    result = pugongying.get_darwin_detail("mock_darwin_001")
    assert isinstance(result, dict)
    assert result["darwin_id"] == "mock_darwin_001"


def test_get_darwin_detail_invalid_id_raises():
    with pytest.raises(ValueError):
        pugongying.get_darwin_detail("")


def test_send_invite_returns_mock_result():
    result = pugongying.send_invite("mock_darwin_001", "合作邀约测试")
    assert result["ok"] is True
    assert "invite_id" in result


def test_send_invite_empty_id_raises():
    with pytest.raises(ValueError):
        pugongying.send_invite("", "测试")


def test_check_pugongying_runtime_mock_ok():
    result = pugongying.check_pugongying_runtime()
    assert result["ok"] is True
    assert result["mode"] == "mock"
