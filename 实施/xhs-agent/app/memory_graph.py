"""Graph-style view over operation memory records.

This is the first M5 slice: it derives topic, pain point, content format,
content type, and performance relationships from existing operation memory.
It does not introduce a vector database or external graph store yet.
"""

from __future__ import annotations

from typing import Any


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _record_score(record: dict[str, Any]) -> int:
    return _safe_int(record.get("performance_score"))


def _record_matches_topic(record: dict[str, Any], topic: str) -> bool:
    clean_topic = _clean_text(topic)
    if not clean_topic:
        return True
    haystack_parts = [
        record.get("topic"),
        record.get("title"),
        record.get("content_type"),
        record.get("content_format"),
        record.get("review_summary"),
        record.get("next_action"),
    ]
    for pain in record.get("pain_points") or []:
        if isinstance(pain, dict):
            haystack_parts.append(pain.get("pain"))
            haystack_parts.append(pain.get("evidence"))
    haystack = " ".join(_clean_text(part) for part in haystack_parts)
    record_topic = _clean_text(record.get("topic"))
    return (
        clean_topic in haystack
        or (record_topic and record_topic in clean_topic)
        or (record_topic and clean_topic in record_topic)
    )


def _node(nodes: dict[str, dict[str, Any]], node_id: str, *, type_: str, label: str, **extra: Any) -> None:
    if not label:
        return
    existing = nodes.get(node_id)
    if existing is None:
        nodes[node_id] = {"id": node_id, "type": type_, "label": label, **extra}
        return
    existing["weight"] = _safe_int(existing.get("weight")) + _safe_int(extra.get("weight") or 1)
    existing["max_score"] = max(_safe_int(existing.get("max_score")), _safe_int(extra.get("max_score")))


def _edge(
    edges: dict[tuple[str, str, str], dict[str, Any]],
    source: str,
    target: str,
    relation: str,
    *,
    weight: int = 1,
) -> None:
    if not source or not target:
        return
    key = (source, target, relation)
    existing = edges.get(key)
    if existing is None:
        edges[key] = {
            "source": source,
            "target": target,
            "relation": relation,
            "weight": weight,
        }
    else:
        existing["weight"] = _safe_int(existing.get("weight")) + weight


def _compact_record(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "record_id": record.get("record_id") or "",
        "topic": record.get("topic") or "",
        "title": record.get("title") or "",
        "content_type": record.get("content_type") or "",
        "content_format": record.get("content_format") or "",
        "performance_score": _record_score(record),
        "performance_data": record.get("performance_data") or {},
        "review_summary": record.get("review_summary") or "",
        "next_action": record.get("next_action") or "",
        "updated_at": record.get("updated_at") or "",
    }


def _select_records(records: list[dict[str, Any]], *, topic: str, limit: int) -> list[dict[str, Any]]:
    selected = [
        record
        for record in records
        if isinstance(record, dict) and _record_matches_topic(record, topic)
    ]
    selected.sort(
        key=lambda record: (
            _record_score(record),
            _clean_text(record.get("updated_at")),
        ),
        reverse=True,
    )
    return selected[: max(0, int(limit))]


def _recommended_content_types(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for record in records:
        content_type = _clean_text(record.get("content_type"))
        if not content_type:
            continue
        item = grouped.setdefault(
            content_type,
            {"content_type": content_type, "count": 0, "total_score": 0, "max_score": 0},
        )
        score = _record_score(record)
        item["count"] += 1
        item["total_score"] += score
        item["max_score"] = max(item["max_score"], score)
    recommendations = []
    for item in grouped.values():
        count = max(1, _safe_int(item.get("count")))
        recommendations.append(
            {
                "content_type": item["content_type"],
                "count": item["count"],
                "average_score": round(float(item["total_score"]) / count, 2),
                "max_score": item["max_score"],
            }
        )
    recommendations.sort(
        key=lambda item: (
            _safe_int(item.get("max_score")),
            _safe_int(item.get("count")),
            str(item.get("content_type") or ""),
        ),
        reverse=True,
    )
    return recommendations


def _related_pain_points(records: list[dict[str, Any]], *, limit: int = 10) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for record in records:
        score = _record_score(record)
        for pain in record.get("pain_points") or []:
            if not isinstance(pain, dict):
                continue
            pain_text = _clean_text(pain.get("pain"))
            if not pain_text:
                continue
            item = grouped.setdefault(
                pain_text,
                {"pain": pain_text, "count": 0, "max_score": 0, "record_ids": []},
            )
            item["count"] += 1
            item["max_score"] = max(item["max_score"], score)
            if record.get("record_id"):
                item["record_ids"].append(record.get("record_id"))
    result = list(grouped.values())
    result.sort(
        key=lambda item: (
            _safe_int(item.get("max_score")),
            _safe_int(item.get("count")),
            str(item.get("pain") or ""),
        ),
        reverse=True,
    )
    return result[:limit]


def build_memory_graph(
    records: list[dict[str, Any]],
    *,
    topic: str = "",
    limit: int = 20,
) -> dict[str, Any]:
    selected = _select_records(records, topic=topic, limit=limit)
    nodes: dict[str, dict[str, Any]] = {}
    edges: dict[tuple[str, str, str], dict[str, Any]] = {}

    for record in selected:
        record_id = _clean_text(record.get("record_id"))
        if not record_id:
            continue
        score = _record_score(record)
        record_node_id = f"record:{record_id}"
        _node(
            nodes,
            record_node_id,
            type_="record",
            label=_clean_text(record.get("title")) or _clean_text(record.get("topic")),
            max_score=score,
            weight=1,
            record_id=record_id,
        )

        topic_label = _clean_text(record.get("topic"))
        topic_node_id = f"topic:{topic_label}"
        _node(nodes, topic_node_id, type_="topic", label=topic_label, max_score=score, weight=1)
        _edge(edges, record_node_id, topic_node_id, "about_topic")

        content_type = _clean_text(record.get("content_type"))
        content_type_node_id = f"content_type:{content_type}"
        _node(nodes, content_type_node_id, type_="content_type", label=content_type, max_score=score, weight=1)
        _edge(edges, record_node_id, content_type_node_id, "uses_content_type")

        content_format = _clean_text(record.get("content_format"))
        content_format_node_id = f"content_format:{content_format}"
        _node(nodes, content_format_node_id, type_="content_format", label=content_format, max_score=score, weight=1)
        _edge(edges, record_node_id, content_format_node_id, "uses_content_format")

        for pain in record.get("pain_points") or []:
            if not isinstance(pain, dict):
                continue
            pain_text = _clean_text(pain.get("pain"))
            pain_node_id = f"pain:{pain_text}"
            _node(nodes, pain_node_id, type_="pain", label=pain_text, max_score=score, weight=1)
            _edge(edges, record_node_id, pain_node_id, "addresses_pain")
            _edge(edges, topic_node_id, pain_node_id, "topic_has_pain")
            _edge(edges, pain_node_id, content_type_node_id, "pain_uses_content_type")

    compact_records = [_compact_record(record) for record in selected]
    return {
        "record_count": len(selected),
        "nodes": sorted(nodes.values(), key=lambda node: (node["type"], node["label"])),
        "edges": sorted(edges.values(), key=lambda edge: (edge["source"], edge["target"], edge["relation"])),
        "top_records": compact_records[:5],
        "recommended_content_types": _recommended_content_types(selected),
    }


def query_memory_graph(
    records: list[dict[str, Any]],
    *,
    topic: str,
    limit: int = 20,
) -> dict[str, Any]:
    selected = _select_records(records, topic=topic, limit=limit)
    graph = build_memory_graph(selected, topic="", limit=limit)
    compact_records = [_compact_record(record) for record in selected]
    return {
        "query": _clean_text(topic),
        "related_records": compact_records,
        "related_pain_points": _related_pain_points(selected),
        "recommended_content_types": graph["recommended_content_types"],
        "recall_evidence": compact_records[:5],
        "graph": graph,
    }
