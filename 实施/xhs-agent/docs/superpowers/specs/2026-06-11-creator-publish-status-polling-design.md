# creator 发布状态只读同步设计

## 目标

在已经完成真实 creator 私密发布、creator v2 作品列表同步和 `creator_note_id` 表现回填烟测后，补上 M4 真实平台端到端中的“发布状态轮询/状态同步”最小能力。

本轮只做只读同步，不触发任何 creator 发布、修改、公开、删除或重试操作。用户或工作台可以用 `creator_note_id` 查询平台侧当前状态，系统把平台返回字段归一化为可展示、可诊断的本地状态。

## 范围

本轮包含：
- 在 creator 适配层新增按 `creator_note_id` 查询/归一化发布状态的函数。
- 复用现有 creator v2 作品列表能力，不新增新的写入接口。
- 后端新增一个轻量 API 辅助函数，供后续 HTTP 路由和工作台调用。
- 工作台在已有“同步作品列表”结果中显示平台状态摘要。
- 新增测试覆盖状态归一化、找不到笔记、敏感字段脱敏和前端静态契约。

本轮不包含：
- 不做公开发布、视频发布、定时发布。
- 不自动轮询后台任务，不新增队列任务。
- 不自动写回主运营记忆，除非用户后续明确要把同步状态沉淀到记忆。
- 不自动抓取或回填表现数据；表现回填仍走现有人工录入入口。

## 状态模型

状态归一化基于 creator v2 作品列表中已经可见的字段：
- `permission_msg`：例如 `仅自己可见`，用于判断私密/权限提示。
- `permission_code`：平台权限码，作为辅助字段保留。
- `tab_status`：平台列表分类状态，作为辅助字段保留。
- `type`：平台内容类型，例如 `normal`。
- `view_count`、`likes`、`collected_count`、`comments_count`：只作为状态摘要中的指标，不自动写入表现。

归一化结果建议：
- `synced`：找到了平台笔记，并成功读取状态。
- `not_found`：作品列表中没有找到该 `creator_note_id`。
- `unavailable`：Cookie 缺失、接口失败或返回不可解析。

对于 `synced` 状态，额外返回：
- `visibility_label`：优先使用 `permission_msg`，为空时按 `permission_code` 兜底。
- `platform_type`、`permission_code`、`tab_status`。
- `metrics_snapshot`：只读指标快照。
- `raw`：继续使用现有敏感字段脱敏结果。

## 后端设计

`platforms.creator` 新增：
- `get_published_note_status(creator_note_id: str, limit: int = 50) -> dict`

该函数复用 `list_published_notes()`：
1. 校验 `creator_note_id` 非空。
2. 调用 creator 列表同步，只读获取最近作品。
3. 在 `notes` 中匹配 `note_id`。
4. 找到后返回 `ok=True`、`status="synced"` 和归一化状态。
5. 找不到时返回 `ok=False`、`status="not_found"`。
6. 列表接口失败时返回 `ok=False`、`status="unavailable"` 和脱敏错误。

`app.api` 新增：
- `get_creator_note_status(creator_note_id: str) -> dict`

HTTP 层后续可复用该函数，保持与现有 `list_creator_notes()`、`record_performance()` 风格一致。本轮若改路由，仅新增只读 `GET /creator/notes/status?creator_note_id=...`，不改变现有接口行为。

## 前端设计

工作台已有“同步作品列表”按钮和作品列表渲染。本轮最小增强：
- 列表项显示平台状态摘要，例如 `仅自己可见`、浏览/点赞/收藏/评论快照。
- 保持点击作品填入 `creator_note_id` 的现有行为。
- 不新增自动轮询按钮，不新增定时器，避免用户误以为系统会持续抓取。

如果后续需要独立查询某条笔记状态，再在表现录入区增加“查询状态”按钮；本轮优先利用同步列表结果。

## 错误处理

- 缺少 Cookie：返回 `unavailable`，错误信息沿用 creator runtime/list 错误，不暴露 Cookie。
- 平台接口失败：返回 `unavailable`，不自动重试。
- 找不到笔记：返回 `not_found`，提示用户先同步作品列表或检查 `creator_note_id`。
- 原始响应中的 `xsec_token`、cookie、authorization、token、password 等字段继续脱敏。

## 测试计划

单元测试：
- `get_published_note_status()` 能从列表结果匹配目标 `creator_note_id`。
- 找不到目标时返回 `not_found`。
- 列表失败时返回 `unavailable`。
- 状态结果中的 raw 仍脱敏。

API 测试：
- `get_creator_note_status()` 返回适配层结果。
- HTTP 路由如果新增，则覆盖缺少参数和正常返回。

前端静态测试：
- 作品列表渲染包含平台状态摘要和指标快照。
- 点击作品填入 `creator_note_id` 的既有契约不变。

真实验证：
- 使用 `CREATOR_MODE=spider_xhs` 和已有 creator Cookie，只读同步 `creator_note_id=6a2abffc0000000022027f7a`。
- 预期返回 `status=synced`，`visibility_label=仅自己可见`，指标快照为当前平台值。

## 风险与边界

- creator v2 列表只返回最近作品，较旧笔记可能需要更大 `limit` 或分页。本轮默认最多读取 50 条，避免过度请求。
- 平台字段含义可能变化，因此本轮保留原始脱敏 raw，便于后续诊断。
- 这不是平台审核状态的权威完整轮询，只是当前作品列表可见状态的只读同步。
