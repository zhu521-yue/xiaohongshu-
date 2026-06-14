"""Graph-style view over operation memory records.

This is the first M5 slice: it derives topic, pain point, content format,
content type, and performance relationships from existing operation memory.
It does not introduce a vector database or external graph store yet.
"""

from __future__ import annotations

from typing import Any

from app.rules import load_data_quality_rules


DATA_QUALITY_RULES = load_data_quality_rules()


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


def _cross_domain_rules() -> dict[str, Any]:
    rules = DATA_QUALITY_RULES.get("cross_domain_pollution")
    return rules if isinstance(rules, dict) else {}


def _topic_is_health_related(topic: str) -> bool:
    normalized = str(topic or "")
    keywords = _cross_domain_rules().get("health_topic_keywords") or []
    return any(str(keyword) in normalized for keyword in keywords)


def _iter_text_values(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        texts: list[str] = []
        for child in value.values():
            texts.extend(_iter_text_values(child))
        return texts
    if isinstance(value, list):
        texts = []
        for child in value:
            texts.extend(_iter_text_values(child))
        return texts
    return [str(value)]


def _record_has_cross_domain_health_pollution(topic: str, record: dict[str, Any]) -> bool:
    if _topic_is_health_related(topic):
        return False

    patterns = _cross_domain_rules().get("health_pollution_patterns") or []
    fields_to_scan = {
        "topic": record.get("topic"),
        "title": record.get("title"),
        "titles": record.get("titles"),
        "pain_points": record.get("pain_points"),
        "comment_insights": record.get("comment_insights"),
        "review_summary": record.get("review_summary"),
        "next_action": record.get("next_action"),
    }
    haystack = " ".join(_iter_text_values(fields_to_scan))
    return any(str(pattern) in haystack for pattern in patterns)


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


def _context_terms(*values: Any) -> list[str]:
    terms: list[str] = []
    seen: set[str] = set()
    for value in values:
        for text in _iter_text_values(value):
            clean = _clean_text(text)
            if len(clean) < 2:
                continue
            if clean in seen:
                continue
            seen.add(clean)
            terms.append(clean)
    return terms


def _compliance_terms(issues: list[str] | None) -> list[str]:
    terms: list[str] = []
    seen: set[str] = set()
    for issue in issues or []:
        clean = _clean_text(issue)
        if clean and clean not in seen:
            seen.add(clean)
            terms.append(clean)
        if "：" in clean:
            tail = _clean_text(clean.rsplit("：", 1)[-1])
            if len(tail) >= 2 and tail not in seen:
                seen.add(tail)
                terms.append(tail)
        for marker in ("绝对词", "敏感主题", "禁止", "承诺"):
            if marker in clean and marker not in seen:
                seen.add(marker)
                terms.append(marker)
    return terms


def _record_match_fields(record: dict[str, Any], terms: list[str]) -> tuple[list[str], list[str]]:
    fields = {
        "topic": record.get("topic"),
        "title": record.get("title"),
        "pain_points": record.get("pain_points"),
        "comment_insights": record.get("comment_insights"),
        "review_summary": record.get("review_summary"),
        "next_action": record.get("next_action"),
    }
    matched_terms: list[str] = []
    matched_fields: list[str] = []
    for field_name, value in fields.items():
        haystack = " ".join(_iter_text_values(value))
        for term in terms:
            if term and term in haystack and term not in matched_terms:
                matched_terms.append(term)
            if term and term in haystack and field_name not in matched_fields:
                matched_fields.append(field_name)
    return matched_terms, matched_fields


def _compliance_match_fields(record: dict[str, Any], terms: list[str]) -> tuple[list[str], list[str]]:
    fields = {
        "compliance_issues": record.get("compliance_issues"),
        "compliance_risk_level": record.get("compliance_risk_level"),
        "review_summary": record.get("review_summary"),
        "next_action": record.get("next_action"),
        "title": record.get("title"),
        "pain_points": record.get("pain_points"),
    }
    matched_terms: list[str] = []
    matched_fields: list[str] = []
    for field_name, value in fields.items():
        haystack = " ".join(_iter_text_values(value))
        for term in terms:
            if term and term in haystack and term not in matched_terms:
                matched_terms.append(term)
            if term and term in haystack and field_name not in matched_fields:
                matched_fields.append(field_name)
    return matched_terms, matched_fields


def _similar_experience_records(
    records: list[dict[str, Any]],
    *,
    topic: str,
    terms: list[str],
    limit: int,
) -> list[dict[str, Any]]:
    if not terms:
        return []

    candidates: list[tuple[int, int, str, dict[str, Any]]] = []
    for record in records:
        if not isinstance(record, dict):
            continue
        if _record_has_cross_domain_health_pollution(topic, record):
            continue
        matched_terms, matched_fields = _record_match_fields(record, terms)
        if not matched_terms:
            continue
        score = _record_score(record)
        compact = _compact_record(record)
        compact.update(
            {
                "matched_terms": matched_terms,
                "matched_fields": matched_fields,
                "reason": "当前痛点与历史记录的痛点、评论洞察或复盘摘要相似。",
            }
        )
        candidates.append((len(matched_terms), len(matched_fields), score, compact))

    candidates.sort(key=lambda item: (item[0], item[1], item[2], item[3]["record_id"]), reverse=True)
    return [item[3] for item in candidates[: max(0, int(limit))]]


def _historical_compliance_risks(
    records: list[dict[str, Any]],
    *,
    terms: list[str],
    risk_level: str,
    limit: int,
) -> list[dict[str, Any]]:
    if risk_level not in {"medium", "high"} or not terms:
        return []

    candidates: list[tuple[int, int, int, dict[str, Any]]] = []
    for record in records:
        if not isinstance(record, dict):
            continue
        matched_terms, matched_fields = _compliance_match_fields(record, terms)
        if not matched_terms:
            continue
        item = {
            "record_id": record.get("record_id") or "",
            "topic": record.get("topic") or "",
            "risk_level": record.get("compliance_risk_level") or risk_level,
            "issues": record.get("compliance_issues") if isinstance(record.get("compliance_issues"), list) else [],
            "matched_terms": matched_terms,
            "matched_fields": matched_fields,
            "reason": "当前合规问题与历史风险记录相似，生成前需要避免重复表达。",
        }
        candidates.append((len(matched_terms), len(matched_fields), _record_score(record), item))

    candidates.sort(key=lambda item: (item[0], item[1], item[2], item[3]["record_id"]), reverse=True)
    return [item[3] for item in candidates[: max(0, int(limit))]]


def _similar_pain_points(
    records: list[dict[str, Any]],
    *,
    similar_records: list[dict[str, Any]],
    limit: int = 10,
) -> list[dict[str, Any]]:
    similar_ids = {record.get("record_id") for record in similar_records}
    grouped: dict[str, dict[str, Any]] = {}
    for record in records:
        record_id = record.get("record_id")
        if record_id not in similar_ids:
            continue
        score = _record_score(record)
        matched = next((item for item in similar_records if item.get("record_id") == record_id), {})
        for pain in record.get("pain_points") or []:
            if not isinstance(pain, dict):
                continue
            pain_text = _clean_text(pain.get("pain"))
            if not pain_text:
                continue
            item = grouped.setdefault(
                pain_text,
                {"pain": pain_text, "count": 0, "max_score": 0, "record_ids": [], "matched_terms": []},
            )
            item["count"] += 1
            item["max_score"] = max(item["max_score"], score)
            if record_id:
                item["record_ids"].append(record_id)
            for term in matched.get("matched_terms") or []:
                if term not in item["matched_terms"]:
                    item["matched_terms"].append(term)
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


def _recall_explanations(
    similar_records: list[dict[str, Any]],
    compliance_risks: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    explanations: list[dict[str, Any]] = []
    for record in similar_records:
        explanations.append(
            {
                "type": "similar_experience",
                "record_id": record.get("record_id") or "",
                "reason": record.get("reason") or "",
                "matched_terms": record.get("matched_terms") or [],
                "matched_fields": record.get("matched_fields") or [],
            }
        )
    for risk in compliance_risks:
        explanations.append(
            {
                "type": "historical_compliance_risk",
                "record_id": risk.get("record_id") or "",
                "reason": risk.get("reason") or "",
                "matched_terms": risk.get("matched_terms") or [],
                "matched_fields": risk.get("matched_fields") or [],
            }
        )
    return explanations


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
    pain_points: list[dict[str, Any]] | None = None,
    comment_insights: list[dict[str, Any]] | None = None,
    compliance_issues: list[str] | None = None,
    compliance_risk_level: str = "",
) -> dict[str, Any]:
    selected = _select_records(records, topic=topic, limit=limit)
    graph = build_memory_graph(selected, topic="", limit=limit)
    compact_records = [_compact_record(record) for record in selected]
    experience_terms = _context_terms(pain_points or [], comment_insights or [])
    similar_records = _similar_experience_records(records, topic=topic, terms=experience_terms, limit=limit)
    compliance_risks = _historical_compliance_risks(
        records,
        terms=_compliance_terms(compliance_issues),
        risk_level=_clean_text(compliance_risk_level),
        limit=limit,
    )
    return {
        "query": _clean_text(topic),
        "related_records": compact_records,
        "related_pain_points": _related_pain_points(selected),
        "recommended_content_types": graph["recommended_content_types"],
        "recall_evidence": compact_records[:5],
        "similar_experience_records": similar_records,
        "similar_pain_points": _similar_pain_points(records, similar_records=similar_records),
        "historical_compliance_risks": compliance_risks,
        "recall_explanations": _recall_explanations(similar_records, compliance_risks),
        "graph": graph,
    }
