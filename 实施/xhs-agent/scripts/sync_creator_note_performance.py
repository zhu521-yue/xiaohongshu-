from __future__ import annotations

import argparse
import json
import os
import sys
import time
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
    parser.add_argument(
        "--creator-note-id",
        action="append",
        default=[],
        help="Creator platform note id to sync. Can be passed multiple times.",
    )
    parser.add_argument(
        "--run-id",
        action="append",
        default=[],
        help="Run id whose creator_note_id should be synced. Can be passed multiple times.",
    )
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
    parser.add_argument("--repeat-count", type=int, default=1, help="Number of sync rounds to run.")
    parser.add_argument(
        "--repeat-interval-seconds",
        type=float,
        default=60.0,
        help="Seconds to wait between repeated sync rounds.",
    )
    return parser


def _targets(args: argparse.Namespace) -> list[dict[str, str]]:
    targets = [
        {"creator_note_id": str(note_id or "").strip()}
        for note_id in args.creator_note_id
        if str(note_id or "").strip()
    ]
    targets.extend(
        {"run_id": str(run_id or "").strip()}
        for run_id in args.run_id
        if str(run_id or "").strip()
    )
    return targets


def _sync_once(args: argparse.Namespace, targets: list[dict[str, str]]) -> dict[str, Any]:
    if len(targets) == 1 and int(args.repeat_count or 1) == 1:
        target = targets[0]
        return api.sync_creator_note_performance(
            creator_note_id=target.get("creator_note_id", ""),
            run_id=target.get("run_id", ""),
            limit=args.limit,
            wait=args.wait,
            attempts=args.attempts,
            interval_seconds=args.interval_seconds,
            notes=args.notes,
        )
    return api.sync_creator_note_performance_batch(
        targets=targets,
        limit=args.limit,
        wait=args.wait,
        attempts=args.attempts,
        interval_seconds=args.interval_seconds,
        notes=args.notes,
    )


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.mode:
        os.environ["CREATOR_MODE"] = args.mode

    try:
        targets = _targets(args)
        if not targets:
            raise ValueError("Missing required field: creator_note_id or run_id")
        repeat_count = max(1, int(args.repeat_count or 1))
        runs = []
        for index in range(repeat_count):
            runs.append(_sync_once(args, targets))
            if index < repeat_count - 1:
                time.sleep(max(0.0, float(args.repeat_interval_seconds or 0.0)))
    except Exception as exc:
        _print_json({"ok": False, "error": str(exc)})
        return 1

    result = runs[-1]
    if repeat_count > 1:
        _print_json({"ok": True, "runs": runs})
        return 0 if all(item.get("failed", 0) == 0 for item in runs) else 1
    _print_json({"ok": True, **result})
    if result.get("synced") is True:
        return 0
    return 0 if result.get("failed", 0) == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
