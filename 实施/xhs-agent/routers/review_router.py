from app.state import XHSState

def route_human_review(state: XHSState) -> str:
    if state.get("human_approved") is True:
        return "publish_or_schedule"
    
    return "reject_publish"
