"""XHS 采集接口层。

M2 当前仍然使用模拟数据，但节点层只依赖这个模块。
后续接入 Spider_XHS 时，优先替换本文件内部实现。
"""

from typing import Any, Dict, List

from platforms.comment_analysis import extract_comment_insights, insights_to_pain_points


def collect_topic_samples(topic: str, limit: int = 5) -> dict:
    """按主题采集笔记和评论样本。

    当前返回模拟数据；真实采集时保持返回结构不变。
    """
    if not topic:
        raise ValueError("topic is required")

    raw_notes = [
        {
            "title": f"{topic}相关高互动笔记样本",
            "likes": 1200,
            "collects": 860,
            "comments": 150,
            "shares": 200,
        }
    ][:limit]

    raw_comments = [
        {"content": f"我最困惑的是{topic}到底该从哪一步开始"},
        {"content": f"网上关于{topic}的说法太多，不知道哪些靠谱"},
        {"content": f"希望有人能把{topic}的避坑点讲清楚"},
    ]

    return {
        "raw_notes": raw_notes,
        "raw_comments": raw_comments,
    }


def clean_notes(raw_notes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    cleaned_notes = []

    for note in raw_notes:
        likes = int(note.get("likes") or note.get("Likes") or 0)
        collects = int(note.get("collects") or 0)
        comments = int(note.get("comments") or 0)
        shares = int(note.get("shares") or 0)

        cleaned_notes.append(
            {
                "title": note.get("title", ""),
                "interaction_score": likes + collects + comments + shares,
            }
        )

    return cleaned_notes


def extract_subtopics(topic: str, raw_comments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    comments_text = " ".join(str(item.get("content", "")) for item in raw_comments)
    subtopics = []

    if "第一步" in comments_text or "从哪一步" in comments_text:
        subtopics.append({"name": f"{topic}入门步骤", "score": 0.86})

    if "避坑" in comments_text or "靠谱" in comments_text:
        subtopics.append({"name": f"{topic}常见误区", "score": 0.78})

    return subtopics or [{"name": f"{topic}基础知识", "score": 0.65}]


def extract_pain_points(topic: str, raw_comments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    comments_text = " ".join(str(item.get("content", "")) for item in raw_comments)
    pain_points = []

    if "从哪一步" in comments_text or "第一步" in comments_text:
        pain_points.append(
            {
                "pain": "信息太碎片化，不知道从哪里开始",
                "evidence": "多条评论提到“第一步”“从哪开始”",
                "priority": 1,
            }
        )

    if "避坑" in comments_text or "靠谱" in comments_text:
        pain_points.append(
            {
                "pain": "担心照着做反而踩坑",
                "evidence": "评论中出现“避坑”“靠谱不靠谱”等表达",
                "priority": 2,
            }
        )

    pain_points.append(
        {
            "pain": "需要可直接执行的清单或步骤",
            "evidence": f"用户希望有人把{topic}的步骤讲清楚",
            "priority": 3,
        }
    )

    return pain_points


def collect_topic_insights(topic: str, limit: int = 5) -> dict:
    samples = collect_topic_samples(topic, limit=limit)
    raw_notes = samples["raw_notes"]
    raw_comments = samples["raw_comments"]
    comment_insights = extract_comment_insights(topic, raw_comments)

    return {
        "raw_notes": raw_notes,
        "raw_comments": raw_comments,
        "cleaned_notes": clean_notes(raw_notes),
        "top_subtopics": extract_subtopics(topic, raw_comments),
        "comment_insights": comment_insights,
        "pain_points": insights_to_pain_points(topic, comment_insights),
    }
