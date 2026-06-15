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


def test_query_memory_graph_returns_cross_topic_similar_experience() -> None:
    records = [
        _record(
            "op_tool",
            topic="自由职业接单避坑",
            content_type="avoid_mistakes",
            score=45,
            pain="担心踩坑浪费时间",
        ),
        _record(
            "op_unrelated",
            topic="宝宝湿疹护理",
            content_type="qa_education",
            score=99,
            pain="担心护理方式不靠谱",
        ),
    ]

    result = memory_graph.query_memory_graph(
        records,
        topic="小红书选题",
        limit=5,
        pain_points=[{"pain": "担心踩坑浪费时间", "evidence": "不知道是否值得继续做"}],
    )

    assert result["similar_experience_records"][0]["record_id"] == "op_tool"
    assert "担心踩坑浪费时间" in result["similar_experience_records"][0]["matched_terms"]
    assert result["similar_experience_records"][0]["reason"]
    assert result["similar_pain_points"][0]["pain"] == "担心踩坑浪费时间"
    assert not any(item["record_id"] == "op_unrelated" for item in result["similar_experience_records"])


def test_query_memory_graph_returns_lightweight_semantic_recall() -> None:
    records = [
        _record(
            "op_semantic",
            topic="新手做内容定位",
            content_type="step_tutorial",
            score=36,
            pain="刚开始做账号没有方向，不知道先服务哪类人群",
        ),
        _record(
            "op_unrelated",
            topic="宝宝湿疹护理",
            content_type="qa_education",
            score=99,
            pain="担心护理方式不靠谱",
        ),
    ]

    result = memory_graph.query_memory_graph(
        records,
        topic="小红书选题",
        limit=5,
        pain_points=[
            {
                "pain": "新账号选题总是很散，定位不清楚，不知道先写给谁看",
                "evidence": "评论说账号方向太乱",
            }
        ],
    )

    semantic = result["semantic_recall_records"][0]
    assert semantic["record_id"] == "op_semantic"
    assert semantic["semantic_score"] > 0
    assert "semantic_recall" in semantic["reason"]
    assert any(
        item["type"] == "semantic_recall" and item["record_id"] == "op_semantic"
        for item in result["recall_explanations"]
    )
    semantic_explanation = next(
        item for item in result["recall_explanations"] if item["type"] == "semantic_recall"
    )
    assert semantic_explanation["embedding_model"] == "local_hashing_embedding_v1"
    assert semantic_explanation["embedding_dimensions"] == 64
    assert semantic_explanation["semantic_score"] == semantic["semantic_score"]
    assert not any(item["record_id"] == "op_unrelated" for item in result["semantic_recall_records"])


def test_query_memory_graph_marks_semantic_recall_as_local_embedding() -> None:
    records = [
        _record(
            "op_embedding",
            topic="新手做内容定位",
            content_type="step_tutorial",
            score=36,
            pain="刚开始做账号没有方向，不知道先服务哪类人群",
        )
    ]

    result = memory_graph.query_memory_graph(
        records,
        topic="小红书选题",
        limit=5,
        pain_points=[
            {
                "pain": "新账号选题总是很散，定位不清楚，不知道先写给谁看",
                "evidence": "评论说账号方向太乱",
            }
        ],
    )

    semantic = result["semantic_recall_records"][0]
    assert semantic["embedding_model"] == "local_hashing_embedding_v1"
    assert semantic["embedding_dimensions"] == 64
    assert semantic["semantic_score"] > 0
    assert semantic["reason"] == "semantic_recall: 本地 embedding 向量与历史记录相近。"


def test_query_memory_graph_local_embedding_recalls_synonymous_audience_positioning() -> None:
    records = [
        _record(
            "op_audience",
            topic="新手起号方法",
            content_type="step_tutorial",
            score=31,
            pain="不知道先服务哪类人群",
        ),
        _record(
            "op_unrelated",
            topic="宝宝湿疹护理",
            content_type="qa_education",
            score=99,
            pain="担心护理方式不靠谱",
        ),
    ]

    result = memory_graph.query_memory_graph(
        records,
        topic="小红书选题",
        limit=5,
        pain_points=[
            {
                "pain": "内容定位模糊，受众画像不清晰",
                "evidence": "评论说看不出账号适合谁",
            }
        ],
    )

    semantic = result["semantic_recall_records"][0]
    assert semantic["record_id"] == "op_audience"
    assert semantic["semantic_score"] > 0
    assert "audience_positioning" in semantic["matched_terms"]
    assert not any(item["record_id"] == "op_unrelated" for item in result["semantic_recall_records"])


def test_query_memory_graph_returns_historical_compliance_risks() -> None:
    record = _record(
        "op_risk",
        topic="小红书涨粉话题",
        content_type="avoid_mistakes",
        score=20,
        pain="担心表达太夸张",
    )
    record["compliance_risk_level"] = "medium"
    record["compliance_issues"] = ["内容中包含绝对词：一定"]

    result = memory_graph.query_memory_graph(
        [record],
        topic="小红书选题",
        limit=5,
        compliance_risk_level="medium",
        compliance_issues=["内容中包含绝对词：一定"],
    )

    assert result["historical_compliance_risks"][0]["record_id"] == "op_risk"
    assert result["historical_compliance_risks"][0]["risk_level"] == "medium"
    assert "一定" in result["historical_compliance_risks"][0]["matched_terms"]
    assert any(item["type"] == "historical_compliance_risk" for item in result["recall_explanations"])


def test_historical_compliance_risks_prefer_structured_fields() -> None:
    record = _record(
        "op_structured_risk",
        topic="小红书标题表达",
        content_type="avoid_mistakes",
        score=18,
        pain="担心标题太夸张",
    )
    record["compliance_summary"] = {
        "risk_level": "medium",
        "issue_count": 1,
        "issues": ["内容中包含绝对词：一定"],
        "has_revision": True,
    }

    result = memory_graph.query_memory_graph(
        [record],
        topic="小红书选题",
        compliance_risk_level="medium",
        compliance_issues=["内容中包含绝对词：一定"],
    )

    risk = result["historical_compliance_risks"][0]
    assert risk["record_id"] == "op_structured_risk"
    assert "compliance_summary" in risk["matched_fields"]
