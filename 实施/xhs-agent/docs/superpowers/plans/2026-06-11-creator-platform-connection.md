# M19a Creator Platform Connection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a low-risk creator-platform adapter that supports mock/private image-text publishing, creator published-note list synchronization, and real-mode preflight checks without changing the existing approval-to-Markdown flow.

**Architecture:** Add a narrow `platforms/creator.py` boundary that hides Spider_XHS tuple responses behind structured dictionaries. Keep real Spider_XHS imports inside spider-only code paths; keep mock mode as the default. Add an explicit operator script for smoke checks so publishing cannot happen accidentally through the existing API approval flow.

**Tech Stack:** Python standard library, pytest, existing Spider_XHS vendor dependency, existing `.env` and script patterns.

---

## File Structure

- Create: `platforms/creator.py`
  - Creator-platform adapter with mock and spider modes.
  - Owns validation, safety gates, cookie loading, vendor import setup, response normalization.
- Create: `scripts/check_creator_platform.py`
  - Operator-driven smoke/preflight script for mock publishing, mock list sync, and real-mode check-only validation.
- Create: `tests/test_creator_platform.py`
  - TDD coverage for safety gates, mock behavior, real-mode preflight, and normalized list sync.
- Modify: `.env.example`
  - Adds `CREATOR_MODE=mock` and `XHS_CREATOR_COOKIES=`.
- Create: `docs/m19a-creator-platform-connection.md`
  - User-facing guide for mock checks and real private publish prerequisites.
- Modify: `memory/current_progress.md`
  - Records M19a completion and verification after implementation.

## Task 1: Adapter Tests And Safety Contract

**Files:**
- Create: `tests/test_creator_platform.py`

- [ ] **Step 1: Write failing adapter tests**

```python
import sys

import pytest

from platforms import creator


def sample_draft() -> dict:
    return {
        "title": "私密发布测试标题",
        "desc": "这是一条用于验证创作者平台适配层的私密草稿。",
        "images": [b"fake-image-bytes"],
        "topics": ["小红书运营"],
    }


def test_mock_private_publish_requires_human_confirmation(monkeypatch) -> None:
    monkeypatch.setenv("CREATOR_MODE", "mock")

    with pytest.raises(ValueError, match="human_confirmed"):
        creator.publish_private_image_text(sample_draft(), human_confirmed=False)


def test_mock_private_publish_returns_private_result(monkeypatch) -> None:
    monkeypatch.setenv("CREATOR_MODE", "mock")

    result = creator.publish_private_image_text(sample_draft(), human_confirmed=True)

    assert result["ok"] is True
    assert result["mode"] == "mock"
    assert result["platform"] == "xhs_creator"
    assert result["visibility"] == "private"
    assert result["note_id"].startswith("mock_private_")
    assert result["raw"]["title"] == "私密发布测试标题"


def test_publish_rejects_empty_images(monkeypatch) -> None:
    monkeypatch.setenv("CREATOR_MODE", "mock")
    draft = sample_draft()
    draft["images"] = []

    with pytest.raises(ValueError, match="images"):
        creator.publish_private_image_text(draft, human_confirmed=True)


def test_publish_rejects_more_than_fifteen_images(monkeypatch) -> None:
    monkeypatch.setenv("CREATOR_MODE", "mock")
    draft = sample_draft()
    draft["images"] = [b"x"] * 16

    with pytest.raises(ValueError, match="15"):
        creator.publish_private_image_text(draft, human_confirmed=True)


def test_spider_mode_preflight_requires_creator_cookies(monkeypatch) -> None:
    monkeypatch.setenv("CREATOR_MODE", "spider_xhs")
    monkeypatch.delenv("XHS_CREATOR_COOKIES", raising=False)

    result = creator.check_creator_runtime()

    assert result["ok"] is False
    assert result["mode"] == "spider_xhs"
    assert "XHS_CREATOR_COOKIES" in result["error"]


def test_mock_list_published_notes_is_normalized(monkeypatch) -> None:
    monkeypatch.setenv("CREATOR_MODE", "mock")

    result = creator.list_published_notes(limit=2)

    assert result["ok"] is True
    assert result["mode"] == "mock"
    assert result["platform"] == "xhs_creator"
    assert len(result["notes"]) == 2
    assert set(result["notes"][0]) >= {"note_id", "title", "visibility", "raw"}


def test_mock_mode_does_not_import_spider_modules(monkeypatch) -> None:
    monkeypatch.setenv("CREATOR_MODE", "mock")
    before = set(sys.modules)

    creator.publish_private_image_text(sample_draft(), human_confirmed=True)

    imported = set(sys.modules) - before
    assert not any(name.startswith("apis.xhs_creator_apis") for name in imported)
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_creator_platform.py -q
```

Expected: failures because `platforms.creator` does not exist yet.

## Task 2: Creator Adapter

**Files:**
- Create: `platforms/creator.py`

- [ ] **Step 1: Implement the adapter**

Required public functions:

```python
def publish_private_image_text(draft: dict, *, human_confirmed: bool) -> dict:
    ...


def list_published_notes(limit: int = 20) -> dict:
    ...


def check_creator_runtime() -> dict:
    ...
```

Implementation rules:
- Default mode is `mock`.
- Valid modes are `mock` and `spider_xhs`.
- `publish_private_image_text()` validates human confirmation, title, desc, images, and 15-image limit before mode dispatch.
- Mock publish returns a deterministic `mock_private_<sha1>` id based on title and desc.
- Spider publish builds a Spider_XHS `noteInfo` dict with `type: 1`, `media_type: "image"`, and normalized topics.
- Spider imports are inside a helper that only runs in spider mode.
- Spider calls run inside a vendor working directory context, following `platforms/spider_xhs_collector.py`.
- `check_creator_runtime()` does not publish anything.

- [ ] **Step 2: Run focused tests**

Run:

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_creator_platform.py -q
```

Expected: all creator adapter tests pass.

## Task 3: Operator Script

**Files:**
- Create: `scripts/check_creator_platform.py`
- Test: extend `tests/test_creator_platform.py`

- [ ] **Step 1: Add script tests**

Append these tests:

```python
from scripts import check_creator_platform


def test_check_creator_platform_mock_publish(monkeypatch) -> None:
    monkeypatch.setenv("CREATOR_MODE", "mock")

    exit_code = check_creator_platform.main(["--mode", "mock", "--publish-private", "--human-confirmed"])

    assert exit_code == 0


def test_check_creator_platform_blocks_publish_without_confirmation(monkeypatch) -> None:
    monkeypatch.setenv("CREATOR_MODE", "mock")

    exit_code = check_creator_platform.main(["--mode", "mock", "--publish-private"])

    assert exit_code == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_creator_platform.py -q
```

Expected: failures because `scripts/check_creator_platform.py` does not exist yet.

- [ ] **Step 3: Implement the script**

Script behavior:
- `--mode mock|spider_xhs` sets `CREATOR_MODE`.
- `--check-only` prints `check_creator_runtime()` and exits 0 only if `ok=True`.
- `--publish-private` calls `publish_private_image_text()`.
- Real private publishing requires `--human-confirmed`.
- `--list` calls `list_published_notes()`.
- If no action is selected, run check-only.
- Print JSON with `ensure_ascii=False`.

- [ ] **Step 4: Run focused tests**

Run:

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_creator_platform.py -q
```

Expected: all creator platform tests pass.

## Task 4: Config And Documentation

**Files:**
- Modify: `.env.example`
- Create: `docs/m19a-creator-platform-connection.md`

- [ ] **Step 1: Add `.env.example` entries**

Add:

```text
# Creator platform adapter.
# Keep CREATOR_MODE=mock unless explicitly testing Spider_XHS creator APIs.
CREATOR_MODE=mock
XHS_CREATOR_COOKIES=
```

- [ ] **Step 2: Add user guide**

The guide must include:
- What M19a does and does not do.
- Mock publish command.
- Mock list command.
- Spider preflight command.
- Real private publish prerequisites.
- Reminder that public publish and automatic approval-to-platform publishing are out of scope.

- [ ] **Step 3: Run focused tests**

Run:

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_creator_platform.py -q
```

Expected: all creator platform tests pass.

## Task 5: Verification, Progress, Commit

**Files:**
- Modify: `memory/current_progress.md`

- [ ] **Step 1: Run mock smoke commands**

Run:

```powershell
D:\Anaconda\envs\ContentShare\python.exe .\scripts\check_creator_platform.py --mode mock --publish-private --human-confirmed
D:\Anaconda\envs\ContentShare\python.exe .\scripts\check_creator_platform.py --mode mock --list
D:\Anaconda\envs\ContentShare\python.exe .\scripts\check_creator_platform.py --mode spider_xhs --check-only
```

Expected:
- First two commands exit 0.
- Third command exits 1 when `XHS_CREATOR_COOKIES` is absent and prints a clear preflight error.

- [ ] **Step 2: Run full verification**

Run:

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m pytest -q
D:\Anaconda\envs\ContentShare\python.exe -m compileall app nodes routers platforms memory scripts llm
```

Expected: all tests pass and compileall exits 0.

- [ ] **Step 3: Update progress**

Add a new top section to `memory/current_progress.md` summarizing:
- M19a adapter added.
- Safety gates.
- Mock and preflight commands.
- Remaining limits.

- [ ] **Step 4: Commit**

Run:

```powershell
git add platforms/creator.py scripts/check_creator_platform.py tests/test_creator_platform.py .env.example docs/m19a-creator-platform-connection.md memory/current_progress.md
git commit -m "feat: add creator platform adapter"
```
