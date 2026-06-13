# Basic Analysis Report Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a deterministic `analysis_report` to collection/run insights so each run explains sample selection, comment quality, pain point confidence, content structure hints, and risks.

**Architecture:** Create a focused `platforms/analysis_report.py` module that reads already-sanitized collection data and returns a pure dict. Wire that dict through `nodes/insight_node.py`, `app/state.py`, `app/api.py`, and `scripts/check_collector.py` without changing collector ranking, database storage, or platform write behavior.

**Tech Stack:** Python 3, pytest, existing XHS agent modules, deterministic rule-based scoring.

---

### Task 1: Analysis Report Core

**Files:**
- Create: `platforms/analysis_report.py`
- Test: `tests/test_analysis_report.py`

- [ ] **Step 1: Write failing core tests**

Add `tests/test_analysis_report.py` with tests for high-quality reports, low evidence risk, fetch-error downgrade, and content structure hints:

```python
from platforms.analysis_report import build_analysis_report


def _candidate(title: str, *, score: int = 100, selected: bool = True) -> dict:
    return {
        "title": title,
        "score": score,
        "selected": selected,
        "rank": 1,
        "reasons": ["主题相关", "评论较多"],
    }


def _insight(pain: str, evidence: list[str]) -> dict:
    return {
        "pain": pain,
        "evidence_comments": evidence,
        "evidence_count": len(evidence),
        "priority": 1,
    }


def test_analysis_report_summarizes_high_quality_collection() -> None:
    report = build_analysis_report(
        topic="小红书新手选题方法",
        collection_candidates=[
            _candidate("新手选题避坑指南", score=142),
            _candidate("小红书选题步骤", score=118),
            _candidate("泛流量变现", score=30, selected=False),
        ],
        raw_notes=[{"title": "新手选题避坑指南"}],
        raw_comments=[{"content": f"评论{i} 不知道怎么判断选题？"} for i in range(20)],
        comment_insights=[
            _insight(
                "用户不知道怎么判断选题是否值得做",
                [
                    "新手不知道怎么判断选题？",
                    "怎么判断这个选题能不能做？",
                    "怕选题方向一开始就错了",
                    "有没有判断选题的方法？",
                    "选题避坑到底看什么？",
                ],
            )
        ],
        pain_points=[{"pain": "用户不知道怎么判断选题是否值得做"}],
        comment_fetch_errors=[],
    )

    assert report["sample_selection"]["candidate_count"] == 3
    assert report["sample_selection"]["selected_count"] == 2
    assert report["sample_selection"]["top_score"] == 142
    assert report["sample_selection"]["selected_titles"] == ["新手选题避坑指南", "小红书选题步骤"]
    assert report["comment_quality"]["quality_level"] == "high"
    assert report["comment_quality"]["evidence_count"] == 5
    assert report["pain_point_confidence"]["level"] == "high"
    assert report["content_structure_hint"]["recommended_type"] == "avoid_mistakes"
    assert report["risks"] == []


def test_analysis_report_flags_low_comment_evidence() -> None:
    report = build_analysis_report(
        topic="小红书新手选题方法",
        collection_candidates=[_candidate("新手选题方法", score=80)],
        raw_notes=[{"title": "新手选题方法"}],
        raw_comments=[{"content": "蹲"}],
        comment_insights=[],
        pain_points=[],
        comment_fetch_errors=[],
    )

    assert report["comment_quality"]["quality_level"] == "low"
    assert report["pain_point_confidence"]["level"] == "low"
    assert "评论样本较少" in report["risks"]
    assert "痛点证据不足" in report["risks"]


def test_analysis_report_downgrades_when_comment_fetch_errors_exist() -> None:
    report = build_analysis_report(
        topic="小红书新手选题方法",
        collection_candidates=[_candidate("新手选题步骤", score=120)],
        raw_notes=[{"title": "新手选题步骤"}],
        raw_comments=[{"content": f"评论{i} 怎么开始？"} for i in range(30)],
        comment_insights=[
            _insight("用户不知道从哪里开始", ["怎么开始？", "第一步做什么？", "有没有步骤？", "方法是什么？", "从哪里开始？"])
        ],
        pain_points=[{"pain": "用户不知道从哪里开始"}],
        comment_fetch_errors=[{"note_title": "新手选题步骤", "error": "cookie expired"}],
    )

    assert report["comment_quality"]["quality_level"] == "medium"
    assert report["pain_point_confidence"]["level"] in {"medium", "high"}
    assert "部分评论抓取失败" in report["risks"]


def test_analysis_report_recommends_qa_for_question_heavy_evidence() -> None:
    report = build_analysis_report(
        topic="小红书账号定位",
        collection_candidates=[_candidate("账号定位常见问题", score=90)],
        raw_notes=[{"title": "账号定位常见问题"}],
        raw_comments=[{"content": "我适合做什么定位？"}, {"content": "定位要不要垂直？"}],
        comment_insights=[_insight("用户需要判断账号定位", ["我适合做什么定位？", "定位要不要垂直？"])],
        pain_points=[{"pain": "用户需要判断账号定位"}],
        comment_fetch_errors=[],
    )

    assert report["content_structure_hint"]["recommended_type"] == "qa_education"
```

- [ ] **Step 2: Verify RED**

Run:

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m pytest tests\test_analysis_report.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'platforms.analysis_report'`.

- [ ] **Step 3: Implement core report builder**

Create `platforms/analysis_report.py` with a pure `build_analysis_report(...) -> dict` function. It should count candidates, selected candidates, comments, evidence comments, pain points, fetch errors, compute quality/confidence levels, content hint, risks, and summary exactly as described in the design spec.

- [ ] **Step 4: Verify GREEN**

Run:

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m pytest tests\test_analysis_report.py -q
```

Expected: PASS.

### Task 2: Pipeline and API Wiring

**Files:**
- Modify: `app/state.py`
- Modify: `nodes/insight_node.py`
- Modify: `app/api.py`
- Test: `tests/test_analysis_report_integration.py`

- [ ] **Step 1: Write failing integration tests**

Add `tests/test_analysis_report_integration.py` with tests that monkeypatch collection, call the insight node, and verify API payload passthrough:

```python
from app.api import _insight_payload
from nodes import insight_node


def test_insight_node_adds_analysis_report_on_success(monkeypatch) -> None:
    monkeypatch.setattr(
        insight_node,
        "collect_topic_insights",
        lambda topic, limit=5: {
            "raw_notes": [{"title": "新手选题避坑指南"}],
            "collection_candidates": [
                {"title": "新手选题避坑指南", "score": 120, "selected": True, "rank": 1}
            ],
            "raw_comments": [{"content": "不知道怎么判断选题？"} for _ in range(6)],
            "cleaned_notes": [],
            "top_subtopics": [],
            "comment_insights": [
                {
                    "pain": "用户不知道怎么判断选题",
                    "evidence_comments": ["不知道怎么判断选题？", "选题怎么避坑？"],
                    "evidence_count": 2,
                    "priority": 1,
                }
            ],
            "pain_points": [{"pain": "用户不知道怎么判断选题"}],
            "comment_fetch_errors": [],
        },
    )

    result = insight_node.analyze_topic_and_pain_points(
        {"user_topic": "小红书新手选题方法", "collect_limit": 1}
    )

    assert result["analysis_report"]["sample_selection"]["selected_count"] == 1
    assert result["analysis_report"]["comment_quality"]["quality_level"] == "medium"


def test_insight_node_adds_low_confidence_report_on_collection_failure(monkeypatch) -> None:
    def fail_collect(topic, limit=5):
        raise RuntimeError("collector unavailable")

    monkeypatch.setattr(insight_node, "collect_topic_insights", fail_collect)

    result = insight_node.analyze_topic_and_pain_points(
        {"user_topic": "小红书新手选题方法", "collect_limit": 1}
    )

    report = result["analysis_report"]
    assert report["comment_quality"]["quality_level"] == "low"
    assert report["pain_point_confidence"]["level"] == "low"
    assert "部分评论抓取失败" in report["risks"]


def test_insight_payload_exposes_analysis_report() -> None:
    state = {
        "collection_candidates": [],
        "comment_insights": [],
        "pain_points": [],
        "comment_fetch_errors": [],
        "analysis_report": {"summary": "样本质量中等"},
    }

    payload = _insight_payload(state)

    assert payload["analysis_report"] == {"summary": "样本质量中等"}
```

- [ ] **Step 2: Verify RED**

Run:

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m pytest tests\test_analysis_report_integration.py -q
```

Expected: FAIL because `analysis_report` is not yet wired through the node/API payload.

- [ ] **Step 3: Wire the report**

Modify:
- `app/state.py`: add `analysis_report: Dict[str, Any]`.
- `nodes/insight_node.py`: import `build_analysis_report`; after collection success or failure, attach `analysis_report`.
- `app/api.py`: include `analysis_report` in `_insight_payload()`.

- [ ] **Step 4: Verify GREEN**

Run:

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m pytest tests\test_analysis_report_integration.py -q
```

Expected: PASS.

### Task 3: Diagnostic Script Output

**Files:**
- Modify: `scripts/check_collector.py`
- Test: `tests/test_check_collector_output.py`

- [ ] **Step 1: Extend failing script-output test**

Update `tests/test_check_collector_output.py` to assert the script output can contain `analysis_report` when printing collector diagnostics.

- [ ] **Step 2: Verify RED**

Run:

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m pytest tests\test_check_collector_output.py -q
```

Expected: FAIL until `scripts/check_collector.py` includes `analysis_report` in the final payload.

- [ ] **Step 3: Add script report output**

Modify `scripts/check_collector.py` to import `build_analysis_report` and include `analysis_report` in the final JSON payload built from candidates, raw comments, insights, pain points, and fetch errors.

- [ ] **Step 4: Verify GREEN**

Run:

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m pytest tests\test_check_collector_output.py -q
```

Expected: PASS.

### Task 4: Regression, Docs, and Memory

**Files:**
- Modify: `memory/current_progress.md`
- Modify: `memory/project_status_and_roadmap.md`

- [ ] **Step 1: Run focused regression**

Run:

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m pytest tests\test_analysis_report.py tests\test_analysis_report_integration.py tests\test_check_collector_output.py tests\test_collector_candidate_scoring.py -q
```

Expected: PASS.

- [ ] **Step 2: Run compile check**

Run:

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m compileall platforms\analysis_report.py nodes\insight_node.py app\api.py app\state.py scripts\check_collector.py
```

Expected: exit code 0.

- [ ] **Step 3: Run full test suite**

Run:

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m pytest -q
```

Expected: PASS.

- [ ] **Step 4: Update memory**

Append a short completion note to `memory/current_progress.md` and update `memory/project_status_and_roadmap.md` so “基础数据分析报告” is marked as initial implementation complete, with next steps for database schema and comment quality refinement.

- [ ] **Step 5: Final hygiene**

Run:

```powershell
git diff --check
git status --short
```

Expected: `git diff --check` exits 0; `git status --short` shows only intended changes plus pre-existing workspace changes.
