"""Submit an API run and poll until it finishes."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

import requests


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


MEMORY_CONTEXT_COUNT_KEYS = (
    "graph_record_count",
    "recommended_content_type_count",
    "recall_evidence_count",
    "similar_experience_count",
    "historical_compliance_risk_count",
    "recall_explanation_count",
)


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
    parser.add_argument(
        "--require-memory-context",
        action="store_true",
        help="Fail LangGraph smoke unless memory_context_summary.enabled is true.",
    )
    parser.add_argument(
        "--min-recall-explanations",
        type=int,
        default=0,
        help="Fail LangGraph smoke unless recall_explanation_count is at least this value.",
    )
    parser.add_argument(
        "--require-recall-explanation-type",
        action="append",
        default=[],
        dest="required_recall_explanation_types",
        choices=("similar_experience", "historical_compliance_risk"),
        help="Fail LangGraph smoke unless sampled recall_explanations include this type. Can be repeated.",
    )
    parser.add_argument(
        "--seed-recall-memory",
        action="store_true",
        help="Seed local SQLite operation memory with a deterministic record for recall explanation smoke.",
    )
    return parser


def _seed_recall_pain(topic: str) -> str:
    return f"不知道「{topic}」从哪里开始，需要清晰的入门步骤"


def _seed_recall_state(topic: str, target_user: str, content_format: str) -> dict[str, Any]:
    pain = _seed_recall_pain(topic)
    return {
        "post_id": f"seed://m5-recall/{topic}/{content_format}",
        "user_topic": topic,
        "target_user": target_user,
        "account_stage": "cold_start",
        "content_type": "step_tutorial",
        "content_format": content_format,
        "titles": [f"{topic}历史召回种子"],
        "publish_status": "success",
        "publish_time": "2026-06-14T00:00:00",
        "pain_points": [
            {
                "pain": pain,
                "evidence": f"历史记录用于验证 {topic} 的召回解释链路。",
                "priority": 1,
            }
        ],
        "comment_insights": [
            {
                "pain": pain,
                "evidence_comments": [f"我最困惑的是{topic}到底该从哪一步开始"],
                "evidence_count": 1,
                "priority": 1,
            }
        ],
        "rag_eligibility": {
            "eligible": True,
            "level": "eligible",
            "score": 90,
            "reasons": ["可控 smoke 种子"],
            "blocking_reasons": [],
            "recommended_action": "用于验证 LangGraph M5 召回解释链路。",
        },
        "compliance_risk_level": "medium",
        "compliance_issues": ["内容中包含绝对词：一定"],
        "revised_content": "发布前提醒：避免绝对化承诺，只保留经验分享和过程说明。",
        "performance_data": {"views": 500, "likes": 40, "collects": 30, "comments": 8, "follows": 2},
        "review_summary": f"可控历史种子命中痛点：{pain}",
        "next_action": "后续同类主题继续复用该痛点切入，并观察召回解释是否进入生成上下文。",
    }


def _require_sqlite_memory_backend_for_seed() -> None:
    memory_store = os.getenv("XHS_AGENT_MEMORY_STORE", "").strip().lower()
    memory_db_path = os.getenv("XHS_AGENT_MEMORY_DB_PATH", "").strip()
    if memory_store != "sqlite" or not memory_db_path:
        raise RuntimeError(
            "--seed-recall-memory requires XHS_AGENT_MEMORY_STORE=sqlite "
            "and XHS_AGENT_MEMORY_DB_PATH to avoid modifying default JSON operation memory"
        )


def seed_recall_memory(topic: str, target_user: str, content_format: str) -> dict[str, Any]:
    _require_sqlite_memory_backend_for_seed()
    from memory import operation_store

    operation_store.MEMORY_BACKEND = None
    return operation_store.upsert_record_from_state(
        _seed_recall_state(topic, target_user, content_format)
    )


def build_seed_recall_probe_graph(
    topic: str,
    records: list[dict[str, Any]],
    *,
    compliance_risk_level: str = "",
    compliance_issues: list[str] | None = None,
) -> dict[str, Any]:
    from app.memory_graph import query_memory_graph

    pain = _seed_recall_pain(topic)
    return query_memory_graph(
        records,
        topic=topic,
        limit=5,
        pain_points=[{"pain": pain, "evidence": "seed probe"}],
        comment_insights=[
            {
                "pain": pain,
                "evidence_comments": ["seed probe"],
                "evidence_count": 1,
                "priority": 1,
            }
        ],
        compliance_risk_level=compliance_risk_level,
        compliance_issues=compliance_issues or [],
    )


def _is_non_negative_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _validate_memory_context_summary(value: Any) -> list[str]:
    issues: list[str] = []
    if not isinstance(value, dict):
        return ["memory_context_summary must be an object"]

    if not isinstance(value.get("enabled"), bool):
        issues.append("memory_context_summary.enabled must be boolean")
    if not isinstance(value.get("query"), str):
        issues.append("memory_context_summary.query must be a string")

    for key in MEMORY_CONTEXT_COUNT_KEYS:
        if not _is_non_negative_int(value.get(key)):
            issues.append(f"memory_context_summary.{key} must be a non-negative integer")

    explanations = value.get("recall_explanations")
    if not isinstance(explanations, list):
        issues.append("memory_context_summary.recall_explanations must be a list")
    elif _is_non_negative_int(value.get("recall_explanation_count")):
        if len(explanations) > value["recall_explanation_count"]:
            issues.append("memory_context_summary.recall_explanations has more samples than recall_explanation_count")

    return issues


def validate_final_run(
    final: dict[str, Any],
    *,
    engine: str,
    require_memory_context: bool = False,
    min_recall_explanations: int = 0,
    required_recall_explanation_types: list[str] | None = None,
) -> list[str]:
    issues: list[str] = []
    summary = final.get("summary") if isinstance(final.get("summary"), dict) else {}
    if engine == "langgraph":
        if "memory_context_summary" not in summary:
            issues.append("missing memory_context_summary in LangGraph run summary")
        else:
            memory_summary = summary.get("memory_context_summary")
            issues.extend(_validate_memory_context_summary(memory_summary))
            if isinstance(memory_summary, dict):
                if require_memory_context and memory_summary.get("enabled") is not True:
                    issues.append("memory_context_summary.enabled is false; expected recalled memory context")
                min_explanations = max(0, int(min_recall_explanations or 0))
                explanation_count = memory_summary.get("recall_explanation_count")
                if (
                    min_explanations
                    and _is_non_negative_int(explanation_count)
                    and explanation_count < min_explanations
                ):
                    issues.append(
                        "memory_context_summary.recall_explanation_count "
                        f"is {explanation_count}, below required minimum {min_explanations}"
                    )
                required_types = [
                    str(item).strip()
                    for item in (required_recall_explanation_types or [])
                    if str(item).strip()
                ]
                explanations = memory_summary.get("recall_explanations")
                if required_types and isinstance(explanations, list):
                    seen_types = {
                        str(item.get("type") or "").strip()
                        for item in explanations
                        if isinstance(item, dict)
                    }
                    for required_type in required_types:
                        if required_type not in seen_types:
                            issues.append(
                                "memory_context_summary.recall_explanations "
                                f"missing required type: {required_type}"
                            )
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

    if args.seed_recall_memory:
        try:
            seed_record = seed_recall_memory(
                topic=args.topic,
                target_user=args.target_user,
                content_format=args.content_format,
            )
        except Exception as exc:
            _print_line(f"seed recall memory failed: {exc}")
            return 2
        _print_line("seed_recall_record_id:", seed_record.get("record_id"))

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
    validation_issues = validate_final_run(
        final,
        engine=args.engine,
        require_memory_context=args.require_memory_context,
        min_recall_explanations=args.min_recall_explanations,
        required_recall_explanation_types=args.required_recall_explanation_types,
    )
    if validation_issues:
        _print_json({"validation_issues": validation_issues})
        return 1
    return 0 if final.get("status") == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
