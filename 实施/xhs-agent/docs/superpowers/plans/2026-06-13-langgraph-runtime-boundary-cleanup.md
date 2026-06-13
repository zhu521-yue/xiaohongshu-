# LangGraph Runtime Boundary Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove LangGraph migration leftovers from `app/api.py` while keeping current LangGraph-first behavior intact.

**Architecture:** `app/api.py` remains the HTTP/run projection boundary. Creator publishing stays in `platforms/creator_publish_flow.py` and `nodes/creator_publish_node.py`. The cleanup removes only legacy direct-publish helpers and unreachable code paths.

**Tech Stack:** Python 3, pytest, existing stdlib HTTP API, LangGraph runtime.

---

## File Structure

- Modify: `tests/test_api_langgraph_resume.py`
  - Add a boundary regression test that fails while legacy direct creator publish helpers still exist in `app.api`.
  - Keep approve/reject resume behavior tests.
- Modify: `app/api.py`
  - Remove unused direct node imports.
  - Remove legacy creator publish helper functions that were only used by unreachable code.
  - Remove unreachable code after `approve_run()` returns from LangGraph resume.
- Optional modify: `memory/current_progress.md`
  - Record this cleanup after implementation if code changes are committed.

## Task 1: Add Boundary Test

**Files:**
- Modify: `tests/test_api_langgraph_resume.py`

- [ ] **Step 1: Write the failing boundary test**

Add this test near the existing approve/reject tests:

```python
def test_api_no_longer_exposes_legacy_direct_creator_publish_helpers() -> None:
    legacy_names = [
        "_publish_creator_private_if_requested",
        "_creator_publish_not_requested",
        "_creator_publish_failed",
        "_creator_publish_success",
        "_build_creator_image_text_draft",
        "_creator_images_from_state",
    ]

    assert [name for name in legacy_names if hasattr(api, name)] == []
```

- [ ] **Step 2: Run the test and verify RED**

Run:

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_api_langgraph_resume.py::test_api_no_longer_exposes_legacy_direct_creator_publish_helpers -q
```

Expected: fail because legacy helper names still exist on `app.api`.

## Task 2: Remove API Dead Code

**Files:**
- Modify: `app/api.py`
- Modify: `tests/test_api_langgraph_resume.py`

- [ ] **Step 1: Update approve resume test setup**

In `tests/test_api_langgraph_resume.py`, remove monkeypatches that target these API-level direct-call symbols:

```python
api.publish_node
api.review_performance
api.write_operation_memory
```

Keep the rest of `test_approve_run_resumes_graph_without_direct_node_calls()` unchanged so it still verifies the final published state.

- [ ] **Step 2: Remove unused imports from API**

In `app/api.py`, remove:

```python
from nodes.memory_node import write_operation_memory
from nodes import publish_node
from nodes.review_node import review_performance
```

- [ ] **Step 3: Remove legacy helper functions**

Delete these function definitions from `app/api.py`:

```python
_creator_publish_not_requested
_creator_publish_failed
_compact_creator_publish_result
_creator_publish_success
_creator_description_from_state
_creator_images_from_state
_build_creator_image_text_draft
_publish_creator_private_if_requested
_creator_image_file_bytes_from_state
_resolve_creator_asset_path
```

Keep these functions because they are still used:

```python
_sanitize_creator_error
_sanitize_business_sync_error
_redacted_creator_error_match
_is_supported_creator_image_bytes
```

- [ ] **Step 4: Remove unreachable approve code**

In `approve_run()`, delete everything after this live return:

```python
    LOGGER.info("run_approved run_id=%s", run_id)
    return reviewed
```

Stop deleting when the next live function definition starts:

```python
def reject_run(...)
```

- [ ] **Step 5: Run boundary and resume tests**

Run:

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_api_langgraph_resume.py -q
```

Expected: all tests in the file pass.

## Task 3: Verify Related Creator/API Coverage

**Files:**
- No code changes expected.

- [ ] **Step 1: Run related tests**

Run:

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_api_creator_review_publish.py tests/test_creator_asset_binding.py tests/test_api_langgraph_resume.py -q
```

Expected: all selected tests pass.

- [ ] **Step 2: Run compile check**

Run:

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m compileall app nodes routers platforms memory scripts llm
```

Expected: exit code 0.

- [ ] **Step 3: Run full tests**

Run:

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m pytest -q
```

Expected: all tests pass.

## Task 4: Record Progress And Commit

**Files:**
- Modify: `memory/current_progress.md`

- [ ] **Step 1: Append progress note**

Append a short section:

```markdown
## 2026-06-13 LangGraph runtime 边界清理

本轮清理 LangGraph-first 迁移后留在 `app/api.py` 的旧直接发布流程：

- 删除 API 层不可达的旧 approve 后续流程。
- 删除只服务旧流程的 creator 发布 helper。
- 保留 LangGraph-first runtime、图内 creator 发布节点和显式 `engine=local` 兼容路径。

验证结果：
- `tests/test_api_langgraph_resume.py` 通过。
- creator/API 相关回归通过。
- `compileall` 通过。
- 全量测试通过。
```

- [ ] **Step 2: Stage and commit**

Run:

```powershell
git add 实施/xhs-agent/app/api.py 实施/xhs-agent/tests/test_api_langgraph_resume.py 实施/xhs-agent/memory/current_progress.md 实施/xhs-agent/docs/superpowers/specs/2026-06-13-langgraph-runtime-boundary-cleanup-design.md 实施/xhs-agent/docs/superpowers/plans/2026-06-13-langgraph-runtime-boundary-cleanup.md
git commit -m "chore: clean up langgraph runtime api boundary"
```

Expected: commit succeeds.
