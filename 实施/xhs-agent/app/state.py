"""全流程 State 数据合同。

所有节点都只读写这个 State，不在节点之间传零散参数。
节点函数返回的 dict 会被合并回 State。
"""

from typing import Any, Dict, List, Literal, Optional, TypedDict


class XHSState(TypedDict, total=False):
    # Runtime
    run_id: str

    # 用户输入
    user_topic: str
    target_user: str
    user_selected_format: Literal["image_text", "video"]
    user_goal: str

    # 账号阶段
    account_stage: Literal["cold_start", "growth", "monetization_ready"]
    allow_soft_ad: bool

    # 数据分析
    raw_notes: List[Dict[str, Any]]
    collection_candidates: List[Dict[str, Any]]
    raw_comments: List[Dict[str, Any]]
    cleaned_notes: List[Dict[str, Any]]
    top_subtopics: List[Dict[str, Any]]
    pain_points: List[Dict[str, Any]]
    comment_insights: List[Dict[str, Any]]
    analysis_report: Dict[str, Any]
    collect_limit: int
    save_collection: bool
    collection_path: Optional[str]
    comment_fetch_errors: List[Dict[str, Any]]

    # 记忆检索
    retrieved_memory: List[Dict[str, Any]]
    successful_patterns: List[Dict[str, Any]]
    operation_record_id: Optional[str]
    operation_memory_path: Optional[str]
    operation_memory_written: bool

    # 策略结果
    content_type: Literal[
        "knowledge_share",
        "experience_summary",
        "avoid_mistakes",
        "qa_education",
        "step_tutorial",
        "soft_ad",
    ]
    content_format: Literal["image_text", "video"]

    # 商品软广相关，M1 暂不使用，阶段二再接入
    product_info: Optional[Dict[str, Any]]
    product_selling_points: List[str]
    product_pain_match: List[Dict[str, Any]]

    # 内容结果
    titles: List[str]
    cover_texts: List[str]
    body: str
    image_page_plan: List[Dict[str, Any]]
    image_prompts: List[str]
    video_script: Dict[str, Any]
    tags: List[str]
    comment_call: str
    llm_generation: Dict[str, Any]

    # 合规审核
    compliance_risk_level: Literal["low", "medium", "high"]
    compliance_issues: List[str]
    revised_content: Optional[str]

    # 人工审核
    human_approved: bool
    human_feedback: Optional[str]

    # 发布结果
    publish_status: Literal["pending", "success", "failed"]
    post_id: Optional[str]
    publish_time: Optional[str]
    creator_image_files: List[str]
    creator_images_count: int
    creator_assets_updated_at: Optional[str]

    # 复盘结果
    performance_data: Dict[str, Any]
    review_summary: str
    next_action: str
    review_generation: Dict[str, Any]

    # 错误处理
    error_message: Optional[str]
    error_messages: List[str]
