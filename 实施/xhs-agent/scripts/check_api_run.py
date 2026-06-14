"""Submit an API run and poll until it finishes."""

from __future__ import annotations

import argparse
import json
import sys
import time
from typing import Any

import requests


def _print_line(*values: Any, sep: str = " ", end: str = "\n") -> None:
    text = sep.join(str(value) for value in values) + end
    try:
        sys.stdout.write(text)
    except UnicodeEncodeError:
        encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
        safe_text = text.encode(encoding, errors="backslashreplace").decode(
            encoding,
            errors="replace",
        )
        sys.stdout.write(safe_text)


def _print_json(data: Any) -> None:
    _print_line(json.dumps(data, ensure_ascii=False, indent=2))


def build_headers(api_token: str | None) -> dict[str, str]:
    token = str(api_token or "").strip()
    if not token:
        return {}
    return {"Authorization": f"Bearer {token}"}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Check async /runs API flow.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8010", help="API base URL.")
    parser.add_argument("--api-token", default=None, help="API token for guarded API mode.")
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


def validate_final_run(final: dict[str, Any], *, engine: str) -> list[str]:
    issues: list[str] = []
    summary = final.get("summary") if isinstance(final.get("summary"), dict) else {}
    if engine == "langgraph" and "memory_context_summary" not in summary:
        issues.append("missing memory_context_summary in LangGraph run summary")
    return issues


def main() -> int:
    args = build_parser().parse_args()
    base_url = args.base_url.rstrip("/")
    headers = build_headers(args.api_token)

    payload = {
        "topic": args.topic,
        "target_user": args.target_user,
        "format": args.content_format,
        "engine": args.engine,
        "approve": args.approve,
        "collect_limit": args.collect_limit,
    }

    try:
        response = requests.post(f"{base_url}/runs", json=payload, headers=headers, timeout=30)
    except requests.RequestException as exc:
        _print_line(f"API request failed: {exc}")
        return 2

    _print_line("submit_status:", response.status_code)
    try:
        data = response.json()
    except ValueError:
        _print_line(response.text)
        return 2

    if not data.get("ok"):
        _print_json(data)
        return 2

    run = data["run"]
    run_id = run["run_id"]
    _print_line("run_id:", run_id)
    _print_line("initial_status:", run.get("status"))

    deadline = time.time() + args.timeout
    final = run
    index = 0
    while time.time() < deadline:
        try:
            poll_response = requests.get(f"{base_url}/runs/{run_id}", headers=headers, timeout=30)
            poll_data = poll_response.json()
        except (requests.RequestException, ValueError) as exc:
            _print_line(f"poll failed: {exc}")
            return 2

        if not poll_data.get("ok"):
            _print_json(poll_data)
            return 2

        final = poll_data["run"]
        status = final.get("status")
        _print_line(f"poll_{index}: {status}")
        if status in {"success", "failed"}:
            break

        index += 1
        time.sleep(args.interval)
    else:
        _print_line(f"timeout waiting for run: {run_id}")
        return 2

    _print_json(final)
    validation_issues = validate_final_run(final, engine=args.engine)
    if validation_issues:
        _print_json({"validation_issues": validation_issues})
        return 1
    return 0 if final.get("status") == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
