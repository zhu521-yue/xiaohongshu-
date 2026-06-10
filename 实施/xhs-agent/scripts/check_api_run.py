"""Submit an API run and poll until it finishes."""

from __future__ import annotations

import argparse
import json
import sys
import time
from typing import Any

import requests


def _print_json(data: Any) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Check async /runs API flow.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8010", help="API base URL.")
    parser.add_argument("--topic", default="小红书新手选题方法", help="Content topic.")
    parser.add_argument("--target-user", default="内容创作新手", help="Target user.")
    parser.add_argument(
        "--format",
        choices=("image_text", "video"),
        default="image_text",
        dest="content_format",
        help="Content format.",
    )
    parser.add_argument(
        "--engine",
        choices=("local", "langgraph"),
        default="langgraph",
        help="Workflow engine.",
    )
    parser.add_argument("--approve", action="store_true", help="Save Markdown and write memory.")
    parser.add_argument("--collect-limit", type=int, default=5, help="Collector note limit.")
    parser.add_argument("--interval", type=float, default=2.0, help="Polling interval seconds.")
    parser.add_argument("--timeout", type=float, default=180.0, help="Max wait seconds.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    base_url = args.base_url.rstrip("/")

    payload = {
        "topic": args.topic,
        "target_user": args.target_user,
        "format": args.content_format,
        "engine": args.engine,
        "approve": args.approve,
        "collect_limit": args.collect_limit,
    }

    try:
        response = requests.post(f"{base_url}/runs", json=payload, timeout=30)
    except requests.RequestException as exc:
        print(f"API request failed: {exc}")
        return 2

    print("submit_status:", response.status_code)
    try:
        data = response.json()
    except ValueError:
        print(response.text)
        return 2

    if not data.get("ok"):
        _print_json(data)
        return 2

    run = data["run"]
    run_id = run["run_id"]
    print("run_id:", run_id)
    print("initial_status:", run.get("status"))

    deadline = time.time() + args.timeout
    final = run
    index = 0
    while time.time() < deadline:
        try:
            poll_response = requests.get(f"{base_url}/runs/{run_id}", timeout=30)
            poll_data = poll_response.json()
        except (requests.RequestException, ValueError) as exc:
            print(f"poll failed: {exc}")
            return 2

        if not poll_data.get("ok"):
            _print_json(poll_data)
            return 2

        final = poll_data["run"]
        status = final.get("status")
        print(f"poll_{index}: {status}")
        if status in {"success", "failed"}:
            break

        index += 1
        time.sleep(args.interval)
    else:
        print(f"timeout waiting for run: {run_id}")
        return 2

    _print_json(final)
    return 0 if final.get("status") == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
