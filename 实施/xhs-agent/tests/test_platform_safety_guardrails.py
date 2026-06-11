from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from platforms import collector, creator, platform_guardrails


def _now() -> datetime:
    return datetime(2026, 6, 11, 12, 0, 0)


def _sample_draft() -> dict:
    return {
        "title": "真实发布护栏测试",
        "desc": "这是一条用于验证 M25 平台安全护栏的私密图文草稿。",
        "images": [b"\x89PNG\r\n\x1a\n" + b"0" * 64],
        "topics": ["小红书运营"],
    }


@pytest.fixture()
def guardrail_path(tmp_path: Path, monkeypatch) -> Path:
    path = tmp_path / "platform_guardrails.json"
    monkeypatch.setenv("XHS_PLATFORM_GUARDRAIL_PATH", str(path))
    return path


def test_creator_daily_limit_blocks_after_configured_success_count(guardrail_path, monkeypatch) -> None:
    monkeypatch.setenv("XHS_CREATOR_DAILY_LIMIT", "2")

    assert platform_guardrails.check_creator_publish_allowed(now=_now())["allowed"] is True

    platform_guardrails.record_creator_publish_success(now=_now())
    platform_guardrails.record_creator_publish_success(now=_now())

    result = platform_guardrails.check_creator_publish_allowed(now=_now())

    assert result["allowed"] is False
    assert "daily limit" in result["reason"]
    assert guardrail_path.exists()


def test_creator_failure_sets_same_day_stop_flag(guardrail_path, monkeypatch) -> None:
    monkeypatch.setenv("XHS_CREATOR_DAILY_LIMIT", "3")

    platform_guardrails.record_creator_publish_failure("success=False: 风控验证", now=_now())

    result = platform_guardrails.check_creator_publish_allowed(now=_now())

    assert result["allowed"] is False
    assert "风控验证" in result["reason"]
    assert guardrail_path.exists()


def test_spider_creator_publish_preflights_cookie_before_vendor_api(monkeypatch, guardrail_path) -> None:
    monkeypatch.setenv("CREATOR_MODE", "spider_xhs")
    monkeypatch.delenv("XHS_CREATOR_COOKIES", raising=False)

    def fail_if_loaded():
        raise AssertionError("creator API should not be loaded without a runtime preflight pass")

    monkeypatch.setattr(creator, "_load_creator_api", fail_if_loaded)

    result = creator.publish_private_image_text(_sample_draft(), human_confirmed=True)

    assert result["ok"] is False
    assert "XHS_CREATOR_COOKIES" in result["error"]


def test_spider_creator_publish_sleeps_before_post_note(monkeypatch, guardrail_path) -> None:
    monkeypatch.setenv("CREATOR_MODE", "spider_xhs")
    monkeypatch.setenv("XHS_CREATOR_COOKIES", "a1=fake")
    monkeypatch.setenv("XHS_CREATOR_DAILY_LIMIT", "3")
    calls: list[str] = []

    monkeypatch.setattr(creator, "check_creator_runtime", lambda: {"ok": True, "mode": "spider_xhs", "platform": "xhs_creator"})
    monkeypatch.setattr(platform_guardrails, "sleep_before_creator_publish", lambda: calls.append("sleep"))

    class FakeCreatorApi:
        def post_note(self, note_info, cookies):
            calls.append("post_note")
            return True, "ok", {"note_id": "real_private_001"}

    monkeypatch.setattr(creator, "_load_creator_api", lambda: FakeCreatorApi())

    result = creator.publish_private_image_text(_sample_draft(), human_confirmed=True)

    assert result["ok"] is True
    assert calls == ["sleep", "post_note"]


def test_collector_runtime_check_passes_in_mock_mode(monkeypatch) -> None:
    monkeypatch.setenv("COLLECTOR_MODE", "mock")

    result = collector.check_collector_runtime()

    assert result["ok"] is True
    assert result["mode"] == "mock"


def test_spider_collector_runtime_check_requires_pc_cookie(monkeypatch) -> None:
    monkeypatch.setenv("COLLECTOR_MODE", "spider_xhs")
    monkeypatch.delenv("XHS_COOKIES_PC", raising=False)
    monkeypatch.delenv("COOKIES_PC", raising=False)
    monkeypatch.delenv("COOKIES", raising=False)

    result = collector.check_collector_runtime()

    assert result["ok"] is False
    assert result["mode"] == "spider_xhs"
    assert "XHS_COOKIES_PC" in result["error"]

