"""Spider_XHS 只读采集适配器。

安全边界：
- 只搜索公开笔记和读取公开评论
- 不发布、不点赞、不收藏、不评论、不关注
- 返回数据会去标识化，不保留昵称、头像、主页、用户 ID、评论 ID
"""

import os
import random
import re
import sys
import time
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List
from urllib.parse import parse_qs, quote, urlparse

import requests
from dotenv import load_dotenv

from app.json_store import write_json_atomic
from platforms.comment_analysis import (
    extract_comment_insights,
    insights_to_pain_points,
    is_noise_comment_text as _common_is_noise_comment_text,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
VENDOR_ROOT = PROJECT_ROOT / "vendor" / "Spider_XHS"
VENDOR_NODE_MODULES = VENDOR_ROOT / "node_modules"
DATA_ROOT = PROJECT_ROOT / "data"
load_dotenv(PROJECT_ROOT / ".env")

NOISE_COMMENT_KEYWORDS = (
    "邀请码",
    "长按复制",
    "复制这条",
    "打开小红书",
    "加入该群",
    "加入群聊",
    "群聊",
    ":/#",
)


def _ensure_vendor_importable() -> None:
    if not VENDOR_ROOT.exists():
        raise RuntimeError(f"Spider_XHS vendor directory not found: {VENDOR_ROOT}")

    vendor_path = str(VENDOR_ROOT)
    if vendor_path not in sys.path:
        sys.path.insert(0, vendor_path)

    if VENDOR_NODE_MODULES.exists():
        node_modules_path = str(VENDOR_NODE_MODULES)
        existing_node_path = os.environ.get("NODE_PATH", "")
        node_paths = [item for item in existing_node_path.split(os.pathsep) if item]
        if node_modules_path not in node_paths:
            os.environ["NODE_PATH"] = os.pathsep.join([node_modules_path, *node_paths])


@contextmanager
def _vendor_working_directory():
    """Run Spider_XHS ExecJS calls from the vendor root.

    Some bundled JS files use relative require paths such as
    "./static/xhs_xray_pack1.js". PyExecJS resolves those paths from the Python
    process cwd at call time, so live API calls must temporarily run from the
    Spider_XHS root.
    """

    previous_cwd = Path.cwd()
    os.chdir(VENDOR_ROOT)
    try:
        yield
    finally:
        os.chdir(previous_cwd)


def _load_xhs_api():
    _ensure_vendor_importable()
    from apis.xhs_pc_apis import XHS_Apis

    return XHS_Apis()


def _load_cookies() -> str:
    cookies = os.getenv("XHS_COOKIES_PC") or os.getenv("COOKIES_PC") or os.getenv("COOKIES")
    if not cookies:
        raise RuntimeError("Missing XHS_COOKIES_PC in .env")
    return cookies


def check_collector_runtime() -> dict[str, Any]:
    try:
        cookies = _load_cookies()
    except Exception as exc:
        return {"ok": False, "mode": "spider_xhs", "platform": "xhs_pc", "error": str(exc)}

    try:
        _load_xhs_api()
    except Exception as exc:
        return {"ok": False, "mode": "spider_xhs", "platform": "xhs_pc", "error": str(exc)}

    return {
        "ok": True,
        "mode": "spider_xhs",
        "platform": "xhs_pc",
        "cookie_present": bool(cookies),
        "vendor_root": str(VENDOR_ROOT),
    }


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return default


def _sleep_between_calls() -> None:
    min_delay = _env_float("XHS_MIN_DELAY_SECONDS", 2.0)
    max_delay = _env_float("XHS_MAX_DELAY_SECONDS", 5.0)
    if max_delay < min_delay:
        max_delay = min_delay
    time.sleep(random.uniform(min_delay, max_delay))


def _count_to_int(value: Any) -> int:
    if value is None:
        return 0
    if isinstance(value, (int, float)):
        return int(value)

    text = str(value).strip().replace(",", "")
    if not text:
        return 0

    try:
        if text.endswith("万"):
            return int(float(text[:-1]) * 10000)
        return int(float(text))
    except ValueError:
        return 0


def _note_interaction_score(note: Dict[str, Any]) -> int:
    return (
        _count_to_int(note.get("likes"))
        + _count_to_int(note.get("collects"))
        + _count_to_int(note.get("comments"))
        + _count_to_int(note.get("shares"))
    )


def _compact_text(value: str) -> str:
    return re.sub(r"\s+", "", str(value or "").lower())


def _topic_terms(topic: str) -> list[str]:
    compact = _compact_text(topic)
    terms: set[str] = set()
    if len(compact) >= 2:
        terms.add(compact)
    for size in (4, 3, 2):
        if len(compact) < size:
            continue
        for index in range(0, len(compact) - size + 1):
            terms.add(compact[index : index + size])
    return sorted(terms, key=lambda item: (-len(item), item))


def _topic_relevance_score(topic: str, note: Dict[str, Any]) -> tuple[int, list[str]]:
    text = _compact_text(
        " ".join(
            [
                str(note.get("title") or ""),
                str(note.get("desc") or ""),
                " ".join(str(tag) for tag in note.get("tags") or []),
            ]
        )
    )
    if not text:
        return 0, []

    score = 0
    matched_terms: list[str] = []
    compact_topic = _compact_text(topic)
    if compact_topic and compact_topic in text:
        score += 60
        matched_terms.append(compact_topic)

    for term in _topic_terms(topic):
        if term == compact_topic or term not in text:
            continue
        if len(term) >= 4:
            score += 18
        elif len(term) == 3:
            score += 12
        else:
            score += 6
        matched_terms.append(term)
        if score >= 90:
            break

    return min(score, 90), matched_terms[:8]


def _comment_score(comments: int) -> int:
    if comments >= 1000:
        return 35
    if comments >= 100:
        return 25
    if comments >= 10:
        return 15
    if comments >= 1:
        return 8
    return 0


def _interaction_bucket_score(interaction_score: int) -> int:
    if interaction_score >= 10000:
        return 30
    if interaction_score >= 1000:
        return 24
    if interaction_score >= 100:
        return 16
    if interaction_score >= 10:
        return 8
    return 0


def _score_candidate(topic: str, note: Dict[str, Any], original_index: int) -> Dict[str, Any]:
    title = str(note.get("title") or "").strip()
    comments = _count_to_int(note.get("comments"))
    interaction = _note_interaction_score(note)
    relevance_score, matched_terms = _topic_relevance_score(topic, note)
    comment_score = _comment_score(comments)
    interaction_score = _interaction_bucket_score(interaction)
    quality_score = 0
    penalties = 0
    reasons: list[str] = []
    penalty_reasons: list[str] = []

    if title and title != "无标题":
        quality_score += 10
    else:
        penalties += 35
        penalty_reasons.append("标题缺失或无效")

    if note.get("note_url"):
        quality_score += 5
    else:
        penalties += 80
        penalty_reasons.append("缺少笔记链接")

    if relevance_score > 0:
        reasons.append(f"主题相关：{', '.join(matched_terms[:4])}")
    else:
        penalties += 20
        penalty_reasons.append("主题相关度低")

    if comments > 0:
        reasons.append(f"评论数 {comments}")
    else:
        penalties += 12
        penalty_reasons.append("评论数为 0")

    if interaction > 0:
        reasons.append(f"互动量 {interaction}")
    else:
        penalties += 8
        penalty_reasons.append("互动量为 0")

    score_breakdown = {
        "topic_relevance": relevance_score,
        "comments": comment_score,
        "interaction": interaction_score,
        "quality": quality_score,
        "penalty": penalties,
    }
    score = relevance_score + comment_score + interaction_score + quality_score - penalties

    return {
        "rank": 0,
        "selected": False,
        "original_index": original_index,
        "title": title,
        "note_url": str(note.get("note_url") or ""),
        "comments": comments,
        "likes": _count_to_int(note.get("likes")),
        "collects": _count_to_int(note.get("collects")),
        "shares": _count_to_int(note.get("shares")),
        "score": score,
        "score_breakdown": score_breakdown,
        "reasons": reasons,
        "penalties": penalty_reasons,
    }


def score_collection_candidates(
    topic: str,
    notes: List[Dict[str, Any]],
    selected_limit: int = 5,
) -> List[Dict[str, Any]]:
    candidates = [
        _score_candidate(topic, note, index)
        for index, note in enumerate(notes)
        if isinstance(note, dict)
    ]
    candidates.sort(key=lambda item: (-_safe_candidate_score(item), item["original_index"]))

    selected_count = max(0, int(selected_limit or 0))
    eligible_positions = [
        position
        for position, candidate in enumerate(candidates)
        if _is_useful_note(notes[candidate["original_index"]])
    ]
    if not eligible_positions:
        eligible_positions = list(range(len(candidates)))
    selected_positions = set(eligible_positions[:selected_count])

    for position, candidate in enumerate(candidates):
        candidate["rank"] = position + 1
        candidate["selected"] = position in selected_positions
    return candidates


def _safe_candidate_score(candidate: Dict[str, Any]) -> int:
    return _count_to_int(candidate.get("score"))


def _is_useful_note(note: Dict[str, Any]) -> bool:
    title = str(note.get("title") or "").strip()
    note_url = str(note.get("note_url") or "").strip()
    comments = _count_to_int(note.get("comments"))
    interaction_score = _note_interaction_score(note)

    min_comments = _env_int("XHS_MIN_NOTE_COMMENTS", 1)
    min_interaction = _env_int("XHS_MIN_NOTE_INTERACTION", 10)

    if not note_url:
        return False
    if title in ("", "无标题") and comments <= 0:
        return False
    if comments < min_comments and interaction_score < min_interaction:
        return False
    return True


def _is_noise_comment_text(text: str) -> bool:
    return _common_is_noise_comment_text(text)


def _should_keep_comment(comment: Dict[str, Any]) -> bool:
    content = str(comment.get("content") or "").strip()
    return bool(content) and not _is_noise_comment_text(content)


def _note_url(note: Dict[str, Any]) -> str:
    if note.get("note_url"):
        return str(note["note_url"])
    if note.get("url"):
        return str(note["url"])

    note_id = note.get("id") or note.get("note_id") or note.get("note_card", {}).get("note_id")
    if not note_id:
        return ""

    xsec_token = note.get("xsec_token") or note.get("note_card", {}).get("xsec_token") or ""
    url = f"https://www.xiaohongshu.com/explore/{note_id}"
    if xsec_token:
        url = f"{url}?xsec_token={quote(str(xsec_token))}&xsec_source=pc_search"
    return url


def _deidentify_note(note: Dict[str, Any]) -> Dict[str, Any]:
    card = note.get("note_card") or {}
    interact = card.get("interact_info") or note.get("interact_info") or {}

    title = (
        note.get("title")
        or card.get("display_title")
        or card.get("title")
        or card.get("desc")
        or "无标题"
    )

    return {
        "title": str(title),
        "desc": str(card.get("desc") or note.get("desc") or ""),
        "note_url": _note_url(note),
        "note_type": str(card.get("type") or note.get("note_type") or ""),
        "likes": _count_to_int(interact.get("liked_count") or note.get("likes")),
        "collects": _count_to_int(interact.get("collected_count") or note.get("collects")),
        "comments": _count_to_int(interact.get("comment_count") or note.get("comments")),
        "shares": _count_to_int(interact.get("share_count") or note.get("shares")),
        "tags": [
            str(tag.get("name"))
            for tag in card.get("tag_list", [])
            if isinstance(tag, dict) and tag.get("name")
        ],
    }


def _deidentify_comment(comment: Dict[str, Any], source_note_title: str) -> Dict[str, Any]:
    return {
        "content": str(comment.get("content") or ""),
        "like_count": _count_to_int(comment.get("like_count")),
        "source_note_title": source_note_title,
    }


def _parse_note_url(note_url: str) -> tuple[str, str]:
    parsed = urlparse(note_url)
    note_id = parsed.path.rstrip("/").split("/")[-1]
    query = parse_qs(parsed.query)
    xsec_token = (query.get("xsec_token") or [""])[0]
    return note_id, xsec_token


def _comment_response_summary(res_json: Dict[str, Any]) -> Dict[str, Any]:
    data = res_json.get("data") if isinstance(res_json, dict) else None
    data = data if isinstance(data, dict) else {}
    comments = data.get("comments")
    return {
        "code": res_json.get("code") if isinstance(res_json, dict) else None,
        "success": res_json.get("success") if isinstance(res_json, dict) else None,
        "msg": res_json.get("msg") if isinstance(res_json, dict) else None,
        "data_keys": sorted(data.keys()),
        "comments_count": len(comments) if isinstance(comments, list) else None,
        "has_more": data.get("has_more"),
        "cursor": data.get("cursor"),
    }


def _search_item_summary(item: Dict[str, Any]) -> Dict[str, Any]:
    card = item.get("note_card") if isinstance(item, dict) else None
    card = card if isinstance(card, dict) else {}
    interact = card.get("interact_info") or item.get("interact_info") or {}
    interact = interact if isinstance(interact, dict) else {}

    return {
        "top_keys": sorted(item.keys()) if isinstance(item, dict) else [],
        "note_card_keys": sorted(card.keys()),
        "interact_keys": sorted(interact.keys()),
        "raw_title_candidates": {
            "item.title": item.get("title") if isinstance(item, dict) else None,
            "card.display_title": card.get("display_title"),
            "card.title": card.get("title"),
            "card.desc": card.get("desc"),
        },
        "raw_interact": {
            "liked_count": interact.get("liked_count"),
            "collected_count": interact.get("collected_count"),
            "comment_count": interact.get("comment_count"),
            "share_count": interact.get("share_count"),
        },
        "parsed_note": _deidentify_note(item) if isinstance(item, dict) else {},
    }


def _search_response_summary(res_json: Dict[str, Any], max_items: int = 5) -> Dict[str, Any]:
    data = res_json.get("data") if isinstance(res_json, dict) else None
    data = data if isinstance(data, dict) else {}
    items = data.get("items") or []
    item_summaries = [
        _search_item_summary(item)
        for item in items[:max_items]
        if isinstance(item, dict)
    ]

    return {
        "code": res_json.get("code") if isinstance(res_json, dict) else None,
        "success": res_json.get("success") if isinstance(res_json, dict) else None,
        "msg": res_json.get("msg") if isinstance(res_json, dict) else None,
        "data_keys": sorted(data.keys()),
        "items_count": len(items) if isinstance(items, list) else None,
        "has_more": data.get("has_more"),
        "item_summaries": item_summaries,
    }


def _request_comment_page(
    api: Any,
    note_id: str,
    cursor: str,
    xsec_token: str,
    cookies: str,
) -> Dict[str, Any]:
    _ensure_vendor_importable()
    from xhs_utils.http_util import REQUEST_TIMEOUT
    from xhs_utils.xhs_util import generate_request_params, splice_str

    comment_api = "/api/sns/web/v2/comment/page"
    params = {
        "note_id": note_id,
        "cursor": cursor,
        "top_comment_id": "",
        "image_formats": "jpg,webp,avif",
        "xsec_token": xsec_token,
    }
    splice_api = splice_str(comment_api, params)

    with _vendor_working_directory():
        headers, cookie_dict, _ = generate_request_params(cookies, splice_api, "", "GET")
        response = requests.get(
            api.base_url + splice_api,
            headers=headers,
            cookies=cookie_dict,
            timeout=REQUEST_TIMEOUT,
        )

    return response.json()


def _fetch_limited_comments(
    api: Any,
    note_url: str,
    cookies: str,
    limit: int,
    debug: bool = False,
) -> tuple[List[Dict[str, Any]], str | None, List[Dict[str, Any]]]:
    """Fetch a bounded set of top-level comments.

    Spider_XHS expects every successful response to contain a "msg" key, but
    Xiaohongshu can return shapes like {"code": 0, "success": true, "data": {}}.
    Treat those as empty comment pages instead of failing the entire collection.
    """

    if limit <= 0:
        return [], None, []

    note_id, xsec_token = _parse_note_url(note_url)
    if not note_id:
        return [], "missing note_id", []

    cursor = ""
    comments: List[Dict[str, Any]] = []
    debug_responses: List[Dict[str, Any]] = []

    while len(comments) < limit:
        try:
            res_json = _request_comment_page(api, note_id, cursor, xsec_token, cookies)
        except requests.RequestException as exc:
            return comments, f"comment request failed: {exc}", debug_responses
        except ValueError as exc:
            return comments, f"invalid comment response json: {exc}", debug_responses

        if debug:
            debug_responses.append(_comment_response_summary(res_json))

        if not isinstance(res_json, dict):
            return comments, "invalid comment response", debug_responses

        if res_json.get("success") is not True:
            return comments, res_json.get("msg") or str(_comment_response_summary(res_json)), debug_responses

        data = res_json.get("data") or {}
        page_comments = data.get("comments") or []
        if not page_comments:
            return comments, None, debug_responses

        remaining = limit - len(comments)
        comments.extend(page_comments[:remaining])

        if len(comments) >= limit or not data.get("has_more"):
            break

        cursor = str(data.get("cursor") or "")
        if not cursor:
            break

    return comments, None, debug_responses


def clean_notes(raw_notes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    cleaned_notes = []
    for note in raw_notes:
        cleaned_notes.append(
            {
                "title": note.get("title", ""),
                "interaction_score": (
                    _count_to_int(note.get("likes"))
                    + _count_to_int(note.get("collects"))
                    + _count_to_int(note.get("comments"))
                    + _count_to_int(note.get("shares"))
                ),
            }
        )
    return cleaned_notes


def _safe_filename_part(text: str) -> str:
    text = re.sub(r'[\\/:*?"<>|]+', "-", text)
    text = re.sub(r"\s+", " ", text).strip().strip(".")
    return text[:60] or "topic"


def save_collection_result(
    topic: str,
    result: Dict[str, Any],
    output_dir: str | Path | None = None,
    collector_name: str = "spider_xhs",
) -> Path:
    target_dir = Path(output_dir) if output_dir else DATA_ROOT / "collector_runs"
    target_dir.mkdir(parents=True, exist_ok=True)

    now = datetime.now()
    filename = f"{now.strftime('%Y%m%d_%H%M%S')}_{_safe_filename_part(topic)}.json"
    path = target_dir / filename
    payload = {
        "topic": topic,
        "collector": collector_name,
        "created_at": now.isoformat(timespec="seconds"),
        "summary": {
            "raw_notes_count": len(result.get("raw_notes") or []),
            "raw_comments_count": len(result.get("raw_comments") or []),
            "comment_insights_count": len(result.get("comment_insights") or []),
            "cleaned_notes_count": len(result.get("cleaned_notes") or []),
            "pain_points_count": len(result.get("pain_points") or []),
            "comment_fetch_errors_count": len(result.get("comment_fetch_errors") or []),
        },
        "result": result,
    }
    write_json_atomic(path, payload)
    return path


def extract_subtopics(topic: str, raw_comments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    text = " ".join(str(item.get("content", "")) for item in raw_comments)
    subtopics = []

    if any(word in text for word in ("第一步", "从哪", "步骤", "流程")):
        subtopics.append({"name": f"{topic}入门步骤", "score": 0.86})

    if any(word in text for word in ("避坑", "误区", "靠谱", "踩坑")):
        subtopics.append({"name": f"{topic}常见误区", "score": 0.78})

    if any(word in text for word in ("反复", "担心", "怎么办")):
        subtopics.append({"name": f"{topic}高频疑问", "score": 0.7})

    return subtopics or [{"name": f"{topic}基础知识", "score": 0.65}]


def extract_pain_points(topic: str, raw_comments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    text = " ".join(str(item.get("content", "")) for item in raw_comments)
    pain_points = []

    if any(word in text for word in ("第一步", "从哪", "步骤", "流程")):
        pain_points.append(
            {
                "pain": "信息太碎片化，不知道从哪里开始",
                "evidence": "评论中出现“第一步 / 从哪 / 步骤 / 流程”等表达",
                "priority": 1,
            }
        )

    if any(word in text for word in ("避坑", "误区", "靠谱", "踩坑")):
        pain_points.append(
            {
                "pain": "担心照着做反而踩坑",
                "evidence": "评论中出现“避坑 / 误区 / 靠谱 / 踩坑”等表达",
                "priority": 2,
            }
        )

    if not pain_points:
        pain_points.append(
            {
                "pain": "需要更具体、可执行的经验说明",
                "evidence": f"评论内容围绕「{topic}」展开，但缺少可直接执行的路径",
                "priority": 1,
            }
        )

    return pain_points


def collect_topic_samples(topic: str, limit: int = 5) -> dict:
    if not topic:
        raise ValueError("topic is required")

    cookies = _load_cookies()
    api = _load_xhs_api()

    note_limit = min(limit, _env_int("XHS_NOTE_LIMIT", 3))
    candidate_multiplier = max(1, _env_int("XHS_CANDIDATE_POOL_MULTIPLIER", 3))
    default_candidate_limit = max(note_limit, min(20, note_limit * candidate_multiplier))
    candidate_pool_limit = max(note_limit, _env_int("XHS_CANDIDATE_POOL_LIMIT", default_candidate_limit))
    search_limit = max(note_limit, min(candidate_pool_limit, note_limit * candidate_multiplier))
    comments_per_note = _env_int("XHS_COMMENTS_PER_NOTE", 10)
    sort_type_choice = _env_int("XHS_SORT_TYPE", 2)

    with _vendor_working_directory():
        success, msg, notes = api.search_some_note(
            topic,
            search_limit,
            cookies,
            sort_type_choice=sort_type_choice,
            note_type=0,
        )
    if not success:
        raise RuntimeError(f"Spider_XHS search failed: {msg}")

    deidentified_notes = [_deidentify_note(note) for note in notes]
    collection_candidates = score_collection_candidates(
        topic,
        deidentified_notes,
        selected_limit=note_limit,
    )
    selected_indices = [
        int(candidate.get("original_index"))
        for candidate in collection_candidates
        if candidate.get("selected") is True
    ]
    raw_notes = [deidentified_notes[index] for index in selected_indices]
    if not raw_notes:
        raw_notes = deidentified_notes[:note_limit]

    raw_comments = []
    comment_fetch_errors = []

    for note in raw_notes:
        note_url = note.get("note_url")
        if not note_url:
            continue

        _sleep_between_calls()
        comments, error, _ = _fetch_limited_comments(api, note_url, cookies, comments_per_note)
        if error:
            comment_fetch_errors.append(
                {
                    "note_title": note.get("title", ""),
                    "error": error,
                }
            )
            continue

        kept_for_note = 0
        for comment in comments[:comments_per_note]:
            if kept_for_note >= comments_per_note:
                break

            cleaned_comment = _deidentify_comment(comment, note.get("title", ""))
            if _should_keep_comment(cleaned_comment):
                raw_comments.append(cleaned_comment)
                kept_for_note += 1

            sub_comments = comment.get("sub_comments") or []
            for sub_comment in sub_comments:
                if kept_for_note >= comments_per_note:
                    break

                cleaned_sub_comment = _deidentify_comment(sub_comment, note.get("title", ""))
                if _should_keep_comment(cleaned_sub_comment):
                    raw_comments.append(cleaned_sub_comment)
                    kept_for_note += 1

    return {
        "raw_notes": raw_notes,
        "raw_comments": raw_comments,
        "comment_fetch_errors": comment_fetch_errors,
        "collection_candidates": collection_candidates,
    }


def collect_topic_insights(topic: str, limit: int = 5) -> dict:
    samples = collect_topic_samples(topic, limit=limit)
    raw_notes = samples["raw_notes"]
    raw_comments = samples["raw_comments"]
    comment_insights = extract_comment_insights(topic, raw_comments)

    return {
        "raw_notes": raw_notes,
        "raw_comments": raw_comments,
        "cleaned_notes": clean_notes(raw_notes),
        "comment_fetch_errors": samples.get("comment_fetch_errors") or [],
        "collection_candidates": samples.get("collection_candidates") or [],
        "top_subtopics": extract_subtopics(topic, raw_comments),
        "comment_insights": comment_insights,
        "pain_points": insights_to_pain_points(topic, comment_insights),
    }
