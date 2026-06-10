""" 目标：无论用户传进来的字段完整不完整，系统都补齐 M1 需要的默认值。"""
from app.state import XHSState


def load_user_input(state:XHSState)->dict:
    user_topic = state.get("user_topic","").strip()
    if not user_topic:
        raise ValueError("user_topic is required")
    target_user = state.get("target_user") or "小红书目标用户"
    user_selected_format = state.get("user_selected_format") or "image_text"
    user_goal = state.get("user_goal") or "生成一篇冷启动阶段的知识分享内容"
    if user_selected_format not in ("image_text","video"):
        raise ValueError("user_selected_format must be image_text or video")
    return {
        "user_topic":user_topic,
        "target_user":target_user,
        "user_selected_format":user_selected_format,
        "user_goal":user_goal,
    }