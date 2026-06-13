# Foundation Baselines Design

## Goal

Build the first implementation slice for three foundation lines before continuing the main feature track:

1. Data quality baseline before RAG and GraphRAG.
2. Configuration governance for remaining hard-coded business rules.
3. Production-lite deployment baseline for a final deploy path.

This slice must stay small, testable, and compatible with the current LangGraph-first, SQLite-capable runtime. It must not introduce vector search, a graph database, Docker, Nginx, systemd, Redis, user accounts, or new public platform write behavior.

## Current State

The project already has:

- Candidate scoring and selected sample flags in `collection_candidates`.
- Deterministic `analysis_report` output with sample selection, comment quality, pain point confidence, structure hint, and risks.
- SQLite run store, queue, operation memory, business table overlay, performance records, run events, and local stack scripts.
- M5 first slice: `app/memory_graph.py` derives a graph-style view from operation memory.
- Minimal production guardrails: optional API token, redacted logs, runtime config checks, startup/health/stop/tail scripts.

The project still lacks:

- An explicit RAG eligibility gate that says whether a run is good enough to enter future RAG/GraphRAG memory.
- Configurable thresholds for analysis quality and cross-domain pollution filtering.
- A production-lite deploy checklist that can be machine-checked beyond the existing runtime config checks.
- Backup and restore helpers for the single-file SQLite production-lite shape.

## Scope

### In Scope

Data quality:

- Add a deterministic quality gate that consumes existing run state fields:
  - `analysis_report`
  - `collection_candidates`
  - `raw_comments`
  - `comment_insights`
  - `pain_points`
  - `comment_fetch_errors`
- Return a `rag_eligibility` object with:
  - `eligible`
  - `level`
  - `score`
  - `reasons`
  - `blocking_reasons`
  - `recommended_action`
- Persist the gate result in run state and business table JSON payloads through existing sync paths where possible.

Configuration governance:

- Move analysis threshold values from code into a new JSON config file.
- Move operation memory cross-domain pollution keywords and patterns into config.
- Keep safe fallback defaults in code only for missing optional labels, not for business policy.

Deployment baseline:

- Add a production-lite deployment checklist helper that verifies:
  - API token is set.
  - SQLite run store, queue, and memory are enabled.
  - Foundation schema is selected.
  - Business table writes are enabled.
  - Log directory is writable.
  - DB parent directory is writable.
  - Backup directory is writable.
  - Real LLM key and Spider_XHS cookie are present or explicitly marked as unavailable warnings.
- Add SQLite backup and restore scripts for the production-lite single-DB path.
- Document what this baseline can support and what remains required before public exposure.

### Out of Scope

- Embeddings, vector databases, pgvector, graph databases, or full GraphRAG ingestion.
- Full historical data migration.
- Docker, Nginx, systemd, HTTPS certificates, Redis/RQ/Celery, or user account systems.
- Public publishing, video publishing, platform scheduled publishing, or expanded creator write behavior.
- Encrypting cookies at rest. This remains a later security item.

## Architecture

### Data Quality Gate

Create `app/data_quality_gate.py`.

Responsibilities:

- Load threshold rules from config.
- Evaluate existing structured signals without re-fetching platform data.
- Produce a compact `rag_eligibility` result suitable for run state, business table payloads, future GraphRAG ingestion, and UI display.

Suggested result shape:

```json
{
  "eligible": false,
  "level": "blocked",
  "score": 38,
  "reasons": ["候选池存在，但评论证据偏少"],
  "blocking_reasons": ["评论样本较少", "痛点证据不足"],
  "recommended_action": "重新采集更多候选和评论后再进入 RAG 入库"
}
```

Scoring should start simple and deterministic:

- Use analysis report confidence score as the main signal.
- Add selected candidate count signal.
- Add comment insight and evidence signal.
- Penalize comment fetch errors.
- Block when no candidates, no comments, or confidence is below configured minimum.

### Configuration Files

Add `config/data_quality_rules.json`.

Initial structure:

```json
{
  "rag_gate": {
    "min_score": 60,
    "min_selected_candidates": 1,
    "min_raw_comments": 5,
    "min_evidence_count": 2,
    "block_on_comment_fetch_errors": false
  },
  "analysis_report": {
    "high_quality_min_comments": 20,
    "high_quality_min_evidence": 5,
    "medium_quality_min_comments": 5,
    "medium_quality_min_evidence": 2,
    "comment_fetch_error_penalty": 15,
    "empty_sample_score_cap": 45
  },
  "cross_domain_pollution": {
    "health_topic_keywords": [],
    "health_pollution_patterns": []
  }
}
```

The actual keyword lists should be moved from `memory/operation_store.py` into this file.

Extend `app/rules.py` with `load_data_quality_rules()`.

### Integration Points

Data quality should integrate at the lowest-risk points:

- `platforms/analysis_report.py` reads configurable thresholds but keeps its public return shape.
- The LangGraph analysis node or run assembly path adds `rag_eligibility` after `analysis_report` exists.
- Business table sync stores the value inside existing sanitized JSON payloads first; adding a dedicated column can be a later migration.
- `memory_graph` stays read-only and does not ingest anything new in this slice.

### Deployment Helpers

Add scripts:

- `scripts/check_production_lite_deploy.py`
- `scripts/backup_sqlite_db.py`
- `scripts/restore_sqlite_db.py`

`check_production_lite_deploy.py` should reuse `scripts/check_runtime_config.py` logic where possible and add deployment-specific checks rather than duplicate everything.

Backup script behavior:

- Resolve DB path inside the project unless an absolute path is provided.
- Create a timestamped copy in `data/backups` by default.
- Refuse to overwrite an existing backup.
- Output structured JSON.

Restore script behavior:

- Default to dry-run.
- Require `--apply` to replace the target DB.
- Create a pre-restore backup before replacement.
- Refuse paths outside the project unless explicitly absolute and readable.
- Output structured JSON.

## Error Handling

- Missing config file should fail loudly for required rules.
- Malformed config should raise a clear runtime error through `app.rules`.
- Data quality gate should never raise on missing run fields; it should return a blocked or low-confidence result.
- Backup and restore scripts must never delete files.
- Restore must not run without `--apply`.
- All script output must avoid printing cookies, API keys, authorization headers, or raw `.env` values.

## Testing

Add focused tests:

- `tests/test_data_quality_gate.py`
  - Eligible run with enough candidates, comments, evidence, and confidence.
  - Blocked run when comments or evidence are missing.
  - Penalized run when comment fetch errors exist.
- `tests/test_analysis_report_config.py`
  - Config thresholds influence comment quality levels.
- `tests/test_operation_memory_config.py`
  - Cross-domain pollution keywords load from config and still block health contamination for non-health topics.
- `tests/test_production_lite_deploy_check.py`
  - Missing API token fails.
  - SQLite production-lite settings pass the deployment preflight.
  - Missing backup directory is created or reported writable.
- `tests/test_sqlite_backup_restore_scripts.py`
  - Backup creates timestamped copy.
  - Restore dry-run does not modify DB.
  - Restore with `--apply` creates pre-restore backup and replaces DB.

Run targeted tests first, then related regression, then full test suite if time allows.

## Documentation

Update:

- `docs/m17b-startup-templates.md` with production-lite deploy checklist, backup, and restore commands.
- `memory/current_progress.md` with this slice's completed work, verification, and remaining limits.
- `memory/project_status_and_roadmap.md` to mark the three foundation lines as initial implementation started, not fully complete.

## Acceptance Criteria

- `analysis_report` thresholds are configurable.
- Operation memory cross-domain pollution rules are configurable.
- A run can expose `rag_eligibility` without introducing full RAG.
- Production-lite deployment preflight has a dedicated script.
- SQLite backup and restore helpers exist and are covered by tests.
- No `.env` secret values are read into logs or documentation.
- Existing local/mock flow keeps working.

## Remaining Work After This Slice

- Full RAG/GraphRAG ingestion and vector retrieval.
- Historical JSON and operation memory migration.
- Dedicated business table columns for RAG eligibility and quality metrics.
- Public-production deployment with HTTPS, reverse proxy, process supervision, user accounts, and stronger secret handling.
- Complete BI and time-series analytics.
