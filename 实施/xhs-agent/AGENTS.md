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
- 原始主线依据是 `从0实现指导手册.md`，后续判断"还剩哪些任务"必须优先对照这份手册的 M0-M6，而不是只看最近工程迭代。

## 当前项目目标

当前主项目定位为"面试展示用的小红书两阶段多智能体运营系统"。目标不是追求长期生产化大而全，而是在 LangGraph-first 主链上做出相对稳定、可演示、能讲清楚架构取舍的完整两阶段版：阶段一覆盖选题洞察、真实/Mock 评论采集、内容生成、合规、人工确认、私密发布、表现回收、复盘和 GraphRAG 记忆沉淀；阶段二覆盖软广/达人能力的最小闭环，包括商品/卖点输入、软广内容生成、商业合规与频率护栏、达人/平台适配的 mock 或轻量入口。

## 当前阶段

- 两阶段完整闭环已基本站稳。M0-M6 主线全部完成，面试版核心能力就绪。
- M0 环境与链路验证：完成。mock 链路和脚本齐全，真实 PC/creator Cookie 已有预检和小流量验证记录；千帆/蒲公英 Cookie 为 mock，不追求真实对接。
- M1 内容生成最小闭环：完成。主题到图文/视频、合规、人工审核、Markdown 保存已可用；`human_review` 已升级为 LangGraph interrupt/resume。
- M2 只读采集：完成。已有 collector 薄封装、Spider_XHS 采集、评论去噪、去标识化和候选池评分初版；Cookie 失效提示待补最小轻量版本。
- M3 复盘闭环 + 运营记忆：完成。已有 SQLite operation memory、业务表、表现录入反向同步、复盘、运营记忆前端展示和历史表现补偿脚本。
- M4 创作者平台发布：完成。LangGraph-first 私密图文发布闭环已完成最新复验；平台指标同步已有手动、批量、脚本循环和工作台入口；公开发布、定时发布、公开视频发布和后台常驻调度已降级为后置。
- M5 GraphRAG 运营记忆增强：完成。基于 operation memory 的图谱视图与 API 查询、策略/生成节点消费图谱记忆、`rag_eligibility` 控制长期运营记忆写入、工作台轻量召回依据查看、本地 embedding 语义召回基线、合规后记忆刷新节点均已完成；外部 embedding 服务/独立向量数据库、历史大迁移和复杂图谱可视化已降级为后置。
- M6 阶段二软广 + 达人：完成。新增 `product_node`（千帆 mock 选品+痛点匹配）、`soft_ad_node`（LLM 优先+模板兜底）、`route_content_type`（两级路由）、`platforms/qianfan.py` 和 `platforms/pugongying.py`（mock adapter）、软广专属合规规则、频率护栏（本周≤2篇+不连发）、CLI `--stage monetization_ready --product-name` 和 API `stage_override` 支持。
- M17a 已完成最小生产护栏：API token、日志落盘、敏感字段脱敏、运行配置检查和 token 烟测。
- M17b 已完成启动模板：本地 API、SQLite API、SQLite worker 的 PowerShell 模板。
- M19a-M26 已完成创作者平台链路、工作台闭环可视化、失败诊断、安全护栏等。
- 最新运行时主线为 LangGraph-first：API/CLI 默认 `engine=langgraph`。
- 最近验证状态：全量测试 `353 passed`（333 回归 + 20 M6 新增），`compileall app nodes routers platforms memory llm` 通过，软广告端到端 smoke 通过（`content_type: soft_ad, publish_status: success`）。

## 面试展示版未完成主线

1. 阶段一演示稳定性收口：
   - Cookie 失效提示与重取流程保留为轻量工作台/脚本提示。
   - 真实 Cookie 状态在最终演示前做一次小流量复验即可。
   - 采集/发布安全护栏保留现有初版，补最小监控/告警或健康检查说明。
2. 手册骨架对齐：
   - `prompts/` 目录目前为空，Prompt 实际放在 `config/llm_prompts.json`——正式记录"以当前结构替代"。
   - 之前缺失的 `product_node.py`、`routers/content_type_router.py`、`platforms/qianfan.py`、`platforms/pugongying.py` 已全部补齐。
3. 后置增强项（不做）：
   - 公开发布、定时发布、公开视频、复杂告警策略、完整 BI 趋势和统一常驻调度。
   - 外部 embedding 服务/独立向量数据库、历史操作记忆大迁移/质量补标、复杂图谱可视化。
   - 真实千帆/蒲公英全量自动化、达人真实邀约闭环。

## 当前优先级

1. 阶段一演示稳定性收口：Cookie 失效轻量提示、安全护栏健康检查说明。
2. 端到端演示预演：用真实参数完整走通阶段一+阶段二链路，确认可演示。
3. 面试讲解材料准备：LangGraph 图结构梳理、架构决策说明、两阶段递进逻辑。
4. 不再做前端细节小功能，除非它直接服务演示闭环或面试讲解。

## 当前工作树提示

- `master` 与 `origin/master` 同步。
- 当前合理变更范围是全项目，M6 新增文件已全部稳定。
- 不要并行运行多个 pytest 命令：`pytest.ini` 固定 `--basetemp=data/pytest_tmp_safe`，并行 pytest 会争用同一临时目录。
- 旧 worktree 和备份分支如需清理可在后续单独处理。

## 其他协作注意事项

- `pdf识别` 目录与当前小红书项目无关，可以从当前仓库移除。
- 每次任务结束后，需要更新项目记忆文件，记录当前的进度和未完成的任务。
- 所有的文档必须是中文。
