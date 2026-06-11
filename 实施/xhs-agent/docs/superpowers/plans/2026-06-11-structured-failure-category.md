# 结构化失败分类实施计划

> 给执行者：本计划按测试先行执行。所有规划和说明使用中文。

**目标：** 将工作台失败诊断从前端文本判断升级为后端结构化 `failure_category`，让 API、运行记录和前端诊断共用同一套失败分类。

**架构：** 保持现有标准库 HTTP API 和静态前端。后端新增失败分类函数，根据 run 顶层 `error`、状态摘要中的 `creator_publish_error`、合规风险等字段生成 `failure_category` 和 `failure_category_label`；前端优先展示后端 label，旧文本判断只作为兼容旧记录的兜底。

**技术栈：** Python 标准库 HTTP API、现有 run store、静态 JavaScript、pytest。

---

## 字段约定

顶层 run 字段：
- `failure_category`
- `failure_category_label`

summary 字段：
- `failure_category`
- `failure_category_label`

分类值：
- `creator_publish`：创作者平台或发布素材问题。
- `llm_generation`：LLM 生成或解析问题。
- `collection`：采集或 Cookie 问题。
- `compliance`：合规拦截。
- `unknown`：未分类失败，请查看错误详情。
- `null`：没有失败。

## 文件范围

- 修改：`app/api.py`
  - 新增失败分类函数。
  - `_run_record()` 写入顶层失败分类。
  - `_state_summary()` 写入 summary 失败分类。
  - `/runs` 列表和 `/runs/{run_id}` 对旧记录也补派生分类。
- 修改：`app/static/app.js`
  - `diagnoseRunFailure()` 优先读取后端结构化 label。
  - 旧文本关键词判断保留为兜底。
- 新增：`tests/test_run_failure_category.py`
  - 覆盖后端分类和旧记录响应补齐。
- 修改：`tests/test_workbench_run_diagnostics_static.py`
  - 覆盖前端使用后端字段。
- 修改：`memory/current_progress.md`
  - 记录 M24 完成内容、限制和自测步骤。

## 任务一：后端失败测试

- [ ] 新增 `tests/test_run_failure_category.py`。
- [ ] 覆盖 `_failure_category_from_text()` 或等价函数：
  - `creator adapter unavailable` -> `creator_publish`
  - `image bytes missing` -> `creator_publish`
  - `LLM JSON parse failed` -> `llm_generation`
  - `cookie expired while collecting comments` -> `collection`
  - `compliance risk high` -> `compliance`
  - `unexpected crash` -> `unknown`
- [ ] 覆盖 `_run_record()` 顶层失败记录写入 `failure_category` 和 `failure_category_label`。
- [ ] 覆盖 `_state_summary()` 在 creator publish failed 时写入 summary 失败分类。
- [ ] 覆盖旧 run 记录经响应装饰后能补齐分类字段。
- [ ] 运行：

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_run_failure_category.py -q
```

预期：先失败。

## 任务二：前端契约测试

- [ ] 修改 `tests/test_workbench_run_diagnostics_static.py`。
- [ ] 断言 `diagnoseRunFailure()` 使用 `failure_category_label`。
- [ ] 断言 `renderRunDiagnostics()` 或错误展示读取后端分类。
- [ ] 运行：

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_workbench_run_diagnostics_static.py -q
```

预期：先失败。

## 任务三：后端实现

- [ ] 在 `app/api.py` 新增分类映射和分类函数。
- [ ] `_state_summary()` 对 creator publish failed、合规高风险等状态写入 summary 分类。
- [ ] `_run_record()` 对顶层 failed run 写入顶层分类。
- [ ] 新增响应装饰函数，对历史 run 补齐顶层和 summary 分类，不强制迁移旧 JSON。
- [ ] `/runs` 和 `/runs/{run_id}` 使用装饰后的 run。

## 任务四：前端实现

- [ ] `diagnoseRunFailure()` 优先返回：
  - `run.failure_category_label`
  - `run.summary.failure_category_label`
- [ ] 如果后端字段不存在，再按旧关键词兜底。

## 任务五：项目记忆

- [ ] 在 `memory/current_progress.md` 顶部新增 M24 记录。
- [ ] 写清楚：本轮只做结构化分类，不做完整日志追踪或队列级重试。

## 任务六：验证

- [ ] 运行 M24 聚焦测试：

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_run_failure_category.py tests/test_workbench_run_diagnostics_static.py -q
```

- [ ] 运行 creator 主链路回归：

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_creator_platform.py tests/test_api_creator_review_publish.py tests/test_creator_asset_binding.py tests/test_creator_note_performance_sync.py -q
```

- [ ] 运行工作台静态回归：

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_workbench_run_diagnostics_static.py tests/test_workbench_memory_visibility_static.py tests/test_workbench_creator_notes_static.py tests/test_workbench_creator_assets_static.py tests/test_workbench_creator_publish_static.py -q
```

- [ ] 运行全量测试：

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m pytest -q
```

- [ ] 运行编译检查：

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m compileall app nodes routers platforms memory scripts llm
```

- [ ] 运行工作台浏览器 smoke。

## 用户自测步骤

1. 启动本地 API 并打开工作台。
2. 点击一条失败或 creator publish failed 的运行记录。
3. 查看“运行诊断”中的失败分类。
4. 确认分类来自后端字段，而不是只靠前端猜测。
5. 旧记录仍应能正常显示兜底诊断。
