from app.state import XHSState

def route_content_format(state:XHSState)->str:
    content_format = state.get("content_format")
    if content_format == "image_text":
        return "generate_image_text"
    elif content_format == "video":
        return "generate_video_script"
    return "error_handler"

