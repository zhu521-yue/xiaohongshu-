from pathlib import Path
import sys
from pprint import pprint
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.graph import build_langgraph

def run_trace(content_format:str)->None:
    graph = build_langgraph()
    initial_state = {
        "user_topic": "宝宝湿疹护理",
        "target_user": "新手宝妈",
        "user_selected_format": content_format,
        "human_approved": True,
    }
    print(f"\n=== trace: {content_format} ===") 
    for step in graph.stream(initial_state, stream_mode="updates"): 
        pprint(step,width=120)

if __name__ == "__main__":
    run_trace("image_text")    
    run_trace("video")