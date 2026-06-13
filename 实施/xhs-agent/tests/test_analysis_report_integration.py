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
