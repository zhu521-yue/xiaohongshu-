"""Test Qianfan platform adapter."""
from __future__ import annotations

import pytest
from platforms import qianfan


def test_search_product_returns_list():
    result = qianfan.search_product("婴儿辅食机")
    assert isinstance(result, list)
    assert len(result) >= 1
    for item in result:
        assert isinstance(item, dict)
        assert "product_id" in item
        assert "name" in item
        assert "price_range" in item
        assert "selling_points" in item


def test_search_product_empty_keyword_raises():
    with pytest.raises(ValueError):
        qianfan.search_product("")


def test_get_product_detail_returns_dict():
    result = qianfan.get_product_detail("mock_prod_001")
    assert isinstance(result, dict)
    assert result["product_id"] == "mock_prod_001"
    assert "name" in result
    assert "selling_points" in result


def test_get_product_detail_invalid_id_raises():
    with pytest.raises(ValueError):
        qianfan.get_product_detail("")


def test_check_qianfan_runtime_mock_ok():
    result = qianfan.check_qianfan_runtime()
    assert result["ok"] is True
    assert result["mode"] == "mock"


def test_mode_defaults_to_mock(monkeypatch):
    monkeypatch.setenv("QIANFAN_MODE", "")
    from platforms.qianfan import _mode
    assert _mode() == "mock"
