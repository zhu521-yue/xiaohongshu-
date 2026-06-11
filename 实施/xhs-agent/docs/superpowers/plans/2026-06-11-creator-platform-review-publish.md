# Creator Platform Review Publish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Connect opt-in private creator-platform publishing to the existing approve-run workflow while keeping default approval local-only.

**Architecture:** Keep the integration at the API review boundary. `app/api.py` validates opt-in approval payload fields, saves the local Markdown draft first, then calls the M19a creator adapter only when explicitly requested. Operation memory stores creator metadata as additional fields while `post_id` remains the local Markdown path.

**Tech Stack:** Python standard library HTTP API, existing `LocalRunStore` / `SQLiteRunStore`, existing `memory.operation_store`, existing `platforms.creator`, pytest.

---

## File Structure

- Modify `app/api.py`
  - Add creator publishing summary fields.
  - Add small helper functions for approval payload validation, draft mapping, compact result storage, and opt-in creator publishing.
  - Call the helper from `approve_run()` after local Markdown save and before review/memory write.
- Modify `platforms/creator.py`
  - Add a public `creator_mode()` wrapper so API code does not call the private `_mode()` helper.
- Modify `memory/operation_store.py`
  - Preserve creator publish metadata in `record_from_state()`.
- Create `tests/test_api_creator_review_publish.py`
  - Cover default local-only approval, mock creator success, missing confirmation rejection, video request failure without adapter call, and adapter exception failure recording.
- Modify `memory/current_progress.md`
  - Add M19b progress after implementation and verification.
- Modify `D:\codex\project\小红书内容分享\AGENTS.md`
  - Update project memory after M19b implementation.

---

### Task 1: Add Review-Flow Creator Publishing Tests

**Files:**
- Create: `tests/test_api_creator_review_publish.py`
- Modify: none
- Test: `tests/test_api_creator_review_publish.py`

- [ ] **Step 1: Write the failing test file**

Create `tests/test_api_creator_review_publish.py` with:

```python
from __future__ import annotations

from pathlib import Path

import pytest

from app import api
from app.run_store import LocalRunStore
from memory import operation_store


def _reset_services() -> None:
    api.RUN_STORE = None
    api.RUN_QUEUE_SERVICE = None
    operation_store.MEMORY_BACKEND = None


@pytest.fixture()
def isolated_api(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("XHS_AGENT_RUN_STORE", "json")
    monkeypatch.setenv("XHS_AGENT_RUN_QUEUE", "local")
    monkeypatch.setenv("XHS_AGENT_MEMORY_STORE", "json")
    monkeypatch.setenv("CREATOR_MODE", "mock")
    monkeypatch.setattr(api, "RUN_STORE", LocalRunStore(tmp_path / "runs", json_default=api._json_default))
    monkeypatch.setattr(api, "RUNS_DIR", tmp_path / "runs")
    monkeypatch.setattr(operation_store, "MEMORY_BACKEND", operation_store.JsonOperationMemoryBackend(tmp_path / "operation_history.json"))
    monkeypatch.setattr(api.publish_node, "OUTPUT_DIR", tmp_path / "markdown_exports")
    yield tmp_path
    _reset_services()


def _generated_record(run_id: str = "run_creator_001", *, content_format: str = "image_text") -> dict:
    if content_format == "video":
        content = {
            "video_script": {
                "title": "视频测试标题",
                "hook": "开场",
                "talking_points": ["要点"],
                "shot_plan": [],
            },
            "tags": ["小红书运营"],
            "comment_call": "你会怎么做？",
        }
        state_content = {
            "video_script": content["video_script"],
            "tags": content["tags"],
            "comment_call": content["comment_call"],
        }
    else:
        content = {
            "titles": ["私密发布测试标题"],
            "cover_texts": ["封面"],
            "body": "这是一段用于私密发布的正文。",
            "image_page_plan": [{"page": 1, "title": "第一页", "text": "正文重点"}],
            "image_prompts": ["图片提示词"],
            "tags": ["小红书运营", "内容创作"],
            "comment_call": "你准备什么时候开始？",
        }
        state_content = dict(content)

    state = {
        "user_topic": "小红书新手选题方法",
        "target_user": "内容创作新手",
        "user_selected_format": content_format,
        "content_format": content_format,
        "content_type": "step_tutorial",
        "compliance_risk_level": "low",
        "compliance_issues": [],
        "human_approved": False,
        "publish_status": "pending",
        "post_id": None,
        "pain_points": [{"pain": "不知道怎么开始", "evidence": "评论证据", "priority": 1}],
        "comment_insights": [],
        "comment_fetch_errors": [],
        **state_content,
    }
    return {
        "run_id": run_id,
        "status": "success",
        "created_at": "2026-06-11T10:00:00",
        "updated_at": "2026-06-11T10:00:00",
        "started_at": "2026-06-11T09:59:00",
        "finished_at": "2026-06-11T10:00:00",
        "request": {
            "topic": "小红书新手选题方法",
            "target_user": "内容创作新手",
            "format": content_format,
            "goal": "生成一篇冷启动阶段的知识分享内容",
            "approve": False,
            "engine": "langgraph",
            "collect_limit": 3,
            "save_collection": False,
        },
        "summary": api._state_summary(state),
        "content": content,
        "insights": {
            "pain_points": state["pain_points"],
            "comment_insights": [],
            "comment_fetch_errors": [],
        },
        "state": state,
        "paths": {
            "post_id": None,
            "collection_path": None,
            "operation_memory_path": None,
        },
        "error": None,
    }


def _save_generated(record: dict) -> None:
    api._save_run(record)


def test_approve_without_creator_publish_does_not_call_creator_adapter(isolated_api, monkeypatch) -> None:
    calls = []

    def fail_if_called(*args, **kwargs):
        calls.append((args, kwargs))
        raise AssertionError("creator adapter should not be called")

    monkeypatch.setattr(api.creator_platform, "publish_private_image_text", fail_if_called)
    record = _generated_record()
    _save_generated(record)

    reviewed = api.approve_run(record["run_id"], {"feedback": "人工审核通过。"})

    assert calls == []
    assert reviewed["summary"]["publish_status"] == "success"
    assert reviewed["summary"]["creator_publish_requested"] is False
    assert reviewed["summary"]["creator_publish_status"] == "not_requested"
    assert reviewed["state"]["operation_memory_written"] is True


def test_approve_with_creator_publish_records_mock_creator_note(isolated_api) -> None:
    record = _generated_record()
    _save_generated(record)

    reviewed = api.approve_run(
        record["run_id"],
        {
            "feedback": "人工审核通过。",
            "creator_publish": True,
            "creator_publish_private": True,
            "creator_human_confirmed": True,
        },
    )

    assert reviewed["summary"]["publish_status"] == "success"
    assert reviewed["summary"]["creator_publish_requested"] is True
    assert reviewed["summary"]["creator_publish_status"] == "success"
    assert reviewed["summary"]["creator_publish_mode"] == "mock"
    assert reviewed["summary"]["creator_note_id"].startswith("mock_private_")
    assert reviewed["state"]["creator_publish_result"]["visibility"] == "private"
    assert reviewed["state"]["operation_memory_written"] is True

    history = operation_store.load_history()
    saved = history["records"][-1]
    assert saved["creator_publish_requested"] is True
    assert saved["creator_publish_status"] == "success"
    assert saved["creator_note_id"].startswith("mock_private_")
    assert saved["post_id"] == reviewed["summary"]["post_id"]


def test_creator_publish_requires_explicit_human_confirmation(isolated_api, monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(
        api.creator_platform,
        "publish_private_image_text",
        lambda *args, **kwargs: calls.append((args, kwargs)),
    )
    record = _generated_record()
    _save_generated(record)

    with pytest.raises(ValueError, match="creator_human_confirmed"):
        api.approve_run(
            record["run_id"],
            {
                "feedback": "人工审核通过。",
                "creator_publish": True,
                "creator_publish_private": True,
            },
        )

    assert calls == []


def test_video_creator_publish_request_records_failed_without_calling_adapter(isolated_api, monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(
        api.creator_platform,
        "publish_private_image_text",
        lambda *args, **kwargs: calls.append((args, kwargs)),
    )
    record = _generated_record("run_creator_video", content_format="video")
    _save_generated(record)

    reviewed = api.approve_run(
        record["run_id"],
        {
            "feedback": "人工审核通过。",
            "creator_publish": True,
            "creator_publish_private": True,
            "creator_human_confirmed": True,
        },
    )

    assert calls == []
    assert reviewed["summary"]["publish_status"] == "success"
    assert reviewed["summary"]["creator_publish_requested"] is True
    assert reviewed["summary"]["creator_publish_status"] == "failed"
    assert "image_text" in reviewed["summary"]["creator_publish_error"]
    assert reviewed["state"]["operation_memory_written"] is True


def test_creator_adapter_exception_records_failure_after_local_save(isolated_api, monkeypatch) -> None:
    def raise_adapter_error(*args, **kwargs):
        raise RuntimeError("creator adapter unavailable")

    monkeypatch.setattr(api.creator_platform, "publish_private_image_text", raise_adapter_error)
    record = _generated_record()
    _save_generated(record)

    reviewed = api.approve_run(
        record["run_id"],
        {
            "feedback": "人工审核通过。",
            "creator_publish": True,
            "creator_publish_private": True,
            "creator_human_confirmed": True,
        },
    )

    assert reviewed["summary"]["publish_status"] == "success"
    assert reviewed["summary"]["post_id"]
    assert reviewed["summary"]["creator_publish_status"] == "failed"
    assert "creator adapter unavailable" in reviewed["summary"]["creator_publish_error"]
    assert reviewed["state"]["operation_memory_written"] is True

    history = operation_store.load_history()
    saved = history["records"][-1]
    assert saved["creator_publish_status"] == "failed"
    assert "creator adapter unavailable" in saved["creator_publish_error"]
```

- [ ] **Step 2: Run the new test file and verify it fails**

Run:

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_api_creator_review_publish.py -q
```

Expected: fail because `app.api` does not yet expose `creator_platform`, creator summary fields, or creator approval behavior.

- [ ] **Step 3: Commit only if no production code was changed**

Do not commit yet if the test file cannot import because of a simple typo. Fix test typos and rerun until the failures are about missing M19b behavior.

---

### Task 2: Expose Creator Mode Publicly

**Files:**
- Modify: `platforms/creator.py`
- Test: `tests/test_creator_platform.py`

- [ ] **Step 1: Add a failing test for public creator mode**

Append to `tests/test_creator_platform.py`:

```python
def test_creator_mode_returns_normalized_mode(monkeypatch) -> None:
    monkeypatch.setenv("CREATOR_MODE", " MOCK ")

    assert creator.creator_mode() == "mock"
```

- [ ] **Step 2: Run the focused test and verify it fails**

Run:

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_creator_platform.py::test_creator_mode_returns_normalized_mode -q
```

Expected: fail with `AttributeError` because `creator_mode()` does not exist.

- [ ] **Step 3: Implement the public wrapper**

Add near `_mode()` in `platforms/creator.py`:

```python
def creator_mode() -> str:
    return _mode()
```

- [ ] **Step 4: Run creator platform tests**

Run:

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_creator_platform.py -q
```

Expected: all creator platform tests pass.

- [ ] **Step 5: Commit**

Run:

```powershell
git add platforms/creator.py tests/test_creator_platform.py
git commit -m "feat: expose creator platform mode"
```

---

### Task 3: Implement Opt-In Creator Publish In Approval Flow

**Files:**
- Modify: `app/api.py`
- Test: `tests/test_api_creator_review_publish.py`

- [ ] **Step 1: Import the creator adapter and publish module alias**

In `app/api.py`, change the publish-node import block from:

```python
from nodes.publish_node import publish_or_schedule
```

to:

```python
from nodes import publish_node
from platforms import creator as creator_platform
```

Then update the existing call:

```python
state.update(publish_or_schedule(state))
```

to:

```python
state.update(publish_node.publish_or_schedule(state))
```

This keeps tests able to monkeypatch `api.publish_node.OUTPUT_DIR`.

- [ ] **Step 2: Add creator fields to run summary**

In `_state_summary()`, add:

```python
        "creator_publish_requested": state.get("creator_publish_requested"),
        "creator_publish_status": state.get("creator_publish_status"),
        "creator_publish_mode": state.get("creator_publish_mode"),
        "creator_note_id": state.get("creator_note_id"),
        "creator_publish_error": state.get("creator_publish_error"),
```

Place these near `publish_status` and `post_id`.

- [ ] **Step 3: Add helper functions before `approve_run()`**

Add these helpers above `approve_run()`:

```python
def _creator_publish_not_requested() -> dict[str, Any]:
    return {
        "creator_publish_requested": False,
        "creator_publish_status": "not_requested",
        "creator_publish_mode": creator_platform.creator_mode(),
        "creator_note_id": None,
        "creator_publish_error": None,
        "creator_publish_result": {},
    }


def _creator_publish_failed(error: str, *, requested: bool = True) -> dict[str, Any]:
    return {
        "creator_publish_requested": requested,
        "creator_publish_status": "failed",
        "creator_publish_mode": creator_platform.creator_mode(),
        "creator_note_id": None,
        "creator_publish_error": str(error),
        "creator_publish_result": {
            "ok": False,
            "mode": creator_platform.creator_mode(),
            "platform": "xhs_creator",
            "error": str(error),
        },
    }


def _compact_creator_publish_result(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "ok": result.get("ok") is True,
        "mode": result.get("mode"),
        "platform": result.get("platform"),
        "visibility": result.get("visibility"),
        "note_id": result.get("note_id"),
        "error": result.get("error"),
    }


def _creator_publish_success(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "creator_publish_requested": True,
        "creator_publish_status": "success",
        "creator_publish_mode": str(result.get("mode") or creator_platform.creator_mode()),
        "creator_note_id": result.get("note_id"),
        "creator_publish_error": None,
        "creator_publish_result": _compact_creator_publish_result(result),
    }


def _validate_creator_publish_payload(payload: dict[str, Any]) -> None:
    if not _bool(payload.get("creator_publish"), default=False):
        return
    if _bool(payload.get("creator_publish_private"), default=False) is not True:
        raise ValueError("creator_publish_private=True is required for creator publishing")
    if _bool(payload.get("creator_human_confirmed"), default=False) is not True:
        raise ValueError("creator_human_confirmed=True is required for creator publishing")


def _creator_description_from_state(state: dict[str, Any]) -> str:
    parts = [str(state.get("body") or "").strip()]
    tags = [str(tag).strip().lstrip("#") for tag in state.get("tags") or [] if str(tag).strip()]
    if tags:
        parts.append(" ".join(f"#{tag}" for tag in tags))
    comment_call = str(state.get("comment_call") or "").strip()
    if comment_call:
        parts.append(comment_call)
    return "\n\n".join(part for part in parts if part).strip()


def _creator_images_from_state(state: dict[str, Any], *, mode: str) -> list[Any]:
    images = state.get("creator_image_bytes") or state.get("creator_images") or []
    if isinstance(images, list) and images:
        return images
    if mode == "mock":
        return [b"mock-image-bytes"]
    raise ValueError("creator publishing requires image bytes in state when CREATOR_MODE=spider_xhs")


def _build_creator_image_text_draft(state: dict[str, Any], *, mode: str) -> dict[str, Any]:
    title = str((state.get("titles") or [state.get("user_topic") or "未命名笔记"])[0]).strip()
    desc = _creator_description_from_state(state)
    return {
        "title": title,
        "desc": desc or title,
        "images": _creator_images_from_state(state, mode=mode),
        "topics": [str(tag).strip().lstrip("#") for tag in state.get("tags") or [] if str(tag).strip()],
    }


def _publish_creator_private_if_requested(state: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    if not _bool(payload.get("creator_publish"), default=False):
        return _creator_publish_not_requested()

    mode = creator_platform.creator_mode()
    if state.get("content_format") != "image_text":
        return _creator_publish_failed("creator publishing is image_text only in M19b")

    try:
        draft = _build_creator_image_text_draft(state, mode=mode)
        result = creator_platform.publish_private_image_text(draft, human_confirmed=True)
    except Exception as exc:
        return _creator_publish_failed(str(exc))

    if result.get("ok") is True:
        return _creator_publish_success(result)
    return _creator_publish_failed(str(result.get("error") or "creator publish failed"))
```

- [ ] **Step 4: Wire helpers into `approve_run()`**

In `approve_run()`, after `payload = payload or {}`, add:

```python
    _validate_creator_publish_payload(payload)
```

Then replace the publish/review/memory block:

```python
    state.update(publish_or_schedule(state))
    state.update(review_performance(state))
    state.update(write_operation_memory(state))
```

with:

```python
    state.update(publish_node.publish_or_schedule(state))
    state.update(_publish_creator_private_if_requested(state, payload))
    state.update(review_performance(state))
    state.update(write_operation_memory(state))
```

- [ ] **Step 5: Run the review publish tests**

Run:

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_api_creator_review_publish.py -q
```

Expected: tests may still fail on operation memory fields until Task 4 is implemented. Summary-level tests should pass.

---

### Task 4: Preserve Creator Metadata In Operation Memory

**Files:**
- Modify: `memory/operation_store.py`
- Modify: `app/api.py`
- Test: `tests/test_api_creator_review_publish.py`

- [ ] **Step 1: Add operation record fields**

In `memory/operation_store.py`, update `record_from_state()` by adding these fields to the returned dict after `publish_time`:

```python
        "creator_publish_requested": state.get("creator_publish_requested"),
        "creator_publish_status": state.get("creator_publish_status"),
        "creator_publish_mode": state.get("creator_publish_mode"),
        "creator_note_id": state.get("creator_note_id"),
        "creator_publish_error": state.get("creator_publish_error"),
```

- [ ] **Step 2: Include creator fields in compact memory API responses**

In `app/api.py`, update `_compact_memory_record()` by adding:

```python
        "creator_publish_requested": record.get("creator_publish_requested"),
        "creator_publish_status": record.get("creator_publish_status"),
        "creator_publish_mode": record.get("creator_publish_mode"),
        "creator_note_id": record.get("creator_note_id"),
        "creator_publish_error": record.get("creator_publish_error"),
```

- [ ] **Step 3: Run the review publish tests**

Run:

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_api_creator_review_publish.py -q
```

Expected: all tests in `tests/test_api_creator_review_publish.py` pass.

- [ ] **Step 4: Run operation store tests**

Run:

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_operation_store_sqlite.py -q
```

Expected: existing operation memory tests pass.

- [ ] **Step 5: Commit**

Run:

```powershell
git add app/api.py memory/operation_store.py tests/test_api_creator_review_publish.py
git commit -m "feat: publish approved runs to creator platform"
```

---

### Task 5: Add Operator Documentation And Progress Memory

**Files:**
- Create: `docs/m19b-creator-review-publish.md`
- Modify: `memory/current_progress.md`
- Modify: `D:\codex\project\小红书内容分享\AGENTS.md`

- [ ] **Step 1: Add M19b operator doc**

Create `docs/m19b-creator-review-publish.md` with:

```markdown
# M19b Creator Review Publish

M19b connects creator-platform private publishing to the approve-run API.

Default approval still only saves the local Markdown draft and writes operation memory:

```json
{
  "feedback": "人工审核通过。"
}
```

Opt-in private creator publishing requires all three flags:

```json
{
  "feedback": "人工审核通过。",
  "creator_publish": true,
  "creator_publish_private": true,
  "creator_human_confirmed": true
}
```

## Boundaries

- The frontend button remains local-only in this milestone.
- Creator publishing is image-text only.
- Mock mode can use sample image bytes.
- Real `spider_xhs` mode requires actual image bytes in the run state and `XHS_CREATOR_COOKIES`.
- `publish_status` means local Markdown save status.
- `creator_publish_status` means creator-platform publish status.
- `post_id` remains the local Markdown path.
- `creator_note_id` stores the creator-platform note ID when available.

## Self-Test

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_api_creator_review_publish.py -q
D:\Anaconda\envs\ContentShare\python.exe -m pytest -q
D:\Anaconda\envs\ContentShare\python.exe -m compileall app nodes routers platforms memory scripts llm
```
```

- [ ] **Step 2: Update `memory/current_progress.md`**

Add a new top section:

```markdown
## 2026-06-11 M19b 审核通过后私密发布接入

本轮目标是在不改变前端默认行为的前提下，把创作者平台私密发布接入审核 API。默认审核仍只保存本地 Markdown 和写入运营记忆；只有审批请求显式带 `creator_publish=true`、`creator_publish_private=true`、`creator_human_confirmed=true` 时，才触发创作者平台私密发布。

已完成：
- `approve_run()` 支持显式 creator publish 参数。
- 默认审核不调用创作者平台。
- mock 模式私密发布结果会回填 `creator_note_id` 和 `creator_publish_status`。
- 视频内容请求 creator publish 时会保存本地草稿，但 creator publish 标记为失败。
- 创作者平台异常不会抹掉本地草稿保存结果，运营记忆仍会写入失败状态。
- 运营记忆记录 creator publish 元数据。

已验证：
- `D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_api_creator_review_publish.py -q` 通过。
- `D:\Anaconda\envs\ContentShare\python.exe -m pytest -q` 通过。
- `D:\Anaconda\envs\ContentShare\python.exe -m compileall app nodes routers platforms memory scripts llm` 通过。

当前限制：
- 前端暂未新增“同时私密发布到创作者平台”的勾选项。
- 真实 `spider_xhs` 发布还需要 run state 里有真实图片字节。
- 暂不支持视频、公开发布、定时发布和失败重试。
```

- [ ] **Step 3: Update root `AGENTS.md`**

In `D:\codex\project\小红书内容分享\AGENTS.md`, update current stage with:

```markdown
- M19b 已完成审核 API 显式触发创作者平台私密发布：默认审核仍保存本地草稿，显式参数才触发 mock/真实创作者适配器。
```

Update current priority so the next step points to frontend publish controls or real image bytes:

```markdown
2. 下一步优先补 M19c：前端增加私密发布选项，或先补真实图片字节生成/选择链路。
```

- [ ] **Step 4: Commit docs and memory**

Run:

```powershell
git add docs/m19b-creator-review-publish.md memory/current_progress.md ../../AGENTS.md
git commit -m "docs: add creator review publish guide"
```

---

### Task 6: Final Verification

**Files:**
- No code changes unless verification finds a defect.

- [ ] **Step 1: Run creator platform tests**

Run:

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_creator_platform.py tests/test_api_creator_review_publish.py -q
```

Expected: all targeted creator tests pass.

- [ ] **Step 2: Run full test suite**

Run:

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m pytest -q
```

Expected: all tests pass.

- [ ] **Step 3: Run compile check**

Run:

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m compileall app nodes routers platforms memory scripts llm
```

Expected: exit code `0` with directory listing output and no syntax errors.

- [ ] **Step 4: Inspect git status**

Run:

```powershell
git status --short
git log --oneline -5
```

Expected: no uncommitted M19b files. The latest commits should include the M19b plan, implementation, and docs.

---

## Self-Review

- Spec coverage: the plan covers opt-in API publishing, default local-only approval, image-text-only handling, state/summary fields, operation memory fields, error handling, documentation, and verification.
- Marker scan: no task uses unresolved markers or unspecified implementation steps.
- Type consistency: creator fields use the same names across `state`, `summary`, operation memory, and tests.
- Scope control: frontend controls, video publishing, public publishing, retry queues, and other ecosystem platforms remain out of M19b.
