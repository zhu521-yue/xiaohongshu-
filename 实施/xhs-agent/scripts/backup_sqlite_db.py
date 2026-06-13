from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.config import PROJECT_ROOT  # noqa: E402


def _resolve(path_value: str | Path) -> Path:
    path = Path(path_value)
    return path if path.is_absolute() else PROJECT_ROOT / path


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def backup_database(
    db_path: str | Path,
    backup_dir: str | Path = "data/backups",
    timestamp: str | None = None,
) -> dict[str, Any]:
    source = _resolve(db_path)
    if not source.exists():
        return {"ok": False, "error": f"database not found: {source}"}
    if not source.is_file():
        return {"ok": False, "error": f"database path is not a file: {source}"}

    stamp = timestamp or _timestamp()
    target_dir = _resolve(backup_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"{source.stem}_{stamp}{source.suffix or '.sqlite3'}"
    if target.exists():
        return {"ok": False, "error": f"backup already exists: {target}"}

    shutil.copy2(source, target)
    return {
        "ok": True,
        "source_path": str(source),
        "backup_path": str(target),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Back up a SQLite database file.")
    parser.add_argument("--db-path", default="data/xhs_agent.sqlite3")
    parser.add_argument("--backup-dir", default="data/backups")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    result = backup_database(db_path=args.db_path, backup_dir=args.backup_dir)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
