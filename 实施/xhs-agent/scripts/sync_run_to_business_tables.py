"""Sync existing run records into foundation business tables."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.business_store import sync_run_business_tables  # noqa: E402
from app.config import PROJECT_ROOT, load_settings  # noqa: E402
from app.run_store import LocalRunStore, SQLiteRunStore  # noqa: E402


def _resolve_project_path(path_value: str | Path) -> Path:
    path = Path(path_value)
    return path if path.is_absolute() else PROJECT_ROOT / path


def _json_default(value: Any) -> str:
    if isinstance(value, Path):
        return str(value)
    return str(value)


def _load_run_store() -> LocalRunStore | SQLiteRunStore:
    settings = load_settings()
    if settings.run_store_backend == "sqlite":
        return SQLiteRunStore(
            _resolve_project_path(settings.run_db_path),
            runs_dir=PROJECT_ROOT / "data" / "api_runs",
            json_default=_json_default,
        )
    return LocalRunStore(PROJECT_ROOT / "data" / "api_runs", json_default=_json_default)


def _load_records(store: LocalRunStore | SQLiteRunStore, *, run_id: str | None, limit: int) -> list[dict[str, Any]]:
    if run_id:
        record = store.load(run_id)
        return [record] if isinstance(record, dict) else []
    return store.list(limit=max(1, int(limit or 20)))


def _should_sync(record: dict[str, Any]) -> str | None:
    status = str(record.get("status") or "")
    if status != "success":
        return f"status is {status or 'empty'}"
    if not isinstance(record.get("state"), dict) or not record.get("state"):
        return "state is empty"
    return None


def sync_runs(
    db_path: str | Path,
    runs: list[dict[str, Any]],
    *,
    dry_run: bool = False,
) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "dry_run": dry_run,
        "synced": [],
        "skipped": [],
        "errors": [],
    }
    for record in runs:
        run_id = str(record.get("run_id") or "").strip()
        reason = _should_sync(record)
        if reason:
            summary["skipped"].append({"run_id": run_id, "reason": reason})
            continue
        if dry_run:
            summary["synced"].append({"run_id": run_id, "counts": {}})
            continue
        try:
            counts = sync_run_business_tables(db_path, record)
        except Exception as exc:
            summary["errors"].append({"run_id": run_id, "error": str(exc)})
            continue
        summary["synced"].append({"run_id": run_id, "counts": counts})
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Sync run records into foundation business tables.")
    parser.add_argument("--run-id", default=None, help="Sync one run by run_id.")
    parser.add_argument("--limit", type=int, default=20, help="Recent run count when --run-id is omitted.")
    parser.add_argument("--dry-run", action="store_true", help="Print what would sync without writing tables.")
    parser.add_argument(
        "--db-path",
        default=None,
        help="Target SQLite DB path. Defaults to XHS_AGENT_RUN_DB_PATH.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    settings = load_settings()
    store = _load_run_store()
    db_path = _resolve_project_path(args.db_path or settings.run_db_path)
    records = _load_records(store, run_id=args.run_id, limit=args.limit)
    summary = sync_runs(db_path, records, dry_run=args.dry_run)
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=_json_default))
    return 1 if summary["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
