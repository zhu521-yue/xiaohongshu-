from nodes import content_node, video_node


def _state() -> dict:
    return {
        "user_topic": "小红书选题",
        "target_user": "新手博主",
        "content_type": "knowledge_share",
        "pain_points": [{"pain": "不知道第一步怎么做"}],
        "comment_insights": [
            {"pain": "不知道第一步怎么做", "evidence_comments": ["第一步是什么"]}
        ],
        "successful_patterns": [],
        "graphrag_memory": {
            "query": "小红书选题",
            "recommended_content_types": [
                {
                    "content_type": "step_tutorial",
                    "count": 2,
                    "average_score": 82.5,
                    "max_score": 91,
                }
            ],
            "related_pain_points": [
                {"pain": "不知道第一步怎么做", "count": 2, "max_score": 91}
            ],
            "recall_evidence": [
                {
                    "record_id": "op_1",
                    "topic": "小红书选题",
                    "title": "选题第一步",
                    "content_type": "step_tutorial",
                    "performance_score": 91,
                }
            ],
        },
    }


def test_image_text_prompt_includes_memory_context(monkeypatch) -> None:
    captured: dict = {}

    def fake_build_json_prompt(template_name: str, input_payload: dict) -> list:
        captured["template_name"] = template_name
        captured["input_payload"] = input_payload
        return []

    monkeypatch.setattr(content_node, "build_json_prompt", fake_build_json_prompt)

    content_node._build_image_text_prompt(
        state=_state(),
        profile={"content_type": "knowledge_share", "label": "知识分享"},
        content_label="知识分享",
        pain_points=["不知道第一步怎么做"],
        comment_insights=[],
        patterns=[],
        primary_pain="不知道第一步怎么做",
    )

    assert captured["template_name"] == "image_text_generation"
    assert captured["input_payload"]["memory_context"]["enabled"] is True
    assert captured["input_payload"]["memory_context"]["recall_evidence"][0]["record_id"] == "op_1"


def test_video_prompt_includes_memory_context(monkeypatch) -> None:
    captured: dict = {}

    def fake_build_json_prompt(template_name: str, input_payload: dict) -> list:
        captured["template_name"] = template_name
        captured["input_payload"] = input_payload
        return []

    monkeypatch.setattr(video_node, "build_json_prompt", fake_build_json_prompt)

    video_node._build_video_prompt(
        state=_state(),
        profile={"content_type": "knowledge_share", "label": "知识分享"},
        pain_points=["不知道第一步怎么做"],
        comment_insights=[],
        patterns=[],
        primary_pain="不知道第一步怎么做",
    )

    assert captured["template_name"] == "video_script_generation"
    assert captured["input_payload"]["memory_context"]["enabled"] is True
    assert (
        captured["input_payload"]["memory_context"]["recommended_content_types"][0][
            "content_type"
        ]
        == "step_tutorial"
    )


def test_generation_prompt_uses_disabled_memory_context_when_empty(monkeypatch) -> None:
    captured: dict = {}

    def fake_build_json_prompt(template_name: str, input_payload: dict) -> list:
        captured["input_payload"] = input_payload
        return []

    monkeypatch.setattr(content_node, "build_json_prompt", fake_build_json_prompt)

    state = _state()
    state["graphrag_memory"] = {}
    content_node._build_image_text_prompt(
        state=state,
        profile={"content_type": "knowledge_share", "label": "知识分享"},
        content_label="知识分享",
        pain_points=[],
        comment_insights=[],
        patterns=[],
        primary_pain="小红书选题",
    )

    assert captured["input_payload"]["memory_context"] == {
        "enabled": False,
        "query": "",
        "recommended_content_types": [],
        "related_pain_points": [],
        "recall_evidence": [],
    }
