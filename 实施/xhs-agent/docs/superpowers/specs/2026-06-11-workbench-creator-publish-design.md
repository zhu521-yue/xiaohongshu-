# M19c Workbench Creator Publish Design

## Goal

M19c connects the existing M19b approve-run creator publish flags to the workbench UI.

The workbench should keep its current default behavior: approving a run saves the local Markdown draft and writes operation memory. It should only request creator-platform private publishing when the user explicitly selects that option in the review area.

## Current Context

The current workbench is implemented in:

- `app/static/index.html`
- `app/static/app.js`
- `app/static/styles.css`

The current review UI has:

- `审核通过并保存`
- `审核不通过`
- `reviewNotice`

The current approval payload only sends:

```json
{
  "feedback": "前端人工审核通过。"
}
```

M19b already supports creator publishing at the API layer. The workbench must send these fields only when the user opts in:

```json
{
  "creator_publish": true,
  "creator_publish_private": true,
  "creator_human_confirmed": true
}
```

M19b also returns creator publish fields in run summary:

- `creator_publish_requested`
- `creator_publish_status`
- `creator_publish_mode`
- `creator_note_id`
- `creator_publish_error`

## User-Facing Behavior

Add one checkbox in the review action area:

```text
同时私密发布到创作者平台
```

Default state:

- Unchecked.
- Existing approval behavior remains unchanged.
- The existing button label can remain `审核通过并保存`.

When checked and the user clicks `审核通过并保存`:

- The frontend sends `creator_publish=true`.
- The frontend sends `creator_publish_private=true`.
- The frontend sends `creator_human_confirmed=true`.
- The backend remains responsible for final safety enforcement.

## Status Display

The summary area should show creator publish status in addition to local publish status:

- `创作发布`: `未请求` when `creator_publish_status` is missing or `not_requested`.
- `创作发布`: `成功` when `creator_publish_status` is `success`.
- `创作发布`: `失败` when `creator_publish_status` is `failed`.

When `creator_note_id` exists, show it as `平台笔记`.

When `creator_publish_error` exists, show the redacted error in `reviewNotice` after rendering the run. The raw JSON tab still shows the full run object, but M19b has already redacted persisted creator errors before they reach the frontend.

## Review Area Rules

The creator publish checkbox should only be interactive when the approval action is interactive:

- Enabled when `canReview` is true.
- Disabled when the run cannot be reviewed.
- Hidden with the review action area when the run has no review actions.
- Reset to unchecked after successful approve or reject action.

The frontend should not duplicate backend safety logic. It may leave the checkbox visible for image-text and video runs; if video creator publish is requested, the backend records `creator_publish_status="failed"` and returns the clear error.

## Scope

M19c includes:

- One review-area checkbox.
- Approval payload wiring for M19b creator flags.
- Creator status and note ID display in the summary grid.
- Review notice display for creator publish failure.
- Lightweight tests or script checks for UI behavior.
- Documentation/progress update after implementation.

M19c excludes:

- New page or modal.
- Real image upload or image-byte selection UI.
- Public publishing.
- Video creator publishing.
- Retry flow for creator publish failures.
- Pugongying or Qianfan UI.

## Testing Strategy

Prefer DOM-level tests if the current project has a lightweight way to test static JS. If not, add a focused Python script check similar to existing workbench UI checks.

Required coverage:

- The review checkbox exists in `index.html`.
- `submitReviewAction("approve")` sends creator flags only when the checkbox is checked.
- `submitReviewAction("approve")` does not send creator flags when unchecked.
- Summary rendering includes creator publish status.
- Creator failure error can be shown in the review notice.

Keep full verification:

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m pytest -q
D:\Anaconda\envs\ContentShare\python.exe -m compileall app nodes routers platforms memory scripts llm
```

If frontend behavior is changed, run the existing workbench UI smoke check against a local API server when feasible.

## Implementation Notes

Use existing frontend patterns:

- Keep controls inside `review-actions`.
- Reuse `check-row` styling for the checkbox.
- Do not add a landing page, wizard, or separate publish panel.
- Keep wording operational and explicit.

Potential DOM additions:

```html
<label class="check-row review-publish-option">
  <input name="creator_publish" id="creatorPublishCheckbox" type="checkbox" />
  <span>同时私密发布到创作者平台</span>
</label>
```

Potential JS additions:

- Add `creatorPublishCheckbox` to `elements`.
- Add creator metrics in `renderSummary()`.
- Disable/reset checkbox in `renderReviewActions()`.
- In `submitReviewAction("approve")`, include creator flags only when checked.
