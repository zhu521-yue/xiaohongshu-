from app import api


def test_failure_category_from_text_classifies_known_failures() -> None:
    assert api._failure_category_from_text("creator adapter unavailable") == "creator_publish"
    assert api._failure_category_from_text("image bytes missing") == "creator_publish"
    assert api._failure_category_from_text("LLM JSON parse failed") == "llm_generation"
    assert api._failure_category_from_text("cookie expired while collecting comments") == "collection"
    assert api._failure_category_from_text("compliance risk high") == "compliance"
    assert api._failure_category_from_text("unexpected crash") == "unknown"
    assert api._failure_category_from_text("") is None


def test_run_record_writes_top_level_failure_category() -> None:
    record = api._run_record(
        run_id="run_failed",
        request_payload={
            "topic": "选题方法",
            "target_user": "内容创作新手",
            "format": "image_text",
            "engine": "local",
            "goal": "生成内容",
            "collect_limit": 1,
            "save_collection": False,
            "approve": False,
        },
        status="failed",
        error="LLM JSON parse failed",
    )

    assert record["failure_category"] == "llm_generation"
    assert record["failure_category_label"] == "LLM 生成或解析问题"


def test_state_summary_writes_creator_publish_failure_category() -> None:
    summary = api._state_summary(
        {
            "creator_publish_status": "failed",
            "creator_publish_error": "creator adapter unavailable",
            "compliance_risk_level": "low",
        }
    )

    assert summary["failure_category"] == "creator_publish"
    assert summary["failure_category_label"] == "创作者平台或发布素材问题"


def test_state_summary_writes_compliance_failure_category() -> None:
    summary = api._state_summary(
        {
            "creator_publish_status": "not_requested",
            "compliance_risk_level": "high",
            "compliance_issues": ["compliance risk high"],
        }
    )

    assert summary["failure_category"] == "compliance"
    assert summary["failure_category_label"] == "合规拦截"


def test_decorate_run_record_backfills_failure_category_for_old_records() -> None:
    old_record = {
        "run_id": "run_old_failed",
        "status": "failed",
        "request": {},
        "summary": {},
        "error": "cookie expired while collecting comments",
    }

    decorated = api._decorate_run_record(old_record)

    assert decorated["failure_category"] == "collection"
    assert decorated["failure_category_label"] == "采集或 Cookie 问题"
    assert old_record.get("failure_category") is None
