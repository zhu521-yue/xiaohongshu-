# 工作台运行历史详情与失败诊断实施计划

> 给执行者：本计划按测试先行执行，每个任务完成后都要跑对应测试。所有规划和说明使用中文。

**目标：** 在工作台中让用户选中运行记录后，直接看到任务参数、运行时间、错误信息和失败诊断，并能用原任务参数重新提交一个新任务。

**架构：** 不引入新框架，不新增真实平台写入行为。后端现有 `/runs/{run_id}` 已返回完整 run 记录，本轮主要改静态前端：在任务结果区新增运行诊断面板，读取已有 `run.request`、`run.status`、`run.error`、`run.created_at`、`run.updated_at`、`run.summary` 字段展示；重新提交按钮复用现有 `POST /runs`。

**技术栈：** Python 标准库 HTTP API、现有静态 HTML/CSS/JavaScript、pytest 静态契约测试、现有浏览器 smoke 脚本。

---

## 文件范围

- 修改：`app/static/index.html`
  - 在任务结果摘要下方增加运行诊断容器。
- 修改：`app/static/app.js`
  - 增加运行诊断渲染函数。
  - 增加失败原因分类函数。
  - 增加“用此任务参数重新提交”按钮行为。
- 修改：`app/static/styles.css`
  - 增加运行诊断面板、参数网格、失败提示和重新提交按钮样式。
- 新增：`tests/test_workbench_run_diagnostics_static.py`
  - 覆盖前端静态契约。
- 修改：`memory/current_progress.md`
  - 记录 M23 完成内容、限制和自测步骤。

## 任务一：前端契约测试

- [ ] 新增 `tests/test_workbench_run_diagnostics_static.py`。
- [ ] 断言 `index.html` 有 `runDiagnostics` 容器。
- [ ] 断言 `app.js` 有 `renderRunDiagnostics()`。
- [ ] 断言 `app.js` 有 `diagnoseRunFailure()`。
- [ ] 断言 `app.js` 有 `resubmitRunFromCurrent()`。
- [ ] 断言重新提交 payload 使用 `state.currentRun.request`。
- [ ] 断言失败状态会展示错误字段。
- [ ] 运行：

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_workbench_run_diagnostics_static.py -q
```

预期：先失败，因为功能尚未实现。

## 任务二：前端实现

- [ ] 在 `index.html` 的任务结果区域加入：

```html
<div class="run-diagnostics" id="runDiagnostics"></div>
```

- [ ] 在 `app.js` 中增加失败分类：
  - 包含 `creator`、`publish`、`image bytes` 时，提示创作者平台或发布素材问题。
  - 包含 `llm`、`json`、`model` 时，提示 LLM 生成或解析问题。
  - 包含 `collect`、`comment`、`cookie`、`spider` 时，提示采集或 Cookie 问题。
  - 包含 `compliance`、`risk` 时，提示合规拦截。
  - 其他失败统一显示“未分类失败，请查看错误详情”。

- [ ] 在 `renderRun()` 中调用 `renderRunDiagnostics(run)`。
- [ ] 重新提交时复用原任务参数：

```javascript
const request = state.currentRun?.request || {};
const payload = {
  topic: request.topic,
  target_user: request.target_user,
  format: request.format,
  engine: request.engine,
  collect_limit: Number(request.collect_limit || 5),
  approve: Boolean(request.approve),
};
```

- [ ] 调用 `apiPost("/runs", payload)` 后切换到新 run 并开始轮询。

## 任务三：样式

- [ ] 新增 `.run-diagnostics`、`.diagnostics-grid`、`.diagnostic-alert`、`.diagnostic-actions` 样式。
- [ ] 移动端保持单列，避免按钮和文本挤压。

## 任务四：项目记忆

- [ ] 在 `memory/current_progress.md` 顶部新增 M23 记录。
- [ ] 写清楚：本轮只做诊断展示和复制参数重新提交，不做队列级自动重试。

## 任务五：验证

- [ ] 运行 M23 聚焦测试：

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_workbench_run_diagnostics_static.py -q
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

- [ ] 运行浏览器 smoke：

```powershell
使用现有 `scripts/check_workbench_ui.py` 检查工作台移动端页面。
```

## 用户自测步骤

1. 启动本地 API 并打开工作台。
2. 点击任意一条“运行记录”。
3. 在任务结果区查看“运行诊断”。
4. 如果该任务失败，确认能看到失败诊断和错误详情。
5. 点击“用此任务参数重新提交”。
6. 确认系统创建一个新任务，并开始轮询新任务状态。
