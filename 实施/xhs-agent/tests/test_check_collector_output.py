from __future__ import annotations

from scripts import check_collector


class FlakyGBKStdout:
    encoding = "gbk"

    def __init__(self) -> None:
        self.calls = 0
        self.writes: list[str] = []

    def write(self, text: str) -> int:
        self.calls += 1
        if self.calls == 1:
            raise UnicodeEncodeError("gbk", "📝", 0, 1, "illegal multibyte sequence")
        self.writes.append(text)
        return len(text)


def test_print_json_falls_back_when_console_rejects_unicode(monkeypatch) -> None:
    stdout = FlakyGBKStdout()
    monkeypatch.setattr(check_collector.sys, "stdout", stdout)

    check_collector._print_json({"title": "候选📝"})

    assert stdout.calls == 2
    assert "\\U0001f4dd" in stdout.writes[0]


def test_build_collection_diagnostic_payload_includes_analysis_report() -> None:
    payload = check_collector.build_collection_diagnostic_payload(
        topic="小红书新手选题方法",
        raw_notes=[{"title": "新手选题避坑指南"}],
        collection_candidates=[
            {"title": "新手选题避坑指南", "score": 120, "selected": True, "rank": 1}
        ],
        raw_comments=[{"content": "不知道怎么判断选题？"} for _ in range(6)],
        comment_insights=[
            {
                "pain": "用户不知道怎么判断选题",
                "evidence_comments": ["不知道怎么判断选题？", "选题怎么避坑？"],
                "evidence_count": 2,
                "priority": 1,
            }
        ],
        pain_points=[{"pain": "用户不知道怎么判断选题"}],
        comment_fetch_errors=[],
    )

    assert payload["analysis_report"]["sample_selection"]["selected_count"] == 1
    assert payload["analysis_report"]["comment_quality"]["quality_level"] == "medium"
