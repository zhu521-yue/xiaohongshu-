from __future__ import annotations

from contextlib import nullcontext

from platforms import spider_xhs_collector as collector


def _note(
    title: str,
    *,
    likes: int = 0,
    collects: int = 0,
    comments: int = 0,
    shares: int = 0,
    desc: str = "",
    url: str | None = None,
) -> dict:
    safe = title.replace(" ", "_") or "note"
    return {
        "title": title,
        "desc": desc,
        "note_url": url or f"https://www.xiaohongshu.com/explore/{safe}",
        "note_type": "normal",
        "likes": likes,
        "collects": collects,
        "comments": comments,
        "shares": shares,
        "tags": [],
    }


def test_score_collection_candidates_prefers_relevance_over_raw_interaction() -> None:
    notes = [
        _note("小红书的8种变现方式", likes=27727, collects=23995, comments=13859),
        _note("新手选题避坑指南", likes=80, collects=42, comments=18, desc="小红书新手怎么找选题"),
        _note("无标题", likes=0, collects=0, comments=0),
    ]

    candidates = collector.score_collection_candidates(
        "小红书新手选题方法",
        notes,
        selected_limit=2,
    )

    assert candidates[0]["title"] == "新手选题避坑指南"
    assert candidates[0]["selected"] is True
    assert candidates[0]["rank"] == 1
    assert candidates[0]["score"] > candidates[1]["score"]
    assert "topic_relevance" in candidates[0]["score_breakdown"]
    assert any("主题相关" in reason for reason in candidates[0]["reasons"])
    assert any(candidate["title"] == "无标题" and candidate["selected"] is False for candidate in candidates)


def test_collect_topic_samples_uses_scored_candidates_for_comment_fetch(monkeypatch) -> None:
    monkeypatch.setenv("XHS_NOTE_LIMIT", "1")
    monkeypatch.setenv("XHS_CANDIDATE_POOL_LIMIT", "3")
    monkeypatch.setenv("XHS_CANDIDATE_POOL_MULTIPLIER", "3")
    monkeypatch.setenv("XHS_COMMENTS_PER_NOTE", "2")
    monkeypatch.setattr(collector, "_load_cookies", lambda: "cookie")
    monkeypatch.setattr(collector, "_sleep_between_calls", lambda: None)
    monkeypatch.setattr(collector, "_vendor_working_directory", lambda: nullcontext())

    class FakeApi:
        def search_some_note(self, topic, limit, cookies, sort_type_choice=2, note_type=0):
            assert topic == "小红书新手选题方法"
            assert limit == 3
            return (
                True,
                "ok",
                [
                    {
                        "id": "off_topic",
                        "note_card": {
                            "display_title": "小红书的8种变现方式",
                            "desc": "",
                            "type": "normal",
                            "interact_info": {
                                "liked_count": 27727,
                                "collected_count": 23995,
                                "comment_count": 13859,
                                "share_count": 0,
                            },
                        },
                    },
                    {
                        "id": "relevant",
                        "note_card": {
                            "display_title": "新手选题避坑指南",
                            "desc": "小红书新手怎么找选题",
                            "type": "normal",
                            "interact_info": {
                                "liked_count": 80,
                                "collected_count": 42,
                                "comment_count": 18,
                                "share_count": 0,
                            },
                        },
                    },
                    {
                        "id": "low_value",
                        "note_card": {
                            "display_title": "无标题",
                            "desc": "",
                            "type": "normal",
                            "interact_info": {
                                "liked_count": 0,
                                "collected_count": 0,
                                "comment_count": 0,
                                "share_count": 0,
                            },
                        },
                    },
                ],
            )

    fetched_urls: list[str] = []

    def fake_fetch_limited_comments(api, note_url, cookies, limit, debug=False):
        fetched_urls.append(note_url)
        return ([{"content": "新手不知道怎么判断选题", "like_count": 3}], None, [])

    monkeypatch.setattr(collector, "_load_xhs_api", lambda: FakeApi())
    monkeypatch.setattr(collector, "_fetch_limited_comments", fake_fetch_limited_comments)

    result = collector.collect_topic_samples("小红书新手选题方法", limit=1)

    assert result["raw_notes"][0]["title"] == "新手选题避坑指南"
    assert len(result["raw_notes"]) == 1
    assert len(result["collection_candidates"]) == 3
    assert result["collection_candidates"][0]["selected"] is True
    assert result["collection_candidates"][0]["title"] == "新手选题避坑指南"
    assert len(fetched_urls) == 1
    assert "relevant" in fetched_urls[0]


def test_collect_topic_insights_exposes_collection_candidates(monkeypatch) -> None:
    monkeypatch.setattr(
        collector,
        "collect_topic_samples",
        lambda topic, limit=5: {
            "raw_notes": [_note("新手选题避坑指南", comments=18)],
            "raw_comments": [{"content": "不知道从哪里开始", "source_note_title": "新手选题避坑指南"}],
            "comment_fetch_errors": [],
            "collection_candidates": [
                {
                    "title": "新手选题避坑指南",
                    "score": 120,
                    "selected": True,
                    "reasons": ["主题相关"],
                }
            ],
        },
    )

    result = collector.collect_topic_insights("小红书新手选题方法", limit=1)

    assert result["collection_candidates"][0]["title"] == "新手选题避坑指南"
    assert result["collection_candidates"][0]["selected"] is True
