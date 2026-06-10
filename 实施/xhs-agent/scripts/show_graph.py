from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.graph import build_langgraph


graph = build_langgraph()
print(graph.get_graph().draw_mermaid())
