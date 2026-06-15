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
    api_token: str | None
    log_dir: str
    log_level: str
    log_max_bytes: int
    log_backup_count: int
    run_store_backend: str
    run_db_path: str
    run_queue_backend: str
    queue_db_path: str
    queue_poll_seconds: float
    queue_max_attempts: int
    queue_lock_timeout_seconds: int
    queue_heartbeat_interval_seconds: float
    queue_heartbeat_timeout_seconds: int
    worker_id: str | None
    memory_store_backend: str
    memory_db_path: str
    db_schema: str
    business_tables_enabled: bool


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

MONETIZATION_READY_RULES = {
    "account_stage": "monetization_ready",
    "allow_soft_ad": True,
    "allowed_content_types": [
        "knowledge_share",
        "experience_summary",
        "avoid_mistakes",
        "qa_education",
        "step_tutorial",
        "soft_ad",
    ],
    "allowed_content_formats": ["image_text", "video"],
    "manual_review_required": True,
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


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _optional_env(name: str) -> str | None:
    value = os.getenv(name)
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


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
        api_token=_optional_env("XHS_AGENT_API_TOKEN"),
        log_dir=os.getenv("XHS_AGENT_LOG_DIR", "data/logs"),
        log_level=os.getenv("XHS_AGENT_LOG_LEVEL", "INFO").strip().upper() or "INFO",
        log_max_bytes=_env_int("XHS_AGENT_LOG_MAX_BYTES", 1048576),
        log_backup_count=_env_int("XHS_AGENT_LOG_BACKUP_COUNT", 5),
        run_store_backend=os.getenv("XHS_AGENT_RUN_STORE", "json").strip().lower() or "json",
        run_db_path=os.getenv("XHS_AGENT_RUN_DB_PATH", "data/xhs_agent.sqlite3"),
        run_queue_backend=os.getenv("XHS_AGENT_RUN_QUEUE", "local").strip().lower() or "local",
        queue_db_path=os.getenv("XHS_AGENT_QUEUE_DB_PATH", "data/xhs_agent.sqlite3"),
        queue_poll_seconds=_env_float("XHS_AGENT_QUEUE_POLL_SECONDS", 1.0),
        queue_max_attempts=_env_int("XHS_AGENT_QUEUE_MAX_ATTEMPTS", 3),
        queue_lock_timeout_seconds=_env_int("XHS_AGENT_QUEUE_LOCK_TIMEOUT_SECONDS", 900),
        queue_heartbeat_interval_seconds=_env_float("XHS_AGENT_QUEUE_HEARTBEAT_INTERVAL_SECONDS", 30.0),
        queue_heartbeat_timeout_seconds=_env_int("XHS_AGENT_QUEUE_HEARTBEAT_TIMEOUT_SECONDS", 1800),
        worker_id=os.getenv("XHS_AGENT_WORKER_ID"),
        memory_store_backend=os.getenv("XHS_AGENT_MEMORY_STORE", "json").strip().lower() or "json",
        memory_db_path=os.getenv("XHS_AGENT_MEMORY_DB_PATH", "data/xhs_agent.sqlite3"),
        db_schema=os.getenv("XHS_AGENT_DB_SCHEMA", "foundation").strip().lower() or "foundation",
        business_tables_enabled=_env_bool("XHS_AGENT_BUSINESS_TABLES_ENABLED", False),
    )

def get_stage_rules(account_stage: str) -> dict:
    if account_stage == "cold_start":
        return COLD_START_RULES
    if account_stage == "monetization_ready":
        return MONETIZATION_READY_RULES
    raise ValueError(f"Unsupported account stage: {account_stage}")
