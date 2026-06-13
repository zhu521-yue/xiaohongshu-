from app.state import XHSState
from app.data_quality_gate import evaluate_rag_eligibility
from platforms.analysis_report import build_analysis_report
from platforms.collector import collect_topic_insights
from platforms.spider_xhs_collector import save_collection_result


def analyze_topic_and_pain_points(state: XHSState) -> dict:
    topic = state.get("user_topic", "").strip()

    if not topic:
        raise ValueError("user_topic is required before insight analysis")

    limit = int(state.get("collect_limit") or 5)
    try:
        result = collect_topic_insights(topic, limit=limit)
    except Exception as exc:
        result = {
            "raw_notes": [],
            "collection_candidates": [],
            "raw_comments": [],
            "cleaned_notes": [],
            "top_subtopics": [{"name": f"{topic}基础知识", "score": 0.5}],
            "comment_insights": [],
            "pain_points": [
                {
                    "pain": f"用户需要更清晰、可执行的「{topic}」经验说明",
                    "evidence": "真实采集暂时失败，使用主题级兜底痛点，后续需重新采集验证。",
                    "priority": 1,
                }
            ],
            "comment_fetch_errors": [
                {
                    "note_title": topic,
                    "error": f"collector failed: {exc}",
                }
            ],
        }

    result["analysis_report"] = build_analysis_report(
        topic=topic,
        collection_candidates=result.get("collection_candidates") or [],
        raw_notes=result.get("raw_notes") or [],
        raw_comments=result.get("raw_comments") or [],
        comment_insights=result.get("comment_insights") or [],
        pain_points=result.get("pain_points") or [],
        comment_fetch_errors=result.get("comment_fetch_errors") or [],
    )
    result["rag_eligibility"] = evaluate_rag_eligibility(result)

    if state.get("save_collection"):
        path = save_collection_result(topic, result)
        result["collection_path"] = str(path)

    return result
