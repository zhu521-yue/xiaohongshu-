"""Collect topic insights and save them as a reusable data artifact."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from platforms.collector import collect_topic_insights  # noqa: E402
from platforms.spider_xhs_collector import save_collection_result  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Collect and save XHS topic insights.")
    parser.add_argument("--topic", required=True, help="Topic to collect.")
    parser.add_argument("--limit", type=int, default=3, help="Maximum notes to collect.")
    parser.add_argument(
        "--output-dir",
        help="Output directory. Defaults to data/collector_runs.",
    )
    return parser


def _print_summary(result: dict, path: Path) -> None:
    summary = {
        "raw_notes_count": len(result.get("raw_notes") or []),
        "raw_comments_count": len(result.get("raw_comments") or []),
        "comment_insights": result.get("comment_insights") or [],
        "pain_points": result.get("pain_points") or [],
        "top_subtopics": result.get("top_subtopics") or [],
        "saved_to": str(path),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def main() -> int:
    args = build_parser().parse_args()
    mode = os.getenv("COLLECTOR_MODE", "mock").strip().lower()

    result = collect_topic_insights(args.topic, limit=args.limit)
    path = save_collection_result(
        args.topic,
        result,
        output_dir=args.output_dir,
        collector_name=mode,
    )
    _print_summary(result, path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
