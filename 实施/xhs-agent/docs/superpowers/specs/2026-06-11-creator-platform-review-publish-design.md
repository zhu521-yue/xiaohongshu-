# M19b Creator Platform Review Publish Design

## Goal

M19b connects the M19a creator-platform adapter to the existing review workflow without changing the default behavior of the workbench.

The system should still save a local Markdown draft and write operation memory when a run is approved. It should only call the creator platform when the approval request explicitly asks for private creator publishing and includes a human confirmation flag.

## Current Context

The current review workflow is implemented in `app/api.py`:

- `approve_run(run_id, payload)` restores a successful generated run.
- It rejects high-risk compliance results.
- It sets `human_approved=True`.
- It calls `publish_or_schedule(state)` to save a local Markdown draft.
- It calls `review_performance(state)`.
- It calls `write_operation_memory(state)`.
- It saves the reviewed run back through the run store.

M19a added `platforms/creator.py`:

- `publish_private_image_text(draft, human_confirmed=True)` supports mock and `spider_xhs` modes.
- `list_published_notes(limit)` reads published-note lists.
- `check_creator_runtime()` checks creator runtime requirements.
- Real mode requires `XHS_CREATOR_COOKIES`.

The current frontend approval button only sends `feedback`, so default UI behavior must remain local-only for M19b.

## User-Facing Behavior

Default approval stays unchanged:

```json
{
  "feedback": "人工审核通过。"
}
```

This only saves the local Markdown draft and writes operation memory.

Private creator publishing is opt-in through the approval API:

```json
{
  "feedback": "人工审核通过。",
  "creator_publish": true,
  "creator_publish_private": true,
  "creator_human_confirmed": true
}
```

This saves the local Markdown draft first, then calls the creator-platform adapter for private image-text publishing.

## Scope

M19b includes:

- API-level opt-in creator publishing from `approve_run()`.
- Image-text only creator draft conversion.
- Mock-mode self-test coverage.
- Run summary/state fields for creator publish status.
- Operation memory fields that preserve creator publish result.
- Clear failure behavior when creator publishing fails.

M19b excludes:

- Automatic publishing from the frontend button.
- Public publishing.
- Video publishing.
- Image generation or image rendering.
- Retry queue for failed creator publishing.
- Pugongying or Qianfan integration.
- Creator login automation.

## Approval Payload Contract

`approve_run(run_id, payload)` will inspect these optional fields:

- `creator_publish`: boolean. Default `False`.
- `creator_publish_private`: boolean. Must be `True` when `creator_publish=True`.
- `creator_human_confirmed`: boolean. Must be `True` when `creator_publish=True`.

If `creator_publish` is false or missing, no creator-platform call happens.

If `creator_publish=True` but either `creator_publish_private` or `creator_human_confirmed` is not true, approval should return a `ValueError` before calling the creator adapter.

## Creator Draft Mapping

M19b only supports `content_format == "image_text"`.

The creator draft will be built from the approved run state:

- `title`: first item from `titles`, falling back to `user_topic`.
- `desc`: `body` plus tags and comment call when present.
- `images`: mock-only sample image bytes are acceptable for API self-tests; real mode requires explicit image bytes and therefore remains blocked until the workflow has generated or supplied image bytes.
- `topics`: `tags`.

For real `spider_xhs` mode, M19b must not pretend image bytes exist. If no image byte payload is available, it should return a clear failure result instead of calling the real creator API.

## State And Run Fields

The run `state` should receive:

- `creator_publish_requested`: boolean.
- `creator_publish_status`: one of `not_requested`, `success`, `failed`.
- `creator_publish_mode`: current creator mode.
- `creator_note_id`: note ID returned by the adapter when successful.
- `creator_publish_error`: error message when failed.
- `creator_publish_result`: compact adapter result with raw values excluded or minimized.

The run `summary` should expose the same high-value fields:

- `creator_publish_requested`
- `creator_publish_status`
- `creator_publish_mode`
- `creator_note_id`
- `creator_publish_error`

The existing `publish_status` continues to mean local draft save status. It should remain `success` if the local Markdown draft was saved even if creator publishing fails.

## Operation Memory

`memory/operation_store.py` should preserve creator publishing fields when writing operation records:

- `creator_publish_requested`
- `creator_publish_status`
- `creator_publish_mode`
- `creator_note_id`
- `creator_publish_error`

The `post_id` remains the local Markdown path for now. The creator note ID is additional platform metadata, not a replacement for the local draft path.

## Error Handling

Local draft save is the first durable action.

If local draft save fails, approval fails as it does today.

If creator publishing fails after local draft save:

- The API approval should still complete.
- The run should show `publish_status="success"` for the local draft.
- The run should show `creator_publish_status="failed"`.
- `creator_publish_error` should contain the concise error.
- Operation memory should still be written, including the creator failure fields.

If the approval payload requests creator publishing for video content:

- Approval should save the local video Markdown as today.
- Creator publishing should be marked failed with a clear image-text-only message.

## Testing Strategy

Add tests before implementation:

- Approving without creator fields does not call the creator adapter.
- Approving with creator fields in mock mode stores `creator_note_id` and `creator_publish_status="success"`.
- Missing `creator_human_confirmed` blocks creator publishing before adapter call.
- Video creator publishing request is recorded as failed without calling the adapter.
- Creator adapter exception records `creator_publish_status="failed"` while preserving local `publish_status="success"` and operation memory write.

Keep full verification:

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m pytest -q
D:\Anaconda\envs\ContentShare\python.exe -m compileall app nodes routers platforms memory scripts llm
```

## Implementation Notes

Add a small helper in `app/api.py` or a focused new module if the code grows too large. The helper should build the creator draft and call `platforms.creator.publish_private_image_text()` only when explicitly requested.

The initial implementation should stay API-driven. Frontend controls can be added later after the backend behavior is stable.
