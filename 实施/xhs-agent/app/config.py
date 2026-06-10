# 先负责读取配置
# 建设“冷启动阶段规则”和环境变量读取入口
from dataclasses import dataclass
import os
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")


@dataclass(frozen=True)
class Settings:
    llm_api_key: str | None
    llm_base_url:str | None
    llm_model_name: str
    llm_timeout_seconds: float
    llm_image_text_max_tokens: int
    llm_video_max_tokens: int
    llm_review_max_tokens: int
    account_stage:str
    run_store_backend: str
    run_db_path: str
    memory_store_backend: str
    memory_db_path: str


COLD_START_RULES = {
    "account_stage": "cold_start",
    "allow_soft_ad": False,
    "allowed_content_types": [
        "knowledge_share",
        "experience_summary",
        "avoid_mistakes",
        "qa_education",
        "step_tutorial",
    ],
    "allowed_content_formats": [
        "image_text",
        "video",
    ],
    "manual_review_required":True,
}


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return default


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def load_settings() -> Settings:
    return Settings(
        llm_api_key=os.getenv("LLM_API_KEY"),
        llm_base_url=os.getenv("LLM_BASE_URL"),
        llm_model_name=os.getenv("LLM_MODEL_NAME", "mock"),
        llm_timeout_seconds=_env_float("LLM_TIMEOUT_SECONDS", 60.0),
        llm_image_text_max_tokens=_env_int("LLM_IMAGE_TEXT_MAX_TOKENS", 5000),
        llm_video_max_tokens=_env_int("LLM_VIDEO_MAX_TOKENS", 4000),
        llm_review_max_tokens=_env_int("LLM_REVIEW_MAX_TOKENS", 1200),
        account_stage=os.getenv("ACCOUNT_STAGE", "cold_start"),
        run_store_backend=os.getenv("XHS_AGENT_RUN_STORE", "json").strip().lower() or "json",
        run_db_path=os.getenv("XHS_AGENT_RUN_DB_PATH", "data/xhs_agent.sqlite3"),
        memory_store_backend=os.getenv("XHS_AGENT_MEMORY_STORE", "json").strip().lower() or "json",
        memory_db_path=os.getenv("XHS_AGENT_MEMORY_DB_PATH", "data/xhs_agent.sqlite3"),
    )

def get_stage_rules(account_stage:str)->dict:
    if account_stage != "cold_start":
        raise ValueError(f"Unsupported account stage for M1: {account_stage}")
    return COLD_START_RULES
