"""Small helpers for durable local file storage."""

from __future__ import annotations

import copy
import json
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Callable


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S_%f")


def _tmp_path(path: Path) -> Path:
    return path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")


def move_corrupt_file(path: Path, reason: str) -> Path | None:
    """Move a bad JSON file away so future reads can recover cleanly."""

    if not path.exists():
        return None

    backup_dir = path.parent / "corrupt"
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_path = backup_dir / f"{path.name}.{_timestamp()}.{reason}.bak"
    try:
        path.replace(backup_path)
    except OSError:
        return None
    return backup_path


def read_json_file(
    path: str | Path,
    default: Any,
    expected_type: type | tuple[type, ...] | None = None,
) -> Any:
    path = Path(path)
    if not path.exists():
        return copy.deepcopy(default)

    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except OSError:
        return copy.deepcopy(default)
    except json.JSONDecodeError:
        move_corrupt_file(path, "invalid-json")
        return copy.deepcopy(default)

    if expected_type is not None and not isinstance(data, expected_type):
        move_corrupt_file(path, "invalid-root")
        return copy.deepcopy(default)

    return data


def write_text_atomic(path: str | Path, content: str, encoding: str = "utf-8") -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = _tmp_path(path)
    try:
        with tmp.open("w", encoding=encoding, newline="\n") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    except Exception:
        tmp.unlink(missing_ok=True)
        raise
    return path


def write_json_atomic(
    path: str | Path,
    payload: Any,
    default: Callable[[Any], str] | None = None,
) -> Path:
    text = json.dumps(payload, ensure_ascii=False, indent=2, default=default)
    return write_text_atomic(path, f"{text}\n")
