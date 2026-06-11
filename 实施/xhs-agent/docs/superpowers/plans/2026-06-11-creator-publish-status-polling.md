# Creator Publish Status Polling Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a read-only creator note status sync path that can report platform visibility, status, and metrics by `creator_note_id`.

**Architecture:** Reuse `platforms.creator.list_published_notes()` as the only platform read. Add a small normalizer in `platforms/creator.py`, expose it through `app/api.py`, and render the extra status fields in the existing workbench creator notes list. No publishing, retries, background polling, or memory writes are introduced.

**Tech Stack:** Python standard library API, existing Spider_XHS creator adapter, pytest, static HTML/JavaScript workbench.

---

### Task 1: Creator Status Normalizer

**Files:**
- Modify: `platforms/creator.py`
- Test: `tests/test_creator_platform.py`

- [ ] **Step 1: Write the failing status sync tests**

Append these tests after `test_normalize_note_redacts_sensitive_raw_fields()` in `tests/test_creator_platform.py`:

```python
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
```

- [ ] **Step 2: Run the tests and verify they fail**

Run:

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_creator_platform.py::test_get_published_note_status_returns_synced_status tests/test_creator_platform.py::test_get_published_note_status_returns_not_found tests/test_creator_platform.py::test_get_published_note_status_returns_unavailable_on_list_failure -q
```

Expected: fail because `platforms.creator.get_published_note_status` does not exist.

- [ ] **Step 3: Implement the minimal normalizer**

Add this helper block in `platforms/creator.py` after `_spider_list_published_notes()` and before `list_published_notes()`:

```python
def _safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _visibility_label(raw: dict[str, Any], fallback: str) -> str:
    permission_msg = str(raw.get("permission_msg") or "").strip()
    if permission_msg:
        return permission_msg
    permission_code = raw.get("permission_code")
    if permission_code == 1 or str(permission_code) == "1":
        return VISIBILITY_PRIVATE
    return fallback or ""


def _status_from_note(note: dict[str, Any]) -> dict[str, Any]:
    raw = note.get("raw") if isinstance(note.get("raw"), dict) else {}
    return {
        "ok": True,
        "status": "synced",
        "creator_note_id": note.get("note_id"),
        "title": note.get("title") or "",
        "visibility": note.get("visibility") or "",
        "visibility_label": _visibility_label(raw, str(note.get("visibility") or "")),
        "platform_type": raw.get("type") or note.get("visibility") or "",
        "permission_code": raw.get("permission_code"),
        "tab_status": raw.get("tab_status"),
        "metrics_snapshot": {
            "views": _safe_int(raw.get("view_count")),
            "likes": _safe_int(raw.get("likes")),
            "collects": _safe_int(raw.get("collected_count")),
            "comments": _safe_int(raw.get("comments_count")),
        },
        "raw": redact_sensitive(raw),
    }


def get_published_note_status(creator_note_id: str, limit: int = 50) -> dict[str, Any]:
    clean_note_id = str(creator_note_id or "").strip()
    if not clean_note_id:
        return {
            "ok": False,
            "status": "not_found",
            "creator_note_id": "",
            "error": "creator_note_id is required",
        }

    list_result = list_published_notes(limit=max(0, int(limit)))
    if list_result.get("ok") is not True:
        return {
            "ok": False,
            "status": "unavailable",
            "creator_note_id": clean_note_id,
            "error": str(list_result.get("error") or "creator notes unavailable"),
            "raw": redact_sensitive(list_result),
        }

    for note in list_result.get("notes") or []:
        if isinstance(note, dict) and str(note.get("note_id") or "") == clean_note_id:
            return _status_from_note(note)

    return {
        "ok": False,
        "status": "not_found",
        "creator_note_id": clean_note_id,
        "error": f"creator note not found: {clean_note_id}",
    }
```

- [ ] **Step 4: Run the creator tests**

Run:

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_creator_platform.py -q
```

Expected: all creator platform tests pass.

---

### Task 2: API Helper And HTTP Route

**Files:**
- Modify: `app/api.py`
- Test: `tests/test_creator_note_performance_sync.py`

- [ ] **Step 1: Write failing API tests**

Append these tests to `tests/test_creator_note_performance_sync.py`:

```python
def test_get_creator_note_status_returns_adapter_result(isolated_api, monkeypatch) -> None:
    expected = {
        "ok": True,
        "status": "synced",
        "creator_note_id": "mock_note_001",
        "visibility_label": "仅自己可见",
    }

    def fake_status(creator_note_id: str, limit: int = 50) -> dict:
        assert creator_note_id == "mock_note_001"
        assert limit == 50
        return expected

    monkeypatch.setattr(api.creator_platform, "get_published_note_status", fake_status)

    result = api.get_creator_note_status("mock_note_001")

    assert result == {"creator_note_status": expected}
```

- [ ] **Step 2: Run the API test and verify it fails**

Run:

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_creator_note_performance_sync.py::test_get_creator_note_status_returns_adapter_result -q
```

Expected: fail because `app.api.get_creator_note_status` does not exist.

- [ ] **Step 3: Add the API helper and route**

In `app/api.py`, add this helper after `list_creator_notes()`:

```python
def get_creator_note_status(creator_note_id: str, limit: int = 50) -> dict[str, Any]:
    return {
        "creator_note_status": creator_platform.get_published_note_status(
            creator_note_id=creator_note_id,
            limit=max(0, int(limit)),
        )
    }
```

In the `do_GET()` router section that handles `/creator/notes`, add this route before the existing `/creator/notes` branch:

```python
        if path == "/creator/notes/status":
            creator_note_id = str(query.get("creator_note_id", [""])[0] or "").strip()
            limit = int(query.get("limit", ["50"])[0] or 50)
            self._send_json(200, {"ok": True, **get_creator_note_status(creator_note_id, limit=limit)})
            return
```

- [ ] **Step 4: Run the API sync tests**

Run:

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_creator_note_performance_sync.py -q
```

Expected: all creator note performance sync tests pass.

---

### Task 3: Workbench Status Summary

**Files:**
- Modify: `app/static/app.js`
- Test: `tests/test_workbench_creator_notes_static.py`

- [ ] **Step 1: Write failing frontend static tests**

Append this test to `tests/test_workbench_creator_notes_static.py`:

```python
def test_creator_notes_render_status_summary():
    assert "renderCreatorNoteStatus(note)" in APP_JS
    assert "note.visibility_label" in APP_JS
    assert "metricsSnapshot.views" in APP_JS
    assert "平台状态" in APP_JS
```

- [ ] **Step 2: Run the frontend static test and verify it fails**

Run:

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_workbench_creator_notes_static.py::test_creator_notes_render_status_summary -q
```

Expected: fail because `renderCreatorNoteStatus()` is not implemented.

- [ ] **Step 3: Add status rendering helper**

In `app/static/app.js`, add this helper near the other render helpers:

```javascript
function renderCreatorNoteStatus(note) {
  const raw = note.raw || {};
  const metricsSnapshot = note.metrics_snapshot || {
    views: raw.view_count || 0,
    likes: raw.likes || 0,
    collects: raw.collected_count || 0,
    comments: raw.comments_count || 0,
  };
  const visibilityLabel = note.visibility_label || raw.permission_msg || note.visibility || "-";
  return `
    <div class="creator-note-status">
      <span>平台状态 ${escapeHtml(visibilityLabel)}</span>
      <span>浏览 ${escapeHtml(metricsSnapshot.views || 0)}</span>
      <span>赞 ${escapeHtml(metricsSnapshot.likes || 0)}</span>
      <span>藏 ${escapeHtml(metricsSnapshot.collects || 0)}</span>
      <span>评 ${escapeHtml(metricsSnapshot.comments || 0)}</span>
    </div>
  `;
}
```

Update the creator notes list rendering inside `syncCreatorNotes()` so each list item includes:

```javascript
${renderCreatorNoteStatus(note)}
```

- [ ] **Step 4: Run frontend static tests and JS syntax check**

Run:

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_workbench_creator_notes_static.py -q
node --check app\static\app.js
```

Expected: static tests pass and Node reports no syntax errors.

---

### Task 4: Verification, Memory, And Commit

**Files:**
- Modify: `memory/current_progress.md`

- [ ] **Step 1: Run focused test suite**

Run:

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_creator_platform.py tests/test_creator_note_performance_sync.py tests/test_workbench_creator_notes_static.py -q
```

Expected: all focused tests pass.

- [ ] **Step 2: Run full verification**

Run:

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m pytest -q
D:\Anaconda\envs\ContentShare\python.exe -m compileall app nodes routers platforms memory scripts llm
node --check app\static\app.js
```

Expected: pytest passes, compileall exits 0, and Node syntax check exits 0.

- [ ] **Step 3: Run true read-only platform smoke**

Run:

```powershell
$env:CREATOR_MODE='spider_xhs'; D:\Anaconda\envs\ContentShare\python.exe -c "import json; from platforms.creator import get_published_note_status; result=get_published_note_status('6a2abffc0000000022027f7a'); print(json.dumps(result, ensure_ascii=False, indent=2))"
```

Expected: `status` is `synced`, `creator_note_id` is `6a2abffc0000000022027f7a`, and `visibility_label` is `仅自己可见`.

- [ ] **Step 4: Update project memory**

Prepend this section to `memory/current_progress.md`:

```markdown
## 2026-06-11 creator 发布状态只读同步

本轮目标是在真实 creator v2 作品列表和表现回填烟测之后，补上只读发布状态同步能力。

已完成：
- 新增按 `creator_note_id` 查询平台状态的后端归一化函数。
- 状态同步复用 creator v2 作品列表，不触发发布、修改、公开、删除或重试。
- 状态结果包含 `synced` / `not_found` / `unavailable`、可见性提示、权限字段和指标快照。
- 工作台作品列表展示平台状态摘要和指标快照。

已验证：
- creator 平台状态单测通过。
- API 与工作台静态契约测试通过。
- 全量测试、compileall 和前端语法检查通过。
- 真实只读状态同步可找到 `creator_note_id=6a2abffc0000000022027f7a`。

当前限制：
- 本轮不是后台自动轮询，不写回主运营记忆。
- 表现数据仍需通过现有人工表现录入入口写入。
```

- [ ] **Step 5: Commit implementation**

Run:

```powershell
git status --short
git diff --check
git add platforms/creator.py app/api.py app/static/app.js tests/test_creator_platform.py tests/test_creator_note_performance_sync.py tests/test_workbench_creator_notes_static.py memory/current_progress.md
git commit -m "feat: add creator status sync"
```

Expected: commit succeeds and working tree is clean.
