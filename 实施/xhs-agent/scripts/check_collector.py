"""Staged checks for the Spider_XHS read-only collector.

Default mode only checks local configuration and imports. Use --search to make
one search request, and --comments to fetch comments for returned notes.
"""

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

from platforms import spider_xhs_collector as collector  # noqa: E402
from platforms.analysis_report import build_analysis_report  # noqa: E402


def _print_step(name: str, status: str, detail: str = "") -> None:
    suffix = f" - {detail}" if detail else ""
    print(f"[{status}] {name}{suffix}")


def _print_json(data) -> None:
    text = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    try:
        sys.stdout.write(text)
    except UnicodeEncodeError:
        encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
        safe_text = text.encode(encoding, errors="backslashreplace").decode(
            encoding,
            errors="replace",
        )
        sys.stdout.write(safe_text)


def _get_cookie() -> str | None:
    return os.getenv("XHS_COOKIES_PC") or os.getenv("COOKIES_PC") or os.getenv("COOKIES")


def check_env() -> str | None:
    env_path = ROOT / ".env"
    if env_path.exists():
        _print_step(".env", "OK", str(env_path))
    else:
        _print_step(".env", "FAIL", "missing; copy .env.example to .env first")

    cookie = _get_cookie()
    if cookie:
        _print_step("cookie", "OK", f"present, length={len(cookie)}")
    else:
        _print_step("cookie", "FAIL", "missing XHS_COOKIES_PC")

    for name in (
        "XHS_NOTE_LIMIT",
        "XHS_COMMENTS_PER_NOTE",
        "XHS_SORT_TYPE",
        "XHS_MIN_NOTE_COMMENTS",
        "XHS_MIN_NOTE_INTERACTION",
        "XHS_MIN_DELAY_SECONDS",
        "XHS_MAX_DELAY_SECONDS",
    ):
        value = os.getenv(name)
        if value is not None:
            _print_step(name, "OK", value)

    return cookie


def check_vendor_import():
    collector._ensure_vendor_importable()
    _print_step("vendor path", "OK", str(collector.VENDOR_ROOT))
    api = collector._load_xhs_api()
    _print_step("XHS_Apis import", "OK", type(api).__name__)
    return api


def run_search(api, cookie: str, topic: str, limit: int, debug_search: bool) -> tuple[list[dict], list[dict]]:
    note_limit = min(limit, collector._env_int("XHS_NOTE_LIMIT", limit))
    candidate_multiplier = max(1, collector._env_int("XHS_CANDIDATE_POOL_MULTIPLIER", 3))
    default_candidate_limit = max(note_limit, min(20, note_limit * candidate_multiplier))
    candidate_pool_limit = max(
        note_limit,
        collector._env_int("XHS_CANDIDATE_POOL_LIMIT", default_candidate_limit),
    )
    search_limit = max(note_limit, min(candidate_pool_limit, note_limit * candidate_multiplier))
    sort_type_choice = collector._env_int("XHS_SORT_TYPE", 2)
    _print_step(
        "search request",
        "RUN",
        f"topic={topic}, selected_limit={note_limit}, search_limit={search_limit}, sort={sort_type_choice}",
    )

    if debug_search:
        with collector._vendor_working_directory():
            success, msg, res_json = api.search_note(
                topic,
                cookie,
                page=1,
                sort_type_choice=sort_type_choice,
                note_type=0,
            )
        if not success:
            raise RuntimeError(f"Spider_XHS search failed: {msg}")
        _print_json(
            {"search_response_debug": collector._search_response_summary(res_json, max_items=search_limit)}
        )
        notes = (res_json.get("data") or {}).get("items") or []
        notes = notes[:search_limit]
    else:
        with collector._vendor_working_directory():
            success, msg, notes = api.search_some_note(
                topic,
                search_limit,
                cookie,
                sort_type_choice=sort_type_choice,
                note_type=0,
            )
        if not success:
            raise RuntimeError(f"Spider_XHS search failed: {msg}")

    raw_notes = [collector._deidentify_note(note) for note in notes]
    collection_candidates = collector.score_collection_candidates(
        topic,
        raw_notes,
        selected_limit=note_limit,
    )
    selected_indices = [
        int(candidate.get("original_index"))
        for candidate in collection_candidates
        if candidate.get("selected") is True
    ]
    notes_for_comments = [raw_notes[index] for index in selected_indices]
    if not notes_for_comments:
        notes_for_comments = raw_notes[:note_limit]

    _print_step(
        "search request",
        "OK",
        f"raw_notes={len(raw_notes)}, selected_notes={len(notes_for_comments)}",
    )
    _print_json(
        {
            "search_filter_summary": {
                "raw_notes_count": len(raw_notes),
                "selected_notes_count": len(notes_for_comments),
                "fallback_to_raw": not selected_indices,
            },
            "candidate_score_summary": [
                {
                    "rank": candidate.get("rank"),
                    "selected": candidate.get("selected"),
                    "title": candidate.get("title"),
                    "score": candidate.get("score"),
                    "score_breakdown": candidate.get("score_breakdown"),
                    "reasons": candidate.get("reasons"),
                    "penalties": candidate.get("penalties"),
                }
                for candidate in collection_candidates[:10]
            ],
            "collection_candidates": collection_candidates,
            "raw_notes": raw_notes,
            "selected_notes": notes_for_comments,
            "filtered_notes": notes_for_comments,
        }
    )
    return notes_for_comments, collection_candidates

def run_comments(api, cookie: str, raw_notes: list[dict], debug_response: bool) -> list[dict]:
    comments_per_note = collector._env_int("XHS_COMMENTS_PER_NOTE", 5)
    raw_comments: list[dict] = []
    fetched_comments_count = 0
    dropped_comments_count = 0

    for note in raw_notes:
        note_url = note.get("note_url")
        if not note_url:
            _print_step("comment request", "SKIP", f"missing note_url for {note.get('title')}")
            continue

        _print_step("comment request", "RUN", note.get("title", "untitled"))
        collector._sleep_between_calls()
        comments, error, debug_responses = collector._fetch_limited_comments(
            api,
            note_url,
            cookie,
            comments_per_note,
            debug=debug_response,
        )
        if debug_response:
            _print_json(
                {
                    "comment_response_debug": {
                        "note_title": note.get("title", "untitled"),
                        "responses": debug_responses,
                    }
                }
            )
        if error:
            _print_step("comment request", "WARN", f"{note.get('title', 'untitled')}: {error}")
            continue

        for comment in comments[:comments_per_note]:
            fetched_comments_count += 1
            cleaned_comment = collector._deidentify_comment(comment, note.get("title", ""))
            if collector._should_keep_comment(cleaned_comment):
                raw_comments.append(cleaned_comment)
            else:
                dropped_comments_count += 1

    _print_step(
        "comment request",
        "OK",
        f"fetched={fetched_comments_count}, kept={len(raw_comments)}, dropped={dropped_comments_count}",
    )
    _print_json(
        {
            "comment_filter_summary": {
                "fetched_comments_count": fetched_comments_count,
                "kept_comments_count": len(raw_comments),
                "dropped_comments_count": dropped_comments_count,
            },
            "raw_comments": raw_comments,
        }
    )
    return raw_comments


def print_comment_insights(topic: str, raw_comments: list[dict]) -> tuple[list[dict], list[dict]]:
    comment_insights = collector.extract_comment_insights(topic, raw_comments)
    pain_points = collector.insights_to_pain_points(topic, comment_insights)

    _print_step(
        "comment insights",
        "OK",
        f"insights={len(comment_insights)}, pain_points={len(pain_points)}",
    )
    _print_json(
        {
            "comment_insights": comment_insights,
            "pain_points": pain_points,
        }
    )
    return comment_insights, pain_points


def build_collection_diagnostic_payload(
    *,
    topic: str,
    raw_notes: list[dict],
    collection_candidates: list[dict],
    raw_comments: list[dict],
    comment_insights: list[dict],
    pain_points: list[dict],
    comment_fetch_errors: list[dict],
) -> dict:
    return {
        "analysis_report": build_analysis_report(
            topic=topic,
            collection_candidates=collection_candidates,
            raw_notes=raw_notes,
            raw_comments=raw_comments,
            comment_insights=comment_insights,
            pain_points=pain_points,
            comment_fetch_errors=comment_fetch_errors,
        )
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Check Spider_XHS collector readiness.")
    parser.add_argument("--topic", default="宝宝湿疹护理", help="Search topic for live checks.")
    parser.add_argument("--limit", type=int, default=1, help="Max notes to fetch in live checks.")
    parser.add_argument("--search", action="store_true", help="Make a live note search request.")
    parser.add_argument("--comments", action="store_true", help="Fetch comments after live search.")
    parser.add_argument(
        "--debug-search",
        action="store_true",
        help="Print search API response summaries without exposing cookies.",
    )
    parser.add_argument(
        "--debug-response",
        action="store_true",
        help="Print comment API response summaries without exposing cookies.",
    )
    parser.add_argument("--save", action="store_true", help="Save collected data to data/collector_runs.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    cookie = check_env()
    api = check_vendor_import()

    if not args.search:
        _print_step("live search", "SKIP", "pass --search after .env is ready")
        return 0 if cookie else 2

    if not cookie:
        _print_step("live search", "FAIL", "missing cookie; cannot call Spider_XHS")
        return 2

    raw_notes, collection_candidates = run_search(api, cookie, args.topic, args.limit, args.debug_search)
    raw_comments: list[dict] = []
    comment_insights: list[dict] = []
    pain_points: list[dict] = []
    if args.comments:
        raw_comments = run_comments(api, cookie, raw_notes, args.debug_response)
        comment_insights, pain_points = print_comment_insights(args.topic, raw_comments)
    else:
        _print_step("comment request", "SKIP", "pass --comments after search works")

    diagnostic_payload = build_collection_diagnostic_payload(
        topic=args.topic,
        raw_notes=raw_notes,
        collection_candidates=collection_candidates,
        raw_comments=raw_comments,
        comment_insights=comment_insights,
        pain_points=pain_points,
        comment_fetch_errors=[],
    )
    _print_step("analysis report", "OK", diagnostic_payload["analysis_report"]["summary"])
    _print_json(diagnostic_payload)

    if args.save:
        result = {
            "raw_notes": raw_notes,
            "raw_comments": raw_comments,
            "cleaned_notes": collector.clean_notes(raw_notes),
            "collection_candidates": collection_candidates,
            "top_subtopics": collector.extract_subtopics(args.topic, raw_comments),
            "comment_insights": comment_insights,
            "pain_points": pain_points,
            "comment_fetch_errors": [],
            "analysis_report": diagnostic_payload["analysis_report"],
        }
        path = collector.save_collection_result(args.topic, result)
        _print_step("save", "OK", str(path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
