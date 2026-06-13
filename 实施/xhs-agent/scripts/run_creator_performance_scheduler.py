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
from app import creator_performance_scheduler as scheduler  # noqa: E402


def _print_json(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run scheduled read-only creator note performance sync."
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
    parser.add_argument("--schedule-interval-seconds", type=float, default=1800.0)
    parser.add_argument("--max-rounds", type=int, default=None, help="Maximum rounds before exit. Omit to run until stopped.")
    parser.add_argument("--max-consecutive-failed-rounds", type=int, default=3)
    parser.add_argument("--limit", type=int, default=50, help="Max creator notes to read when matching status.")
    parser.add_argument("--wait", action="store_true", help="Wait for creator note status before syncing.")
    parser.add_argument("--attempts", type=int, default=5, help="Wait attempts when --wait is enabled.")
    parser.add_argument(
        "--status-interval-seconds",
        type=float,
        default=2.0,
        help="Wait interval used inside each creator status read.",
    )
    parser.add_argument("--notes", default=None, help="Operator notes stored with each performance record.")
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


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.mode:
        os.environ["CREATOR_MODE"] = args.mode

    try:
        result = scheduler.run_creator_performance_sync_schedule(
            targets=_targets(args),
            sync_runner=api.sync_creator_note_performance_batch,
            sleep=time.sleep,
            schedule_interval_seconds=args.schedule_interval_seconds,
            max_rounds=args.max_rounds,
            max_consecutive_failed_rounds=args.max_consecutive_failed_rounds,
            limit=args.limit,
            wait=args.wait,
            attempts=args.attempts,
            status_interval_seconds=args.status_interval_seconds,
            notes=args.notes,
        )
    except Exception as exc:
        _print_json({"ok": False, "error": str(exc)})
        return 1

    _print_json(result)
    return 0 if result.get("ok") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
