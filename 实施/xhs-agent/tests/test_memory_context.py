from nodes.memory_context import (
    build_generation_memory_context,
    has_memory_evidence,
    recommended_memory_content_type,
)


def _state(graphrag_memory: dict) -> dict:
    return {"graphrag_memory": graphrag_memory}


def test_recommended_memory_content_type_uses_evidenced_valid_type() -> None:
    result = recommended_memory_content_type(
        _state(
            {
                "recommended_content_types": [
                    {"content_type": "step_tutorial", "count": 2, "max_score": 90}
                ],
                "recall_evidence": [{"record_id": "op_1"}],
            }
        )
    )

    assert result == "step_tutorial"


def test_recommended_memory_content_type_ignores_recommendation_without_evidence() -> None:
    result = recommended_memory_content_type(
        _state(
            {
                "recommended_content_types": [
                    {"content_type": "step_tutorial", "count": 2, "max_score": 90}
                ],
                "recall_evidence": [],
                "related_records": [],
            }
        )
    )

    assert result is None


def test_recommended_memory_content_type_ignores_invalid_type() -> None:
    result = recommended_memory_content_type(
        _state(
            {
                "recommended_content_types": [
                    {"content_type": "unknown_type", "count": 3, "max_score": 95},
                    {"content_type": "qa_education", "count": 1, "max_score": 80},
                ],
                "recall_evidence": [{"record_id": "op_2"}],
            }
        )
    )

    assert result == "qa_education"


def test_generation_memory_context_compacts_and_limits_fields() -> None:
    context = build_generation_memory_context(
        _state(
            {
                "query": "小红书选题",
                "recommended_content_types": [
                    {
                        "content_type": "step_tutorial",
                        "count": 2,
                        "average_score": 81.5,
                        "max_score": 90,
                    }
                ],
                "related_pain_points": [
                    {
                        "pain": "不知道第一步怎么做",
                        "count": 2,
                        "max_score": 90,
                        "record_ids": ["op_1"],
                    }
                ],
                "recall_evidence": [
                    {
                        "record_id": "op_1",
                        "topic": "小红书选题",
                        "title": "选题方法",
                        "content_type": "step_tutorial",
                        "content_format": "image_text",
                        "performance_score": 90,
                        "review_summary": "表现好",
                        "performance_data": {"likes": 100},
                    }
                ],
            }
        ),
        limit=1,
    )

    assert context == {
        "enabled": True,
        "query": "小红书选题",
        "recommended_content_types": [
            {
                "content_type": "step_tutorial",
                "count": 2,
                "average_score": 81.5,
                "max_score": 90,
            }
        ],
        "related_pain_points": [
            {"pain": "不知道第一步怎么做", "count": 2, "max_score": 90}
        ],
        "recall_evidence": [
            {
                "record_id": "op_1",
                "topic": "小红书选题",
                "title": "选题方法",
                "content_type": "step_tutorial",
                "performance_score": 90,
            }
        ],
    }


def test_empty_generation_memory_context_is_disabled() -> None:
    context = build_generation_memory_context({})

    assert context == {
        "enabled": False,
        "query": "",
        "recommended_content_types": [],
        "related_pain_points": [],
        "recall_evidence": [],
    }
    assert has_memory_evidence({}) is False
