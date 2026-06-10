"""Check the local web workbench with Playwright.

Default mode only verifies that the UI loads and can read the API shell data.
Use ``--submit`` when you intentionally want to create a real API run.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Check the XHS Agent workbench UI.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8010", help="Workbench base URL.")
    parser.add_argument("--headed", action="store_true", help="Show the browser window.")
    parser.add_argument("--timeout", type=float, default=15.0, help="UI wait timeout in seconds.")
    parser.add_argument("--viewport", choices=("desktop", "mobile"), default="desktop", help="Viewport profile.")
    parser.add_argument("--screenshot-dir", default="data/ui_checks", help="Screenshot output directory.")
    parser.add_argument("--submit", action="store_true", help="Submit one real API run through the UI.")
    parser.add_argument("--wait-run", action="store_true", help="With --submit, wait for success/failed.")
    parser.add_argument("--wait-run-timeout", type=float, default=180.0, help="Run wait timeout in seconds.")
    parser.add_argument("--topic", default="小红书新手选题方法", help="Topic used by --submit.")
    parser.add_argument("--target-user", default="内容创作新手", help="Target user used by --submit.")
    parser.add_argument("--format", choices=("image_text", "video"), default="image_text", dest="content_format")
    parser.add_argument("--engine", choices=("langgraph", "local"), default="langgraph")
    parser.add_argument("--collect-limit", type=int, default=3)
    parser.add_argument("--approve", action="store_true", help="With --submit, save Markdown and write memory.")
    return parser


def _print_json(data: Any) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2))


def _check_server(base_url: str) -> dict[str, Any]:
    health_url = f"{base_url.rstrip('/')}/health"
    request = urllib.request.Request(health_url, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            body = response.read().decode("utf-8")
    except urllib.error.URLError as exc:
        raise RuntimeError(
            f"API server is not reachable: {health_url}\n"
            "Start it first: python .\\scripts\\run_api.py --host 127.0.0.1 --port 8010"
        ) from exc

    data = json.loads(body)
    if not data.get("ok"):
        raise RuntimeError(f"API health check failed: {data}")
    return data


def _require_text(page: Any, selector: str, expected: str, timeout_ms: float) -> str:
    locator = page.locator(selector)
    locator.wait_for(state="visible", timeout=timeout_ms)
    text = locator.inner_text(timeout=timeout_ms)
    if expected not in text:
        raise AssertionError(f"{selector} expected to contain {expected!r}, got {text!r}")
    return text


def _submit_run(page: Any, args: argparse.Namespace, timeout_ms: float) -> dict[str, Any]:
    page.locator('input[name="topic"]').fill(args.topic)
    page.locator('input[name="target_user"]').fill(args.target_user)
    page.locator('select[name="format"]').select_option(args.content_format)
    page.locator('select[name="engine"]').select_option(args.engine)
    page.locator('input[name="collect_limit"]').fill(str(args.collect_limit))

    approve_box = page.locator('input[name="approve"]')
    if args.approve:
        approve_box.check()
    else:
        approve_box.uncheck()

    page.locator("#submitButton").click()
    page.wait_for_function(
        "() => /run_[a-f0-9]+/.test(document.querySelector('#formNotice')?.textContent || '')",
        timeout=timeout_ms,
    )

    notice = page.locator("#formNotice").inner_text(timeout=timeout_ms)
    status = page.locator("#currentStatus").inner_text(timeout=timeout_ms)
    result: dict[str, Any] = {"notice": notice, "status_after_submit": status}

    if args.wait_run:
        deadline = time.time() + args.wait_run_timeout
        while time.time() < deadline:
            status = page.locator("#currentStatus").inner_text(timeout=timeout_ms)
            if status in {"success", "failed"}:
                result["final_status"] = status
                return result
            page.wait_for_timeout(2000)
        raise TimeoutError(f"Timed out waiting for run to finish; last status={status}")

    return result


def main() -> int:
    args = build_parser().parse_args()
    base_url = args.base_url.rstrip("/")
    timeout_ms = args.timeout * 1000

    try:
        health = _check_server(base_url)
    except Exception as exc:
        print(str(exc))
        return 2

    try:
        from playwright.sync_api import Error as PlaywrightError
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Playwright is not installed. Run: pip install playwright")
        return 2

    screenshot_dir = ROOT / args.screenshot_dir
    screenshot_dir.mkdir(parents=True, exist_ok=True)
    screenshot_path = screenshot_dir / f"workbench_{args.viewport}_{time.strftime('%Y%m%d_%H%M%S')}.png"
    viewport = {"width": 390, "height": 900} if args.viewport == "mobile" else {"width": 1440, "height": 1000}

    console_errors: list[str] = []
    result: dict[str, Any] = {
        "ok": False,
        "base_url": base_url,
        "viewport": args.viewport,
        "health": health,
        "screenshot_path": str(screenshot_path),
        "submitted": False,
    }

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=not args.headed)
            page = browser.new_page(viewport=viewport, is_mobile=args.viewport == "mobile")
            page.on("console", lambda message: console_errors.append(message.text) if message.type == "error" else None)
            page.goto(base_url, wait_until="networkidle", timeout=timeout_ms)

            title = page.title()
            if "XHS Agent 工作台" not in title:
                raise AssertionError(f"Unexpected page title: {title!r}")

            _require_text(page, "h1", "XHS Agent 工作台", timeout_ms)
            page.wait_for_function(
                "() => (document.querySelector('#serviceStatus')?.textContent || '').includes('xhs-agent-api')",
                timeout=timeout_ms,
            )
            _require_text(page, "#queueStrip", "等待", timeout_ms)
            _require_text(page, "#queueStrip", "运行", timeout_ms)
            _require_text(page, ".form-panel h2", "新建任务", timeout_ms)
            _require_text(page, ".result-panel h2", "任务结果", timeout_ms)
            page.get_by_role("heading", name="队列").wait_for(state="visible", timeout=timeout_ms)
            page.get_by_role("heading", name="运行记录").wait_for(state="visible", timeout=timeout_ms)
            _require_text(page, ".performance-panel h2", "表现录入", timeout_ms)
            _require_text(page, ".memory-panel h2", "运营记忆", timeout_ms)

            for selector in [
                'input[name="topic"]',
                'input[name="target_user"]',
                'select[name="format"]',
                'select[name="engine"]',
                'input[name="collect_limit"]',
                "#submitButton",
                "#refreshButton",
            ]:
                page.locator(selector).wait_for(state="visible", timeout=timeout_ms)

            page.locator('button[data-tab="insights"]').click()
            page.locator("#insightsTab.active").wait_for(state="visible", timeout=timeout_ms)
            page.locator('button[data-tab="raw"]').click()
            page.locator("#rawTab.active").wait_for(state="visible", timeout=timeout_ms)
            page.locator('button[data-tab="draft"]').click()
            page.locator("#draftTab.active").wait_for(state="visible", timeout=timeout_ms)

            if args.submit:
                result["submitted"] = True
                result["submit_result"] = _submit_run(page, args, timeout_ms)

            page.screenshot(path=str(screenshot_path), full_page=True)
            browser.close()

        result["ok"] = True
        result["console_errors"] = console_errors
        _print_json(result)
        return 0
    except PlaywrightTimeoutError as exc:
        result["error"] = f"Playwright timeout: {exc}"
    except PlaywrightError as exc:
        result["error"] = (
            f"Playwright error: {exc}\n"
            "If Chromium is missing, run: python -m playwright install chromium"
        )
    except Exception as exc:
        result["error"] = str(exc)

    result["console_errors"] = console_errors
    _print_json(result)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
