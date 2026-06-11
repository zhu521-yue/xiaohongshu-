# Creator Note Performance Sync Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the workbench pull creator-platform notes and record performance by `creator_note_id`.

**Architecture:** Keep the current standard-library JSON API. Add a read-only creator notes endpoint backed by `platforms.creator.list_published_notes()`, extend performance recording to find operation records by either local `post_id` or platform `creator_note_id`, and add a small workbench selector that fills the performance form.

**Tech Stack:** Python standard-library HTTP API, existing operation memory store, existing static workbench JavaScript, pytest.

---

## File Structure

- Modify: `memory/operation_store.py`
  - Allow `update_record_performance()` to locate records by `creator_note_id` when `post_id` is not provided.
- Modify: `app/api.py`
  - Add `list_creator_notes()`.
  - Add `GET /creator/notes?limit=20`.
  - Allow `record_performance()` payloads with `creator_note_id`.
- Modify: `app/static/index.html`
  - Add `creator_note_id` input and a sync button in the performance panel.
  - Add a small creator notes list container.
- Modify: `app/static/app.js`
  - Call `/creator/notes`.
  - Render returned notes.
  - Fill the performance form with selected `creator_note_id`.
  - Submit `creator_note_id` with performance payload.
- Create: `tests/test_creator_note_performance_sync.py`
  - Backend tests for note listing and performance by creator note ID.
- Create: `tests/test_workbench_creator_notes_static.py`
  - Static frontend contract tests.
- Modify: `memory/current_progress.md`
  - Record M21 completion and manual self-test steps.

## Task 1: Backend Failing Tests

**Files:**
- Create: `tests/test_creator_note_performance_sync.py`

- [ ] **Step 1: Write failing tests**

Add tests that:

- patch `api.creator_platform.list_published_notes()` and assert `api.list_creator_notes()` returns normalized notes;
- create an operation memory record with `creator_note_id`;
- call `api.record_performance()` with only `creator_note_id`;
- assert performance data and review status are updated;
- assert missing identifiers are rejected.

- [ ] **Step 2: Run focused tests**

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_creator_note_performance_sync.py -q
```

Expected: fail because `list_creator_notes()` does not exist and `record_performance()` still requires `post_id`.

## Task 2: Backend Implementation

**Files:**
- Modify: `memory/operation_store.py`
- Modify: `app/api.py`

- [ ] **Step 1: Extend operation memory lookup**

Update `update_record_performance()` to accept:

```python
creator_note_id: str | None = None
```

Find the target record by `post_id` first, then by `creator_note_id`.

- [ ] **Step 2: Extend API performance payload**

Allow:

```json
{
  "creator_note_id": "mock_note_001",
  "views": 1000,
  "likes": 50,
  "collects": 20,
  "comments": 8,
  "follows": 3
}
```

- [ ] **Step 3: Add creator notes endpoint**

Add `GET /creator/notes?limit=20`, returning:

```json
{
  "ok": true,
  "creator_notes": {
    "ok": true,
    "mode": "mock",
    "platform": "xhs_creator",
    "notes": []
  }
}
```

- [ ] **Step 4: Run focused backend tests**

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_creator_note_performance_sync.py -q
```

Expected: pass.

## Task 3: Frontend Failing Tests

**Files:**
- Create: `tests/test_workbench_creator_notes_static.py`

- [ ] **Step 1: Write static contract tests**

Assert that:

- the performance form has `creator_note_id`;
- the performance panel has a `syncCreatorNotesButton`;
- app JS calls `/creator/notes`;
- app JS renders notes into `creatorNotesList`;
- performance payload includes `creator_note_id`.

- [ ] **Step 2: Run static tests**

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_workbench_creator_notes_static.py -q
```

Expected: fail because frontend controls are not implemented yet.

## Task 4: Frontend Implementation

**Files:**
- Modify: `app/static/index.html`
- Modify: `app/static/app.js`
- Modify: `app/static/styles.css`

- [ ] **Step 1: Add performance form controls**

Add `creator_note_id` input and a "同步作品列表" button.

- [ ] **Step 2: Add JS note sync**

Implement `syncCreatorNotes()` and `renderCreatorNotes()`.

- [ ] **Step 3: Wire selection to form**

Clicking a note should fill `creator_note_id`, and if the note has a URL-like raw field later it can be extended without changing the API.

- [ ] **Step 4: Run static tests**

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_workbench_creator_notes_static.py -q
```

Expected: pass.

## Task 5: Documentation And Verification

- [ ] **Step 1: Update `memory/current_progress.md`**

Record M21 completion, current limits, and user self-test steps.

- [ ] **Step 2: Run focused tests**

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_creator_note_performance_sync.py tests/test_workbench_creator_notes_static.py -q
```

- [ ] **Step 3: Run regression tests**

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_creator_platform.py tests/test_api_creator_review_publish.py tests/test_creator_asset_binding.py -q
```

- [ ] **Step 4: Run all tests**

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m pytest -q
```

- [ ] **Step 5: Run compile check**

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m compileall app nodes routers platforms memory scripts llm
```

## Manual Self-Test For User

1. Start local API in mock creator mode.
2. Open workbench.
3. Approve a run with creator publishing so an operation memory record has `creator_note_id`.
4. In the performance panel, click `同步作品列表`.
5. Pick a note from the returned list.
6. Confirm `creator_note_id` fills in the performance form.
7. Enter views/likes/collects/comments/follows and submit.
8. Confirm operation memory updates to `performance_recorded`.
