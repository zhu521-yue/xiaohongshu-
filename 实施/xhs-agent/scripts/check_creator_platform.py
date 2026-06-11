from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from platforms.creator import (  # noqa: E402
    check_creator_runtime,
    list_published_notes,
    publish_private_image_text,
)


def _sample_draft() -> dict[str, Any]:
    return {
        "title": "M19a 私密发布 mock 草稿",
        "desc": "这是一条用于验证创作者平台适配层的私密发布草稿。",
        "images": [b"mock-image-bytes"],
        "topics": ["小红书运营"],
    }


def _print_json(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Check xhs-agent creator platform adapter.")
    parser.add_argument("--mode", choices=("mock", "spider_xhs"), default=None, help="Override CREATOR_MODE.")
    parser.add_argument("--check-only", action="store_true", help="Only check runtime configuration.")
    parser.add_argument("--publish-private", action="store_true", help="Run a private image-text publish smoke check.")
    parser.add_argument("--human-confirmed", action="store_true", help="Required for private publish smoke checks.")
    parser.add_argument("--list", action="store_true", help="List published creator notes.")
    parser.add_argument("--limit", type=int, default=20, help="Max notes for --list.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.mode:
        os.environ["CREATOR_MODE"] = args.mode

    if args.check_only or not (args.publish_private or args.list):
        result = check_creator_runtime()
        _print_json(result)
        return 0 if result.get("ok") is True else 1

    ok = True
    if args.publish_private:
        try:
            publish_result = publish_private_image_text(_sample_draft(), human_confirmed=args.human_confirmed)
        except Exception as exc:
            publish_result = {"ok": False, "error": str(exc)}
        _print_json({"publish_private": publish_result})
        ok = ok and publish_result.get("ok") is True

    if args.list:
        list_result = list_published_notes(limit=args.limit)
        _print_json({"list_published_notes": list_result})
        ok = ok and list_result.get("ok") is True

    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
