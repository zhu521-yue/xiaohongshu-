# Business Table Auto Sync Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enable opt-in automatic business table synchronization for successful SQLite runs, and add a repair script for existing run records.

**Architecture:** Extend existing settings with `XHS_AGENT_DB_SCHEMA` and `XHS_AGENT_BUSINESS_TABLES_ENABLED`, keep writes disabled by default, and call `sync_run_business_tables()` only after successful run records are saved to the SQLite run database. Add a script that loads run records from the configured run store and synchronizes all or selected runs into the same SQLite database.

**Tech Stack:** Python 3, SQLite, existing `app.api`, `app.config`, `app.run_store`, `app.business_store`, pytest.

---

### Task 1: Settings and API Auto Sync

**Files:**
- Modify: `app/config.py`
- Modify: `app/api.py`
- Test: `tests/test_m17a_config.py`
- Test: `tests/test_api_business_table_sync.py`

- [ ] **Step 1: Write settings tests**

Add assertions that:
- default `business_tables_enabled` is `False`.
- env `XHS_AGENT_BUSINESS_TABLES_ENABLED=true` reads as `True`.
- default `db_schema` is `foundation`.

- [ ] **Step 2: Write API sync tests**

Use SQLite run store with `XHS_AGENT_BUSINESS_TABLES_ENABLED=true`. Save a successful run through `api._save_run(record)` and assert rows appear in `raw_notes`, `collection_candidates`, `raw_comments`, and `analysis_reports`.

Also test:
- queued/running records do not sync.
- disabled flag does not sync.
- sync failure does not raise from `_save_run`; it records `summary.business_table_sync_status="failed"`.

- [ ] **Step 3: Run red tests**

Run:

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m pytest tests\test_m17a_config.py tests\test_api_business_table_sync.py -q
```

Expected: fail because settings fields and API sync hook do not exist.

- [ ] **Step 4: Implement settings and hook**

Implementation details:
- Add `db_schema: str` and `business_tables_enabled: bool` to `Settings`.
- Add `_env_bool(name, default)` to `app.config`.
- In `app.api`, import `sync_run_business_tables`.
- Add helper `_maybe_sync_business_tables(record)` that returns a copied record.
- `_save_run(record)` should first save the run record, then if enabled and `status=="success"` and the run store is `SQLiteRunStore`, call `sync_run_business_tables()`.
- On sync success, save a copied record with:
  - `summary.business_table_sync_status="success"`
  - `summary.business_table_sync_counts=<counts>`
  - `summary.business_table_sync_error=None`
- On sync failure, save a copied record with:
  - `summary.business_table_sync_status="failed"`
  - `summary.business_table_sync_error=<sanitized short error>`
- Do not sync when store is JSON or status is not success.

- [ ] **Step 5: Run focused tests**

Run:

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m pytest tests\test_m17a_config.py tests\test_api_business_table_sync.py -q
```

Expected: pass.

### Task 2: Historical Run Repair Script

**Files:**
- Create: `scripts/sync_run_to_business_tables.py`
- Test: `tests/test_sync_run_to_business_tables_script.py`

- [ ] **Step 1: Write failing script tests**

Test that:
- `build_parser()` accepts `--run-id`, `--limit`, and `--dry-run`.
- `sync_runs(db_path, runs)` writes successful records and skips non-success records.
- `main()` can dry-run without writing rows.

- [ ] **Step 2: Run red tests**

Run:

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m pytest tests\test_sync_run_to_business_tables_script.py -q
```

Expected: fail because script is missing.

- [ ] **Step 3: Implement script**

Implementation details:
- Import project root via `sys.path.insert`.
- Load configured run store from `load_settings()`.
- Resolve DB path from `XHS_AGENT_RUN_DB_PATH`.
- Support:
  - `--run-id <id>` to sync one run.
  - `--limit <N>` to sync recent runs from store.
  - `--dry-run` to report what would sync.
- Only successful records with state should be synchronized.
- Print JSON summary with `synced`, `skipped`, `errors`, and `dry_run`.

- [ ] **Step 4: Run focused tests**

Run:

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m pytest tests\test_sync_run_to_business_tables_script.py tests\test_business_store.py -q
```

Expected: pass.

### Task 3: Runtime Config Check and Final Verification

**Files:**
- Modify: `scripts/check_runtime_config.py`
- Modify: `tests/test_runtime_config_check.py`
- Modify: `memory/current_progress.md`
- Modify: `memory/project_status_and_roadmap.md`

- [ ] **Step 1: Add runtime config tests**

Assert that sqlite-worker profile reports a PASS when business table writes are enabled with SQLite run store, and a WARN if business table writes are enabled while run store is not SQLite.

- [ ] **Step 2: Implement runtime checks**

Read settings and report:
- `business table schema: foundation`
- `business table writes disabled` when disabled.
- PASS for enabled + SQLite run store.
- WARN for enabled + non-SQLite run store.

- [ ] **Step 3: Run focused regression**

Run:

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m pytest tests\test_api_business_table_sync.py tests\test_sync_run_to_business_tables_script.py tests\test_runtime_config_check.py tests\test_business_store.py tests\test_foundation_database_schema.py -q
```

Expected: pass.

- [ ] **Step 4: Compile changed modules**

Run:

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m compileall app\api.py app\config.py app\business_store.py app\database_schema.py scripts\sync_run_to_business_tables.py scripts\check_runtime_config.py
```

Expected: exit code 0.

- [ ] **Step 5: Full regression**

Run:

```powershell
$env:PYTEST_DEBUG_TEMPROOT='data\pytest_tmp_full_verify'
D:\Anaconda\envs\ContentShare\python.exe -m pytest -q
```

Expected: full suite passes.
