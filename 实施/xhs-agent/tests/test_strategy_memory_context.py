from nodes.strategy_node import decide_content_strategy


def _state(**overrides) -> dict:
    state = {
        "user_topic": "小红书选题",
        "pain_points": [{"pain": "想找到更稳定的选题方向", "evidence": "最近灵感不稳定"}],
        "user_selected_format": "image_text",
        "successful_patterns": [],
        "account_stage": "growth",
        "allow_soft_ad": False,
    }
    state.update(overrides)
    return state


def test_strategy_uses_graphrag_recommended_content_type_when_evidenced() -> None:
    result = decide_content_strategy(
        _state(
            graphrag_memory={
                "recommended_content_types": [
                    {"content_type": "qa_education", "count": 2, "max_score": 88}
                ],
                "recall_evidence": [{"record_id": "op_1"}],
            }
        )
    )

    assert result["content_type"] == "qa_education"


def test_strategy_keyword_rule_still_overrides_graphrag_recommendation() -> None:
    result = decide_content_strategy(
        _state(
            pain_points=[{"pain": "这些坑怎么避开", "evidence": "踩坑了"}],
            graphrag_memory={
                "recommended_content_types": [
                    {"content_type": "qa_education", "count": 2, "max_score": 88}
                ],
                "recall_evidence": [{"record_id": "op_1"}],
            },
        )
    )

    assert result["content_type"] == "avoid_mistakes"


def test_strategy_ignores_graphrag_recommendation_without_evidence() -> None:
    result = decide_content_strategy(
        _state(
            graphrag_memory={
                "recommended_content_types": [
                    {"content_type": "qa_education", "count": 2, "max_score": 88}
                ],
                "recall_evidence": [],
            }
        )
    )

    assert result["content_type"] == "knowledge_share"
