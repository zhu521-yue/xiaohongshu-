# 当前工程进度

## 2026-06-11 M19a 创作者平台连接：私密发布与作品列表基础适配

本轮目标是在不自动公开发布、不引入新平台流程的前提下，先把小红书创作者平台连接封装成低风险适配层：默认 mock，自测可运行；真实 `spider_xhs` 模式必须显式提供创作者 Cookie，且当前只开放私密图文发布和作品列表读取入口。

已完成：
- 新增 `platforms/creator.py`，集中封装创作者平台适配逻辑，支持 `mock` 与 `spider_xhs` 两种模式。
- 新增 `publish_private_image_text()`，仅允许私密图文草稿/私密笔记发布，并要求 `human_confirmed=True` 作为写入类操作硬门槛。
- 新增 `list_published_notes()`，用于作品列表同步的基础读取，返回统一的 `note_id`、`title`、`visibility` 和原始数据。
- 新增 `check_creator_runtime()`，用于在真实平台模式下预检 `XHS_CREATOR_COOKIES`、vendor 目录、`NODE_PATH` 和创作者 API 导入能力。
- 新增 `scripts/check_creator_platform.py`，提供命令行自测入口：`--check-only`、`--publish-private`、`--list`。
- 新增 `tests/test_creator_platform.py`，覆盖 mock 发布、人工确认门槛、图片数量限制、真实模式缺 Cookie 保护、真实模式导入错误暴露、mock 列表同步和脚本退出码。
- 更新 `.env.example`，补充 `CREATOR_MODE` 和 `XHS_CREATOR_COOKIES`。
- 新增 `docs/m19a-creator-platform-connection.md`，说明 mock 自测、真实平台预检、私密发布边界和当前限制。

已验证：
- `D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_creator_platform.py -q` 通过，10 个创作者平台测试全部通过。
- `D:\Anaconda\envs\ContentShare\python.exe .\scripts\check_creator_platform.py --mode mock --publish-private --human-confirmed` 通过，返回 mock 私密笔记 ID。
- `D:\Anaconda\envs\ContentShare\python.exe .\scripts\check_creator_platform.py --mode mock --list --limit 2` 通过，返回 2 条 mock 作品记录。
- `D:\Anaconda\envs\ContentShare\python.exe .\scripts\check_creator_platform.py --mode spider_xhs --check-only` 在未配置 `XHS_CREATOR_COOKIES` 时按预期退出 1，并提示必须提供 Cookie。
- 使用临时 `XHS_CREATOR_COOKIES=a1=fake` 执行 `--mode spider_xhs --check-only` 通过，确认当前 `ContentShare` 环境可以导入 Spider_XHS 创作者 API；该检查不发发布请求。
- `D:\Anaconda\envs\ContentShare\python.exe -m pytest -q` 通过，当前 69 个测试全部通过。
- `D:\Anaconda\envs\ContentShare\python.exe -m compileall app nodes routers platforms memory scripts llm` 通过。

当前阶段判断：
- 当前系统已经从“只能生成内容并人工发布”推进到“具备创作者平台连接的基础封装和低风险自测入口”。
- 真实平台写入仍受到人工确认、Cookie 预检和私密发布边界限制，暂不做自动公开发布。
- 这一步还没有接入主工作流，生成内容后不会自动调用创作者平台发布；当前只是先把平台边界和自测能力做出来。

尚未完成：
- 主链路中的人工审核通过后，自动调用私密发布适配器。
- 发布结果回填到 run、运营记忆和作品表现记录。
- 图片上传、视频上传和真实素材路径管理的完整验证。
- 公开发布、定时发布、失败重试、发布状态轮询。
- 蒲公英、千帆等其他小红书生态平台的数据连接。

建议下一步：
1. 进入 M19b：把 M19a 适配器接入现有审核/运行结果链路，但仍保持私密发布和人工确认。
2. 发布成功后，把 `note_id`、发布时间、发布模式写回 run store 与运营记忆。
3. 暂不处理公开发布和其他平台，等私密发布闭环稳定后再扩展。

## 2026-06-11 M17b 启动模板与部署清单

本轮目标是在不引入 Docker、Nginx、systemd、Redis 或新进程管理器的前提下，把当前 API/worker 的启动方式固化为可重复执行的 Windows/PowerShell 模板，并明确使用 `ContentShare` Python 环境。

已完成：
- 新增 `scripts/start_local_api.ps1`，用于本地开发模式启动 API，默认 `COLLECTOR_MODE=mock`、`LLM_MODEL_NAME=mock`、`XHS_AGENT_RUN_QUEUE=local`。
- 新增 `scripts/start_sqlite_api.ps1`，用于 SQLite 分进程模式启动 API，统一设置 run store、run queue、operation memory 到同一个 SQLite DB 路径。
- 新增 `scripts/start_sqlite_worker.ps1`，用于 SQLite 分进程模式启动 worker，支持 `-Once` 单步处理。
- 三个启动模板都支持 `-CheckOnly`，可只运行配置检查，不启动长时间运行进程。
- 三个启动模板都按顺序选择 Python：`-Python` 参数、`XHS_AGENT_PYTHON`、`D:\Anaconda\envs\ContentShare\python.exe`、最后才回退到裸 `python`。
- 新增 `docs/m17b-startup-templates.md`，说明本地模式、SQLite 分进程模式、带 token 模式、production-lite preflight、日志位置和当前限制。
- 新增 `tests/test_startup_templates.py`，覆盖启动模板存在性、`CheckOnly` 支持、`ContentShare` Python 选择逻辑提示和 SQLite DB 路径一致性要求。
- 新增设计与计划文档：
  - `docs/superpowers/specs/2026-06-11-startup-templates-design.md`
  - `docs/superpowers/plans/2026-06-11-startup-templates.md`

已验证：
- `D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_startup_templates.py -q` 通过，3 个启动模板测试通过。
- `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\start_local_api.ps1 -CheckOnly -Python D:\Anaconda\envs\ContentShare\python.exe` 通过，local profile 检查退出 0。
- `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\start_sqlite_api.ps1 -CheckOnly -Python D:\Anaconda\envs\ContentShare\python.exe` 通过，sqlite-worker profile 检查退出 0。
- `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\start_sqlite_worker.ps1 -CheckOnly -Python D:\Anaconda\envs\ContentShare\python.exe` 通过，sqlite-worker profile 检查退出 0。
- `D:\Anaconda\envs\ContentShare\python.exe -m pytest -q` 通过，当前 59 个测试全部通过。
- `D:\Anaconda\envs\ContentShare\python.exe -m compileall app nodes routers platforms memory scripts llm` 通过。

当前阶段判断：
- 当前 API/worker 已有可重复启动模板，后续自测不必再手动复制大量环境变量。
- 本轮仍不等于完整生产部署；公网部署前仍需要 HTTPS、反向代理、进程守护、备份、账号权限和更完整的密钥治理。

建议下一步：
1. 如继续工程主线，进入 M18：更高并发队列能力评估和 Redis/RQ 或 Celery 的取舍。
2. 如继续产品功能主线，进入 M19：创作者平台私密发布和作品列表同步的低风险验证。
3. 规则泛化和硬编码问题已记录，暂不阻塞当前主功能推进。

## 2026-06-11 后续待处理：规则泛化与硬编码问题记录

本轮只记录问题，不立即进入修复。当前优先级仍是继续推进主要工程功能；内容审核、评论洞察、模板 fallback 和跨领域记忆过滤的泛化问题，后续按阶段逐步改善。

已确认的后续问题：
- 合规规则仍偏单层，当前主要覆盖健康/母婴与小红书增长承诺；法律、金融、教育、职场、医美、减肥等主题还没有独立风险分层。
- `config/compliance_rules.json` 中已配置 `avoid_promise_words`，但 `nodes/compliance_node.py` 当前审核流程没有实际拦截 `爆款`、`必火`、`暴涨`、`快速涨粉` 等过度承诺词。
- 全局 `safety_note` 目前是健康类提示，如果后续直接扩展金融/法律等敏感主题，可能出现提示语错配，需要改成按领域匹配。
- `memory/operation_store.py` 的跨领域污染过滤目前只针对健康护理旧记录，不是通用领域隔离机制。
- `config/comment_insight_rules.json` 已有通用规则和 `baby_skin_care` 领域组，但领域覆盖仍窄，后续需要逐步补法律、金融、教育、职场、医美、内容创作等高频主题规则。
- 图文和视频 fallback 模板仍有较多“小红书运营/知识分享/内容创作”默认表达；真实 LLM 路径影响较小，但 mock 或 LLM 失败时会带偏输出。

后续建议：
1. 先继续主功能开发，不让这些细节阻塞当前工程主线。
2. 后续单独开一轮规则治理，把合规规则改成多领域规则组，并补充对应测试。
3. 再逐步处理模板 fallback、评论洞察领域扩展和历史记忆跨领域复用边界。

## 2026-06-11 M17a 最小生产护栏

本轮目标是在不引入 Docker、Nginx、systemd、Redis 或新 Web 框架的前提下，给当前 API/worker 增加最小生产护栏。

已完成：
- API token 鉴权支持，默认本地开发关闭，设置 `XHS_AGENT_API_TOKEN` 后保护 `/runs`、`/queue`、审核、表现录入和记忆查询等非公开 API。
- `/health`、`/`、`/static/*` 和 `OPTIONS` 保持公开，便于健康检查、页面加载和 CORS preflight。
- 修复静态目录公开边界，避免 `/static/../static_evil/...` 这类 sibling 目录被误判为公开静态资源。
- API 与 worker 增加日志落盘，默认写入 `data/logs/api.log` 和 `data/logs/worker.log`。
- 增加敏感字段脱敏工具，避免 token、cookie、api key、authorization、password 等值进入结构化日志。
- API access log 不再记录 query string 和 fragment，避免 URL 参数泄露。
- 新增 `scripts/check_runtime_config.py`，支持 `local`、`sqlite-worker`、`production-lite` 三种配置检查。
- 自检脚本使用唯一临时探针检查目录可写性，不会覆盖或删除已有 `.write_check` 文件。
- `scripts/check_api_run.py` 支持 `--api-token`，可验证带鉴权的 API。
- `.env.example` 补充 API token 和日志配置。
- 新增 `docs/m17a-production-guardrails.md`，说明本地、带鉴权模式、运行配置检查和日志位置。

已验证：
- `python -m pytest -q` 通过，当前 56 个测试全部通过。
- `python -m compileall app nodes routers platforms memory scripts llm` 通过。
- `python .\scripts\check_runtime_config.py --profile local` 通过，输出 `WARN api token empty: auth disabled`。
- `python .\scripts\check_runtime_config.py --profile production-lite` 在 token 为空时按预期退出 1，并输出 `FAIL production-lite requires XHS_AGENT_API_TOKEN`。
- 带 `XHS_AGENT_API_TOKEN=test-token` 的 API 烟测通过：未带 token 的 `POST /runs` 返回 `401`，带 `--api-token test-token` 的 `check_api_run.py` 能完成 mock LangGraph run，并从 `queued/running` 变为 `success`。

验证环境说明：
- 当前工具默认 `python` 指向 `D:\Anaconda\python.exe`，该环境没有直接安装 `langgraph`。
- `requirements.txt` 已声明 `langgraph==1.2.1`，`D:\Anaconda\envs\ContentShare\python.exe` 可以导入 `langgraph`。
- 本轮最终测试使用 `PYTHONPATH=D:\Anaconda\envs\ContentShare\Lib\site-packages` 让当前工具默认 Python 读取 ContentShare 依赖后通过。用户在已激活 `(ContentShare)` 的终端里执行时不需要额外设置该 `PYTHONPATH`。
- Windows 下 pytest 临时目录偶尔会残留不可访问 ACL；本轮已清理 `data\pytest_tmp` 和 M17a 临时 SQLite/pytest 文件。

当前阶段判断：
- 当前系统仍不是完整生产部署，但已经具备最小 server-facing 护栏：鉴权、日志、脱敏、自检和带 token 烟测。
- 仅设置 `XHS_AGENT_API_TOKEN` 不等于可以直接公网暴露；真正对公网部署前仍需要 HTTPS、反向代理、进程守护、备份、账号体系和更完整的密钥治理。

建议下一步：
1. M17b：补进程启动模板和部署清单，继续保持不引入重型新组件。
2. M18：需要更高并发时再进入 Redis/RQ 或 Celery。
3. M19：基础部署稳定后，再推进小红书创作者平台私密发布和作品列表同步。

## 2026-06-11 M16b API / worker 启动与自测说明

本轮目标是把 M16a 已经实现的 SQLite 队列和独立 worker 入口整理成可操作说明，避免后续只停留在“代码能跑”，但用户不知道如何分别启动 API 和 worker。

已完成：
- 新增 `docs/m16b-api-worker-startup.md`。
- 区分默认本地模式和 SQLite 分进程模式。
- 写明 cmd 与 PowerShell 两套环境变量写法，避免在 cmd 里误用 `$env:...`。
- 写明 API 进程和 worker 进程必须使用同一组 SQLite DB 路径。
- 补充 `/queue` 队列状态检查命令。
- 说明 `run_worker.py --once` 没有任务时返回非零退出码是预期行为。
- 补充常见问题：任务一直 queued、worker 未设置 SQLite 队列、真实采集 Cookie 要求。
- 补充 pytest 临时目录权限残留的清理方式。

已验证：
- `python .\scripts\run_api.py --help` 通过。
- `python .\scripts\run_worker.py --help` 通过。
- `python .\scripts\check_api_run.py --help` 通过。
- `python -m pytest tests/test_sqlite_queue_worker_integration.py -q` 通过。
- `python -m pytest -q` 通过，当前 27 个测试全部通过。
- `python -m compileall app nodes routers platforms memory scripts llm` 通过。
- 使用临时 SQLite DB 启动 API 进程和 worker 进程，`check_api_run.py --engine langgraph` 提交任务后从 `queued` 变为 `success`。

当前阶段判断：
- 本地开发可以继续用默认 `local` 队列。
- 需要验证 API/worker 分进程时，使用 `XHS_AGENT_RUN_QUEUE=sqlite` 并分别启动 API 和 worker。
- 工程链路调试优先使用 `COLLECTOR_MODE=mock` 与 `LLM_MODEL_NAME=mock`，避免真实采集和真实 LLM 干扰基础链路判断。

建议下一步：
1. M17：补生产部署准备，包括日志落盘、进程守护、基础鉴权和敏感配置治理。
2. M19：等基础部署能力稳定后，再进入创作者平台私密发布和小红书生态扩展。

## 2026-06-11 M16a SQLite 持久化运行队列与 worker 入口

本轮目标是在不引入 Redis/RQ/Celery 的前提下，把运行队列从 API 进程内存迁移到 SQLite，并新增独立 worker 脚本，为后续 API/worker 进程拆分铺路。

已完成：
- 新增 `SQLiteRunQueue`，通过 `run_queue_jobs` 表持久化队列任务。
- 保留 `LocalRunQueue` 默认行为，只有设置 `XHS_AGENT_RUN_QUEUE=sqlite` 时启用 SQLite 队列。
- API 提交流程仍创建 `queued` run，再写入队列；SQLite 队列模式下 API 不启动后端 worker 线程。
- 新增 `scripts/run_worker.py`，支持 worker 从 SQLite 队列领取任务并调用现有 `_execute_run(run_id)`。
- 队列支持入队去重、领取锁、成功完成、失败重试、终态失败和过期锁重新领取。
- `.env.example` 新增 SQLite 队列相关配置。
- 新增 `pytest.ini`，将 pytest 收集范围固定到 `tests`，并把临时目录放到已忽略的 `data/pytest_tmp`，避免 Windows 用户临时目录权限残留影响测试。

已验证：
- SQLite 队列单元测试通过。
- API 队列后端选择测试通过。
- worker 单步执行测试通过。
- SQLite 队列 + SQLite run store + mock LangGraph 集成测试通过。
- `python -m pytest -q` 通过。
- `python -m compileall app nodes routers platforms memory scripts llm` 通过。

当前阶段判断：
- API 和 worker 已具备分进程运行基础。
- SQLite 队列适合当前本地和轻量部署阶段。
- Redis/RQ/Celery、部署守护、鉴权、取消任务和前端队列管理仍不在本轮范围内。
- 当前环境已验证 `langgraph` 可用，M16a 集成烟测使用 `engine=langgraph` 验证队列/worker 链路。

建议下一步：
1. M16b：补启动说明和自测命令，明确 API 进程与 worker 进程如何分别启动。
2. M17：进入生产部署准备，补日志、进程守护和基础鉴权。
3. M18：在需要更高并发时再替换为 Redis/RQ 或 Celery。
4. M19：小红书生态平台连接扩展，先评估创作者平台私密发布和作品列表同步，再调研蒲公英/千帆数据价值。

## 2026-06-11 M19 规划补充：小红书生态平台连接扩展

本轮只补规划，不实现平台写入能力。`Spider_XHS技术路线分析.md` 显示 Spider_XHS 除 PC 端只读采集外，还包含创作者平台、蒲公英和千帆等小红书生态入口。当前系统实际完成的是 PC 端搜索、笔记详情和评论采集，尚未接入创作者平台发布、蒲公英达人数据或千帆分销数据。

已写入路线图：
- 创作者平台登录状态和 Cookie 管理。
- 创作者平台私密发布测试。
- 图文/视频上传能力封装。
- 已发布作品列表同步。
- 发布状态回填到 run 和运营记忆。
- 蒲公英达人/KOL 数据调研。
- 千帆分销/商品数据调研。
- 写入类操作必须保留人工确认硬门槛。

当前阶段判断：
- 这部分能力可以让系统从“生成草稿 + 人工发布”逐步升级到“半自动发布 + 发布后回填”。
- 自动公开发布涉及平台风控和账号安全，不应作为第一步。
- 最稳顺序是先做创作者平台私密发布和作品列表同步；蒲公英、千帆先做业务价值调研。

建议顺序：
1. M16b：先完成 API/worker 启动说明和自测流程。
2. M17：补部署、安全、日志和基础鉴权。
3. M19：进入小红书生态平台连接扩展，先做低风险私密发布验证。

## 2026-06-10 M15 运营记忆 SQLite 后端

本轮目标是在保留 `memory/operation_history.json` 默认行为的前提下，给运营记忆增加 SQLite 可切换后端，为后续数据库化和 API/worker 拆分继续铺路。

已完成：
- 新增 `memory.operation_store` 内部后端边界：
  - `JsonOperationMemoryBackend`
  - `SQLiteOperationMemoryBackend`
  - `_memory_backend()`
  - `operation_memory_path()`
- `load_history()`、`save_history()`、`upsert_record_from_state()`、`find_relevant_records()`、`find_successful_patterns()`、`update_record_performance()` 保持公开函数 API 不变，默认调用会根据环境变量选择后端。
- 新增 SQLite 表 `operation_records`，完整记录保存在 `record_json`，同时保留 `topic`、`post_id`、`content_type`、`performance_score`、`created_at`、`updated_at` 等索引字段。
- 新增环境变量：
  - `XHS_AGENT_MEMORY_STORE=json|sqlite`
  - `XHS_AGENT_MEMORY_DB_PATH=data/xhs_agent.sqlite3`
- 更新 `nodes/memory_node.py`、`app/api.py`、`scripts/record_performance.py`，展示当前选中后端的记忆路径。
- 新增 `tests/test_operation_store_sqlite.py`，覆盖 SQLite 运营记忆写入、更新、检索、成功模式提取、表现录入和跨领域健康污染过滤。

已验证：
- `python -m pytest -q` 通过，当前 14 个测试全部通过。
- `python -m compileall app nodes routers platforms memory scripts llm` 通过。
- 使用临时 SQLite DB 的运营记忆烟测通过：
  - 写入一条 operation record。
  - 能按主题检索到相关记录。
  - 能录入表现数据并更新为 `performance_recorded`。
- 临时测试 DB 已清理。

当前阶段判断：
- M14 RunStore SQLite 可切换后端已完成。
- M15 Operation Memory SQLite 可切换后端已完成。
- 默认行为仍是 JSON，只有显式设置环境变量时才启用 SQLite。
- 还没有做历史 JSON 自动迁移；后续如需要，应单独实现迁移脚本并做数据校验。

建议下一步：
1. M16：设计并接入真正的外部队列后端，优先评估 Redis/RQ 与现有 `LocalRunQueue` 的接口差异。
2. M17：拆分 API 进程和 worker 进程，让耗时采集/LLM 任务从 API 服务中移出。
3. M18：补数据库迁移脚本，把 `data/api_runs/*.json` 和 `memory/operation_history.json` 可控迁移到 SQLite。

## 2026-06-10 M9 配置治理

本轮目标是修正节点里业务规则和提示词硬编码的问题，让后续迭代优先改配置，而不是反复进入节点代码。

已完成：
- 新增 `app/rules.py`，统一读取 `config/*.json` 业务规则。
- 新增 `config/content_structures.json`，承载内容结构、图文页规划、标题模板等规则。
- 新增 `config/compliance_rules.json`，承载绝对词、敏感主题、免责声明词、安全提示和承诺类禁用词。
- 新增 `config/strategy_rules.json`，承载内容策略判断关键词和默认策略。
- 新增 `config/comment_insight_rules.json`，承载评论痛点归类规则。
- 新增 `config/text_replacements.json`，承载风险词替换规则。
- 新增 `config/performance_rules.json`，承载表现分权重。
- 新增 `config/llm_prompts.json`，承载图文生成、视频脚本生成、运营复盘的系统提示词、用户提示词模板和 expected JSON。
- 新增 `llm/prompts.py`，负责把外置提示词模板渲染成 `ChatMessage`。
- 改造 `content_node.py`、`video_node.py`、`review_node.py`，节点只组织业务输入，不再直接拼大段 LLM prompt。
- 改造 `compliance_node.py`、`strategy_node.py`、`pattern_utils.py`、`comment_analysis.py`、`operation_store.py`、`review_node.py`，规则来源改为配置文件。
- 修复 `publish_node.py` 中输出目录依赖当前工作目录的问题，改为项目根目录下的 `output/markdown_exports`。
- 修复 `publish_node.py` 中 `state.get("body" or "")` 的错误写法。

已验证：
- `python -m compileall app nodes routers platforms memory scripts llm` 通过。
- `llm.prompts.build_json_prompt()` 能正确加载并渲染外置提示词。
- mock 模式下图文 LangGraph 主流程通过。
- mock 模式下视频 LangGraph 主流程通过。

当前阶段判断：
- M9A 业务规则配置化：完成。
- M9B LLM 提示词配置化：完成基础版。
- 当前仍不是生产部署完成态，下一阶段应处理任务状态、人审流程、存储可靠性和部署安全。

建议下一步：
1. M10：把现在的 `--approve` 假人工确认，升级为真实的前端人审状态流。
2. M11：把 JSON 文件读写加锁、原子写入和异常恢复做扎实。
3. M12：补前端失败任务展示、运行记录详情、表现录入后的记忆刷新。
4. M13：整理部署配置，包括生产 `.env`、日志、进程守护、启动脚本和反向代理。

## 2026-06-10 M10 人工审核入口

本轮目标是让工作台支持“先生成待审草稿，再人工审核通过或驳回”，不再只能靠提交任务时的 `approve` 参数决定是否保存。

已完成：
- `app/api.py` 的 run 记录开始保存完整 `state`，用于后续审核动作继续执行发布、复盘和写运营记忆。
- 新增 `approve_run(run_id, payload)`：
  - 只允许对已经生成成功的 run 操作。
  - 高合规风险内容不能直接通过。
  - 审核通过后调用 `publish_or_schedule()` 保存 Markdown。
  - 随后调用 `review_performance()` 生成复盘摘要。
  - 最后调用 `write_operation_memory()` 写入运营记忆。
- 新增 `reject_run(run_id, payload)`：
  - 审核驳回后设置 `publish_status=rejected`。
  - 不保存 Markdown。
  - 不写运营记忆。
- 新增 HTTP 接口：
  - `POST /runs/{run_id}/approve`
  - `POST /runs/{run_id}/reject`
- 前端工作台新增审核区：
  - `审核通过并保存`
  - `审核不通过`
  - 显示待审、已保存、已驳回、高风险不可直接通过等状态。

已验证：
- `python -m compileall app nodes routers platforms memory scripts llm` 通过。
- `node --check app/static/app.js` 通过。
- 函数级审核通过链路通过：`pending -> success`，并触发运营记忆字段。
- 函数级审核驳回链路通过：`pending -> rejected`，不写运营记忆。
- 临时 mock API 服务下，桌面端 Playwright 工作台提交链路通过，无 console error。
- 临时 mock API 服务下，移动端 Playwright 工作台检查通过，无 console error。

当前阶段判断：
- M9 配置治理：完成基础版。
- M10 人工审核入口：完成基础版。
- 当前人审仍是 API 层继续执行，不是 LangGraph 原生 interrupt/resume；这对当前 MVP 足够，但生产级人审可以后续再升级。

建议下一步：
1. M11：增强 JSON 存储可靠性，重点是原子写入、损坏备份、运行记录和运营记忆的文件锁。
2. M12：优化前端运行记录详情、失败任务展示、审核反馈输入框、表现录入后的记忆刷新体验。
3. M13：进入部署准备，整理 `.env.example`、启动脚本、日志落盘、进程守护和反向代理。

## 2026-06-10 M11 本地存储可靠性

本轮目标是降低 JSON 文件在断电、进程中断或并发写入时损坏的风险。

已完成：
- 新增 `app/json_store.py`：
  - `write_json_atomic()`：先写同目录临时文件，刷新到磁盘，再用 `os.replace()` 原子替换目标文件。
  - `write_text_atomic()`：给 Markdown 等文本产物复用同样的原子写入机制。
  - `read_json_file()`：读取 JSON 时校验根类型。
  - `move_corrupt_file()`：发现损坏 JSON 或根类型不符合预期时，移入同目录 `corrupt/` 备份目录。
- 改造 `app/api.py`：
  - `data/api_runs/*.json` 改为原子写入。
  - 读取 run JSON 时发现损坏文件会隔离到 `data/api_runs/corrupt/`。
- 改造 `memory/operation_store.py`：
  - `operation_history.json` 改为原子写入。
  - 新增 `HISTORY_LOCK`，保护运营记忆的读改写流程。
  - 损坏的运营记忆文件会隔离到 `memory/corrupt/`。
- 改造 `platforms/spider_xhs_collector.py`：
  - 采集快照 `data/collector_runs/*.json` 改为原子写入。
- 改造 `nodes/publish_node.py`：
  - Markdown 草稿保存改为原子写入。

已验证：
- `python -m compileall app nodes routers platforms memory scripts llm` 通过。
- 存储工具正常写入、读取、损坏 JSON 自动隔离通过。
- 临时 API run 目录下，mock LangGraph run 保存和读取通过。
- 临时 operation history 文件下，新增记录和录入表现数据通过。
- 临时 mock API 服务下，工作台提交链路通过，无 console error。

当前阶段判断：
- M11 本地存储可靠性：完成基础版。
- 当前锁是单进程内线程锁，适合现在的单 API 进程和单 worker 队列。
- 如果未来多进程部署，需要升级到数据库、Redis 队列，或引入跨进程文件锁。

建议下一步：
1. M12：优化前端可用性，重点是失败任务详情、审核反馈输入框、运行记录详情、表现录入后的自动刷新。
2. M13：部署准备，补 `.env.example`、启动脚本、日志落盘和进程守护。

## 2026-06-10 M14 高并发改造第一步：队列和存储边界拆分

本轮目标不是立刻接入 Redis/PostgreSQL，而是先把 `app/api.py` 中耦合在一起的 HTTP、run 存储、队列、worker 逻辑拆出可替换边界。这样后续替换成 Redis 队列、Celery worker、PostgreSQL 存储时，不需要重写整个 API 层。

已完成：
- 新增 `app/run_store.py`：
  - `LocalRunStore` 封装 `data/api_runs/*.json` 的保存、读取、列表查询。
  - 当前仍使用本地 JSON 文件，但 API 层不再直接关心文件读写细节。
  - 后续可替换为 `PostgresRunStore`。
- 新增 `app/run_queue.py`：
  - `LocalRunQueue` 封装入队、pending 恢复、worker 启动、队列状态。
  - 当前仍是本进程内队列，但 API 层不再直接持有 `Queue`、worker 线程和去重集合。
  - 后续可替换为 Redis/Celery/RQ。
- 改造 `app/api.py`：
  - `_save_run()`、`_load_run()`、`_list_runs()` 改为委托 `LocalRunStore`。
  - `_enqueue_run()`、`_recover_pending_runs()`、`queue_status()` 改为委托 `LocalRunQueue`。
  - 移除 API 层直接管理 `RUN_QUEUE`、`QUEUE_LOCK`、`ENQUEUED_RUN_IDS`、`WORKER_STARTED` 的逻辑。
- 新增环境变量：
  - `XHS_AGENT_LOCAL_WORKERS`
  - 默认值为 `1`。
  - 本地模式可临时调高 worker 数，但这仍不是最终生产级高并发方案。
- `GET /queue` 返回中新增：
  - `worker_backend`
  - `worker_count`

已验证：
- `python -m compileall app nodes routers platforms memory scripts llm` 通过。
- 函数级 mock run 保存和读取通过。
- `queue_status()` 正常返回队列状态。
- `XHS_AGENT_LOCAL_WORKERS=3` 时，`queue_status()` 能看到 `worker_count=3`。
- 临时 mock API 服务下，工作台提交链路通过，无 console error。

当前阶段判断：
- 高并发改造的第一步完成：边界拆出来了。
- 当前仍不是生产级高并发，因为任务状态仍在本地 JSON，队列仍在单进程内存。
- 下一步必须进入真正的外部基础设施：Redis 队列和 PostgreSQL 存储。

建议下一步：
1. M15：设计并落地数据库模型，先用 SQLite/PostgreSQL 兼容方式替换 run 存储。
2. M16：引入 Redis 队列或 Celery/RQ，替换 `LocalRunQueue`。
3. M17：把 API 进程和 worker 进程拆开，支持多 worker 横向扩容。

## 2026-06-10 M14.5 评论洞察泛化修复

本轮目标是修复真实测试中暴露出的内容质量问题：主题为“小红书新手选题方法”时，评论洞察错误输出“对护理方法存在疑问，担心建议不靠谱”。

问题原因：
- 原 `config/comment_insight_rules.json` 中的 6 条规则全部来自“宝宝湿疹护理”场景。
- 规则关键词中包含“真的可以”“步骤”“流程”“靠谱吗”等通用词，导致非健康主题也被归到护理痛点。
- 采集评论中存在大量互粉、数字、引流、炫耀收入类噪声，影响痛点提取。

已完成：
- 重构 `config/comment_insight_rules.json`：
  - 新增 `generic_insight_rules`，用于通用主题。
  - 新增 `domain_rule_groups`，只有主题命中领域关键词时才启用专用规则。
  - 将宝宝湿疹相关规则放入 `baby_skin_care` 领域组。
  - 新增 `noise_comment_keywords` 和 `low_value_comments`。
- 改造 `platforms/comment_analysis.py`：
  - 根据 topic 选择通用规则和领域专用规则。
  - 支持 `pain_template`，让痛点文案绑定当前主题。
  - 增加评论噪声过滤。
  - 避免同一条评论重复作为多条 insight 的证据。
  - 无匹配时仍回退到主题级通用痛点。
- 改造 `nodes/content_node.py`：
  - 非健康主题的兜底模板不再固定输出“不替代诊断”。
  - 只有敏感健康上下文才使用诊断边界提示。

已验证：
- `python -m compileall app nodes routers platforms memory scripts llm` 通过。
- “小红书新手选题方法”样本输出：
  - 对主题是否真实可行存在怀疑，需要可信案例和边界说明。
  - 不知道从哪里开始，需要清晰的入门步骤。
  - 担心投入成本或试错风险，需要避坑提醒。
- “宝宝湿疹护理”样本仍能输出：
  - 分不清湿疹、热疹、过敏等相似皮肤问题。
  - 担心是否需要用药、擦药或就医处理。
- 使用真实 run `run_03aaaf930533` 的 raw_comments 回放后，不再出现护理痛点污染。
- mock 图文主流程通过。
- 非健康主题兜底正文不再包含“不替代诊断”。

当前阶段判断：
- 评论洞察从“单领域规则”升级为“通用规则 + 领域规则”基础版。
- 这仍然是规则系统，不是最终智能分类；后续可以引入 LLM/embedding 做评论聚类和主题适配。

建议下一步：
1. 用真实采集再跑一次“小红书新手选题方法”，确认新洞察能带动生成内容变好。
2. 继续补通用评论洞察规则，尤其是学习、职场、电商、母婴、内容创作等高频领域。
3. 稳定后再回到高并发主线：数据库模型和 Redis 队列。

## 2026-06-10 M14.6 内容记忆污染修复

本轮目标是修复真实 API 测试中继续出现的跨领域内容污染：主题为“小红书新手选题方法”时，结果里仍然出现“对护理方法存在疑问，担心建议不靠谱”等健康护理类痛点。

问题判断：
- 当前代码层面的评论洞察规则已经修复，但正在运行的 API 服务不会热更新，需要重启后才会加载新代码。
- `memory/operation_history.json` 中存在历史脏记录，旧的“小红书新手选题方法”记录里已经写入了护理类痛点和标题。
- 这些历史记录会通过 `retrieved_memory` 和 `successful_patterns` 被重新喂给生成链路，导致新内容继续被旧记忆污染。

已完成：
- 在 `memory/operation_store.py` 增加跨领域健康污染过滤。
  - 非健康主题检索历史记忆时，如果记录中含有湿疹、热疹、擦药、用药、就医、诊断、护理方法等健康领域残留，会跳过该记录。
  - 健康主题本身不受影响，例如“宝宝湿疹护理”仍然可以读取健康护理相关历史。
- 新增 `scripts/repair_operation_memory.py`。
  - 默认 dry-run，只报告将修复哪些记录。
  - 使用 `--apply` 时会先备份 `operation_history.json`，再写入修复后的历史记忆。
- 已执行一次修复：
  - 修复 6 条“小红书新手选题方法”历史记录。
  - 备份文件：`memory/operation_history.json.backup_20260610_160400`。
  - 修复后 dry-run 显示 `changed_records_count: 0`。

已验证：
- `python -m compileall app nodes routers platforms memory scripts llm` 通过。
- 评论样本“真的可以做到吗？需要干货...”现在输出：
  - `对「小红书新手选题方法」是否真实可行存在怀疑，需要可信案例和边界说明`
- `find_successful_patterns("小红书新手选题方法")` 不再返回护理类痛点。
- `find_successful_patterns("宝宝湿疹护理")` 仍能返回健康护理主题记录。

下一步：
1. 重启正在运行的 API 服务，否则 `127.0.0.1:8010` 仍可能使用旧代码。
2. 重新运行 `scripts/check_api_run.py`，确认返回结果中的 `insights.pain_points` 不再出现护理类表达。
3. 如果内容质量稳定，再回到高并发主线，继续推进数据库模型和外部队列。

## 2026-06-10 M14.7 内容结构与安全替换修复

本轮目标是处理真实 LLM 输出中的两个新问题：
- `content_type` 显示为 `avoid_mistakes`，但正文实际是步骤教程，摘要与内容结构不一致。
- 安全替换把“不要保证/一定”等表达替坏，出现“不尽量你照做就建议有结果”这类病句。

问题判断：
- `strategy_node` 会先根据痛点命中“避坑”，得到 `avoid_mistakes`。
- `pattern_utils.structure_profile()` 会优先复用高表现历史结构，实际生成时使用了 `step_tutorial`。
- 图文/视频生成节点之前没有把实际使用的结构类型回写到 state，导致最终摘要仍显示旧的策略类型。
- `text_replacements.json` 只有单词级替换，例如 `保证 -> 尽量`、`一定 -> 建议`，破坏了“不保证你照做就一定有结果”的句子结构。

已完成：
- 更新 `config/text_replacements.json`：
  - 新增 `phrase_replacements`，先处理完整短语。
  - 将“不保证你照做就一定有结果”修正为“不是说照做就会直接出结果”。
  - 调整部分单词兜底替换，降低病句概率。
- 更新 `nodes/content_node.py`：
  - 安全替换顺序改为：短语替换 -> 绝对词替换 -> 质量词替换。
  - LLM 图文结果和模板图文结果都会回写实际 `content_type`。
- 更新 `nodes/video_node.py`：
  - 同步使用短语优先的安全替换。
  - LLM 视频结果和模板视频结果都会回写实际 `content_type`。

已验证：
- `python -m compileall app nodes routers platforms memory scripts llm` 通过。
- 替换样本：
  - 输入：`这篇不保证你照做就一定有结果，但能帮你避开一定会踩的坑。`
  - 输出：`这篇不是说照做就会直接出结果，但能帮你避开可能会踩的坑。`
- mock LangGraph 主流程通过。
- mock 结果中 `content_type` 已变为 `step_tutorial`，与步骤正文一致。

下一步：
1. 重启 API 服务。
2. 用真实 LLM 再跑一次“小红书新手选题方法”，重点检查正文最后一段是否仍有病句。
3. 如果内容质量稳定，再继续高并发主线。

## 2026-06-10 M14.8 采集噪声与中文空格清洗

本轮目标是处理 cookie 恢复后真实采集暴露出的两个小问题：
- `raw_comments` 中仍保留“互粉、回复 1、加粉”等噪声评论。
- LLM 正文偶尔出现“再 处理”这类中文词中间异常空格。

已完成：
- 更新 `platforms/comment_analysis.py`：
  - 将噪声评论判断暴露为 `is_noise_comment_text()`。
  - 噪声关键词匹配改为压缩空白后判断，避免换行和空格绕过过滤。
- 更新 `platforms/spider_xhs_collector.py`：
  - 采集层复用评论洞察层的噪声判断，避免两套过滤标准不一致。
- 更新 `nodes/content_node.py` 和 `nodes/video_node.py`：
  - 生成文本清洗阶段移除中文字符之间的异常空格。
  - 保留数字与中文之间的正常空格，例如 `30 篇`、`5-10 个`。

已验证：
- `python -m compileall app nodes routers platforms memory scripts llm` 通过。
- “不够1000人的告诉我 / 让我们成为彼此的粉丝”会被判定为噪声。
- “1”会被判定为噪声。
- “真的可以做到吗？需要干货”会保留。
- “第三步：再 处理。”会被清洗为“第三步：再处理。”。

下一步：
1. 重启 API 服务。
2. 重新跑真实采集，确认 `raw_comments_count` 会下降，但 `comment_insights_count` 仍能稳定保持。
3. 如果采集质量稳定，再回到高并发主线。

补充修复：
- 真实测试中仍发现少量中文异常空格，例如“不匹配 、无法”“一开始 就”“新手穿搭  小个子通勤”。
- 已收紧中文空格清洗规则：
  - 保留段落换行。
  - 删除中文之间的单个异常空格。
  - 删除标点前后的异常空格。
  - 两段中文之间的两个以上空格转成中文逗号，避免直接粘成病句。
  - 保留数字与单位之间的正常空格，例如 `30 篇`、`5-10 个`。
- 已验证：
  - `不匹配 、无法` -> `不匹配、无法`
  - `一开始 就` -> `一开始就`
  - `新手穿搭  小个子通勤` -> `新手穿搭，小个子通勤`

## 2026-06-10 M14.9 可信表达收敛

本轮目标是处理真实 LLM 输出中的“虚构背书”和“过度承诺”表达。

问题表现：
- 标题中出现 `实测可行`、`照着做就行`、`刷了100篇才懂`、`直接抄作业`、`少走半年弯路`。
- 这些表达虽然不一定触发合规风险，但会降低内容可信度；在没有真实输入证据时，不能让模型伪装成已有个人经历或明确承诺结果。

已完成：
- 更新 `config/text_replacements.json`：
  - `照着做就行` -> `可以照着步骤先试`
  - `直接抄作业` -> `可以参考这个步骤`
  - `亲测有效` -> `有参考价值`
  - `实测可行/实测可用` -> `可以按步骤验证`
  - `刷了100篇才懂` -> `看了很多案例后整理`
  - `少走半年弯路` -> `少走一些弯路`
  - `瞎找` -> `盲目找`
- 更新 `config/llm_prompts.json`：
  - 图文和视频系统提示中加入：不要虚构个人经历、验证次数、收益结果或亲测背书。
  - 无输入证据时禁止写 `亲测`、`实测`、`刷了100篇`、`少走半年弯路`、`照着做就行`、`直接抄作业`。

已验证：
- `python -m compileall app nodes routers platforms memory scripts llm` 通过。
- 安全替换样本通过：
  - `实测可行｜...` -> `可以按步骤验证｜...`
  - `照着做就行` -> `可以照着步骤先试`
  - `刷了100篇才懂` -> `看了很多案例后整理`
  - `直接抄作业` -> `可以参考这个步骤`
- LLM prompt 可正常加载，系统提示已包含“不要虚构个人经历”。

下一步：
1. 重启 API 服务。
2. 再跑一次真实 LLM 测试，确认标题不再出现虚构背书和强承诺表达。
3. 若通过，内容质量修复阶段可以收尾，回到高并发主线。

## 2026-06-10 全局进度与工程路线图整理

已新增 `memory/project_status_and_roadmap.md`，用于记录：
- 当前项目总体目标。
- 已完成的主链路能力。
- 当前系统架构。
- 期待的生产级工程形态。
- 尚未实现的关键环节。
- 后续优先级排序。

该文件是后续 `/resume` 或重新进入项目时的全局上下文入口；`current_progress.md` 继续用于记录每轮小步变更。
