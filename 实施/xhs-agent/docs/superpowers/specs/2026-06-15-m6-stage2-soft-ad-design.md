# M6 阶段二 · 软广+达人面试展示版设计

日期：2026-06-15
状态：设计完成，待用户审阅

## 1. 目标与范围

面试展示版阶段二最小闭环：商品/卖点输入 → 软广内容生成 → 商业合规+频率护栏 → 达人/平台 mock 适配 → 人工审核。

**不做**：真实千帆/蒲公英全量自动化、公开发布、定时发布。

## 2. 用户决策记录

| 决策项 | 选择 |
|---|---|
| 商品/卖点输入 | 用户手动输入（input_node 阶段） |
| 阶段触发 | API/CLI 参数 `stage_override` 覆盖，不依赖 .env |
| 软广生成节点 | 独立 `soft_ad_node.py`，与 content_node 平级 |
| 商业合规 | 复用现有 `compliance_node`，新增软广专属规则 |
| 频率护栏 | 从 operation memory 实时统计，`.env` 配置阈值 |
| 千帆/蒲公英 | 完整 mock adapter 接口（`platforms/qianfan.py`、`platforms/pugongying.py`） |
| 路由方式 | 两级路由：先 `route_content_type`，再 `route_content_format` |
| 内容生成 | LLM 优先 + 模板兜底，与现有 content_node 模式一致 |

## 3. LangGraph 图结构变更

```
START
  → load_user_input (扩展：支持输入商品信息)
  → check_account_stage (扩展：支持 stage_override)
  → analyze_topic_and_pain_points
  → retrieve_graphrag_memory
  → decide_content_strategy (扩展：允许 soft_ad 输出 + 频率护栏 pre-check)
  → route_content_type (新增，内部委托 route_content_format)
      ├─ soft_ad → product_node (新增) → soft_ad_node (新增) → check_compliance
      ├─ image_text → generate_image_text (现有)
      ├─ video → generate_video_script (现有)
      └─ error → END
  → refresh_graphrag_memory_after_compliance
  → route_compliance_result (现有，扩展软广风险维度)
  → human_review → publish_or_schedule → creator_publish_or_skip → review_performance → write_operation_memory → END
```

**两级路由实现方式**：`route_content_type` 先判断 `content_type=="soft_ad"`，是则返回 `product_node`；否则委托给现有 `route_content_format` 做 image_text/video 分流。在 `graph.py` 中用一条 conditional edge 表达，两个路由函数职责分离但串联调用。

## 4. State 字段变更

### 4.1 已有字段（不变）

`product_info`、`product_selling_points`、`product_pain_match` 已在 `XHSState` 中定义。

### 4.2 新增/扩展字段

```python
# 用户输入扩展
user_product_name: str              # 用户输入的商品名称
user_product_selling_points: str    # 用户输入的卖点描述（自由文本）

# 阶段覆盖
stage_override: Optional[Literal["cold_start", "growth", "monetization_ready"]]

# 软广频率护栏（运行时计算）
soft_ad_frequency_check: Dict[str, Any]  # {allowed: bool, this_week_count: int, last_published_at: str, reason: str}

# 达人/蒲公英相关（M6 阶段二新增）
darwin_candidates: List[Dict[str, Any]]   # 达人匹配候选
darwin_selected: Optional[Dict[str, Any]] # 选中的达人
```

## 5. 新增文件

### 5.1 `nodes/product_node.py` — 商品选择节点

- **职责**：读取用户输入的商品信息 → 写入 State → 调用千帆 mock 做轻量商品搜索 → 商品卖点与痛点匹配
- **读 State**：`user_product_name`、`user_product_selling_points`、`pain_points`、`user_topic`
- **写 State**：`product_info`（商品基本信息）、`product_selling_points`（卖点列表）、`product_pain_match`（痛点-卖点匹配）

**执行逻辑**：
1. 从 `user_product_name` / `user_product_selling_points` 提取商品信息
2. 调 `platforms/qianfan.py` 的 `search_product()` 做 mock 商品搜索
3. 将商品卖点与当前 `pain_points` 做简单关键词匹配
4. 如果用户没提供商品信息，返回错误让上游重试

### 5.2 `nodes/soft_ad_node.py` — 软广内容生成

- **职责**：基于商品信息 + 用户痛点 + 记忆上下文，生成软广图文内容
- **读 State**：`user_topic`、`target_user`、`pain_points`、`comment_insights`、`product_info`、`product_selling_points`、`product_pain_match`、`graphrag_memory`
- **写 State**：`titles`、`cover_texts`、`body`、`image_page_plan`、`image_prompts`、`tags`、`comment_call`、`llm_generation`

**执行逻辑**：
1. LLM 模式：构造 soft_ad 专用 prompt，JSON 模式生成。prompt 中包含商品卖点、痛点匹配、软广结构模板（和 knowledge_share 不同：要求自然植入、加广告标识）
2. 模板兜底：LLM 不可用时用规则拼装软广内容

### 5.3 软广内容结构模板

在 `config/content_structures.json` 的 `structure_profiles` 中新增：

```json
"soft_ad": {
  "label": "好物分享",
  "title_templates": [
    "{topic}用到的一个好东西，先讲清楚再决定要不要试",
    "关于{topic}，我最近试了一个思路",
    "{primary_pain}，后来发现可以这样解决"
  ],
  "cover_main": "{topic}好物思路",
  "cover_sub": "先看清楚再决定",
  "body_heading": "评论里最集中的问题是：",
  "soft_ad_heading": "我用了一个东西来帮自己理清楚：",
  "action_heading": "建议你先按下面顺序判断：",
  "action_steps": [
    "先看自己的具体场景和问题是否对得上。",
    "再去了解这个产品具体能做什么、不能做什么。",
    "最后决定要不要试，不要因为种草盲买。"
  ],
  "page_titles": ["先讲问题", "解决方案", "产品思路", "理性提醒"],
  "page_texts": ["先看真实问题", "{primary_pain}", "我是怎么用的", "别盲买，先判断"],
  "video_hook": "如果你也在纠结{topic}，先别急着买，听我说完。",
  "video_points": ["先讲清楚问题", "再讲我用什么的思路", "最后给出理性判断提醒"],
  "ad_disclaimer": "本内容包含商业合作信息，请理性种草。"
}
```

### 5.4 `platforms/qianfan.py` — 千帆选品 mock adapter

- 参考 `platforms/creators.py` 的模式：mock/real 切换，接口签名一致
- Mock 实现：
  - `search_product(keyword)` → 返回 2-3 条 mock 商品（名称、价格区间、品类、卖点标签）
  - `get_product_detail(product_id)` → 返回单商品详情
- 环境变量：`QIANFAN_MODE`（默认 `mock`）、`XHS_QIANFAN_COOKIES`

### 5.5 `platforms/pugongying.py` — 蒲公英达人 mock adapter

- 同样模式：mock/real 切换
- Mock 实现：
  - `search_darwin(topic, limit)` → 返回 3-5 位 mock 达人（昵称、粉丝量级、内容风格标签、合作报价区间）
  - `get_darwin_detail(darwin_id)` → 返回单达人详情
  - `send_invite(darwin_id, message)` → mock 邀约发送（返回假邀约 ID）
- 环境变量：`PUGONGYING_MODE`（默认 `mock`）、`XHS_PUGONGYING_COOKIES`

## 6. 修改文件

### 6.1 `nodes/stage_node.py` — 支持 stage_override

新增逻辑：
```python
def check_account_stage(state: XHSState) -> dict:
    override = state.get("stage_override")
    if override in ("cold_start", "growth", "monetization_ready"):
        rules = get_stage_rules(override)
        return {"account_stage": rules["account_stage"], "allow_soft_ad": rules["allow_soft_ad"]}
    # 原有逻辑继续...
```

`get_stage_rules()` 新增 `monetization_ready` 阶段的规则：
```python
MONETIZATION_READY_RULES = {
    "account_stage": "monetization_ready",
    "allow_soft_ad": True,
    "allowed_content_types": [
        "knowledge_share", "experience_summary", "avoid_mistakes",
        "qa_education", "step_tutorial", "soft_ad",
    ],
    "allowed_content_formats": ["image_text", "video"],
    "manual_review_required": True,
    "soft_ad_weekly_limit": 2,
    "soft_ad_no_back_to_back": True,
}
```

### 6.2 `nodes/input_node.py` — 支持商品输入

扩展输入字段：
- `user_product_name`：商品名称（可选，阶段二时必填）
- `user_product_selling_points`：卖点描述（可选，自由文本）

阶段二运行时会校验：如果 `allow_soft_ad=True` 且用户选了软广，需要提供商品信息。

### 6.3 `nodes/compliance_node.py` — 新增软广专属规则

在 `check_compliance` 中，当 `content_type == "soft_ad"` 时额外检查：

1. **广告标识检查**：内容是否包含广告/合作相关标识
2. **功效承诺检查**：是否包含与商品相关的绝对化功效承诺
3. **频率护栏检查**：从 `soft_ad_frequency_check` 读取运行时计算结果
   - `this_week_count >= weekly_limit` → 新增 issue，风险等级中
   - `last_published_at` 为上一条 → 新增 issue，风险等级中

软广合规规则写入 `config/compliance_rules.json`，新增：
```json
"soft_ad_rules": {
  "required_disclaimers": ["广告", "合作", "理性种草"],
  "forbidden_soft_ad_words": ["根治", "必买", "必入", "神药", "秒杀一切"],
  "forbidden_efficacy_claims": ["用完就", "一次就", "绝对有效"],
  "weekly_limit": 2,
  "no_back_to_back": true
}
```

### 6.4 `routers/` — 新增 `route_content_type`

新建 `routers/content_type_router.py`：

```python
from app.state import XHSState
from routers.content_format_router import route_content_format


def route_content_type(state: XHSState) -> str:
    """先判断 content_type，soft_ad 走独立分支，其余委托 format 路由。"""
    content_type = state.get("content_type", "knowledge_share")
    if content_type == "soft_ad":
        return "product_node"
    return route_content_format(state)
```

此路由合并了两级判断：type 不匹配 → 委托给 `route_content_format` 走现有 image_text/video 分流。

### 6.5 `app/graph.py` — 注册新节点和路由

变更点：
1. 删除 `decide_content_strategy` → `route_content_format` 的原条件边，替换为 `decide_content_strategy` → `route_content_type` 条件边
2. `route_content_type` 的映射：`"product_node"` → `product_node`，`"generate_image_text"` → `generate_image_text`，`"generate_video_script"` → `generate_video_script`，`"error_handler"` → `END`
3. 注册 `product_node`、`soft_ad_node` 两个新节点
4. `product_node` → `soft_ad_node`（直连边）
5. `soft_ad_node` → `check_compliance`（直连边）
6. 不再需要独立的 `route_content_format` 条件边——`route_content_type` 内部委托给了 `route_content_format`

### 6.6 `app/config.py` — 扩展阶段规则

`get_stage_rules()` 支持 `monetization_ready`，返回对应的规则字典。

### 6.7 `config/strategy_rules.json` — 扩展

`valid_content_types` 新增 `"soft_ad"`。

### 6.8 `app/main.py` / CLI — 新增 `--stage` 参数

CLI 新增 `--stage` 参数：
```
python -m app.main --stage monetization_ready --topic "宝宝辅食"
```

API `POST /runs` 新增 `stage_override` 字段。

### 6.9 `config/compliance_rules.json` — 新增软广规则

如 6.3 节所述。

## 7. 频率护栏实现

### 7.1 检查时机

频率护栏在 **两个位置** 执行：
1. **`decide_content_strategy`（策略节点）**：在策略选择前先做频率 pre-check。如果频率检查不通过（本周已满/连发），强制回退 `content_type` 到非 soft_ad 类型（如 `knowledge_share`）
2. **`check_compliance`（合规节点）**：再次验证 `content_type=="soft_ad"` 时频率护栏状态，兜底拦截

### 7.2 实现

在 `nodes/strategy_node.py` 中新增 `_check_soft_ad_frequency()`：

```python
def _check_soft_ad_frequency() -> dict:
    """从 operation memory 统计本周软广发布情况"""
    from memory.operation_store import list_records_by_type
    records = list_records_by_type("soft_ad", days=7)
    this_week_count = len(records)
    last_record = records[0] if records else None
    
    rules = load_compliance_rules().get("soft_ad_rules", {})
    weekly_limit = int(rules.get("weekly_limit", 2))
    no_back_to_back = bool(rules.get("no_back_to_back", True))
    
    issues = []
    if this_week_count >= weekly_limit:
        issues.append(f"本周软广已达上限 {weekly_limit} 篇")
    if no_back_to_back and last_record:
        issues.append("不允许连发软广")
    
    return {
        "allowed": len(issues) == 0,
        "this_week_count": this_week_count,
        "weekly_limit": weekly_limit,
        "last_published_at": last_record.get("published_at") if last_record else None,
        "issues": issues,
    }
```

`decide_content_strategy` 中调用：
```python
def decide_content_strategy(state: XHSState) -> dict:
    content_type = _choose_content_type(state)
    ...
    # 频率护栏 pre-check
    if content_type == "soft_ad":
        freq_check = _check_soft_ad_frequency()
        if not freq_check["allowed"]:
            content_type = DEFAULT_CONTENT_TYPE  # 回退到知识分享
        updates["soft_ad_frequency_check"] = freq_check
    ...
```

## 8. LLM Prompt 新增

在 `config/llm_prompts.json` 中新增 `soft_ad_generation`：

```json
{
  "soft_ad_generation": {
    "system": "你是小红书好物分享内容生成助手。核心原则：先讲清问题，再说产品思路，最后提醒理性判断。必须输出合法 JSON，不要 Markdown，不要代码块。内容必须自然植入，不能硬广。必须包含广告/合作标识。不能夸大产品功效，不能承诺具体效果，不能制造焦虑。不能虚构个人经历或使用效果。涉及产品的表述必须是'提供一个思路/工具'，不是'解决方案'。",
    "user_template": "请根据下面输入生成一篇小红书好物分享笔记草稿。必须严格输出 JSON，字段必须与 expected_json 一致。\n\nexpected_json:\n{expected_json}\n\ninput:\n{input_payload}",
    "expected_json": {
      "titles": ["标题1", "标题2", "标题3"],
      "cover_texts": ["封面主标题", "封面副标题", "收藏提示"],
      "body": "正文内容，允许分段，但必须是字符串。",
      "image_page_plan": [
        {"page": 1, "title": "第一页标题（问题）", "text": "第一页文字"},
        {"page": 2, "title": "第二页标题（产品思路）", "text": "第二页文字"},
        {"page": 3, "title": "第三页标题（理性提醒）", "text": "第三页文字"}
      ],
      "image_prompts": ["配图提示词1", "配图提示词2"],
      "tags": ["标签1", "标签2", "标签3"],
      "comment_call": "评论区引导语",
      "ad_disclaimer": "本内容包含商业合作信息，请理性种草。"
    }
  }
}
```

## 9. 测试计划

| 测试文件 | 覆盖内容 |
|---|---|
| `tests/test_product_node.py` | 商品节点：正常输入、缺少商品信息、mock 匹配 |
| `tests/test_soft_ad_node.py` | 软广生成：LLM/mock 模式、模板兜底、结构校验 |
| `tests/test_content_type_router.py` | 路由：soft_ad 分流、非 soft_ad 走原路 |
| `tests/test_soft_ad_compliance.py` | 合规：软广规则、频率护栏统计 |
| `tests/test_stage_override.py` | 阶段覆盖参数 |
| `tests/test_qianfan_mock.py` | 千帆 mock adapter |
| `tests/test_pugongying_mock.py` | 蒲公英 mock adapter |

## 10. 实施顺序

1. **State + 配置**：State 字段、config JSON、stage_override
2. **路由层**：`route_content_type` 新路由 + `graph.py` 边变更
3. **千帆/蒲公英 mock adapter**：`platforms/qianfan.py`、`platforms/pugongying.py`
4. **product_node**：商品选择节点
5. **soft_ad_node**：软广内容生成（LLM + 模板兜底）
6. **合规扩展**：compliance_node 软广规则 + 频率护栏
7. **CLI/API 扩展**：`--stage` 参数 + input_node 商品字段
8. **测试**：逐模块测试
9. **端到端 smoke**：完整软广链路跑通
