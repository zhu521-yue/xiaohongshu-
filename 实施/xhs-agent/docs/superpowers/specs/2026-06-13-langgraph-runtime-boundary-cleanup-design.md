# LangGraph runtime 边界清理设计

## 背景

LangGraph-first 主流程已经合并到 `master`。默认 API、worker 和 CLI 路径现在通过 `run_graph_thread()` 与 `resume_graph_thread()` 执行，审核通过、驳回、creator 私密发布、复盘和写运营记忆都回到图内节点。

迁移后 `app/api.py` 仍保留了一段旧实现：

- API 层直接构造 creator 发布结果的 helper。
- `approve_run()` 在 `return reviewed` 后面的旧手动发布、creator、复盘、写记忆流程。
- 这些 helper 只服务不可达旧流程，和当前 `platforms/creator_publish_flow.py` / `nodes/creator_publish_node.py` 重复。

## 目标

第一轮清理只做保守收敛：

- 删除 `app/api.py` 中不可达旧流程。
- 删除只被不可达旧流程使用的 legacy creator 发布 helper。
- 删除对应无用 import。
- 保留 `run_local_graph()` 和显式 `engine=local` 兼容路径。
- 保留 creator 素材绑定、错误脱敏、business sync 错误脱敏等仍在使用的 API helper。

## 非目标

- 不删除历史 docs/specs/plans。
- 不删除 `run_local_graph()`。
- 不改真实平台适配器。
- 不重构 `app/api.py` 文件结构。
- 不做 GraphRAG、真实发布或工作台 UI 变更。

## 设计

清理边界以测试约束：

1. 新增一个 API 边界测试，明确 `app.api` 不再暴露 legacy direct creator publish helper。
2. 保留 approve/reject 通过 LangGraph resume 的现有测试。
3. 删除 `approve_run()` return 后不可达代码。
4. 删除没有外部引用的旧 helper：
   - `_creator_publish_not_requested`
   - `_creator_publish_failed`
   - `_compact_creator_publish_result`
   - `_creator_publish_success`
   - `_creator_description_from_state`
   - `_creator_images_from_state`
   - `_build_creator_image_text_draft`
   - `_publish_creator_private_if_requested`
   - `_creator_image_file_bytes_from_state`
   - `_resolve_creator_asset_path`
5. 保留 `_sanitize_creator_error()` 和 `_sanitize_business_sync_error()`，因为 business table sync 和错误脱敏仍使用它们。
6. 保留 `_is_supported_creator_image_bytes()`，因为 creator asset 上传校验仍使用它。

## 验收

- 新增边界测试先失败，清理后通过。
- `tests/test_api_langgraph_resume.py` 通过。
- `tests/test_api_creator_review_publish.py` 通过。
- `tests/test_creator_asset_binding.py` 通过。
- 全量测试通过。
