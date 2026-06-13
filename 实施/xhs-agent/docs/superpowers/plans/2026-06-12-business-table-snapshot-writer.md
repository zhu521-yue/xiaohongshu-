# Business Table Snapshot Writer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an opt-in snapshot writer that syncs completed run state into the foundation business tables without changing current API behavior.

**Architecture:** Create a focused `app/business_store.py` module that reads an existing run record or state dict, initializes the foundation schema, sanitizes sensitive fields, and upserts core collection data into `raw_notes`, `collection_candidates`, `raw_comments`, and `analysis_reports`. Keep this as an explicit callable boundary for now so later API/worker integration can turn it on behind `XHS_AGENT_BUSINESS_TABLES_ENABLED`.

**Tech Stack:** Python 3, SQLite, existing `app.database_schema.initialize_foundation_schema`, pytest.

---

### Task 1: Core Snapshot Writer

**Files:**
- Create: `app/business_store.py`
- Test: `tests/test_business_store.py`

- [ ] **Step 1: Write the failing tests**

```python
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
                "comment_quality": {"raw_comments_count": 1, "evidence_count": 1, "quality_level": "low"},
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
            "collection_candidates": [{"rank": 1, "selected": True, "original_index": 0, "title": "选题方法"}],
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m pytest tests\test_business_store.py -q
```

Expected: fail with `ModuleNotFoundError: No module named 'app.business_store'`.

- [ ] **Step 3: Implement the minimal writer**

Create `app/business_store.py` with:
- `sync_run_business_tables(db_path, run_record) -> dict[str, int]`
- deterministic text IDs using SHA-256 short hashes.
- recursive sanitization for cookie/token/key/authorization and user identity fields.
- upserts for the four core tables.
- timestamp fallback from `finished_at`, `updated_at`, `created_at`, then current UTC time.

- [ ] **Step 4: Run focused tests**

Run:

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m pytest tests\test_business_store.py tests\test_foundation_database_schema.py -q
```

Expected: all selected tests pass.

### Task 2: Final Verification and Progress Notes

**Files:**
- Modify: `memory/current_progress.md`
- Modify: `memory/project_status_and_roadmap.md`

- [ ] **Step 1: Compile changed modules**

Run:

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m compileall app\business_store.py app\database_schema.py
```

Expected: exit code 0.

- [ ] **Step 2: Run full regression with isolated temp root**

Run:

```powershell
$env:PYTEST_DEBUG_TEMPROOT='data\pytest_tmp_full_verify'
D:\Anaconda\envs\ContentShare\python.exe -m pytest -q
```

Expected: full suite passes.

- [ ] **Step 3: Update progress memory**

Record:
- core business table snapshot writer added.
- writes remain explicit/opt-in.
- next tasks: integrate behind env flag, add repair script, expand tables for drafts/assets/creator notes/performance/audit.

- [ ] **Step 4: Report user-facing verification**

Include:
- exact test commands.
- what the task enables.
- how the user can validate by calling the sync function against a run record.
