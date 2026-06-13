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
