from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.config import PROJECT_ROOT, load_settings  # noqa: E402


def _resolve(path_value: str | Path) -> Path:
    path = Path(path_value)
    return path if path.is_absolute() else PROJECT_ROOT / path


def _check(level: str, message: str) -> dict[str, str]:
    return {"level": level, "message": message}


def _writable_dir(label: str, path_value: str | Path) -> dict[str, str]:
    path = _resolve(path_value)
    probe_path: Path | None = None
    try:
        path.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path,
            prefix=".deploy_check.",
            delete=False,
        ) as probe:
            probe_path = Path(probe.name)
            probe.write("ok")
        return _check("PASS", f"{label} writable")
    except OSError as exc:
        return _check("FAIL", f"{label} not writable: {exc}")
    finally:
        if probe_path is not None:
            probe_path.unlink(missing_ok=True)


def _backend_check(label: str, actual: str, expected: str = "sqlite") -> dict[str, str]:
    if actual == expected:
        return _check("PASS", f"{label}: {actual}")
    return _check("FAIL", f"{label} must be {expected}, got {actual}")


def check_deployment(backup_dir: str | Path = "data/backups") -> dict[str, Any]:
    settings = load_settings()
    checks = [
        _check("PASS", "core settings loaded"),
        _check("PASS" if settings.api_token else "FAIL", "API token set" if settings.api_token else "API token missing"),
        _backend_check("run store backend", settings.run_store_backend),
        _backend_check("run queue backend", settings.run_queue_backend),
        _backend_check("memory store backend", settings.memory_store_backend),
        _check("PASS" if settings.db_schema == "foundation" else "FAIL", f"db schema: {settings.db_schema}"),
        _check(
            "PASS" if settings.business_tables_enabled else "FAIL",
            "business table writes enabled" if settings.business_tables_enabled else "business table writes disabled",
        ),
        _writable_dir("log_dir", settings.log_dir),
        _writable_dir("run_db_parent", _resolve(settings.run_db_path).parent),
        _writable_dir("backup_dir", backup_dir),
        _check("PASS" if settings.llm_api_key else "WARN", "LLM_API_KEY set" if settings.llm_api_key else "LLM_API_KEY missing"),
        _check(
            "PASS" if os.getenv("XHS_COOKIES_PC") else "WARN",
            "XHS_COOKIES_PC set" if os.getenv("XHS_COOKIES_PC") else "XHS_COOKIES_PC missing",
        ),
    ]
    return {
        "ok": not any(item["level"] == "FAIL" for item in checks),
        "checks": checks,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Check production-lite deploy readiness.")
    parser.add_argument("--backup-dir", default="data/backups")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    result = check_deployment(backup_dir=args.backup_dir)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
