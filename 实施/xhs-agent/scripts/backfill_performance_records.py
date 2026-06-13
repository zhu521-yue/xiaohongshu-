"""Backfill historical operation-memory performance into run business tables."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app import api  # noqa: E402
from memory import operation_store  # noqa: E402


_METRIC_KEYS = ("views", "likes", "collects", "comments", "follows")


def _json_default(value: Any) -> str:
    if isinstance(value, Path):
        return str(value)
    return str(value)


def _int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _matches_filters(
    record: dict[str, Any],
    *,
    record_id: str | None,
    creator_note_id: str | None,
    post_id: str | None,
) -> bool:
    if record_id and record.get("record_id") != record_id:
        return False
    if creator_note_id and record.get("creator_note_id") != creator_note_id:
        return False
    if post_id and record.get("post_id") != post_id:
        return False
    return True


def _eligible_records(
    *,
    record_id: str | None = None,
    creator_note_id: str | None = None,
    post_id: str | None = None,
    limit: int | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if limit is not None and int(limit) <= 0:
        return [], []

    history = operation_store.load_history()
    records = history.get("records") if isinstance(history, dict) else []
    candidates: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for record in records or []:
        if not isinstance(record, dict):
            continue
        if not _matches_filters(
            record,
            record_id=record_id,
            creator_note_id=creator_note_id,
            post_id=post_id,
        ):
            continue
        clean_record_id = str(record.get("record_id") or "").strip()
        if record.get("status") != "performance_recorded":
            skipped.append({"record_id": clean_record_id, "reason": "status is not performance_recorded"})
            continue
        performance_data = record.get("performance_data")
        if not operation_store.has_performance_data(performance_data if isinstance(performance_data, dict) else None):
            skipped.append({"record_id": clean_record_id, "reason": "performance data is empty"})
            continue
        candidates.append(record)
        if limit is not None and len(candidates) >= int(limit):
            break
    return candidates, skipped


def _dry_run_item(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "record_id": record.get("record_id"),
        "post_id": record.get("post_id"),
        "creator_note_id": record.get("creator_note_id"),
        "dry_run": True,
    }


def _payload_from_record(record: dict[str, Any]) -> dict[str, Any]:
    performance_data = record.get("performance_data") if isinstance(record.get("performance_data"), dict) else {}
    payload = {
        "post_id": record.get("post_id") or "",
        "creator_note_id": record.get("creator_note_id") or "",
        "published_url": record.get("published_url") or "",
        "notes": record.get("operator_notes") or "historical performance backfill",
    }
    for key in _METRIC_KEYS:
        payload[key] = _int(performance_data.get(key))
    return payload


def backfill_performance_records(
    *,
    dry_run: bool = True,
    record_id: str | None = None,
    creator_note_id: str | None = None,
    post_id: str | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    candidates, skipped = _eligible_records(
        record_id=record_id,
        creator_note_id=creator_note_id,
        post_id=post_id,
        limit=limit,
    )
    summary: dict[str, Any] = {
        "dry_run": dry_run,
        "processed": [],
        "skipped": skipped,
        "errors": [],
    }
    for record in candidates:
        if dry_run:
            summary["processed"].append(_dry_run_item(record))
            continue
        try:
            result = api.record_performance(_payload_from_record(record))
        except Exception as exc:
            summary["errors"].append({"record_id": record.get("record_id"), "error": str(exc)})
            continue
        business_sync = result.get("business_sync") if isinstance(result, dict) else {}
        if business_sync.get("status") == "success":
            summary["processed"].append(
                {
                    "record_id": record.get("record_id"),
                    "post_id": record.get("post_id"),
                    "creator_note_id": record.get("creator_note_id"),
                    "run_id": business_sync.get("run_id"),
                    "business_sync": business_sync,
                }
            )
            continue
        summary["skipped"].append(
            {
                "record_id": record.get("record_id"),
                "reason": business_sync.get("reason") or business_sync.get("status") or "business sync skipped",
                "business_sync": business_sync,
            }
        )
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Backfill operation-memory performance into business tables.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--apply", action="store_true", help="Write backfill updates.")
    mode.add_argument("--dry-run", action="store_true", help="Preview without writing. This is the default.")
    parser.add_argument("--record-id", default=None)
    parser.add_argument("--creator-note-id", default=None)
    parser.add_argument("--post-id", default=None)
    parser.add_argument("--limit", type=int, default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = backfill_performance_records(
        dry_run=not args.apply,
        record_id=args.record_id,
        creator_note_id=args.creator_note_id,
        post_id=args.post_id,
        limit=args.limit,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, default=_json_default))
    return 1 if result["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
