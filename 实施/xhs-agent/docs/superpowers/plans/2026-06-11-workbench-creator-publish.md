# Workbench Creator Publish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a workbench review checkbox that sends the existing creator private-publish approval flags only when the user opts in.

**Architecture:** Keep the feature in the existing static workbench. `index.html` owns the checkbox, `app.js` owns payload wiring and status rendering, and a focused pytest file checks the static contract without adding a browser test dependency.

**Tech Stack:** FastAPI static assets, browser JavaScript, pytest, Python standard library.

---

## File Structure

- Create: `tests/test_workbench_creator_publish_static.py`
  - Verifies the review checkbox exists.
  - Verifies approve payload wiring sends creator flags only behind the checked checkbox condition.
  - Verifies summary and review notice rendering includes creator publish fields.
- Modify: `app/static/index.html`
  - Adds one checkbox inside `#reviewActions`.
- Modify: `app/static/app.js`
  - Adds `creatorPublishCheckbox` to `elements`.
  - Adds helper functions for creator status labels and creator error lookup.
  - Adds creator publish status and note id metrics in `renderSummary()`.
  - Disables/resets the checkbox in review flows.
  - Adds creator flags to approve payload only when checked.
- Modify: `app/static/styles.css`
  - Adds small responsive styling for the checkbox row if needed.
- Modify: `memory/current_progress.md`
  - Records M19c completion.
- Modify: `../../AGENTS.md`
  - Updates project memory with M19c status.

---

### Task 1: Static Contract Tests

**Files:**
- Create: `tests/test_workbench_creator_publish_static.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_workbench_creator_publish_static.py`:

```python
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INDEX_HTML = (ROOT / "app" / "static" / "index.html").read_text(encoding="utf-8")
APP_JS = (ROOT / "app" / "static" / "app.js").read_text(encoding="utf-8")


def test_review_area_has_creator_publish_checkbox():
    assert 'id="creatorPublishCheckbox"' in INDEX_HTML
    assert 'name="creator_publish"' in INDEX_HTML
    assert "review-publish-option" in INDEX_HTML
    assert "同时私密发布到创作者平台" in INDEX_HTML


def test_approve_payload_adds_creator_flags_only_when_checked():
    assert "const reviewPayload = {" in APP_JS
    assert "elements.creatorPublishCheckbox.checked" in APP_JS
    assert "reviewPayload.creator_publish = true;" in APP_JS
    assert "reviewPayload.creator_publish_private = true;" in APP_JS
    assert "reviewPayload.creator_human_confirmed = true;" in APP_JS
    assert "isApprove && elements.creatorPublishCheckbox.checked" in APP_JS


def test_summary_and_notice_render_creator_publish_result():
    assert "creatorPublishStatusLabel" in APP_JS
    assert 'metric("创作发布", creatorPublishStatusLabel(summary.creator_publish_status))' in APP_JS
    assert 'metric("平台笔记", summary.creator_note_id)' in APP_JS
    assert "creator_publish_error" in APP_JS
    assert "creatorPublishError(summary)" in APP_JS
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_workbench_creator_publish_static.py -q
```

Expected: `3 failed`, because the checkbox, payload wiring, and summary fields are not implemented yet.

- [ ] **Step 3: Commit is not required yet**

Do not commit failing tests alone unless interrupted.

---

### Task 2: Workbench HTML Checkbox

**Files:**
- Modify: `app/static/index.html`

- [ ] **Step 1: Add the checkbox inside `#reviewActions`**

Change the review actions block to include this label before `#reviewNotice`:

```html
<label class="check-row review-publish-option">
  <input name="creator_publish" id="creatorPublishCheckbox" type="checkbox" />
  <span>同时私密发布到创作者平台</span>
</label>
```

- [ ] **Step 2: Run the focused tests**

Run:

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_workbench_creator_publish_static.py -q
```

Expected: the checkbox test passes; the JS tests still fail.

---

### Task 3: Workbench JavaScript Behavior

**Files:**
- Modify: `app/static/app.js`

- [ ] **Step 1: Register the checkbox element**

Add this entry near the other review elements:

```javascript
creatorPublishCheckbox: $("#creatorPublishCheckbox"),
```

- [ ] **Step 2: Add creator status helpers**

Add these helpers near `metric()`:

```javascript
function creatorPublishStatusLabel(status) {
  if (status === "success") return "成功";
  if (status === "failed") return "失败";
  return "未请求";
}

function creatorPublishError(summary) {
  return summary.creator_publish_error || "";
}
```

- [ ] **Step 3: Add summary metrics**

In `renderSummary(run)`, add these metrics after the existing local publish metric:

```javascript
metric("创作发布", creatorPublishStatusLabel(summary.creator_publish_status)),
metric("平台笔记", summary.creator_note_id),
```

- [ ] **Step 4: Wire checkbox state and creator error notice**

In `renderReviewActions(run)`, after button disabled state is set, add:

```javascript
elements.creatorPublishCheckbox.disabled = !canReview;
if (!canReview) {
  elements.creatorPublishCheckbox.checked = false;
}
```

Then make creator publish errors the first notice branch:

```javascript
const creatorError = creatorPublishError(summary);
if (creatorError) {
  setNotice(elements.reviewNotice, creatorError, true);
} else if (summary.publish_status === "success") {
  ...
}
```

- [ ] **Step 5: Build approve payload conditionally**

In `submitReviewAction(action)`, replace the inline payload object with:

```javascript
const reviewPayload = {
  feedback: isApprove ? "前端人工审核通过。" : "前端人工审核不通过。",
};
if (isApprove && elements.creatorPublishCheckbox.checked) {
  reviewPayload.creator_publish = true;
  reviewPayload.creator_publish_private = true;
  reviewPayload.creator_human_confirmed = true;
}
const data = await apiPost(`/runs/${encodeURIComponent(state.currentRunId)}/${action}`, reviewPayload);
```

- [ ] **Step 6: Reset checkbox after successful approve or reject**

After `renderRun(data.run);`, add:

```javascript
elements.creatorPublishCheckbox.checked = false;
```

- [ ] **Step 7: Run focused tests**

Run:

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_workbench_creator_publish_static.py -q
```

Expected: `3 passed`.

---

### Task 4: Review Area Styling

**Files:**
- Modify: `app/static/styles.css`

- [ ] **Step 1: Add compact checkbox styling**

Add this block after `.review-actions[hidden]`:

```css
.review-publish-option {
  min-height: 38px;
  white-space: nowrap;
}
```

Add this block inside the `@media (max-width: 760px)` section:

```css
  .review-actions {
    align-items: flex-start;
    flex-wrap: wrap;
  }

  .review-publish-option {
    white-space: normal;
  }
```

- [ ] **Step 2: Run focused tests**

Run:

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_workbench_creator_publish_static.py -q
```

Expected: `3 passed`.

---

### Task 5: Documentation And Progress

**Files:**
- Modify: `memory/current_progress.md`
- Modify: `../../AGENTS.md`

- [ ] **Step 1: Update progress memory**

Append a concise M19c entry to `memory/current_progress.md`:

```markdown
## 2026-06-11 M19c 工作台创作者平台发布入口

- 已在工作台审核区增加“同时私密发布到创作者平台”勾选项，默认不勾选，不改变原有本地保存行为。
- 勾选后审核通过会向 M19b 后端发送 `creator_publish`、`creator_publish_private`、`creator_human_confirmed` 三个确认字段。
- 摘要区展示创作发布状态和平台笔记 ID，审核提示区展示后端已脱敏的创作发布错误。
- 已补充静态行为测试覆盖前端入口、payload 条件和状态展示契约。
```

- [ ] **Step 2: Update root project memory**

In `../../AGENTS.md`, update the current stage bullet list to include:

```markdown
- M19c 已完成工作台创作者平台发布入口：审核区可勾选私密发布，前端按需发送 M19b 发布确认字段，并展示发布状态、平台笔记 ID 与脱敏错误。
```

---

### Task 6: Verification And Commit

**Files:**
- All changed files from previous tasks.

- [ ] **Step 1: Run focused frontend contract tests**

Run:

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_workbench_creator_publish_static.py -q
```

Expected: `3 passed`.

- [ ] **Step 2: Run all tests**

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

Expected: no syntax errors.

- [ ] **Step 4: Review git diff**

Run:

```powershell
git -c core.excludesfile= diff -- app/static/index.html app/static/app.js app/static/styles.css tests/test_workbench_creator_publish_static.py memory/current_progress.md ../../AGENTS.md
```

Expected: diff only contains M19c workbench publish changes.

- [ ] **Step 5: Commit implementation**

Run:

```powershell
git add app/static/index.html app/static/app.js app/static/styles.css tests/test_workbench_creator_publish_static.py memory/current_progress.md ../../AGENTS.md docs/superpowers/plans/2026-06-11-workbench-creator-publish.md
git commit -m "feat: add workbench creator publish option"
```

Expected: one implementation commit.
