# M19a Creator Platform Connection Design

## Goal

M19a adds a low-risk connection layer for the Xiaohongshu creator platform. The first implementation must support private publishing and published-note list synchronization through a narrow adapter, without changing the existing default flow where approval saves a local Markdown draft.

The goal is to create a safe foundation for later semi-automated publishing and post-publish feedback, not to enable automatic public publishing.

## Current Context

The project already has a stable MVP content pipeline:
- Generate image-text drafts or video scripts.
- Run compliance checks.
- Wait for human approval.
- Save approved drafts as Markdown.
- Write operation memory and performance reviews.

Spider_XHS already includes creator-platform APIs:
- `XHS_Creator_Apis().post_note(noteInfo, cookies_str)`
- `XHS_Creator_Apis().get_all_publish_note_info(cookies_str)`

The technical route analysis says these APIs are high risk and should be wrapped behind `platforms/` so LangGraph nodes never import Spider_XHS directly. Creator-platform writes must keep a human confirmation hard gate. The first publish tests must use `type: 1`, which means private visibility.

## Scope

M19a includes:
- A new `platforms/creator.py` adapter.
- A `CREATOR_MODE=mock|spider_xhs` switch.
- A creator cookie env var: `XHS_CREATOR_COOKIES`.
- Private image-text publish support at the adapter level.
- Published-note list synchronization at the adapter level.
- A script for mock smoke checks and real-environment preflight checks.
- Tests for the adapter boundary and safety gates.
- Documentation for how to run mock checks and what is required before real private publishing.

M19a does not include:
- Automatic public publishing.
- Automatic publishing immediately after API approval.
- Video upload.
- Image generation or image layout rendering.
- Frontend upload UI.
- Pugongying or Qianfan data integration.
- Cookie login automation.

## Adapter Design

Add `platforms/creator.py` with a narrow public API:

```python
def publish_private_image_text(draft: dict, *, human_confirmed: bool) -> dict:
    ...

def list_published_notes(limit: int = 20) -> dict:
    ...

def check_creator_runtime() -> dict:
    ...
```

The adapter returns structured dictionaries instead of exposing Spider_XHS tuple results directly.

`publish_private_image_text()` accepts a normalized draft dictionary:

```python
{
    "title": "title",
    "desc": "body text",
    "images": [b"..."],
    "topics": ["topic"],
}
```

For M19a, the adapter always sends `type: 1` to Spider_XHS for private publishing. A caller cannot request public publishing through this first API.

## Safety Gates

The adapter must reject publishing when:
- `human_confirmed` is not exactly `True`.
- `title` is empty.
- `desc` is empty.
- `images` is empty.
- More than 15 images are provided.
- `CREATOR_MODE=spider_xhs` but `XHS_CREATOR_COOKIES` is missing.

In mock mode, publishing returns a deterministic fake note id and does not call Spider_XHS.

In spider mode, the adapter:
- Imports Spider_XHS only inside the spider call path.
- Temporarily runs from the vendor root, matching the existing collector pattern for ExecJS.
- Converts Spider_XHS `(success, msg, data)` responses into:

```python
{
    "ok": True,
    "mode": "spider_xhs",
    "visibility": "private",
    "platform": "xhs_creator",
    "note_id": "...",
    "raw": {...}
}
```

If the platform response does not contain a stable note id, the adapter still returns the raw response and a stable local generated id so the operation can be logged.

## List Sync

`list_published_notes(limit=20)` returns:

```python
{
    "ok": True,
    "mode": "mock",
    "platform": "xhs_creator",
    "notes": [
        {
            "note_id": "...",
            "title": "...",
            "visibility": "...",
            "raw": {...}
        }
    ]
}
```

In spider mode, it calls `get_all_publish_note_info()` and normalizes the first `limit` notes. It keeps each original item in `raw` for later field mapping improvements.

## Integration Boundary

M19a should not replace `nodes/publish_node.py` behavior. Approval should continue saving Markdown locally.

If we add a command-line script, it should be explicit and operator-driven, for example:

```powershell
D:\Anaconda\envs\ContentShare\python.exe .\scripts\check_creator_platform.py --mode mock --publish-private
D:\Anaconda\envs\ContentShare\python.exe .\scripts\check_creator_platform.py --mode mock --list
D:\Anaconda\envs\ContentShare\python.exe .\scripts\check_creator_platform.py --mode spider_xhs --check-only
```

Real private publishing should require an explicit `--human-confirmed` flag and should not happen in `--check-only`.

## Configuration

Add these env vars to `.env.example`:

```text
CREATOR_MODE=mock
XHS_CREATOR_COOKIES=
```

`CREATOR_MODE=mock` must be the default.

## Testing

Tests should cover:
- Mock private publish succeeds when `human_confirmed=True`.
- Publish rejects when `human_confirmed=False`.
- Publish rejects empty images.
- Publish rejects more than 15 images.
- Spider mode preflight fails when `XHS_CREATOR_COOKIES` is missing.
- Mock list sync returns normalized notes.
- The adapter does not import Spider_XHS in mock mode.

Manual verification uses the `ContentShare` interpreter:

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_creator_platform.py -q
D:\Anaconda\envs\ContentShare\python.exe -m pytest -q
D:\Anaconda\envs\ContentShare\python.exe -m compileall app nodes routers platforms memory scripts llm
```

## Rollout

After M19a is complete, the next safe step is to expose a manual API or UI action that publishes an already-approved local draft privately. That should be a separate milestone because it changes the current approval workflow.
