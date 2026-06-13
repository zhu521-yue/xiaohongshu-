"""Foundation SQLite schema for structured business data."""

from __future__ import annotations

import sqlite3
from pathlib import Path


FOUNDATION_TABLES = (
    "run_events",
    "raw_notes",
    "collection_candidates",
    "raw_comments",
    "analysis_reports",
    "drafts",
    "creator_assets",
    "creator_notes",
    "performance_records",
    "audit_events",
)

FOUNDATION_INDEXES = (
    "idx_run_events_run_id_created_at",
    "idx_run_events_type",
    "idx_raw_notes_run_id",
    "idx_raw_notes_topic",
    "idx_raw_notes_source_note_id",
    "idx_collection_candidates_run_rank",
    "idx_collection_candidates_topic_score",
    "idx_collection_candidates_selected",
    "idx_raw_comments_run_id",
    "idx_raw_comments_topic",
    "idx_raw_comments_note_row_id",
    "idx_analysis_reports_topic",
    "idx_analysis_reports_quality",
    "idx_drafts_run_id",
    "idx_drafts_topic",
    "idx_drafts_status",
    "idx_creator_assets_run_id",
    "idx_creator_assets_status",
    "idx_creator_notes_run_id",
    "idx_creator_notes_operation_record_id",
    "idx_creator_notes_publish_status",
    "idx_performance_records_creator_note_id",
    "idx_performance_records_operation_record_id",
    "idx_audit_events_run_id_created_at",
    "idx_audit_events_action",
)

FOUNDATION_SCHEMA_SQL = (
    """
    CREATE TABLE IF NOT EXISTS run_events (
      event_id TEXT PRIMARY KEY,
      run_id TEXT NOT NULL,
      event_type TEXT NOT NULL,
      node_name TEXT,
      status TEXT,
      message TEXT,
      error TEXT,
      started_at TEXT,
      finished_at TEXT,
      duration_ms INTEGER,
      payload_json TEXT NOT NULL DEFAULT '{}',
      created_at TEXT NOT NULL,
      FOREIGN KEY (run_id) REFERENCES runs(run_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS raw_notes (
      note_row_id TEXT PRIMARY KEY,
      run_id TEXT NOT NULL,
      topic TEXT NOT NULL,
      source TEXT NOT NULL DEFAULT 'xhs_pc',
      source_note_id TEXT,
      title TEXT,
      note_url TEXT,
      note_type TEXT,
      likes INTEGER NOT NULL DEFAULT 0,
      collects INTEGER NOT NULL DEFAULT 0,
      comments INTEGER NOT NULL DEFAULT 0,
      shares INTEGER NOT NULL DEFAULT 0,
      raw_json TEXT NOT NULL DEFAULT '{}',
      collected_at TEXT NOT NULL,
      FOREIGN KEY (run_id) REFERENCES runs(run_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS collection_candidates (
      candidate_id TEXT PRIMARY KEY,
      run_id TEXT NOT NULL,
      note_row_id TEXT,
      topic TEXT NOT NULL,
      rank INTEGER NOT NULL,
      selected INTEGER NOT NULL DEFAULT 0,
      score INTEGER NOT NULL DEFAULT 0,
      title TEXT,
      note_url TEXT,
      reasons_json TEXT NOT NULL DEFAULT '[]',
      penalties_json TEXT NOT NULL DEFAULT '[]',
      score_breakdown_json TEXT NOT NULL DEFAULT '{}',
      candidate_json TEXT NOT NULL DEFAULT '{}',
      created_at TEXT NOT NULL,
      FOREIGN KEY (run_id) REFERENCES runs(run_id),
      FOREIGN KEY (note_row_id) REFERENCES raw_notes(note_row_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS raw_comments (
      comment_row_id TEXT PRIMARY KEY,
      run_id TEXT NOT NULL,
      note_row_id TEXT,
      topic TEXT NOT NULL,
      source_note_title TEXT,
      content TEXT NOT NULL,
      like_count INTEGER NOT NULL DEFAULT 0,
      kept INTEGER NOT NULL DEFAULT 1,
      noise_reason TEXT,
      raw_json TEXT NOT NULL DEFAULT '{}',
      collected_at TEXT NOT NULL,
      FOREIGN KEY (run_id) REFERENCES runs(run_id),
      FOREIGN KEY (note_row_id) REFERENCES raw_notes(note_row_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS analysis_reports (
      report_id TEXT PRIMARY KEY,
      run_id TEXT NOT NULL UNIQUE,
      topic TEXT NOT NULL,
      candidate_count INTEGER NOT NULL DEFAULT 0,
      selected_count INTEGER NOT NULL DEFAULT 0,
      raw_comments_count INTEGER NOT NULL DEFAULT 0,
      evidence_count INTEGER NOT NULL DEFAULT 0,
      comment_quality_level TEXT,
      pain_point_confidence_level TEXT,
      pain_point_confidence_score INTEGER NOT NULL DEFAULT 0,
      recommended_type TEXT,
      risks_json TEXT NOT NULL DEFAULT '[]',
      summary TEXT,
      report_json TEXT NOT NULL DEFAULT '{}',
      created_at TEXT NOT NULL,
      updated_at TEXT NOT NULL,
      FOREIGN KEY (run_id) REFERENCES runs(run_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS drafts (
      draft_id TEXT PRIMARY KEY,
      run_id TEXT NOT NULL,
      operation_record_id TEXT,
      topic TEXT NOT NULL,
      content_format TEXT NOT NULL,
      content_type TEXT,
      title TEXT,
      titles_json TEXT NOT NULL DEFAULT '[]',
      body TEXT,
      cover_texts_json TEXT NOT NULL DEFAULT '[]',
      image_page_plan_json TEXT NOT NULL DEFAULT '[]',
      image_prompts_json TEXT NOT NULL DEFAULT '[]',
      video_script_json TEXT NOT NULL DEFAULT '{}',
      tags_json TEXT NOT NULL DEFAULT '[]',
      comment_call TEXT,
      markdown_path TEXT,
      status TEXT NOT NULL DEFAULT 'draft',
      draft_json TEXT NOT NULL DEFAULT '{}',
      created_at TEXT NOT NULL,
      updated_at TEXT NOT NULL,
      FOREIGN KEY (run_id) REFERENCES runs(run_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS creator_assets (
      asset_id TEXT PRIMARY KEY,
      run_id TEXT,
      draft_id TEXT,
      source TEXT NOT NULL,
      provider TEXT,
      model TEXT,
      file_path TEXT NOT NULL,
      file_name TEXT,
      mime_type TEXT,
      file_size INTEGER,
      width INTEGER,
      height INTEGER,
      prompt TEXT,
      bound_order INTEGER,
      status TEXT NOT NULL DEFAULT 'available',
      metadata_json TEXT NOT NULL DEFAULT '{}',
      created_at TEXT NOT NULL,
      updated_at TEXT NOT NULL,
      FOREIGN KEY (run_id) REFERENCES runs(run_id),
      FOREIGN KEY (draft_id) REFERENCES drafts(draft_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS creator_notes (
      creator_note_id TEXT PRIMARY KEY,
      run_id TEXT,
      operation_record_id TEXT,
      draft_id TEXT,
      title TEXT,
      publish_mode TEXT,
      publish_status TEXT,
      visibility_label TEXT,
      permission_code TEXT,
      tab_status TEXT,
      platform_type TEXT,
      metrics_snapshot_json TEXT NOT NULL DEFAULT '{}',
      last_sync_status TEXT,
      last_synced_at TEXT,
      publish_response_json TEXT NOT NULL DEFAULT '{}',
      created_at TEXT NOT NULL,
      updated_at TEXT NOT NULL,
      FOREIGN KEY (run_id) REFERENCES runs(run_id),
      FOREIGN KEY (draft_id) REFERENCES drafts(draft_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS performance_records (
      performance_id TEXT PRIMARY KEY,
      operation_record_id TEXT,
      creator_note_id TEXT,
      run_id TEXT,
      views INTEGER NOT NULL DEFAULT 0,
      likes INTEGER NOT NULL DEFAULT 0,
      collects INTEGER NOT NULL DEFAULT 0,
      comments INTEGER NOT NULL DEFAULT 0,
      follows INTEGER NOT NULL DEFAULT 0,
      performance_score INTEGER NOT NULL DEFAULT 0,
      source TEXT NOT NULL DEFAULT 'manual',
      notes TEXT,
      payload_json TEXT NOT NULL DEFAULT '{}',
      recorded_at TEXT NOT NULL,
      created_at TEXT NOT NULL,
      FOREIGN KEY (run_id) REFERENCES runs(run_id),
      FOREIGN KEY (creator_note_id) REFERENCES creator_notes(creator_note_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS audit_events (
      audit_id TEXT PRIMARY KEY,
      run_id TEXT,
      operation_record_id TEXT,
      actor TEXT,
      action TEXT NOT NULL,
      target_type TEXT,
      target_id TEXT,
      result TEXT,
      message TEXT,
      payload_json TEXT NOT NULL DEFAULT '{}',
      created_at TEXT NOT NULL,
      FOREIGN KEY (run_id) REFERENCES runs(run_id)
    )
    """,
)

FOUNDATION_INDEX_SQL = (
    "CREATE INDEX IF NOT EXISTS idx_run_events_run_id_created_at ON run_events(run_id, created_at)",
    "CREATE INDEX IF NOT EXISTS idx_run_events_type ON run_events(event_type)",
    "CREATE INDEX IF NOT EXISTS idx_raw_notes_run_id ON raw_notes(run_id)",
    "CREATE INDEX IF NOT EXISTS idx_raw_notes_topic ON raw_notes(topic)",
    "CREATE INDEX IF NOT EXISTS idx_raw_notes_source_note_id ON raw_notes(source_note_id)",
    "CREATE INDEX IF NOT EXISTS idx_collection_candidates_run_rank ON collection_candidates(run_id, rank)",
    "CREATE INDEX IF NOT EXISTS idx_collection_candidates_topic_score ON collection_candidates(topic, score)",
    "CREATE INDEX IF NOT EXISTS idx_collection_candidates_selected ON collection_candidates(run_id, selected)",
    "CREATE INDEX IF NOT EXISTS idx_raw_comments_run_id ON raw_comments(run_id)",
    "CREATE INDEX IF NOT EXISTS idx_raw_comments_topic ON raw_comments(topic)",
    "CREATE INDEX IF NOT EXISTS idx_raw_comments_note_row_id ON raw_comments(note_row_id)",
    "CREATE INDEX IF NOT EXISTS idx_analysis_reports_topic ON analysis_reports(topic)",
    "CREATE INDEX IF NOT EXISTS idx_analysis_reports_quality ON analysis_reports(comment_quality_level, pain_point_confidence_level)",
    "CREATE INDEX IF NOT EXISTS idx_drafts_run_id ON drafts(run_id)",
    "CREATE INDEX IF NOT EXISTS idx_drafts_topic ON drafts(topic)",
    "CREATE INDEX IF NOT EXISTS idx_drafts_status ON drafts(status)",
    "CREATE INDEX IF NOT EXISTS idx_creator_assets_run_id ON creator_assets(run_id)",
    "CREATE INDEX IF NOT EXISTS idx_creator_assets_status ON creator_assets(status)",
    "CREATE INDEX IF NOT EXISTS idx_creator_notes_run_id ON creator_notes(run_id)",
    "CREATE INDEX IF NOT EXISTS idx_creator_notes_operation_record_id ON creator_notes(operation_record_id)",
    "CREATE INDEX IF NOT EXISTS idx_creator_notes_publish_status ON creator_notes(publish_status)",
    "CREATE INDEX IF NOT EXISTS idx_performance_records_creator_note_id ON performance_records(creator_note_id, recorded_at)",
    "CREATE INDEX IF NOT EXISTS idx_performance_records_operation_record_id ON performance_records(operation_record_id, recorded_at)",
    "CREATE INDEX IF NOT EXISTS idx_audit_events_run_id_created_at ON audit_events(run_id, created_at)",
    "CREATE INDEX IF NOT EXISTS idx_audit_events_action ON audit_events(action)",
)


def initialize_foundation_schema(db_path: str | Path) -> Path:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path, timeout=30) as connection:
        connection.execute("PRAGMA busy_timeout = 5000")
        for statement in FOUNDATION_SCHEMA_SQL:
            connection.execute(statement)
        for statement in FOUNDATION_INDEX_SQL:
            connection.execute(statement)
    return path
