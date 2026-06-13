"""Snapshot writer for foundation business tables."""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from app.database_schema import initialize_foundation_schema


SENSITIVE_KEY_PARTS = (
    "token",
    "api_key",
    "apikey",
    "key",
    "secret",
    "cookie",
    "authorization",
    "password",
    "xsec",
)

SENSITIVE_IDENTITY_KEYS = {
    "author",
    "avatar",
    "avatarurl",
    "avatar_url",
    "commentid",
    "comment_id",
    "nickname",
    "nick_name",
    "userid",
    "user_id",
    "uid",
    "user",
}

SENSITIVE_QUERY_KEYS = {
    "access_token",
    "api_key",
    "apikey",
    "authorization",
    "cookie",
    "key",
    "secret",
    "token",
    "xsec_token",
}

PERFORMANCE_KEYS = ("views", "likes", "collects", "comments", "follows")

MIME_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".bmp": "image/bmp",
}


def sync_run_business_tables(db_path: str | Path, run_record: dict[str, Any]) -> dict[str, int]:
    """Sync a run record into the core foundation business tables."""

    run_id = str(run_record.get("run_id") or "").strip()
    if not run_id:
        raise ValueError("run record missing run_id")

    state = run_record.get("state") if isinstance(run_record.get("state"), dict) else {}
    content = run_record.get("content") if isinstance(run_record.get("content"), dict) else {}
    paths = run_record.get("paths") if isinstance(run_record.get("paths"), dict) else {}
    topic = _topic_from(run_record, state)
    timestamp = _timestamp_from(run_record)
    raw_notes = _dict_items(state.get("raw_notes"))
    candidates = _dict_items(state.get("collection_candidates"))
    raw_comments = _dict_items(state.get("raw_comments"))
    analysis_report = state.get("analysis_report")

    path = initialize_foundation_schema(db_path)
    note_refs = _build_note_refs(run_id, raw_notes)

    with sqlite3.connect(path, timeout=30) as connection:
        connection.execute("PRAGMA busy_timeout = 5000")
        _upsert_raw_notes(connection, run_id, topic, timestamp, raw_notes, note_refs)
        _upsert_collection_candidates(
            connection,
            run_id,
            topic,
            timestamp,
            candidates,
            note_refs,
        )
        _upsert_raw_comments(connection, run_id, topic, timestamp, raw_comments, note_refs)
        report_count = _upsert_analysis_report(
            connection,
            run_id,
            topic,
            timestamp,
            analysis_report,
            candidates,
            raw_comments,
        )
        draft_count = _upsert_draft(connection, run_id, topic, timestamp, run_record, state, content, paths)
        assets_count = _upsert_creator_assets(connection, run_id, timestamp, state)
        creator_notes_count = _upsert_creator_note(connection, run_id, timestamp, state)
        performance_count = _upsert_performance_record(connection, run_id, timestamp, state)
        audit_count = _upsert_audit_events(connection, run_id, timestamp, run_record, state)

    return {
        "raw_notes": len(raw_notes),
        "collection_candidates": len(candidates),
        "raw_comments": len(raw_comments),
        "analysis_reports": report_count,
        "drafts": draft_count,
        "creator_assets": assets_count,
        "creator_notes": creator_notes_count,
        "performance_records": performance_count,
        "audit_events": audit_count,
    }


def _build_note_refs(run_id: str, raw_notes: list[dict[str, Any]]) -> dict[str, str]:
    refs: dict[str, str] = {}
    for index, note in enumerate(raw_notes):
        note_url = _sanitize_url(_text(note.get("note_url")))
        source_note_id = _source_note_id(note)
        title = _text(note.get("title"))
        row_id = _note_row_id(run_id, note, index)
        refs[f"index:{index}"] = row_id
        if source_note_id:
            refs[f"source:{source_note_id}"] = row_id
        if note_url:
            refs[f"url:{note_url}"] = row_id
        if title:
            refs[f"title:{title}"] = row_id
    return refs


def _upsert_raw_notes(
    connection: sqlite3.Connection,
    run_id: str,
    topic: str,
    timestamp: str,
    raw_notes: list[dict[str, Any]],
    note_refs: dict[str, str],
) -> None:
    for index, note in enumerate(raw_notes):
        note_url = _sanitize_url(_text(note.get("note_url")))
        source_note_id = _source_note_id(note)
        title = _text(note.get("title"))
        row = {
            "note_row_id": note_refs[f"index:{index}"],
            "run_id": run_id,
            "topic": topic,
            "source": _text(note.get("source")) or "xhs_pc",
            "source_note_id": source_note_id or None,
            "title": title or None,
            "note_url": note_url or None,
            "note_type": _text(note.get("note_type") or note.get("type")) or None,
            "likes": _to_int(note.get("likes") or note.get("liked_count")),
            "collects": _to_int(note.get("collects") or note.get("collected_count")),
            "comments": _to_int(note.get("comments") or note.get("comment_count")),
            "shares": _to_int(note.get("shares") or note.get("share_count")),
            "raw_json": _json_dumps(_sanitize_payload(note)),
            "collected_at": _text(note.get("collected_at")) or timestamp,
        }
        connection.execute(
            """
            INSERT INTO raw_notes (
                note_row_id, run_id, topic, source, source_note_id, title,
                note_url, note_type, likes, collects, comments, shares,
                raw_json, collected_at
            )
            VALUES (
                :note_row_id, :run_id, :topic, :source, :source_note_id, :title,
                :note_url, :note_type, :likes, :collects, :comments, :shares,
                :raw_json, :collected_at
            )
            ON CONFLICT(note_row_id) DO UPDATE SET
                run_id = excluded.run_id,
                topic = excluded.topic,
                source = excluded.source,
                source_note_id = excluded.source_note_id,
                title = excluded.title,
                note_url = excluded.note_url,
                note_type = excluded.note_type,
                likes = excluded.likes,
                collects = excluded.collects,
                comments = excluded.comments,
                shares = excluded.shares,
                raw_json = excluded.raw_json,
                collected_at = excluded.collected_at
            """,
            row,
        )


def _upsert_collection_candidates(
    connection: sqlite3.Connection,
    run_id: str,
    topic: str,
    timestamp: str,
    candidates: list[dict[str, Any]],
    note_refs: dict[str, str],
) -> None:
    for index, candidate in enumerate(candidates):
        rank = _to_int(candidate.get("rank")) or index + 1
        note_row_id = _candidate_note_row_id(candidate, note_refs)
        row = {
            "candidate_id": _prefixed_hash(
                "cand",
                run_id,
                rank,
                _text(candidate.get("title")),
                _sanitize_url(_text(candidate.get("note_url"))),
            ),
            "run_id": run_id,
            "note_row_id": note_row_id,
            "topic": topic,
            "rank": rank,
            "selected": 1 if bool(candidate.get("selected")) else 0,
            "score": _to_int(candidate.get("score")),
            "title": _text(candidate.get("title")) or None,
            "note_url": _sanitize_url(_text(candidate.get("note_url"))) or None,
            "reasons_json": _json_dumps(_list_or_empty(candidate.get("reasons"))),
            "penalties_json": _json_dumps(_list_or_empty(candidate.get("penalties"))),
            "score_breakdown_json": _json_dumps(_dict_or_empty(candidate.get("score_breakdown"))),
            "candidate_json": _json_dumps(_sanitize_payload(candidate)),
            "created_at": _text(candidate.get("created_at")) or timestamp,
        }
        connection.execute(
            """
            INSERT INTO collection_candidates (
                candidate_id, run_id, note_row_id, topic, rank, selected, score,
                title, note_url, reasons_json, penalties_json,
                score_breakdown_json, candidate_json, created_at
            )
            VALUES (
                :candidate_id, :run_id, :note_row_id, :topic, :rank, :selected,
                :score, :title, :note_url, :reasons_json, :penalties_json,
                :score_breakdown_json, :candidate_json, :created_at
            )
            ON CONFLICT(candidate_id) DO UPDATE SET
                run_id = excluded.run_id,
                note_row_id = excluded.note_row_id,
                topic = excluded.topic,
                rank = excluded.rank,
                selected = excluded.selected,
                score = excluded.score,
                title = excluded.title,
                note_url = excluded.note_url,
                reasons_json = excluded.reasons_json,
                penalties_json = excluded.penalties_json,
                score_breakdown_json = excluded.score_breakdown_json,
                candidate_json = excluded.candidate_json,
                created_at = excluded.created_at
            """,
            row,
        )


def _upsert_raw_comments(
    connection: sqlite3.Connection,
    run_id: str,
    topic: str,
    timestamp: str,
    raw_comments: list[dict[str, Any]],
    note_refs: dict[str, str],
) -> None:
    for index, comment in enumerate(raw_comments):
        content = _text(comment.get("content"))
        source_title = _text(comment.get("source_note_title") or comment.get("note_title"))
        row = {
            "comment_row_id": _prefixed_hash("cmt", run_id, source_title, content, index),
            "run_id": run_id,
            "note_row_id": _comment_note_row_id(comment, source_title, note_refs),
            "topic": topic,
            "source_note_title": source_title or None,
            "content": content,
            "like_count": _to_int(comment.get("like_count") or comment.get("likes")),
            "kept": 0 if comment.get("kept") is False else 1,
            "noise_reason": _text(comment.get("noise_reason")) or None,
            "raw_json": _json_dumps(_sanitize_payload(comment)),
            "collected_at": _text(comment.get("collected_at")) or timestamp,
        }
        connection.execute(
            """
            INSERT INTO raw_comments (
                comment_row_id, run_id, note_row_id, topic, source_note_title,
                content, like_count, kept, noise_reason, raw_json, collected_at
            )
            VALUES (
                :comment_row_id, :run_id, :note_row_id, :topic, :source_note_title,
                :content, :like_count, :kept, :noise_reason, :raw_json, :collected_at
            )
            ON CONFLICT(comment_row_id) DO UPDATE SET
                run_id = excluded.run_id,
                note_row_id = excluded.note_row_id,
                topic = excluded.topic,
                source_note_title = excluded.source_note_title,
                content = excluded.content,
                like_count = excluded.like_count,
                kept = excluded.kept,
                noise_reason = excluded.noise_reason,
                raw_json = excluded.raw_json,
                collected_at = excluded.collected_at
            """,
            row,
        )


def _upsert_analysis_report(
    connection: sqlite3.Connection,
    run_id: str,
    topic: str,
    timestamp: str,
    analysis_report: Any,
    candidates: list[dict[str, Any]],
    raw_comments: list[dict[str, Any]],
) -> int:
    if not isinstance(analysis_report, dict) or not analysis_report:
        return 0

    sample_selection = _dict_or_empty(analysis_report.get("sample_selection"))
    comment_quality = _dict_or_empty(analysis_report.get("comment_quality"))
    confidence = _dict_or_empty(analysis_report.get("pain_point_confidence"))
    structure_hint = _dict_or_empty(analysis_report.get("content_structure_hint"))
    row = {
        "report_id": _prefixed_hash("rpt", run_id),
        "run_id": run_id,
        "topic": topic,
        "candidate_count": _to_int(sample_selection.get("candidate_count")) or len(candidates),
        "selected_count": _to_int(sample_selection.get("selected_count"))
        or sum(1 for item in candidates if item.get("selected")),
        "raw_comments_count": _to_int(comment_quality.get("raw_comments_count")) or len(raw_comments),
        "evidence_count": _to_int(comment_quality.get("evidence_count")),
        "comment_quality_level": _text(comment_quality.get("quality_level")) or None,
        "pain_point_confidence_level": _text(confidence.get("level")) or None,
        "pain_point_confidence_score": _to_int(confidence.get("score")),
        "recommended_type": _text(structure_hint.get("recommended_type")) or None,
        "risks_json": _json_dumps(_list_or_empty(analysis_report.get("risks"))),
        "summary": _text(analysis_report.get("summary")) or None,
        "report_json": _json_dumps(_sanitize_payload(analysis_report)),
        "created_at": _text(analysis_report.get("created_at")) or timestamp,
        "updated_at": _text(analysis_report.get("updated_at")) or timestamp,
    }
    connection.execute(
        """
        INSERT INTO analysis_reports (
            report_id, run_id, topic, candidate_count, selected_count,
            raw_comments_count, evidence_count, comment_quality_level,
            pain_point_confidence_level, pain_point_confidence_score,
            recommended_type, risks_json, summary, report_json, created_at, updated_at
        )
        VALUES (
            :report_id, :run_id, :topic, :candidate_count, :selected_count,
            :raw_comments_count, :evidence_count, :comment_quality_level,
            :pain_point_confidence_level, :pain_point_confidence_score,
            :recommended_type, :risks_json, :summary, :report_json, :created_at, :updated_at
        )
        ON CONFLICT(run_id) DO UPDATE SET
            topic = excluded.topic,
            candidate_count = excluded.candidate_count,
            selected_count = excluded.selected_count,
            raw_comments_count = excluded.raw_comments_count,
            evidence_count = excluded.evidence_count,
            comment_quality_level = excluded.comment_quality_level,
            pain_point_confidence_level = excluded.pain_point_confidence_level,
            pain_point_confidence_score = excluded.pain_point_confidence_score,
            recommended_type = excluded.recommended_type,
            risks_json = excluded.risks_json,
            summary = excluded.summary,
            report_json = excluded.report_json,
            updated_at = excluded.updated_at
        """,
        row,
    )
    return 1


def _upsert_draft(
    connection: sqlite3.Connection,
    run_id: str,
    topic: str,
    timestamp: str,
    run_record: dict[str, Any],
    state: dict[str, Any],
    content: dict[str, Any],
    paths: dict[str, Any],
) -> int:
    if not _has_draft_content(state, content):
        return 0

    content_format = _text(state.get("content_format") or run_record.get("request", {}).get("format")) or "image_text"
    content_type = _text(state.get("content_type")) or None
    title = _first_text(state.get("titles")) or _first_text(content.get("titles"))
    video_script = _dict_or_empty(state.get("video_script") or content.get("video_script"))
    if not title and video_script:
        title = _text(video_script.get("title"))
    markdown_path = _text(state.get("post_id") or paths.get("post_id"))
    draft_id = _draft_id(run_id)
    row = {
        "draft_id": draft_id,
        "run_id": run_id,
        "operation_record_id": _text(state.get("operation_record_id")) or None,
        "topic": topic,
        "content_format": content_format,
        "content_type": content_type,
        "title": title or None,
        "titles_json": _json_dumps(_list_or_empty(state.get("titles") or content.get("titles"))),
        "body": _text(state.get("body") or content.get("body")) or None,
        "cover_texts_json": _json_dumps(_list_or_empty(state.get("cover_texts") or content.get("cover_texts"))),
        "image_page_plan_json": _json_dumps(
            _sanitize_payload(_list_or_empty(state.get("image_page_plan") or content.get("image_page_plan")))
        ),
        "image_prompts_json": _json_dumps(_list_or_empty(state.get("image_prompts") or content.get("image_prompts"))),
        "video_script_json": _json_dumps(_sanitize_payload(video_script)),
        "tags_json": _json_dumps(_list_or_empty(state.get("tags") or content.get("tags"))),
        "comment_call": _text(state.get("comment_call") or content.get("comment_call")) or None,
        "markdown_path": markdown_path or None,
        "status": _text(state.get("publish_status")) or ("draft_saved" if markdown_path else "draft"),
        "draft_json": _json_dumps(_sanitize_payload({"content": content, "state": _draft_state_snapshot(state)})),
        "created_at": _text(run_record.get("created_at")) or timestamp,
        "updated_at": _text(run_record.get("updated_at")) or timestamp,
    }
    connection.execute(
        """
        INSERT INTO drafts (
            draft_id, run_id, operation_record_id, topic, content_format,
            content_type, title, titles_json, body, cover_texts_json,
            image_page_plan_json, image_prompts_json, video_script_json,
            tags_json, comment_call, markdown_path, status, draft_json,
            created_at, updated_at
        )
        VALUES (
            :draft_id, :run_id, :operation_record_id, :topic, :content_format,
            :content_type, :title, :titles_json, :body, :cover_texts_json,
            :image_page_plan_json, :image_prompts_json, :video_script_json,
            :tags_json, :comment_call, :markdown_path, :status, :draft_json,
            :created_at, :updated_at
        )
        ON CONFLICT(draft_id) DO UPDATE SET
            run_id = excluded.run_id,
            operation_record_id = excluded.operation_record_id,
            topic = excluded.topic,
            content_format = excluded.content_format,
            content_type = excluded.content_type,
            title = excluded.title,
            titles_json = excluded.titles_json,
            body = excluded.body,
            cover_texts_json = excluded.cover_texts_json,
            image_page_plan_json = excluded.image_page_plan_json,
            image_prompts_json = excluded.image_prompts_json,
            video_script_json = excluded.video_script_json,
            tags_json = excluded.tags_json,
            comment_call = excluded.comment_call,
            markdown_path = excluded.markdown_path,
            status = excluded.status,
            draft_json = excluded.draft_json,
            updated_at = excluded.updated_at
        """,
        row,
    )
    return 1


def _upsert_creator_assets(
    connection: sqlite3.Connection,
    run_id: str,
    timestamp: str,
    state: dict[str, Any],
) -> int:
    files = [item for item in state.get("creator_image_files") or [] if _text(item)]
    if not files:
        return 0

    prompts = _list_or_empty(state.get("image_prompts"))
    draft_id = _draft_id(run_id) if _has_draft_content(state, {}) else None
    for index, file_value in enumerate(files, start=1):
        file_path = _text(file_value)
        path = Path(file_path)
        row = {
            "asset_id": _prefixed_hash("asset", run_id, index, file_path),
            "run_id": run_id,
            "draft_id": draft_id,
            "source": "bound_file",
            "provider": None,
            "model": None,
            "file_path": file_path,
            "file_name": path.name or None,
            "mime_type": _mime_type_from_path(path),
            "file_size": _file_size(file_path),
            "width": None,
            "height": None,
            "prompt": _text(prompts[index - 1]) if index - 1 < len(prompts) else None,
            "bound_order": index,
            "status": "available",
            "metadata_json": _json_dumps(_sanitize_payload({"exists": Path(file_path).exists()})),
            "created_at": _text(state.get("creator_assets_updated_at")) or timestamp,
            "updated_at": _text(state.get("creator_assets_updated_at")) or timestamp,
        }
        connection.execute(
            """
            INSERT INTO creator_assets (
                asset_id, run_id, draft_id, source, provider, model, file_path,
                file_name, mime_type, file_size, width, height, prompt,
                bound_order, status, metadata_json, created_at, updated_at
            )
            VALUES (
                :asset_id, :run_id, :draft_id, :source, :provider, :model,
                :file_path, :file_name, :mime_type, :file_size, :width,
                :height, :prompt, :bound_order, :status, :metadata_json,
                :created_at, :updated_at
            )
            ON CONFLICT(asset_id) DO UPDATE SET
                run_id = excluded.run_id,
                draft_id = excluded.draft_id,
                source = excluded.source,
                provider = excluded.provider,
                model = excluded.model,
                file_path = excluded.file_path,
                file_name = excluded.file_name,
                mime_type = excluded.mime_type,
                file_size = excluded.file_size,
                width = excluded.width,
                height = excluded.height,
                prompt = excluded.prompt,
                bound_order = excluded.bound_order,
                status = excluded.status,
                metadata_json = excluded.metadata_json,
                updated_at = excluded.updated_at
            """,
            row,
        )
    return len(files)


def _upsert_creator_note(
    connection: sqlite3.Connection,
    run_id: str,
    timestamp: str,
    state: dict[str, Any],
) -> int:
    publish_result = _dict_or_empty(state.get("creator_publish_result"))
    creator_note_id = _text(state.get("creator_note_id") or publish_result.get("note_id"))
    if not creator_note_id:
        return 0

    row = {
        "creator_note_id": creator_note_id,
        "run_id": run_id,
        "operation_record_id": _text(state.get("operation_record_id")) or None,
        "draft_id": _draft_id(run_id) if _has_draft_content(state, {}) else None,
        "title": _first_text(state.get("titles")) or _text(publish_result.get("title")) or None,
        "publish_mode": _text(state.get("creator_publish_mode") or publish_result.get("mode")) or None,
        "publish_status": _text(state.get("creator_publish_status")) or None,
        "visibility_label": _text(
            publish_result.get("visibility_label")
            or publish_result.get("visibility")
            or state.get("visibility_label")
        ) or None,
        "permission_code": _text(publish_result.get("permission_code")) or None,
        "tab_status": _text(publish_result.get("tab_status") or publish_result.get("status")) or None,
        "platform_type": _text(publish_result.get("platform")) or None,
        "metrics_snapshot_json": _json_dumps(
            _sanitize_payload(
                publish_result.get("metrics_snapshot")
                or publish_result.get("metrics")
                or {}
            )
        ),
        "last_sync_status": _text(state.get("creator_note_sync_status")) or None,
        "last_synced_at": _text(state.get("creator_note_synced_at")) or None,
        "publish_response_json": _json_dumps(_sanitize_payload(publish_result)),
        "created_at": timestamp,
        "updated_at": timestamp,
    }
    connection.execute(
        """
        INSERT INTO creator_notes (
            creator_note_id, run_id, operation_record_id, draft_id, title,
            publish_mode, publish_status, visibility_label, permission_code,
            tab_status, platform_type, metrics_snapshot_json, last_sync_status,
            last_synced_at, publish_response_json, created_at, updated_at
        )
        VALUES (
            :creator_note_id, :run_id, :operation_record_id, :draft_id,
            :title, :publish_mode, :publish_status, :visibility_label,
            :permission_code, :tab_status, :platform_type,
            :metrics_snapshot_json, :last_sync_status, :last_synced_at,
            :publish_response_json, :created_at, :updated_at
        )
        ON CONFLICT(creator_note_id) DO UPDATE SET
            run_id = excluded.run_id,
            operation_record_id = excluded.operation_record_id,
            draft_id = excluded.draft_id,
            title = excluded.title,
            publish_mode = excluded.publish_mode,
            publish_status = excluded.publish_status,
            visibility_label = excluded.visibility_label,
            permission_code = excluded.permission_code,
            tab_status = excluded.tab_status,
            platform_type = excluded.platform_type,
            metrics_snapshot_json = excluded.metrics_snapshot_json,
            last_sync_status = excluded.last_sync_status,
            last_synced_at = excluded.last_synced_at,
            publish_response_json = excluded.publish_response_json,
            updated_at = excluded.updated_at
        """,
        row,
    )
    return 1


def _upsert_performance_record(
    connection: sqlite3.Connection,
    run_id: str,
    timestamp: str,
    state: dict[str, Any],
) -> int:
    performance_data = state.get("performance_data")
    if not isinstance(performance_data, dict) or not any(key in performance_data for key in PERFORMANCE_KEYS):
        return 0

    creator_note_id = _text(state.get("creator_note_id")) or None
    operation_record_id = _text(state.get("operation_record_id")) or None
    row = {
        "performance_id": _prefixed_hash("perf", operation_record_id, creator_note_id, run_id),
        "operation_record_id": operation_record_id,
        "creator_note_id": creator_note_id,
        "run_id": run_id,
        "views": _to_int(performance_data.get("views")),
        "likes": _to_int(performance_data.get("likes")),
        "collects": _to_int(performance_data.get("collects")),
        "comments": _to_int(performance_data.get("comments")),
        "follows": _to_int(performance_data.get("follows")),
        "performance_score": _to_int(state.get("performance_score")),
        "source": "run_state",
        "notes": _text(state.get("review_summary")) or None,
        "payload_json": _json_dumps(
            _sanitize_payload(
                {
                    "performance_data": performance_data,
                    "review_summary": state.get("review_summary"),
                    "next_action": state.get("next_action"),
                }
            )
        ),
        "recorded_at": _text(state.get("performance_recorded_at")) or timestamp,
        "created_at": timestamp,
    }
    connection.execute(
        """
        INSERT INTO performance_records (
            performance_id, operation_record_id, creator_note_id, run_id,
            views, likes, collects, comments, follows, performance_score,
            source, notes, payload_json, recorded_at, created_at
        )
        VALUES (
            :performance_id, :operation_record_id, :creator_note_id, :run_id,
            :views, :likes, :collects, :comments, :follows,
            :performance_score, :source, :notes, :payload_json,
            :recorded_at, :created_at
        )
        ON CONFLICT(performance_id) DO UPDATE SET
            operation_record_id = excluded.operation_record_id,
            creator_note_id = excluded.creator_note_id,
            run_id = excluded.run_id,
            views = excluded.views,
            likes = excluded.likes,
            collects = excluded.collects,
            comments = excluded.comments,
            follows = excluded.follows,
            performance_score = excluded.performance_score,
            source = excluded.source,
            notes = excluded.notes,
            payload_json = excluded.payload_json,
            recorded_at = excluded.recorded_at
        """,
        row,
    )
    return 1


def _upsert_audit_events(
    connection: sqlite3.Connection,
    run_id: str,
    timestamp: str,
    run_record: dict[str, Any],
    state: dict[str, Any],
) -> int:
    events = _audit_events(run_id, timestamp, run_record, state)
    for event in events:
        connection.execute(
            """
            INSERT INTO audit_events (
                audit_id, run_id, operation_record_id, actor, action,
                target_type, target_id, result, message, payload_json, created_at
            )
            VALUES (
                :audit_id, :run_id, :operation_record_id, :actor, :action,
                :target_type, :target_id, :result, :message, :payload_json,
                :created_at
            )
            ON CONFLICT(audit_id) DO UPDATE SET
                run_id = excluded.run_id,
                operation_record_id = excluded.operation_record_id,
                actor = excluded.actor,
                action = excluded.action,
                target_type = excluded.target_type,
                target_id = excluded.target_id,
                result = excluded.result,
                message = excluded.message,
                payload_json = excluded.payload_json,
                created_at = excluded.created_at
            """,
            event,
        )
    return len(events)


def _candidate_note_row_id(candidate: dict[str, Any], note_refs: dict[str, str]) -> str | None:
    original_index = candidate.get("original_index")
    if isinstance(original_index, int):
        found = note_refs.get(f"index:{original_index}")
        if found:
            return found
    for key in (
        f"source:{_text(candidate.get('source_note_id') or candidate.get('note_id') or candidate.get('id'))}",
        f"url:{_sanitize_url(_text(candidate.get('note_url')))}",
        f"title:{_text(candidate.get('title'))}",
    ):
        if key in note_refs:
            return note_refs[key]
    return None


def _comment_note_row_id(
    comment: dict[str, Any],
    source_title: str,
    note_refs: dict[str, str],
) -> str | None:
    for key in (
        f"source:{_text(comment.get('source_note_id') or comment.get('note_id'))}",
        f"url:{_sanitize_url(_text(comment.get('note_url')))}",
        f"title:{source_title}",
    ):
        if key in note_refs:
            return note_refs[key]
    return None


def _draft_id(run_id: str) -> str:
    return _prefixed_hash("draft", run_id)


def _has_draft_content(state: dict[str, Any], content: dict[str, Any]) -> bool:
    return any(
        bool(value)
        for value in (
            state.get("titles"),
            state.get("body"),
            state.get("video_script"),
            content.get("titles"),
            content.get("body"),
            content.get("video_script"),
        )
    )


def _draft_state_snapshot(state: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "user_topic",
        "target_user",
        "content_format",
        "content_type",
        "titles",
        "cover_texts",
        "body",
        "image_page_plan",
        "image_prompts",
        "video_script",
        "tags",
        "comment_call",
        "post_id",
        "publish_status",
        "operation_record_id",
    )
    return {key: state.get(key) for key in keys if key in state}


def _first_text(value: Any) -> str:
    if isinstance(value, list):
        for item in value:
            text = _text(item)
            if text:
                return text
    return _text(value)


def _mime_type_from_path(path: Path) -> str | None:
    return MIME_TYPES.get(path.suffix.lower())


def _file_size(file_path: str) -> int:
    try:
        path = Path(file_path)
        return path.stat().st_size if path.exists() and path.is_file() else 0
    except OSError:
        return 0


def _audit_events(
    run_id: str,
    timestamp: str,
    run_record: dict[str, Any],
    state: dict[str, Any],
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    operation_record_id = _text(state.get("operation_record_id")) or None

    if "human_approved" in state or run_record.get("review_action"):
        action = "human_review"
        result = _text(run_record.get("review_action")) or ("approved" if state.get("human_approved") else "rejected")
        events.append(
            _audit_event_row(
                run_id,
                timestamp,
                operation_record_id,
                action,
                target_type="run",
                target_id=run_id,
                result=result,
                message=_text(state.get("human_feedback")) or None,
                payload={
                    "human_approved": state.get("human_approved"),
                    "review_action": run_record.get("review_action"),
                },
            )
        )

    if state.get("creator_publish_requested") is not None:
        action = "creator_publish"
        events.append(
            _audit_event_row(
                run_id,
                timestamp,
                operation_record_id,
                action,
                target_type="creator_note",
                target_id=_text(state.get("creator_note_id")) or None,
                result=_text(state.get("creator_publish_status")) or None,
                message=_text(state.get("creator_publish_error")) or None,
                payload={
                    "creator_publish_requested": state.get("creator_publish_requested"),
                    "creator_publish_mode": state.get("creator_publish_mode"),
                    "creator_publish_result": state.get("creator_publish_result") or {},
                },
            )
        )

    if state.get("operation_memory_written") is not None:
        action = "operation_memory_write"
        events.append(
            _audit_event_row(
                run_id,
                timestamp,
                operation_record_id,
                action,
                target_type="operation_record",
                target_id=operation_record_id,
                result="success" if state.get("operation_memory_written") else "skipped",
                message=None,
                payload={
                    "operation_memory_path": state.get("operation_memory_path"),
                    "operation_memory_written": state.get("operation_memory_written"),
                },
            )
        )

    return events


def _audit_event_row(
    run_id: str,
    timestamp: str,
    operation_record_id: str | None,
    action: str,
    *,
    target_type: str,
    target_id: str | None,
    result: str | None,
    message: str | None,
    payload: dict[str, Any],
) -> dict[str, Any]:
    return {
        "audit_id": _prefixed_hash("audit", run_id, action, target_id),
        "run_id": run_id,
        "operation_record_id": operation_record_id,
        "actor": "system",
        "action": action,
        "target_type": target_type,
        "target_id": target_id,
        "result": result,
        "message": message,
        "payload_json": _json_dumps(_sanitize_payload(payload)),
        "created_at": timestamp,
    }


def _note_row_id(run_id: str, note: dict[str, Any], index: int) -> str:
    return _prefixed_hash(
        "note",
        run_id,
        _source_note_id(note),
        _sanitize_url(_text(note.get("note_url"))),
        _text(note.get("title")),
        index,
    )


def _source_note_id(note: dict[str, Any]) -> str:
    note_card = note.get("note_card") if isinstance(note.get("note_card"), dict) else {}
    return _text(
        note.get("source_note_id")
        or note.get("note_id")
        or note.get("id")
        or note_card.get("note_id")
    )


def _topic_from(run_record: dict[str, Any], state: dict[str, Any]) -> str:
    request = run_record.get("request") if isinstance(run_record.get("request"), dict) else {}
    return (
        _text(state.get("user_topic"))
        or _text(state.get("topic"))
        or _text(request.get("topic"))
        or _text(request.get("user_topic"))
        or "unknown"
    )


def _timestamp_from(run_record: dict[str, Any]) -> str:
    for key in ("finished_at", "updated_at", "created_at"):
        value = _text(run_record.get(key))
        if value:
            return value
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _sanitize_payload(value: Any) -> Any:
    if isinstance(value, dict):
        sanitized: dict[str, Any] = {}
        for key, item in value.items():
            if _is_sensitive_key(str(key)):
                continue
            sanitized[key] = _sanitize_payload(item)
        return sanitized
    if isinstance(value, list):
        return [_sanitize_payload(item) for item in value]
    if isinstance(value, tuple):
        return [_sanitize_payload(item) for item in value]
    if isinstance(value, str):
        return _sanitize_text(value)
    return value


def _is_sensitive_key(key: str) -> bool:
    lowered = key.lower()
    compact = re.sub(r"[^a-z0-9]+", "", lowered)
    if compact in SENSITIVE_IDENTITY_KEYS:
        return True
    return any(part in lowered for part in SENSITIVE_KEY_PARTS)


def _sanitize_text(value: str) -> str:
    text = _sanitize_url(value)
    text = re.sub(r"(?i)\bauthorization\s*[:=]\s*Bearer\s+[^\s,;]+", "authorization=<redacted>", text)
    text = re.sub(r"(?i)\b(cookie|token|password|api[_-]?key|apikey)\s*[:=]\s*[^\s,;]+", r"\1=<redacted>", text)
    text = re.sub(r"sk-[A-Za-z0-9_\-\*]+", "<redacted_api_key>", text)
    return text


def _sanitize_url(value: str) -> str:
    if not value:
        return ""
    parsed = urlsplit(value)
    if not parsed.scheme or not parsed.netloc:
        return value
    query = [
        (key, item)
        for key, item in parse_qsl(parsed.query, keep_blank_values=True)
        if key.lower() not in SENSITIVE_QUERY_KEYS
        and not _is_sensitive_key(key)
    ]
    return urlunsplit(
        (
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            urlencode(query, doseq=True),
            parsed.fragment,
        )
    )


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def _prefixed_hash(prefix: str, *parts: Any) -> str:
    text = "|".join(str(part) for part in parts if part is not None)
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]
    return f"{prefix}_{digest}"


def _dict_items(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _dict_or_empty(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list_or_empty(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _to_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0
