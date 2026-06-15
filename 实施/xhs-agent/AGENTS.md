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

当前主项目定位调整为“面试展示用的小红书两阶段多智能体运营系统”。目标不是追求长期生产化大而全，而是在 LangGraph-first 主链上做出相对稳定、可演示、能讲清楚架构取舍的完整两阶段版：阶段一覆盖选题洞察、真实/Mock 评论采集、内容生成、合规、人工确认、私密发布、表现回收、复盘和 GraphRAG 记忆沉淀；阶段二覆盖软广/达人能力的最小闭环，包括商品/卖点输入、软广内容生成、商业合规与频率护栏、达人/平台适配的 mock 或轻量入口。

## 当前阶段

- 按“面试展示用、相对稳的完整两阶段版”重新校准后：阶段一 MVP 与 creator 私密发布闭环已基本站稳，M5 GraphRAG 正在增强；后续不再优先追求公开发布、重型生产部署或复杂平台自动化，而是优先补齐两阶段演示闭环、稳定脚本、清晰记忆链路和可讲述的工程边界。
- M0 环境与链路验证：部分完成。mock 链路和脚本齐全，真实 PC/creator Cookie 已有预检和小流量验证记录；LangGraph-first 迁移后的真实私密发布端到端复验已完成，千帆/蒲公英 Cookie 未进入。
- M1 内容生成最小闭环：基本完成。主题到图文/视频、合规、人工审核、Markdown 保存已可用；`human_review` 已升级为 LangGraph interrupt/resume。
- M2 只读采集：部分完成。已有 collector 薄封装、Spider_XHS 采集、评论去噪、去标识化和候选池评分初版；评论质量评分细化、Cookie 失效产品化提示仍需继续完善。
- M3 复盘闭环 + 运营记忆：基本完成，并已扩展 SQLite operation memory、业务表、表现录入反向同步、复盘、运营记忆前端展示和历史表现补偿脚本。
- M4 创作者平台发布：面试展示版基本够用。已验证 LangGraph-first 私密图文发布、真实图片素材绑定、作品列表同步、发布状态等待、表现回填、平台指标手动/批量同步、脚本循环同步、趋势摘要和工作台同步入口；公开发布、定时发布、公开视频发布和后台常驻调度降为后置项，除非演示必须，不再作为当前完成口径。
- M5 GraphRAG 运营记忆增强：已完成五片规则版闭环，并继续沿 LangGraph-first 主链增强。当前已有基于 operation memory 的图谱视图与 `GET /memory/graph` 查询初版，LangGraph 记忆节点已返回 `graphrag_memory`，策略/生成节点已消费图谱记忆；`rag_eligibility` 已开始控制长期运营记忆写入，工作台已支持轻量查看召回依据、相似经验、历史合规风险、本地 embedding 语义召回和召回解释；召回解释也已进入图文/视频生成的 `memory_context`。脚本级 mock smoke 已能结构化校验 `memory_context_summary`，并可用 `--require-memory-context` / `--min-recall-explanations` / `--require-recall-explanation-type` 对有历史记忆的 LangGraph run 做更强复验；summary 现在会暴露 `semantic_embedding_model`、`semantic_embedding_dimensions`、`semantic_recall_top_score` 和 `semantic_recall_threshold`，`semantic_recall` 解释项也会透出 `embedding_model`、`embedding_dimensions` 与 `semantic_score`，脚本会在命中语义召回但 summary 或解释样本缺少 embedding 元信息、召回分为 0 时失败。`--seed-recall-memory` 已可在临时 SQLite operation memory 中种入可控历史记录和合规留痕，复验 `similar_experience`、`semantic_recall` 与 `historical_compliance_risk` 召回解释。LangGraph 主链顺序已调整为先洞察、再记忆召回，并在 `check_compliance` 后增加合规记忆刷新节点，确保当前痛点、评论洞察和合规问题都能进入图内召回链路。项目内 `local_hashing_embedding_v1` 本地 embedding 语义召回基线已完成；外部 embedding 服务/独立向量数据库、历史大迁移和复杂图谱可视化仍未完成。
- M6 阶段二软广 + 达人：面试展示版尚未完成，是后续主线大头。目标收敛为最小可演示闭环，不追求真实千帆/蒲公英全量自动化。
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
- 最近验证状态：LangGraph M5 语义召回 score summary 与阈值质量门槛已通过；API/smoke/LangGraph 冷启动定点 `5 passed`，相关回归 `39 passed`，M5/LangGraph 相关回归 `59 passed`，全量测试 `333 passed`，`compileall app nodes scripts tests` 通过。此前语义召回解释 embedding 元信息增强通过：`tests/test_memory_graph.py tests/test_memory_context.py` -> `14 passed`，`tests/test_check_api_run_auth.py` -> `15 passed`。可控语义召回 mock HTTP smoke 通过，run `run_087837c15550` 最终 `status=success`、`summary.run_status=waiting_review`、`memory_context_summary.semantic_recall_count=1`，完整 state 中召回解释类型同时包含 `similar_experience`、`semantic_recall` 与 `historical_compliance_risk`。此前历史合规风险 mock HTTP smoke 通过，run `run_5440f2fc2fde` 最终 `status=success`、`summary.run_status=waiting_review`、`compliance_risk_level=medium`、`memory_context_summary.recall_explanation_count=2`，召回解释类型同时包含 `similar_experience` 与 `historical_compliance_risk`；可控相似经验召回解释 mock HTTP smoke、普通 mock HTTP smoke 和强制 memory context mock HTTP smoke 也已通过。旧 SQLite stack 健康/停止/日志脚本定点测试 `9 passed`，健康脚本 `-ConfigOnly` / `-SkipApi` 通过，停止脚本 dry-run 通过，日志脚本通过；真实 creator 只读批量同步通过，`total=2`、`succeeded=2`、`failed=0`。

## 面试展示版未完成主线

1. 阶段一演示稳定性收口：
   - Cookie 失效提示与重取流程保留为轻量工作台/脚本提示，不做复杂账号运维系统。
   - 真实 Cookie 状态在最终演示前做一次小流量复验即可。
   - 采集/发布安全护栏保留现有初版，补最小监控/告警或健康检查说明，不追求长期生产告警平台。
2. M4 真实平台端到端：
   - LangGraph-first 私密图文真实闭环已完成最新复验：`waiting_review -> 绑定真实图片 -> creator 私密发布 -> 作品列表只读同步 -> /performance 回填`。
   - 平台指标同步已有手动、批量、脚本循环和工作台入口；面试版只需要保证可演示和可解释。
   - 公开图文、公开视频、定时发布、复杂告警策略、完整 BI 趋势和统一常驻调度不纳入当前完成口径，除非后续明确要展示。
3. M5 GraphRAG 运营记忆增强：
   - 基于 operation memory 的主题 -> 痛点 -> 内容形式 -> 表现图谱视图已完成初版。
   - 策略/生成节点消费 `graphrag_memory` 已完成初版。
   - 按 `rag_eligibility` 控制可入库长期运营记忆已完成初版。
   - 前端查看召回依据已完成轻量展示初版。
   - 项目内本地 embedding 语义召回基线已完成，召回解释项和生成上下文已保留 embedding 模型、维度与语义分数，API summary 已暴露语义召回最高分与当前阈值；外部 embedding 服务/独立向量数据库仍未完成。
   - 跨主题相似经验召回规则版已完成，embedding/向量语义版已在现有 `semantic_recall_records` 契约上完成第一版本地替换，后续可继续接入可选 provider 或向量索引。
   - 合规风险历史召回规则版已完成，并已通过 LangGraph-first 可控 mock HTTP smoke 复验；历史数据大迁移/质量补标仍未完成。
   - 历史 operation memory 大迁移/质量补标仍未完成。
   - 更完整图谱可视化仍未完成。
4. M6 阶段二软广 + 达人：
   - 需要补最小 `product_node.py` 或等价商品/卖点输入节点。
   - 需要补独立 `soft_ad` 生成节点或等价 LangGraph 分支。
   - 需要商品卖点与用户痛点匹配的轻量规则/LLM 入口。
   - 需要商业合规审核、70/30 内容比例、单周软广 <= 2、不连发软广等演示级护栏。
   - 千帆/蒲公英真实平台适配可用 mock/轻量接口替代，真实 Cookie 和完整自动化后置。
   - 达人匹配与邀约做可演示的数据结构、评分和 mock 流程即可，不追求真实邀约闭环。
5. 手册骨架偏离项：
   - `prompts/` 目录目前为空，Prompt 实际放在 `config/llm_prompts.json`。
   - 没有 `routers/content_type_router.py`。
   - 没有 `product_node.py`。
   - 没有 `platforms/qianfan.py` / `platforms/pugongying.py`。
   - 这些不一定要机械照搬，但后续需要决定是补齐手册结构，还是正式记录“以当前结构替代”。

## 当前优先级

1. 目标口径改为面试展示版：优先完成“相对稳的完整两阶段闭环”，不追求长期生产化大而全。
2. 不要继续优先做前端细节小功能，除非它直接服务演示闭环或面试讲解。
3. 阶段一以 LangGraph-first 私密发布闭环为稳定基线，公开图文、视频、定时发布和复杂常驻调度后置。
4. M5 继续保持轻量：保留本地 embedding/GraphRAG 可观测链路，可做最小 provider 抽象；复杂向量库、历史大迁移和复杂图谱可视化后置。
5. 下一条主线优先进入 M6 面试版最小闭环：商品/卖点输入 -> 软广生成 -> 商业合规/频率护栏 -> 达人/平台 mock 匹配 -> 人工审核。
6. 每轮任务完成后继续更新记忆文档，明确哪些是面试版必做，哪些已降级为后置增强。

## 当前工作树提示

- 最近主线代码已包含 M5 第五片合规留痕与召回解释可见化、召回解释进入 LangGraph 生成上下文、LangGraph M5 smoke 校验增强、可控召回解释 smoke 与节点顺序修复、合规后记忆刷新节点、本地 embedding 语义召回基线、embedding summary/smoke 可观测性质量门槛、`semantic_recall` 解释项的 embedding 元信息透传，以及语义召回 top score/threshold summary；本地 `master` 继续领先 `origin/master`，远端同步主要走现有 PR 分支。上一轮 `codex/m5-rag-eligibility-recall` 推送已恢复并核验到 `0246f8d55d231f7ca09df23191086b55bad25152`。
- 当前合理变更范围是 `app/memory_graph.py`、`nodes/memory_context.py`、`app/api.py`、`scripts/check_api_run.py`、相关测试和项目记忆文件；新线程开始后，先跑 `git status --short --branch` 和必要测试，确认工作树状态。
- 不要并行运行多个 pytest 命令：`pytest.ini` 固定 `--basetemp=data/pytest_tmp_safe`，并行 pytest 会争用同一临时目录，可能导致 setup 阶段 `FileNotFoundError`。
- 远端 `origin/master` 是否已经同步需要重新 `git fetch origin` 后确认；当前环境曾因 `.git/FETCH_HEAD` 权限无法自动 fetch，必要时由用户手动核验。
- 旧 worktree `.worktrees/m5-rag-eligibility-recall-evidence` 已在用户授权后用 `git worktree remove` 清理；本地分支 `codex/m5-rag-eligibility-recall-evidence` 仍保留，后续如确认不再需要可再单独删除。

## 其他协作注意事项

- `pdf识别` 目录与当前小红书项目无关，可以从当前仓库移除。
- 每次任务结束后，需要更新项目记忆文件，记录当前的进度和未完成的任务。
- 所有的文档必须是中文。
