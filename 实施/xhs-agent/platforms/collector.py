"""采集统一入口。

节点层只调用本模块，不直接依赖 mock 或 Spider_XHS。
通过 COLLECTOR_MODE 控制采集实现：
- mock: 开发阶段模拟数据
- spider_xhs: 真实只读小红书采集
"""

import os
from pathlib import Path

from dotenv import load_dotenv

from platforms.mock_collector import collect_topic_insights as collect_mock_topic_insights
from platforms.spider_xhs_collector import collect_topic_insights as collect_spider_topic_insights


PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")


def collect_topic_insights(topic: str, limit: int = 5) -> dict:
    mode = os.getenv("COLLECTOR_MODE", "mock").strip().lower()

    if mode == "mock":
        return collect_mock_topic_insights(topic, limit=limit)

    if mode == "spider_xhs":
        return collect_spider_topic_insights(topic, limit=limit)

    raise ValueError(f"Unsupported COLLECTOR_MODE: {mode}")
