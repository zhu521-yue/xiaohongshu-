# 小红书内容分享项目记忆

## 回复与协作约定

- 每条回复正文开头必须先加：`锋宝：`
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
- M0 环境与链路验证：部分完成。mock 链路和脚本齐全，真实 PC/creator Cookie 已有预检和小流量验证记录；LangGraph-first 迁移后的真实私密发布端到端复验已完成，千帆/蒲公英 Cookie 未进入。
- M1 内容生成最小闭环：基本完成。主题到图文/视频、合规、人工审核、Markdown 保存已可用；`human_review` 已升级为 LangGraph interrupt/resume。
- M2 只读采集：部分完成。已有 collector 薄封装、Spider_XHS 采集、评论去噪、去标识化和候选池评分初版；评论质量评分细化、Cookie 失效产品化提示仍需继续完善。
- M3 复盘闭环 + 运营记忆：基本完成，并已扩展 SQLite operation memory、业务表、表现录入反向同步、复盘、运营记忆前端展示和历史表现补偿脚本。
- M4 创作者平台发布：部分完成。已验证 LangGraph-first 私密图文发布、真实图片素材绑定、作品列表同步、发布状态等待、表现回填、平台指标手动/批量同步、脚本循环同步、趋势摘要和工作台同步入口；公开发布、定时发布、视频发布、后台常驻定时调度仍未完成。
- M5 GraphRAG 运营记忆增强：已完成五片规则版闭环，并继续沿 LangGraph-first 主链增强。当前已有基于 operation memory 的图谱视图与 `GET /memory/graph` 查询初版，LangGraph 记忆节点已返回 `graphrag_memory`，策略/生成节点已消费图谱记忆；`rag_eligibility` 已开始控制长期运营记忆写入，工作台已支持轻量查看召回依据、相似经验、历史合规风险、本地 embedding 语义召回和召回解释；召回解释也已进入图文/视频生成的 `memory_context`。脚本级 mock smoke 已能结构化校验 `memory_context_summary`，并可用 `--require-memory-context` / `--min-recall-explanations` / `--require-recall-explanation-type` 对有历史记忆的 LangGraph run 做更强复验；summary 现在会暴露 `semantic_embedding_model` 和 `semantic_embedding_dimensions`，脚本也会在命中语义召回但 embedding 元信息缺失时失败。`--seed-recall-memory` 已可在临时 SQLite operation memory 中种入可控历史记录和合规留痕，复验 `similar_experience`、`semantic_recall` 与 `historical_compliance_risk` 召回解释。LangGraph 主链顺序已调整为先洞察、再记忆召回，并在 `check_compliance` 后增加合规记忆刷新节点，确保当前痛点、评论洞察和合规问题都能进入图内召回链路。项目内 `local_hashing_embedding_v1` 本地 embedding 语义召回基线已完成；外部 embedding 服务/独立向量数据库、历史大迁移和复杂图谱可视化仍未完成。
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
- M25 已完成平台安全护栏：Cookie 预检、发布日限、随机延时、失败停手和本地 guardrail 状态记录。
- M26 已完成发布状态等待：按需只读轮询 creator 作品列表，避免私密发布后短暂 `not_found` 误判。
- 最新运行时主线已收敛为 LangGraph-first：API/CLI 默认 `engine=langgraph`，`engine=local` 仅保留为显式兼容路径。
- 最近验证状态：LangGraph M5 本地 embedding 召回可观测性增强已通过；`tests/test_api_memory_graph.py tests/test_check_api_run_auth.py` -> `20 passed`，M5/LangGraph 相关回归 `58 passed`，全量测试 `332 passed`，`compileall app nodes scripts tests` 通过。此前本地 embedding 语义召回基线通过：`tests/test_memory_graph.py tests/test_memory_context.py` -> `14 passed`。可控语义召回 mock HTTP smoke 通过，run `run_087837c15550` 最终 `status=success`、`summary.run_status=waiting_review`、`memory_context_summary.semantic_recall_count=1`，完整 state 中召回解释类型同时包含 `similar_experience`、`semantic_recall` 与 `historical_compliance_risk`。此前历史合规风险 mock HTTP smoke 通过，run `run_5440f2fc2fde` 最终 `status=success`、`summary.run_status=waiting_review`、`compliance_risk_level=medium`、`memory_context_summary.recall_explanation_count=2`，召回解释类型同时包含 `similar_experience` 与 `historical_compliance_risk`；可控相似经验召回解释 mock HTTP smoke、普通 mock HTTP smoke 和强制 memory context mock HTTP smoke 也已通过。旧 SQLite stack 健康/停止/日志脚本定点测试 `9 passed`，健康脚本 `-ConfigOnly` / `-SkipApi` 通过，停止脚本 dry-run 通过，日志脚本通过；真实 creator 只读批量同步通过，`total=2`、`succeeded=2`、`failed=0`。

## 从0手册对照后的未完成主线

1. M0/M2/M4 安全护栏产品化：
   - Cookie 失效提示与重取流程仍需更完整的工作台/脚本入口。
   - 真实 Cookie 状态需要在 LangGraph-first 主链小流量复验前重新确认。
   - 采集/发布安全护栏已有初版，后续继续补长期运行监控和告警。
2. M4 真实平台端到端：
   - LangGraph-first 私密图文真实闭环已完成最新复验：`waiting_review -> 绑定真实图片 -> creator 私密发布 -> 作品列表只读同步 -> /performance 回填`。
   - 平台指标自动抓取已有手动/批量/脚本循环/工作台入口和脚本级后台调度器：`POST /creator/notes/performance-sync`、`POST /creator/notes/performance-sync/batch`、`scripts/sync_creator_note_performance.py` 和 `scripts/run_creator_performance_scheduler.py` 可从作品列表快照回填 `/performance`；统一进程编排、告警策略和完整 BI 趋势仍未完成。
   - 公开视频/公开图文/定时发布尚未完成。
3. M5 GraphRAG 运营记忆增强：
   - 基于 operation memory 的主题 -> 痛点 -> 内容形式 -> 表现图谱视图已完成初版。
   - 策略/生成节点消费 `graphrag_memory` 已完成初版。
   - 按 `rag_eligibility` 控制可入库长期运营记忆已完成初版。
   - 前端查看召回依据已完成轻量展示初版。
   - 项目内本地 embedding 语义召回基线已完成，外部 embedding 服务/独立向量数据库仍未完成。
   - 跨主题相似经验召回规则版已完成，embedding/向量语义版已在现有 `semantic_recall_records` 契约上完成第一版本地替换，后续可继续接入可选 provider 或向量索引。
   - 合规风险历史召回规则版已完成，并已通过 LangGraph-first 可控 mock HTTP smoke 复验；历史数据大迁移/质量补标仍未完成。
   - 历史 operation memory 大迁移/质量补标仍未完成。
   - 更完整图谱可视化仍未完成。
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
2. 把本次 LangGraph-first 真实私密发布复验作为 M4 私密图文最新稳定基线。
3. 下一步继续 M5 或阶段一收口：优先保持 LangGraph-first 主链稳定，先做真实小流量复验；如继续 M5，则基于现有本地 embedding 召回契约评估可选 embedding provider 或小型向量索引，工作台批量选择和复杂图谱可视化可后置。
4. 公开图文、视频、定时发布继续后置，执行前必须重新确认平台写入风险。
5. M6 阶段二软广和达人能力最后做。

## 当前工作树提示

- 最近主线代码已包含 M5 第五片合规留痕与召回解释可见化、召回解释进入 LangGraph 生成上下文、LangGraph M5 smoke 校验增强、可控召回解释 smoke 与节点顺序修复、合规后记忆刷新节点、本地 embedding 语义召回基线，以及 embedding summary/smoke 可观测性质量门槛；本地 `master` 继续领先 `origin/master`，远端同步主要走现有 PR 分支。
- 当前合理变更范围是 `app/memory_graph.py`、`nodes/memory_context.py`、`app/api.py`、`scripts/check_api_run.py`、相关测试和项目记忆文件；新线程开始后，先跑 `git status --short --branch` 和必要测试，确认工作树状态。
- 不要并行运行多个 pytest 命令：`pytest.ini` 固定 `--basetemp=data/pytest_tmp_safe`，并行 pytest 会争用同一临时目录，可能导致 setup 阶段 `FileNotFoundError`。
- 远端 `origin/master` 是否已经同步需要重新 `git fetch origin` 后确认；当前环境曾因 `.git/FETCH_HEAD` 权限无法自动 fetch，必要时由用户手动核验。
- 旧 worktree `.worktrees/m5-rag-eligibility-recall-evidence` 已在用户授权后用 `git worktree remove` 清理；本地分支 `codex/m5-rag-eligibility-recall-evidence` 仍保留，后续如确认不再需要可再单独删除。

## 其他协作注意事项

- `pdf识别` 目录与当前小红书项目无关，可以从当前仓库移除。
- 每次任务结束后，需要更新项目记忆文件，记录当前的进度和未完成的任务。
- 所有的文档必须是中文。
