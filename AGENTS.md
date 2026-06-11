# 小红书内容分享项目记忆

## 回复与协作约定

- 每条回复正文开头必须先加：`锋神殿下，奴婢认为：`
- 当用户提供状态描述和问题时，先复述用户的核心目标，再回答。
- 如果用户没有明确目标，先澄清目标，不要直接猜测。
- 规划、设计、实施计划统一使用中文，不要用英文标题和英文计划模板。
- 每次执行命令前，需要说明执行目的、预期结果和异常处理方式。
- Python 命令优先使用 `D:\Anaconda\envs\ContentShare\python.exe`。

## 使用约定

- 本文件是仓库根目录级项目记忆入口，用于记录当前主项目方向、关键进度和后续协作约定。
- 当前主要开发目录是 `实施/xhs-agent`。
- 详细逐轮进度记录在 `实施/xhs-agent/memory/current_progress.md`。
- 全局路线图记录在 `实施/xhs-agent/memory/project_status_and_roadmap.md`。
- 原始主线依据是 `从0实现指导手册.md`，后续判断“还剩哪些任务”必须优先对照这份手册的 M0-M6，而不是只看最近工程迭代。

## 当前项目目标

当前主项目是“小红书两阶段多智能体运营系统”。目标是用 LangGraph 编排、复用 Spider_XHS 能力、接入国产 LLM，完成从选题洞察、真实评论采集、内容生成、合规、人工确认、发布、表现回收、复盘、GraphRAG 记忆沉淀，到阶段二软广/达人能力的闭环。

## 当前阶段

- 按 `从0实现指导手册.md` 重新校准后，当前不是“快完成”，而是：阶段一 MVP 与部分 creator 私密发布闭环已完成，完整两阶段系统仍有较多主线任务。
- M0 环境与链路验证：部分完成。mock 链路和脚本齐全，但真实 PC Cookie、真实 creator Cookie、真实发布端到端仍需最新验证；千帆/蒲公英 Cookie 未进入。
- M1 内容生成最小闭环：基本完成。主题到图文/视频、合规、人工审核、Markdown 保存已可用；但 `human_review` 还不是 LangGraph interrupt。
- M2 只读采集：部分完成。已有 collector 薄封装、Spider_XHS 采集、评论去噪和去标识化；但随机延时、Cookie 失效前置自检、正式笔记/评论表、采集质量评分仍不完整。
- M3 复盘闭环 + JSON 运营记忆：基本完成，并已扩展 SQLite operation memory、表现录入、复盘、运营记忆前端展示。
- M4 创作者平台发布：部分完成。已做私密图文发布低风险子集；公开发布、定时发布、视频发布、发布间随机延时、单日发布限制、风控停手、真实端到端自测仍未完成。
- M5 GraphRAG 运营记忆增强：未完成。
- M6 阶段二软广 + 达人：未完成。
- M17a 已完成最小生产护栏：API token、日志落盘、敏感字段脱敏、运行配置检查和 token 烟测。
- M17b 已完成启动模板：本地 API、SQLite API、SQLite worker 的 PowerShell 模板，并明确优先使用 `D:\Anaconda\envs\ContentShare\python.exe`。
- M19a 已完成创作者平台连接基础适配：默认 mock、真实模式 Cookie 预检、私密图文发布入口、作品列表同步入口和命令行自测。
- M19b 已完成审核 API 显式触发创作者平台私密发布：默认审核仍保存本地草稿，显式参数才触发 mock/真实创作者适配器，并将 creator 发布结果回填 run 与运营记忆。
- M19c 已完成工作台创作者平台发布入口：审核区可勾选私密发布，前端按需发送 M19b 发布确认字段，并展示发布状态、平台笔记 ID 与脱敏错误。
- M20 已完成真实本地图片素材绑定：浏览器选择图片、后端校验 image bytes、保存到 `data/creator_assets/<run_id>/`，发布时读取真实 bytes。
- M21 已完成创作者平台作品列表同步后的表现回填入口：`GET /creator/notes`，`POST /performance` 支持 `creator_note_id`。
- M22 已完成工作台闭环可视化：运营记忆卡片展示创作发布、平台笔记、表现状态、表现分，并能一键填入表现表单。
- M23 已完成工作台运行历史详情与失败诊断：任务结果区展示运行诊断、错误详情，并支持用原任务参数重新提交。
- M24 已完成结构化失败分类：后端返回 `failure_category` / `failure_category_label`，前端优先使用后端分类。
- 最近验证状态：全量测试 `111 passed`，compileall 通过，浏览器 mobile smoke 通过，带 mock 提交的浏览器检查通过且无 console error。

## 从0手册对照后的未完成主线

1. M0/M2/M4 安全护栏补齐：
   - 真实 PC Cookie 自检前置。
   - 真实 creator Cookie 自检前置。
   - 采集/发布随机延时。
   - 单日发布量个位数限制。
   - 风控或 `success=False` 后立即停手，不自动重试轰炸。
   - Cookie 失效提示与重取流程。
2. M4 真实平台端到端：
   - 真实图片素材绑定后私密发布。
   - 返回真实 `creator_note_id`。
   - 同步真实作品列表。
   - 按真实 `creator_note_id` 回填表现。
   - 发布状态轮询尚未完成。
   - 公开视频/公开图文/定时发布尚未完成。
3. M5 GraphRAG 运营记忆增强：
   - 主题 -> 子主题 -> 痛点 -> 内容形式 -> 表现 的图谱关系。
   - 向量检索。
   - 跨主题相似经验召回。
   - 合规风险历史召回。
   - 前端查看召回依据。
4. M6 阶段二软广 + 达人：
   - `platforms/qianfan.py` 未做。
   - `platforms/pugongying.py` 未做。
   - `product_node.py` 未做。
   - 独立 `soft_ad` 生成节点未做。
   - 商品卖点与用户痛点匹配未做。
   - 商业合规审核、70/30 内容比例、单周软广 <= 2、不连发软广未做。
   - 达人匹配与邀约未做。
5. 手册骨架偏离项：
   - `prompts/` 目录目前为空，Prompt 实际放在 `config/llm_prompts.json`。
   - 没有 `routers/content_type_router.py`。
   - 没有 `product_node.py`。
   - 没有 `platforms/qianfan.py` / `platforms/pugongying.py`。
   - 这些不一定要机械照搬，但后续需要决定是补齐手册结构，还是正式记录“以当前结构替代”。

## 当前优先级

1. 不要继续优先做前端细节小功能。
2. 下一步建议进入 M25：平台安全护栏补齐。
3. M25 推荐范围：Cookie 自检前置、采集/发布随机延时、发布频率限制、风控失败停手。
4. M25 完成后，再做真实平台端到端验证。
5. 真实平台稳定后，再进入 M5 GraphRAG；M6 阶段二最后做。

## 当前工作树提示

- M20-M24 相关代码和测试仍在工作区，尚未提交。
- 已知新增计划与测试包括：
  - `docs/superpowers/plans/2026-06-11-creator-image-assets.md`
  - `docs/superpowers/plans/2026-06-11-creator-note-performance-sync.md`
  - `docs/superpowers/plans/2026-06-11-workbench-run-diagnostics.md`
  - `docs/superpowers/plans/2026-06-11-structured-failure-category.md`
  - `tests/test_creator_asset_binding.py`
  - `tests/test_creator_note_performance_sync.py`
  - `tests/test_workbench_creator_assets_static.py`
  - `tests/test_workbench_creator_notes_static.py`
  - `tests/test_workbench_memory_visibility_static.py`
  - `tests/test_workbench_run_diagnostics_static.py`
  - `tests/test_run_failure_category.py`
- 新线程开始后，先跑 `git status --short` 和必要测试，确认工作树仍是这个状态。

## 其他协作注意事项

- `pdf识别` 目录与当前小红书项目无关，可以从当前仓库移除。
- 每次任务结束后，需要更新项目记忆文件，记录当前的进度和未完成的任务。
