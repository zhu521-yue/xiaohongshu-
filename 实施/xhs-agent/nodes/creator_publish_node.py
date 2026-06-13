from app.state import XHSState
from platforms.creator_publish_flow import publish_creator_private_if_requested


def creator_publish_or_skip(state: XHSState) -> dict:
    return publish_creator_private_if_requested(dict(state))
