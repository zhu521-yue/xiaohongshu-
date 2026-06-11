# Creator Image Assets Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let an image-text run bind real local image files before creator-platform private publishing.

**Architecture:** Keep the current standard-library JSON API. The workbench reads selected image files with `FileReader`, sends base64 JSON to a run-level endpoint, the backend validates and stores files under `data/creator_assets/<run_id>/`, and creator publishing reads bytes from those stored files at approval time.

**Tech Stack:** Python standard library HTTP API, existing run store abstraction, browser JavaScript, pytest.

---

## File Structure

- Modify: `app/api.py`
  - Add creator asset storage constants and helpers.
  - Add `attach_creator_assets(run_id, payload)`.
  - Add `POST /runs/{run_id}/creator-assets`.
  - Teach creator publishing to load bytes from stored asset files.
  - Include `creator_images_count` in run summary.
- Modify: `app/static/index.html`
  - Add image file input and bind button near review actions.
- Modify: `app/static/app.js`
  - Add file-to-base64 conversion.
  - Add `/creator-assets` POST wiring.
  - Show bound image count in summary.
  - Disable asset controls when the run cannot be reviewed.
- Modify: `app/static/styles.css`
  - Add compact responsive styling for asset controls.
- Create: `tests/test_creator_asset_binding.py`
  - Backend behavior tests.
- Create: `tests/test_workbench_creator_assets_static.py`
  - Static frontend contract tests.
- Modify: `memory/current_progress.md`
  - Record M20 completion and manual self-test path.
- Modify: `../../AGENTS.md`
  - Update project memory after M20.

## Task 1: Backend Failing Tests

**Files:**
- Create: `tests/test_creator_asset_binding.py`

- [ ] **Step 1: Write failing tests**

Add tests that:

- save a successful image-text run;
- attach one valid PNG through `api.attach_creator_assets()`;
- assert the file is written and summary/state are updated;
- approve with creator publish in `spider_xhs` mode and assert the adapter receives real image bytes;
- reject invalid image payloads before writing assets.

- [ ] **Step 2: Run focused tests**

Run:

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_creator_asset_binding.py -q
```

Expected: fail because `attach_creator_assets()` does not exist yet.

## Task 2: Backend Implementation

**Files:**
- Modify: `app/api.py`

- [ ] **Step 1: Add asset helpers**

Implement helpers for:

- safe filename normalization;
- decoding base64 image payloads;
- validating image magic bytes with existing creator image validation;
- writing image bytes to `data/creator_assets/<run_id>/`;
- reading stored file bytes back during publish.

- [ ] **Step 2: Add run-level attach function**

Implement:

```python
def attach_creator_assets(run_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    ...
```

It should update:

- `state["creator_image_files"]`
- `state["creator_images_count"]`
- `summary["creator_images_count"]`
- `updated_at`

- [ ] **Step 3: Add API route**

Add:

```text
POST /runs/{run_id}/creator-assets
```

This route should call `attach_creator_assets()` and return the updated run.

- [ ] **Step 4: Run focused tests**

Run:

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_creator_asset_binding.py -q
```

Expected: pass.

## Task 3: Frontend Failing Tests

**Files:**
- Create: `tests/test_workbench_creator_assets_static.py`

- [ ] **Step 1: Write static contract tests**

Assert that:

- `index.html` contains a multiple image file input;
- `index.html` contains a bind button;
- `app.js` calls `/creator-assets`;
- `app.js` sends `filename` and `content_base64`;
- `app.js` renders `creator_images_count`.

- [ ] **Step 2: Run static tests**

Run:

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_workbench_creator_assets_static.py -q
```

Expected: fail because frontend controls are not implemented yet.

## Task 4: Frontend Implementation

**Files:**
- Modify: `app/static/index.html`
- Modify: `app/static/app.js`
- Modify: `app/static/styles.css`

- [ ] **Step 1: Add asset controls**

Add controls near review actions:

- file input with `accept="image/*"` and `multiple`;
- bind button.

- [ ] **Step 2: Add JS behavior**

Implement:

- `fileToCreatorAssetPayload(file)`;
- `attachCreatorAssets()`;
- bind button event listener;
- summary metric for bound image count;
- disabled state when the run cannot be reviewed.

- [ ] **Step 3: Add styling**

Add compact layout rules that fit desktop and mobile without changing the current workbench structure.

- [ ] **Step 4: Run static tests**

Run:

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_workbench_creator_assets_static.py -q
```

Expected: pass.

## Task 5: Documentation And Progress

**Files:**
- Modify: `memory/current_progress.md`
- Modify: `../../AGENTS.md`

- [ ] **Step 1: Record M20 progress**

Record what changed, current limits, and exact manual self-test steps.

- [ ] **Step 2: Keep limitations explicit**

Mention that M20 does not add image generation, image layout rendering, public publishing, video publishing, retry, or scheduled publishing.

## Task 6: Verification

- [ ] **Step 1: Run backend focused tests**

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_creator_asset_binding.py -q
```

- [ ] **Step 2: Run frontend static tests**

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_workbench_creator_assets_static.py -q
```

- [ ] **Step 3: Run creator publish regression tests**

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_api_creator_review_publish.py tests/test_workbench_creator_publish_static.py -q
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

1. Start local API with mock LLM and mock collector.
2. Open the workbench.
3. Submit an image-text run.
4. Select one or more local PNG/JPG/WebP images in the review area.
5. Click the bind button and confirm the summary shows the bound image count.
6. Tick `同时私密发布到创作者平台`.
7. Click `审核通过并保存`.
8. In mock creator mode, confirm `创作发布` shows success and `平台笔记` appears.
9. For real `spider_xhs` mode, configure creator cookies first, then repeat with a real image file; the expected failure mode should no longer be `image bytes` missing.
