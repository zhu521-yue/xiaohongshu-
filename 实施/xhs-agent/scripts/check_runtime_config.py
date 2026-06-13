from __future__ import annotations

import argparse
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.config import PROJECT_ROOT, load_settings  # noqa: E402


@dataclass(frozen=True)
class CheckResult:
    level: str
    message: str


def _resolve_project_path(path_value: str) -> Path:
    path = Path(path_value)
    return path if path.is_absolute() else PROJECT_ROOT / path


def _check_writable_dir(label: str, path_value: str) -> CheckResult:
    path = _resolve_project_path(path_value)
    probe_path: Path | None = None
    try:
        path.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path,
            prefix=".write_check.",
            delete=False,
        ) as probe:
            probe_path = Path(probe.name)
            probe.write("ok")
    except OSError as exc:
        return CheckResult("FAIL", f"{label} not writable: {path} ({exc})")
    finally:
        if probe_path is not None:
            probe_path.unlink(missing_ok=True)
    return CheckResult("PASS", f"{label} writable: {path_value}")


def _check_db_parent(label: str, path_value: str) -> CheckResult:
    path = _resolve_project_path(path_value)
    parent = path.parent
    probe_path: Path | None = None
    try:
        parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=parent,
            prefix=".write_check.",
            delete=False,
        ) as probe:
            probe_path = Path(probe.name)
            probe.write("ok")
    except OSError as exc:
        return CheckResult("FAIL", f"{label} parent not writable: {parent} ({exc})")
    finally:
        if probe_path is not None:
            probe_path.unlink(missing_ok=True)
    return CheckResult("PASS", f"{label} parent writable: {path_value}")


def _check_local_profile() -> list[CheckResult]:
    settings = load_settings()
    results = [
        CheckResult("PASS", "core modules importable"),
        _check_writable_dir("log_dir", settings.log_dir),
        CheckResult("PASS", f"run store backend: {settings.run_store_backend}"),
        CheckResult("PASS", f"run queue backend: {settings.run_queue_backend}"),
        _business_table_check(settings),
    ]
    if settings.api_token:
        results.append(CheckResult("PASS", "api token set: auth enabled"))
    else:
        results.append(CheckResult("WARN", "api token empty: auth disabled"))
    return results


def _check_sqlite_worker_profile() -> list[CheckResult]:
    settings = load_settings()
    results = [_check_writable_dir("log_dir", settings.log_dir), _business_table_check(settings)]

    expected = [
        ("run store backend", settings.run_store_backend, "sqlite"),
        ("run queue backend", settings.run_queue_backend, "sqlite"),
        ("memory store backend", settings.memory_store_backend, "sqlite"),
    ]
    for label, actual, expected_value in expected:
        if actual == expected_value:
            results.append(CheckResult("PASS", f"{label}: {actual}"))
        else:
            results.append(CheckResult("FAIL", f"{label} must be {expected_value}, got {actual}"))

    results.extend(_queue_heartbeat_checks(settings))
    results.append(_queue_event_timeline_check(settings))

    results.extend(
        [
            _check_db_parent("run db", settings.run_db_path),
            _check_db_parent("queue db", settings.queue_db_path),
            _check_db_parent("memory db", settings.memory_db_path),
        ]
    )

    run_db_path = _resolve_project_path(settings.run_db_path).resolve()
    queue_db_path = _resolve_project_path(settings.queue_db_path).resolve()
    if run_db_path != queue_db_path:
        results.append(CheckResult("WARN", "run DB path and queue DB path differ; verify both processes use matching env"))
    else:
        results.append(CheckResult("PASS", "run DB path and queue DB path match"))

    return results


def _business_table_check(settings) -> CheckResult:
    if settings.db_schema != "foundation":
        return CheckResult("WARN", f"business table schema is {settings.db_schema}; foundation is expected")
    if not settings.business_tables_enabled:
        return CheckResult("PASS", "business table writes disabled")
    if settings.run_store_backend != "sqlite":
        return CheckResult("WARN", "business table writes require sqlite run store")
    return CheckResult("PASS", "business table writes enabled for sqlite run store")


def _queue_heartbeat_checks(settings) -> list[CheckResult]:
    results: list[CheckResult] = []
    interval = settings.queue_heartbeat_interval_seconds
    timeout = settings.queue_heartbeat_timeout_seconds
    if interval > 0:
        results.append(CheckResult("PASS", f"queue heartbeat interval seconds: {interval:g}"))
    else:
        results.append(CheckResult("FAIL", "queue heartbeat interval seconds must be positive"))

    if timeout > 0:
        results.append(CheckResult("PASS", f"queue heartbeat timeout seconds: {timeout}"))
    else:
        results.append(CheckResult("FAIL", "queue heartbeat timeout seconds must be positive"))

    if interval > 0 and timeout > 0:
        if interval < timeout:
            results.append(CheckResult("PASS", "queue heartbeat interval is lower than timeout"))
        else:
            results.append(CheckResult("FAIL", "queue heartbeat interval must be lower than timeout"))
    return results


def _queue_event_timeline_check(settings) -> CheckResult:
    if (
        settings.run_store_backend == "sqlite"
        and settings.run_queue_backend == "sqlite"
        and settings.db_schema == "foundation"
        and settings.business_tables_enabled
    ):
        return CheckResult("PASS", "queue event timeline enabled")
    return CheckResult(
        "WARN",
        "queue event timeline disabled; watchdog still updates queue state but run_events may be incomplete",
    )


def _check_production_lite_profile() -> list[CheckResult]:
    settings = load_settings()
    results = [_check_writable_dir("log_dir", settings.log_dir)]

    if settings.api_token:
        results.append(CheckResult("PASS", "XHS_AGENT_API_TOKEN set"))
    else:
        results.append(CheckResult("FAIL", "production-lite requires XHS_AGENT_API_TOKEN"))

    if settings.llm_api_key:
        results.append(CheckResult("PASS", "LLM_API_KEY set"))
    else:
        results.append(CheckResult("WARN", "LLM_API_KEY empty: real LLM calls will not work"))

    import os

    if os.getenv("XHS_COOKIES_PC"):
        results.append(CheckResult("PASS", "XHS_COOKIES_PC set"))
    else:
        results.append(CheckResult("WARN", "XHS_COOKIES_PC empty: real Spider_XHS collection will not work"))

    if settings.run_queue_backend == "sqlite":
        results.extend(_check_sqlite_worker_profile())
    else:
        results.append(CheckResult("WARN", f"run queue backend is {settings.run_queue_backend}; API and worker are not split"))

    return results


def check_profile(profile: str) -> list[CheckResult]:
    if profile == "local":
        return _check_local_profile()
    if profile == "sqlite-worker":
        return _check_sqlite_worker_profile()
    if profile == "production-lite":
        return _check_production_lite_profile()
    raise ValueError(f"Unsupported profile: {profile}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Check xhs-agent runtime configuration.")
    parser.add_argument(
        "--profile",
        choices=("local", "sqlite-worker", "production-lite"),
        default="local",
        help="Configuration profile to check.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    results = check_profile(args.profile)
    for result in results:
        print(f"{result.level} {result.message}")
    return 1 if any(result.level == "FAIL" for result in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
