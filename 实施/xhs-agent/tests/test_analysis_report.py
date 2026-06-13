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
            _insight(
                "用户不知道从哪里开始",
                ["怎么开始？", "第一步做什么？", "有没有步骤？", "方法是什么？", "从哪里开始？"],
            )
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
