# 表现闭环真实检查与历史补偿设计

## 目标

本轮目标是把上一轮已经人工验证过的表现数据闭环沉淀为可重复工具，并补齐历史表现数据回写能力。

完成后，开发者可以用一条只读检查命令确认某个真实 `creator_note_id` 是否能完成“creator 作品列表 -> run state -> operation memory -> performance_records”的本地闭环；也可以用补偿命令扫描历史 run 和 operation memory，把已经录入过的表现数据补回 SQLite run state 与业务表，减少手工排查成本。

## 范围

包含：

- 新增真实表现闭环检查脚本，只读 creator 作品列表，不触发发布、修改、删除或重试。
- 检查脚本支持指定 `run_id`、`creator_note_id`、临时 SQLite DB、列表 limit，并输出结构化 JSON。
- 检查脚本把指定 JSON run 导入临时 SQLite run store，登记对应 operation memory，再调用现有 `api.record_performance()` 验证业务表同步。
- 新增历史表现补偿脚本，扫描 operation memory 中已录入表现的记录，匹配成功 run，并复用现有 `/performance` 同步路径写回业务表。
- 补偿脚本默认 `--dry-run`，显式写入时才更新 run store 与 `performance_records`。
- 补偿脚本幂等，多次运行不重复生成多条 `performance_records`。
- 增加单元测试覆盖 fake creator 列表、dry-run、不匹配跳过、成功写入与幂等。
- 更新项目记忆，记录当前闭环状态和后续限制。

不包含：

- 不新增真实发布动作。
- 不自动抓取平台指标作为后台任务。
- 不改表现分计算规则。
- 不改 business table schema。
- 不清理或迁移 `data/` 里的真实运行产物。

## 现状

`app.api.record_performance()` 已经可以在 SQLite run store、foundation schema、business tables enabled 的组合下，按 `operation_record_id`、`creator_note_id` 或 `post_id` 找到成功 run，把表现数据合并回 run state，并复用 `_save_run()` 刷新 `performance_records`。

当前缺口有两个：

1. 真实闭环验证只停留在一次性手写脚本，无法稳定复跑，也不方便交给后续开发者使用。
2. 历史 operation memory 中可能已经有 `performance_recorded` 记录，但对应 run 仍停留在旧 state，`performance_records` 也可能缺失。

## 设计方案

### 真实闭环检查脚本

新增 `scripts/check_real_performance_closure.py`。

脚本职责：

- 临时设置 SQLite run store、SQLite operation memory、foundation schema 和 business tables enabled。
- 默认使用 `data/real_performance_closure_<随机>.sqlite3`，也允许通过 `--db-path` 指定。
- 调用 `platforms.creator.list_published_notes(limit=...)` 做只读作品列表检查。
- 从 `data/api_runs/<run_id>.json` 读取指定 run，并保存到临时 SQLite run store。
- 从 run state 生成 operation memory 记录。
- 构造表现 payload，优先使用命令行指标；如果启用 `--use-platform-metrics`，从作品列表中能识别的指标快照补齐缺失指标。
- 调用 `api.record_performance(payload)` 走现有同步路径。
- 读取 `api.get_business_run_snapshot(run_id)`，汇总 `performance_records` 行数和关键字段。
- 输出 JSON，包含 `ok`、`platform_note`、`business_sync`、`business_counts`、`performance_record`、`checks`。

脚本不直接写入生产 SQLite；默认使用临时 DB。指定 `--db-path` 时也只操作该 DB，不碰真实平台写操作。

### 历史表现补偿脚本

新增 `scripts/backfill_performance_records.py`。

脚本职责：

- 使用当前配置的 run store 和 operation memory。
- 只处理状态为 `performance_recorded` 且包含 `performance_data` 的 operation memory 记录。
- 通过现有 `api.record_performance()` 回写 run state 和 business tables，而不是另写 SQL。
- 匹配条件继续复用 `/performance` 的逻辑：`operation_record_id`、`creator_note_id`、`post_id`。
- 默认 `--dry-run`，只输出将处理、将跳过和错误摘要。
- 传入 `--apply` 时才执行写入；`--dry-run` 和 `--apply` 互斥，默认等价 dry-run。
- 支持 `--record-id`、`--creator-note-id`、`--post-id`、`--limit` 缩小范围。

幂等性来自 `performance_records.performance_id` 的确定性生成：同一个 `operation_record_id`、`creator_note_id`、`run_id` 会落到同一个主键，重复回写只更新同一行。

### 输出结构

真实检查脚本输出示例：

```json
{
  "ok": true,
  "run_id": "run_fda76a64a278",
  "creator_note_id": "6a2bce0b000000003502c564",
  "db_path": "data/real_performance_closure_xxxxxxxx.sqlite3",
  "platform_note": {"found": true, "source": "creator_v2"},
  "business_sync": {"status": "success", "run_id": "run_fda76a64a278"},
  "business_counts": {"performance_records": 1},
  "checks": {
    "platform_note_found": true,
    "memory_updated": true,
    "business_sync_success": true,
    "run_state_synced": true,
    "performance_record_written": true
  }
}
```

补偿脚本输出示例：

```json
{
  "dry_run": false,
  "processed": [{"record_id": "op_xxx", "run_id": "run_xxx", "business_sync": {"status": "success"}}],
  "skipped": [{"record_id": "op_yyy", "reason": "performance data is empty"}],
  "errors": []
}
```

## 错误处理

- creator 只读列表失败：真实检查脚本返回 `ok=false`，不继续声称平台闭环完成。
- 指定 run 文件不存在：返回错误并退出非 0。
- operation memory 找不到匹配记录：真实检查脚本先从 run state 登记记录；补偿脚本则列入 skipped。
- `/performance` 同步返回 skipped：脚本不吞掉原因，原样放入 `business_sync.reason`。
- 写入异常：进入 `errors`，退出码为 1。
- 所有输出沿用现有脱敏逻辑可见面，不打印 Cookie 或 token。

## 测试策略

新增测试文件：

- `tests/test_check_real_performance_closure.py`
- `tests/test_backfill_performance_records.py`

覆盖点：

- fake `list_published_notes()` 可驱动真实检查脚本，不访问真实网络。
- 真实检查脚本能导入 run、登记 operation memory、调用 `record_performance()` 并写出一条 `performance_records`。
- 补偿脚本默认 dry-run 不写库。
- 补偿脚本 `--apply` 能把历史表现补回 run state 和 `performance_records`。
- 不匹配 success run 的历史记录进入 skipped。
- 重复执行补偿保持 `performance_records` 一条记录。

验证命令：

```powershell
D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_check_real_performance_closure.py tests/test_backfill_performance_records.py -q
D:\Anaconda\envs\ContentShare\python.exe .\scripts\check_sqlite_stack.py
D:\Anaconda\envs\ContentShare\python.exe -m compileall app scripts tests
D:\Anaconda\envs\ContentShare\python.exe -m pytest -q
```

真实只读验证命令在本地网络允许时执行：

```powershell
D:\Anaconda\envs\ContentShare\python.exe .\scripts\check_real_performance_closure.py --run-id run_fda76a64a278 --creator-note-id 6a2bce0b000000003502c564 --use-platform-metrics
```

## 成功标准

- 本地测试可证明两个脚本的主要行为。
- `check_real_performance_closure.py` 可以复现上一轮真实闭环检查流程，且只读平台。
- `backfill_performance_records.py --apply` 可以把历史表现记录补回 run state 与 `performance_records`。
- dry-run 是默认行为，避免误写真实工作库。
- 全量 pytest、compileall、SQLite stack smoke 通过。
