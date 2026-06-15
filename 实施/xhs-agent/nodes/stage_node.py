"""读取当前账号阶段 → 找到对应规则 → 写回 State"""
from app.state import XHSState
from app.config import load_settings, get_stage_rules


def check_account_stage(state: XHSState) -> dict:
    override = state.get("stage_override")
    if override in ("cold_start", "growth", "monetization_ready"):
        rules = get_stage_rules(override)
        return {
            "account_stage": rules["account_stage"],
            "allow_soft_ad": rules["allow_soft_ad"],
        }

    settings = load_settings()
    account_stage = state.get("account_stage") or settings.account_stage
    rules = get_stage_rules(account_stage)
    return {
        "account_stage": rules["account_stage"],
        "allow_soft_ad": rules["allow_soft_ad"],
    }
