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
        raising=False,
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
