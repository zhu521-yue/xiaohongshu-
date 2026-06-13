# 项目进度与工程路线图

更新时间：2026-06-13

本文档用于记录当前项目的全局状态、我们期待实现的工程形态，以及尚未实现的关键环节。它不记录长测试输出，只记录对后续开发有价值的结论。

## 1. 项目目标

本项目目标是实现一套“小红书内容生成 Agent”系统，面向小红书冷启动账号，帮助完成从选题洞察到内容草稿生成、人工审核、运营记忆沉淀、表现复盘的闭环。

理想完整流程：

1. 用户提交主题、目标用户、内容形式。
2. 系统采集小红书搜索结果和评论。
3. 系统清洗评论噪声，提取用户痛点和内容机会。
4. 系统读取历史运营记忆，寻找同主题或相近主题的成功结构。
5. 系统决定内容策略，例如知识分享、步骤教程、避坑、问答、经验总结。
6. 系统调用 LLM 生成图文或视频脚本，要求结构化 JSON 输出。
7. 系统执行合规检查和文本安全清洗。
8. 内容进入人工审核状态。
9. 人工审核通过后保存 Markdown 草稿。
10. 发布后人工录入真实表现数据。
11. 系统根据表现数据生成复盘，并沉淀可复用经验。
12. 后续同类主题生成时复用高表现结构，但继续用新评论验证选题。

当前定位：已经完成 MVP 主链路，正在从“能跑通”进入“工程化、可部署、可扩展、可长期维护”阶段。

## 2. 当前已完成的能力

### 2.1 LangGraph 主流程

已完成：

- 建立 LangGraph 工作流。
- 节点已覆盖：主题洞察、记忆读取、策略选择、图文生成、视频生成、合规检查、人工审核、发布保存、复盘、运营记忆写入。
- 支持 `local` 和 `langgraph` 两种执行方式。
- 已确认 LangGraph 路由逻辑可运行。

当前状态：

- LangGraph 作为主流程编排已可用。
- 人工审核当前仍是 API 层继续执行保存，不是 LangGraph 原生 interrupt/resume。

### 2.2 小红书采集

已完成：

- 接入 `vendor/Spider_XHS`。
- 可以搜索公开笔记。
- 可以读取公开评论。
- 已增加采集延迟配置，降低请求过快风险。
- 已做去标识化处理，不保留昵称、头像、主页、用户 ID、评论 ID。
- 已过滤明显无效笔记。
- 已过滤评论噪声，包括互粉、回复 1、群邀请、引流、低价值短评论等。
- 已记录评论抓取错误，例如 cookie 过期、请求失败。

当前状态：

- cookie 有效时，真实采集可以跑通。
- cookie 失效时，会返回 `comment_fetch_errors`，内容会回退到主题级默认痛点或历史记忆。
- 采集仍依赖第三方逆向库，稳定性受平台变更、登录态、网络环境影响。

### 2.3 评论洞察

已完成：

- 评论痛点提取从单一“宝宝湿疹护理”场景，升级为“通用规则 + 领域规则”。
- 健康护理类规则只在宝宝、湿疹、热疹、皮疹、护理等主题命中时启用。
- 通用规则覆盖：
  - 真实性怀疑
  - 不知道从哪里开始
  - 需要具体干货
  - 担心试错和被骗
  - 想获得收益或独立能力
  - 希望有人判断是否适合自己
- 已过滤噪声评论，避免互粉和引流评论进入痛点证据。

当前状态：

- 规则系统足够支撑 MVP。
- 还不是最终智能聚类方案。
- 后续可引入 LLM 或 embedding 做更稳的语义聚类和领域适配。

### 2.4 LLM 接入

已完成：

- DeepSeek OpenAI-compatible 接口已接入。
- 支持真实 LLM 和 mock 模式。
- 图文和视频脚本使用 JSON 输出模式。
- 已把 prompt 移到 `config/llm_prompts.json`。
- 已增加 prompt 约束：
  - 不输出 Markdown。
  - 不解释。
  - 避免绝对化承诺。
  - 不承诺爆款、必火、暴涨、快速涨粉。
  - 不虚构个人经历、验证次数、收益结果或亲测背书。
  - 非健康主题禁止套用健康、护理、诊断、治疗类表达。

当前状态：

- 真实 LLM 图文生成链路可用。
- 结构化 JSON 可用，但仍需要本地校验和兜底。
- LLM 文案质量仍需要长期迭代，尤其是可信表达和平台风格。

### 2.5 内容生成

已完成：

- 支持图文草稿生成。
- 支持视频脚本生成。
- 支持根据 `successful_patterns` 复用高表现内容结构。
- 支持多种结构：
  - `knowledge_share`
  - `experience_summary`
  - `avoid_mistakes`
  - `qa_education`
  - `step_tutorial`
- 已修复实际结构和 state 中 `content_type` 不一致的问题。
- 已修复跨领域污染问题，例如小红书选题主题不再输出宝宝护理类痛点。
- 已增加中文文本清洗：
  - 清理中文异常空格。
  - 保留数字和单位之间的正常空格。
  - 修复标点前后的异常空格。
- 已增加可信表达替换：
  - `实测可行` -> `可以按步骤验证`
  - `照着做就行` -> `可以照着步骤先试`
  - `刷了100篇才懂` -> `看了很多案例后整理`
  - `直接抄作业` -> `可以参考这个步骤`
  - `少走半年弯路` -> `少走一些弯路`

当前状态：

- 内容主链路已稳定。
- 内容质量仍是细节优化项，不应阻塞工程主线。

### 2.6 合规检查

已完成：

- 已配置绝对词、敏感主题、免责声明、禁止承诺词。
- 支持低、中、高风险判断。
- 中风险内容会补充安全提示。
- 高风险内容不能直接人工审核通过。
- 健康类主题会加入“经验分享、不替代诊断”的边界。

当前状态：

- MVP 合规可用。
- 合规仍是规则系统，后续需要更细的行业、平台、广告、安全、医疗、金融等规则分层。

### 2.7 运营记忆

已完成：

- 使用 `memory/operation_history.json` 作为第一阶段持久记忆。
- 已支持：
  - 保存草稿记录。
  - 写入主题、目标用户、内容类型、标题、痛点、评论证据。
  - 录入表现数据。
  - 计算表现分。
  - 生成运营复盘。
  - 检索历史相关记录。
  - 提取 `successful_patterns`。
- 已修复历史记忆污染：
  - 非健康主题不会读取湿疹、热疹、擦药、诊断等健康类旧记录。
  - 已修复旧的“小红书新手选题方法”污染记录。
- 已保留修复备份：
  - `memory/operation_history.json.backup_20260610_160400`

当前状态：

- JSON 记忆适合 MVP。
- 不适合高并发、多进程、生产部署。
- 后续需要升级为数据库和向量检索。

### 2.8 API 服务

已完成：

- 支持提交运行任务。
- 支持查询运行结果。
- 支持查询队列状态。
- 支持人工审核通过和驳回。
- API 会保存 run state，便于审核后继续保存草稿和写运营记忆。
- 已把 run 存储从 `app/api.py` 拆到 `app/run_store.py`。
- 已把本地队列从 `app/api.py` 拆到 `app/run_queue.py`。
- 支持本地 worker 数配置：`XHS_AGENT_LOCAL_WORKERS`。

当前状态：

- 当前队列仍是本进程内本地队列。
- 当前 run store 仍是本地 JSON 文件。
- 适合本地开发，不适合生产高并发。

### 2.9 本地存储可靠性

已完成：

- 新增 `app/json_store.py`。
- JSON 和 Markdown 写入改为原子写入。
- 读到损坏 JSON 时会隔离到 `corrupt/`。
- `operation_history.json` 写入有线程锁。

当前状态：

- 单进程和本地开发足够。
- 多进程部署仍需要数据库或跨进程锁。

### 2.10 前端工作台

已完成：

- 有基础工作台页面。
- 支持提交任务。
- 支持展示运行状态、摘要、内容结果。
- 支持人工审核通过和驳回入口。
- 已用 Playwright 做过基础 UI 检查。

当前状态：

- 仍是 MVP 工作台。
- 缺少生产级体验，例如运行历史详情、失败任务详情、筛选、表现录入 UI、记忆查看 UI。

## 3. 当前系统大致架构

当前运行形态：

```text
用户/前端/脚本
  -> app/api.py
  -> LocalRunQueue
  -> LangGraph workflow
  -> collector / memory / strategy / LLM / compliance / review
  -> LocalRunStore JSON
  -> operation_history JSON
  -> Markdown output
```

当前关键目录：

```text
app/        API、配置、队列、run 存储、JSON 存储
nodes/      LangGraph 业务节点
routers/    LangGraph 路由函数
platforms/  小红书采集和评论分析
llm/        LLM 客户端和 prompt 渲染
config/     外置业务规则和 prompt
memory/     当前进度、运营记忆、记忆存储逻辑
scripts/    检查、运行、录入表现、修复脚本
output/     Markdown 草稿输出
vendor/     Spider_XHS 逆向采集依赖
```

## 4. 我们期待的最终工程实现

### 4.1 后端服务形态

目标形态：

```text
Web/API 进程
  -> PostgreSQL/SQLite run store
  -> Redis/RQ/Celery queue
  -> Worker 进程池
  -> LangGraph workflow
  -> Object/file storage
  -> Operation memory DB
```

期望能力：

- API 进程只负责接收请求、查询状态、人工审核。
- Worker 进程负责耗时任务：采集、LLM、内容生成、复盘。
- 队列支持重试、失败记录、超时、取消、并发控制。
- 状态存储从 JSON 文件升级到数据库。
- 操作日志可追踪。
- 运行记录可审计。

### 4.2 数据库目标

建议先做 SQLite 兼容模型，后续迁移 PostgreSQL。

核心表建议：

- `runs`
  - run_id
  - status
  - request_payload
  - summary
  - state
  - error
  - created_at
  - started_at
  - finished_at
- `operation_records`
  - record_id
  - topic
  - target_user
  - content_type
  - content_format
  - titles
  - pain_points
  - comment_insights
  - post_id
  - publish_status
  - performance_data
  - performance_score
  - review_summary
  - next_action
- `collections`
  - collection_id
  - topic
  - raw_notes
  - raw_comments
  - comment_fetch_errors
  - created_at
- `drafts`
  - draft_id
  - run_id
  - title
  - body
  - image_page_plan
  - video_script
  - markdown_path
  - status
- `audit_events`
  - event_id
  - run_id
  - operator
  - action
  - feedback
  - created_at

### 4.3 队列目标

目标能力：

- 支持多个 worker 并发处理。
- 支持任务重试。
- 支持任务超时。
- 支持任务取消。
- 支持失败原因记录。
- 支持队列长度和运行中任务监控。
- 支持不同任务类型拆分队列，例如采集、生成、复盘。

可选方案：

- Redis + RQ：简单直接，适合当前阶段。
- Redis + Celery：功能更完整，适合更复杂任务编排。
- Dramatiq：也可行，但生态和团队熟悉度需评估。

建议路径：

1. 先抽象 queue interface。
2. 保留 LocalRunQueue 作为开发模式。
3. 新增 RedisRunQueue 或 RQRunQueue。
4. API 与 worker 进程拆开启动。

### 4.4 记忆系统目标

当前是 JSON 运营记忆。

目标是分三层：

1. 操作记忆
   - 记录每次生成、发布、表现、复盘。
2. 模式记忆
   - 从高表现内容中提取结构、标题风格、痛点切入。
3. 语义记忆
   - 用 embedding/GraphRAG 检索相似主题、相似用户痛点、相似内容结构。

后续实现方向：

- PostgreSQL 保存结构化记录。
- 向量数据库或 PostgreSQL pgvector 保存语义索引。
- 给每条记忆增加来源、可信度、适用范围和过期机制。
- 避免旧记录长期污染新主题。

### 4.5 前端工作台目标

目标功能：

- 新建内容任务。
- 查看任务列表。
- 查看任务详情。
- 查看采集结果和痛点证据。
- 查看生成内容。
- 人工审核通过/驳回。
- 编辑或反馈生成内容。
- 录入发布后表现数据。
- 查看运营记忆。
- 查看同类主题历史表现。
- 查看失败原因和重试按钮。

当前前端还只是 MVP，需要后续系统化改造。

### 4.6 部署目标

目标部署形态：

```text
Nginx
  -> API service
  -> frontend static files

API service
  -> PostgreSQL
  -> Redis
  -> Worker service

Worker service
  -> Spider_XHS
  -> LLM provider
  -> file/object storage
```

需要补齐：

- `.env.production`
- 启动脚本
- systemd 或 Docker Compose
- 日志目录
- 健康检查
- 进程守护
- 备份策略
- API 鉴权
- HTTPS / 反向代理配置

## 5. 尚未实现的关键环节

### 5.1 高并发生产化

未完成：

- 数据库 run store。
- Redis/Celery/RQ 外部队列。
- API 和 worker 进程拆分。
- 多 worker 横向扩容。
- 任务重试、取消、超时。
- 队列监控。

优先级：高。

原因：这是未来部署到服务器并支持多人/多任务使用的基础。

### 5.2 数据库落地

未完成：

- 数据库 schema。
- ORM 或 SQL 访问层。
- JSON run 文件迁移。
- operation_history JSON 迁移。
- 数据库备份。
- 数据库版本迁移工具。

优先级：高。

建议下一步先做 SQLite/PostgreSQL 兼容数据层，不要一上来直接做复杂 GraphRAG。

### 5.3 生产级 API 鉴权

未完成：

- 登录/鉴权。
- API token。
- 用户隔离。
- 操作权限。
- 审核人记录。

优先级：高。

原因：部署到服务器后不能裸奔，否则任何人都能触发采集、消耗 LLM token、读取历史结果。

### 5.4 采集稳定性

未完成：

- cookie 状态检测和过期提醒。
- cookie 更新工作流。
- 采集失败重试。
- 平台限流处理。
- 采集结果质量评分。
- 对无标题、高互动但低相关笔记的过滤优化。
- 更强的反引流、反水军评论过滤。

优先级：中高。

说明：采集是内容质量的上游，稳定性会直接影响生成质量。

### 5.5 LLM 输出质量治理

未完成：

- 更细的文案风格控制。
- 标题可信度评分。
- 虚构经历检测。
- 过度承诺检测。
- 小红书风格但不夸张的表达模板。
- 生成后自检节点。
- 多候选内容打分筛选。

优先级：中。

说明：这属于内容质量细节，不应该阻塞高并发和部署主线，但需要持续迭代。

### 5.6 人工审核工作流

未完成：

- 审核意见输入。
- 驳回后重新生成。
- 审核通过后手动编辑内容。
- 审核事件记录。
- 审核人身份。
- 审核状态在前端更清晰展示。

优先级：中。

当前已有 API 层审核基础，但还不是完整内容生产工作台。

### 5.7 发布与平台操作

未完成：

- 自动发布到小红书。
- 图片生成和排版。
- 视频生成。
- 封面生成。
- 多图导出。
- 发布时间计划。
- 发布状态回填。

优先级：中。

当前项目更适合作为“生成草稿 + 人工发布”的系统。自动发布涉及平台风控和账号安全，应谨慎。

### 5.7.1 小红书生态平台连接扩展

未完成：

- 创作者平台登录状态和 Cookie 管理。
- 创作者平台私密发布测试。
- 图文/视频上传能力封装。
- 已发布作品列表同步。
- 发布状态回填到 run 和运营记忆。
- 蒲公英达人/KOL 数据调研。
- 千帆分销/商品数据调研。
- 写入类操作的人工确认硬门槛。

优先级：中。

说明：`Spider_XHS` 不只包含 PC 端只读采集，还包含创作者平台、蒲公英、千帆等小红书生态入口。当前系统只接入了 PC 端搜索、笔记详情和评论采集。后续可以把创作者平台作为发布和回填链路的第一阶段扩展，蒲公英和千帆先做业务价值评估，不直接进入主链路。

### 5.8 表现数据闭环

未完成：

- 前端录入表现数据。
- 自动关联草稿和真实发布链接。
- 定时提醒录入数据。
- 表现趋势分析。
- 同类主题对比。
- 复盘结果可视化。

优先级：中。

当前表现数据可以用脚本录入，但还不是完整运营闭环。

### 5.9 测试体系

未完成：

- 单元测试系统化。
- API 集成测试。
- LangGraph 节点测试。
- LLM mock snapshot 测试。
- 采集 mock 测试。
- 前端自动化测试常规化。
- 回归测试脚本。

优先级：中高。

说明：现在靠手动命令验证较多，后续工程规模变大后必须补测试。

### 5.10 日志、监控、告警

未完成：

- 结构化日志。
- 每个 run 的节点耗时。
- LLM token 成本统计。
- 采集失败率。
- 队列积压监控。
- worker 异常告警。
- API 访问日志。

优先级：中。

部署到服务器前至少需要基础日志和成本统计。

### 5.11 配置与安全

未完成：

- `.env.example` 继续完善。
- 生产环境配置模板。
- 密钥脱敏展示。
- cookie 加密存储。
- LLM key 安全管理。
- 禁止把 `.env` 打包泄露。
- 敏感日志清理。

优先级：高。

原因：涉及真实账号 cookie 和 LLM API key。

## 6. 当前优先级排序

建议当前不要继续陷入文案细节，而是按下面顺序推进：

### P0：工程主线

1. 数据库模型设计。
2. RunStore 从 JSON 抽象到 SQLite/PostgreSQL。
3. Operation memory 从 JSON 迁移到数据库。
4. Redis/RQ 或 Celery 队列接入。
5. API 和 worker 拆分。
6. 部署配置和启动脚本。

### P1：可用性和安全

1. API 鉴权。
2. 前端运行历史。
3. 审核反馈输入。
4. 表现数据录入 UI。
5. 日志和错误详情。
6. cookie 过期提醒。

### P2：内容质量专项

1. 标题可信度优化。
2. 文案风格统一。
3. 生成后自检节点。
4. 评论洞察 LLM/embedding 聚类。
5. 更强的噪声评论和引流识别。

### P3：高级能力

1. 自动图片生成和排版。
2. 视频脚本到视频生产。
3. 自动发布或半自动发布。
4. 小红书创作者平台私密发布和作品列表同步。
5. 蒲公英/千帆数据调研。
6. GraphRAG/语义记忆。
7. 多账号管理。

## 7. 当前阶段结论

当前项目不是一个只停留在 demo 的状态，已经具备 MVP 主链路：

- 能采集。
- 能分析评论痛点。
- 能读取历史记忆。
- 能调用真实 LLM。
- 能生成结构化内容。
- 能做基础合规。
- 能等待人工审核。
- 能保存草稿和运营记忆。
- 能录入表现数据并复盘。

但它还不是生产级系统。

当前最大缺口不是内容生成，而是工程化：

- 本地 JSON 存储要升级为数据库。
- 本地队列要升级为外部队列。
- API 和 worker 要拆分。
- 部署、安全、日志、测试要补齐。

下一阶段建议正式进入“数据库与外部队列改造”。

## 8. 2026-06-11 主链真实验证补充

已完成一次真实主链小流量验证，不再只停留在 mock：

- 使用 `COLLECTOR_MODE=spider_xhs`、`engine=langgraph`、`LLM_MODEL_NAME=deepseek-v4-pro`。
- 非沙箱网络 API 端口：`8013`。
- 真实 run：`run_c91c97a1d502`。
- 结果：`success`。
- 真实采集：1 篇笔记、9 条评论，评论采集错误为 0。
- 真实 LLM：`openai_compatible`，模型 `deepseek-v4-pro`，总 token 3315。
- 合规：低风险。
- 日志：`data/logs/api.log` 已落盘记录。

当前判断更新：

- 主链路“真实采集 -> LangGraph -> 运营记忆召回 -> 真实 LLM -> 合规 -> 待人工审核”已通过小流量验证。
- 不能再把系统状态概括为“主要还是 mock”。mock 仍是默认回归档，但真实主链已经可跑。
- 后续重点应从“能否跑通”转为“如何稳定、可观测、可恢复地跑”：进程启动模板、日志、失败分类、脚本编码、Cookie 自检、数据库/队列工程化。

注意事项：

- 普通沙箱网络会导致外部请求走 `127.0.0.1:9` 并失败；真实小红书和真实 LLM 验证必须用非沙箱网络启动 API。
- `scripts/check_api_run.py` 在 Windows GBK 控制台可能因 emoji 输出触发 `UnicodeEncodeError`，需要修复为 UTF-8 友好输出。

## 9. 采集策略与 RAG 基础方向

后续 RAG 的基础不应是“互动最高笔记”的简单堆叠，而应是“高相关 + 高质量互动”的候选池。

采集排序建议：

- 主题相关度优先。
- 评论数、点赞数、收藏数作为互动因子。
- 评论质量作为核心因子，优先保留真实问题、真实反对意见、真实使用场景。
- 对互粉、引流、水军、抽奖、低相关情绪评论做惩罚或过滤。
- 兼顾近期性和账号体量，避免只学习大号爆款或过旧内容。

实施状态：

- 主链后半段真实闭环已经通过：私密发布、状态同步和表现回填都已验证。
- 候选池评分初版已经完成：真实采集会先扩大候选池，再按主题相关度、互动和评论质量信号排序选样本。
- 下一步应进入“基础数据分析报告 + 评论质量评分细化 + RAG 入库结构”专项。
- GraphRAG 应建立在稳定采集、稳定表现回填和可解释候选评分之后，而不是先做复杂图谱。

## 10. 2026-06-12 主链后半段真实闭环补充

已完成一次完整后半段真实闭环：

- 新 run：`run_d2572a74de62`。
- 绑定图片素材：`creator_images_count=1`。
- 创作者平台私密发布：`creator_publish_status=success`。
- 模式：`spider_xhs`。
- 平台笔记 ID：`6a2adc0c000000003502cd53`。
- 状态同步：`status=synced`，`visibility_label=仅自己可见`。
- 表现回填：`op_247efc20de96` 更新为 `performance_recorded`，初始表现分 0。

当前判断更新：

- 主链路已从“真实采集 + LangGraph + 真实 LLM”推进到“私密发布 + 平台状态同步 + 表现回填”。
- 当前最大功能缺口不再是能否完成闭环，而是稳定性、素材质量和工程化。
- 采集阶段暴露出候选选择问题：本次真实搜索第一条笔记评论数为 0，后续必须做候选池评分。
- 发布状态同步存在短暂延迟，后续应设计轮询而不是只查一次。
- 下一步可以独立尝试“根据文本生成图片素材”，再复用现有 `creator-assets` 和私密发布流程。
- 图片生成方向需要新增 OpenAI 图片配置，目前 `.env` 尚未配置 `OPENAI_API_KEY` 或图片模型变量；不能复用当前 DeepSeek 文本 LLM key。

## 11. 2026-06-12 GPT-image-2 生图素材链路状态

已新增 OpenAI 图片生成最小链路：

- `platforms/openai_image.py`：读取图片配置、构造 run 图像提示词、调用 OpenAI Images API、保存生成图。
- `scripts/generate_creator_image_asset.py`：从 run 读取内容，生成图片，并可选绑定到 `creator-assets`。
- `.env.example`：补充 `OPENAI_API_KEY`、`OPENAI_BASE_URL`、`OPENAI_IMAGE_MODEL`、图片尺寸、格式和超时配置。
- 测试覆盖：图片配置、请求 payload、base64 解码、错误脱敏、图片保存、脚本绑定 payload、`prompt-out` 自动建目录。

最新验证：

- 早期真实请求曾返回 HTTP 401 `invalid_api_key`，随后又因错误 Key 返回 `This token has no access to model gpt-image-2`。
- 用户更换正确 Key 后，`https://api.xrouter.dev/v1/models` 可见 `gpt-image-2`。
- 本地 `.env` 的 `OPENAI_BASE_URL` 需要配置为 `https://api.xrouter.dev/v1`；少 `/v1` 会请求到 HTML 页面并导致 `OpenAI image response is not valid JSON`。
- 使用 `run_fda76a64a278` 已完成真实生图并绑定到 creator assets：
  - 生成图：`data/generated_assets/run_fda76a64a278/20260612_162936_openai_cover.png`
  - 绑定图：`data/creator_assets/run_fda76a64a278/01_20260612_162936_openai_cover.png`
  - `creator_images_count=1`
- 相关回归：`tests/test_openai_image_generation.py`、`tests/test_generate_creator_image_asset.py`、`tests/test_creator_asset_binding.py` 共 `12 passed`。

当前结论：

- GPT-image-2 生图素材链路已从“工程就绪但外部 Key/通道阻塞”更新为“真实生图通过并可绑定 run”。
- 当前还没有在本轮触发真实 creator 私密发布；下一步如要继续后半段闭环，可基于已绑定图片的 `run_fda76a64a278` 做人工确认后的私密发布验证。

## 12. 2026-06-12 M25 平台护栏状态入口

用户决定先暂停生图问题，继续主流程。当前推进点：

- 底层已有创作者发布日限、失败停手、发布前 Cookie 自检、发布前随机延时、采集端 Cookie 自检。
- 新增 `GET /platform/status` 只读接口，汇总：
  - `collector_runtime`
  - `creator_runtime`
  - `creator_publish_guardrail`
- 该接口不触发真实采集或发布，只用于主链提交/发布前检查当前平台状态。
- 相关回归 `47 passed`，`app/api.py` 编译通过。

最新补充：

- 工作台已接入 `/platform/status`，侧边栏展示采集端、创作者端和发布护栏状态。
- `scripts/check_workbench_ui.py` 已增加平台状态面板检查。
- 最新验证：全量测试 `143 passed`，`compileall app platforms scripts` 通过，desktop/mobile 浏览器 smoke 均为 `ok=true` 且无 console error。

下一步：

- 发布状态轮询/等待已完成：后端提供只读等待函数，API 支持 `wait=true` / `attempts` / `interval_seconds`，工作台作品列表可按单条作品刷新状态。
- 真实后半段验证已通过：`run_fda76a64a278` 使用已绑定 GPT-image-2 图片素材完成 creator 私密发布，平台笔记 ID 为 `6a2bce0b000000003502c564`，等待状态同步返回 `status=synced`，并已按真实 `creator_note_id` 回填表现到 `op_3ad88ee563ba`。
- 采集候选池评分初版已完成，真实采集会返回 `collection_candidates`、候选评分和入选标记，为后续 RAG 入库质量打基础。
- 基础数据分析报告初版已完成：run/API 和采集诊断脚本会返回 `analysis_report`，解释样本来源、评论质量、痛点可信度、内容结构建议和风险。
- 数据库基础表 schema 初始化已完成：新增 foundation 业务表初始化入口，先建表和索引，不改变当前 API/JSON 行为。
- 业务表核心快照旁路写入初版已完成：可显式把 run state 同步到 `raw_notes`、`collection_candidates`、`raw_comments`、`analysis_reports`。
- 下一步建议把旁路写入挂到 run 成功保存流程后面，并受 `XHS_AGENT_BUSINESS_TABLES_ENABLED` 控制；同时补历史 run 同步脚本。

## 13. 2026-06-12 竣工口径复盘：数据库、部署与加速路线

本次重新校准“项目竣工”口径：不能只看业务主链是否跑通，还必须覆盖数据库、部署、队列/worker、日志监控、安全、数据分析、GraphRAG 和阶段二能力。

当前结论：
- 阶段一 MVP 主链已经基本跑通，但还不是稳定生产化系统。
- 当前最大缺口是稳定性、工程化、数据沉淀和部署能力。
- 数据分析不应放在 GraphRAG 之后，而应前置；GraphRAG 是建立在干净、结构化、可评分数据上的增强层。

数据库主线必须补齐：
- 正式 schema：`runs`、`run_events`、`drafts`、`creator_assets`、`creator_notes`、`operation_records`、`performance_records`、`collection_candidates`、`raw_notes`、`raw_comments`、`analysis_reports`、`audit_events`。
- JSON run store 和 operation memory 迁移到 SQLite/PostgreSQL。
- 图片素材、采集候选、清洗评论、表现回填和分析报告都需要结构化入库。
- 需要迁移工具、索引、唯一约束、幂等键、备份恢复和敏感字段脱敏。

部署主线必须补齐：
- API/worker 进程拆分。
- 队列持久化和任务恢复。
- 反向代理、HTTPS、健康检查、启动脚本。
- `.env.local`、`.env.production`、`.env.example` 分层和 secrets 管理。
- 持久化目录规划：数据库、run 数据、图片素材、Markdown、日志、备份。
- 从空机器到跑通一条主链的部署文档。

日志监控必须补齐：
- run 事件时间线。
- 节点耗时。
- LLM token 与成本统计。
- 采集成功率、评论命中率、Cookie 失败率。
- 发布成功率、状态同步延迟。
- 错误聚合、查询入口和告警。

推荐加速路线：
- 主链稳定线，2-4 天：发布状态轮询、采集候选池评分初版、基础数据分析报告初版已完成；后续继续评论质量评分细化。
- 工程化数据线，4-7 天：SQLite schema、run store/operation memory 迁移、事件表、素材表、表现表。
- 部署可运行线，3-6 天：API/worker 启动模板、环境配置、日志目录、健康检查、部署文档。

工期判断：
- 阶段一“可稳定本地/单机部署运行”：约 7-12 天。
- 加上 GraphRAG：再加约 5-8 天。
- 加上阶段二软广、达人、千帆、蒲公英和完整生产化部署：整体约 4-6 周。

优先级更新：
- 下一步不应直接进入 GraphRAG。
- 发布状态轮询、采集候选池评分初版、基础数据分析报告初版、数据库基础表 schema 初始化、核心四表显式旁路写入、配置开关自动同步和历史补偿脚本已完成；优先扩展草稿、素材、平台笔记、表现和审计表写入。
- 数据库应在 GraphRAG 前完成，避免后续把松散 JSON 与临时文件迁移成图谱/向量系统时返工。

## 14. 2026-06-12 采集候选池评分初版完成

本次主线补齐了采集质量上游能力：

- `spider_xhs` 采集不再只取搜索前几条，而是按 `XHS_CANDIDATE_POOL_MULTIPLIER` 和 `XHS_CANDIDATE_POOL_LIMIT` 扩大候选池。
- 候选笔记会按主题相关度、标题命中、评论数、点赞/收藏等互动信号综合评分，并对低相关或低质量候选做惩罚。
- run/API 结果新增 `collection_candidates`，包含候选评分、排名、是否选中和评分摘要。
- `scripts/check_collector.py --search` 会展示候选评分、入选笔记和原始候选，且已修复 Windows GBK 控制台 emoji 输出问题。
- mock collector、state、insight 节点和 API payload 已全部兼容候选池字段。

验证补充：

- 聚焦候选池测试和脚本输出测试通过。
- 真实搜索 `小红书新手选题方法` 返回 `raw_notes=9`、`selected_notes=3`，候选第 1 评分 `164` 并被选中。
- 全量回归通过：`153 passed`。

路线图影响：

- “采集候选池评分”从未完成项调整为初版完成项。
- 下一步主链建议转向“基础数据分析报告”，让每次 run 能解释为什么选这些样本、评论质量如何、痛点可信度如何，以及适合什么内容结构。
- 评论质量评分仍需要继续细化，尤其是真实问题、反对意见、使用场景和引流/水军惩罚。

## 15. 2026-06-12 基础数据分析报告初版完成

本次主线补齐了采集后的基础可解释分析能力：

- 新增 `analysis_report`，从候选池、入选笔记、评论、评论洞察、痛点和评论抓取错误中生成确定性报告。
- 报告覆盖样本选择、评论质量、痛点可信度、内容结构建议、风险和一句话摘要。
- insight 节点成功采集和采集失败兜底都会返回报告。
- run/API 的 `insights.analysis_report` 已可直接读取。
- `scripts/check_collector.py` 已输出同一套报告，便于真实采集时快速判断样本质量。

验证补充：

- 新增核心测试、节点/API 集成测试和脚本输出测试。
- 聚焦回归通过：`12 passed`。
- 全量回归通过：`161 passed`。

路线图影响：

- “基础数据分析报告”从未完成项调整为初版完成项。
- 下一步优先级上移到数据库基础表设计：`analysis_reports`、`collection_candidates`、`raw_notes`、`raw_comments` 等应结构化落库。
- 评论质量评分仍需要继续细化，用于提升报告可信度和后续 GraphRAG 入库质量。

## 16. 2026-06-12 数据库基础业务表 schema 初始化完成

本次主线完成了数据库基础表第一轮落地：

- 新增 `app/database_schema.py`，提供统一的 foundation schema 初始化入口。
- 新增 10 张基础业务表：`run_events`、`raw_notes`、`collection_candidates`、`raw_comments`、`analysis_reports`、`drafts`、`creator_assets`、`creator_notes`、`performance_records`、`audit_events`。
- 每张表保留关键查询字段，同时保留 `raw_json`、`payload_json`、`report_json` 等 JSON 兜底字段，避免初版拆字段过细。
- 初始化过程幂等，可和现有 `runs`、`run_queue_jobs`、`operation_records` 共存在同一 SQLite 数据库。
- `.env.example` 增加 foundation schema 配置说明。

验证补充：

- 新增 `tests/test_foundation_database_schema.py`。
- SQLite 兼容聚焦回归通过：`22 passed`。
- 全量回归通过：`164 passed`。

路线图影响：

- “数据库基础表设计/第一轮 schema 初始化”从待办调整为完成。
- 下一步数据库主线应进入业务表旁路写入，先同步 `raw_notes`、`collection_candidates`、`raw_comments`、`analysis_reports`。
- 历史数据迁移、查询切换、GraphRAG 入库仍保持后置。

## 17. 2026-06-12 业务表核心快照旁路写入初版完成

本次主线完成了数据库基础表第二轮落地：

- 新增 `app/business_store.py`，提供 `sync_run_business_tables(db_path, run_record)` 显式同步入口。
- 初版写入四张核心业务表：`raw_notes`、`collection_candidates`、`raw_comments`、`analysis_reports`。
- 同步前自动初始化 foundation schema。
- 写入使用稳定 hash ID 和 upsert，重复同步同一 run 不会重复插入。
- 候选和评论会尽量关联到对应 `raw_notes.note_row_id`。
- JSON 兜底字段增加递归脱敏，过滤 Cookie、token、api key、authorization、xsec_token、用户昵称、头像、用户 ID、评论 ID 等敏感字段。
- URL 中敏感查询参数也会过滤，避免 `xsec_token` 随 `note_url` 落库。

验证补充：

- 新增 `tests/test_business_store.py`。
- TDD RED：测试初始因 `app.business_store` 缺失失败。
- 聚焦回归通过：`6 passed`。
- 编译检查通过。
- 全量回归通过：`167 passed`。

路线图影响：

- “核心四表显式旁路写入”从待办调整为完成。
- 自动接入 API/worker 保存流程和历史 run 补偿脚本已在下一轮完成。
- 下一步优先扩展 `drafts`、`creator_assets`、`creator_notes`、`performance_records`、`audit_events`。

## 18. 2026-06-12 业务表自动同步与历史补偿脚本完成

本次主线完成了数据库基础表第三轮落地：

- 配置层新增 `XHS_AGENT_DB_SCHEMA` 和 `XHS_AGENT_BUSINESS_TABLES_ENABLED` 的正式读取字段。
- 默认仍关闭业务表自动写入。
- 当 `XHS_AGENT_BUSINESS_TABLES_ENABLED=true` 且 run store 为 SQLite 时，成功 run 保存后会自动同步四张核心业务表。
- queued/running/failed 记录不会同步，JSON run store 也不会同步。
- 同步成功/失败结果会回写到 run summary，不阻断 run 主流程。
- 新增 `scripts/sync_run_to_business_tables.py`，支持单 run、最近 N 个 run、dry-run 补偿同步。
- 运行时配置检查已能提示业务表写入开启、关闭或配置不匹配。

验证补充：

- 新增 `tests/test_api_business_table_sync.py`。
- 新增 `tests/test_sync_run_to_business_tables_script.py`。
- 扩展配置和 runtime check 测试。
- 聚焦配置/API/脚本测试通过：`16 passed`。
- 数据库相关回归通过：`34 passed`。
- 编译检查通过。
- 全量回归通过：`175 passed`。

路线图影响：

- “配置开启后的核心四表自动同步”和“历史 run 补偿脚本”从待办调整为完成。
- 数据库主线下一步进入剩余业务表旁路写入：草稿、素材、平台笔记、表现记录、审计事件。
- 查询切换、GraphRAG 入库仍保持后置。

## 19. 2026-06-12 业务表剩余快照旁路写入完成

本次主线完成了数据库基础表第四轮落地：

- `sync_run_business_tables()` 已从核心四表扩展到 9 张业务表。
- 新增写入 `drafts`，沉淀草稿标题、正文、图文页规划、图片 prompt、视频脚本、标签、评论引导、Markdown 路径和 `operation_record_id`。
- 新增写入 `creator_assets`，沉淀已绑定图片路径、文件名、mime、文件大小、绑定顺序和 prompt，并关联 `draft_id`。
- 新增写入 `creator_notes`，沉淀 `creator_note_id`、发布模式、发布状态、可见性、平台类型、指标快照和脱敏后的发布响应。
- 新增写入 `performance_records`，当 run state 已有表现数据时沉淀曝光、点赞、收藏、评论、关注和表现分。
- 新增写入 `audit_events`，当前覆盖人工审核、creator 发布和运营记忆写入三类快照级事件。
- 继续保持幂等 upsert 和敏感字段脱敏，业务表写入仍是旁路能力，不改变现有 API/JSON 行为。

验证补充：

- 新增实施计划：`docs/superpowers/plans/2026-06-12-business-table-extended-writer.md`。
- 扩展 `tests/test_business_store.py`、`tests/test_api_business_table_sync.py`、`tests/test_sync_run_to_business_tables_script.py`。
- TDD RED：新增测试先因 `drafts` 等剩余表未写入而失败。
- 聚焦业务表回归通过：`12 passed`。
- 编译检查通过：`compileall app tests`。
- 全量回归通过：`177 passed`。

路线图影响：

- “剩余业务表旁路写入：草稿、素材、平台笔记、表现记录、审计事件”从待办调整为完成。
- 数据库主线下一步建议转向只读查询入口或 `run_events` 节点事件时间线。
- `/performance` 后写入运营记忆的表现记录还没有自动同步到业务表，后续可作为表现链路增强项。
- 查询切换、历史大迁移和 GraphRAG 入库仍保持后置。

## 20. 2026-06-12 业务表只读查询 API 完成

本次主线完成了数据库基础表第五轮落地：

- 新增 `app/business_queries.py`，提供 `get_business_run_snapshot(db_path, run_id)`。
- 查询入口会按 `run_id` 读取 9 张 foundation 业务表：
  - `raw_notes`
  - `collection_candidates`
  - `raw_comments`
  - `analysis_reports`
  - `drafts`
  - `creator_assets`
  - `creator_notes`
  - `performance_records`
  - `audit_events`
- 返回每张表的紧凑列表和 `counts` 汇总，便于确认自动同步和历史补偿是否真实落库。
- JSON 字段会在查询响应中解析为结构化字段，例如 `reasons_json` -> `reasons`、`payload_json` -> `payload`。
- `app.api.get_business_run_snapshot(run_id)` 新增 API 层入口，仅支持 SQLite run store。
- HTTP 新增只读路由：`GET /business/runs/{run_id}`。
- JSON run store 下不模拟业务表查询，会明确提示需要 SQLite run store。
- 本轮不改变现有 `/runs/{run_id}`，也不把业务分析查询切换到业务表。

验证补充：

- 新增实施计划：`docs/superpowers/plans/2026-06-12-business-table-read-api.md`。
- 新增 `tests/test_business_queries.py`。
- 扩展 `tests/test_api_business_table_sync.py` 和 `tests/test_api_platform_status.py`。
- TDD RED：新增测试先因 `app.business_queries` 模块缺失失败。
- 聚焦 API/查询测试通过：`12 passed`。
- 数据库相关回归通过：`25 passed`。
- 编译检查通过：`compileall app tests`。
- 全量回归通过：`182 passed`。

路线图影响：

- “业务表只读查询入口”从待办调整为完成。
- 下一步可给工作台增加只读“业务表快照”面板，直接调用 `/business/runs/{run_id}`。
- 也可以继续补 `run_events` 节点事件时间线，为队列恢复、节点耗时、失败诊断和监控打基础。
- `/performance` 写入运营记忆后的表现记录仍未自动反向同步到 `performance_records`，后续可作为表现链路增强项。

## 21. 2026-06-12 run_events 节点事件时间线完成

本次主线完成了数据库基础表第六轮落地，把 `run_events` 从预留 schema 变成可写、可查的基础时间线：

- 新增 `app/run_events.py`，提供 `record_run_event(db_path, ...)` 统一写入入口。
- 事件写入会自动初始化 foundation schema，并通过稳定 hash 事件 ID 保持同一事件幂等 upsert。
- `app.api._save_run()` 已在 SQLite run store、foundation schema、业务表开关启用时记录 run 生命周期事件：`queued`、`running`、`success`、`failed`。
- 生命周期事件写入失败不会阻断 run 保存，只记录 warning。
- 新增 `_run_workflow()` 统一 workflow 调用，local engine 会把 `run_id` 和 SQLite DB 路径传给本地 graph。
- `app.graph.run_local_graph()` 支持记录节点级事件：
  - 节点成功写入 `node_finished`。
  - 节点失败写入 `node_failed`，再抛出原异常。
  - 记录显式节点名、开始时间、结束时间、耗时和更新字段。
- `app.business_queries` 已把 `run_events` 纳入 `/business/runs/{run_id}` 快照和 counts。
- langgraph 路径当前只记录 API 生命周期事件，节点级细粒度事件后置。

验证补充：

- 新增 `tests/test_run_events.py`。
- 新增 `tests/test_graph_run_events.py`。
- 扩展 `tests/test_business_queries.py`、`tests/test_api_business_table_sync.py`、`tests/test_api_platform_status.py`。
- 聚焦事件/API 回归通过：`18 passed`。
- 编译检查通过：`compileall app tests`。
- 全量回归通过：`188 passed`。

路线图影响：

- “run_events 节点事件时间线”从待办调整为完成。
- 数据库主线现在已经覆盖 foundation schema、9 张业务表旁路写入、历史补偿、只读查询 API 和基础事件时间线。
- 下一步可给工作台增加只读“业务表快照/事件时间线”面板，直接展示 `/business/runs/{run_id}` 的结构化快照。
- 后续工程化重点可继续转向队列恢复、任务超时/取消/重试、日志监控聚合，以及 `/performance` 到 `performance_records` 的反向同步。
- GraphRAG 入库、历史大迁移和分析查询切换仍保持后置，等结构化数据和监控基础继续稳住后再进入。

## 22. 2026-06-12 SQLite 队列事件可观测性完成

本次主线从数据库基础切到队列/worker 工程化，把 SQLite queue 的关键状态变化接入 `run_events` 时间线：

- 新增 `app/queue_events.py`，作为队列事件适配层，复用 `record_run_event()` 写入结构化事件。
- `record_queue_event_safely()` 保证事件写入失败不阻断队列状态机。
- `SQLiteRunQueue` 新增可选 `event_db_path`，默认关闭事件记录，API 配置满足条件时才开启。
- 已记录的队列事件：
  - `queue_enqueued`
  - `queue_claimed`
  - `queue_reclaimed`
  - `queue_requeued`
  - `queue_succeeded`
  - `queue_failed`
- `SQLiteRunQueue.status()` 增加 `jobs` 明细，返回 active/failed job 的 attempts、max_attempts、locked_by 和 last_error。
- `app.api._run_queue_service()` 只在 SQLite run store、foundation schema、业务表开关开启时为队列传入事件 DB。
- queue DB 和 run DB 分离时，队列事件写入 run DB，便于 `/business/runs/{run_id}` 聚合查询。
- `.env.example` 已说明队列事件复用现有业务表开关，不新增独立配置。

验证补充：

- 新增实施计划：`docs/superpowers/plans/2026-06-12-sqlite-queue-events-observability.md`。
- 新增 `tests/test_queue_events.py`。
- 扩展 `tests/test_sqlite_run_queue.py`、`tests/test_api_run_queue_selection.py`、`tests/test_run_worker.py`。
- TDD RED：新增测试先因 `app.queue_events` 缺失失败。
- 队列/worker 聚焦回归通过：`20 passed`。
- 队列 + 事件 + 业务查询聚焦回归通过：`32 passed`。
- 编译检查通过：`compileall app scripts tests`。
- 全量回归通过：`194 passed`。

路线图影响：

- “队列/worker 可观测性基础”从待办调整为完成。
- 当前可观测性已经覆盖 run 生命周期、local graph 节点耗时和 SQLite queue 状态变化。
- 下一步推荐做工作台只读“事件时间线/队列诊断”面板，把 `/business/runs/{run_id}` 的事件直接呈现出来。
- 继续工程化时，可进入任务取消、超时标记、running 任务恢复策略和 worker 心跳。
- Redis/RQ/Celery、多队列拆分、GraphRAG 入库和历史大迁移继续后置。

## 23. 2026-06-12 工作台事件时间线与任务控制完成

本次主线同时完成了工作台只读可观测面板和第一批任务控制能力：

- `SQLiteRunQueue` 新增 `cancel()` 和 `mark_timed_out()`。
- SQLite queue job 新增可见终态：`cancelled`、`timed_out`。
- `run_events` 新增队列事件：`queue_cancelled`、`queue_timed_out`。
- API 新增显式控制函数：
  - `cancel_run(run_id, payload)`
  - `timeout_run(run_id, payload)`
- HTTP 新增显式控制路由：
  - `POST /runs/{run_id}/cancel`
  - `POST /runs/{run_id}/timeout`
- run lifecycle 事件扩展支持 `cancelled` 和 `timed_out`。
- `_finish_run()` 增加保护，避免 worker 后续把已取消/已超时的 run 覆盖成 success/failed。
- `/queue` 的 SQLite backend 状态继续扩展，返回 cancelled/timed_out 计数、ID 列表和 job 明细。
- 工作台任务结果区新增 `runTimeline`，直接读取 `/business/runs/{run_id}` 展示：
  - run 生命周期事件
  - SQLite queue events
  - local graph 节点耗时事件
- 工作台队列区新增 job 诊断和操作按钮：
  - 查看状态、尝试次数、worker、last_error。
  - 对非终态任务执行取消或标记超时。

验证补充：

- 新增实施计划：`docs/superpowers/plans/2026-06-12-workbench-timeline-and-run-control.md`。
- 新增 `tests/test_api_run_control.py`。
- 新增 `tests/test_workbench_event_timeline_static.py`。
- 扩展 `tests/test_sqlite_run_queue.py`。
- TDD RED：新增测试先因队列控制方法、API 控制函数和前端时间线容器缺失失败。
- 队列控制聚焦回归通过：`12 passed`。
- API 控制 + 队列聚焦回归通过：`15 passed`。
- 前端静态和诊断回归通过：`8 passed`。
- 综合聚焦回归通过：`35 passed`。
- JS 语法检查通过：`node --check app/static/app.js`。

路线图影响：

- “工作台事件时间线/队列诊断面板”从待办调整为完成。
- “任务取消/超时标记/运行中终态保护”从待办调整为初版完成。
- 当前仍不强杀运行线程，不撤销已发出的真实平台请求；这部分需要更完整的 worker 心跳、可中断执行器或任务边界设计。
- 下一步工程化重点建议进入 worker 心跳和 watchdog 自动超时扫描。
- GraphRAG 入库、Redis/RQ/Celery、多队列拆分和历史大迁移继续后置。

## 24. 2026-06-12 工作台事件时间线排序与时区显示修复
本轮修复用户在浏览器里指出的事件时间线异常。问题根因是 `run_events` 中同时存在 UTC aware 时间和本地 naive 时间，后端按原始文本排序、前端按原始文本展示，导致队列事件显示为 `+00:00` 原文并排在生命周期事件前面。

已完成：

- `app.business_queries` 对 `run_events` 读出排序做归一化：
  - aware 时间转换成本地时间。
  - 按秒级时间桶排序。
  - 同一秒内使用 SQLite `rowid` 保留写入顺序。
- `app/static/app.js` 的 `compactTime()` 现在把带时区 ISO 时间显示为本地 `YYYY-MM-DD HH:mm:ss`。
- `app/static/app.js` 新增前端时间线排序，兼容尚未重启的旧 API 进程返回旧顺序。
- 扩展 `tests/test_business_queries.py` 和 `tests/test_workbench_event_timeline_static.py`，覆盖混合时区排序、本地时间显示和旧 API 顺序兼容。

验证补充：

- 新增定点测试先失败后通过。
- 相关回归通过：`38 passed`。
- JS 语法检查通过：`node --check app/static/app.js`。
- 浏览器复查通过：当前 8024 页面同一 run 的时间线已显示为本地时间，顺序为“进入队列 -> 队列入队 -> 队列领取 -> 开始运行 -> 运行成功 -> 队列成功”。

路线图影响：

- “工作台事件时间线”从功能可用提升为可读性和历史数据兼容更稳的状态。
- 暂不迁移历史 SQLite 数据，也不强制统一所有写入端时间格式；后续可在 worker 心跳/watchdog 或事件规范化主线里统一事件时间精度与时区策略。
- 下一步主线建议仍是 worker 心跳 + watchdog 自动超时扫描，然后补运行配置组合检查和 `/performance` 到 `performance_records` 的反向同步。

## 25. 2026-06-13 worker 心跳与 watchdog 自动超时扫描完成

本次主线继续推进队列/worker 工程化，把 SQLite worker 的存活信号和自动超时扫描接入现有队列状态机与事件时间线：

- `run_queue_jobs` 新增 `heartbeat_at` 字段，并支持旧库幂等补列。
- `SQLiteRunQueue.claim_next()` 领取任务时初始化 `heartbeat_at`。
- `SQLiteRunQueue.status()` 的 job 明细返回 `heartbeat_at`。
- 新增 `SQLiteRunQueue.heartbeat(run_id, worker_id)`：
  - 只允许当前锁定 worker 更新 running job。
  - 更新 `heartbeat_at`。
  - 写入 `queue_heartbeat` 事件。
- 新增 `SQLiteRunQueue.mark_stale_running_as_timed_out()`：
  - 根据 `heartbeat_at` 判断过期。
  - 历史 running job 没有 heartbeat 时回退 `locked_at`。
  - 复用 `mark_timed_out()` 进入现有 `timed_out` 终态和 `queue_timed_out` 事件。
- `scripts/run_worker.py`：
  - `run_once()` 领取任务后写一次 heartbeat。
  - 新增 `run_watchdog_once()`。
  - CLI 新增 `--watchdog-once`。
- 配置新增 `XHS_AGENT_QUEUE_HEARTBEAT_TIMEOUT_SECONDS`，运行配置检查会校验正数。
- 工作台事件时间线识别 `queue_heartbeat`，显示为“队列心跳”，并排序在队列领取之后、运行开始之前。
- 新增设计和计划文档：
  - `docs/superpowers/specs/2026-06-13-worker-heartbeat-watchdog-design.md`
  - `docs/superpowers/plans/2026-06-13-worker-heartbeat-watchdog.md`

验证补充：

- TDD RED：新增测试先因缺少 heartbeat 字段、队列方法、worker watchdog 入口、配置检查和前端事件映射失败。
- 定点 RED->GREEN 通过：`8 passed`。
- 相关聚焦回归通过：`39 passed`。
- JS 语法检查通过：`node --check app/static/app.js`。
- Python 编译检查通过：`compileall app scripts tests`。
- 全量回归通过：`214 passed`。

路线图影响：

- “worker 心跳 + watchdog 自动超时扫描”从待办调整为初版完成。
- 当前仍不强杀运行线程，也不撤销真实平台请求；自动超时只更新本地 run/queue/event 状态。
- 当前 worker 只在领取任务后写一次 heartbeat，周期心跳线程和常驻 watchdog 仍是后续增强。
- 下一步建议补 worker 周期心跳、watchdog 常驻/启动模板集成，以及更完整的运行配置组合检查。
- `/performance` 到 `performance_records` 的反向同步仍未完成，可作为表现链路下一条主线。

## 26. 2026-06-13 worker 周期心跳与 watchdog loop 完成

本次主线把上一轮 worker heartbeat/watchdog 初版继续推进到可长期运行的基础形态：

- `run_once()` 支持 `heartbeat_interval_seconds`，任务执行期间会通过 daemon 线程周期刷新 heartbeat。
- 心跳线程在任务结束或异常后停止，心跳写入失败只记录 warning，不影响任务主流程。
- 新增 `run_watchdog_loop()`，可循环执行 watchdog 扫描。
- `scripts/run_worker.py` CLI 新增 `--watchdog-loop`。
- 配置新增 `XHS_AGENT_QUEUE_HEARTBEAT_INTERVAL_SECONDS`，默认 30 秒。
- `scripts/check_runtime_config.py --profile sqlite-worker` 现在会检查：
  - heartbeat interval 为正数。
  - heartbeat timeout 为正数。
  - heartbeat interval 小于 timeout。
  - queue event timeline 是否完整启用。
- `scripts/start_sqlite_worker.ps1` 新增 heartbeat interval、heartbeat timeout 和 `-Watchdog` 模式。
- 新增设计和计划文档：
  - `docs/superpowers/specs/2026-06-13-worker-periodic-heartbeat-watchdog-loop-design.md`
  - `docs/superpowers/plans/2026-06-13-worker-periodic-heartbeat-watchdog-loop.md`

验证补充：

- TDD RED：新增测试先因周期心跳、watchdog loop、配置检查和启动模板能力缺失失败。
- 定点 RED->GREEN 通过：`6 passed`。
- 聚焦回归通过：`25 passed`。

路线图影响：

- “worker 周期心跳”从待办调整为完成。
- “watchdog 常驻/启动模板集成”从待办调整为初版完成。
- 当前仍不强杀运行线程，不撤销真实平台请求；这是符合平台安全边界的本地状态治理。
- 下一步建议做完整运行配置组合检查或 mock SQLite 端到端 smoke，再进入 `/performance` 到 `performance_records` 的反向同步。

## 27. 2026-06-13 SQLite stack smoke 组合检查完成

本次主线新增一键 mock SQLite stack smoke，用于提高日常开发效率和提交前验证质量：

- 新增 `scripts/check_sqlite_stack.py`。
- 脚本会在进程内临时设置 mock + SQLite 环境：
  - SQLite run store
  - SQLite run queue
  - SQLite operation memory
  - foundation business tables
  - business table events
- 脚本会提交一条异步 run，调用 worker 处理，调用 watchdog 扫描，并读取业务表快照。
- 输出 JSON 摘要，包含 run 状态、queue 状态、watchdog 结果、business_run、event_types 和 checks。
- 执行完成后恢复原环境变量并重置 API/operation memory 单例。
- 新增测试 `tests/test_check_sqlite_stack.py`，覆盖 smoke 成功、环境恢复和 CLI 输出。
- 新增设计和计划文档：
  - `docs/superpowers/specs/2026-06-13-sqlite-stack-smoke-design.md`
  - `docs/superpowers/plans/2026-06-13-sqlite-stack-smoke.md`

验证补充：

- TDD RED：新增测试先因 `scripts.check_sqlite_stack` 缺失失败。
- 定点 RED->GREEN 通过：`tests/test_check_sqlite_stack.py` 为 `4 passed`。
- 重点组合验证通过：`tests/test_check_sqlite_stack.py tests/test_sqlite_queue_worker_integration.py tests/test_run_worker.py tests/test_runtime_config_check.py` 为 `26 passed`。
- CLI smoke 通过：`scripts/check_sqlite_stack.py` 输出 `"ok": true`，run 最终 `status=success`，queue 清空，watchdog 未误标超时。
- 编译检查通过：`python -m compileall app scripts tests`。
- 全量测试通过：`224 passed`。

路线图影响：

- “完整运行配置组合检查或 smoke 脚本”从待办调整为初版完成。
- 现在每轮开发可以先用 `scripts/check_sqlite_stack.py` 快速确认工程底座健康。
- 该 smoke 不替代真实 HTTP/API 端口验证和真实平台小流量验证；它服务本地工程链路健康检查。
- 下一步建议进入 `/performance` 到 `performance_records` 的反向同步。

## 28. 2026-06-13 /performance 到 performance_records 反向同步完成

本次主线收口了表现数据闭环：`/performance` 人工录入表现后，运营记忆、SQLite run state 和 `performance_records` 能保持一致。

- `/performance` 保持现有入参和运营记忆更新行为，新增 `business_sync` 响应摘要。
- 非 SQLite run store、业务表未启用或找不到匹配 success run 时，返回 `business_sync.status=skipped`，不影响运营记忆更新。
- SQLite run store + foundation business tables 启用时，会按 `operation_record_id`、`creator_note_id`、`post_id` 查找匹配的 success run。
- 匹配成功后，把表现数据、表现分、复盘摘要和下一步建议合并回 run state。
- 复用 `_save_run()` 和 `sync_run_business_tables()` 刷新 `performance_records`，没有新增旁路写表逻辑。
- 同步异常返回 `business_sync.status=failed`，错误信息复用现有脱敏逻辑。
- `/runs/{run_id}` 的 summary 现在包含 `performance_data` 和 `performance_score`。
- 新增实施计划：
  - `docs/superpowers/plans/2026-06-13-performance-business-sync.md`

验证补充：

- TDD RED：`tests/test_creator_note_performance_sync.py` 先因 `business_sync` 缺失出现 `4 failed, 4 passed`。
- 定点 RED->GREEN 通过：`tests/test_creator_note_performance_sync.py` 为 `8 passed`。
- 相关回归通过：`tests/test_creator_note_performance_sync.py tests/test_api_business_table_sync.py tests/test_business_store.py` 为 `21 passed`。
- SQLite stack smoke 通过：`scripts/check_sqlite_stack.py` 输出 `"ok": true`，run 最终 `status=success`，queue 清空，watchdog 未误标超时，业务快照包含 `performance_records`。
- 编译检查通过：`python -m compileall app scripts tests`。
- 全量测试通过：`227 passed`。

路线图影响：

- “`/performance` 到 `performance_records` 的反向同步”从待办调整为完成。
- 当前结构化数据主线已经覆盖 foundation schema、业务表写入、业务查询、事件时间线、队列/worker 可观测、worker watchdog、SQLite stack smoke 和表现数据闭环。
- 下一步建议转入真实 Cookie 小流量复验：用一条真实私密发布记录确认 `creator_note_id -> /performance -> performance_records` 闭环。
- 历史 operation memory 表现记录批量补偿、GraphRAG 入库和历史大迁移继续后置。

## 29. 2026-06-13 表现闭环真实检查与历史补偿完成

本次主线继续提高表现数据闭环的可复验性和开发效率：

- 新增 `scripts/check_real_performance_closure.py`，把上一轮手工真实闭环检查工具化。
  - 只读 creator 作品列表，不触发真实发布或修改。
  - 支持把指定 `data/api_runs/<run_id>.json` 导入临时 SQLite。
  - 支持指定 `creator_note_id`，并可从平台列表指标快照补齐表现 payload。
  - 复用 `api.record_performance()` 验证 operation memory、run state 和 `performance_records` 一致性。
  - 输出结构化 JSON，便于后续 smoke 或人工复核。
- 新增 `scripts/backfill_performance_records.py`，补齐历史 operation memory 表现记录回写能力。
  - 默认 dry-run，降低误写真实工作库风险。
  - `--apply` 时复用 `/performance` 同步路径，不新增旁路 SQL。
  - 支持按 `record_id`、`creator_note_id`、`post_id` 和 `limit` 缩小范围。
  - 通过确定性 `performance_id` 保持重复执行幂等。
- 新增测试：
  - `tests/test_check_real_performance_closure.py`
  - `tests/test_backfill_performance_records.py`
- 新增设计和计划文档：
  - `docs/superpowers/specs/2026-06-13-performance-backfill-and-real-check-design.md`
  - `docs/superpowers/plans/2026-06-13-performance-backfill-and-real-check.md`

验证补充：
- TDD RED 覆盖脚本缺失、CLI `--runs-dir` 缺失、apply 未实现和 `limit=0` 边界。
- 新增定点测试通过：`tests/test_check_real_performance_closure.py tests/test_backfill_performance_records.py` -> `7 passed`。
- 相关回归通过：表现闭环工具、`/performance` 反向同步、业务表写入和旧同步脚本组合 -> `31 passed`。
- SQLite stack smoke 通过：`scripts/check_sqlite_stack.py` -> `"ok": true`。
- Python 编译检查通过：`compileall app scripts tests`。
- 全量测试通过：`234 passed`。

路线图影响：

- “历史 operation memory 表现记录到 `performance_records` 的一次性补偿脚本”从待办调整为初版完成。
- “真实 Cookie 小流量复验前的表现闭环确认”从手工步骤提升为可复跑脚本。
- 当前仍未完成真实平台指标自动抓取、公开/视频/定时发布、GraphRAG 入库、历史大规模迁移、阶段二软广和达人能力。
- 下一步建议先完成本轮全量验证和提交，再用真实 `run_fda76a64a278` 与 `creator_note_id=6a2bce0b000000003502c564` 跑一次只读闭环工具，确认工具化脚本复现真实闭环。

## 30. 2026-06-13 LangGraph-first 全盘运行时迁移完成

本次主线把项目默认执行路径从“API/local executor 拼接流程”收敛为 LangGraph-first runtime：

- 新增 SQLite-backed checkpoint snapshot，LangGraph thread 使用 `run_id` 作为 `thread_id`。
- `human_review` 改为真正的 LangGraph interrupt/resume。
- `approve_run()` 和 `reject_run()` 都通过同一个 graph thread resume，不再由 API 手动调用发布、creator、复盘和写记忆节点。
- 驳回和 creator 私密发布迁入图内节点，保留 creator 发布失败脱敏、视频格式限制、缺图保护等旧断言。
- worker 遇到 human interrupt 后保存 `waiting_review` 并释放队列任务，不再长期占用 worker。
- LangGraph 主路径记录节点级事件，继续投影到 RunStore、业务表和工作台查询结构。
- API/CLI 默认 engine 改为 `langgraph`，`engine=local` 只作为显式兼容路径保留。
- creator 素材绑定会同步 waiting_review checkpoint，确保审核通过后图内 creator 节点能读取已绑定图片文件。
- local executor 使用本地审核兼容逻辑，避免在非 LangGraph runnable 上下文调用 `interrupt()`。

验证补充：

- 编译检查通过：`compileall app nodes routers platforms memory scripts llm`。
- 相关回归通过：`tests/test_creator_asset_binding.py tests/test_api_creator_review_publish.py tests/test_api_langgraph_resume.py tests/test_api_engine_defaults.py tests/test_api_run_control.py` -> `24 passed`。
- SQLite stack smoke 回归通过：`tests/test_check_sqlite_stack.py` -> `4 passed`。
- 全量测试通过：`246 passed`。
- HTTP API smoke 通过：`scripts/check_api_run.py --engine langgraph --collect-limit 1 --timeout 180`，run 最终为 `status=success` 且 `summary.run_status=waiting_review`。

路线图影响：

- “LangGraph 主流程”从可用提升为默认主干。
- “人工审核工作流”已完成关键架构迁移：审核等待和恢复现在由 LangGraph checkpoint 控制；审核人身份、编辑反馈、驳回重生成仍待后续工作台增强。
- “RunStore/业务表”职责进一步收敛为状态投影和查询，不再决定主流程下一步。
- “worker 工程化”已经能正确处理 waiting_review，不再把人工审核等待视为失败。
- `local` executor 后续不再新增业务能力，只保留回归和调试兼容。

下一步建议：

- 用真实 Cookie 做一条小流量端到端复验：LangGraph waiting_review -> 绑定真实图片 -> creator 私密发布 -> 作品列表只读同步 -> `/performance` 回填。
- 真实平台闭环稳定后，再进入 M5 GraphRAG 运营记忆增强。
- 公开图文、视频、定时发布、平台指标自动抓取、阶段二软广和达人能力继续后置。

## 31. 2026-06-13 平台指标手动触发自动抓取初版完成

本次主线把“creator 作品列表指标快照 -> `/performance` -> operation memory / run state / `performance_records`”从人工拼接提升为手动触发的模块化能力。

已完成：

- 新增 `app/creator_performance_sync.py`：
  - 负责解析同步目标、从 `run_id` 读取 `creator_note_id`、校验平台状态、构造表现回填 payload。
  - 使用依赖注入接收 run loader、creator status reader 和 performance recorder，不直接耦合 HTTP、SQLite 或平台实现。
- 新增 API 入口：
  - `app.api.sync_creator_note_performance()`
  - `POST /creator/notes/performance-sync`
  - 支持 `creator_note_id` 或 `run_id`，支持等待参数和 operator notes。
- 新增 CLI：
  - `scripts/sync_creator_note_performance.py`
  - 支持 `--creator-note-id` 或 `--run-id`。
  - 支持 `--mode spider_xhs`、`--wait`、`--limit`、`--attempts`、`--interval-seconds`。
- 真实 cookie 更新后复验通过：
  - `check_creator_platform.py --mode spider_xhs --check-only` -> `ok=true`
  - `check_creator_platform.py --mode spider_xhs --list --limit 5` -> `source=creator_v2`
  - `sync_creator_note_performance.py --run-id run_877b49f35f98 --mode spider_xhs --wait` -> `synced=true`
  - 从 SQLite run state 解析到 `creator_note_id=6a2d186a000000003503829c`
  - 平台状态 `status=synced`，可见性 `仅自己可见`
  - 当前平台指标快照为 0，回填链路正常，`performance_records=1`

验证补充：

- TDD RED：服务模块和脚本缺失测试先失败。
- 定点测试通过：自动抓取服务、HTTP 参数转发和 CLI -> `8 passed`。
- 相关回归通过：自动抓取、平台状态、表现反向同步、真实闭环工具和历史补偿 -> `27 passed`。
- Python 编译检查通过：`compileall app scripts tests`。
- 全量测试通过：`255 passed`。

路线图影响：

- “平台指标自动抓取”从未完成调整为手动触发初版完成。
- 该能力仍不是后台定时轮询、批量同步或趋势分析。
- 公开图文、视频、定时发布、GraphRAG 入库、历史大规模迁移、阶段二软广和达人能力继续后置。

## 32. 2026-06-13 平台指标批量同步与工作台入口完成

本次主线继续解决平台指标自动抓取后的遗留项，把单条同步扩展为批量、脚本循环、趋势摘要和工作台入口。

已完成：

- `app/creator_performance_sync.py`
  - 新增 `sync_creator_note_performance_batch()`。
  - 新增 `summarize_performance_trends()`。
  - 批量任务按目标逐条返回结果，单条失败不会中断其他目标。
- API：
  - 新增 `POST /creator/notes/performance-sync/batch`。
  - 新增 `GET /performance/trends?limit=...`。
- CLI：
  - `scripts/sync_creator_note_performance.py` 支持多个 `--creator-note-id` 和 `--run-id`。
  - 新增 `--repeat-count` 和 `--repeat-interval-seconds`，用于人工触发的短周期循环同步。
- 工作台：
  - 表现录入区显示表现趋势摘要。
  - 平台作品列表支持“同步表现”。
  - 运营记忆记录支持按 `creator_note_id` “同步表现”。

验证补充：

- 定点新增测试组通过：`20 passed`。
- 相关回归通过：`33 passed`。
- `node --check app/static/app.js` 通过。
- Python 编译检查通过：`compileall app scripts tests`。
- 浏览器工作台 smoke 通过：趋势区域渲染，页面中可见同步表现按钮。
- 全量测试通过：`263 passed`。
- 真实 creator 只读批量同步复验通过：
  - `--run-id run_877b49f35f98`
  - `--creator-note-id 6a2d186a000000003503829c`
  - `total=2`
  - `succeeded=2`
  - `failed=0`

路线图影响：

- “平台指标批量同步”和“工作台同步入口”从待办调整为初版完成。
- “趋势分析”从未完成调整为轻量摘要完成；完整 BI 和时间序列分析仍可后续扩展。
- “后台常驻定时调度”已推进到脚本级调度器初版；统一进程编排和告警策略仍未完成。
- 公开图文、视频、定时发布、GraphRAG、阶段二软广/达人能力继续后置。

## 33. 2026-06-13 平台指标后台同步调度器初版完成

本次主线继续收口 M4 指标同步遗留项，把“手动批量同步/短循环脚本”扩展为可长期运行的调度器入口。

已完成：

- 新增 `app/creator_performance_scheduler.py`：
  - 负责调度轮次、轮间等待、连续失败停手和结果汇总。
  - 每轮通过依赖注入调用批量同步函数，默认由 CLI 对接 `api.sync_creator_note_performance_batch()`。
  - 支持 `max_rounds` 和 `max_consecutive_failed_rounds`，避免异常时无限重复访问平台。
- 新增 `scripts/run_creator_performance_scheduler.py`：
  - 支持多个 `--creator-note-id` / `--run-id`。
  - 支持 `--schedule-interval-seconds`、`--max-rounds`、`--max-consecutive-failed-rounds`。
  - 支持 creator mode、等待参数和 operator notes。
- 新增测试：
  - `tests/test_creator_performance_scheduler.py`
  - `tests/test_run_creator_performance_scheduler_script.py`

验证补充：

- TDD RED：调度器模块和脚本缺失时新增测试先失败。
- 定点新增测试通过：`6 passed`。
- 相关回归通过：`24 passed`。
- Python 编译检查通过：`compileall app scripts tests`。
- 全量测试通过：`269 passed`。

路线图影响：

- “后台常驻定时调度”从未完成调整为脚本级调度器初版完成。
- 当前调度器仍不负责进程守护、系统级定时、告警通知或统一编排。
- 真实平台边界仍是只读作品列表指标同步，不触发发布、编辑、删除、公开或平台定时发布。
- 下一步工程化建议是统一启动编排脚本，或转入 M5 GraphRAG 数据入库/查询设计。

## 34. 2026-06-13 SQLite stack 统一启动编排脚本完成

本次主线继续解决上一轮遗留工程化问题：把 API、SQLite worker、watchdog 和可选 performance scheduler 组合成一个统一启动入口。

已完成：

- 新增 `scripts/start_sqlite_stack.ps1`：
  - 统一设置 SQLite run store、run queue、operation memory DB 路径。
  - 统一设置 collector、creator、LLM、API token 和 heartbeat 配置。
  - 默认启动 API、worker 和 watchdog loop。
  - 使用 `Start-Process -WindowStyle Hidden -PassThru` 启动子进程并输出 PID。
  - 支持 `-NoApi`、`-NoWorker`、`-NoWatchdog`。
  - 支持 `-CheckOnly` 配置预检。
  - 支持显式 `-StartScheduler`，通过 `-CreatorNoteId` / `-RunId` 传入只读指标同步目标。
- 扩展启动模板测试：
  - `tests/test_startup_templates.py` 覆盖统一脚本和 scheduler 参数。
- 更新启动文档：
  - `docs/m17b-startup-templates.md` 新增 SQLite Stack Mode。

验证补充：

- TDD RED：统一脚本缺失时启动模板测试先失败，`3 failed, 3 passed`。
- RED->GREEN：`tests/test_startup_templates.py` -> `6 passed`。
- `start_sqlite_stack.ps1 -CheckOnly` 通过，sqlite-worker profile 返回 0。

路线图影响：

- “统一启动编排脚本”从未完成调整为初版完成。
- 当前仍不是系统级进程守护，不负责自动重启、停止全部子进程或告警通知。
- 下一步工程化可补健康检查/停止脚本/日志查看脚本；主线可转入 M5 GraphRAG 数据入库和查询设计。

## 35. 2026-06-13 SQLite stack 健康检查、停止与日志脚本完成

本次继续收口本地工程化遗留项，在统一启动脚本之后补齐运行后的健康检查、停止和日志查看入口。

已完成：

- 新增 `scripts/check_sqlite_stack_health.ps1`：
  - 运行 sqlite-worker 配置预检。
  - 可检查 API `/health` 和 `/queue`。
  - 可查找 stack 相关进程。
  - 支持 `-ConfigOnly` 和 `-SkipApi`。
- 新增 `scripts/stop_sqlite_stack.ps1`：
  - 默认 dry-run。
  - 显式 `-Apply` 才停止匹配进程。
  - 只匹配 `run_api.py`、`run_worker.py`、`run_creator_performance_scheduler.py`。
- 新增 `scripts/tail_sqlite_stack_logs.ps1`：
  - 查看 API、worker 和 scheduler 日志尾部。
- 扩展 `tests/test_startup_templates.py` 和 `docs/m17b-startup-templates.md`。

验证补充：

- TDD RED：三个脚本缺失时启动模板测试先失败，`4 failed, 5 passed`。
- RED->GREEN：`tests/test_startup_templates.py` -> `9 passed`。
- 健康脚本 `-ConfigOnly` 和 `-SkipApi` 通过。
- 停止脚本 dry-run 通过，未停止任何进程。
- 日志脚本 `-Tail 5` 通过。

路线图影响：

- 本地 SQLite stack 的启动、健康检查、停止和日志查看入口初版已齐。
- 工程化仍缺系统级进程守护、自动重启和告警通知，但不再阻塞进入 M5。
- 下一步主线进入 M5 GraphRAG 数据入库/查询准备。

## 36. 2026-06-13 M5 GraphRAG 运营记忆图谱视图初版完成

本次正式启动 M5 主线第一片：在不引入新外部依赖的前提下，从现有 operation memory 派生图谱视图和查询接口。

已完成：

- 新增 `app/memory_graph.py`：
  - 抽取 topic、pain、content_type、content_format、record 节点。
  - 生成记录与主题、痛点、内容形式、内容格式之间的关系边。
  - 输出高表现记录、相关痛点、推荐内容形式和召回证据。
  - 主题过滤改为保守包含匹配，避免单字召回造成跨领域污染。
- 新增 API：
  - `GET /memory/graph?topic=...&limit=...`
- `nodes/memory_node.retrieve_graphrag_memory()` 现在会返回：
  - `retrieved_memory`
  - `successful_patterns`
  - `graphrag_memory`
- `app/state.py` 增加 `graphrag_memory` 字段。
- 新增测试：
  - `tests/test_memory_graph.py`
  - `tests/test_api_memory_graph.py`
  - `tests/test_memory_node.py`

验证补充：

- TDD RED 覆盖服务缺失和节点未返回 `graphrag_memory`。
- 新增 M5 测试通过：`4 passed`。
- 相关回归通过：`17 passed`。
- Python 编译检查通过：`compileall app nodes memory scripts tests`。

路线图影响：

- M5 从“未开始”调整为“图谱视图与查询初版完成”。
- 向量检索、embedding、跨主题语义召回、合规风险历史召回和前端召回依据展示仍未完成。
- 下一步建议继续 M5：让策略/生成节点消费 `graphrag_memory`，或先在工作台展示召回依据。
