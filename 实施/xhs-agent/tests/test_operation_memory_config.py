from memory import operation_store


def test_cross_domain_health_pollution_rules_load_from_config(monkeypatch) -> None:
    monkeypatch.setattr(
        operation_store,
        "DATA_QUALITY_RULES",
        {
            "cross_domain_pollution": {
                "health_topic_keywords": ["测试健康主题"],
                "health_pollution_patterns": ["测试污染词"],
            }
        },
        raising=False,
    )

    record = {
        "topic": "旧主题",
        "title": "测试污染词",
        "pain_points": [],
    }

    assert operation_store._record_has_cross_domain_health_pollution("小红书选题", record) is True
    assert operation_store._record_has_cross_domain_health_pollution("测试健康主题", record) is False
