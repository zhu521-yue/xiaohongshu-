from app.rules import load_compliance_rules
from app.state import XHSState


_COMPLIANCE_RULES = load_compliance_rules()
ABSOLUTE_WORDS = list(_COMPLIANCE_RULES.get("absolute_words") or [])
SENSITIVE_TOPICS = list(_COMPLIANCE_RULES.get("sensitive_topics") or [])
DISCLAIMER_WORDS = list(_COMPLIANCE_RULES.get("disclaimer_words") or [])
AVOID_PROMISE_WORDS = list(_COMPLIANCE_RULES.get("avoid_promise_words") or [])
SAFETY_NOTE = str(_COMPLIANCE_RULES.get("safety_note") or "")


# 内容提取逻辑
def _content_text(state:XHSState)->str:
    parts = []
    body = state.get("body", "")
    if body:
        parts.append(str(body))
    video_script = state.get("video_script")
    if isinstance(video_script, dict):
        parts.extend(str(value) for value in video_script.values())
    elif video_script:
        parts.append(str(video_script))

    return "\n".join(parts)

# 审核逻辑
def check_compliance(state: XHSState) -> dict:
    text = _content_text(state)
    issues = []

    if state.get("account_stage") == "cold_start" and state.get("content_type") == "soft_ad":
        issues.append("冷启动阶段禁止生成或发布软广内容")

    for word in ABSOLUTE_WORDS:
        if word in text:
            issues.append(f"内容中包含绝对词：{word}")

    has_sensitive_topic = any(word in text for word in SENSITIVE_TOPICS)
    has_disclaimer = any(word in text for word in DISCLAIMER_WORDS)

    if has_sensitive_topic and not has_disclaimer:
        issues.append("敏感主题缺少经验分享或风险提示")

    # --- Stage 2: soft_ad specific compliance ---
    if state.get("content_type") == "soft_ad":
        rules = _COMPLIANCE_RULES.get("soft_ad_rules") or {}

        # Check required disclaimers
        required = rules.get("required_disclaimers") or []
        found = [d for d in required if d in text]
        if not found:
            issues.append("软广内容缺少广告/合作标识")

        # Check forbidden soft-ad words
        forbidden = rules.get("forbidden_soft_ad_words") or []
        for word in forbidden:
            if word in text:
                issues.append(f"软广内容包含禁止词：{word}")

        # Check efficacy claims
        efficacy = rules.get("forbidden_efficacy_claims") or []
        for claim in efficacy:
            if claim in text:
                issues.append(f"软广内容包含功效承诺：{claim}")

        # Check frequency guardrail (from strategy pre-check)
        freq_check = state.get("soft_ad_frequency_check")
        if isinstance(freq_check, dict) and not freq_check.get("allowed"):
            for issue in freq_check.get("issues") or []:
                issues.append(f"频率护栏：{issue}")
    # --- End soft_ad compliance ---

    if not issues:
        risk_level = "low"
    elif any("禁止" in issue or "根治" in issue for issue in issues):
        risk_level = "high"
    else:
        risk_level = "medium"

    return {
        "compliance_risk_level": risk_level,
        "compliance_issues": issues,
        "revised_content": None,
    }


def revise_content_for_compliance(state: XHSState) -> dict:
    """Add explicit safety notes for medium-risk content before human review."""

    risk_level = state.get("compliance_risk_level")
    issues = state.get("compliance_issues") or []

    if risk_level != "medium":
        return {"revised_content": state.get("revised_content")}

    updates = {
        "revised_content": SAFETY_NOTE,
    }

    body = str(state.get("body") or "")
    if body and SAFETY_NOTE not in body:
        updates["body"] = "\n".join([body.rstrip(), "", "发布前提醒：", SAFETY_NOTE])

    video_script = state.get("video_script")
    if isinstance(video_script, dict):
        next_script = dict(video_script)
        existing_note = str(next_script.get("compliance_note") or "")
        if SAFETY_NOTE not in existing_note:
            next_script["compliance_note"] = (
                f"{existing_note} {SAFETY_NOTE}".strip()
                if existing_note
                else SAFETY_NOTE
            )
        updates["video_script"] = next_script

    if issues:
        updates["human_feedback"] = (
            "合规中风险，已补充发布前提醒；请人工重点检查："
            + "；".join(str(issue) for issue in issues)
        )

    return updates
