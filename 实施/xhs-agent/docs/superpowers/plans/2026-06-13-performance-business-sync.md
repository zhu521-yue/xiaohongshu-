# Performance Business Sync Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `/performance` synchronize manually entered performance data back into the matching SQLite run state and `performance_records`.

**Architecture:** Keep `/performance` as the single user-facing write entry. After `operation_store.update_record_performance()` succeeds, `app.api` finds the matching successful SQLite run, merges the updated memory performance fields into run state, and calls existing `_save_run()` so `sync_run_business_tables()` refreshes `performance_records`. Non-SQLite or disabled business-table configurations return a skipped sync result and keep current behavior.

**Tech Stack:** Python standard library, existing `app.api`, `app.run_store.SQLiteRunStore`, `memory.operation_store`, existing business table writer/query modules, pytest.

---

## File Structure

- Modify: `app/api.py`
  - Add internal helpers for `/performance` business sync.
  - Keep existing public request fields and response fields.
- Modify: `tests/test_creator_note_performance_sync.py`
  - Add SQLite API fixture and API-level tests for sync success, skipped sync, and failure sanitization.
- Modify: `memory/current_progress.md`
  - Record implementation outcome and verification.
- Modify: `memory/project_status_and_roadmap.md`
  - Move `/performance` to `performance_records` reverse sync from pending to completed.

---

### Task 1: Add API-Level Failing Tests

**Files:**
- Modify: `tests/test_creator_note_performance_sync.py`
- Read: `app/api.py`
- Read: `app/run_store.py`
- Read: `app/business_queries.py`

- [ ] **Step 1: Add imports for SQLite tests**

Add imports near the top:

```python
import sqlite3

from app.run_store import LocalRunStore, SQLiteRunStore
```

Replace the existing `from app.run_store import LocalRunStore` import with the combined import.

- [ ] **Step 2: Add SQLite fixture**

Add this fixture after `isolated_api`:

```python
@pytest.fixture()
def sqlite_business_api(tmp_path: Path, monkeypatch) -> Path:
    db_path = tmp_path / "xhs_agent.sqlite3"
    monkeypatch.setenv("XHS_AGENT_RUN_STORE", "sqlite")
    monkeypatch.setenv("XHS_AGENT_RUN_DB_PATH", str(db_path))
    monkeypatch.setenv("XHS_AGENT_RUN_QUEUE", "local")
    monkeypatch.setenv("XHS_AGENT_MEMORY_STORE", "sqlite")
    monkeypatch.setenv("XHS_AGENT_MEMORY_DB_PATH", str(db_path))
    monkeypatch.setenv("XHS_AGENT_DB_SCHEMA", "foundation")
    monkeypatch.setenv("XHS_AGENT_BUSINESS_TABLES_ENABLED", "true")
    monkeypatch.setenv("CREATOR_MODE", "mock")
    monkeypatch.setenv("LLM_MODEL_NAME", "mock")
    _reset_services()
    yield db_path
    _reset_services()
```

- [ ] **Step 3: Add helper for saved success run**

Add this helper after `_operation_state()`:

```python
def _successful_run_from_operation(record: dict, *, run_id: str = "run_perf_sync") -> dict:
    state = {
        **_operation_state(
            post_id=record.get("post_id") or "output/post.md",
            creator_note_id=record.get("creator_note_id") or "mock_note_001",
        ),
        "operation_record_id": record["record_id"],
        "operation_memory_written": True,
        "performance_data": {},
        "performance_score": 0,
        "review_summary": "发布后等待表现。",
        "next_action": "录入表现后复盘。",
    }
    return {
        "run_id": run_id,
        "status": "success",
        "created_at": "2026-06-13T10:00:00",
        "updated_at": "2026-06-13T10:01:00",
        "started_at": "2026-06-13T10:00:00",
        "finished_at": "2026-06-13T10:01:00",
        "request": {"topic": state["user_topic"], "format": "image_text"},
        "summary": api._state_summary(state),
        "content": api._content_payload(state),
        "insights": api._insight_payload(state),
        "state": state,
        "paths": {"post_id": state["post_id"], "operation_memory_path": None, "collection_path": None},
        "error": None,
    }
```

- [ ] **Step 4: Add helper for performance rows**

Add this helper near the tests:

```python
def _performance_rows(db_path: Path) -> list[sqlite3.Row]:
    with sqlite3.connect(db_path) as connection:
        connection.row_factory = sqlite3.Row
        return connection.execute("SELECT * FROM performance_records").fetchall()
```

- [ ] **Step 5: Add failing test for SQLite reverse sync**

Add:

```python
def test_record_performance_syncs_sqlite_run_and_business_table(sqlite_business_api: Path) -> None:
    saved = operation_store.upsert_record_from_state(_operation_state())
    api._save_run(_successful_run_from_operation(saved))

    result = api.record_performance(
        {
            "creator_note_id": "mock_note_001",
            "views": 1000,
            "likes": 50,
            "collects": 20,
            "comments": 8,
            "follows": 3,
            "notes": "首轮表现复盘",
        }
    )

    assert result["business_sync"]["status"] == "success"
    assert result["business_sync"]["run_id"] == "run_perf_sync"
    assert result["business_sync"]["counts"]["performance_records"] == 1

    loaded = api._load_run("run_perf_sync")
    assert loaded is not None
    assert loaded["state"]["performance_data"]["views"] == 1000
    assert loaded["state"]["performance_score"] == result["updated_record"]["performance_score"]
    assert loaded["summary"]["performance_score"] == result["updated_record"]["performance_score"]
    assert loaded["summary"]["business_table_sync_status"] == "success"

    rows = _performance_rows(sqlite_business_api)
    assert len(rows) == 1
    assert rows[0]["operation_record_id"] == saved["record_id"]
    assert rows[0]["creator_note_id"] == "mock_note_001"
    assert rows[0]["views"] == 1000
    assert rows[0]["likes"] == 50
    assert rows[0]["collects"] == 20
    assert rows[0]["comments"] == 8
    assert rows[0]["follows"] == 3
```

- [ ] **Step 6: Add failing test for skipped sync with no matching run**

Add:

```python
def test_record_performance_keeps_memory_update_when_no_matching_sqlite_run(
    sqlite_business_api: Path,
) -> None:
    operation_store.upsert_record_from_state(_operation_state(creator_note_id="orphan_note_001"))

    result = api.record_performance({"creator_note_id": "orphan_note_001", "views": 12})

    assert result["updated_record"]["status"] == "performance_recorded"
    assert result["business_sync"]["status"] == "skipped"
    assert result["business_sync"]["reason"] == "matching success run not found"
    assert _performance_rows(sqlite_business_api) == []
```

- [ ] **Step 7: Add failing test for JSON compatibility**

Extend existing `test_record_performance_can_match_creator_note_id` with:

```python
    assert result["business_sync"]["status"] == "skipped"
    assert result["business_sync"]["reason"] == "business tables require sqlite run store"
```

- [ ] **Step 8: Add failing test for sanitized sync failure**

Add:

```python
def test_record_performance_business_sync_failure_is_sanitized(
    sqlite_business_api: Path,
    monkeypatch,
) -> None:
    saved = operation_store.upsert_record_from_state(_operation_state())
    api._save_run(_successful_run_from_operation(saved, run_id="run_perf_sync_failure"))

    def fail_save(record: dict) -> None:
        raise RuntimeError("cookie=secret-token should not leak")

    monkeypatch.setattr(api, "_save_run", fail_save)

    result = api.record_performance({"creator_note_id": "mock_note_001", "views": 100})

    assert result["updated_record"]["status"] == "performance_recorded"
    assert result["business_sync"]["status"] == "failed"
    assert "secret-token" not in result["business_sync"]["reason"]
    assert "cookie=[REDACTED]" in result["business_sync"]["reason"]
```

- [ ] **Step 9: Run tests to verify RED**

Run:

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_creator_note_performance_sync.py -q
```

Expected: new tests fail because `business_sync` is missing or SQLite run/business table is not updated.

---

### Task 2: Implement `/performance` Business Sync

**Files:**
- Modify: `app/api.py`
- Test: `tests/test_creator_note_performance_sync.py`

- [ ] **Step 1: Add skipped/failed result helpers**

Add near `_sanitize_business_sync_error()`:

```python
def _performance_business_sync_result(
    status: str,
    *,
    run_id: str | None = None,
    counts: dict[str, Any] | None = None,
    reason: str | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {"status": status}
    if run_id:
        result["run_id"] = run_id
    if counts is not None:
        result["counts"] = counts
    if reason:
        result["reason"] = reason
    return result
```

- [ ] **Step 2: Add run matching helpers**

Add near `record_performance()`:

```python
def _record_matches_performance_target(
    record: dict[str, Any],
    *,
    operation_record_id: str,
    creator_note_id: str,
    post_id: str,
) -> bool:
    state = record.get("state") if isinstance(record.get("state"), dict) else {}
    summary = record.get("summary") if isinstance(record.get("summary"), dict) else {}
    paths = record.get("paths") if isinstance(record.get("paths"), dict) else {}
    if operation_record_id and state.get("operation_record_id") == operation_record_id:
        return True
    if creator_note_id and (
        state.get("creator_note_id") == creator_note_id
        or summary.get("creator_note_id") == creator_note_id
    ):
        return True
    if post_id and (
        state.get("post_id") == post_id
        or summary.get("post_id") == post_id
        or paths.get("post_id") == post_id
    ):
        return True
    return False


def _find_success_run_for_performance(
    store: SQLiteRunStore,
    updated_record: dict[str, Any],
    *,
    post_id: str,
    creator_note_id: str,
) -> dict[str, Any] | None:
    operation_record_id = str(updated_record.get("record_id") or "").strip()
    clean_creator_note_id = str(creator_note_id or updated_record.get("creator_note_id") or "").strip()
    clean_post_id = str(post_id or updated_record.get("post_id") or "").strip()
    candidates = [
        record
        for record in store.list(limit=500)
        if record.get("status") == "success"
        and _record_matches_performance_target(
            record,
            operation_record_id=operation_record_id,
            creator_note_id=clean_creator_note_id,
            post_id=clean_post_id,
        )
    ]
    if not candidates:
        return None
    candidates.sort(key=lambda item: str(item.get("updated_at") or item.get("created_at") or ""), reverse=True)
    return candidates[0]
```

- [ ] **Step 3: Add state merge helper**

Add near the matching helpers:

```python
def _merge_performance_record_into_run_state(
    run_record: dict[str, Any],
    updated_record: dict[str, Any],
) -> dict[str, Any]:
    state = _state_from_record(run_record)
    if not state:
        state = {}
    state["performance_data"] = dict(updated_record.get("performance_data") or {})
    state["performance_score"] = _int(updated_record.get("performance_score"), default=0)
    state["performance_recorded_at"] = updated_record.get("updated_at") or _now_iso()
    state["review_summary"] = updated_record.get("review_summary") or ""
    state["next_action"] = updated_record.get("next_action") or ""
    state["review_generation"] = updated_record.get("review_generation") or {}
    state["operation_record_id"] = updated_record.get("record_id") or state.get("operation_record_id")
    if updated_record.get("creator_note_id"):
        state["creator_note_id"] = updated_record.get("creator_note_id")
    if updated_record.get("published_url"):
        state["published_url"] = updated_record.get("published_url")
    if updated_record.get("operator_notes"):
        state["operator_notes"] = updated_record.get("operator_notes")

    merged = dict(run_record)
    merged["updated_at"] = _now_iso()
    merged["summary"] = _state_summary(state)
    merged["content"] = _content_payload(state)
    merged["insights"] = _insight_payload(state)
    merged["state"] = state
    merged["paths"] = {
        **(run_record.get("paths") if isinstance(run_record.get("paths"), dict) else {}),
        "post_id": state.get("post_id"),
        "collection_path": state.get("collection_path"),
        "operation_memory_path": state.get("operation_memory_path"),
    }
    return merged
```

- [ ] **Step 4: Add business sync coordinator**

Add:

```python
def _sync_performance_to_business_tables(
    updated_record: dict[str, Any],
    *,
    post_id: str,
    creator_note_id: str,
) -> dict[str, Any]:
    settings = load_settings()
    if settings.run_store_backend != "sqlite":
        return _performance_business_sync_result(
            "skipped",
            reason="business tables require sqlite run store",
        )
    if settings.db_schema != "foundation" or not settings.business_tables_enabled:
        return _performance_business_sync_result(
            "skipped",
            reason="business tables are not enabled",
        )

    store = _run_store()
    if not isinstance(store, SQLiteRunStore):
        return _performance_business_sync_result(
            "skipped",
            reason="business tables require sqlite run store",
        )

    run_record = _find_success_run_for_performance(
        store,
        updated_record,
        post_id=post_id,
        creator_note_id=creator_note_id,
    )
    if run_record is None:
        return _performance_business_sync_result(
            "skipped",
            reason="matching success run not found",
        )

    try:
        merged = _merge_performance_record_into_run_state(run_record, updated_record)
        _save_run(merged)
    except Exception as exc:
        return _performance_business_sync_result(
            "failed",
            run_id=str(run_record.get("run_id") or ""),
            reason=_sanitize_business_sync_error(exc),
        )

    saved = _load_run(str(run_record.get("run_id") or "")) or merged
    summary = saved.get("summary") if isinstance(saved.get("summary"), dict) else {}
    return _performance_business_sync_result(
        "success",
        run_id=str(saved.get("run_id") or ""),
        counts=summary.get("business_table_sync_counts") or {},
    )
```

- [ ] **Step 5: Wire helper into `record_performance()`**

Change the return block to:

```python
    business_sync = _sync_performance_to_business_tables(
        record,
        post_id=post_id,
        creator_note_id=creator_note_id,
    )
    return {
        "memory_path": str(operation_memory_path()),
        "updated_record": _compact_memory_record(record),
        "business_sync": business_sync,
    }
```

- [ ] **Step 6: Run focused tests to verify GREEN**

Run:

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_creator_note_performance_sync.py -q
```

Expected: all tests in `test_creator_note_performance_sync.py` pass.

- [ ] **Step 7: Run related regression tests**

Run:

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_creator_note_performance_sync.py tests/test_api_business_table_sync.py tests/test_business_store.py -q
```

Expected: related API/business-store tests pass.

---

### Task 3: Update Progress Docs and Run Verification

**Files:**
- Modify: `memory/current_progress.md`
- Modify: `memory/project_status_and_roadmap.md`
- Run: verification commands

- [ ] **Step 1: Update progress docs**

Append a short section to both memory files:

```markdown
## 2026-06-13 /performance 到 performance_records 反向同步

本轮目标是收口表现数据闭环：`/performance` 人工录入表现后，运营记忆、SQLite run state 和 `performance_records` 能保持一致。

已完成：
- `/performance` 保持现有入参和运营记忆更新行为。
- SQLite run store + foundation business tables 启用时，会查找匹配的 success run。
- 匹配后把表现数据、表现分、复盘摘要和下一步建议合并回 run state。
- 复用 `_save_run()` 和 `sync_run_business_tables()` 刷新 `performance_records`。
- 非 SQLite、业务表未启用或找不到匹配 run 时返回 `business_sync.status=skipped`，不影响运营记忆更新。
- 同步异常返回 `business_sync.status=failed`，错误信息脱敏。

验证结果：
- 待填入本轮实际命令结果。

下一步建议：
- 在真实 Cookie 小流量复验前，用 SQLite stack smoke 和一条真实发布记录验证表现闭环。
```

- [ ] **Step 2: Run smoke check**

Run:

```powershell
D:\Anaconda\envs\ContentShare\python.exe .\scripts\check_sqlite_stack.py
```

Expected: output contains `"ok": true`.

- [ ] **Step 3: Run compile check**

Run:

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m compileall app scripts tests
```

Expected: exit code 0.

- [ ] **Step 4: Run full test suite**

Run:

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m pytest -q
```

Expected: all tests pass.

- [ ] **Step 5: Replace draft verification line with actual verification results**

Update the “待填入本轮实际命令结果” lines with the exact passed counts and smoke result from Steps 2-4.

- [ ] **Step 6: Inspect staged changes**

Run:

```powershell
git status --short
git diff --check
git diff --stat
```

Expected: only intended files are changed, and no whitespace errors.

- [ ] **Step 7: Commit implementation**

Run:

```powershell
git add -A
git commit -m "feat: sync performance records to business tables"
```

Expected: commit succeeds.

---

## Self-Review

Spec coverage:
- `/performance` compatibility: Task 1 Step 7 and Task 2 Step 5.
- SQLite matching run lookup: Task 2 Step 2.
- run state merge: Task 2 Step 3.
- existing business table writer reuse: Task 2 Step 4.
- response status summary: Task 2 Steps 1 and 5.
- skipped/failed behavior: Task 1 Steps 6-8 and Task 2 Step 4.
- verification: Task 3 Steps 2-4.

Completeness scan:
- The plan contains concrete files, commands, expected outcomes, and code snippets for implementation.

Type consistency:
- `business_sync.status`, `business_sync.run_id`, `business_sync.counts`, and `business_sync.reason` are used consistently in tests and implementation.
