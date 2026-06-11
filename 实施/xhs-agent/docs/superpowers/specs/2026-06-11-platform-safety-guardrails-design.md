# M25 平台安全护栏设计

## 目标

M25 补齐真实平台操作前的最小安全护栏，先服务当前主链路中的只读采集和创作者平台私密图文发布。目标不是扩大发布能力，而是在真实 Cookie、真实 Spider_XHS 模式下做到先自检、低频、限量、失败即停。

## 当前上下文

当前系统已经支持：
- `COLLECTOR_MODE=mock|spider_xhs` 的只读采集。
- `CREATOR_MODE=mock|spider_xhs` 的创作者平台适配。
- 审核 API 显式触发私密图文发布。
- 图片素材绑定、作品列表同步、表现回填和失败分类。

现有缺口：
- 采集和 creator 真实模式只有缺 Cookie 时的被动报错，主链路缺少统一 runtime 自检结果。
- creator 发布没有发布前随机延时。
- creator 发布没有单日个位数限制。
- creator 写入失败或疑似风控后，没有本地停手标记阻止后续连续发布。

## 范围

本轮包含：
- 新增平台护栏状态模块，用 JSON 文件记录 creator 当日发布次数和停手原因。
- `platforms.creator` 在真实发布前执行 runtime 自检、发布许可检查和随机延时。
- `platforms.creator` 在真实发布成功后记录当日发布次数。
- `platforms.creator` 在真实发布 `success=False`、异常或疑似风控时记录停手状态。
- `platforms.spider_xhs_collector` 和统一 `platforms.collector` 暴露 Cookie/runtime 自检函数。
- `.env.example` 补充 M25 护栏配置。
- 测试覆盖 guardrail 状态、creator 发布前门禁和 collector 自检。

本轮不包含：
- 公开发布。
- 视频发布。
- 定时发布。
- 发布状态轮询。
- Cookie 自动登录或自动刷新。
- GraphRAG。
- 千帆/蒲公英。
- 前端新增大功能。

## 设计

新增 `platforms/platform_guardrails.py`，只使用标准库和现有 JSON 原子写工具。它负责：
- 从环境变量读取 `XHS_CREATOR_DAILY_LIMIT`，默认 3，最大允许 9。
- 从环境变量读取 `XHS_CREATOR_MIN_DELAY_SECONDS` / `XHS_CREATOR_MAX_DELAY_SECONDS`，默认沿用 2 到 5 秒。
- 从环境变量读取 `XHS_PLATFORM_GUARDRAIL_PATH`，默认 `data/platform_guardrails.json`。
- 提供 `check_creator_publish_allowed()`，当当日次数达到上限或当日已经停手时返回不允许。
- 提供 `sleep_before_creator_publish()`，真实 creator 发布前随机 sleep。
- 提供 `record_creator_publish_success()`，成功后增加当日计数。
- 提供 `record_creator_publish_failure()`，失败或疑似风控后写入当日停手原因。

creator mock 模式不走发布延时、计数和停手，避免影响本地开发与测试。

`platforms.creator.publish_private_image_text()` 的 spider 路径执行顺序：
1. 校验人工确认、标题、正文、图片数量。
2. 校验 creator runtime：模式、Cookie、vendor/API 可导入。
3. 校验当日是否允许发布。
4. 随机延时。
5. 调用 Spider_XHS `post_note(type=1)`。
6. `success=True` 时记录成功次数。
7. `success=False` 或异常时记录停手原因并返回/抛出。

`platforms.collector.check_collector_runtime()` 统一返回结构化结果。mock 模式直接通过；spider 模式检查 PC Cookie、vendor 目录、`NODE_PATH` 和 `XHS_Apis` 导入能力。主采集入口在 spider 模式下先执行这个自检，失败时抛出带明确信息的错误，避免半路才暴露 Cookie 问题。

## 错误处理

creator 写入失败后的停手是本地保护，不自动清除；进入下一自然日后自动使用新日期计数。错误信息继续由 API 层做脱敏后写入 run 和运营记忆。

疑似风控关键词包括 `风控`、`risk`、`频繁`、`验证`、`captcha`、`安全`、`限制`、`blocked`。普通 `success=False` 也会停手，因为当前阶段不应自动重试真实写入操作。

## 测试

新增或扩展测试覆盖：
- creator guardrail 达到当日上限后阻止真实发布。
- creator `success=False` 后记录停手并阻止下一次真实发布。
- creator 真实模式缺 Cookie 时在调用 adapter 前失败。
- creator 真实发布前会调用延时函数。
- collector mock runtime 自检通过。
- collector spider runtime 缺 PC Cookie 时失败。

## 验收

通过以下命令：

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m pytest -q
D:\Anaconda\envs\ContentShare\python.exe -m compileall app nodes routers platforms memory scripts llm
node --check app\static\app.js
```

