from app.state import XHSState


def route_compliance_result(state: XHSState) -> str:
    risk_level = state.get("compliance_risk_level")
    if risk_level == "low":
        return "human_review"
    elif risk_level == "medium":
        return "revise_content"
    elif risk_level == "high":
        return "stop_publish"
    return "error_handler"
