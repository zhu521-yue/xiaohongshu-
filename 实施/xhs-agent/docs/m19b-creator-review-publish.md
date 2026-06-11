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
- Real mode validates image bytes before calling the creator adapter and rejects fake placeholder bytes.
- Creator publish errors are redacted before being stored in run summary, state, or operation memory.
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
