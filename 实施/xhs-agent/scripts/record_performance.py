"""Record manual performance data for an operation memory record."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from memory.operation_store import (  # noqa: E402
    load_history,
    operation_memory_path,
    update_record_performance,
)


def _print_json(data: dict) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2))


def list_recent_records(limit: int) -> int:
    history = load_history()
    records = [
        record
        for record in history.get("records") or []
        if isinstance(record, dict)
    ]
    records = records[-limit:]

    _print_json(
        {
            "memory_path": str(operation_memory_path()),
            "records": [
                {
                    "record_id": record.get("record_id"),
                    "topic": record.get("topic"),
                    "title": record.get("title"),
                    "post_id": record.get("post_id"),
                    "status": record.get("status"),
                    "performance_score": record.get("performance_score"),
                    "updated_at": record.get("updated_at"),
                }
                for record in records
            ],
        }
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Record manual XHS post performance.")
    parser.add_argument("--post-id", help="The post_id printed by app.main, usually a Markdown path.")
    parser.add_argument("--views", type=int, default=0, help="Exposure or views.")
    parser.add_argument("--likes", type=int, default=0, help="Likes.")
    parser.add_argument("--collects", type=int, default=0, help="Collects or favorites.")
    parser.add_argument("--comments", type=int, default=0, help="Comments.")
    parser.add_argument("--follows", type=int, default=0, help="New follows attributed to this post.")
    parser.add_argument("--published-url", default="", help="Optional real XHS note URL.")
    parser.add_argument("--notes", default="", help="Optional operator notes.")
    parser.add_argument("--list", action="store_true", help="List recent operation memory records.")
    parser.add_argument("--limit", type=int, default=10, help="Record count for --list.")
    return parser


def main() -> int:
    args = build_parser().parse_args()

    if args.list:
        return list_recent_records(limit=args.limit)

    if not args.post_id:
        print("Missing --post-id. Use --list to see recent records.")
        return 2

    performance_data = {
        "views": args.views,
        "likes": args.likes,
        "collects": args.collects,
        "comments": args.comments,
        "follows": args.follows,
    }

    try:
        record = update_record_performance(
            post_id=args.post_id,
            performance_data=performance_data,
            published_url=args.published_url or None,
            notes=args.notes or None,
        )
    except ValueError as exc:
        print(str(exc))
        return 2

    _print_json(
        {
            "memory_path": str(operation_memory_path()),
            "updated_record": {
                "record_id": record.get("record_id"),
                "topic": record.get("topic"),
                "title": record.get("title"),
                "post_id": record.get("post_id"),
                "status": record.get("status"),
                "performance_data": record.get("performance_data"),
                "performance_score": record.get("performance_score"),
                "review_summary": record.get("review_summary"),
                "next_action": record.get("next_action"),
                "review_generation": record.get("review_generation"),
            },
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
