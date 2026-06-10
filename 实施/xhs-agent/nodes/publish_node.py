# M1 阶段它不做真实发布，只负责把内容保存成本地 Markdown 文件
from datetime import datetime
from pathlib import Path
import re
from app.json_store import write_text_atomic
from app.state import XHSState

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = PROJECT_ROOT / "output" / "markdown_exports"

VIDEO_SCRIPT_LABELS = {
    "title": "标题",
    "hook": "开场钩子",
    "duration": "建议时长",
    "opening": "开场口播",
    "talking_points": "口播要点",
    "shot_plan": "分镜规划",
    "subtitle_plan": "字幕规划",
    "cover_text": "封面文字",
    "compliance_note": "合规提醒",
}

def _safe_filename(text:str)->str:
    text = re.sub(r'[\\/:*?"<>|]+', "-", text) 
    text = text.strip().strip(".")
    return text[:50] or "xhs-note"

def _render_image_text_markdown(state: XHSState) -> str:
    title = (state.get("titles") or ["未命名笔记"])[0]
    lines = [
        f"# {title}",
        "",
        "## 封面文案",
    ]
    for item in state.get("cover_texts") or []: 
        lines.append(f"- {item}") 
    lines.extend([
        "",
        "## 正文",
        state.get("body") or "",
        "",
        "## 图片页规划",
    ])
    for page in state.get("image_page_plan") or []:
        if isinstance(page, dict):
            lines.append(f"- P{page.get('page')}: {page.get('title')} - {page.get('text')}")    
        else:
            lines.append(f"- {page}")

    lines.extend(
        [
            "",
            "## 图片提示词",
        ]
    )

    for prompt in state.get("image_prompts") or []:
        lines.append(f"- {prompt}")
    
    lines.extend(
        [
            "",
            "## 标签",
            " ".join(f"#{tag}" for tag in state.get("tags") or []),
            "",
            "## 评论引导",
            state.get("comment_call") or "",
            "",
        ]
    )
    return "\n".join(lines)

# 视频markdown 渲染
def _render_video_markdown(state: XHSState) -> str:
    script = state.get("video_script") or {}
    title = script.get("title") if isinstance(script, dict) else "未命名视频脚本"
    lines = [
        f"# {title}",
        "",
        "## 视频脚本",
    ]
    if isinstance(script, dict):
        for key, value in script.items():
            lines.append(f"### {VIDEO_SCRIPT_LABELS.get(key, key)}")
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        scene = item.get("scene")
                        visual = item.get("visual")
                        text = item.get("text")
                        prefix = f"镜头{scene}" if scene else "镜头"
                        if visual and text:
                            lines.append(f"- {prefix}：{visual}｜屏幕文字：{text}")
                        elif visual:
                            lines.append(f"- {prefix}：{visual}")
                        elif text:
                            lines.append(f"- {prefix}：{text}")
                        else:
                            lines.append(f"- {item}")
                    else:
                        lines.append(f"- {item}")
            else:
                lines.append(str(value))
    else:
        lines.append(str(script))

    lines.extend(
        [
            "## 标签",
            " ".join(f"#{tag}" for tag in state.get("tags") or []), 
            "",
            "## 评论引导",
            state.get("comment_call") or "",
            "",
        ]
    )
    return "\n".join(lines) 

def publish_or_schedule(state:XHSState)->dict:
    if state.get("human_approved") is not True:
        return{
            "publish_status":"pending",
            "post_id":None,
            "publish_time":None,
        }
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    now = datetime.now()
    title = (state.get("titles") or [state.get("user_topic") or "xhs-note"])[0]
    filename = f"{now.strftime('%Y%m%d_%H%M%S')}_{_safe_filename(title)}.md"
    path = OUTPUT_DIR / filename 
    if state.get("content_format") == "video":
        markdown = _render_video_markdown(state)
    else:
        markdown = _render_image_text_markdown(state)
    write_text_atomic(path, markdown)
    return {
        "publish_status":"success",
        "post_id":str(path),
        "publish_time":now.isoformat(timespec="seconds"),
    }
    
