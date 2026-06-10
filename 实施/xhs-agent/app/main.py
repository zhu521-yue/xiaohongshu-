"""M1 命令行入口。"""

from argparse import ArgumentParser

from app.graph import run_local_graph,run_langgraph


def build_parser() -> ArgumentParser:
    parser = ArgumentParser(description="Run the local XHS content workflow.")
    parser.add_argument("--topic", required=True, help="用户输入的内容主题")
    parser.add_argument("--target-user", default="小红书目标用户", help="目标用户")
    parser.add_argument(
        "--format",
        choices=("image_text", "video"),
        default="image_text",
        dest="content_format",
        help="内容形式",
    )
    parser.add_argument("--goal", default="生成一篇冷启动阶段的知识分享内容", help="用户目标")
    parser.add_argument("--approve", action="store_true", help="模拟人工审核通过")
    parser.add_argument("--engine",choices=("local","langgraph"),default="local",help="流程运行引擎")
    parser.add_argument("--collect-limit", type=int, default=5, help="采集笔记数量上限")
    parser.add_argument("--save-collection", action="store_true", help="保存本次采集结果")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    runner = run_langgraph if args.engine == "langgraph" else run_local_graph
    final_state = runner(
        {
            "user_topic": args.topic,
            "target_user": args.target_user,
            "user_selected_format": args.content_format,
            "user_goal": args.goal,
            "human_approved": args.approve,
            "collect_limit": args.collect_limit,
            "save_collection": args.save_collection,
        }
    )

    print("raw_notes_count:", len(final_state.get("raw_notes") or []))
    print("raw_comments_count:", len(final_state.get("raw_comments") or []))
    print("comment_insights_count:", len(final_state.get("comment_insights") or []))
    print("pain_points_count:", len(final_state.get("pain_points") or []))
    print("comment_fetch_errors_count:", len(final_state.get("comment_fetch_errors") or []))
    print("collection_path:", final_state.get("collection_path"))
    print("retrieved_memory_count:", len(final_state.get("retrieved_memory") or []))
    print("successful_patterns_count:", len(final_state.get("successful_patterns") or []))
    print("content_format:", final_state.get("content_format"))
    print("content_type:", final_state.get("content_type"))
    print("compliance_risk_level:", final_state.get("compliance_risk_level"))
    print("compliance_issues:", final_state.get("compliance_issues"))
    print("revised_content:", final_state.get("revised_content"))
    print("human_approved:", final_state.get("human_approved"))
    print("publish_status:", final_state.get("publish_status"))
    print("post_id:", final_state.get("post_id"))
    print("llm_generation:", final_state.get("llm_generation"))
    print("operation_memory_written:", final_state.get("operation_memory_written"))
    print("operation_record_id:", final_state.get("operation_record_id"))
    print("operation_memory_path:", final_state.get("operation_memory_path"))
    print("review_summary:", final_state.get("review_summary")) 
    print("next_action:", final_state.get("next_action"))  
    print("review_generation:", final_state.get("review_generation"))
    print("engine:", args.engine)

if __name__ == "__main__":
    main()
