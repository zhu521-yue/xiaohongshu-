from __future__ import annotations

from app import memory_graph


def _record(
    record_id: str,
    *,
    topic: str,
    content_type: str,
    score: int,
    pain: str,
) -> dict:
    return {
        "record_id": record_id,
        "topic": topic,
        "title": f"{topic} 标题",
        "content_type": content_type,
        "content_format": "image_text",
        "pain_points": [{"pain": pain, "evidence": "评论证据", "priority": 1}],
        "performance_data": {"views": score * 10, "likes": score},
        "performance_score": score,
        "review_summary": f"{content_type} 表现复盘",
        "next_action": "继续用新评论验证。",
        "updated_at": f"2026-06-13T10:0{score}:00",
    }


def test_build_memory_graph_extracts_topic_pain_type_and_record_edges() -> None:
    records = [
        _record(
            "op_high",
            topic="小红书新手选题方法",
            content_type="step_tutorial",
            score=30,
            pain="不知道怎么判断选题是否值得做",
        ),
        _record(
            "op_mid",
            topic="小红书新手选题方法",
            content_type="avoid_mistakes",
            score=12,
            pain="担心选题判断太主观",
        ),
        _record(
            "op_other",
            topic="宝宝湿疹护理",
            content_type="qa_education",
            score=99,
            pain="担心护理方式不靠谱",
        ),
    ]

    graph = memory_graph.build_memory_graph(records, topic="小红书新手选题方法", limit=10)
    node_pairs = {(node["type"], node["label"]) for node in graph["nodes"]}
    edge_pairs = {(edge["source"], edge["target"], edge["relation"]) for edge in graph["edges"]}

    assert graph["record_count"] == 2
    assert ("topic", "小红书新手选题方法") in node_pairs
    assert ("pain", "不知道怎么判断选题是否值得做") in node_pairs
    assert ("content_type", "step_tutorial") in node_pairs
    assert ("record", "小红书新手选题方法 标题") in node_pairs
    assert not any(node["label"] == "宝宝湿疹护理" for node in graph["nodes"])
    assert ("record:op_high", "topic:小红书新手选题方法", "about_topic") in edge_pairs
    assert ("record:op_high", "content_type:step_tutorial", "uses_content_type") in edge_pairs
    assert graph["top_records"][0]["record_id"] == "op_high"
    assert graph["recommended_content_types"][0]["content_type"] == "step_tutorial"


def test_query_memory_graph_returns_related_records_and_recall_evidence() -> None:
    records = [
        _record(
            "op_a",
            topic="小红书新手选题方法",
            content_type="step_tutorial",
            score=8,
            pain="不知道从哪里开始选题",
        ),
        _record(
            "op_b",
            topic="小红书选题避坑",
            content_type="avoid_mistakes",
            score=40,
            pain="担心踩坑浪费时间",
        ),
    ]

    result = memory_graph.query_memory_graph(records, topic="选题", limit=5)

    assert result["query"] == "选题"
    assert [record["record_id"] for record in result["related_records"]] == ["op_b", "op_a"]
    assert result["related_pain_points"][0]["pain"] == "担心踩坑浪费时间"
    assert result["recall_evidence"][0]["record_id"] == "op_b"
    assert result["graph"]["record_count"] == 2
