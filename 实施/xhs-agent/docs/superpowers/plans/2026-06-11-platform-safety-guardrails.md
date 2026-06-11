# M25 平台安全护栏 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the smallest production guardrails for real Spider_XHS collection and creator private publishing: runtime checks, random creator publish delay, daily publish limit, and stop-on-failure protection.

**Architecture:** Add a focused `platforms/platform_guardrails.py` module for local safety state and delay handling. Integrate it into the existing `platforms.creator` spider-only path and expose collector runtime checks through `platforms.collector`. Keep mock mode fast and side-effect-free.

**Tech Stack:** Python standard library, pytest, existing JSON atomic write helpers, existing Spider_XHS adapter pattern.

---

## 文件结构

- 新增：`platforms/platform_guardrails.py`
  - 负责 creator 发布次数、停手状态、随机延时和疑似风控判断。
- 修改：`platforms/creator.py`
  - spider 发布前调用 runtime 自检、护栏许可和延时；发布成功/失败后记录护栏状态。
- 修改：`platforms/spider_xhs_collector.py`
  - 新增 `check_collector_runtime()`。
- 修改：`platforms/collector.py`
  - 暴露统一 `check_collector_runtime()`，spider 采集前执行自检。
- 修改：`.env.example`
  - 补充 M25 护栏配置。
- 新增：`tests/test_platform_safety_guardrails.py`
  - 覆盖护栏状态、creator 门禁和 collector 自检。
- 修改：`memory/current_progress.md`
  - 完成后记录 M25 进度、验证命令和剩余任务。

## 任务 1：写失败测试

- [ ] 新增 `tests/test_platform_safety_guardrails.py`，覆盖：
  - `check_creator_publish_allowed()` 在达到 `XHS_CREATOR_DAILY_LIMIT=2` 后阻止发布。
  - `record_creator_publish_failure()` 后同日阻止发布。
  - `creator.publish_private_image_text()` 在 spider 模式缺 Cookie 时不调用 `_load_creator_api()`。
  - `creator.publish_private_image_text()` 在 spider 模式发布前调用 `sleep_before_creator_publish()`。
  - `collector.check_collector_runtime()` 在 mock 模式通过。
  - `collector.check_collector_runtime()` 在 spider 模式缺 PC Cookie 时失败。

- [ ] 运行：

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_platform_safety_guardrails.py -q
```

预期：失败，原因是新模块和函数还不存在。

## 任务 2：实现护栏模块

- [ ] 新增 `platforms/platform_guardrails.py`：
  - `PlatformOperationBlocked(RuntimeError)`
  - `creator_daily_limit()`
  - `check_creator_publish_allowed(now=None)`
  - `ensure_creator_publish_allowed(now=None)`
  - `sleep_before_creator_publish()`
  - `record_creator_publish_success(now=None)`
  - `record_creator_publish_failure(reason, now=None)`
  - `is_risk_control_response(value)`

- [ ] 运行：

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_platform_safety_guardrails.py -q
```

预期：与 creator/collector 集成相关测试仍失败，护栏模块直接行为通过。

## 任务 3：接入 creator 和 collector

- [ ] 修改 `platforms/creator.py`：
  - spider 发布前调用 `check_creator_runtime()`。
  - spider 发布前调用 `platform_guardrails.ensure_creator_publish_allowed()`。
  - spider 发布前调用 `platform_guardrails.sleep_before_creator_publish()`。
  - `success=True` 后调用 `record_creator_publish_success()`。
  - `success=False` 或异常时调用 `record_creator_publish_failure()`。

- [ ] 修改 `platforms/spider_xhs_collector.py`：
  - 新增 `check_collector_runtime()`，检查 PC Cookie、vendor 和 API 导入。

- [ ] 修改 `platforms/collector.py`：
  - 新增统一 `check_collector_runtime()`。
  - spider 模式 `collect_topic_insights()` 前先检查 runtime。

- [ ] 运行：

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_platform_safety_guardrails.py -q
```

预期：M25 新测试通过。

## 任务 4：配置、记忆和全量验证

- [ ] 修改 `.env.example`，新增：
  - `XHS_PLATFORM_GUARDRAIL_PATH=data/platform_guardrails.json`
  - `XHS_CREATOR_DAILY_LIMIT=3`
  - `XHS_CREATOR_MIN_DELAY_SECONDS=2`
  - `XHS_CREATOR_MAX_DELAY_SECONDS=5`

- [ ] 修改 `memory/current_progress.md`，记录 M25 完成内容、限制和验证命令。

- [ ] 运行：

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m pytest -q
D:\Anaconda\envs\ContentShare\python.exe -m compileall app nodes routers platforms memory scripts llm
node --check app\static\app.js
```

预期：全量通过。

- [ ] 提交：

```powershell
git add docs/superpowers/specs/2026-06-11-platform-safety-guardrails-design.md docs/superpowers/plans/2026-06-11-platform-safety-guardrails.md platforms/platform_guardrails.py platforms/creator.py platforms/spider_xhs_collector.py platforms/collector.py .env.example tests/test_platform_safety_guardrails.py memory/current_progress.md
git commit -m "feat: add platform safety guardrails"
```

