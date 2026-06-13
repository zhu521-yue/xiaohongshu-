from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app import api  # noqa: E402


def _print_json(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Sync creator note platform metrics into operation performance records."
    )
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--creator-note-id", default="", help="Creator platform note id to sync.")
    target.add_argument("--run-id", default="", help="Run id whose creator_note_id should be synced.")
    parser.add_argument("--mode", choices=("mock", "spider_xhs"), default=None, help="Override CREATOR_MODE.")
    parser.add_argument("--limit", type=int, default=50, help="Max creator notes to read when matching status.")
    parser.add_argument("--wait", action="store_true", help="Wait for creator note status before syncing.")
    parser.add_argument("--attempts", type=int, default=5, help="Wait attempts when --wait is enabled.")
    parser.add_argument(
        "--interval-seconds",
        type=float,
        default=2.0,
        help="Wait interval when --wait is enabled.",
    )
    parser.add_argument("--notes", default=None, help="Operator notes stored with the performance record.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.mode:
        os.environ["CREATOR_MODE"] = args.mode

    try:
        result = api.sync_creator_note_performance(
            creator_note_id=str(args.creator_note_id or "").strip(),
            run_id=str(args.run_id or "").strip(),
            limit=args.limit,
            wait=args.wait,
            attempts=args.attempts,
            interval_seconds=args.interval_seconds,
            notes=args.notes,
        )
    except Exception as exc:
        _print_json({"ok": False, "error": str(exc)})
        return 1

    _print_json({"ok": True, **result})
    return 0 if result.get("synced") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
