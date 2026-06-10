# 人工审核占位，先用一个节点控制
"""   1. 如果合规风险是 high：人工审核直接不通过                                                                                                            
  2. 如果 state 里 human_approved 是 True：审核通过                                                                                                     
  3. 否则默认审核不通过，发布状态保持 pending  """


from app.state import XHSState


def human_review(state: XHSState) -> dict:
    risk_level = state.get("compliance_risk_level", "low")
    if risk_level == "high":
        return {
            "human_approved": False,
            "human_feedback": "合规风险高，人工审核不通过",
            "publish_status": "pending",
        }
    
    if state.get("human_approved") is True:
        return {
            "human_approved": True,
            "human_feedback": state.get("human_feedback") or "人工审核通过。",
            "publish_status": "pending",
        }
    
    return {
        "human_approved": False,
        "human_feedback": state.get("human_feedback") or "等待人工审核确认。",
        "publish_status": "pending",
    }