# M19a Creator Platform Connection

M19a adds a low-risk creator-platform adapter. It does not change the current approval flow: approving a run still saves a local Markdown draft.

## What This Adds

- `platforms/creator.py`: a narrow adapter around creator-platform publishing and published-note list sync.
- `scripts/check_creator_platform.py`: an operator-driven check script.
- Mock private publishing for local verification.
- Mock published-note list sync.
- Real creator-platform preflight checks.

## What This Does Not Add

- No automatic public publishing.
- No automatic publishing after API approval.
- No video upload.
- No image generation or image layout rendering.
- No frontend publishing UI.
- No Pugongying or Qianfan integration.
- No creator login automation.

## Mock Private Publish

Use mock mode first. This does not call Spider_XHS.

```powershell
D:\Anaconda\envs\ContentShare\python.exe .\scripts\check_creator_platform.py --mode mock --publish-private --human-confirmed
```

Expected:

- Exit code `0`.
- JSON output with `ok: true`.
- `visibility` is `private`.
- `note_id` starts with `mock_private_`.

Without `--human-confirmed`, publishing is blocked:

```powershell
D:\Anaconda\envs\ContentShare\python.exe .\scripts\check_creator_platform.py --mode mock --publish-private
```

Expected:

- Exit code `1`.
- JSON output with an error mentioning `human_confirmed`.

## Mock Published List

```powershell
D:\Anaconda\envs\ContentShare\python.exe .\scripts\check_creator_platform.py --mode mock --list --limit 2
```

Expected:

- Exit code `0`.
- JSON output with normalized `notes`.

## Real Creator Preflight

Before any real private publishing, set creator cookies in your local `.env` or terminal:

```powershell
$env:CREATOR_MODE='spider_xhs'
$env:XHS_CREATOR_COOKIES='replace-with-creator-cookie'
D:\Anaconda\envs\ContentShare\python.exe .\scripts\check_creator_platform.py --mode spider_xhs --check-only
```

Expected:

- Exit code `0` only when `XHS_CREATOR_COOKIES` is present, the Spider_XHS vendor directory is available, and the creator API can be imported.
- This command does not publish anything.

If `XHS_CREATOR_COOKIES` is missing, the command exits `1` with a clear preflight error.

## Real Private Publish Boundary

The adapter only exposes private image-text publishing in M19a. It sends `type: 1` to Spider_XHS, which is the private visibility setting in the vendor creator API.

Real publishing must be a deliberate operator action and requires `--human-confirmed`. Public publishing and automatic approval-to-platform publishing are intentionally out of scope for this milestone.

## Developer Verification

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_creator_platform.py -q
D:\Anaconda\envs\ContentShare\python.exe -m pytest -q
D:\Anaconda\envs\ContentShare\python.exe -m compileall app nodes routers platforms memory scripts llm
```
