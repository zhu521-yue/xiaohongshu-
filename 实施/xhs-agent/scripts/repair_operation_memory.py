"""Repair cross-domain pollution in operation memory.

The script is dry-run by default. Use --apply to write the repaired history.
When --apply is used, a timestamped backup is created next to the history file.
"""

from __future__ import annotations

import argparse
import copy
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from memory.operation_store import HISTORY_PATH, load_history, save_history  # noqa: E402


HEALTH_TOPIC_KEYWORDS = (
    "\u5b9d\u5b9d",
    "\u5a74\u513f",
    "\u5b69\u5b50",
    "\u6e7f\u75b9",
    "\u70ed\u75b9",
    "\u76ae\u75b9",
    "\u75b9\u5b50",
    "\u8fc7\u654f",
    "\u53d1\u70e7",
    "\u9ad8\u70e7",
    "\u533b\u751f",
    "\u5c31\u533b",
    "\u7528\u836f",
    "\u64e6\u836f",
    "\u8bca\u65ad",
    "\u6bcd\u4e73",
)


POLLUTION_PATTERNS = (
    "\u5bf9\u62a4\u7406\u65b9\u6cd5\u5b58\u5728\u7591\u95ee",
    "\u62a4\u7406\u65b9\u5411",
    "\u5b9d\u5b9d\u6e7f\u75b9",
    "\u6e7f\u75b9",
    "\u70ed\u75b9",
    "\u76ae\u75b9",
    "\u75b9\u5b50",
    "\u64e6\u836f",
    "\u7528\u836f",
    "\u5c31\u533b",
    "\u8bca\u65ad",
    "\u4e0d\u66ff\u4ee3\u4e13\u4e1a\u8bca\u65ad",
)


GENERIC_PAIN_TEMPLATE = (
    "\u5bf9\u300c{topic}\u300d\u662f\u5426\u771f\u5b9e\u53ef\u884c"
    "\u5b58\u5728\u6000\u7591\uff0c\u9700\u8981\u53ef\u4fe1\u6848\u4f8b"
    "\u548c\u8fb9\u754c\u8bf4\u660e"
)
GENERIC_REVIEW_TEMPLATE = (
    "\u4e3b\u9898\u300c{topic}\u300d\u7684\u5386\u53f2\u8bb0\u5f55"
    "\u5df2\u4fee\u6b63\u8de8\u9886\u57df\u75db\u70b9\u8868\u8fbe\uff0c"
    "\u4e0b\u6b21\u751f\u6210\u65f6\u5e94\u7ee7\u7eed\u7528\u65b0\u8bc4\u8bba"
    "\u9a8c\u8bc1\u7528\u6237\u771f\u5b9e\u9700\u6c42\u3002"
)
GENERIC_NEXT_ACTION = (
    "\u4e0b\u6b21\u540c\u7c7b\u4e3b\u9898\u5148\u590d\u7528\u901a\u7528\u5b9e\u64cd"
    "\u7ed3\u6784\uff0c\u4f46\u4e0d\u590d\u7528\u65e7\u8bb0\u5f55\u4e2d\u7684"
    "\u8de8\u9886\u57df\u75db\u70b9\u8868\u8fbe\u3002"
)


def _now_stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _topic_is_health_related(topic: str) -> bool:
    return any(keyword in str(topic or "") for keyword in HEALTH_TOPIC_KEYWORDS)


def _contains_pollution(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return any(pattern in value for pattern in POLLUTION_PATTERNS)
    if isinstance(value, dict):
        return any(_contains_pollution(child) for child in value.values())
    if isinstance(value, list):
        return any(_contains_pollution(child) for child in value)
    return False


def _repair_pain_points(record: dict[str, Any], field_name: str, topic: str) -> bool:
    items = record.get(field_name)
    if not isinstance(items, list):
        return False

    changed = False
    for item in items:
        if not isinstance(item, dict) or not _contains_pollution(item):
            continue
        item["pain"] = GENERIC_PAIN_TEMPLATE.format(topic=topic)
        changed = True
    return changed


def _repair_titles(record: dict[str, Any], topic: str) -> bool:
    changed = False

    if _contains_pollution(record.get("title")):
        record["title"] = f"{topic}\u5b9e\u64cd\u6b65\u9aa4\uff0c\u4e00\u6b65\u4e00\u6b65\u770b"
        changed = True

    titles = record.get("titles")
    if isinstance(titles, list):
        clean_titles = [str(title) for title in titles if not _contains_pollution(title)]
        if clean_titles != titles:
            changed = True
        if not clean_titles:
            clean_titles = [record.get("title") or f"{topic}\u5b9e\u64cd\u6b65\u9aa4"]
            changed = True
        record["titles"] = clean_titles

    return changed


def repair_record(record: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    topic = str(record.get("topic") or "").strip()
    repaired = copy.deepcopy(record)
    if not topic or _topic_is_health_related(topic):
        return repaired, []

    changes: list[str] = []

    if _repair_pain_points(repaired, "pain_points", topic):
        changes.append("pain_points")
    if _repair_pain_points(repaired, "comment_insights", topic):
        changes.append("comment_insights")
    if _repair_titles(repaired, topic):
        changes.append("titles")

    if _contains_pollution(repaired.get("review_summary")):
        repaired["review_summary"] = GENERIC_REVIEW_TEMPLATE.format(topic=topic)
        changes.append("review_summary")
    if _contains_pollution(repaired.get("next_action")):
        repaired["next_action"] = GENERIC_NEXT_ACTION
        changes.append("next_action")

    if changes:
        repaired["updated_at"] = _now_iso()
        notes = repaired.get("repair_notes")
        if not isinstance(notes, list):
            notes = []
        notes.append(
            {
                "at": _now_iso(),
                "reason": "cross_domain_health_memory_repair",
                "fields": changes,
            }
        )
        repaired["repair_notes"] = notes

    return repaired, changes


def repair_history(history: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    repaired_history = copy.deepcopy(history)
    records = repaired_history.get("records")
    if not isinstance(records, list):
        return repaired_history, []

    report = []
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            continue
        repaired, changes = repair_record(record)
        if changes:
            records[index] = repaired
            report.append(
                {
                    "record_id": repaired.get("record_id"),
                    "topic": repaired.get("topic"),
                    "title": repaired.get("title"),
                    "changed_fields": changes,
                }
            )

    return repaired_history, report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Repair polluted operation memory records.")
    parser.add_argument("--apply", action="store_true", help="Write repaired memory after creating a backup.")
    parser.add_argument("--path", default=str(HISTORY_PATH), help="Operation history JSON path.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    path = Path(args.path)
    history = load_history(path)
    repaired_history, report = repair_history(history)

    result: dict[str, Any] = {
        "memory_path": str(path),
        "mode": "apply" if args.apply else "dry_run",
        "changed_records_count": len(report),
        "changed_records": report,
    }

    if args.apply and report:
        backup_path = path.with_name(f"{path.name}.backup_{_now_stamp()}")
        shutil.copy2(path, backup_path)
        save_history(repaired_history, path)
        result["backup_path"] = str(backup_path)
        result["written"] = True
    else:
        result["written"] = False

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
