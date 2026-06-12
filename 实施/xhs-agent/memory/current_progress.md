# 当前工程进度

## 2026-06-11 creator 发布状态只读同步

本轮目标是在真实 creator v2 作品列表和表现回填烟测之后，补上只读发布状态同步能力。

已完成：
- 新增 `platforms.creator.get_published_note_status()`，可按 `creator_note_id` 从 creator v2 作品列表中匹配平台笔记并归一化状态。
- 状态同步复用 creator v2 作品列表，不触发发布、修改、公开、删除或重试。
- 状态结果包含 `synced` / `not_found` / `unavailable`、可见性提示、权限字段和指标快照。
- 新增 `app.api.get_creator_note_status()` 和只读 `GET /creator/notes/status?creator_note_id=...` 路由。
- 工作台作品列表展示平台状态摘要和浏览/赞/藏/评快照，同时保持点击作品填入 `creator_note_id` 的行为。

已验证：
- `tests/test_creator_platform.py`、`tests/test_creator_note_performance_sync.py`、`tests/test_workbench_creator_notes_static.py` 聚焦测试通过。
- 全量测试通过：`127 passed`。
- `compileall app nodes routers platforms memory scripts llm` 通过。
- `node --check app/static/app.js` 通过。
- 真实只读状态同步可找到 `creator_note_id=6a2abffc0000000022027f7a`，返回 `status=synced`、标题 `M25 私密发布链路验证`、`visibility_label=仅自己可见`，当前指标快照均为 0。

当前限制：
- 本轮不是后台自动轮询，不写回主运营记忆。
- 表现数据仍需通过现有人工表现录入入口写入。
- 普通沙箱网络会被代理拦截，真实 creator 只读验证需要提权执行；这不影响本地 mock/单元测试。

## 2026-06-11 真实 creator_note_id 表现回填烟测

本轮目标是在 creator v2 作品列表同步修复后，继续验证真实 `creator_note_id` 是否能走通“作品列表 -> 表现回填”的本地闭环。

已验证：
- 当前主运营记忆中没有 `creator_note_id=6a2abffc0000000022027f7a` 的记录，因为这条真实私密发布是适配层小流量验证，不是通过完整 run 审核链路产生的记录。
- 使用真实 creator v2 作品列表只读同步，能找到目标笔记：
  - `creator_note_id=6a2abffc0000000022027f7a`
  - 标题：`M25 私密发布链路验证`
- 在系统临时目录创建临时运营记忆文件，登记同一个真实 `creator_note_id` 后调用 `record_performance()`，可按平台笔记 ID 匹配并更新记录。
- 烟测结果为 `status=performance_recorded`，`performance_data={views:0, likes:0, collects:0, comments:0, follows:0}`，`performance_score=0`。
- 表现分为 0 是因为当前平台返回该私密笔记指标均为 0，不是回填链路失败。

当前判断：
- M21 的 `creator_note_id` 表现回填能力对真实平台 ID 可用。
- 若希望主运营记忆中长期保留这条真实笔记，需要后续通过完整 run 审核发布链路生成记录，或明确允许把本次适配层小流量验证登记为一条运营记忆记录。
- 下一步可以继续进入主要链路后续任务；优先建议补发布状态轮询或主链路真实 run 发布验证，二者都属于 M4 真实平台端到端的后半段。

## 2026-06-11 creator 作品列表 v2 同步修复

本轮目标是在真实私密发布成功后，继续排查 creator 作品列表同步失败，恢复“平台作品列表 -> creator_note_id -> 表现回填”的只读链路。

已完成：
- 参考了 `D:\codex\project\小红书内容分享\referrence\Spider_XHS-master`，确认参考版 Spider_XHS 的 creator 列表实现仍使用旧 `/api/galaxy/creator/note/user/posted`，不能直接解决当前真实平台列表失败。
- 从 creator 前端 JS 确认当前真实页面使用 `GET /api/galaxy/v2/creator/note/user/posted`，参数为 `tab=1`、`page=0` 起，响应中的 `page=-1` 表示没有下一页。
- `platforms/creator.py` 的真实作品列表读取改为优先使用 creator v2 接口，旧 vendor 列表接口仅作为兜底，避免旧接口空正文导致成功结果后仍打印 JSONDecode traceback。
- 兼容 v2 响应字段：`id`、`displayTitle` / `display_title`、`type`，并继续归一化为 `note_id`、`title`、`visibility`。
- 作品列表返回的 `raw` 已复用现有敏感字段脱敏工具，避免 `xsec_token`、cookie 等字段暴露到脚本输出或工作台 API。
- 新增 creator 平台测试覆盖 v2 优先、旧接口失败后的 v2 路径、v2 字段归一化和 raw 脱敏。

已验证：
- `D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_creator_platform.py -q` 通过，当前该文件 14 个测试全部通过。
- `D:\Anaconda\envs\ContentShare\python.exe .\scripts\check_creator_platform.py --mode spider_xhs --list --limit 5` 通过，返回 `source=creator_v2`。
- 真实作品列表已包含刚发布的私密笔记 `creator_note_id=6a2abffc0000000022027f7a`，标题为 `M25 私密发布链路验证`，并显示 `permission_msg=仅自己可见`。
- 同一次真实列表输出中 `xsec_token` 已显示为 `<redacted>`，没有再输出原始 token。

当前限制：
- 作品列表同步仍是只读能力，不自动抓取表现指标，不做发布状态轮询。
- 旧 vendor 接口仅保留兜底，后续如果 Spider_XHS 更新，可再评估是否收敛实现。
- 下一步可用真实 `creator_note_id` 做表现回填验证，然后继续进入主要链路后续任务。

## 2026-06-11 真实平台小流量验证记录

本轮目标是在 M25 平台安全护栏完成后，先做真实平台小流量验证。当前只执行只读采集验证，没有执行 creator 真实写入。

已验证：
- 工作树干净，M20-M25 两个提交已落地。
- `scripts/check_runtime_config.py --profile local` 通过：核心模块可导入、日志目录可写、run store 为 JSON、run queue 为 local；仅提示本地 API token 为空。
- `scripts/check_collector.py` 预检通过：`.env` 存在、PC Cookie 存在、vendor 路径存在、`XHS_Apis` 可导入。
- `scripts/check_creator_platform.py --mode spider_xhs --check-only` 未通过：缺少 `XHS_CREATOR_COOKIES`，因此没有执行真实 creator 私密发布。
- 真实只读搜索通过：主题 `小红书新手选题方法`，limit=1，返回 1 条脱敏笔记。
- 真实评论读取通过：对 1 条笔记读取 10 条评论，保留 1 条、过滤 9 条，并生成 1 条 comment insight / pain point。
- 首次未提权执行真实搜索时失败，原因是沙箱代理指向 `127.0.0.1:9`；提权后网络链路正常。

暴露问题：
- 保留的 1 条评论仍明显像“提升成长地方/无偿分享/看下面进4”这类引流噪声，说明评论噪声过滤还需补充规则。
- creator 真实链路目前缺少 `XHS_CREATOR_COOKIES`，只能完成预检失败确认，不能做真实私密发布验证。

下一步建议：
1. 补充评论噪声过滤规则，覆盖“优秀上进的伙伴们、无偿分享、位置不多、自行把握、看下面进”等引流表达。
2. 配置 `XHS_CREATOR_COOKIES` 后，再执行 1 条 creator 私密图文发布小流量验证。
3. 私密发布验证成功后，同步作品列表，确认真实 `creator_note_id` 能用于表现回填。

补充进展：
- 已补充评论噪声过滤规则，新增覆盖“优秀上进的伙伴、提升成长的地方、小红书项目礼物、无偿分享位置不多、自行把握、看下面进”等引流表达。
- 新增 `tests/test_comment_noise_filtering.py`，锁定真实引流样本不再进入 fallback insight。
- 复测真实只读采集：搜索和评论读取仍可执行；本次返回 1 条笔记、0 条评论，最终走主题级默认痛点兜底。
- 再次脱敏检查确认：当前 `实施/xhs-agent/.env`、上级 `.env` 和系统环境中仍没有 `XHS_CREATOR_COOKIES` / `CREATOR_COOKIES`，因此 creator 真实私密发布继续阻塞，尚未执行写入验证。
- 已验证：全量测试 `119 passed`，compileall 通过，`node --check app/static/app.js` 通过。
- 之后发现 creator Cookie 被误写入可提交模板 `.env.example`，已将其移入本地 `.env` 的 `XHS_CREATOR_COOKIES`，并清理 `.env.example`，未提交 Cookie。
- creator 真实模式预检通过：`check_creator_platform.py --mode spider_xhs --check-only` 返回 `ok=true`。
- 已执行 1 条真实 creator 私密图文发布验证，使用本地 JPEG 素材，返回 `mode=spider_xhs`、`visibility=private`、`note_id=6a2abffc0000000022027f7a`。
- M25 本地护栏文件 `data/platform_guardrails.json` 已记录当日 `success_count=1`、`stopped=false`。
- creator 作品列表同步验证未通过：`check_creator_platform.py --mode spider_xhs --list --limit 5` 返回 HTML 404 导致 JSON 解析失败，发布成功但列表同步入口需要后续排查 Spider_XHS creator 列表接口。

## 2026-06-11 M25 平台安全护栏补齐

本轮目标是在 M20-M24 已经打通 creator 私密发布、图片素材绑定、作品同步、表现回填和失败诊断后，回到从0手册主线，补齐真实平台操作前的最小安全护栏。本轮不扩大公开发布、视频发布、定时发布，也不进入 GraphRAG。

已完成：
- 新增 `platforms/platform_guardrails.py`，记录真实 creator 发布当日成功次数、同日停手原因和发布前随机延时。
- creator 真实 `spider_xhs` 发布前会先执行 runtime 自检、当日发布许可检查和随机延时。
- creator 真实发布成功后会累计当日成功次数。
- creator 真实发布 `success=False` 或异常后会记录停手原因，阻止同日后续连续发布。
- creator 日发布限制默认 `3`，并在代码层限制为个位数最大 `9`。
- 新增 collector runtime 自检：mock 直接通过，`spider_xhs` 模式检查 PC Cookie 和 Spider_XHS API 导入能力。
- 统一 collector 入口在 `spider_xhs` 模式下会先执行 runtime 自检，避免缺 Cookie 时半路失败。
- `.env.example` 新增 M25 护栏配置：`XHS_PLATFORM_GUARDRAIL_PATH`、`XHS_CREATOR_DAILY_LIMIT`、`XHS_CREATOR_MIN_DELAY_SECONDS`、`XHS_CREATOR_MAX_DELAY_SECONDS`。
- 新增 `tests/test_platform_safety_guardrails.py`，覆盖当日发布限制、失败停手、creator Cookie 前置自检、发布前延时和 collector Cookie 自检。
- 新增中文设计与计划文档：
  - `docs/superpowers/specs/2026-06-11-platform-safety-guardrails-design.md`
  - `docs/superpowers/plans/2026-06-11-platform-safety-guardrails.md`

当前限制：
- 停手状态是本地 JSON 护栏，不是平台端状态轮询。
- 停手按自然日隔离，下一日自动进入新日期计数。
- Cookie 自检只确认本地配置和导入能力，不发真实登录态探测请求；真实 Cookie 是否已过期仍需后续真实小流量验证。
- 真实发布状态轮询、公开发布、视频发布和定时发布仍未完成。

用户自测建议：
1. mock 模式下运行全量测试，确认本地链路不受护栏影响。
2. 真实采集前配置 `COLLECTOR_MODE=spider_xhs` 和 `XHS_COOKIES_PC`，先运行采集检查脚本。
3. 真实 creator 私密发布前配置 `CREATOR_MODE=spider_xhs` 和 `XHS_CREATOR_COOKIES`。
4. 保持 `XHS_CREATOR_DAILY_LIMIT=3` 或更低，先只做 1 条私密发布验证。
5. 如果出现 `success=False`、风控或异常，先查看 `data/platform_guardrails.json` 和 run 失败诊断，不要连续重试。

## 2026-06-11 M24 结构化失败分类

本轮目标是在 M23 工作台运行诊断的基础上，把失败诊断从前端文本判断升级为后端结构化字段，让 API、运行记录和前端共用同一套失败分类。

已完成：
- 后端新增结构化失败分类字段：`failure_category` 和 `failure_category_label`。
- 顶层 run 失败会根据 `error` 生成失败分类。
- summary 会在 creator publish 失败或高风险合规结果时生成失败分类。
- `/runs` 列表和 `/runs/{run_id}` 详情会对旧记录做响应时补齐，不强制迁移历史 JSON/SQLite 数据。
- 工作台 `diagnoseRunFailure()` 优先使用后端 `failure_category_label`，旧文本关键词判断只保留为兼容兜底。
- 新增 `tests/test_run_failure_category.py`，覆盖分类规则、新 run 写入、summary 写入和旧记录补齐。
- 更新 `tests/test_workbench_run_diagnostics_static.py`，确保前端使用后端分类字段。
- 新增中文实施计划：`docs/superpowers/plans/2026-06-11-structured-failure-category.md`。

当前分类：
- `creator_publish`：创作者平台或发布素材问题。
- `llm_generation`：LLM 生成或解析问题。
- `collection`：采集或 Cookie 问题。
- `compliance`：合规拦截。
- `unknown`：未分类失败，请查看错误详情。
- `null`：没有失败。

当前限制：
- M24 只做结构化失败分类，不做完整链路日志追踪。
- 不做队列级自动重试，也不做真实 creator 发布重试。
- 分类仍基于当前错误文本和状态字段，不是全节点事件审计。

用户自测建议：
1. 启动本地 API 并打开工作台。
2. 点击一条失败或 creator publish failed 的运行记录。
3. 查看“运行诊断”中的失败分类。
4. 如需确认 API 字段，可打开 JSON 标签页查看 `failure_category` 与 `failure_category_label`。
5. 旧记录也应能显示兜底分类，不需要手动迁移历史 run 文件。

## 2026-06-11 M23 工作台运行历史详情与失败诊断

本轮目标是在 M22 已经把运营闭环状态展示清楚后，继续补工作台可用性：让用户点击运行记录后，不必翻 JSON，也能直接看到该任务的请求参数、时间、状态、失败诊断和错误详情，并能用同一组任务参数重新提交一个新 run。

已完成：
- 任务结果区新增“运行诊断”面板，展示任务状态、主题、目标用户、形式、引擎、采集数量、创建时间、更新时间和任务 ID。
- 失败任务会根据错误文本做最小分类提示：创作者平台或发布素材问题、LLM 生成或解析问题、采集或 Cookie 问题、合规拦截，无法分类时提示查看错误详情。
- 诊断面板展示错误详情，优先读取 run error，也兼容 creator publish 错误字段。
- 新增“用此任务参数重新提交”按钮，复用当前 run 的 request 参数调用现有 `POST /runs` 创建新任务，并自动切换到新任务轮询。
- 新增 `tests/test_workbench_run_diagnostics_static.py`，覆盖诊断容器、失败分类、重新提交 payload 和响应式样式契约。
- 新增中文实施计划：`docs/superpowers/plans/2026-06-11-workbench-run-diagnostics.md`。

当前限制：
- M23 只做“复制参数重新提交”，不是队列级自动重试；不会复用原 run ID，也不会恢复原任务内部状态。
- 不做 creator 发布失败的真实平台重试，避免误触发写入类平台操作。
- 失败分类是基于错误文本的最小提示，不替代完整日志和链路追踪。

用户自测建议：
1. 启动本地 API 并打开工作台。
2. 点击任意一条运行记录。
3. 在任务结果区查看“运行诊断”，确认能看到请求参数和运行时间。
4. 如果该任务失败，确认能看到失败分类和错误详情。
5. 点击“用此任务参数重新提交”，确认生成一个新任务并开始轮询。

## 2026-06-11 M22 工作台闭环可视化

本轮目标是在 M20/M21 已经打通“图片绑定 -> 私密发布 -> 作品列表 -> 表现回填”的基础上，把闭环关键状态直接显示在工作台运营记忆列表中，减少用户查找 `creator_note_id` 和确认表现录入状态的成本。本轮不新增真实平台写入行为、不做发布重试、不自动抓取表现指标。

已完成：
- 运营记忆卡片新增创作发布状态、平台笔记 ID、表现状态和表现分的紧凑展示。
- 运营记忆卡片展示已录入的表现数据摘要：曝光、点赞、收藏、评论和关注。
- 运营记忆卡片新增“用这条记录录入表现”按钮，点击后自动把该记录的 `post_id` 和 `creator_note_id` 填入表现录入表单。
- 新增 `tests/test_workbench_memory_visibility_static.py`，覆盖运营记忆状态展示、快捷填表行为和响应式样式契约。

当前限制：
- M22 只做工作台可视化和快捷填表，不自动同步平台表现数据。
- 如果某条运营记忆没有 `creator_note_id`，快捷填表只会填入本地 `post_id`。
- 真实平台发布失败后的重试、状态刷新和定时提醒仍后置。

用户自测建议：
1. 启动本地 API 并打开工作台。
2. 完成一条图文 run 的图片绑定和创作者平台私密发布，让运营记忆中产生 `creator_note_id`。
3. 查看“运营记忆”列表，确认能直接看到“创作发布”“平台笔记”“表现状态”“表现分”。
4. 点击该卡片里的“用这条记录录入表现”。
5. 确认“表现录入”表单自动填入 `post_id` 和 `creator_note_id`。
6. 填入表现数据并点击“录入表现”，确认运营记忆卡片刷新为已录入状态且表现分更新。

## 2026-06-11 M21 作品列表同步后的表现数据回填入口

本轮目标是在 M19/M20 已经具备 creator 发布和图片素材绑定后，补上“平台作品列表 -> 表现录入”的最小闭环。当前不自动抓取点赞/收藏/评论等表现数据，只让用户从作品列表选择 `creator_note_id`，再人工录入表现。

已完成：
- 新增 `GET /creator/notes?limit=20`，复用 `platforms.creator.list_published_notes()` 返回 mock 或真实 creator 作品列表。
- `POST /performance` 支持 `creator_note_id`，现在可以按本地 `post_id` 或平台 `creator_note_id` 查找运营记忆记录并更新表现数据。
- `memory.operation_store.update_record_performance()` 支持 `creator_note_id` 查找，同时保持原有 `post_id` 路径优先。
- 工作台表现录入区新增 `creator_note_id` 输入框和“同步作品列表”按钮。
- 同步出的作品列表可点击，点击后自动填入表现录入表单的 `creator_note_id`。
- 新增 `tests/test_creator_note_performance_sync.py`，覆盖作品列表 API、按 `creator_note_id` 录表现、缺少标识时报错。
- 新增 `tests/test_workbench_creator_notes_static.py`，覆盖前端同步入口、作品渲染和表现 payload 契约。

当前限制：
- 作品列表同步只返回平台已有字段，不自动抓取表现指标。
- 表现数据仍需人工录入曝光、点赞、收藏、评论和关注。
- `creator_note_id` 必须已经写入某条运营记忆，才能用它回填表现；否则后端会提示找不到对应记录。

用户自测建议：
1. 先用 mock creator 发布一条图文 run，让运营记忆里产生 `creator_note_id`。
2. 到工作台“表现录入”区点击“同步作品列表”。
3. 点击同步出来的一条作品，确认 `creator_note_id` 自动填入。
4. 填入曝光、点赞、收藏、评论、关注。
5. 点击“录入表现”，确认提示更新成功。
6. 在运营记忆列表中确认该记录状态变为 `performance_recorded`，表现分不再是 0。

## 2026-06-11 M20 真实图片素材输入/选择链路

本轮目标是在不引入新 Web 框架、不做图片生成和排版的前提下，让已生成的图文 run 可以绑定真实本地图片素材，并在审核勾选“同时私密发布到创作者平台”时，把真实图片 bytes 交给 creator adapter。

已完成：
- 新增 run 级图片素材绑定能力：`POST /runs/{run_id}/creator-assets` 接收浏览器传来的 base64 图片 JSON。
- 后端会校验图片数量、base64 内容和图片魔数，只接受 PNG/JPG/GIF/BMP/WebP 等有效图片 bytes。
- 图片文件保存到 `data/creator_assets/<run_id>/`，run JSON 里只保存文件路径、图片数量和更新时间，避免把图片 bytes 直接塞进 run state。
- 审核触发 creator publish 时，后端会优先读取已绑定图片文件并传入 `publish_private_image_text()`。
- 工作台审核区新增图片选择框和“绑定发布图片”按钮；绑定成功后摘要区展示“发布图片”数量。
- 绑定入口只在成功生成、待审核、图文内容时可用；视频和已审核 run 不支持绑定。
- 新增 `tests/test_creator_asset_binding.py` 覆盖后端绑定、真实模式发布读取 bytes、非法图片拒绝。
- 新增 `tests/test_workbench_creator_assets_static.py` 覆盖前端入口、payload 契约和摘要展示。

当前限制：
- M20 只解决真实素材输入/选择，不生成图片、不做多图排版、不做封面图渲染。
- 仍只支持图文私密发布；视频发布、公开发布、定时发布、失败重试继续后置。
- 工作台通过浏览器文件选择上传图片内容；没有做素材库管理、删除、重排和预览。

用户自测建议：
1. 启动本地 API。
2. 打开工作台并提交一个图文 run。
3. run 成功后，在审核区选择 1 张或多张本地 PNG/JPG/WebP 图片。
4. 点击“绑定发布图片”，确认摘要区“发布图片”数量变为对应数量。
5. 勾选“同时私密发布到创作者平台”。
6. 点击“审核通过并保存”。
7. mock 模式下确认“创作发布”为成功，并出现平台笔记 ID。
8. 真实 `spider_xhs` 模式下，先配置 creator Cookie，再重复以上步骤；如果失败，预期不应再是缺少 `image bytes`。

## 2026-06-11 M19c 工作台创作者平台发布入口

本轮目标是把 M19b 已完成的审核后私密发布能力接到工作台前端，让用户在审核区显式勾选后，才请求创作者平台私密发布。

已完成：
- 工作台审核区新增“同时私密发布到创作者平台”勾选项，默认不勾选，不改变原有本地保存 Markdown 和写入运营记忆行为。
- 勾选后点击“审核通过并保存”会向后端发送 `creator_publish=true`、`creator_publish_private=true`、`creator_human_confirmed=true`。
- 未勾选时，审核通过 payload 仍只执行原有本地审核保存链路。
- 摘要区新增创作发布状态展示：未请求、成功、失败。
- 摘要区新增平台笔记 ID 展示，后端返回 `creator_note_id` 时可直接看到。
- 审核提示区会展示后端已经脱敏的 `creator_publish_error`，便于确认创作者平台发布失败原因。
- 新增 `tests/test_workbench_creator_publish_static.py`，覆盖前端入口、payload 条件和展示契约。

当前限制：
- 真实 `spider_xhs` 私密发布仍要求 run state 内有真实图片字节；当前工作台还没有图片素材上传或选择入口。
- 暂不支持视频发布、公开发布、定时发布和失败重试。
- 当前测试是静态契约测试，尚未额外跑浏览器 UI smoke。

建议下一步：
1. 进入真实图片素材输入/选择链路，让 `spider_xhs` 私密图文发布具备真实素材来源。
2. 或先补作品列表同步后的表现数据回填入口，为后续复盘闭环做准备。

## 2026-06-11 M19b 审核通过后私密发布接入

本轮目标是在不改变前端默认行为的前提下，把创作者平台私密发布接入审核 API。默认审核仍只保存本地 Markdown 和写入运营记忆；只有审批请求显式带 `creator_publish=true`、`creator_publish_private=true`、`creator_human_confirmed=true` 时，才触发创作者平台私密发布。

已完成：
- `approve_run()` 支持显式 creator publish 参数。
- 默认审核不调用创作者平台，保持本地 Markdown 草稿保存和运营记忆写入行为。
- mock 模式私密发布结果会回填 `creator_note_id`、`creator_publish_mode` 和 `creator_publish_status`。
- 视频内容请求 creator publish 时会保存本地草稿，但 creator publish 标记为失败且不调用适配器。
- 创作者平台异常不会抹掉本地草稿保存结果，运营记忆仍会写入失败状态。
- 运营记忆记录 creator publish 元数据：请求状态、发布状态、模式、note ID 和脱敏后的错误。
- 真实 `spider_xhs` 模式要求有效图片字节；缺图片、非 bytes 占位和假 bytes 会在调用真实适配器前失败。
- creator publish 错误进入 run summary、state 和 operation memory 前会做基础脱敏，避免 cookie、token、authorization、password、api key 等值直接落盘。
- 新增 Windows pytest 临时目录权限兼容处理，将测试临时目录切到 `data/pytest_tmp_safe`，并只在该目录范围内放宽 pytest 的 `0o700` mkdir 模式。

已验证：
- `D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_api_creator_review_publish.py -q` 通过，12 个审核发布测试全部通过。
- `D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_creator_platform.py -q` 通过，11 个创作者平台测试全部通过。
- `D:\Anaconda\envs\ContentShare\python.exe -m pytest -q` 通过，当前 82 个测试全部通过。
- 规格复核通过：M19b Tasks 1-4 符合设计。
- 代码质量复核通过：真实模式假图片字节、错误脱敏和 pytest Windows 临时目录补丁问题均已修复。

当前限制：
- 前端暂未新增“同时私密发布到创作者平台”的勾选项；目前需要直接调用审批 API 参数触发。
- 真实 `spider_xhs` 发布还需要 run state 里有真实图片字节，当前主链路尚未生成或选择实际图片素材。
- 暂不支持视频、公开发布、定时发布和失败重试。

建议下一步：
1. 进入 M19c：前端增加“同时私密发布到创作者平台”的明确勾选项，并展示 creator 发布状态。
2. 或先补真实图片字节生成/选择链路，让 `spider_xhs` 真实私密发布具备素材输入。
3. 公开发布、视频发布、蒲公英和千帆继续后置。

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

## 2026-06-11 主链真实采集 + LangGraph 验证

本轮目标是把验证重心从 mock 和前端补洞拉回主链：真实 PC 采集、LangGraph 编排、真实 LLM、日志落盘。

执行过程：
- 先检查 `.env`：`COLLECTOR_MODE=spider_xhs`，`LLM_MODEL_NAME=deepseek-v4-pro`，`LLM_BASE_URL=https://api.deepseek.com`，PC Cookie 和 creator Cookie 均已存在。
- 发现旧 8010 API 进程实际继承了 mock 环境变量，导致 run 虽然成功但 `llm_generation.error=LLM is in mock mode`，采集结果也是 mock 样本。
- 在 8012 用显式真实环境变量启动 API 后，确认不再回到 mock，但普通沙箱网络会把外部请求导向 `127.0.0.1:9`，导致小红书和 DeepSeek 都出现 `ProxyError`。
- 按权限规则提权后，在 8013 启动真实网络 API，重新提交同一条 LangGraph 主链。

真实主链验证结果：
- API：`http://127.0.0.1:8013`
- run：`run_c91c97a1d502`
- 状态：`success`
- 引擎：`langgraph`
- 采集：`raw_notes_count=1`，`raw_comments_count=9`，`comment_fetch_errors_count=0`
- 评论洞察：`comment_insights_count=1`，`pain_points_count=1`
- 运营记忆召回：`retrieved_memory_count=5`
- LLM：`enabled=true`，`provider_mode=openai_compatible`，`model=deepseek-v4-pro`
- token：`prompt_tokens=987`，`completion_tokens=2328`，`total_tokens=3315`
- 合规：`compliance_risk_level=low`
- 首条真实笔记标题：`新人起号靠的不是日更而是关键词`
- 生成首标题：`小红书选题先别急着判断，这几个坑要避开`
- 日志：`data/logs/api.log` 已记录 8013 启动和 `run_c91c97a1d502` 轮询请求。

额外发现：
- `scripts/check_api_run.py` 在 Windows GBK 控制台打印包含 `⭐` 的 JSON 时会触发 `UnicodeEncodeError`。主链本身已成功，后续建议单独修复该脚本的输出编码，避免真实结果包含 emoji 时误报命令失败。
- 后续验证真实网络链路时，应优先使用非沙箱网络启动 API；普通沙箱只适合 mock 或本地接口验证。

下一步建议：
1. 旧的 8010/8012 API 进程已停止，目前只保留 8013 真实网络实例，防止误连到 mock 或沙箱网络实例。
2. 修复 `scripts/check_api_run.py` 的 Windows 输出编码问题。
3. 基于 8013 继续做“审核通过保存草稿 -> 人工确认 -> 私密发布/表现回填”的主链后半段验证。

## 2026-06-11 check_api_run Windows 输出编码修复

本轮目标是修复 `scripts/check_api_run.py` 在 Windows GBK 控制台打印真实 run JSON 时，遇到 emoji 等非 GBK 字符会抛出 `UnicodeEncodeError` 的问题。

已完成：
- 在 `tests/test_check_api_run_auth.py` 增加回归测试，模拟 `encoding="gbk"`、`errors="strict"` 的 stdout，打印包含 `⭐` 的 JSON。
- 在 `scripts/check_api_run.py` 增加 `_print_line()`，脚本输出优先按原文本写出；如果 stdout 编码不支持某些字符，则用 `backslashreplace` 转义不可编码字符，避免脚本崩溃。
- 将脚本内直接 `print()` 的地方切换为 `_print_line()`，覆盖提交状态、轮询状态、错误文本和最终 JSON。

已验证：
- RED：新增测试在旧实现下复现 `UnicodeEncodeError`。
- GREEN：`D:\Anaconda\envs\ContentShare\python.exe -m pytest tests\test_check_api_run_auth.py::test_print_json_handles_gbk_stdout_with_emoji -q` 通过。
- 相关测试：`D:\Anaconda\envs\ContentShare\python.exe -m pytest tests\test_check_api_run_auth.py -q`，4 passed。
- 编译：`D:\Anaconda\envs\ContentShare\python.exe -m compileall scripts\check_api_run.py` 通过。

当前仍需注意：
- 真实小红书和真实 LLM 验证需要非沙箱网络，否则会出现 `127.0.0.1:9` 代理失败。
- 8013 是当前保留的真实网络 API 实例；不要误连旧的 8010/8012。
- 下一步主链后半段建议继续验证：审核保存草稿 -> 私密发布/状态同步 -> 表现回填。

## 2026-06-11 采集策略与后续 RAG 基础记录

讨论结论：
- 数据采集不应简单选择评论数、点赞数、收藏数最多的笔记。
- 高互动指标应作为重要排序因子，但不是唯一标准。
- 后续更适合作为 RAG 基础的采集策略是“高相关 + 高质量互动”候选池。

建议采集逻辑：
1. 搜索关键词后先形成候选池，例如前 20-50 篇。
2. 先按主题相关度过滤偏题笔记。
3. 再综合评论数、点赞数、收藏数、近期程度、账号体量等指标排序。
4. 对前 5-10 篇抓评论。
5. 评论层过滤互粉、引流、水军、抽奖、低价值情绪噪声。
6. 最终把“真实问题密度高”的评论和笔记沉淀为后续 RAG 记忆输入。

后续实现时机：
- 不建议立刻进入复杂 GraphRAG。
- 当前优先继续跑通主链后半段：审核保存草稿 -> 私密发布/状态同步 -> 表现回填。
- 等真实主链稳定后，再做采集候选池评分与 RAG 数据结构，这样沉淀的数据才可靠。

## 2026-06-11 主链后半段：审核保存草稿验证

本轮继续主链后半段的第一步：对真实采集 + LangGraph + 真实 LLM 生成的 run 执行人工审核通过，但不触发创作者平台发布。

验证对象：
- API：`http://127.0.0.1:8013`
- run：`run_c91c97a1d502`
- 审核前状态：`status=success`，`publish_status=pending`，`human_approved=false`

执行结果：
- 审核接口：`POST /runs/run_c91c97a1d502/approve`
- 返回：`ok=true`
- `publish_status=success`
- `human_approved=true`
- `operation_memory_written=true`
- `operation_record_id=op_32545c8a8d31`
- `creator_publish_requested=false`
- `creator_publish_status=not_requested`
- Markdown 草稿：`output/markdown_exports/20260611_235133_小红书选题先别急着判断，这几个坑要避开.md`
- API 日志：`data/logs/api.log` 已记录 `run_approved run_id=run_c91c97a1d502`

当前判断：
- 主链已从“待人工审核”推进到“审核通过并保存本地草稿/运营记忆”。
- 因本次未绑定创作者图片素材、也未请求 creator 发布，所以没有触发私密发布。
- 下一条主链任务应使用新 run 做“绑定真实图片素材 -> 审核通过并请求私密发布 -> 状态同步 -> 表现回填”，因为已保存的 run 不能再绑定 creator assets。

## 2026-06-12 主链后半段：真实私密发布、状态同步、表现回填

本轮目标是验证完整的后半段真实闭环：新 run -> 绑定图片素材 -> 审核通过并请求创作者平台私密发布 -> 作品状态同步 -> 按 creator_note_id 表现回填。

执行前提：
- `scripts/check_creator_platform.py --mode spider_xhs` 预检通过：`ok=true`。
- 重新启动 8014 API，并显式设置：
  - `COLLECTOR_MODE=spider_xhs`
  - `CREATOR_MODE=spider_xhs`
  - `LLM_MODEL_NAME=deepseek-v4-pro`
- 8014 运行在非沙箱网络环境，避免真实小红书/LLM 请求走 `127.0.0.1:9`。

执行结果：
- 新 run：`run_d2572a74de62`
- run 状态：`success`
- 真实采集：`raw_notes_count=1`，`raw_comments_count=0`
- LLM：`enabled=true`，`model=deepseek-v4-pro`
- 本地生成中性测试封面：`data/manual_creator_assets/run_d2572a74de62_cover.png`
- 图片绑定接口：`POST /runs/run_d2572a74de62/creator-assets`
- 绑定结果：`creator_images_count=1`
- 审核发布接口：`POST /runs/run_d2572a74de62/approve`
- 发布结果：
  - `publish_status=success`
  - `creator_publish_requested=true`
  - `creator_publish_status=success`
  - `creator_publish_mode=spider_xhs`
  - `creator_note_id=6a2adc0c000000003502cd53`
  - `operation_record_id=op_247efc20de96`
- 状态同步：
  - `GET /creator/notes/status?creator_note_id=6a2adc0c000000003502cd53`
  - `status=synced`
  - `visibility_label=仅自己可见`
  - `metrics_snapshot={views:0, likes:0, collects:0, comments:0}`
- 表现回填：
  - `POST /performance`
  - `updated_record.record_id=op_247efc20de96`
  - `status=performance_recorded`
  - `creator_note_id=6a2adc0c000000003502cd53`
  - `performance_score=0`

重要观察：
- 这次真实采集命中的笔记互动为 0，导致 `raw_comments_count=0`。这再次证明后续必须做“候选池 + 综合评分 + 评论质量评分”，不能只取搜索结果第一条或低互动候选。
- 状态同步第一次请求曾短暂返回 `not_found`，随后作品列表和状态接口均能查到新笔记，说明平台发布后列表可能存在短暂同步延迟；后续应做轮询/等待。
- 当前测试图片是本地生成的中性测试图，不是最终内容生产素材。下一阶段可尝试根据生成文本内容调用 GPT-image 系列模型生成图片，再走同一套 `creator-assets` 绑定和私密发布流程。

下一步建议：
1. 调研并确认 OpenAI 图片生成 API 和实际模型名/API Key 配置，不要直接假设 `GPT-image-2` 可用。
2. 做“文本内容 -> 图片提示词 -> 生成图片 -> 保存到 data/generated_assets -> 绑定 creator-assets”的独立最小链路。
3. 图片生成链路通过后，再替换当前手动/本地测试图素材绑定。

补充调研：
- 本地 `.env` 目前没有 `OPENAI_API_KEY`、`OPENAI_BASE_URL`、`OPENAI_IMAGE_MODEL` 或 `GPT_IMAGE_MODEL`。
- 当前代码中没有 OpenAI 图片生成集成，只有 OpenAI-compatible 文本 LLM 配置，且目前指向 DeepSeek。
- 官方 OpenAI 文档显示图片生成可通过 Image API `images.generate` 使用 `gpt-image-2`，但该模型可能需要组织验证。
- 旧 8013 API 已停止，目前保留 8014 真实 creator 模式 API。

## 2026-06-12 GPT-image-2 生图素材链路：代码就绪，真实请求被 key 拒绝

本轮目标是在已跑通的私密发布闭环基础上，尝试用 OpenAI 图片模型根据 run 文本内容生成封面图，再复用 `creator-assets` 绑定流程。

已完成工程改动：
- 新增 `platforms/openai_image.py`，封装 OpenAI Images API 配置读取、提示词构造、图片请求、base64 解码和本地保存。
- 新增 `scripts/generate_creator_image_asset.py`，支持从 `GET /runs/{run_id}` 读取内容，生成图片，保存到 `data/generated_assets/`，并可选绑定到 `/runs/{run_id}/creator-assets`。
- `.env.example` 增加 `OPENAI_API_KEY`、`OPENAI_BASE_URL`、`OPENAI_IMAGE_MODEL`、`OPENAI_IMAGE_SIZE` 等图片生成配置模板。
- 修复脚本 `--prompt-out` 写入时父目录不存在的问题，新增 `write_prompt()`。
- 新增 OpenAI 图片错误脱敏，避免 HTTP 错误体回显 `sk-...` key 片段。

验证结果：
- 单测与编译：
  - `D:\Anaconda\envs\ContentShare\python.exe -m pytest tests\test_openai_image_generation.py tests\test_generate_creator_image_asset.py tests\test_creator_asset_binding.py tests\test_check_api_run_auth.py -q`
  - 结果：`16 passed`
  - `D:\Anaconda\envs\ContentShare\python.exe -m compileall platforms\openai_image.py scripts\generate_creator_image_asset.py`
  - 结果：通过
- 配置来源检查：
  - `.env` 已存在 `OPENAI_API_KEY`
  - 脚本实际加载的是 `.env` 中的 key，未被系统环境变量覆盖
  - `OPENAI_IMAGE_MODEL=gpt-image-2`
  - `OPENAI_BASE_URL=https://api.openai.com/v1`
- 真实命令：
  - `D:\Anaconda\envs\ContentShare\python.exe .\scripts\generate_creator_image_asset.py --base-url http://127.0.0.1:8014 --run-id run_fda76a64a278 --bind --prompt-out data\generated_assets\run_fda76a64a278_prompt.txt`
  - OpenAI 返回：HTTP 401，`code=invalid_api_key`
  - 脱敏复验通过：错误输出中的 key 已替换为 `[REDACTED_OPENAI_KEY]`

当前判断：
- 这一步还没有通过 GPT-image-2 生图测试；没有生成图片，也没有绑定到 `run_fda76a64a278`。
- 代码侧最小链路已就绪，当前卡点是 `.env` 里的 OpenAI key 不被官方 OpenAI endpoint 接受，或该 key 不对应 `https://api.openai.com/v1`。
- 如果使用官方 OpenAI，需要更换/重新生成有效 API key。
- 如果使用中转或代理服务，需要同时设置对应的 `OPENAI_BASE_URL`，不能只填代理 key 并沿用官方 base URL。

下一步建议：
1. 先更新 `.env` 中的 `OPENAI_API_KEY`，或补充正确的 `OPENAI_BASE_URL`。
2. 更新后重新执行同一条 `generate_creator_image_asset.py` 命令。
3. 生图绑定成功后，再检查生成图片质量，并继续执行私密发布、状态同步、表现回填。

## 2026-06-12 GPT-image-2 中转服务新 key 诊断

本轮用户更换图片服务 key 后重新验证生图链路。

当前 `.env` 图片配置：
- `OPENAI_BASE_URL=https://yituoshiai.com/v1`
- `OPENAI_IMAGE_MODEL=gpt-image-2`
- `OPENAI_IMAGE_SIZE=1024x1536`
- `OPENAI_IMAGE_QUALITY=medium`
- `OPENAI_IMAGE_FORMAT=png`
- 新 key 可被脚本加载，未在日志中输出明文。

诊断结果：
- `GET https://yituoshiai.com/v1/models` 返回 `200`，JSON 正常，模型列表包含 `gpt-image-2`。
- 使用主链脚本执行真实生图绑定：
  - `scripts/generate_creator_image_asset.py --base-url http://127.0.0.1:8014 --run-id run_fda76a64a278 --bind`
  - 返回 `HTTP 503`，错误：`No available compatible accounts`。
- 直接调用 `POST /v1/images/generations` 做最小参数诊断：
  - payload 仅包含 `model=gpt-image-2`、`prompt`、`size=1024x1536`
  - 返回同样 `HTTP 503 No available compatible accounts`。
- 将 size 改为 `1024x1024` 后仍返回同样 `HTTP 503 No available compatible accounts`。

当前判断：
- 新 key 不再表现为 `invalid_api_key`，认证和 `/models` 访问是通的。
- 失败不由本项目脚本的 `quality`、`output_format` 或 `1024x1536` 尺寸导致。
- 根因更可能在中转服务侧：`gpt-image-2` 虽然出现在模型列表，但默认分组下没有可用于 `/images/generations` 的兼容账号/通道，或后台没有给当前 key 分配可用图片生成账号。

下一步建议：
1. 在中转服务后台确认当前 key 所属分组是否已绑定可用的 `gpt-image-2` 图片生成通道。
2. 如果后台实际模型名不是 `gpt-image-2`，需要把 `.env` 的 `OPENAI_IMAGE_MODEL` 改成服务商给出的真实可用模型名。
3. 通道可用后再重跑 `generate_creator_image_asset.py`，成功后继续图片质量检查和私密发布链路。

## 2026-06-12 GPT-image-2 第二个中转服务 key 诊断

本轮用户再次更换图片服务 key 后重新验证生图链路。

当前 `.env` 图片配置：
- `OPENAI_BASE_URL=https://api.xingyuzhida.me/v1`
- `OPENAI_IMAGE_MODEL=gpt-image-2`
- `OPENAI_IMAGE_SIZE=1024x1536`
- `OPENAI_IMAGE_QUALITY=medium`
- `OPENAI_IMAGE_FORMAT=png`
- 新 key 可被脚本加载，未在日志中输出明文。

诊断结果：
- `https://api.xingyuzhida.me/models` 返回 HTML，不是 API JSON。
- `https://api.xingyuzhida.me/v1/models` 返回 `200`，JSON 正常。
- `/v1/models` 中包含 `gpt-image-1`、`gpt-image-1.5`、`gpt-image-2`，当前 `OPENAI_IMAGE_MODEL=gpt-image-2` 存在。
- 修正 `.env` 的 `OPENAI_BASE_URL` 为带 `/v1` 后，主链脚本访问 `/v1/images/generations`。
- 主链脚本仍返回 `HTTP 503`：`No available compatible accounts`。
- 直接调用 `/v1/images/generations` 做最小参数诊断：
  - `size=1024x1536` 返回同样 `HTTP 503 No available compatible accounts`。
  - `size=1024x1024` 返回同样 `HTTP 503 No available compatible accounts`。

当前判断：
- 新 key 认证可用，base URL 修正后也能访问模型列表。
- 失败不是由项目脚本额外参数、图片格式、质量参数或竖图尺寸引起。
- 根因仍更可能是中转服务侧：当前 key/分组没有可用于 `gpt-image-2` 图片生成的兼容账号或通道。

下一步建议：
1. 在中转服务后台确认当前 key 的 `gpt-image-2` 图片生成通道是否真的启用。
2. 如果服务商要求使用 `gpt-image-1` 或 `gpt-image-1.5`，可临时把 `.env` 的 `OPENAI_IMAGE_MODEL` 改成对应模型再测。
3. 服务端通道可用后，再重跑 `generate_creator_image_asset.py` 完成图片生成和绑定。

## 2026-06-12 M25 主流程护栏：平台状态只读入口

本轮按用户要求先暂停生图问题，继续主流程。对照现有代码后确认：
- 创作者平台发布日限、失败停手、发布前 Cookie 自检、发布前随机延时已有实现和测试。
- 采集端 PC Cookie 自检已有实现和测试。
- 主流程缺口之一是这些运行状态不够前置可见，工作台或脚本只能在真正提交/发布时才看到问题。

已完成：
- 新增 `app.api.platform_status()`。
- 新增 `GET /platform/status`，返回只读状态，不触发真实采集或真实发布。
- 返回内容包括：
  - `collector_runtime`
  - `creator_runtime`
  - `creator_publish_guardrail`
- 该接口默认走现有 API 鉴权规则，和 `/queue` 一样不是公开健康检查。
- 新增 `tests/test_api_platform_status.py` 覆盖函数聚合和 HTTP 路由。

已验证：
- RED：新增测试在旧代码下失败，缺少 `collector_platform` 和 `/platform/status`。
- GREEN：实现后 `tests/test_api_platform_status.py` 通过。
- 相关回归：
  - `D:\Anaconda\envs\ContentShare\python.exe -m pytest tests\test_api_platform_status.py tests\test_platform_safety_guardrails.py tests\test_api_auth.py tests\test_api_creator_review_publish.py tests\test_creator_platform.py -q`
  - 结果：`47 passed`
- 编译：
  - `D:\Anaconda\envs\ContentShare\python.exe -m compileall app\api.py`
  - 结果：通过

当前判断：
- M25 的底层护栏已部分可用，并且现在有了 API 层只读状态入口。
- 下一步可以把工作台或检查脚本接到 `/platform/status`，让真实主链提交/私密发布前先显示 Cookie、creator 状态和发布日限/停手原因。

## 2026-06-12 M25 主流程护栏：工作台平台状态可视化

本轮继续主流程，承接 `/platform/status` 只读入口，把采集端、创作者端和发布护栏状态前置展示到工作台。

已完成：
- 工作台侧边栏新增“平台状态”面板。
- 前端 `refreshShell()` 并行请求 `GET /platform/status`，并渲染：
  - 采集端 runtime 状态。
  - 创作者端 runtime 状态。
  - 发布护栏允许/暂停状态、当日发布计数或停手原因。
- 状态面板只读，不触发真实采集、真实发布或作品列表同步。
- `scripts/check_workbench_ui.py` 增加平台状态面板 smoke 检查，避免后续 UI 改动漏掉该面板。
- 新增/更新测试：
  - `tests/test_api_platform_status.py`
  - `tests/test_workbench_platform_status_static.py`

已验证：
- TDD RED/GREEN：先让 smoke 脚本平台状态覆盖测试失败，再补脚本检查并转绿。
- 局部回归：`25 passed`。
- 全量测试：`143 passed`。
- 编译检查：`D:\Anaconda\envs\ContentShare\python.exe -m compileall app platforms scripts` 通过。
- 浏览器 smoke：
  - desktop：`ok=true`，`console_errors=[]`
  - mobile：`ok=true`，`console_errors=[]`
- `git diff --check` 返回 0，仅有 Git 换行提示。

当前判断：
- M25 平台护栏已经从底层检查推进到 API 和工作台可见。
- 下一条主链任务建议做“发布状态轮询/等待”，因为真实私密发布后作品列表可能短暂 `not_found`，目前只查一次会造成误判。
- 另一个后续主线是采集候选池评分，解决真实采集时误选低互动/低评论笔记的问题；但它更适合排在发布状态轮询之后。
