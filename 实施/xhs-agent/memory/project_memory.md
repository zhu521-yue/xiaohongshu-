# 项目记忆

## 2026-06-10 更新：Playwright 工作台自动巡检

本轮目标是在前端工作台雏形完成后，加入浏览器级自动检查，避免每次只靠人工打开页面判断。

新增文件：
- `scripts/check_workbench_ui.py`

脚本能力：
- 检查 API 服务是否在线：`GET /health`。
- 用 Playwright 打开工作台首页。
- 验证页面标题、主标题、服务状态、队列状态。
- 验证核心区域存在：
  - 新建任务
  - 任务结果
  - 队列
  - 运行记录
  - 表现录入
  - 运营记忆
- 验证核心表单控件存在：
  - topic
  - target_user
  - format
  - engine
  - collect_limit
  - submitButton
  - refreshButton
- 验证草稿、痛点、JSON 三个 tab 可以切换。
- 支持桌面和移动端视口：
  ```powershell
  python .\scripts\check_workbench_ui.py --viewport desktop
  python .\scripts\check_workbench_ui.py --viewport mobile
  ```
- 默认不提交生成任务，不消耗 LLM 或真实采集。
- 支持真实点击提交：
  ```powershell
  python .\scripts\check_workbench_ui.py --submit --wait-run
  ```

已验证：
- Playwright Python 包可导入。
- 当前 8010 服务在线，`GET /health` 正常。
- 桌面巡检通过，无 console error。
- 移动端巡检通过，无 console error。
- 使用临时 8011 mock 服务执行提交链路检查通过：
  - 前端点击提交
  - 任务进入 queued
  - 单 worker 执行
  - 最终 success
  - 草稿内容渲染到任务结果区域

截图输出目录：
```text
data/ui_checks/
```

本轮截图：
```text
data/ui_checks/workbench_desktop_20260610_110741.png
data/ui_checks/workbench_mobile_20260610_110742.png
data/ui_checks/workbench_desktop_20260610_111850.png
```

当前阶段判断：
- M8 前端工作台雏形：完成
- M8 浏览器自动巡检：完成基础版
- 现在前端已经不是“能打开即可”，而是有了可重复执行的桌面/移动端/提交链路验证方式。

下一步：
1. 继续人工体验工作台，重点看字段命名和结果展示是否好理解。
2. 补更细的前端交互能力：
   - 点击运行记录后自动展示详情
   - 表现录入成功后的提示和记忆刷新
   - failed 任务的错误展示
3. 再进入部署准备：
   - `.env` 生产配置整理
   - 启动脚本
   - 日志落盘
   - Windows/服务器进程守护方案

## 2026-06-10 更新：前端工作台雏形

本轮目标是在现有标准库 HTTP API 上直接托管一个前端工作台雏形，先打通“浏览器可操作”的基础体验。

设计选择：
- 不额外引入 Vite、React、FastAPI 或 Node 前端依赖。
- 前端静态资源由当前 `scripts/run_api.py` 启动的 API 服务直接托管。
- 打开 `http://127.0.0.1:8010/` 即可进入工作台。

新增文件：
- `app/static/index.html`
- `app/static/styles.css`
- `app/static/app.js`

后端更新：
- `app/api.py` 新增静态资源托管：
  - `GET /` -> `app/static/index.html`
  - `GET /static/styles.css`
  - `GET /static/app.js`
- 保留原 API：
  - `GET /health`
  - `POST /runs`
  - `GET /runs`
  - `GET /runs/{run_id}`
  - `GET /queue`
  - `GET /memory/records`
  - `POST /performance`

工作台已实现能力：
- 新建任务：
  - 主题
  - 目标用户
  - 图文/视频
  - local/langgraph
  - 采集数量
  - 是否保存 Markdown 并写入运营记忆
- 自动提交到 `POST /runs`。
- 自动轮询 `GET /runs/{run_id}`。
- 显示队列状态：
  - `queued_count`
  - `running_count`
  - queued/running run ids
- 展示运行记录列表。
- 点击运行记录可查看详情。
- 展示任务摘要：
  - 内容形式
  - 内容类型
  - 合规等级
  - 采集笔记/评论数量
  - 痛点数量
  - successful_patterns 数量
  - LLM 是否启用
- 展示图文草稿：
  - 标题
  - 封面文案
  - 正文
  - 图片页规划
  - 图片提示词
  - 标签/评论引导
- 展示视频脚本：
  - 标题
  - hook
  - 开场口播
  - 口播要点
  - 分镜规划
  - 字幕/封面
  - 合规提醒
- 展示痛点和评论证据。
- 展示原始 JSON。
- 支持录入表现数据，调用 `POST /performance`。
- 展示最近运营记忆。

已验证：
```powershell
python -m py_compile .\app\api.py
node --check .\app\static\app.js
python -m compileall app nodes routers platforms memory scripts llm
```

HTTP 静态资源验证通过：
```text
GET / -> 200
GET /static/styles.css -> 200
GET /static/app.js -> 200
GET /queue -> ok=true
```

启动命令：
```powershell
python .\scripts\run_api.py --host 127.0.0.1 --port 8010
```

浏览器打开：
```text
http://127.0.0.1:8010/
```

当前阶段判断：
- M8 前端工作台雏形：完成基础版。
- 现在已经可以不用命令行提交任务，而是在浏览器里提交和查看结果。

下一步：
1. 用户在本地浏览器打开工作台做人工体验验证。
2. 根据体验修正：
   - 字段展示是否够清晰
   - 长文本是否易读
   - 失败状态是否好理解
   - 表现录入是否顺手
3. 再进入部署准备：
   - 环境变量整理
   - 启动脚本
   - 服务进程守护
   - 日志文件
   - 服务器目录结构

## 2026-06-10 更新：M7 单 worker 队列

本轮目标是把 M7 的“每个任务一个后台线程”改为“单 worker 队列”，避免多个小红书采集/LLM 任务同时执行。

已完成：
- `app/api.py` 新增全局队列：`RUN_QUEUE`、`QUEUE_LOCK`、`ENQUEUED_RUN_IDS`、`WORKER_STARTED`。
- `submit_run()` 现在只负责保存 `queued` run、入队、立即返回。
- 新增 `_worker_loop()`，后台只有一个 worker 线程顺序执行任务。
- 新增 `_enqueue_run()`，避免同一个 `run_id` 重复入队。
- 新增 `_recover_pending_runs()`，服务启动时会把历史中 `queued/running` 的任务重新放回队列。
- `_execute_run()` 增加保护：如果任务已经是 `success/failed`，不会重复执行。
- 新增 `GET /queue`，用于查看当前队列状态：`queued_count`、`running_count`、`queued_run_ids`、`running_run_ids`。

当前运行模型：
```text
POST /runs
-> 保存 queued
-> 放入 RUN_QUEUE
-> 立即返回 run_id

单 worker
-> 取最早进入队列的任务
-> 标记 running
-> 执行业务链路
-> 标记 success / failed
-> 再取下一个任务
```

验证通过：
```powershell
python -m py_compile .\app\api.py
python -m compileall app nodes routers platforms memory scripts llm
```

函数级队列验证：
```text
连续提交 2 个 mock 任务：
第一个状态：running
第二个状态：queued
queue_status: queued=1, running=1
最终两者 success
```

HTTP 队列验证：
```text
POST /runs -> run_1 queued
POST /runs -> run_2 queued
GET /queue -> queued_count=1, running_count=1
GET /runs/{run_1} -> running -> success
GET /runs/{run_2} -> queued -> success
```

当前阶段判断：
- M7 异步任务：完成
- M7 单 worker 队列：完成
- 当前仍是“单进程 + 单 worker + JSON 落盘”的原型队列，适合本地/单机服务器原型，但还不是生产级队列。

生产化时后续可升级：
- 数据库任务表
- Redis/RQ
- Celery
- FastAPI background tasks
- 服务重启后的任务恢复策略优化

下一步：
1. 更新测试方式，加入 `GET /queue`。
2. 开始前端工作台雏形：提交任务、展示队列状态、轮询任务详情、展示草稿/痛点/运营记忆、录入表现数据。

## 2026-06-10 更新：M7 异步任务队列雏形

本轮目标是把同步版 `POST /runs` 改造成异步任务接口，为后续前端工作台做准备。

已完成：
- `app/api.py` 新增异步运行机制。
- `POST /runs` 现在立即返回，不再等待采集和 LLM 全部完成。
- 运行状态流转为：
  ```text
  queued -> running -> success / failed
  ```
- 后台使用 daemon thread 执行现有 `run_langgraph` / `run_local_graph`，业务节点没有重写。
- 每个 run 继续落盘到：
  ```text
  data/api_runs/{run_id}.json
  ```
- run 记录新增字段：
  - `updated_at`
  - `started_at`
  - `finished_at`
- `GET /runs/{run_id}` 可轮询任务状态和最终结果。
- `create_run()` 保留为同步函数，方便内部烟测。
- `submit_run()` 作为异步提交入口，供 HTTP `POST /runs` 使用。
- 文件读写增加 `RUN_LOCK`，降低同进程并发读写 run JSON 的风险。

接口行为变化：
- 之前：
  ```text
  POST /runs -> 等待完整生成 -> 200 + success 结果
  ```
- 现在：
  ```text
  POST /runs -> 202 + queued run_id
  GET /runs/{run_id} -> 轮询 running/success/failed
  ```

已验证：
```powershell
python -m py_compile .\app\api.py
python -m compileall app nodes routers platforms memory scripts llm
```

函数级异步验证通过：
```powershell
$env:COLLECTOR_MODE='mock'
$env:LLM_MODEL_NAME='mock'
python -c "import time; from app.api import submit_run, _load_run; r=submit_run({'topic':'小红书新手选题方法','target_user':'内容创作新手','format':'image_text','engine':'langgraph','approve':False,'collect_limit':3}); print('initial', r['status'], r['run_id']); final=None
for _ in range(30):
    final=_load_run(r['run_id']); print('poll', final['status'])
    if final['status'] in {'success','failed'}: break
    time.sleep(0.2)
print('final', final['status'], final.get('summary', {}).get('content_format'), final.get('summary', {}).get('operation_memory_written'))"
```

HTTP 异步验证通过：
```text
POST /runs -> 202
initial status -> queued
GET /runs/{run_id} -> running
GET /runs/{run_id} -> success
```

验证结果：
```json
{
  "final_status": "success",
  "content_format": "image_text",
  "memory_written": false
}
```

当前阶段判断：
- M7 异步任务队列雏形已完成。
- 当前任务队列是“进程内线程 + JSON 落盘”版本，适合单机原型。
- 服务器生产化时仍需替换为更稳的任务系统，例如数据库任务表、Redis/RQ、Celery 或 FastAPI background tasks。

下一步：
1. 更新用户测试命令：`POST /runs` 后保存 `run_id`，再轮询 `GET /runs/{run_id}`。
2. 开始前端工作台雏形：
   - 输入主题/目标用户/格式/是否保存
   - 提交任务
   - 显示 queued/running/success/failed
   - 展示草稿、痛点、路径、运营记忆
   - 录入表现数据

## 2026-06-09 更新：最小 HTTP API 雏形

本轮目标是把命令行主流程包装成 HTTP API，为后续前端工作台做接口边界。

设计选择：
- 暂时不引入 FastAPI，先用 Python 标准库 `http.server` 做最小 API。
- 这样可以先稳定接口协议，避免在业务链路还在调整时增加额外依赖。
- 后续前端工作台确定后，可以平滑迁移到 FastAPI。

新增文件：
- `app/api.py`
- `scripts/run_api.py`

已实现接口：
- `GET /health`
  - 健康检查。
- `POST /runs`
  - 触发一次内容生成。
  - 请求字段支持：
    - `topic`
    - `target_user`
    - `format`: `image_text` / `video`
    - `engine`: `local` / `langgraph`
    - `approve`
    - `collect_limit`
    - `save_collection`
  - 返回字段包含：
    - `run_id`
    - `summary`
    - `content`
    - `insights`
    - `paths`
- `GET /runs?limit=20`
  - 查看最近 API 运行记录。
- `GET /runs/{run_id}`
  - 查看单次运行详情。
- `GET /memory/records?limit=20`
  - 查看最近运营记忆记录。
- `POST /performance`
  - 录入发布表现数据。
  - 复用 `memory.operation_store.update_record_performance()`。

数据落盘：
- API 运行记录保存到：
  ```text
  data/api_runs/
  ```
- 该目录已被现有 `.gitignore` 的 `data/` 规则覆盖，不会提交运行数据。

已验证：
```powershell
python -m py_compile .\app\api.py .\scripts\run_api.py
python -m compileall app nodes routers platforms memory scripts llm
```

函数级验证：
```powershell
$env:COLLECTOR_MODE='mock'
$env:LLM_MODEL_NAME='mock'
python -c "from app.api import create_run; r=create_run({'topic':'小红书新手选题方法','target_user':'内容创作新手','format':'image_text','engine':'langgraph','approve':False,'collect_limit':3}); print(r['status']); print(r['summary']['content_format']); print(r['summary']['operation_memory_written']); print(r['run_id'])"
```

HTTP 烟测通过：
```powershell
GET /health
GET /runs?limit=2
GET /memory/records?limit=1
POST /performance
```

启动命令：
```powershell
python .\scripts\run_api.py --host 127.0.0.1 --port 8010
```

本地访问：
```text
http://127.0.0.1:8010/health
```

注意：
- 当前 API 是同步执行。`POST /runs` 会等待采集、LLM、合规、保存全部完成后才返回。
- 下一步可以做异步任务队列雏形：提交任务立即返回 `run_id`，后台执行，前端轮询 `GET /runs/{run_id}`。
- 当前工具环境中的后台进程不会稳定跨命令保活；用户在本地终端手动运行启动命令即可。

## 2026-06-09 更新：视频脚本真实保存质检

本轮目标是对视频格式做一次真实 LLM 生成、保存和人工质量检查，确认 `video_node.py` 的 JSON Output 链路是否可用。

已执行：
```powershell
python -m app.main --topic "小红书新手选题方法" --target-user "内容创作新手" --format video --approve --engine langgraph
```

生成结果：
- `post_id: output\markdown_exports\20260609_233055_小红书新手选题方法.md`
- `llm_generation.enabled: True`
- `llm_generation.provider_mode: openai_compatible`
- `content_format: video`
- `content_type: step_tutorial`
- `compliance_risk_level: low`
- `operation_memory_written: True`
- `operation_record_id: op_de80a3791edc`

人工质检结论：
- 视频脚本没有出现健康领域错位词：`宝宝`、`湿疹`、`护理`、`诊断`、`治疗`、`症状` 等。
- 没有出现合规绝对词：`一定`、`保证`、`彻底`、`根治`、`100%`、`最有效`。
- 没有出现过度承诺词：`爆款`、`必火`、`暴涨`、`快速涨粉`。
- 脚本结构可用：标题、hook、时长、开场口播、口播要点、分镜、字幕、封面、合规提醒齐全。

发现并修复：
- `nodes/publish_node.py` 的视频 Markdown 渲染会把 `shot_plan` 字典直接打印成 Python dict，例如 `{'scene': 1, ...}`，不适合人工查看。
- 已新增 `VIDEO_SCRIPT_LABELS`，把视频脚本字段渲染为中文小标题。
- `shot_plan` 现在渲染为正式分镜格式：
  ```text
  - 镜头1：画面说明｜屏幕文字：xxx
  ```
- 已同步修正本次生成的 Markdown 样本文件。

已验证：
```powershell
python -m py_compile .\nodes\publish_node.py
python -m compileall app nodes routers platforms memory scripts llm
```

当前阶段判断：
- 图文 LLM 生成：可用
- 视频 LLM 生成：可用
- 复盘 LLM：已接入，需在录入表现数据后触发
- 历史成功模式影响生成结构：可用
- Markdown 保存渲染：图文可用，视频已修正为可读格式

下一步建议：
1. 开始整理当前命令行能力，进入接口层雏形。
2. 优先做一个最小 API：`POST /runs` 触发生成，`GET /runs/{id}` 查看结果。
3. 再考虑前端工作台，用于输入主题、查看采集结果、查看草稿、录入表现数据。

## 2026-06-09 更新：图文内容质量质检与后处理

本轮目标是生成一篇真实 LLM 图文草稿并做人工质量检查，确认 `successful_patterns` + LLM 生成链路是否会继续出现领域错位或过度承诺表达。

已执行：
```powershell
python -m app.main --topic "小红书新手选题方法" --target-user "内容创作新手" --format image_text --approve --engine langgraph
```

生成结果：
- `post_id: output\markdown_exports\20260609_232335_小红书新手选题3步法！别再凭感觉乱发了.md`
- `llm_generation.enabled: True`
- `llm_generation.provider_mode: openai_compatible`
- `operation_memory_written: True`
- `operation_record_id: op_8a9168598191`

人工质检结论：
- 没有再出现“宝宝、湿疹、护理、诊断、治疗、症状、医生、专业人士”等健康领域错位词。
- 没有出现合规绝对词：`一定`、`保证`、`彻底`、`根治`、`100%`、`最有效`。
- 草稿整体可用，结构是“记录 -> 判断 -> 拆解”，符合 `step_tutorial`。
- 发现两个表达质量问题：
  - “爆款方向 / 专属爆款方向”偏过度承诺。
  - 图片页标题“终执行”不自然。

已修复：
- `nodes/content_node.py` 新增质量后处理替换：
  - `爆款方向 -> 可验证方向`
  - `爆款选题 -> 高反馈选题`
  - `你的专属爆款方向 -> 更适合你的内容方向`
  - `必火 -> 更容易被看见的`
  - `终执行 -> 最后执行`
  - `终复盘 -> 最后复盘`
- `nodes/content_node.py` prompt 新增约束：不要承诺爆款、必火、暴涨、快速涨粉。
- `nodes/video_node.py` 同步同一套质量后处理和 prompt 约束，保持图文/视频生成标准一致。
- 已同步修正本次生成的 Markdown 样本文件。

已验证：
```powershell
python -m py_compile .\nodes\content_node.py .\nodes\video_node.py
python -m compileall app nodes routers platforms memory scripts llm
```

后处理验证通过：
```text
从0到1找到爆款方向 -> 从0到1找到可验证方向
终执行：拆成选题发布 -> 最后执行：拆成选题发布
慢慢找到你的专属爆款方向 -> 慢慢找到更适合你的内容方向
```

当前阶段判断：
- LLM 图文生成主链路可用。
- successful_patterns 影响结构的逻辑可用。
- 领域错位问题已修正。
- 过度承诺表达已增加后处理兜底。

下一步：
1. 可以对视频格式做同样的真实保存质检。
2. 或进入前端/接口层雏形，把当前命令行能力包装成可视化工作台。

## 2026-06-09 更新：复盘节点接入 LLM JSON Output

本轮目标是把 `review_node.py` 从固定占位复盘升级为“有真实表现数据时优先 LLM 复盘，失败自动模板兜底”。

已完成：
- `nodes/review_node.py` 重写为统一复盘模块。
- 主流程刚生成草稿、还没有真实表现数据时，仍然走模板提示，不额外消耗 LLM token。
- 有 `views`、`likes`、`collects`、`comments`、`follows` 等表现数据时，会优先调用真实 LLM JSON Output 生成：
  - `review_summary`
  - `next_action`
  - `reuse_decision`
  - `key_learning`
- LLM 复盘失败、mock 模式、JSON 不合法、没有表现数据时，自动 fallback 到原来的规则复盘。
- `memory/operation_store.py` 已接入新的复盘生成器。现在 `scripts/record_performance.py` 录入表现数据时，也会复用同一套 LLM/模板复盘逻辑。
- `app/state.py` 新增 `review_generation`。
- `app/main.py` 新增 `review_generation` 输出，便于观察复盘是 LLM 还是模板。
- `app/config.py` 新增 `LLM_REVIEW_MAX_TOKENS`，默认 `1200`。
- `.env.example` 新增 `LLM_REVIEW_MAX_TOKENS=1200`。

已验证：
```powershell
python -m py_compile .\app\config.py .\app\state.py .\app\main.py .\nodes\review_node.py .\memory\operation_store.py .\scripts\record_performance.py
python -m compileall app nodes routers platforms memory scripts llm
```

mock 复盘验证通过：
```powershell
$env:LLM_MODEL_NAME='mock'
python -c "from nodes.review_node import build_operation_review; r=build_operation_review({'topic':'小红书新手选题方法','title':'测试标题','content_type':'step_tutorial','content_format':'image_text','performance_data':{'views':1000,'likes':50,'collects':20,'comments':8,'follows':3},'pain_points':[{'pain':'不知道怎么选题','evidence':'不会选题'}]}); print(r['review_summary']); print(r['review_generation']['enabled'], r['review_generation']['provider_mode'])"
```

主流程 mock 验证通过：
```powershell
$env:COLLECTOR_MODE='mock'
$env:LLM_MODEL_NAME='mock'
python -m app.main --topic "小红书新手选题方法" --target-user "内容创作新手" --format image_text --engine langgraph
```

验证结果：
- `review_generation.enabled: False`
- `review_generation.provider_mode: template`
- 未发布/未录入真实表现时，不触发 LLM 复盘。

下一步：
1. 用真实 `.env` 找一条已经写入 `operation_history.json` 的 `post_id`。
2. 执行表现录入，验证 `review_generation.enabled` 是否为 `True`：
   ```powershell
   python .\scripts\record_performance.py --post-id "output\markdown_exports\xxx.md" --views 1000 --likes 50 --collects 20 --comments 8 --follows 3
   ```
3. 如果 LLM 复盘稳定，再进入下一阶段：前端/接口层雏形，或者继续优化内容质量评估。

## 2026-06-09 更新：视频节点接入 LLM JSON Output

本轮目标是在图文 LLM 已跑通后，继续统一视频生成节点，并修正上次真实图文草稿暴露出的“历史结构携带健康场景措辞”问题。

已完成：
- `nodes/pattern_utils.py` 已把结构模板改成通用表达。`successful_patterns` 现在只影响“步骤教程/避坑/问答/经验总结”等结构，不再默认携带“位置、症状、护理、诊断、专业人士”等健康类措辞。
- `nodes/content_node.py` 调整安全提示触发逻辑。安全提示优先根据原始主题、目标用户、评论痛点判断，避免非健康主题因为历史结构或模型正文误触发健康安全说明。
- `nodes/content_node.py` 的 prompt 明确说明：`preferred_structure` 只代表内容结构，不代表具体领域措辞，不能把健康护理表达套用到非健康主题。
- `nodes/video_node.py` 已接入和图文节点同样的模式：优先调用真实 LLM JSON Output，失败时自动 fallback 到模板。
- `nodes/video_node.py` 新增 JSON 字段校验、绝对词清理、敏感主题安全提示、`llm_generation` 观测字段。
- `app/config.py` 新增 `LLM_VIDEO_MAX_TOKENS` 配置，默认 `4000`。
- `.env.example` 新增 `LLM_VIDEO_MAX_TOKENS=4000`。

已验证：
```powershell
python -m py_compile .\app\config.py .\nodes\content_node.py .\nodes\pattern_utils.py .\nodes\video_node.py
python -m compileall app nodes routers platforms memory scripts llm
```

mock 流程验证通过：
```powershell
$env:COLLECTOR_MODE='mock'
$env:LLM_MODEL_NAME='mock'
python -m app.main --topic "小红书新手选题方法" --target-user "内容创作新手" --format video --engine langgraph
```

验证结果：
- `content_format: video`
- `compliance_risk_level: low`
- `llm_generation.enabled: False`
- `llm_generation.provider_mode: fallback_template`
- `operation_memory_written: False`

下一步：
1. 用户用真实 `.env` 跑一次视频格式，不加 `--approve`，先只检查 LLM 是否真实接入：
   ```powershell
   python -m app.main --topic "小红书新手选题方法" --target-user "内容创作新手" --format video --engine langgraph
   ```
2. 观察输出里的 `llm_generation.enabled` 是否为 `True`。
3. 如果视频 LLM 结果正常，再检查生成脚本质量；之后再决定是否加 `--approve` 保存 Markdown。
4. 视频节点稳定后，下一阶段接入 `review_node.py` 的 LLM 复盘逻辑。

## 2026-06-07 更新：M2 采集质量优化

本轮目标从“接口能跑通”推进到“采集结果更可用”。

已完成：
- `platforms/spider_xhs_collector.py` 新增低价值笔记过滤：无标题且 0 评论的笔记会被过滤，高互动笔记保留。
- `platforms/spider_xhs_collector.py` 新增噪声评论过滤：邀请码、长按复制、加入群聊等广告/引流评论会被过滤。
- `platforms/comment_analysis.py` 重写评论痛点规则，更贴近真实评论里的“湿疹/热疹分不清、帮忙判断、要不要擦药、症状变多、方法是否靠谱、需要步骤”等表达。
- `platforms/comment_analysis.py` 新增证据评分：优先选择提问、求助、症状描述类评论，降低“终于找到了、护理方法来啦、推荐、种草”等解决方案/推广语气评论的证据优先级。
- `platforms/comment_analysis.py` 收紧“步骤/产品选择”规则，移除过宽的 `药` 关键词，避免“擦药吗”同时误触发“用药处理”和“护理步骤”两个痛点。
- `.env.example` 新增 `XHS_MIN_NOTE_COMMENTS`、`XHS_MIN_NOTE_INTERACTION` 两个采集质量阈值。
- `scripts/check_collector.py` 已同步正式采集过滤逻辑，避免诊断脚本只打印原始数据造成误判。
- `scripts/check_collector.py` 新增 `comment_insights` / `pain_points` 输出，便于直接观察“评论 -> 痛点”的归纳质量。

已验证：
- `python -m py_compile .\platforms\spider_xhs_collector.py .\platforms\comment_analysis.py`
- `python -m py_compile .\scripts\check_collector.py`
- `python -m compileall app nodes routers platforms scripts`
- mock 模式 LangGraph 主流程可走到 Markdown 草稿生成。

下一步：
- 用真实命令复测采集结果：`python .\scripts\check_collector.py --search --comments --debug-response --topic "宝宝湿疹护理" --limit 3`
- 如果真实输出稳定，再进入 M3：复盘闭环 + JSON 运营记忆。

## 2026-06-07 更新：M3 JSON 运营记忆雏形

本轮目标是让系统开始拥有可持久化的运营记忆，而不是每次都从零生成。

已完成：
- 新增 `memory/operation_store.py`：负责读写 `memory/operation_history.json`，统一管理运营记录、表现分、复盘摘要、同主题历史检索。
- 更新 `nodes/memory_node.py`：`retrieve_graphrag_memory` 会按主题读取历史记录和高表现模式；`write_operation_memory` 会在草稿保存成功后写入运营记忆。
- 更新 `app/state.py`：新增 `operation_record_id`、`operation_memory_path`、`operation_memory_written`。
- 更新 `app/main.py`：命令行输出会显示记忆检索数量、是否写入记忆、记忆文件路径。
- 新增 `scripts/record_performance.py`：支持人工录入曝光、点赞、收藏、评论、关注，并更新同一条运营记录的复盘摘要。
- 更新 `nodes/strategy_node.py`：当同类主题存在已录入表现数据的高分记录时，策略节点可以轻量复用历史高表现内容类型。

已验证：
- mock 模式 LangGraph 主流程可以写入运营记忆。
- `scripts/record_performance.py` 可以按 `post_id` 更新表现数据、计算表现分、生成复盘摘要。
- 第二次同主题运行时可以检索到历史记录和 `successful_patterns`。
- 验证用的临时 `operation_history.json` 已清理，避免假数据污染正式运营记忆。

常用命令：
```powershell
python .\scripts\record_performance.py --list --limit 10
```

```powershell
python .\scripts\record_performance.py --post-id "output\markdown_exports\xxx.md" --views 1000 --likes 50 --collects 20 --comments 8 --follows 3
```

下一步：
- 将 `successful_patterns` 更明显地用于内容生成结构，而不暴露内部复盘语句到发布正文。
- 之后再接入正式 LLM，提高内容生成和复盘质量。

## 2026-06-07 更新：successful_patterns 接入内容生成

本轮目标是让历史高表现记录不只是被读取，而是实际影响生成结构。

已完成：
- 新增 `nodes/pattern_utils.py`：把 `successful_patterns` 转成结构配置，支持 `knowledge_share`、`avoid_mistakes`、`step_tutorial`、`qa_education`、`experience_summary`。
- 更新 `nodes/content_node.py`：图文标题、封面文案、正文动作段、图片页规划会参考历史高表现内容类型。
- 更新 `nodes/video_node.py`：视频标题、hook、talking points、分镜结构会参考历史高表现内容类型。

设计边界：
- 不把历史记录原文塞进正文。
- 不在正文里暴露“根据历史高表现记录”这类内部逻辑。
- 当前真实评论痛点仍然优先作为内容证据，历史模式只影响结构。

已验证：
- 当 `successful_patterns` 包含 `step_tutorial` 高分记录时，图文生成会切成步骤清单结构。
- 当 `successful_patterns` 包含 `qa_education` 高分记录时，视频生成会切成问答结构。
- `python -m compileall app nodes routers platforms memory scripts` 通过。

## 2026-06-08 更新：medium 合规分支优化

本轮目标是修复 `medium` 合规风险直接截停的问题，让母婴/健康类中风险内容可以先补充安全提示，再进入人工审核。

已完成：
- `nodes/compliance_node.py` 新增 `revise_content_for_compliance`。
- `app/graph.py` 调整 LangGraph 路由：`medium -> revise_content_for_compliance -> human_review`；`high` 仍然停止。
- 本地执行器同步处理中风险内容，保持 local/langgraph 行为一致。
- `app/main.py` 输出 `compliance_issues` 和 `revised_content`，便于观察合规处理结果。
- `memory/operation_store.py` 的历史读取改为 `utf-8-sig`，兼容 PowerShell 写入带 BOM 的 JSON，避免历史记录被误读为空。

当前合规语义：
- `low`：直接进入人工审核。
- `medium`：补充发布前安全提醒，再进入人工审核。
- `high`：停止发布。

已验证：
- 人工构造的母婴健康中风险正文会被追加“发布前提醒”。
- mock 模式 LangGraph 主流程可正常保存草稿并写入记忆。
- `python .\scripts\record_performance.py --list --limit 10` 可正常读取既有 3 条运营记录。

## 2026-06-08 收口记录：M3 通过

用户完成了两条真实流程测试：

```powershell
python -m app.main --topic "小红书新手选题方法" --target-user "内容创作新手" --format image_text --approve --engine langgraph
```

结果：
- `compliance_risk_level: low`
- `publish_status: success`
- `operation_memory_written: True`
- `retrieved_memory_count: 2`
- `successful_patterns_count: 2`

```powershell
python -m app.main --topic "宝宝湿疹护理" --target-user "新手宝妈" --format image_text --approve --engine langgraph
```

结果：
- `compliance_risk_level: medium`
- `compliance_issues: ['内容中包含绝对词：一定']`
- `revised_content` 已生成安全提醒。
- `publish_status: success`
- `operation_memory_written: True`

阶段判断：
```text
M1 本地内容生成闭环：完成
M2 小红书只读采集 + 评论痛点提炼：完成
M3 JSON 运营记忆闭环：完成
successful_patterns 影响内容结构：完成
medium 合规分支修正：完成
```

当前系统已经打通：
```text
输入主题
-> 真实采集小红书笔记/评论
-> 过滤低质量笔记和噪声评论
-> 提炼 comment_insights / pain_points
-> 读取历史运营记忆
-> successful_patterns 影响生成结构
-> 生成图文/视频草稿
-> 合规检查
-> medium 风险补安全提醒
-> 人工审核
-> 保存 Markdown
-> 写入 operation_history.json
-> 人工录入表现数据
-> 下次同类主题读取历史经验
```

下次继续：
1. 进入 LLM 正式接入准备。
2. 新增统一 `llm_client`，读取 `.env` 中的 `LLM_BASE_URL`、`LLM_API_KEY`、`LLM_MODEL_NAME`。
3. 先替换 `content_node.py` / `video_node.py` 的模板生成逻辑。
4. 再替换 `review_node.py` 的模板复盘逻辑。
5. 生成节点要避免源头产生“一定、保证、彻底、根治”等绝对词，尤其母婴/健康类主题。

## 2026-06-09 更新：LLM 接入第一步

本轮目标是先打通统一 LLM 客户端和连通性检查，不直接替换内容生成节点。

已完成：
- 新增 `llm/client.py`：统一封装 OpenAI-compatible `/chat/completions` 调用。
- 支持 `mock` 模式：`LLM_MODEL_NAME=mock` 或缺少 `LLM_BASE_URL` / `LLM_API_KEY` 时走离线 mock。
- 新增 `scripts/check_llm.py`：用于检查 `.env` 中的 LLM 配置，并发起一次测试请求。
- 更新 `app/config.py`：读取 `.env`，新增 `LLM_TIMEOUT_SECONDS`。
- 更新 `.env.example`：补充 `LLM_TIMEOUT_SECONDS=60`。

已验证：
- `python .\scripts\check_llm.py` 在 mock 模式下通过。
- `python -m compileall app nodes routers platforms memory scripts llm` 通过。

下一步：
1. 在 `.env` 中填入真实模型配置：
   - `LLM_MODEL_NAME`
   - `LLM_BASE_URL`
   - `LLM_API_KEY`
   - `LLM_TIMEOUT_SECONDS`
2. 运行：
   ```powershell
   python .\scripts\check_llm.py --require-real
   ```
3. 真实连通后，再替换 `content_node.py` 的图文生成逻辑，并保留模板 fallback。

## 2026-06-09 更新：图文节点接入 DeepSeek JSON Output

本轮目标是把 `content_node.py` 从纯模板生成升级为“优先 LLM 结构化生成，失败自动回退模板”。

已完成：
- `llm/client.py` 的 `chat()` 新增 `response_format` 参数，支持 DeepSeek / OpenAI-compatible JSON Output。
- `nodes/content_node.py` 保留原模板生成逻辑为 `_template_generate_image_text`。
- `nodes/content_node.py` 新增 LLM 图文生成路径：
  - 使用 `response_format={"type": "json_object"}`。
  - 要求输出固定外层 JSON 字段：`titles`、`cover_texts`、`body`、`image_page_plan`、`image_prompts`、`tags`、`comment_call`。
  - 字段内容不固定模板，由 LLM 根据评论痛点、`successful_patterns` 和结构偏好生成。
  - 解析失败、字段缺失、模型异常时 fallback 到模板生成。
- `nodes/content_node.py` 新增生成后清理：
  - 替换“一定、保证、彻底、根治、永久、100%、最有效”等绝对词。
  - 健康/母婴/用药相关内容自动补充安全提醒。
- `app/state.py` 新增 `llm_generation`。
- `app/main.py` 输出 `llm_generation`，用于观察本次是 LLM 生成还是 fallback。
- `scripts/check_llm.py` 新增 `--json-output`，可单独验证 JSON Output 能力。

已验证：
- `python .\scripts\check_llm.py --require-real --json-output` 通过。
- 直接调用 `generate_image_text()`，真实 DeepSeek 返回合法 JSON，`llm_generation.enabled=True`。
- 完整 LangGraph 流程在不加 `--approve` 时可调用真实 LLM，且不会保存草稿或写入记忆。
- mock 模式下会走 fallback 模板，主流程不挂。
- `python -m compileall app nodes routers platforms memory scripts llm` 通过。

下一步：
- 用真实主题跑一次 `--approve` 的图文生成，人工检查 Markdown 质量。
- 如果图文质量可接受，再把同样机制接到 `video_node.py`。
- 后续再替换 `review_node.py` 的复盘逻辑。

## 2026-06-09 修复：DeepSeek JSON Output 空 content

用户正式运行图文生成时出现：
```text
llm_generation.enabled=False
error='LLM response content is empty'
```

判断：
- 已成功进入真实 LLM 调用。
- 空 content 更可能是 JSON Output + reasoning tokens 场景下 `max_tokens` 偏紧，或 prompt 输入偏大导致最终 JSON 没有输出。

已修复：
- `llm/client.py` 空 content 报错会带上 `finish_reason` 和 `usage`，便于下次排查。
- `nodes/content_node.py` 压缩传给 LLM 的 `successful_patterns`，只保留 `content_type`、`title`、`performance_score`。
- `app/config.py` 新增 `LLM_IMAGE_TEXT_MAX_TOKENS`，默认 `5000`。
- `.env.example` 新增 `LLM_IMAGE_TEXT_MAX_TOKENS=5000`。
- `nodes/content_node.py` 图文 LLM 调用改用 `settings.llm_image_text_max_tokens`。

已验证：
- 真实 `generate_image_text()` 小样本通过，`llm_generation.enabled=True`。
- 完整 LangGraph 不保存流程通过，真实 LLM 被调用，未出现空 content。
- `python -m compileall app nodes routers platforms memory scripts llm` 通过。

备注：
- 用户此前 fallback 生成的一条运营记录 `op_90bcf91cbb13` 保留，因为这是用户实际运行产生的记录。

## 2026-06-09 修复：小红书评论接口 SSL 波动不中断主流程

用户运行完整流程时在 `analyze_topic_and_pain_points` 阶段报错：
```text
requests.exceptions.SSLError: HTTPSConnectionPool(host='edith.xiaohongshu.com', ...)
```

判断：
- 报错发生在小红书评论接口请求阶段，还没有进入 LLM。
- 不是历史运行信息导致，而是真实平台接口/网络 SSL 波动。

已修复：
- `platforms/spider_xhs_collector.py` 的 `_fetch_limited_comments` 捕获 `requests.RequestException`，把单篇评论请求失败转成 `comment_fetch_errors`，不中断整次采集。
- `nodes/insight_node.py` 增加顶层采集兜底：如果真实采集整体失败，返回主题级默认 `pain_points` 和 `comment_fetch_errors`，保证 LangGraph 主流程继续。
- `app/main.py` 输出 `comment_fetch_errors_count`，便于观察部分采集失败。

已验证：
- monkey patch `_request_comment_page` 抛出 `requests.exceptions.SSLError` 时，`_fetch_limited_comments` 返回 error 字符串而不是抛异常。
- mock 完整 LangGraph 流程正常。
- `python -m compileall app nodes routers platforms memory scripts llm` 通过。

下一次真实运行时：
- 如果某篇评论接口 SSL 波动，流程会继续。
- 输出中可以观察 `comment_fetch_errors_count`。

## 2026-06-09 收口记录：真实采集 + LLM 图文生成通过

用户重新运行：
```powershell
python -m app.main --topic "小红书新手选题方法" --target-user "内容创作新手" --format image_text --approve --engine langgraph
```

结果：
- `raw_notes_count: 3`
- `raw_comments_count: 20`
- `comment_insights_count: 1`
- `pain_points_count: 1`
- `comment_fetch_errors_count: 0`
- `retrieved_memory_count: 5`
- `successful_patterns_count: 2`
- `content_type: step_tutorial`
- `compliance_risk_level: low`
- `publish_status: success`
- `post_id: output\markdown_exports\20260609_161405_小红书新手选题没人说的实操步骤，看完直接用.md`
- `llm_generation.enabled: True`
- `llm_generation.model: deepseek-v4-pro`
- `operation_memory_written: True`
- `operation_record_id: op_2479a0c24bc3`

阶段判断：
```text
真实小红书采集：通过
comment_fetch_errors 兜底机制：已验证无副作用
DeepSeek JSON Output 图文生成：通过
Markdown 草稿保存：通过
operation_history 写入：通过
```

下次继续：
1. 先打开 `output\markdown_exports\20260609_161405_小红书新手选题没人说的实操步骤，看完直接用.md`，人工检查 LLM 生成质量。
2. 如果图文质量可接受，开始把同样的 JSON Output 机制接入 `video_node.py`。
3. 然后再替换 `review_node.py` 的复盘逻辑。

更新时间：2026-06-06

## 当前阶段

项目已完成 M1，并完成 M2 的核心链路与收口工作。当前状态是：

```text
M1 本地内容生成闭环：完成
M2 真实只读采集：基本完成
M2 数据落盘：完成
M2 评论痛点聚类：完成
M2 真实痛点接入内容生成：完成
M3 复盘闭环 + JSON 运营记忆：下一步
```

现在主流程已经可以：

```text
输入主题
-> 真实采集小红书笔记和评论
-> 去标识化保存 raw_notes / raw_comments
-> 从评论中提炼 comment_insights
-> 转换为 pain_points
-> 基于真实评论痛点生成图文或视频草稿
-> 合规检查
-> 人工确认后保存 Markdown 草稿
-> 可保存采集数据到 data/collector_runs/
```

## 今日关键结论

真实采集链路已打通：

- Cookie 配置可用。
- `vendor/Spider_XHS` 可 import。
- Node 依赖已安装并可被 ExecJS 找到。
- Spider_XHS 签名 JS 可运行。
- 小红书搜索接口可返回真实笔记。
- 评论接口可返回真实评论。
- 评论数据已去标识化，不保留用户 ID、昵称、头像等身份信息。

诊断过程中确认的本地问题：

- PyExecJS 找不到 `crypto-js`，原因是 `node_modules` 在 `vendor/Spider_XHS` 下。
- `xhs_xray.js` 的相对 `require('./static/...')` 依赖 vendor 工作目录。
- Spider_XHS 的评论封装对返回结构假设过硬，遇到缺 `msg` 的成功响应会误报错。

这些问题已在我们自己的适配层解决，未修改 vendor 原始代码。

## 主要代码改动

新增：

- `platforms/comment_analysis.py`
  - 规则版评论痛点聚类。
  - 输出 `comment_insights`。
  - 将 `comment_insights` 转换为 `pain_points`。

- `scripts/check_collector.py`
  - 采集诊断脚本。
  - 支持 `--search`、`--comments`、`--debug-search`、`--debug-response`、`--save`。

- `scripts/collect_topic.py`
  - 正式采集入口。
  - 调用统一采集层，保存采集结果。

更新：

- `platforms/spider_xhs_collector.py`
  - 设置 `NODE_PATH` 指向 `vendor/Spider_XHS/node_modules`。
  - 调 Spider_XHS 时临时切到 vendor 工作目录。
  - 改为有限抓取一级评论。
  - 新增搜索/评论响应摘要。
  - 新增采集结果保存。
  - 输出 `comment_insights`。

- `platforms/mock_collector.py`
  - mock 模式也输出 `comment_insights`，保持字段一致。

- `app/state.py`
  - 增加 `comment_insights`、`collect_limit`、`save_collection`、`collection_path`、`comment_fetch_errors`。

- `nodes/insight_node.py`
  - 支持按 `collect_limit` 采集。
  - 支持主流程保存采集结果。

- `nodes/content_node.py`
  - 图文生成使用 `comment_insights`。
  - 正文加入真实评论证据。
  - 图片页规划加入评论高频问题。

- `nodes/video_node.py`
  - 视频脚本使用 `comment_insights`。
  - hook、talking points、字幕基于真实评论困惑。

- `app/main.py`
  - 增加 `--collect-limit`。
  - 增加 `--save-collection`。
  - 输出采集摘要。

## 常用命令

诊断采集配置：

```powershell
python .\scripts\check_collector.py
```

诊断搜索：

```powershell
python .\scripts\check_collector.py --search --debug-search --topic "宝宝湿疹护理" --limit 3
```

诊断评论：

```powershell
python .\scripts\check_collector.py --search --comments --debug-response --topic "宝宝湿疹护理" --limit 3
```

正式采集并保存：

```powershell
python .\scripts\collect_topic.py --topic "宝宝湿疹护理" --limit 3
```

主流程真实采集并保存：

```powershell
python -m app.main --topic "宝宝湿疹护理" --target-user "新手宝妈" --collect-limit 3 --save-collection
```

主流程真实采集、保存采集数据、保存 Markdown 草稿：

```powershell
python -m app.main --topic "宝宝湿疹护理" --target-user "新手宝妈" --collect-limit 3 --save-collection --approve
```

## 当前环境要求

`.env` 中需要：

```env
COLLECTOR_MODE=spider_xhs
XHS_COOKIES_PC=本地 Cookie
XHS_NOTE_LIMIT=3
XHS_COMMENTS_PER_NOTE=10
XHS_SORT_TYPE=3
XHS_MIN_DELAY_SECONDS=2
XHS_MAX_DELAY_SECONDS=5
```

`vendor/Spider_XHS` 下需要安装 Node 依赖：

```powershell
cd .\vendor\Spider_XHS
npm ci
```

## 下一步

进入 M3：复盘闭环 + JSON 运营记忆雏形。

建议从以下能力开始：

1. 新增 `memory/operation_history.json`。
2. 新增手工录入表现数据脚本，例如：

```powershell
python .\scripts\record_performance.py --collection-path "..." --post-id "..." --views 1000 --likes 50 --collects 20 --comments 8 --follows 3
```

3. 将主题、痛点、标题、内容形式、采集证据、表现数据、复盘结论写入 `operation_history.json`。
4. 改造 `memory_node.py`，让下次同类主题生成时读取历史高表现结构，写入 `successful_patterns`。

M3 完成标志：

```text
第二次发同类主题时，系统能引用第一次的复盘结论和高表现结构来指导生成。
```
