import sys

import pytest

from platforms import creator
from scripts import check_creator_platform


def sample_draft() -> dict:
    return {
        "title": "私密发布测试标题",
        "desc": "这是一条用于验证创作者平台适配层的私密草稿。",
        "images": [b"fake-image-bytes"],
        "topics": ["小红书运营"],
    }


def test_mock_private_publish_requires_human_confirmation(monkeypatch) -> None:
    monkeypatch.setenv("CREATOR_MODE", "mock")

    with pytest.raises(ValueError, match="human_confirmed"):
        creator.publish_private_image_text(sample_draft(), human_confirmed=False)


def test_mock_private_publish_returns_private_result(monkeypatch) -> None:
    monkeypatch.setenv("CREATOR_MODE", "mock")

    result = creator.publish_private_image_text(sample_draft(), human_confirmed=True)

    assert result["ok"] is True
    assert result["mode"] == "mock"
    assert result["platform"] == "xhs_creator"
    assert result["visibility"] == "private"
    assert result["note_id"].startswith("mock_private_")
    assert result["raw"]["title"] == "私密发布测试标题"


def test_publish_rejects_empty_images(monkeypatch) -> None:
    monkeypatch.setenv("CREATOR_MODE", "mock")
    draft = sample_draft()
    draft["images"] = []

    with pytest.raises(ValueError, match="images"):
        creator.publish_private_image_text(draft, human_confirmed=True)


def test_publish_rejects_more_than_fifteen_images(monkeypatch) -> None:
    monkeypatch.setenv("CREATOR_MODE", "mock")
    draft = sample_draft()
    draft["images"] = [b"x"] * 16

    with pytest.raises(ValueError, match="15"):
        creator.publish_private_image_text(draft, human_confirmed=True)


def test_spider_mode_preflight_requires_creator_cookies(monkeypatch) -> None:
    monkeypatch.setenv("CREATOR_MODE", "spider_xhs")
    monkeypatch.delenv("XHS_CREATOR_COOKIES", raising=False)

    result = creator.check_creator_runtime()

    assert result["ok"] is False
    assert result["mode"] == "spider_xhs"
    assert "XHS_CREATOR_COOKIES" in result["error"]


def test_spider_mode_preflight_reports_import_error(monkeypatch) -> None:
    monkeypatch.setenv("CREATOR_MODE", "spider_xhs")
    monkeypatch.setenv("XHS_CREATOR_COOKIES", "a1=fake")

    def fail_load_creator_api():
        raise RuntimeError("creator api import failed")

    monkeypatch.setattr(creator, "_load_creator_api", fail_load_creator_api)

    result = creator.check_creator_runtime()

    assert result["ok"] is False
    assert result["mode"] == "spider_xhs"
    assert "creator api import failed" in result["error"]


def test_mock_list_published_notes_is_normalized(monkeypatch) -> None:
    monkeypatch.setenv("CREATOR_MODE", "mock")

    result = creator.list_published_notes(limit=2)

    assert result["ok"] is True
    assert result["mode"] == "mock"
    assert result["platform"] == "xhs_creator"
    assert len(result["notes"]) == 2
    assert set(result["notes"][0]) >= {"note_id", "title", "visibility", "raw"}


def test_mock_mode_does_not_import_spider_modules(monkeypatch) -> None:
    monkeypatch.setenv("CREATOR_MODE", "mock")
    before = set(sys.modules)

    creator.publish_private_image_text(sample_draft(), human_confirmed=True)

    imported = set(sys.modules) - before
    assert not any(name.startswith("apis.xhs_creator_apis") for name in imported)


def test_check_creator_platform_mock_publish(monkeypatch) -> None:
    monkeypatch.setenv("CREATOR_MODE", "mock")

    exit_code = check_creator_platform.main(["--mode", "mock", "--publish-private", "--human-confirmed"])

    assert exit_code == 0


def test_check_creator_platform_blocks_publish_without_confirmation(monkeypatch) -> None:
    monkeypatch.setenv("CREATOR_MODE", "mock")

    exit_code = check_creator_platform.main(["--mode", "mock", "--publish-private"])

    assert exit_code == 1
