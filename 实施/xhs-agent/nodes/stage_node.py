# 让系统知道当前账号处于什么阶段，并把当前阶段规则写进State
""" 读取当前账号阶段 → 找到对应规则 → 写回 State  """
from app.state import XHSState
from app.config import load_settings,get_stage_rules
def check_account_stage(state:XHSState)->dict:
    settings = load_settings()
    account_stage = state.get("account_stage") or settings.account_stage
    rules = get_stage_rules(account_stage)
    return {
        "account_stage":rules["account_stage"],
        "allow_soft_ad":rules["allow_soft_ad"],
    }
