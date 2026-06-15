"""Content-type routing for stage-2 soft-ad branching.

Delegates to content_format_router for non-soft-ad types so the existing
image_text / video split stays unchanged.
"""

from app.state import XHSState
from routers.content_format_router import route_content_format


def route_content_type(state: XHSState) -> str:
    """Return next node name based on content_type.

    soft_ad → product_node
    everything else → delegate to route_content_format (image_text / video / error)
    """
    content_type = state.get("content_type", "knowledge_share")
    if content_type == "soft_ad":
        return "product_node"
    return route_content_format(state)
