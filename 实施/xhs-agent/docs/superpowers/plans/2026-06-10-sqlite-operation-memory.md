# SQLite Operation Memory Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a SQLite-backed operation memory backend while preserving the existing module-level operation memory API and JSON default behavior.

**Architecture:** Keep business functions in `memory/operation_store.py` and route `load_history()` / `save_history()` through a selected backend. Store full operation records as JSON in SQLite with indexed metadata columns, then reuse the existing Python relevance, pollution filtering, scoring, and review logic.

**Tech Stack:** Python standard library `sqlite3`, existing `python-dotenv` settings loader, `pytest` for tests.

---

## File Structure

- Create: `tests/test_operation_store_sqlite.py`
  - SQLite operation memory backend behavior tests.
- Modify: `memory/operation_store.py`
  - Add backend classes, backend selection, SQLite schema, and path helper.
- Modify: `app/config.py`
  - Add `memory_store_backend` and `memory_db_path`.
- Modify: `nodes/memory_node.py`
  - Display selected memory path through `operation_memory_path()`.
- Modify: `app/api.py`
  - Display selected memory path through `operation_memory_path()`.
- Modify: `scripts/record_performance.py`
  - Display selected memory path through `operation_memory_path()`.
- Modify: `.env.example`
  - Document `XHS_AGENT_MEMORY_STORE` and `XHS_AGENT_MEMORY_DB_PATH`.

## Task 1: Add SQLite Operation Memory Tests

**Files:**
- Create: `tests/test_operation_store_sqlite.py`
- Test: `tests/test_operation_store_sqlite.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_operation_store_sqlite.py` with tests that:

```python
from __future__ import annotations

from pathlib import Path

import pytest

from memory import operation_store as store


def sample_state(post_id: str, topic: str = "小红书新手选题方法") -> dict:
    return {
        "post_id": post_id,
        "publish_status": "success",
        "publish_time": "2026-06-10T10:00:00",
        "user_topic": topic,
        "target_user": "内容创作新手",
        "account_stage": "cold_start",
        "content_type": "step_tutorial",
        "content_format": "image_text",
        "titles": ["选题三步法", "新手选题步骤"],
        "collection_path": None,
        "pain_points": [
            {
                "pain": f"对「{topic}」是否真实可行存在怀疑，需要可信案例和边界说明",
                "evidence": "真的可以做到吗？需要干货",
                "priority": 1,
            }
        ],
        "comment_insights": [
            {
                "pain": f"对「{topic}」是否真实可行存在怀疑，需要可信案例和边界说明",
                "evidence_comments": ["真的可以做到吗？需要干货"],
                "evidence_count": 1,
                "priority": 1,
            }
        ],
        "performance_data": {},
        "review_summary": "草稿已生成。",
        "next_action": "发布后录入表现数据。",
        "review_generation": {"enabled": False, "provider_mode": "template"},
    }


@pytest.fixture()
def sqlite_memory(tmp_path: Path, monkeypatch):
    db_path = tmp_path / "memory.sqlite3"
    monkeypatch.setenv("XHS_AGENT_MEMORY_STORE", "sqlite")
    monkeypatch.setenv("XHS_AGENT_MEMORY_DB_PATH", str(db_path))
    store.MEMORY_BACKEND = None
    yield db_path
    store.MEMORY_BACKEND = None


def test_sqlite_operation_memory_upserts_and_loads_history(sqlite_memory: Path) -> None:
    first = store.upsert_record_from_state(sample_state("output/post.md"))
    second_state = sample_state("output/post.md")
    second_state["titles"] = ["更新后的标题"]
    second = store.upsert_record_from_state(second_state)

    history = store.load_history()

    assert sqlite_memory.exists()
    assert first["record_id"] == second["record_id"]
    assert len(history["records"]) == 1
    assert history["records"][0]["title"] == "更新后的标题"
    assert history["records"][0]["created_at"] == first["created_at"]


def test_sqlite_operation_memory_finds_relevant_records(sqlite_memory: Path) -> None:
    store.upsert_record_from_state(sample_state("output/topic.md", topic="小红书新手选题方法"))
    store.upsert_record_from_state(sample_state("output/other.md", topic="宝宝湿疹护理"))

    records = store.find_relevant_records("小红书新手选题方法", limit=5)

    assert [record["topic"] for record in records] == ["小红书新手选题方法"]


def test_sqlite_operation_memory_successful_patterns_use_performance(sqlite_memory: Path) -> None:
    state = sample_state("output/scored.md")
    state["performance_data"] = {"views": 1000, "likes": 50, "collects": 20, "comments": 8, "follows": 3}
    saved = store.upsert_record_from_state(state)

    patterns = store.find_successful_patterns("小红书新手选题方法", limit=3)

    assert len(patterns) == 1
    assert patterns[0]["record_id"] == saved["record_id"]
    assert patterns[0]["performance_score"] > 0


def test_sqlite_operation_memory_updates_performance(sqlite_memory: Path) -> None:
    saved = store.upsert_record_from_state(sample_state("output/performance.md"))

    updated = store.update_record_performance(
        post_id="output/performance.md",
        performance_data={"views": 1000, "likes": 50, "collects": 20, "comments": 8, "follows": 3},
        published_url="https://example.com/note",
        notes="manual note",
    )

    assert updated["record_id"] == saved["record_id"]
    assert updated["status"] == "performance_recorded"
    assert updated["performance_score"] > 0
    assert updated["published_url"] == "https://example.com/note"
    assert updated["operator_notes"] == "manual note"
    assert store.load_history()["records"][0]["performance_score"] == updated["performance_score"]


def test_sqlite_operation_memory_filters_cross_domain_health_pollution(sqlite_memory: Path) -> None:
    polluted = sample_state("output/polluted.md", topic="小红书新手选题方法")
    polluted["pain_points"] = [{"pain": "对护理方法存在疑问，担心建议不靠谱", "evidence": "旧脏数据", "priority": 1}]
    store.upsert_record_from_state(polluted)
    store.upsert_record_from_state(sample_state("output/clean.md", topic="小红书新手选题方法"))

    records = store.find_relevant_records("小红书新手选题方法", limit=5)

    assert [record["post_id"] for record in records] == ["output/clean.md"]


def test_json_operation_memory_still_loads_and_saves_explicit_path(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("XHS_AGENT_MEMORY_STORE", "json")
    store.MEMORY_BACKEND = None
    path = tmp_path / "operation_history.json"
    history = {"version": 1, "updated_at": None, "records": [store.record_from_state(sample_state("output/json.md"))]}

    store.save_history(history, path=path)
    loaded = store.load_history(path=path)

    assert loaded["records"][0]["post_id"] == "output/json.md"
    store.MEMORY_BACKEND = None
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
python -m pytest tests/test_operation_store_sqlite.py -q
```

Expected: FAIL because `MEMORY_BACKEND` / SQLite memory backend selection does not exist yet.

## Task 2: Implement SQLite Operation Memory Backend

**Files:**
- Modify: `memory/operation_store.py`
- Modify: `app/config.py`
- Test: `tests/test_operation_store_sqlite.py`

- [ ] **Step 1: Add settings**

In `app/config.py`, add fields to `Settings`:

```python
    memory_store_backend: str
    memory_db_path: str
```

Add values in `load_settings()`:

```python
        memory_store_backend=os.getenv("XHS_AGENT_MEMORY_STORE", "json").strip().lower() or "json",
        memory_db_path=os.getenv("XHS_AGENT_MEMORY_DB_PATH", "data/xhs_agent.sqlite3"),
```

- [ ] **Step 2: Add backend infrastructure**

In `memory/operation_store.py`:

- import `json`, `sqlite3`, and `load_settings`
- add `MEMORY_BACKEND = None`
- add `_resolve_project_path()`
- add `operation_memory_path()`
- add `JsonOperationMemoryBackend`
- add `SQLiteOperationMemoryBackend`
- make `load_history()` and `save_history()` use explicit `path` when supplied, otherwise use selected backend

SQLite backend must create `operation_records`, serialize full records into `record_json`, upsert by `record_id`, preserve `created_at` when replacing by `post_id`, and return history records ordered by `created_at ASC`.

- [ ] **Step 3: Update `upsert_record_from_state()` and `update_record_performance()`**

Keep explicit `path` behavior on JSON for tests and repair scripts. When no explicit path is supplied, use `load_history()` and `save_history()` so selected backend is used.

- [ ] **Step 4: Run focused tests**

Run:

```powershell
python -m pytest tests/test_operation_store_sqlite.py -q
```

Expected: PASS.

## Task 3: Update Memory Path Call Sites

**Files:**
- Modify: `nodes/memory_node.py`
- Modify: `app/api.py`
- Modify: `scripts/record_performance.py`
- Test: `tests/test_operation_store_sqlite.py`

- [ ] **Step 1: Replace `HISTORY_PATH` display imports**

Use `operation_memory_path()` for displayed memory path values while keeping behavior unchanged.

- [ ] **Step 2: Run tests**

Run:

```powershell
python -m pytest tests/test_operation_store_sqlite.py -q
```

Expected: PASS.

## Task 4: Document Environment Configuration

**Files:**
- Modify: `.env.example`

- [ ] **Step 1: Add memory backend config**

Add:

```env
# Operation memory backend.
# json keeps memory/operation_history.json behavior.
# sqlite stores operation records in the local SQLite database.
XHS_AGENT_MEMORY_STORE=json
XHS_AGENT_MEMORY_DB_PATH=data/xhs_agent.sqlite3
```

- [ ] **Step 2: Verify keys exist**

Run:

```powershell
rg -n "XHS_AGENT_MEMORY_STORE|XHS_AGENT_MEMORY_DB_PATH" .env.example
```

Expected: both keys are present.

## Task 5: Final Verification

**Files:**
- Test all touched files.

- [ ] **Step 1: Run all tests**

Run:

```powershell
python -m pytest -q
```

Expected: PASS.

- [ ] **Step 2: Compile**

Run:

```powershell
python -m compileall app nodes routers platforms memory scripts llm
```

Expected: PASS.

- [ ] **Step 3: SQLite memory smoke check**

Run:

```powershell
$env:XHS_AGENT_MEMORY_STORE='sqlite'
$env:XHS_AGENT_MEMORY_DB_PATH='data/tmp_operation_memory_check.sqlite3'
$env:LLM_MODEL_NAME='mock'
python -c "from memory import operation_store as s; s.MEMORY_BACKEND=None; state={'post_id':'output/tmp-memory.md','publish_status':'success','user_topic':'小红书新手选题方法','target_user':'内容创作新手','content_type':'step_tutorial','content_format':'image_text','titles':['测试标题'],'pain_points':[{'pain':'不知道从哪里开始','evidence':'需要步骤','priority':1}],'comment_insights':[],'performance_data':{},'review_summary':'已生成','next_action':'录入表现'}; r=s.upsert_record_from_state(state); print(r['record_id']); print(len(s.find_relevant_records('小红书新手选题方法'))); u=s.update_record_performance('output/tmp-memory.md', {'views':100,'likes':5,'collects':2,'comments':1,'follows':0}); print(u['status'], u['performance_score'])"
```

Expected output includes one `op_` record id, relevant record count `1`, and `performance_recorded`.

- [ ] **Step 4: Remove temporary smoke DB**

Run:

```powershell
$workspace=(Resolve-Path '.').Path
$targets=@('data\tmp_operation_memory_check.sqlite3','data\tmp_operation_memory_check.sqlite3-wal','data\tmp_operation_memory_check.sqlite3-shm','data\tmp_operation_memory_check.sqlite3-journal')
foreach ($relative in $targets) {
  $target=Join-Path $workspace $relative
  if (Test-Path -LiteralPath $target) {
    $resolved=(Resolve-Path -LiteralPath $target).Path
    if ($resolved.StartsWith($workspace, [System.StringComparison]::OrdinalIgnoreCase)) {
      Remove-Item -LiteralPath $resolved -Force
    } else {
      throw "Refusing to remove outside workspace: $resolved"
    }
  }
}
```

Expected: no temp DB files remain.

## Self-Review

- Spec coverage: Plan covers SQLite operation memory backend, JSON default, path displays, environment docs, and tests.
- Completion marker scan: No unfinished markers remain.
- Scope check: No queue, API/worker split, JSON migration, ORM, PostgreSQL, or GraphRAG work is included.
