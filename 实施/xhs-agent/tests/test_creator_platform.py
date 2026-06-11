import sys
from contextlib import contextmanager

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


def test_spider_list_published_notes_falls_back_to_legacy_vendor(monkeypatch) -> None:
    monkeypatch.setenv("CREATOR_MODE", "spider_xhs")
    monkeypatch.setenv("XHS_CREATOR_COOKIES", "a1=fake")

    class LegacyCreatorApi:
        def get_all_publish_note_info(self, cookies: str):
            return True, "success", [{"id": "legacy_note_001", "display_title": "legacy note", "type": "normal"}]

    @contextmanager
    def noop_vendor_directory():
        yield

    monkeypatch.setattr(creator, "_vendor_working_directory", noop_vendor_directory)
    monkeypatch.setattr(creator, "_load_creator_api", lambda: LegacyCreatorApi())
    monkeypatch.setattr(creator, "_request_creator_posted_notes_v2", lambda cookies, page: (_ for _ in ()).throw(RuntimeError("v2 down")))

    result = creator.list_published_notes(limit=5)

    assert result["ok"] is True
    assert result["mode"] == "spider_xhs"
    assert result["source"] == "spider_vendor"
    assert result["notes"] == [
        {
            "note_id": "legacy_note_001",
            "title": "legacy note",
            "visibility": "normal",
            "raw": {
                "id": "legacy_note_001",
                "display_title": "legacy note",
                "type": "normal",
            },
        }
    ]


def test_spider_list_published_notes_prefers_creator_v2(monkeypatch) -> None:
    monkeypatch.setenv("CREATOR_MODE", "spider_xhs")
    monkeypatch.setenv("XHS_CREATOR_COOKIES", "a1=fake")

    def fail_legacy_loader():
        raise AssertionError("legacy creator list should not be called when v2 succeeds")

    monkeypatch.setattr(creator, "_load_creator_api", fail_legacy_loader)
    monkeypatch.setattr(
        creator,
        "_request_creator_posted_notes_v2",
        lambda cookies, page: {
            "success": True,
            "data": {
                "page": -1,
                "notes": [
                    {
                        "id": "note_v2_primary",
                        "display_title": "primary v2 note",
                        "type": "normal",
                    }
                ],
            },
        },
    )

    result = creator.list_published_notes(limit=5)

    assert result["ok"] is True
    assert result["source"] == "creator_v2"
    assert result["notes"][0]["note_id"] == "note_v2_primary"


def test_normalize_note_redacts_sensitive_raw_fields() -> None:
    note = creator._normalize_note(
        {
            "id": "note_sensitive",
            "display_title": "sensitive note",
            "xsec_token": "secret-xsec-token",
            "nested": {"cookie": "secret-cookie"},
        },
        1,
    )

    assert note["raw"]["xsec_token"] == "<redacted>"
    assert note["raw"]["nested"]["cookie"] == "<redacted>"
    assert "secret-xsec-token" not in str(note["raw"])
    assert "secret-cookie" not in str(note["raw"])


def test_get_published_note_status_returns_synced_status(monkeypatch) -> None:
    monkeypatch.setenv("CREATOR_MODE", "mock")

    def fake_list_published_notes(limit: int = 50):
        assert limit == 50
        return {
            "ok": True,
            "mode": "spider_xhs",
            "platform": "xhs_creator",
            "source": "creator_v2",
            "notes": [
                {
                    "note_id": "note_status_001",
                    "title": "状态同步测试",
                    "visibility": "normal",
                    "raw": {
                        "id": "note_status_001",
                        "display_title": "状态同步测试",
                        "permission_msg": "仅自己可见",
                        "permission_code": 1,
                        "tab_status": 1,
                        "type": "normal",
                        "view_count": 11,
                        "likes": 2,
                        "collected_count": 3,
                        "comments_count": 4,
                        "xsec_token": "<redacted>",
                    },
                }
            ],
        }

    monkeypatch.setattr(creator, "list_published_notes", fake_list_published_notes)

    result = creator.get_published_note_status("note_status_001")

    assert result["ok"] is True
    assert result["status"] == "synced"
    assert result["creator_note_id"] == "note_status_001"
    assert result["title"] == "状态同步测试"
    assert result["visibility_label"] == "仅自己可见"
    assert result["platform_type"] == "normal"
    assert result["permission_code"] == 1
    assert result["tab_status"] == 1
    assert result["metrics_snapshot"] == {
        "views": 11,
        "likes": 2,
        "collects": 3,
        "comments": 4,
    }
    assert result["raw"]["xsec_token"] == "<redacted>"


def test_get_published_note_status_returns_not_found(monkeypatch) -> None:
    monkeypatch.setattr(
        creator,
        "list_published_notes",
        lambda limit=50: {"ok": True, "mode": "mock", "platform": "xhs_creator", "notes": []},
    )

    result = creator.get_published_note_status("missing_note")

    assert result["ok"] is False
    assert result["status"] == "not_found"
    assert result["creator_note_id"] == "missing_note"
    assert "not found" in result["error"]


def test_get_published_note_status_returns_unavailable_on_list_failure(monkeypatch) -> None:
    monkeypatch.setattr(
        creator,
        "list_published_notes",
        lambda limit=50: {
            "ok": False,
            "mode": "spider_xhs",
            "platform": "xhs_creator",
            "error": "XHS_CREATOR_COOKIES is required",
            "notes": [],
        },
    )

    result = creator.get_published_note_status("note_status_001")

    assert result["ok"] is False
    assert result["status"] == "unavailable"
    assert result["creator_note_id"] == "note_status_001"
    assert "XHS_CREATOR_COOKIES" in result["error"]


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


def test_creator_mode_returns_normalized_mode(monkeypatch) -> None:
    monkeypatch.setenv("CREATOR_MODE", " MOCK ")

    assert creator.creator_mode() == "mock"
