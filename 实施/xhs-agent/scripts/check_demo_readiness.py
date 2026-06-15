"""演示前就绪检查。
在面试演示前运行此脚本，快速确认所有关键链路可用。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv
load_dotenv(ROOT / ".env")


def _ok(label: str, detail: str = "") -> str:
    msg = f"[OK] {label}" + (f" — {detail}" if detail else "")
    print(msg)
    return msg


def _warn(label: str, detail: str = "") -> str:
    msg = f"[WARN] {label}" + (f" — {detail}" if detail else "")
    print(msg)
    return msg


def _fail(label: str, detail: str = "") -> str:
    msg = f"[FAIL] {label}" + (f" — {detail}" if detail else "")
    print(msg)
    return msg


def check_python() -> bool:
    version = sys.version_info
    if version.major >= 3 and version.minor >= 10:
        _ok("Python", f"{version.major}.{version.minor}.{version.micro}")
        return True
    _fail("Python", f"需要 3.10+，当前 {version.major}.{version.minor}")
    return False


def check_env_file() -> bool:
    env_path = ROOT / ".env"
    if env_path.exists():
        _ok(".env 文件", str(env_path))
        return True
    _fail(".env 文件", "缺失，从 .env.example 复制并填入配置")
    return False


def check_collector_cookie() -> bool:
    cookie = os.getenv("XHS_COOKIES_PC") or os.getenv("COOKIES_PC") or os.getenv("COOKIES")
    if cookie:
        _ok("采集 Cookie (XHS_COOKIES_PC)", f"长度={len(cookie)}")
        return True
    _warn("采集 Cookie (XHS_COOKIES_PC)", "未配置，采集将使用 mock")
    return False


def check_creator_cookie() -> bool:
    cookie = os.getenv("XHS_CREATOR_COOKIES") or os.getenv("CREATOR_COOKIES")
    if cookie:
        _ok("创作者 Cookie (XHS_CREATOR_COOKIES)", f"长度={len(cookie)}")
        return True
    _warn("创作者 Cookie (XHS_CREATOR_COOKIES)", "未配置，发布将使用 mock")
    return False


def check_llm() -> bool:
    model = os.getenv("LLM_MODEL_NAME", "mock")
    if model == "mock":
        _warn("LLM", "mock 模式，生成将是模板内容")
        return False
    api_key = os.getenv("LLM_API_KEY")
    base_url = os.getenv("LLM_BASE_URL")
    if api_key and base_url:
        _ok("LLM", f"model={model}")
        return True
    _warn("LLM", f"model={model} 但缺少 API_KEY 或 BASE_URL")
    return False


def check_stage() -> str:
    stage = os.getenv("ACCOUNT_STAGE", "cold_start")
    _ok("账号阶段", stage)
    return stage


def check_collector_runtime() -> bool:
    try:
        from platforms.collector import check_collector_runtime
        result = check_collector_runtime()
        if result.get("ok"):
            _ok("采集器运行时", f"mode={result.get('mode')}")
            return True
        _warn("采集器运行时", result.get("error", "未知错误"))
        return False
    except Exception as exc:
        _warn("采集器运行时", str(exc))
        return False


def check_creator_runtime() -> bool:
    try:
        from platforms.creator import check_creator_runtime
        result = check_creator_runtime()
        if result.get("ok"):
            _ok("创作者平台运行时", f"mode={result.get('mode')}")
            return True
        _warn("创作者平台运行时", result.get("error", "未知错误"))
        return False
    except Exception as exc:
        _warn("创作者平台运行时", str(exc))
        return False


def check_guardrails() -> bool:
    try:
        from platforms.platform_guardrails import check_creator_publish_allowed
        result = check_creator_publish_allowed()
        if result.get("allowed"):
            count = result.get("success_count", 0)
            limit = result.get("daily_limit", "?")
            _ok("安全护栏", f"今日发布 {count}/{limit}")
            return True
        _warn("安全护栏", result.get("reason", "未知原因"))
        return False
    except Exception as exc:
        _warn("安全护栏", str(exc))
        return False


def check_tests() -> bool:
    import subprocess
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "tests/", "-q", "--tb=no"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode == 0:
            lines = result.stdout.strip().splitlines()
            last = lines[-1] if lines else ""
            _ok("测试套件", last.strip())
            return True
        _fail("测试套件", f"部分失败\n{result.stdout[-500:]}")
        return False
    except Exception as exc:
        _warn("测试套件", str(exc))
        return False


def main() -> int:
    print("=" * 50)
    print("  小红书两阶段多智能体系统 - 演示前就绪检查")
    print("=" * 50)
    print()

    results = {
        "Python": check_python(),
        ".env": check_env_file(),
        "采集Cookie": check_collector_cookie(),
        "创作者Cookie": check_creator_cookie(),
        "LLM": check_llm(),
    }

    check_stage()

    print()
    print("--- 运行时链路 ---")
    results["采集器"] = check_collector_runtime()
    results["创作者平台"] = check_creator_runtime()
    results["安全护栏"] = check_guardrails()

    print()
    results["测试"] = check_tests()

    print()
    print("=" * 50)

    failures = sum(1 for v in results.values() if v is False)
    warns = sum(1 for k, v in results.items() if v is False and k in ("采集Cookie", "创作者Cookie", "LLM"))

    if failures == 0:
        print("  结论：所有必需检查通过，可以开始演示")
    elif failures <= warns:
        print(f"  结论：{failures} 项提示（Cookie/LLM mock），演示可用")
    else:
        print(f"  结论：{failures} 项未通过，请先修复再演示")

    return 0 if failures <= warns else 1


if __name__ == "__main__":
    raise SystemExit(main())
