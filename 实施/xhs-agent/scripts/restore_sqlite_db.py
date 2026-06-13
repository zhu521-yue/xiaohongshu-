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


def restore_database(
    target_db_path: str | Path,
    backup_path: str | Path,
    pre_restore_dir: str | Path = "data/backups",
    timestamp: str | None = None,
    apply: bool = False,
) -> dict[str, Any]:
    target = _resolve(target_db_path)
    backup = _resolve(backup_path)
    if not backup.exists():
        return {"ok": False, "error": f"backup not found: {backup}"}
    if not backup.is_file():
        return {"ok": False, "error": f"backup path is not a file: {backup}"}

    if not apply:
        return {
            "ok": True,
            "applied": False,
            "target_path": str(target),
            "backup_path": str(backup),
        }

    stamp = timestamp or _timestamp()
    pre_restore_path: Path | None = None
    if target.exists():
        pre_dir = _resolve(pre_restore_dir)
        pre_dir.mkdir(parents=True, exist_ok=True)
        pre_restore_path = pre_dir / f"{target.stem}_pre_restore_{stamp}{target.suffix or '.sqlite3'}"
        if pre_restore_path.exists():
            return {"ok": False, "error": f"pre-restore backup already exists: {pre_restore_path}"}
        shutil.copy2(target, pre_restore_path)

    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(backup, target)
    return {
        "ok": True,
        "applied": True,
        "target_path": str(target),
        "backup_path": str(backup),
        "pre_restore_backup_path": str(pre_restore_path) if pre_restore_path is not None else None,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Restore a SQLite database file from backup.")
    parser.add_argument("--target-db-path", default="data/xhs_agent.sqlite3")
    parser.add_argument("--backup-path", required=True)
    parser.add_argument("--pre-restore-dir", default="data/backups")
    parser.add_argument("--apply", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    result = restore_database(
        target_db_path=args.target_db_path,
        backup_path=args.backup_path,
        pre_restore_dir=args.pre_restore_dir,
        apply=args.apply,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
