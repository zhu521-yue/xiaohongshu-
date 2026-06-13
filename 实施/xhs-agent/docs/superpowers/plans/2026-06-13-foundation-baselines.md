# 三条基础线一期闭环实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 RAG 前数据质量、硬编码配置治理和 production-lite 部署基线补齐一期可测试闭环。

**Architecture:** 新增 `config/data_quality_rules.json` 作为质量和跨领域污染规则入口；新增 `app/data_quality_gate.py` 生成 `rag_eligibility`，并在洞察节点写入 run state。部署侧新增独立 preflight、SQLite 备份和恢复脚本，继续沿用当前标准库 HTTP、SQLite 和 PowerShell/Python 脚本体系。

**Tech Stack:** Python 3、pytest、SQLite、现有 `app.rules` JSON 配置加载、现有 LangGraph-first 节点和 business table sync。

---

## 文件结构

- Create: `config/data_quality_rules.json`
  - 保存 RAG 入库门槛、analysis report 阈值、跨领域污染规则。
- Modify: `app/rules.py`
  - 新增 `load_data_quality_rules()`。
- Modify: `platforms/analysis_report.py`
  - 从配置读取评论质量阈值、错误惩罚和空样本分数上限。
- Create: `app/data_quality_gate.py`
  - 基于已有 run state 字段计算 `rag_eligibility`。
- Modify: `app/state.py`
  - 增加 `rag_eligibility` 字段。
- Modify: `nodes/insight_node.py`
  - 在 `analysis_report` 生成后写入 `rag_eligibility`。
- Modify: `memory/operation_store.py`
  - 从配置读取健康主题关键词和跨领域污染模式。
- Create: `scripts/check_production_lite_deploy.py`
  - 面向部署前检查，复用 runtime config 思路，输出结构化 JSON。
- Create: `scripts/backup_sqlite_db.py`
  - 生成 timestamp SQLite DB 备份。
- Create: `scripts/restore_sqlite_db.py`
  - 默认 dry-run，`--apply` 时创建 pre-restore 备份并恢复 DB。
- Modify: `docs/m17b-startup-templates.md`
  - 补 production-lite 部署检查、备份和恢复说明。
- Modify: `memory/current_progress.md`
  - 记录本轮完成内容、验证和限制。
- Modify: `memory/project_status_and_roadmap.md`
  - 标记三条基础线一期完成，保留后续限制。

## Task 1: 配置化 analysis report 阈值

**Files:**
- Create: `config/data_quality_rules.json`
- Modify: `app/rules.py`
- Modify: `platforms/analysis_report.py`
- Test: `tests/test_analysis_report_config.py`

- [ ] **Step 1: 写失败测试**

新增 `tests/test_analysis_report_config.py`：

```python
from platforms import analysis_report


def test_analysis_report_uses_configured_comment_quality_thresholds(monkeypatch) -> None:
    monkeypatch.setattr(
        analysis_report,
        "DATA_QUALITY_RULES",
        {
            "analysis_report": {
                "high_quality_min_comments": 10,
                "high_quality_min_evidence": 2,
                "medium_quality_min_comments": 3,
                "medium_quality_min_evidence": 1,
                "comment_fetch_error_penalty": 15,
                "empty_sample_score_cap": 45,
            }
        },
    )

    report = analysis_report.build_analysis_report(
        topic="小红书选题",
        collection_candidates=[{"selected": True, "score": 90, "title": "选题方法"}],
        raw_comments=[{"content": f"评论{i} 怎么开始？"} for i in range(10)],
        comment_insights=[
            {"pain": "不知道怎么开始", "evidence_comments": ["怎么开始？", "第一步是什么？"]}
        ],
        pain_points=[{"pain": "不知道怎么开始"}],
    )

    assert report["comment_quality"]["quality_level"] == "high"
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_analysis_report_config.py -q
```

Expected: FAIL，原因是 `platforms.analysis_report` 还没有 `DATA_QUALITY_RULES` 或仍使用写死阈值。

- [ ] **Step 3: 新增配置文件和规则加载**

新增 `config/data_quality_rules.json`，内容：

```json
{
  "rag_gate": {
    "min_score": 60,
    "min_selected_candidates": 1,
    "min_raw_comments": 5,
    "min_evidence_count": 2,
    "block_on_comment_fetch_errors": false,
    "comment_fetch_error_penalty": 15
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
    "health_topic_keywords": [
      "宝宝",
      "婴儿",
      "孩子",
      "湿疹",
      "热疹",
      "皮疹",
      "疹子",
      "过敏",
      "发烧",
      "高烧",
      "医生",
      "就医",
      "用药",
      "擦药",
      "诊断",
      "母乳"
    ],
    "health_pollution_patterns": [
      "对护理方法存在疑问",
      "护理方向",
      "宝宝湿疹",
      "湿疹",
      "热疹",
      "皮疹",
      "疹子",
      "擦药",
      "用药",
      "就医",
      "诊断",
      "不替代专业诊断"
    ]
  }
}
```

在 `app/rules.py` 增加：

```python
@lru_cache(maxsize=None)
def load_data_quality_rules() -> dict[str, Any]:
    return _read_json_config("data_quality_rules.json")
```

- [ ] **Step 4: 改造 analysis_report 读取阈值**

在 `platforms/analysis_report.py` 顶部导入：

```python
from app.rules import load_data_quality_rules


DATA_QUALITY_RULES = load_data_quality_rules()
```

新增 helper：

```python
def _analysis_rules() -> dict[str, Any]:
    rules = DATA_QUALITY_RULES.get("analysis_report")
    return rules if isinstance(rules, dict) else {}
```

修改 `_comment_quality_level()` 从 `_analysis_rules()` 读取 `high_quality_min_comments`、`high_quality_min_evidence`、`medium_quality_min_comments`、`medium_quality_min_evidence`。

修改 `_confidence_score()` 使用 `comment_fetch_error_penalty` 和 `empty_sample_score_cap`。

- [ ] **Step 5: 运行定点测试和既有分析报告测试**

Run:

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_analysis_report_config.py tests/test_analysis_report.py tests/test_analysis_report_integration.py tests/test_check_collector_output.py -q
```

Expected: PASS。

## Task 2: 新增 RAG 入库质量门槛

**Files:**
- Create: `app/data_quality_gate.py`
- Modify: `app/state.py`
- Modify: `nodes/insight_node.py`
- Test: `tests/test_data_quality_gate.py`
- Test: `tests/test_analysis_report_integration.py`

- [ ] **Step 1: 写失败测试**

新增 `tests/test_data_quality_gate.py`：

```python
from app.data_quality_gate import evaluate_rag_eligibility


def _state(**overrides):
    base = {
        "analysis_report": {
            "sample_selection": {"candidate_count": 3, "selected_count": 1},
            "comment_quality": {
                "raw_comments_count": 8,
                "evidence_count": 3,
                "quality_level": "medium",
            },
            "pain_point_confidence": {"score": 72, "level": "high"},
            "risks": [],
        },
        "collection_candidates": [{"selected": True, "score": 90}],
        "raw_comments": [{"content": "怎么开始？"} for _ in range(8)],
        "comment_insights": [{"pain": "不知道怎么开始", "evidence_comments": ["怎么开始？", "第一步？"]}],
        "pain_points": [{"pain": "不知道怎么开始"}],
        "comment_fetch_errors": [],
    }
    base.update(overrides)
    return base


def test_rag_gate_marks_high_confidence_run_eligible() -> None:
    result = evaluate_rag_eligibility(_state())
    assert result["eligible"] is True
    assert result["level"] == "eligible"
    assert result["blocking_reasons"] == []


def test_rag_gate_blocks_missing_comments_and_evidence() -> None:
    result = evaluate_rag_eligibility(
        _state(
            raw_comments=[],
            comment_insights=[],
            analysis_report={
                "sample_selection": {"candidate_count": 1, "selected_count": 1},
                "comment_quality": {"raw_comments_count": 0, "evidence_count": 0},
                "pain_point_confidence": {"score": 35, "level": "low"},
            },
        )
    )
    assert result["eligible"] is False
    assert result["level"] == "blocked"
    assert "评论样本较少" in result["blocking_reasons"]
    assert "痛点证据不足" in result["blocking_reasons"]


def test_rag_gate_penalizes_comment_fetch_errors() -> None:
    result = evaluate_rag_eligibility(
        _state(comment_fetch_errors=[{"note_title": "样本", "error": "cookie expired"}])
    )
    assert result["score"] < 72
    assert "部分评论抓取失败" in result["reasons"]
```

扩展 `tests/test_analysis_report_integration.py`：

```python
def test_insight_node_adds_rag_eligibility(monkeypatch) -> None:
    from nodes import insight_node

    monkeypatch.setattr(
        insight_node,
        "collect_topic_insights",
        lambda topic, limit: {
            "collection_candidates": [{"selected": True, "score": 90, "title": "选题方法"}],
            "raw_notes": [{"title": "选题方法"}],
            "raw_comments": [{"content": "怎么开始？"} for _ in range(6)],
            "comment_insights": [
                {"pain": "不知道怎么开始", "evidence_comments": ["怎么开始？", "第一步？"]}
            ],
            "pain_points": [{"pain": "不知道怎么开始"}],
            "comment_fetch_errors": [],
        },
    )

    result = insight_node.analyze_topic_and_pain_points(
        {"user_topic": "小红书选题", "collect_limit": 3}
    )

    assert "rag_eligibility" in result
    assert "eligible" in result["rag_eligibility"]
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_data_quality_gate.py tests/test_analysis_report_integration.py -q
```

Expected: FAIL，原因是 `app.data_quality_gate` 和 `rag_eligibility` 集成尚不存在。

- [ ] **Step 3: 实现 `app/data_quality_gate.py`**

创建 `app/data_quality_gate.py`：

```python
from __future__ import annotations

from typing import Any

from app.rules import load_data_quality_rules


def _to_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _rag_rules() -> dict[str, Any]:
    rules = load_data_quality_rules().get("rag_gate")
    return rules if isinstance(rules, dict) else {}


def evaluate_rag_eligibility(state: dict[str, Any]) -> dict[str, Any]:
    rules = _rag_rules()
    analysis_report = _dict(state.get("analysis_report"))
    sample_selection = _dict(analysis_report.get("sample_selection"))
    comment_quality = _dict(analysis_report.get("comment_quality"))
    confidence = _dict(analysis_report.get("pain_point_confidence"))

    selected_count = _to_int(sample_selection.get("selected_count"))
    if selected_count <= 0:
        selected_count = sum(1 for item in _list(state.get("collection_candidates")) if isinstance(item, dict) and item.get("selected"))

    raw_comments_count = _to_int(comment_quality.get("raw_comments_count")) or len(_list(state.get("raw_comments")))
    evidence_count = _to_int(comment_quality.get("evidence_count"))
    if evidence_count <= 0:
        for insight in _list(state.get("comment_insights")):
            if isinstance(insight, dict):
                evidence_count += len(_list(insight.get("evidence_comments"))) or _to_int(insight.get("evidence_count"))

    base_score = _to_int(confidence.get("score"))
    comment_errors = _list(state.get("comment_fetch_errors"))
    penalty = _to_int(rules.get("comment_fetch_error_penalty"))
    score = max(0, min(100, base_score - (penalty if comment_errors else 0)))

    blocking: list[str] = []
    reasons: list[str] = []

    if selected_count < _to_int(rules.get("min_selected_candidates")):
        blocking.append("入选候选不足")
    else:
        reasons.append("已有入选候选")
    if raw_comments_count < _to_int(rules.get("min_raw_comments")):
        blocking.append("评论样本较少")
    else:
        reasons.append("评论样本达到最低要求")
    if evidence_count < _to_int(rules.get("min_evidence_count")):
        blocking.append("痛点证据不足")
    else:
        reasons.append("痛点证据达到最低要求")
    if score < _to_int(rules.get("min_score")):
        blocking.append("痛点可信度分数不足")
    if comment_errors:
        reasons.append("部分评论抓取失败")
        if bool(rules.get("block_on_comment_fetch_errors")):
            blocking.append("评论抓取失败")

    eligible = not blocking
    level = "eligible" if eligible else "blocked"
    action = "可以进入后续 RAG 入库候选。" if eligible else "重新采集更多候选和评论后再进入 RAG 入库。"

    return {
        "eligible": eligible,
        "level": level,
        "score": score,
        "reasons": reasons,
        "blocking_reasons": blocking,
        "recommended_action": action,
    }
```

- [ ] **Step 4: 集成到 state 和 insight node**

在 `app/state.py` 的数据分析字段增加：

```python
rag_eligibility: Dict[str, Any]
```

在 `nodes/insight_node.py` 导入：

```python
from app.data_quality_gate import evaluate_rag_eligibility
```

在 `analysis_report` 生成后增加：

```python
result["rag_eligibility"] = evaluate_rag_eligibility(result)
```

- [ ] **Step 5: 运行定点测试**

Run:

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_data_quality_gate.py tests/test_analysis_report_integration.py -q
```

Expected: PASS。

## Task 3: 配置化 operation memory 跨领域污染规则

**Files:**
- Modify: `memory/operation_store.py`
- Test: `tests/test_operation_memory_config.py`

- [ ] **Step 1: 写失败测试**

新增 `tests/test_operation_memory_config.py`：

```python
from memory import operation_store


def test_cross_domain_health_pollution_rules_load_from_config(monkeypatch) -> None:
    monkeypatch.setattr(
        operation_store,
        "DATA_QUALITY_RULES",
        {
            "cross_domain_pollution": {
                "health_topic_keywords": ["测试健康主题"],
                "health_pollution_patterns": ["测试污染词"],
            }
        },
    )

    record = {
        "topic": "旧主题",
        "title": "测试污染词",
        "pain_points": [],
    }

    assert operation_store._record_has_cross_domain_health_pollution("小红书选题", record) is True
    assert operation_store._record_has_cross_domain_health_pollution("测试健康主题", record) is False
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_operation_memory_config.py -q
```

Expected: FAIL，原因是 `operation_store` 仍使用模块内硬编码元组。

- [ ] **Step 3: 改造 `memory/operation_store.py`**

新增导入：

```python
from app.rules import load_data_quality_rules, load_performance_weights
```

新增模块变量：

```python
DATA_QUALITY_RULES = load_data_quality_rules()
```

替换硬编码元组读取方式：

```python
def _cross_domain_rules() -> dict[str, Any]:
    rules = DATA_QUALITY_RULES.get("cross_domain_pollution")
    return rules if isinstance(rules, dict) else {}


def _health_topic_keywords() -> tuple[str, ...]:
    return tuple(str(item) for item in _cross_domain_rules().get("health_topic_keywords") or [])


def _health_pollution_patterns() -> tuple[str, ...]:
    return tuple(str(item) for item in _cross_domain_rules().get("health_pollution_patterns") or [])
```

修改 `_topic_is_health_related()` 使用 `_health_topic_keywords()`。

修改 `_record_has_cross_domain_health_pollution()` 使用 `_health_pollution_patterns()`。

删除 `HEALTH_TOPIC_KEYWORDS` 和 `CROSS_DOMAIN_HEALTH_PATTERNS` 常量。

- [ ] **Step 4: 运行定点和相关回归**

Run:

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_operation_memory_config.py tests/test_operation_store_sqlite.py tests/test_memory_graph.py tests/test_memory_node.py -q
```

Expected: PASS。

## Task 4: production-lite 部署检查脚本

**Files:**
- Create: `scripts/check_production_lite_deploy.py`
- Test: `tests/test_production_lite_deploy_check.py`

- [ ] **Step 1: 写失败测试**

新增 `tests/test_production_lite_deploy_check.py`：

```python
from scripts import check_production_lite_deploy as deploy_check


def test_deploy_check_fails_without_api_token(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv("XHS_AGENT_API_TOKEN", raising=False)
    monkeypatch.setenv("XHS_AGENT_LOG_DIR", str(tmp_path / "logs"))
    monkeypatch.setenv("XHS_AGENT_RUN_STORE", "sqlite")
    monkeypatch.setenv("XHS_AGENT_RUN_QUEUE", "sqlite")
    monkeypatch.setenv("XHS_AGENT_MEMORY_STORE", "sqlite")
    monkeypatch.setenv("XHS_AGENT_DB_SCHEMA", "foundation")
    monkeypatch.setenv("XHS_AGENT_BUSINESS_TABLES_ENABLED", "true")
    monkeypatch.setenv("XHS_AGENT_RUN_DB_PATH", str(tmp_path / "xhs.sqlite3"))
    monkeypatch.setenv("XHS_AGENT_QUEUE_DB_PATH", str(tmp_path / "xhs.sqlite3"))
    monkeypatch.setenv("XHS_AGENT_MEMORY_DB_PATH", str(tmp_path / "xhs.sqlite3"))

    result = deploy_check.check_deployment(backup_dir=tmp_path / "backups")

    assert result["ok"] is False
    assert any(item["level"] == "FAIL" and "API token" in item["message"] for item in result["checks"])


def test_deploy_check_passes_sqlite_baseline(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "xhs.sqlite3"
    monkeypatch.setenv("XHS_AGENT_API_TOKEN", "secret-token")
    monkeypatch.setenv("XHS_AGENT_LOG_DIR", str(tmp_path / "logs"))
    monkeypatch.setenv("XHS_AGENT_RUN_STORE", "sqlite")
    monkeypatch.setenv("XHS_AGENT_RUN_QUEUE", "sqlite")
    monkeypatch.setenv("XHS_AGENT_MEMORY_STORE", "sqlite")
    monkeypatch.setenv("XHS_AGENT_DB_SCHEMA", "foundation")
    monkeypatch.setenv("XHS_AGENT_BUSINESS_TABLES_ENABLED", "true")
    monkeypatch.setenv("XHS_AGENT_RUN_DB_PATH", str(db_path))
    monkeypatch.setenv("XHS_AGENT_QUEUE_DB_PATH", str(db_path))
    monkeypatch.setenv("XHS_AGENT_MEMORY_DB_PATH", str(db_path))
    monkeypatch.setenv("LLM_API_KEY", "llm-key")
    monkeypatch.setenv("XHS_COOKIES_PC", "cookie-value")

    result = deploy_check.check_deployment(backup_dir=tmp_path / "backups")

    assert result["ok"] is True
    assert (tmp_path / "backups").exists()
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_production_lite_deploy_check.py -q
```

Expected: FAIL，原因是脚本不存在。

- [ ] **Step 3: 实现部署检查脚本**

创建 `scripts/check_production_lite_deploy.py`，提供：

```python
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
    probe: Path | None = None
    try:
        path.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path, prefix=".deploy_check.", delete=False) as handle:
            probe = Path(handle.name)
            handle.write("ok")
        return _check("PASS", f"{label} writable")
    except OSError as exc:
        return _check("FAIL", f"{label} not writable: {exc}")
    finally:
        if probe is not None:
            probe.unlink(missing_ok=True)


def check_deployment(backup_dir: str | Path = "data/backups") -> dict[str, Any]:
    settings = load_settings()
    checks: list[dict[str, str]] = []
    checks.append(_check("PASS", "core settings loaded"))
    checks.append(_check("PASS" if settings.api_token else "FAIL", "API token set" if settings.api_token else "API token missing"))
    checks.append(_check("PASS" if settings.run_store_backend == "sqlite" else "FAIL", f"run store backend: {settings.run_store_backend}"))
    checks.append(_check("PASS" if settings.run_queue_backend == "sqlite" else "FAIL", f"run queue backend: {settings.run_queue_backend}"))
    checks.append(_check("PASS" if settings.memory_store_backend == "sqlite" else "FAIL", f"memory store backend: {settings.memory_store_backend}"))
    checks.append(_check("PASS" if settings.db_schema == "foundation" else "FAIL", f"db schema: {settings.db_schema}"))
    checks.append(_check("PASS" if settings.business_tables_enabled else "FAIL", "business table writes enabled" if settings.business_tables_enabled else "business table writes disabled"))
    checks.append(_writable_dir("log_dir", settings.log_dir))
    checks.append(_writable_dir("run_db_parent", _resolve(settings.run_db_path).parent))
    checks.append(_writable_dir("backup_dir", backup_dir))
    checks.append(_check("PASS" if settings.llm_api_key else "WARN", "LLM_API_KEY set" if settings.llm_api_key else "LLM_API_KEY missing"))
    checks.append(_check("PASS" if os.getenv("XHS_COOKIES_PC") else "WARN", "XHS_COOKIES_PC set" if os.getenv("XHS_COOKIES_PC") else "XHS_COOKIES_PC missing"))
    return {"ok": not any(item["level"] == "FAIL" for item in checks), "checks": checks}


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
```

- [ ] **Step 4: 运行定点测试**

Run:

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_production_lite_deploy_check.py -q
```

Expected: PASS。

## Task 5: SQLite 备份和恢复脚本

**Files:**
- Create: `scripts/backup_sqlite_db.py`
- Create: `scripts/restore_sqlite_db.py`
- Test: `tests/test_sqlite_backup_restore_scripts.py`

- [ ] **Step 1: 写失败测试**

新增 `tests/test_sqlite_backup_restore_scripts.py`：

```python
import sqlite3
from pathlib import Path

from scripts import backup_sqlite_db, restore_sqlite_db


def _make_db(path: Path, value: str) -> None:
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE IF NOT EXISTS sample (value TEXT)")
        connection.execute("DELETE FROM sample")
        connection.execute("INSERT INTO sample (value) VALUES (?)", (value,))


def _read_value(path: Path) -> str:
    with sqlite3.connect(path) as connection:
        return connection.execute("SELECT value FROM sample").fetchone()[0]


def test_backup_creates_timestamped_copy(tmp_path: Path) -> None:
    db_path = tmp_path / "xhs.sqlite3"
    backup_dir = tmp_path / "backups"
    _make_db(db_path, "original")

    result = backup_sqlite_db.backup_database(db_path=db_path, backup_dir=backup_dir, timestamp="20260613_200000")

    assert result["ok"] is True
    backup_path = Path(result["backup_path"])
    assert backup_path.exists()
    assert backup_path.name == "xhs_20260613_200000.sqlite3"
    assert _read_value(backup_path) == "original"


def test_restore_dry_run_does_not_modify_target(tmp_path: Path) -> None:
    target = tmp_path / "xhs.sqlite3"
    backup = tmp_path / "backup.sqlite3"
    _make_db(target, "target")
    _make_db(backup, "backup")

    result = restore_sqlite_db.restore_database(target_db_path=target, backup_path=backup, apply=False)

    assert result["ok"] is True
    assert result["applied"] is False
    assert _read_value(target) == "target"


def test_restore_apply_creates_pre_restore_backup_and_replaces_db(tmp_path: Path) -> None:
    target = tmp_path / "xhs.sqlite3"
    backup = tmp_path / "backup.sqlite3"
    pre_restore_dir = tmp_path / "pre_restore"
    _make_db(target, "target")
    _make_db(backup, "backup")

    result = restore_sqlite_db.restore_database(
        target_db_path=target,
        backup_path=backup,
        pre_restore_dir=pre_restore_dir,
        timestamp="20260613_200001",
        apply=True,
    )

    assert result["ok"] is True
    assert result["applied"] is True
    assert Path(result["pre_restore_backup_path"]).exists()
    assert _read_value(target) == "backup"
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_sqlite_backup_restore_scripts.py -q
```

Expected: FAIL，原因是脚本不存在。

- [ ] **Step 3: 实现备份脚本**

创建 `scripts/backup_sqlite_db.py`，核心函数：

```python
def backup_database(db_path: str | Path, backup_dir: str | Path = "data/backups", timestamp: str | None = None) -> dict[str, Any]:
    source = _resolve(db_path)
    if not source.exists():
        return {"ok": False, "error": f"database not found: {source}"}
    stamp = timestamp or datetime.now().strftime("%Y%m%d_%H%M%S")
    target_dir = _resolve(backup_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    stem = source.stem
    suffix = source.suffix or ".sqlite3"
    target = target_dir / f"{stem}_{stamp}{suffix}"
    if target.exists():
        return {"ok": False, "error": f"backup already exists: {target}"}
    shutil.copy2(source, target)
    return {"ok": True, "source_path": str(source), "backup_path": str(target)}
```

并提供 `build_parser()` 和 `main()`，输出 JSON。

- [ ] **Step 4: 实现恢复脚本**

创建 `scripts/restore_sqlite_db.py`，核心函数：

```python
def restore_database(
    target_db_path: str | Path,
    backup_path: str | Path,
    pre_restore_dir: str | Path = "data/backups",
    timestamp: str | None = None,
    apply: bool = False,
) -> dict[str, Any]:
    target = _resolve(target_db_path)
    backup = _resolve(backup_path)
    if not backup.exists():
        return {"ok": False, "error": f"backup not found: {backup}"}
    if not apply:
        return {"ok": True, "applied": False, "target_path": str(target), "backup_path": str(backup)}
    stamp = timestamp or datetime.now().strftime("%Y%m%d_%H%M%S")
    pre_dir = _resolve(pre_restore_dir)
    pre_dir.mkdir(parents=True, exist_ok=True)
    pre_restore = pre_dir / f"{target.stem}_pre_restore_{stamp}{target.suffix or '.sqlite3'}"
    if target.exists():
        shutil.copy2(target, pre_restore)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(backup, target)
    return {
        "ok": True,
        "applied": True,
        "target_path": str(target),
        "backup_path": str(backup),
        "pre_restore_backup_path": str(pre_restore) if target.exists() else None,
    }
```

并提供 `build_parser()` 和 `main()`，默认不应用恢复，必须传 `--apply`。

- [ ] **Step 5: 运行定点测试**

Run:

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_sqlite_backup_restore_scripts.py -q
```

Expected: PASS。

## Task 6: 文档和进度更新

**Files:**
- Modify: `docs/m17b-startup-templates.md`
- Modify: `memory/current_progress.md`
- Modify: `memory/project_status_and_roadmap.md`

- [ ] **Step 1: 更新启动文档**

在 `docs/m17b-startup-templates.md` 的 Production-Lite Preflight 后补充：

```markdown
## Production-Lite Deploy Checklist

Run the deployment-focused preflight before a server-facing single-machine deployment:

```powershell
& $python .\scripts\check_production_lite_deploy.py --backup-dir data/backups
```

The check fails when API token, SQLite store/queue/memory, foundation schema, business table writes, log directory, DB directory, or backup directory are not ready. Missing real LLM key or Spider_XHS cookie is reported as a warning.

Back up the SQLite database:

```powershell
& $python .\scripts\backup_sqlite_db.py --db-path data/xhs_agent.sqlite3 --backup-dir data/backups
```

Dry-run restore:

```powershell
& $python .\scripts\restore_sqlite_db.py --target-db-path data/xhs_agent.sqlite3 --backup-path data/backups/<backup-file>.sqlite3
```

Apply restore:

```powershell
& $python .\scripts\restore_sqlite_db.py --target-db-path data/xhs_agent.sqlite3 --backup-path data/backups/<backup-file>.sqlite3 --apply
```
```

- [ ] **Step 2: 更新进度文档**

在 `memory/current_progress.md` 顶部新增中文小节，记录：

- 数据质量门槛初版完成。
- 数据分析阈值和 operation memory 健康污染规则已配置化。
- production-lite deploy check、SQLite backup、SQLite restore 初版完成。
- 验证命令和结果。
- 仍未完成完整 RAG、历史大迁移、HTTPS/反向代理/进程守护/用户体系。

- [ ] **Step 3: 更新路线图**

在 `memory/project_status_and_roadmap.md` 追加小节，标记：

- “RAG 前数据质量门槛”从未完成调整为初版完成。
- “硬编码治理”从部分完成推进到关键业务规则继续配置化。
- “部署基线”从启动模板推进到 deploy preflight + backup/restore 初版。
- 正式公网生产部署仍未完成。

## Task 7: 最终验证

**Files:**
- No new files.

- [ ] **Step 1: 运行新增定点测试**

Run:

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_analysis_report_config.py tests/test_data_quality_gate.py tests/test_operation_memory_config.py tests/test_production_lite_deploy_check.py tests/test_sqlite_backup_restore_scripts.py -q
```

Expected: PASS。

- [ ] **Step 2: 运行相关回归**

Run:

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_analysis_report.py tests/test_analysis_report_integration.py tests/test_check_collector_output.py tests/test_operation_store_sqlite.py tests/test_memory_graph.py tests/test_memory_node.py tests/test_business_store.py tests/test_api_business_table_sync.py -q
```

Expected: PASS。

- [ ] **Step 3: 运行编译检查**

Run:

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m compileall app nodes memory platforms scripts tests
```

Expected: exit code 0。

- [ ] **Step 4: 运行 production-lite deploy check 的真实命令**

Run:

```powershell
D:\Anaconda\envs\ContentShare\python.exe .\scripts\check_production_lite_deploy.py --backup-dir data/backups
```

Expected: 当前本地环境可能因为 API token、SQLite 模式或真实 key/cookie 设置不同返回 FAIL/WARN。记录实际结果，不把 FAIL 说成通过。

- [ ] **Step 5: 检查 git diff**

Run:

```powershell
git diff --stat
git status --short
```

Expected: 只包含本轮相关文件和用户既有的 `AGENTS.md` 修改；不要暂存或提交 `AGENTS.md`，除非用户另行要求。

## Self-Review Checklist

- Spec 覆盖：数据质量、配置治理、部署基线均有独立任务。
- TDD 覆盖：每个代码任务都有先失败测试。
- 敏感信息：脚本只检查存在性，不输出 `.env` 明文。
- 范围控制：不引入向量库、Docker、Nginx、systemd、Redis 或真实平台新增写入。
- 集成边界：`memory_graph` 保持只读，`rag_eligibility` 只是入库资格结果，不是真正 RAG 入库。
