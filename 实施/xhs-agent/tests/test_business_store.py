from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from app.business_store import sync_run_business_tables
from app.run_store import SQLiteRunStore


def _save_run(db_path: Path, record: dict) -> None:
    SQLiteRunStore(db_path).save(record)


def _rows(db_path: Path, table: str) -> list[sqlite3.Row]:
    with sqlite3.connect(db_path) as connection:
        connection.row_factory = sqlite3.Row
        return connection.execute(f"SELECT * FROM {table}").fetchall()


def _extended_record(tmp_path: Path) -> dict:
    asset_path = tmp_path / "creator_assets" / "run_business_extended" / "01_cover.png"
    asset_path.parent.mkdir(parents=True, exist_ok=True)
    asset_path.write_bytes(b"\x89PNG\r\n\x1a\nimage-bytes")
    return {
        "run_id": "run_business_extended",
        "status": "success",
        "created_at": "2026-06-12T11:00:00",
        "updated_at": "2026-06-12T11:05:00",
        "finished_at": "2026-06-12T11:05:00",
        "reviewed_at": "2026-06-12T11:04:00",
        "review_action": "approved",
        "request": {"topic": "小红书新手选题方法", "format": "image_text"},
        "summary": {},
        "content": {
            "titles": ["选题第一步"],
            "cover_texts": ["先看评论"],
            "body": "正文内容",
            "image_page_plan": [{"page": 1, "title": "第一页"}],
            "image_prompts": ["干净的信息图"],
            "tags": ["小红书运营"],
            "comment_call": "你卡在哪一步？",
        },
        "insights": {},
        "paths": {"post_id": "output/markdown_exports/run_business_extended.md"},
        "error": None,
        "state": {
            "user_topic": "小红书新手选题方法",
            "content_format": "image_text",
            "content_type": "step_tutorial",
            "titles": ["选题第一步"],
            "cover_texts": ["先看评论"],
            "body": "正文内容",
            "image_page_plan": [{"page": 1, "title": "第一页"}],
            "image_prompts": ["干净的信息图"],
            "tags": ["小红书运营"],
            "comment_call": "你卡在哪一步？",
            "post_id": "output/markdown_exports/run_business_extended.md",
            "publish_status": "success",
            "operation_record_id": "op_extended_001",
            "operation_memory_written": True,
            "creator_image_files": [str(asset_path)],
            "creator_images_count": 1,
            "creator_assets_updated_at": "2026-06-12T11:03:00",
            "creator_publish_requested": True,
            "creator_publish_status": "success",
            "creator_publish_mode": "mock",
            "creator_note_id": "mock_note_extended_001",
            "creator_publish_result": {
                "ok": True,
                "mode": "mock",
                "platform": "xhs_creator",
                "visibility": "private",
                "note_id": "mock_note_extended_001",
                "xsec_token": "secret-xsec",
            },
            "performance_data": {
                "views": 1000,
                "likes": 80,
                "collects": 45,
                "comments": 12,
                "follows": 3,
            },
            "performance_score": 321,
            "review_summary": "表现不错",
            "next_action": "继续复用结构",
        },
    }


def test_sync_run_business_tables_writes_core_snapshot(tmp_path: Path) -> None:
    db_path = tmp_path / "xhs_agent.sqlite3"
    record = {
        "run_id": "run_business_001",
        "status": "success",
        "created_at": "2026-06-12T10:00:00",
        "updated_at": "2026-06-12T10:05:00",
        "finished_at": "2026-06-12T10:05:00",
        "request": {"topic": "小红书新手选题方法"},
        "summary": {},
        "content": {},
        "insights": {},
        "paths": {},
        "error": None,
        "state": {
            "user_topic": "小红书新手选题方法",
            "raw_notes": [
                {
                    "id": "note_a",
                    "title": "小红书选题先别急着判断",
                    "note_url": "https://example.test/note/a",
                    "likes": 10,
                    "collects": 5,
                    "comments": 3,
                    "shares": 1,
                }
            ],
            "collection_candidates": [
                {
                    "rank": 1,
                    "selected": True,
                    "original_index": 0,
                    "title": "小红书选题先别急着判断",
                    "note_url": "https://example.test/note/a",
                    "score": 120,
                    "reasons": ["主题相关"],
                    "penalties": [],
                    "score_breakdown": {"topic_relevance": 60},
                }
            ],
            "raw_comments": [
                {
                    "source_note_title": "小红书选题先别急着判断",
                    "content": "不知道怎么判断选题？",
                    "like_count": 2,
                }
            ],
            "analysis_report": {
                "sample_selection": {"candidate_count": 1, "selected_count": 1},
                "comment_quality": {
                    "raw_comments_count": 1,
                    "evidence_count": 1,
                    "quality_level": "low",
                },
                "pain_point_confidence": {"level": "low", "score": 24},
                "content_structure_hint": {"recommended_type": "qa_education"},
                "risks": ["评论样本较少"],
                "summary": "候选 1 个，入选 1 个，评论质量 low，痛点可信度 low。",
            },
        },
    }
    _save_run(db_path, record)

    summary = sync_run_business_tables(db_path, record)

    assert summary == {
        "raw_notes": 1,
        "collection_candidates": 1,
        "raw_comments": 1,
        "analysis_reports": 1,
        "drafts": 0,
        "creator_assets": 0,
        "creator_notes": 0,
        "performance_records": 0,
        "audit_events": 0,
    }
    note = _rows(db_path, "raw_notes")[0]
    assert note["run_id"] == "run_business_001"
    assert note["topic"] == "小红书新手选题方法"
    assert note["source_note_id"] == "note_a"
    assert note["likes"] == 10
    candidate = _rows(db_path, "collection_candidates")[0]
    assert candidate["rank"] == 1
    assert candidate["selected"] == 1
    assert candidate["score"] == 120
    assert candidate["note_row_id"] == note["note_row_id"]
    comment = _rows(db_path, "raw_comments")[0]
    assert comment["content"] == "不知道怎么判断选题？"
    assert comment["note_row_id"] == note["note_row_id"]
    report = _rows(db_path, "analysis_reports")[0]
    assert report["candidate_count"] == 1
    assert report["selected_count"] == 1
    assert report["raw_comments_count"] == 1
    assert report["recommended_type"] == "qa_education"


def test_sync_run_business_tables_is_idempotent(tmp_path: Path) -> None:
    db_path = tmp_path / "xhs_agent.sqlite3"
    record = {
        "run_id": "run_business_repeat",
        "status": "success",
        "created_at": "2026-06-12T10:00:00",
        "updated_at": "2026-06-12T10:05:00",
        "request": {"topic": "小红书新手选题方法"},
        "summary": {},
        "content": {},
        "insights": {},
        "paths": {},
        "error": None,
        "state": {
            "user_topic": "小红书新手选题方法",
            "raw_notes": [{"title": "选题方法", "likes": 1}],
            "collection_candidates": [
                {
                    "rank": 1,
                    "selected": True,
                    "original_index": 0,
                    "title": "选题方法",
                }
            ],
            "raw_comments": [{"source_note_title": "选题方法", "content": "第一步做什么？"}],
            "analysis_report": {"summary": "样本较少"},
        },
    }
    _save_run(db_path, record)

    sync_run_business_tables(db_path, record)
    sync_run_business_tables(db_path, record)

    assert len(_rows(db_path, "raw_notes")) == 1
    assert len(_rows(db_path, "collection_candidates")) == 1
    assert len(_rows(db_path, "raw_comments")) == 1
    assert len(_rows(db_path, "analysis_reports")) == 1


def test_sync_run_business_tables_sanitizes_sensitive_json_fields(tmp_path: Path) -> None:
    db_path = tmp_path / "xhs_agent.sqlite3"
    record = {
        "run_id": "run_business_sensitive",
        "status": "success",
        "created_at": "2026-06-12T10:00:00",
        "updated_at": "2026-06-12T10:05:00",
        "request": {"topic": "小红书新手选题方法"},
        "summary": {},
        "content": {},
        "insights": {},
        "paths": {},
        "error": None,
        "state": {
            "user_topic": "小红书新手选题方法",
            "raw_notes": [
                {
                    "title": "敏感字段测试",
                    "cookie": "secret_cookie",
                    "xsec_token": "secret_xsec",
                    "user_id": "user_001",
                    "author": {"nickname": "真实昵称", "avatar": "https://avatar.test/a.png"},
                }
            ],
            "collection_candidates": [
                {
                    "rank": 1,
                    "selected": True,
                    "title": "敏感字段测试",
                    "authorization": "Bearer secret",
                    "api_key": "secret_key",
                }
            ],
            "raw_comments": [
                {
                    "source_note_title": "敏感字段测试",
                    "content": "评论内容保留",
                    "comment_id": "comment_001",
                    "user": {"nickname": "评论用户"},
                }
            ],
            "analysis_report": {"summary": "无敏感字段"},
        },
    }
    _save_run(db_path, record)

    sync_run_business_tables(db_path, record)

    payloads = [
        _rows(db_path, "raw_notes")[0]["raw_json"],
        _rows(db_path, "collection_candidates")[0]["candidate_json"],
        _rows(db_path, "raw_comments")[0]["raw_json"],
        _rows(db_path, "analysis_reports")[0]["report_json"],
    ]
    joined = json.dumps([json.loads(payload) for payload in payloads], ensure_ascii=False)
    assert "secret_cookie" not in joined
    assert "secret_xsec" not in joined
    assert "secret_key" not in joined
    assert "真实昵称" not in joined
    assert "评论用户" not in joined
    assert "comment_001" not in joined
    assert "评论内容保留" in joined


def test_sync_run_business_tables_writes_extended_snapshot_tables(tmp_path: Path) -> None:
    db_path = tmp_path / "xhs_agent.sqlite3"
    record = _extended_record(tmp_path)
    _save_run(db_path, record)

    summary = sync_run_business_tables(db_path, record)

    assert summary["drafts"] == 1
    assert summary["creator_assets"] == 1
    assert summary["creator_notes"] == 1
    assert summary["performance_records"] == 1
    assert summary["audit_events"] == 3

    draft = _rows(db_path, "drafts")[0]
    assert draft["run_id"] == "run_business_extended"
    assert draft["operation_record_id"] == "op_extended_001"
    assert draft["topic"] == "小红书新手选题方法"
    assert draft["content_format"] == "image_text"
    assert draft["content_type"] == "step_tutorial"
    assert draft["title"] == "选题第一步"
    assert draft["body"] == "正文内容"
    assert draft["markdown_path"] == "output/markdown_exports/run_business_extended.md"
    assert json.loads(draft["tags_json"]) == ["小红书运营"]

    asset = _rows(db_path, "creator_assets")[0]
    assert asset["run_id"] == "run_business_extended"
    assert asset["draft_id"] == draft["draft_id"]
    assert asset["source"] == "bound_file"
    assert asset["file_name"] == "01_cover.png"
    assert asset["file_size"] > 0
    assert asset["bound_order"] == 1
    assert asset["prompt"] == "干净的信息图"

    creator_note = _rows(db_path, "creator_notes")[0]
    assert creator_note["creator_note_id"] == "mock_note_extended_001"
    assert creator_note["run_id"] == "run_business_extended"
    assert creator_note["operation_record_id"] == "op_extended_001"
    assert creator_note["draft_id"] == draft["draft_id"]
    assert creator_note["publish_mode"] == "mock"
    assert creator_note["publish_status"] == "success"
    assert creator_note["visibility_label"] == "private"
    assert "secret-xsec" not in creator_note["publish_response_json"]

    performance = _rows(db_path, "performance_records")[0]
    assert performance["operation_record_id"] == "op_extended_001"
    assert performance["creator_note_id"] == "mock_note_extended_001"
    assert performance["run_id"] == "run_business_extended"
    assert performance["views"] == 1000
    assert performance["likes"] == 80
    assert performance["collects"] == 45
    assert performance["comments"] == 12
    assert performance["follows"] == 3
    assert performance["performance_score"] == 321

    audit_actions = {row["action"] for row in _rows(db_path, "audit_events")}
    assert audit_actions == {"human_review", "creator_publish", "operation_memory_write"}


def test_sync_run_business_tables_extended_tables_are_idempotent(tmp_path: Path) -> None:
    db_path = tmp_path / "xhs_agent.sqlite3"
    record = _extended_record(tmp_path)
    _save_run(db_path, record)

    sync_run_business_tables(db_path, record)
    sync_run_business_tables(db_path, record)

    assert len(_rows(db_path, "drafts")) == 1
    assert len(_rows(db_path, "creator_assets")) == 1
    assert len(_rows(db_path, "creator_notes")) == 1
    assert len(_rows(db_path, "performance_records")) == 1
    assert len(_rows(db_path, "audit_events")) == 3
