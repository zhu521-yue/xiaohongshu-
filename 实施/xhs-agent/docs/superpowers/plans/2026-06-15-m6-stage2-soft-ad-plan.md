# M6 阶段二 · 软广+达人面试展示版实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现面试展示版阶段二最小闭环：商品/卖点输入 → 软广内容生成 → 商业合规+频率护栏 → 达人/平台 mock 适配 → 人工审核。

**Architecture:** 在现有 LangGraph 主链上扩展，新增 product_node（商品选择）、soft_ad_node（软广生成）两个节点和 route_content_type（两级路由），新增 qianfan/pugongying mock adapter，扩展现有 compliance_node（软广合规）、stage_node（stage_override）、input_node（商品字段）和 graph.py（图结构）。

**Tech Stack:** Python 3.11, LangGraph 1.2.1, 现有 LLM client, 现有 operation_store (JSON/SQLite)

**Spec:** `docs/superpowers/specs/2026-06-15-m6-stage2-soft-ad-design.md`

---

### Task 1: 配置层准备 — State 字段、规则 JSON、阶段规则

**Files:**
- Modify: `app/state.py:10-115`
- Modify: `config/strategy_rules.json:1-7`
- Modify: `config/compliance_rules.json:1-7`
- Modify: `app/config.py:45-60`

- [ ] **Step 1: 在 XHSState 中新增 M6 字段**

在 `app/state.py` 的 `XHSState` 类中新增字段。在 `# 商品软广相关，M1 暂不使用，阶段二再接入` 注释下方新增：

```python
    # 用户输入扩展（阶段二）
    user_product_name: Optional[str]
    user_product_selling_points: Optional[str]

    # 阶段覆盖
    stage_override: Optional[Literal["cold_start", "growth", "monetization_ready"]]

    # 软广频率护栏
    soft_ad_frequency_check: Optional[Dict[str, Any]]

    # 达人/蒲公英相关
    darwin_candidates: Optional[List[Dict[str, Any]]]
    darwin_selected: Optional[Dict[str, Any]]
```

也需修改 `from typing import Any, Dict, List, Literal, Optional, TypedDict` 确保 `Optional` 已导入（检查已有 import）。

- [ ] **Step 2: 扩展 strategy_rules.json**

编辑 `config/strategy_rules.json`，在 `valid_content_types` 数组中新增 `"soft_ad"`：

```json
{
  "avoid_mistake_keywords": ["避坑", "误区", "踩坑", "靠谱不靠谱", "坑"],
  "step_tutorial_keywords": ["步骤", "流程", "第一步", "从哪开始", "怎么开始", "入门", "清单"],
  "valid_content_types": ["knowledge_share", "experience_summary", "avoid_mistakes", "qa_education", "step_tutorial", "soft_ad"],
  "default_content_type": "knowledge_share",
  "default_content_format": "image_text"
}
```

- [ ] **Step 3: 在 compliance_rules.json 中新增软广规则**

在 `config/compliance_rules.json` 文件末尾（`"safety_note"` 字段之后）新增：

```json
  "soft_ad_rules": {
    "required_disclaimers": ["广告", "合作", "理性种草"],
    "forbidden_soft_ad_words": ["根治", "必买", "必入", "神药", "秒杀一切"],
    "forbidden_efficacy_claims": ["用完就", "一次就", "绝对有效"],
    "weekly_limit": 2,
    "no_back_to_back": true
  }
```

- [ ] **Step 4: 扩展 app/config.py 的阶段规则**

在 `app/config.py` 中，在 `COLD_START_RULES` 下方新增 `MONETIZATION_READY_RULES`，并修改 `get_stage_rules()`：

```python
MONETIZATION_READY_RULES = {
    "account_stage": "monetization_ready",
    "allow_soft_ad": True,
    "allowed_content_types": [
        "knowledge_share",
        "experience_summary",
        "avoid_mistakes",
        "qa_education",
        "step_tutorial",
        "soft_ad",
    ],
    "allowed_content_formats": ["image_text", "video"],
    "manual_review_required": True,
}


def get_stage_rules(account_stage: str) -> dict:
    if account_stage == "cold_start":
        return COLD_START_RULES
    if account_stage == "monetization_ready":
        return MONETIZATION_READY_RULES
    raise ValueError(f"Unsupported account stage: {account_stage}")
```

- [ ] **Step 5: 验证 — 运行现有测试确保无回归**

```bash
cd "D:\codex\project\小红书内容分享\实施\xhs-agent" && D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_strategy_memory_context.py tests/test_memory_node.py tests/test_compliance_node.py -v
```

预期：全部 PASS

- [ ] **Step 6: 提交**

```bash
git add app/state.py config/strategy_rules.json config/compliance_rules.json app/config.py
git commit -m "feat: add m6 state fields, stage rules, and compliance config"
```

---

### Task 2: 路由层 — route_content_type + graph.py 边变更

**Files:**
- Create: `routers/content_type_router.py`
- Modify: `app/graph.py:227-305`

- [ ] **Step 1: 创建 content_type_router.py**

```python
"""Content-type routing for stage-2 soft-ad branching.

Delegates to content_format_router for non-soft-ad types so the existing
image_text / video split stays unchanged.
"""

from app.state import XHSState
from routers.content_format_router import route_content_format


def route_content_type(state: XHSState) -> str:
    """Return next node name based on content_type.

    soft_ad → product_node
    everything else → delegate to route_content_format (image_text / video / error)
    """
    content_type = state.get("content_type", "knowledge_share")
    if content_type == "soft_ad":
        return "product_node"
    return route_content_format(state)
```

文件路径：`D:\codex\project\小红书内容分享\实施\xhs-agent\routers\content_type_router.py`

- [ ] **Step 2: 修改 graph.py 导入和节点注册**

在 `app/graph.py` 中：
1. 新增 import 行：

```python
from nodes.product_node import select_product
from nodes.soft_ad_node import generate_soft_ad
from routers.content_type_router import route_content_type
```

2. 新增节点注册（在 `graph.add_node("decide_content_strategy", ...)` 之后）：

```python
graph.add_node("select_product", select_product)
graph.add_node("generate_soft_ad", generate_soft_ad)
```

3. 删除旧的条件边 `graph.add_conditional_edges("decide_content_strategy", route_content_format, ...)`，替换为：

```python
graph.add_conditional_edges(
    "decide_content_strategy",
    route_content_type,
    {
        "product_node": "select_product",
        "generate_image_text": "generate_image_text",
        "generate_video_script": "generate_video_script",
        "error_handler": END,
    },
)
```

4. 新增直连边：

```python
graph.add_edge("select_product", "generate_soft_ad")
graph.add_edge("generate_soft_ad", "check_compliance")
```

- [ ] **Step 3: 同时更新 local 执行器 run_local_graph**

在 `app/graph.py` 的 `run_local_graph()` 函数中，`decide_content_strategy` 节点执行后新增 type 路由逻辑：

```python
    if state.get("content_type") == "soft_ad":
        state = _run_node(
            state,
            select_product,
            node_name="select_product",
            run_id=run_id,
            event_db_path=event_db_path,
        )
        state = _run_node(
            state,
            generate_soft_ad,
            node_name="generate_soft_ad",
            run_id=run_id,
            event_db_path=event_db_path,
        )
    elif state.get("content_format") == "video":
        state = _run_node(
            state,
            generate_video_script,
            node_name="generate_video_script",
            run_id=run_id,
            event_db_path=event_db_path,
        )
    else:
        state = _run_node(
            state,
            generate_image_text,
            node_name="generate_image_text",
            run_id=run_id,
            event_db_path=event_db_path,
        )
```

替换掉原有的内容生成 if/else 块。

- [ ] **Step 4: 验证 — 编译和路由测试**

```bash
cd "D:\codex\project\小红书内容分享\实施\xhs-agent" && D:\Anaconda\envs\ContentShare\python.exe -c "from routers.content_type_router import route_content_type; print('import ok')"
```

预期：`import ok`

- [ ] **Step 5: 提交**

```bash
git add routers/content_type_router.py app/graph.py
git commit -m "feat: add route_content_type and soft_ad branch in graph"
```

---

### Task 3: 千帆 mock adapter

**Files:**
- Create: `platforms/qianfan.py`

- [ ] **Step 1: 写测试文件**

创建 `tests/test_qianfan_mock.py`：

```python
"""Test Qianfan platform adapter."""
from __future__ import annotations

import pytest
from platforms import qianfan


def test_search_product_returns_list():
    result = qianfan.search_product("婴儿辅食机")
    assert isinstance(result, list)
    assert len(result) >= 1
    for item in result:
        assert isinstance(item, dict)
        assert "product_id" in item
        assert "name" in item
        assert "price_range" in item
        assert "selling_points" in item


def test_search_product_empty_keyword_raises():
    with pytest.raises(ValueError):
        qianfan.search_product("")


def test_get_product_detail_returns_dict():
    result = qianfan.get_product_detail("mock_prod_001")
    assert isinstance(result, dict)
    assert result["product_id"] == "mock_prod_001"
    assert "name" in result
    assert "selling_points" in result


def test_get_product_detail_invalid_id_raises():
    with pytest.raises(ValueError):
        qianfan.get_product_detail("")


def test_check_qianfan_runtime_mock_ok():
    result = qianfan.check_qianfan_runtime()
    assert result["ok"] is True
    assert result["mode"] == "mock"


def test_mode_defaults_to_mock(monkeypatch):
    monkeypatch.setenv("QIANFAN_MODE", "")
    from platforms.qianfan import _mode
    assert _mode() == "mock"
```

- [ ] **Step 2: 运行测试，确认 FAIL（文件不存在）**

```bash
cd "D:\codex\project\小红书内容分享\实施\xhs-agent" && D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_qianfan_mock.py -v
```

预期：全部 FAIL（ModuleNotFoundError）

- [ ] **Step 3: 创建 platforms/qianfan.py**

```python
"""Qianfan (千帆) platform adapter for product selection.

Follows the same mock/real pattern as platforms/creators.py.
Stage 2 (M6) uses this to look up products for soft-ad content.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")

PLATFORM = "qianfan"


def _mode() -> str:
    return os.getenv("QIANFAN_MODE", "mock").strip().lower() or "mock"


def _validate_mode(mode: str) -> None:
    if mode not in {"mock", "spider_xhs"}:
        raise ValueError(f"Unsupported QIANFAN_MODE: {mode}")


def check_qianfan_runtime() -> dict:
    mode = _mode()
    try:
        _validate_mode(mode)
    except ValueError as exc:
        return {"ok": False, "mode": mode, "platform": PLATFORM, "error": str(exc)}

    if mode == "mock":
        return {"ok": True, "mode": mode, "platform": PLATFORM}

    # Real mode would check Spider_XHS Qianfan API availability
    cookies = (os.getenv("XHS_QIANFAN_COOKIES") or "").strip()
    if not cookies:
        return {
            "ok": False,
            "mode": mode,
            "platform": PLATFORM,
            "error": "XHS_QIANFAN_COOKIES is required when QIANFAN_MODE=spider_xhs",
        }
    return {"ok": True, "mode": mode, "platform": PLATFORM}


_MOCK_PRODUCTS = [
    {
        "product_id": "mock_prod_001",
        "name": "智能辅食机",
        "category": "母婴小家电",
        "price_range": "¥299-599",
        "selling_points": ["一键蒸煮搅拌", "定时预约", "多档调速", "易清洗"],
        "shop_name": "母婴优选旗舰店",
    },
    {
        "product_id": "mock_prod_002",
        "name": "宝宝餐椅",
        "category": "母婴用品",
        "price_range": "¥159-399",
        "selling_points": ["可折叠收纳", "多档高度调节", "安全绑带", "易擦洗材质"],
        "shop_name": "嘉也母婴官方店",
    },
    {
        "product_id": "mock_prod_003",
        "name": "婴儿指甲剪套装",
        "category": "母婴护理",
        "price_range": "¥29-89",
        "selling_points": ["圆头防夹肉", "LED照明", "静音设计", "新生儿可用"],
        "shop_name": "贝亲官方旗舰店",
    },
]


def search_product(keyword: str, limit: int = 3) -> list[dict]:
    mode = _mode()
    _validate_mode(mode)

    clean_keyword = str(keyword or "").strip()
    if not clean_keyword:
        raise ValueError("keyword is required")

    if mode == "mock":
        results = []
        for product in _MOCK_PRODUCTS:
            name = product.get("name") or ""
            selling_text = " ".join(product.get("selling_points") or [])
            if clean_keyword in name or any(
                char in name for char in clean_keyword if len(char) > 1
            ):
                results.append(dict(product))
        return results[:max(1, int(limit))] if results else [_MOCK_PRODUCT[0]][:max(1, int(limit))]

    # Real mode would call Spider_XHS Qianfan API
    return []


def get_product_detail(product_id: str) -> dict:
    mode = _mode()
    _validate_mode(mode)

    clean_id = str(product_id or "").strip()
    if not clean_id:
        raise ValueError("product_id is required")

    if mode == "mock":
        for product in _MOCK_PRODUCTS:
            if product.get("product_id") == clean_id:
                return dict(product)
        raise ValueError(f"Product not found: {clean_id}")

    # Real mode would call Spider_XHS Qianfan API
    return {}
```

- [ ] **Step 4: 运行测试确认 PASS**

```bash
cd "D:\codex\project\小红书内容分享\实施\xhs-agent" && D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_qianfan_mock.py -v
```

预期：全部 PASS（6 passed）

- [ ] **Step 5: 提交**

```bash
git add platforms/qianfan.py tests/test_qianfan_mock.py
git commit -m "feat: add qianfan mock platform adapter"
```

---

### Task 4: 蒲公英 mock adapter

**Files:**
- Create: `platforms/pugongying.py`
- Create: `tests/test_pugongying_mock.py`

- [ ] **Step 1: 写测试文件**

创建 `tests/test_pugongying_mock.py`：

```python
"""Test Pugongying platform adapter."""
from __future__ import annotations

import pytest
from platforms import pugongying


def test_search_darwin_returns_list():
    result = pugongying.search_darwin("婴儿辅食")
    assert isinstance(result, list)
    assert len(result) >= 1
    for item in result:
        assert isinstance(item, dict)
        assert "darwin_id" in item
        assert "nickname" in item
        assert "fans_level" in item
        assert "content_tags" in item
        assert "price_range" in item


def test_search_darwin_empty_keyword_raises():
    with pytest.raises(ValueError):
        pugongying.search_darwin("")


def test_get_darwin_detail_returns_dict():
    result = pugongying.get_darwin_detail("mock_darwin_001")
    assert isinstance(result, dict)
    assert result["darwin_id"] == "mock_darwin_001"


def test_get_darwin_detail_invalid_id_raises():
    with pytest.raises(ValueError):
        pugongying.get_darwin_detail("")


def test_send_invite_returns_mock_result():
    result = pugongying.send_invite("mock_darwin_001", "合作邀约测试")
    assert result["ok"] is True
    assert "invite_id" in result


def test_send_invite_empty_id_raises():
    with pytest.raises(ValueError):
        pugongying.send_invite("", "测试")


def test_check_pugongying_runtime_mock_ok():
    result = pugongying.check_pugongying_runtime()
    assert result["ok"] is True
    assert result["mode"] == "mock"
```

- [ ] **Step 2: 运行测试，确认 FAIL**

```bash
cd "D:\codex\project\小红书内容分享\实施\xhs-agent" && D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_pugongying_mock.py -v
```

预期：全部 FAIL（ModuleNotFoundError）

- [ ] **Step 3: 创建 platforms/pugongying.py**

```python
"""Pugongying (蒲公英) platform adapter for KOL/darwin matching.

Follows the same mock/real pattern as platforms/creators.py.
Stage 2 (M6) uses this for KOL matching and invite in soft-ad workflow.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")

PLATFORM = "pugongying"


def _mode() -> str:
    return os.getenv("PUGONGYING_MODE", "mock").strip().lower() or "mock"


def _validate_mode(mode: str) -> None:
    if mode not in {"mock", "spider_xhs"}:
        raise ValueError(f"Unsupported PUGONGYING_MODE: {mode}")


def check_pugongying_runtime() -> dict:
    mode = _mode()
    try:
        _validate_mode(mode)
    except ValueError as exc:
        return {"ok": False, "mode": mode, "platform": PLATFORM, "error": str(exc)}

    if mode == "mock":
        return {"ok": True, "mode": mode, "platform": PLATFORM}

    cookies = (os.getenv("XHS_PUGONGYING_COOKIES") or "").strip()
    if not cookies:
        return {
            "ok": False,
            "mode": mode,
            "platform": PLATFORM,
            "error": "XHS_PUGONGYING_COOKIES is required when PUGONGYING_MODE=spider_xhs",
        }
    return {"ok": True, "mode": mode, "platform": PLATFORM}


_MOCK_DARWINS = [
    {
        "darwin_id": "mock_darwin_001",
        "nickname": "樱桃妈妈育儿记",
        "fans_level": "10w-50w",
        "content_tags": ["母婴", "辅食", "育儿好物"],
        "price_range": "¥3000-8000/条",
        "notes_count": 320,
        "avg_interaction": 1500,
    },
    {
        "darwin_id": "mock_darwin_002",
        "nickname": "小明爸爸爱带娃",
        "fans_level": "5w-10w",
        "content_tags": ["母婴", "亲子", "宝宝成长"],
        "price_range": "¥1500-4000/条",
        "notes_count": 180,
        "avg_interaction": 800,
    },
    {
        "darwin_id": "mock_darwin_003",
        "nickname": "营养师Lily",
        "fans_level": "10w-50w",
        "content_tags": ["辅食营养", "科学育儿", "好物评测"],
        "price_range": "¥5000-12000/条",
        "notes_count": 450,
        "avg_interaction": 2200,
    },
    {
        "darwin_id": "mock_darwin_004",
        "nickname": "新手妈妈成长手册",
        "fans_level": "1w-5w",
        "content_tags": ["母婴", "新手妈妈", "好物推荐"],
        "price_range": "¥500-1500/条",
        "notes_count": 95,
        "avg_interaction": 400,
    },
    {
        "darwin_id": "mock_darwin_005",
        "nickname": "学姐育儿笔记",
        "fans_level": "5w-10w",
        "content_tags": ["育儿知识", "母婴好物", "经验分享"],
        "price_range": "¥2000-5000/条",
        "notes_count": 210,
        "avg_interaction": 1200,
    },
]


def search_darwin(topic: str, limit: int = 5) -> list[dict]:
    mode = _mode()
    _validate_mode(mode)

    clean_topic = str(topic or "").strip()
    if not clean_topic:
        raise ValueError("topic is required")

    if mode == "mock":
        results = []
        for darwin in _MOCK_DARWINS:
            tags_text = " ".join(darwin.get("content_tags") or [])
            nickname = darwin.get("nickname") or ""
            if any(char in tags_text or char in nickname for char in clean_topic if len(char) > 1):
                results.append(dict(darwin))
        if not results:
            results = [dict(_MOCK_DARWINS[0])]
        return results[:max(1, int(limit))]

    return []


def get_darwin_detail(darwin_id: str) -> dict:
    mode = _mode()
    _validate_mode(mode)

    clean_id = str(darwin_id or "").strip()
    if not clean_id:
        raise ValueError("darwin_id is required")

    if mode == "mock":
        for darwin in _MOCK_DARWINS:
            if darwin.get("darwin_id") == clean_id:
                return dict(darwin)
        raise ValueError(f"Darwin not found: {clean_id}")

    return {}


def send_invite(darwin_id: str, message: str = "") -> dict:
    mode = _mode()
    _validate_mode(mode)

    clean_id = str(darwin_id or "").strip()
    if not clean_id:
        raise ValueError("darwin_id is required")

    if mode == "mock":
        digest = hashlib.sha1(f"{clean_id}:{message}".encode("utf-8")).hexdigest()[:12]
        return {
            "ok": True,
            "mode": "mock",
            "platform": PLATFORM,
            "invite_id": f"mock_invite_{digest}",
            "darwin_id": clean_id,
            "message_sent": bool(str(message or "").strip()),
        }

    return {"ok": False, "error": "Real pugongying not implemented"}
```

- [ ] **Step 4: 运行测试确认 PASS**

```bash
cd "D:\codex\project\小红书内容分享\实施\xhs-agent" && D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_pugongying_mock.py -v
```

预期：全部 PASS（7 passed）

- [ ] **Step 5: 提交**

```bash
git add platforms/pugongying.py tests/test_pugongying_mock.py
git commit -m "feat: add pugongying mock platform adapter"
```

---

### Task 5: product_node — 商品选择节点

**Files:**
- Create: `nodes/product_node.py`
- Create: `tests/test_product_node.py`

- [ ] **Step 1: 写测试文件**

创建 `tests/test_product_node.py`：

```python
"""Test product_node for M6 stage 2."""
from __future__ import annotations

import pytest
from nodes.product_node import select_product


def test_select_product_basic(monkeypatch):
    monkeypatch.setattr(
        "nodes.product_node.search_product",
        lambda keyword, limit=3: [
            {
                "product_id": "mock_prod_001",
                "name": "智能辅食机",
                "price_range": "¥299-599",
                "selling_points": ["一键蒸煮搅拌", "定时预约"],
            }
        ]
    )

    result = select_product({
        "user_topic": "宝宝辅食",
        "user_product_name": "辅食机",
        "user_product_selling_points": "一键操作，省时间",
        "pain_points": [
            {"pain": "做辅食太费时间", "evidence": "评论多次提到时间不够", "priority": 1}
        ],
    })

    assert isinstance(result.get("product_info"), dict)
    assert result["product_info"]["product_id"] == "mock_prod_001"
    assert len(result.get("product_selling_points") or []) > 0
    assert len(result.get("product_pain_match") or []) > 0


def test_select_product_missing_name_raises():
    with pytest.raises(ValueError, match="user_product_name"):
        select_product({
            "user_topic": "宝宝辅食",
            "user_product_name": "",
            "user_product_selling_points": "",
            "pain_points": [],
        })


def test_select_product_only_name_no_selling_points(monkeypatch):
    monkeypatch.setattr(
        "nodes.product_node.search_product",
        lambda keyword, limit=3: [
            {
                "product_id": "mock_prod_002",
                "name": "宝宝餐椅",
                "price_range": "¥159-399",
                "selling_points": ["可折叠", "多档调节"],
            }
        ]
    )

    result = select_product({
        "user_topic": "宝宝餐椅",
        "user_product_name": "宝宝餐椅",
        "user_product_selling_points": "",
        "pain_points": [],
    })

    assert result["product_info"]["product_id"] == "mock_prod_002"
    assert result["product_selling_points"] == ["可折叠", "多档调节"]


def test_product_pain_match_scoring(monkeypatch):
    monkeypatch.setattr(
        "nodes.product_node.search_product",
        lambda keyword, limit=3: [
            {
                "product_id": "mock_prod_001",
                "name": "辅食机",
                "price_range": "¥299-599",
                "selling_points": ["一键操作", "省时省力", "多档调速"],
            }
        ]
    )

    result = select_product({
        "user_topic": "宝宝辅食",
        "user_product_name": "辅食机",
        "user_product_selling_points": "",
        "pain_points": [
            {"pain": "做辅食太费时间", "evidence": "时间不够", "priority": 1},
            {"pain": "不知道该买哪种工具", "evidence": "选择困难", "priority": 2},
        ],
    })

    matches = result.get("product_pain_match") or []
    assert len(matches) > 0
    for match in matches:
        assert "pain" in match
        assert "selling_point" in match
        assert "score" in match
```

- [ ] **Step 2: 运行测试，确认 FAIL**

```bash
cd "D:\codex\project\小红书内容分享\实施\xhs-agent" && D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_product_node.py -v
```

预期：全部 FAIL

- [ ] **Step 3: 创建 nodes/product_node.py**

```python
"""Product selection node for stage 2 soft-ad workflow.

Reads user-provided product info, calls Qianfan mock adapter for product search,
and matches product selling points to user pain points.
"""

from __future__ import annotations

from app.state import XHSState
from platforms.qianfan import search_product


def _pain_texts(pain_points: list) -> list[str]:
    texts = []
    for item in (pain_points or []):
        if isinstance(item, dict):
            pain = str(item.get("pain") or "").strip()
            if pain:
                texts.append(pain)
        elif isinstance(item, str):
            text = item.strip()
            if text:
                texts.append(text)
    return texts


def _match_pain_to_selling_points(
    pain_points: list,
    selling_points: list[str],
) -> list[dict]:
    pains = _pain_texts(pain_points)
    matches = []
    for pain in pains:
        for sp in selling_points:
            score = 0
            # Simple keyword overlap scoring
            pain_chars = set(pain)
            sp_chars = set(sp)
            common = pain_chars & sp_chars
            if common:
                score = len(common)
            # Bonus for substring match
            if any(word in pain for word in sp[:2]) or any(word in sp for word in pain[:2]):
                score += 3
            if score > 0:
                matches.append({
                    "pain": pain,
                    "selling_point": sp,
                    "score": score,
                })
    matches.sort(key=lambda m: m["score"], reverse=True)
    return matches[:10]


def select_product(state: XHSState) -> dict:
    product_name = str(state.get("user_product_name") or "").strip()
    if not product_name:
        raise ValueError(
            "user_product_name is required for soft_ad content. "
            "Please provide a product name in the input."
        )

    user_selling = str(state.get("user_product_selling_points") or "").strip()
    topic = str(state.get("user_topic") or "")

    # Search via Qianfan
    search_results = search_product(product_name, limit=3)
    if not search_results:
        raise ValueError(f"No products found for: {product_name}")

    # Use the best-matching product
    product = search_results[0]
    selling_points = list(product.get("selling_points") or [])

    # Merge user-provided selling points
    if user_selling:
        selling_points.insert(0, user_selling)

    product_info = {
        "product_id": product.get("product_id"),
        "name": product.get("name"),
        "category": product.get("category"),
        "price_range": product.get("price_range"),
        "shop_name": product.get("shop_name"),
        "source": "qianfan_mock",
    }

    pain_points = state.get("pain_points") or []
    pain_match = _match_pain_to_selling_points(pain_points, selling_points)

    return {
        "product_info": product_info,
        "product_selling_points": selling_points,
        "product_pain_match": pain_match,
    }
```

- [ ] **Step 4: 运行测试确认 PASS**

```bash
cd "D:\codex\project\小红书内容分享\实施\xhs-agent" && D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_product_node.py -v
```

预期：全部 PASS（4 passed）

- [ ] **Step 5: 提交**

```bash
git add nodes/product_node.py tests/test_product_node.py
git commit -m "feat: add product_node for stage 2 product selection"
```

---

### Task 6: content_structures.json — 新增 soft_ad 结构模板

**Files:**
- Modify: `config/content_structures.json`

- [ ] **Step 1: 更新顶层 valid_content_types + 新增 soft_ad 结构模板**

**修改之一**：在顶层 `"valid_content_types"` 数组中新增 `"soft_ad"`。当前文件开头：

```json
{
  "valid_content_types": ["knowledge_share", "experience_summary", "avoid_mistakes", "qa_education", "step_tutorial"],
  "default_content_type": "knowledge_share",
```

改为：

```json
{
  "valid_content_types": ["knowledge_share", "experience_summary", "avoid_mistakes", "qa_education", "step_tutorial", "soft_ad"],
  "default_content_type": "knowledge_share",
```

**修改之二**：在 `structure_profiles` 对象末尾（`"experience_summary"` 闭合 `}` 之后）新增：

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
      "soft_ad_heading": "我用到的一个东西帮了大忙：",
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

注意：确保在 `experience_summary` 的 `}` 之后加逗号，然后在末尾的 `}` 之前插入上述内容。

- [ ] **Step 2: 验证 — structure_profiles 加载正常**

```bash
cd "D:\codex\project\小红书内容分享\实施\xhs-agent" && D:\Anaconda\envs\ContentShare\python.exe -c "from app.rules import load_content_rules; rules = load_content_rules(); profiles = rules.get('structure_profiles', {}); assert 'soft_ad' in profiles; print('soft_ad profile loaded:', profiles['soft_ad']['label'])"
```

预期：`soft_ad profile loaded: 好物分享`

- [ ] **Step 3: 提交**

```bash
git add config/content_structures.json
git commit -m "feat: add soft_ad structure profile"
```

---

### Task 7: 软广 LLM prompt — 在 llm_prompts.json 中新增

**Files:**
- Modify: `config/llm_prompts.json`

- [ ] **Step 1: 新增 soft_ad_generation prompt**

在 `config/llm_prompts.json` 文件末尾（`"operation_review"` 对象闭合 `}` 之后）新增：

```json
  "soft_ad_generation": {
    "system": "你是小红书好物分享内容生成助手。核心原则：先讲清问题，再说产品思路，最后提醒理性判断。必须输出合法 JSON，不要 Markdown，不要代码块。内容必须自然植入，不能硬广。必须包含广告/合作标识。不能夸大产品功效，不能承诺具体效果，不能制造焦虑。不能虚构个人经历或使用效果。涉及产品的表述必须是'提供一个思路/工具'，不是'解决方案'。不要承诺爆款、必火、暴涨、快速涨粉；可以表达为可验证方向、高反馈方向、持续迭代。",
    "user_template": "请根据下面输入生成一篇小红书好物分享笔记草稿。必须严格输出 JSON，字段必须与 expected_json 一致。\n\nexpected_json:\n{expected_json}\n\ninput:\n{input_payload}",
    "expected_json": {
      "titles": ["标题1", "标题2", "标题3"],
      "cover_texts": ["封面主标题", "封面副标题", "收藏提示"],
      "body": "正文内容，允许分段，但必须是字符串。先讲用户痛点，再自然引入产品作为解决思路，最后提醒理性判断。必须包含广告/合作标识。",
      "image_page_plan": [
        {"page": 1, "title": "先讲问题", "text": "展示评论里的真实困惑"},
        {"page": 2, "title": "产品思路", "text": "我是怎么用这个东西来帮自己理清楚的"},
        {"page": 3, "title": "理性提醒", "text": "别盲买，先判断是否适合自己"}
      ],
      "image_prompts": ["配图提示词1", "配图提示词2"],
      "tags": ["标签1", "标签2", "标签3"],
      "comment_call": "评论区引导语，邀请读者说出自己的具体问题",
      "ad_disclaimer": "本内容包含商业合作信息，请理性种草。"
    }
  }
```

注意：确保在 `"operation_review"` 块的 `}` 之后加逗号。

- [ ] **Step 2: 验证 — prompt 加载正常**

```bash
cd "D:\codex\project\小红书内容分享\实施\xhs-agent" && D:\Anaconda\envs\ContentShare\python.exe -c "from llm.prompts import get_prompt_template; t = get_prompt_template('soft_ad_generation'); print('loaded:', t['system'][:30])"
```

预期：`loaded: 你是小红书好物分享内容生成助手。核`

- [ ] **Step 3: 提交**

```bash
git add config/llm_prompts.json
git commit -m "feat: add soft_ad_generation llm prompt template"
```

---

### Task 8: soft_ad_node — 软广内容生成

**Files:**
- Create: `nodes/soft_ad_node.py`
- Create: `tests/test_soft_ad_node.py`

- [ ] **Step 1: 写测试文件**

创建 `tests/test_soft_ad_node.py`：

```python
"""Test soft_ad_node for M6 stage 2."""
from __future__ import annotations

import pytest
from nodes.soft_ad_node import generate_soft_ad


class _MockLLMResponse:
    def __init__(self, content: str):
        self.content = content
        self.provider_mode = "mock"
        self.model = "mock"
        self.usage = {}


class _MockClient:
    is_mock = False
    def chat(self, messages, temperature=0.3, max_tokens=1200, response_format=None):
        import json
        return _MockLLMResponse(json.dumps({
            "titles": ["辅食机的好物分享", "做辅食不累的小工具"],
            "cover_texts": ["辅食机好物思路", "先看清楚再决定", "收藏防丢"],
            "body": "这篇先讲问题，再讲产品思路，最后提醒理性判断。",
            "image_page_plan": [
                {"page": 1, "title": "先讲问题", "text": "评论里的困惑"},
                {"page": 2, "title": "产品思路", "text": "辅食机帮了大忙"},
                {"page": 3, "title": "理性提醒", "text": "别盲买"}
            ],
            "image_prompts": ["辅食机配图"],
            "tags": ["辅食机", "好物分享", "理性种草"],
            "comment_call": "你有什么具体问题？评论区告诉我",
            "ad_disclaimer": "本内容包含商业合作信息，请理性种草。"
        }))


def test_generate_soft_ad_llm_mode(monkeypatch):
    monkeypatch.setattr("nodes.soft_ad_node.get_llm_client", lambda: _MockClient())

    state = {
        "user_topic": "宝宝辅食机",
        "target_user": "新手妈妈",
        "content_type": "soft_ad",
        "pain_points": [{"pain": "做辅食太费时间", "evidence": "时间不够", "priority": 1}],
        "comment_insights": [{"pain": "不知道买哪个", "evidence_comments": ["不知道怎么选"]}],
        "product_info": {
            "product_id": "mock_prod_001",
            "name": "智能辅食机",
            "price_range": "¥299-599",
        },
        "product_selling_points": ["一键操作", "省时间", "多档调速"],
        "product_pain_match": [
            {"pain": "做辅食太费时间", "selling_point": "一键操作", "score": 5}
        ],
        "graphrag_memory": {},
    }

    result = generate_soft_ad(state)

    assert len(result.get("titles") or []) >= 2
    assert len(result.get("cover_texts") or []) >= 2
    assert isinstance(result.get("body"), str) and len(result["body"]) > 0
    assert len(result.get("image_page_plan") or []) >= 3
    assert len(result.get("image_prompts") or []) >= 1
    assert len(result.get("tags") or []) >= 3
    assert isinstance(result.get("comment_call"), str)
    assert result.get("content_type") == "soft_ad"
    assert result["llm_generation"]["enabled"] is True


def test_generate_soft_ad_template_fallback(monkeypatch):
    class _FailingClient:
        is_mock = False
        def chat(self, *args, **kwargs):
            from llm.client import LLMError
            raise LLMError("LLM unavailable")

    monkeypatch.setattr("nodes.soft_ad_node.get_llm_client", lambda: _FailingClient())

    state = {
        "user_topic": "宝宝辅食",
        "target_user": "新手妈妈",
        "content_type": "soft_ad",
        "pain_points": [{"pain": "做辅食太费时间", "evidence": "时间不够", "priority": 1}],
        "comment_insights": [],
        "product_info": {"name": "辅食机", "product_id": "mock_prod_001"},
        "product_selling_points": ["一键操作"],
        "product_pain_match": [],
        "graphrag_memory": {},
    }

    result = generate_soft_ad(state)

    # Template fallback should still produce required fields
    assert len(result.get("titles") or []) >= 1
    assert isinstance(result.get("body"), str) and len(result["body"]) > 0
    assert isinstance(result.get("tags"), list)
    assert result["llm_generation"]["enabled"] is False
    assert result["llm_generation"]["provider_mode"] == "fallback_template"


def test_generate_soft_ad_includes_ad_disclaimer(monkeypatch):
    monkeypatch.setattr("nodes.soft_ad_node.get_llm_client", lambda: _MockClient())

    state = {
        "user_topic": "宝宝辅食",
        "target_user": "新手妈妈",
        "content_type": "soft_ad",
        "pain_points": [],
        "comment_insights": [],
        "product_info": {"name": "辅食机", "product_id": "mock_prod_001"},
        "product_selling_points": ["一键操作"],
        "product_pain_match": [],
        "graphrag_memory": {},
    }

    result = generate_soft_ad(state)
    body = str(result.get("body") or "").lower()
    # Body should include ad disclaimer or related text
    assert len(body) > 0
```

- [ ] **Step 2: 运行测试，确认 FAIL**

```bash
cd "D:\codex\project\小红书内容分享\实施\xhs-agent" && D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_soft_ad_node.py -v
```

预期：全部 FAIL

- [ ] **Step 3: 创建 nodes/soft_ad_node.py**

```python
"""Soft-ad content generation node for stage 2.

Follows the same LLM-first + template-fallback pattern as content_node.py.
Generates image-text content that naturally embeds product information with
compliance disclaimers.
"""

from __future__ import annotations

import json
from typing import Any

from app.rules import load_content_rules, load_text_replacement_rules
from app.state import XHSState
from llm.client import LLMError, get_llm_client
from llm.prompts import build_json_prompt
from nodes.compliance_node import ABSOLUTE_WORDS, AVOID_PROMISE_WORDS
from nodes.memory_context import build_generation_memory_context


_CONTENT_RULES = load_content_rules()
_STRUCTURE_PROFILES = _CONTENT_RULES.get("structure_profiles") or {}
_SOFT_AD_PROFILE = _STRUCTURE_PROFILES.get("soft_ad") or {}

_TEXT_REPLACEMENT_RULES = load_text_replacement_rules()
_PHRASE_REPLACEMENTS = dict(_TEXT_REPLACEMENT_RULES.get("phrase_replacements") or {})

REQUIRED_FIELDS = {
    "titles": list,
    "cover_texts": list,
    "body": str,
    "image_page_plan": list,
    "image_prompts": list,
    "tags": list,
    "comment_call": str,
    "ad_disclaimer": str,
}


def _format_pain_points(state: XHSState) -> list[str]:
    pain_points = state.get("pain_points") or []
    if not isinstance(pain_points, list):
        return [str(pain_points)]
    result = []
    for item in pain_points:
        if isinstance(item, dict):
            text = str(item.get("pain", ""))
        else:
            text = str(item)
        if text.strip():
            result.append(text.strip())
    return result


def _format_comment_insights(state: XHSState) -> list[dict]:
    insights = state.get("comment_insights") or []
    if not isinstance(insights, list):
        return []
    result = []
    for item in insights:
        if not isinstance(item, dict):
            continue
        pain = str(item.get("pain") or "").strip()
        evidence_comments = item.get("evidence_comments") or []
        if not isinstance(evidence_comments, list):
            evidence_comments = []
        evidence_comments = [str(c).strip() for c in evidence_comments if str(c).strip()]
        if pain:
            result.append({"pain": pain, "evidence_comments": evidence_comments})
    return result


def _normalize_string_list(value: Any, min_items: int = 1) -> list[str]:
    if not isinstance(value, list):
        raise ValueError("expected list")
    result = [str(item).strip() for item in value if str(item).strip()]
    if len(result) < min_items:
        raise ValueError("list has too few items")
    return result


def _normalize_page_plan(value: Any) -> list[dict]:
    if not isinstance(value, list):
        raise ValueError("image_page_plan must be a list")
    pages = []
    for index, item in enumerate(value, start=1):
        if not isinstance(item, dict):
            raise ValueError("image_page_plan item must be object")
        title = str(item.get("title") or "").strip()
        text = str(item.get("text") or "").strip()
        if not title or not text:
            raise ValueError("image_page_plan item missing title/text")
        pages.append({
            "page": int(item.get("page") or index),
            "title": title,
            "text": text,
        })
    if len(pages) < 3:
        raise ValueError("image_page_plan has too few pages")
    return pages


def _validate_soft_ad_result(data: Any) -> dict:
    if not isinstance(data, dict):
        raise ValueError("LLM JSON root must be an object")

    for field, expected_type in REQUIRED_FIELDS.items():
        if field not in data:
            raise ValueError(f"missing field: {field}")
        if not isinstance(data[field], expected_type):
            raise ValueError(f"invalid field type: {field}")

    return {
        "titles": _normalize_string_list(data["titles"], min_items=2)[:5],
        "cover_texts": _normalize_string_list(data["cover_texts"], min_items=2)[:4],
        "body": str(data["body"]).strip(),
        "image_page_plan": _normalize_page_plan(data["image_page_plan"])[:6],
        "image_prompts": _normalize_string_list(data["image_prompts"], min_items=1)[:4],
        "tags": _normalize_string_list(data["tags"], min_items=3)[:10],
        "comment_call": str(data["comment_call"]).strip(),
        "ad_disclaimer": str(data.get("ad_disclaimer") or _SOFT_AD_PROFILE.get("ad_disclaimer", "")).strip(),
    }


def _build_soft_ad_prompt(state: XHSState) -> list:
    topic = state["user_topic"]
    target_user = state.get("target_user") or "小红书目标用户"
    pain_points = _format_pain_points(state)
    comment_insights = _format_comment_insights(state)
    product_info = state.get("product_info") or {}
    selling_points = state.get("product_selling_points") or []
    pain_match = state.get("product_pain_match") or []
    primary_pain = pain_points[0] if pain_points else topic

    input_payload = {
        "topic": topic,
        "target_user": target_user,
        "content_type": "soft_ad",
        "content_label": _SOFT_AD_PROFILE.get("label", "好物分享"),
        "primary_pain": primary_pain,
        "comment_insights": comment_insights[:5],
        "pain_points": pain_points[:5],
        "product_name": product_info.get("name", ""),
        "product_selling_points": selling_points,
        "product_pain_match": pain_match[:5],
        "memory_context": build_generation_memory_context(state),
        "preferred_structure": {
            "label": _SOFT_AD_PROFILE.get("label"),
            "body_heading": _SOFT_AD_PROFILE.get("body_heading"),
            "soft_ad_heading": _SOFT_AD_PROFILE.get("soft_ad_heading"),
            "action_heading": _SOFT_AD_PROFILE.get("action_heading"),
            "action_steps": _SOFT_AD_PROFILE.get("action_steps"),
            "page_titles": _SOFT_AD_PROFILE.get("page_titles"),
            "ad_disclaimer": _SOFT_AD_PROFILE.get("ad_disclaimer"),
        },
        "forbidden_words": ABSOLUTE_WORDS,
        "avoid_promise_words": AVOID_PROMISE_WORDS,
    }

    return build_json_prompt("soft_ad_generation", input_payload)


def _llm_generate_soft_ad(state: XHSState) -> dict:
    client = get_llm_client()
    if client.is_mock:
        raise LLMError("LLM is in mock mode")

    response = client.chat(
        messages=_build_soft_ad_prompt(state),
        temperature=0.4,
        max_tokens=5000,
        response_format={"type": "json_object"},
    )
    data = json.loads(response.content)
    result = _validate_soft_ad_result(data)
    result["content_type"] = "soft_ad"
    result["llm_generation"] = {
        "enabled": True,
        "provider_mode": response.provider_mode,
        "model": response.model,
        "usage": response.usage,
    }
    return result


def _template_generate_soft_ad(state: XHSState) -> dict:
    topic = state["user_topic"]
    target_user = state.get("target_user") or "小红书目标用户"
    pain_points = _format_pain_points(state)
    comment_insights = _format_comment_insights(state)
    product_info = state.get("product_info") or {}
    product_name = product_info.get("name") or state.get("user_product_name") or "这个产品"
    selling_points = state.get("product_selling_points") or []
    primary_pain = (
        comment_insights[0]["pain"] if comment_insights
        else (pain_points[0] if pain_points else topic)
    )

    titles = [
        f"{topic}用到的一个好东西，先讲清楚再决定要不要试",
        f"关于{topic}，我最近试了一个思路：{product_name}",
        f"{primary_pain}，后来发现可以这样解决",
    ]

    cover_texts = [
        f"{topic}好物思路",
        "先看清楚再决定",
        "别盲买，先往下看",
    ]

    body_lines = [
        f"这篇笔记适合：{target_user}",
        "",
        f"今天聊的是：{topic}",
        "",
        "评论里最集中的问题是：",
    ]

    if comment_insights:
        for index, insight in enumerate(comment_insights[:3], start=1):
            body_lines.append(f"{index}. {insight['pain']}")
    elif pain_points:
        for index, pain in enumerate(pain_points[:3], start=1):
            body_lines.append(f"{index}. {pain}")

    body_lines.extend([
        "",
        f"我用到的一个东西帮了大忙：{product_name}",
        "",
        f"它是怎么帮到我的：{selling_points[0] if selling_points else '解决了我一直在纠结的问题'}",
        "",
        "建议你先按下面顺序判断：",
        "1. 先看自己的具体场景和问题是否对得上。",
        "2. 再去了解这个产品具体能做什么、不能做什么。",
        "3. 最后决定要不要试，不要因为种草盲买。",
        "",
        "本内容包含商业合作信息，请理性种草。",
    ])

    image_page_plan = [
        {"page": 1, "title": f"{topic}：先讲问题", "text": "评论里的真实困惑"},
        {"page": 2, "title": "产品思路", "text": f"{product_name}帮了大忙"},
        {"page": 3, "title": "理性提醒", "text": "别盲买，先判断"},
    ]

    return {
        "content_type": "soft_ad",
        "titles": titles,
        "cover_texts": cover_texts,
        "body": "\n".join(body_lines),
        "image_page_plan": image_page_plan,
        "image_prompts": [f"{topic}好物分享封面，干净清爽", "产品使用场景图"],
        "tags": [topic, "好物分享", "理性种草", product_name],
        "comment_call": f"你在{topic}上最纠结的是哪一步？评论区告诉我。",
        "ad_disclaimer": "本内容包含商业合作信息，请理性种草。",
        "llm_generation": {
            "enabled": False,
            "provider_mode": "template",
            "model": None,
            "usage": {},
        },
    }


def generate_soft_ad(state: XHSState) -> dict:
    try:
        return _llm_generate_soft_ad(state)
    except (LLMError, ValueError, json.JSONDecodeError) as exc:
        fallback = _template_generate_soft_ad(state)
        fallback["llm_generation"] = {
            "enabled": False,
            "provider_mode": "fallback_template",
            "model": None,
            "usage": {},
            "error": str(exc),
        }
        return fallback
```

- [ ] **Step 4: 运行测试确认 PASS**

```bash
cd "D:\codex\project\小红书内容分享\实施\xhs-agent" && D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_soft_ad_node.py -v
```

预期：全部 PASS（3 passed）

- [ ] **Step 5: 提交**

```bash
git add nodes/soft_ad_node.py tests/test_soft_ad_node.py
git commit -m "feat: add soft_ad_node with LLM+template generation"
```

---

### Task 9: frequency guardrails — operation_store 查询 + strategy_node 集成

**Files:**
- Modify: `memory/operation_store.py`
- Modify: `nodes/strategy_node.py`

- [ ] **Step 1: 在 operation_store.py 中新增查询函数**

在 `memory/operation_store.py` 中 `find_successful_patterns` 函数之后（约 553 行附近）新增：

```python
def find_soft_ad_records_this_week(path: Path | None = None) -> list[dict[str, Any]]:
    """Return soft_ad records published within the last 7 days, most recent first."""
    from datetime import datetime as dt, timedelta

    history = load_history(path)
    cutoff = (dt.now() - timedelta(days=7)).isoformat(timespec="seconds")

    matches = []
    for record in history.get("records") or []:
        if not isinstance(record, dict):
            continue
        if record.get("content_type") != "soft_ad":
            continue
        created_at = str(record.get("created_at") or record.get("publish_time") or "")
        if created_at and created_at < cutoff:
            continue
        matches.append(record)

    matches.sort(
        key=lambda r: str(r.get("created_at") or r.get("publish_time") or ""),
        reverse=True,
    )
    return matches
```

- [ ] **Step 2: 在 strategy_node.py 中新增频率护栏检查**

在 `nodes/strategy_node.py` 的 `decide_content_strategy` 函数中添加频率护栏 pre-check。在现有冷启动/软广拦截之后、返回之前：

修改 `decide_content_strategy` 函数：

```python
def decide_content_strategy(state: XHSState) -> dict:
    content_type = _choose_content_type(state)
    content_format = _choose_content_format(state)

    if state.get("account_stage", "cold_start") == "cold_start" and content_type == "soft_ad":
        content_type = DEFAULT_CONTENT_TYPE

    if not state.get("allow_soft_ad", False) and content_type == "soft_ad":
        content_type = DEFAULT_CONTENT_TYPE

    updates: dict = {
        "content_type": content_type,
        "content_format": content_format,
    }

    # Frequency guardrail pre-check for soft_ad
    if content_type == "soft_ad":
        freq_check = _check_soft_ad_frequency()
        updates["soft_ad_frequency_check"] = freq_check
        if not freq_check["allowed"]:
            updates["content_type"] = DEFAULT_CONTENT_TYPE

    return updates


def _check_soft_ad_frequency() -> dict:
    """Check soft-ad weekly limit and back-to-back rule from operation memory."""
    from memory.operation_store import find_soft_ad_records_this_week

    records = find_soft_ad_records_this_week()
    this_week_count = len(records)
    last_record = records[0] if records else None

    from app.rules import load_compliance_rules
    rules = load_compliance_rules().get("soft_ad_rules") or {}
    weekly_limit = int(rules.get("weekly_limit") or 2)
    no_back_to_back = bool(rules.get("no_back_to_back"))

    issues = []
    if this_week_count >= weekly_limit:
        issues.append(f"本周软广已达上限 {weekly_limit} 篇")
    if no_back_to_back and last_record:
        issues.append("不允许连发软广")

    return {
        "allowed": len(issues) == 0,
        "this_week_count": this_week_count,
        "weekly_limit": weekly_limit,
        "last_published_at": last_record.get("created_at") if last_record else None,
        "issues": issues,
    }
```

- [ ] **Step 3: 验证 — 编译和基本逻辑**

```bash
cd "D:\codex\project\小红书内容分享\实施\xhs-agent" && D:\Anaconda\envs\ContentShare\python.exe -c "from nodes.strategy_node import decide_content_strategy, _check_soft_ad_frequency; result = _check_soft_ad_frequency(); print('freq check:', result)"
```

预期：`freq check: {'allowed': True, 'this_week_count': 0, ...}`

- [ ] **Step 4: 运行现有测试确认无回归**

```bash
cd "D:\codex\project\小红书内容分享\实施\xhs-agent" && D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_strategy_memory_context.py tests/test_memory_node.py -v
```

预期：全部 PASS

- [ ] **Step 5: 提交**

```bash
git add memory/operation_store.py nodes/strategy_node.py
git commit -m "feat: add soft_ad frequency guardrails with operation memory stats"
```

---

### Task 10: stage_node 支持 stage_override

**Files:**
- Modify: `nodes/stage_node.py`

- [ ] **Step 1: 修改 check_account_stage**

编辑 `nodes/stage_node.py`：

```python
"""读取当前账号阶段 → 找到对应规则 → 写回 State"""
from app.state import XHSState
from app.config import load_settings, get_stage_rules


def check_account_stage(state: XHSState) -> dict:
    override = state.get("stage_override")
    if override in ("cold_start", "growth", "monetization_ready"):
        rules = get_stage_rules(override)
        return {
            "account_stage": rules["account_stage"],
            "allow_soft_ad": rules["allow_soft_ad"],
        }

    settings = load_settings()
    account_stage = state.get("account_stage") or settings.account_stage
    rules = get_stage_rules(account_stage)
    return {
        "account_stage": rules["account_stage"],
        "allow_soft_ad": rules["allow_soft_ad"],
    }
```

- [ ] **Step 2: 验证 — 编译检查**

```bash
cd "D:\codex\project\小红书内容分享\实施\xhs-agent" && D:\Anaconda\envs\ContentShare\python.exe -c "from nodes.stage_node import check_account_stage; r = check_account_stage({'stage_override': 'monetization_ready'}); assert r['account_stage'] == 'monetization_ready'; assert r['allow_soft_ad'] is True; print('stage_override ok'); r2 = check_account_stage({}); print('default stage:', r2)"
```

预期：`stage_override ok` + `default stage: {'account_stage': 'cold_start', 'allow_soft_ad': False}`

- [ ] **Step 3: 提交**

```bash
git add nodes/stage_node.py
git commit -m "feat: support stage_override in check_account_stage"
```

---

### Task 11: input_node 支持商品输入字段

**Files:**
- Modify: `nodes/input_node.py`

- [ ] **Step 1: 扩展 load_user_input**

编辑 `nodes/input_node.py`：

```python
"""目标：无论用户传进来的字段完整不完整，系统都补齐 M1 需要的默认值。"""
from app.state import XHSState


def load_user_input(state: XHSState) -> dict:
    user_topic = state.get("user_topic", "").strip()
    if not user_topic:
        raise ValueError("user_topic is required")
    target_user = state.get("target_user") or "小红书目标用户"
    user_selected_format = state.get("user_selected_format") or "image_text"
    user_goal = state.get("user_goal") or "生成一篇冷启动阶段的知识分享内容"
    if user_selected_format not in ("image_text", "video"):
        raise ValueError("user_selected_format must be image_text or video")

    updates: dict = {
        "user_topic": user_topic,
        "target_user": target_user,
        "user_selected_format": user_selected_format,
        "user_goal": user_goal,
    }

    # Stage 2: forward product info if provided
    product_name = str(state.get("user_product_name") or "").strip()
    if product_name:
        updates["user_product_name"] = product_name
        updates["user_product_selling_points"] = str(
            state.get("user_product_selling_points") or ""
        ).strip()

    return updates
```

- [ ] **Step 2: 验证 — 编译检查**

```bash
cd "D:\codex\project\小红书内容分享\实施\xhs-agent" && D:\Anaconda\envs\ContentShare\python.exe -c "from nodes.input_node import load_user_input; r = load_user_input({'user_topic': '辅食', 'user_product_name': '辅食机'}); assert r.get('user_product_name') == '辅食机'; print('input ok:', r)"
```

预期：`input ok: {...}`

- [ ] **Step 3: 提交**

```bash
git add nodes/input_node.py
git commit -m "feat: pass product input fields through input_node"
```

---

### Task 12: compliance_node 扩展软广专属规则

**Files:**
- Modify: `nodes/compliance_node.py`

- [ ] **Step 1: 扩展 check_compliance**

编辑 `nodes/compliance_node.py`，在现有 `check_compliance` 函数的 `issues` 收集完成后、返回之前，新增软广专属检查：

```python
def check_compliance(state: XHSState) -> dict:
    text = _content_text(state)
    issues = []

    if state.get("account_stage") == "cold_start" and state.get("content_type") == "soft_ad":
        issues.append("冷启动阶段禁止生成或发布软广内容")

    for word in ABSOLUTE_WORDS:
        if word in text:
            issues.append(f"内容中包含绝对词：{word}")

    has_sensitive_topic = any(word in text for word in SENSITIVE_TOPICS)
    has_disclaimer = any(word in text for word in DISCLAIMER_WORDS)

    if has_sensitive_topic and not has_disclaimer:
        issues.append("敏感主题缺少经验分享或风险提示")

    # --- Stage 2: soft_ad specific compliance ---
    if state.get("content_type") == "soft_ad":
        rules = _COMPLIANCE_RULES.get("soft_ad_rules") or {}

        # Check required disclaimers
        required = rules.get("required_disclaimers") or []
        found = [d for d in required if d in text]
        if not found:
            issues.append("软广内容缺少广告/合作标识")

        # Check forbidden soft-ad words
        forbidden = rules.get("forbidden_soft_ad_words") or []
        for word in forbidden:
            if word in text:
                issues.append(f"软广内容包含禁止词：{word}")

        # Check efficacy claims
        efficacy = rules.get("forbidden_efficacy_claims") or []
        for claim in efficacy:
            if claim in text:
                issues.append(f"软广内容包含功效承诺：{claim}")

        # Check frequency guardrail (from strategy pre-check)
        freq_check = state.get("soft_ad_frequency_check")
        if isinstance(freq_check, dict) and not freq_check.get("allowed"):
            for issue in freq_check.get("issues") or []:
                issues.append(f"频率护栏：{issue}")
    # --- End soft_ad compliance ---

    if not issues:
        risk_level = "low"
    elif any("禁止" in issue or "根治" in issue for issue in issues):
        risk_level = "high"
    else:
        risk_level = "medium"

    return {
        "compliance_risk_level": risk_level,
        "compliance_issues": issues,
        "revised_content": None,
    }
```

- [ ] **Step 2: 验证 — 编译和基本逻辑**

```bash
cd "D:\codex\project\小红书内容分享\实施\xhs-agent" && D:\Anaconda\envs\ContentShare\python.exe -c "from nodes.compliance_node import check_compliance; r = check_compliance({'content_type': 'soft_ad', 'body': '这个产品必买！用完就有效果。', 'account_stage': 'monetization_ready', 'soft_ad_frequency_check': {'allowed': True}}); print('issues:', r['compliance_issues'], 'risk:', r['compliance_risk_level'])"
```

预期：检测到"必买"禁止词和"用完就"功效承诺

- [ ] **Step 3: 提交**

```bash
git add nodes/compliance_node.py
git commit -m "feat: add soft_ad specific compliance checks"
```

---

### Task 13: CLI — 新增 --stage 参数

**Files:**
- Modify: `app/main.py`

- [ ] **Step 1: 扩展 CLI**

编辑 `app/main.py` 的 `build_parser()` 和 `main()`：

```python
def build_parser() -> ArgumentParser:
    parser = ArgumentParser(description="Run the local XHS content workflow.")
    parser.add_argument("--topic", required=True, help="用户输入的内容主题")
    parser.add_argument("--target-user", default="小红书目标用户", help="目标用户")
    parser.add_argument(
        "--format",
        choices=("image_text", "video"),
        default="image_text",
        dest="content_format",
        help="内容形式",
    )
    parser.add_argument("--goal", default="生成一篇冷启动阶段的知识分享内容", help="用户目标")
    parser.add_argument("--approve", action="store_true", help="模拟人工审核通过")
    parser.add_argument(
        "--engine", choices=("local", "langgraph"), default="langgraph", help="流程运行引擎"
    )
    parser.add_argument("--collect-limit", type=int, default=5, help="采集笔记数量上限")
    parser.add_argument("--save-collection", action="store_true", help="保存本次采集结果")
    parser.add_argument(
        "--stage",
        choices=("cold_start", "growth", "monetization_ready"),
        default=None,
        dest="stage_override",
        help="覆盖账号阶段（面试演示用）",
    )
    parser.add_argument("--product-name", default="", help="商品名称（阶段二软广用）")
    parser.add_argument(
        "--product-selling-points", default="", help="商品卖点描述（阶段二软广用）"
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    runner = run_langgraph if args.engine == "langgraph" else run_local_graph
    initial_state: dict = {
        "user_topic": args.topic,
        "target_user": args.target_user,
        "user_selected_format": args.content_format,
        "user_goal": args.goal,
        "human_approved": args.approve,
        "collect_limit": args.collect_limit,
        "save_collection": args.save_collection,
    }

    if args.stage_override:
        initial_state["stage_override"] = args.stage_override

    if args.product_name:
        initial_state["user_product_name"] = args.product_name
        initial_state["user_product_selling_points"] = args.product_selling_points

    final_state = runner(initial_state)

    # ... 其余 print 语句保持不变 ...
```

- [ ] **Step 2: 验证 — CLI help**

```bash
cd "D:\codex\project\小红书内容分享\实施\xhs-agent" && D:\Anaconda\envs\ContentShare\python.exe -m app.main --help
```

预期：看到 `--stage`、`--product-name`、`--product-selling-points` 参数

- [ ] **Step 3: 提交**

```bash
git add app/main.py
git commit -m "feat: add --stage and --product-* CLI arguments"
```

---

### Task 14: API 扩展 — stage_override + product fields

**Files:**
- Modify: `app/api.py`

- [ ] **Step 1: 扩展 _build_run_request 和 _initial_state_from_request**

编辑 `app/api.py`，在 `_build_run_request()` 函数中扩展 request_payload：

```python
def _build_run_request(payload: dict[str, Any]) -> dict[str, Any]:
    # ... 现有代码保持不变 ...
    request_payload = {
        "topic": topic,
        "target_user": str(payload.get("target_user") or "小红书目标用户"),
        "format": content_format,
        "goal": str(payload.get("goal") or "生成一篇冷启动阶段的知识分享内容"),
        "approve": approve,
        "engine": engine,
        "collect_limit": _int(payload.get("collect_limit"), default=5),
        "save_collection": _bool(payload.get("save_collection"), default=False),
        "stage_override": str(payload.get("stage_override") or "").strip() or None,
        "product_name": str(payload.get("product_name") or "").strip(),
        "product_selling_points": str(payload.get("product_selling_points") or "").strip(),
    }

    return request_payload
```

在 `_initial_state_from_request()` 中：

```python
def _initial_state_from_request(request_payload: dict[str, Any]) -> dict[str, Any]:
    initial = {
        "user_topic": request_payload["topic"],
        "target_user": request_payload["target_user"],
        "user_selected_format": request_payload["format"],
        "user_goal": request_payload["goal"],
        "human_approved": request_payload["approve"],
        "collect_limit": request_payload["collect_limit"],
        "save_collection": request_payload["save_collection"],
        "run_status": "queued",
    }

    stage_override = request_payload.get("stage_override")
    if stage_override and stage_override in ("cold_start", "growth", "monetization_ready"):
        initial["stage_override"] = stage_override

    product_name = str(request_payload.get("product_name") or "").strip()
    if product_name:
        initial["user_product_name"] = product_name
        initial["user_product_selling_points"] = str(
            request_payload.get("product_selling_points") or ""
        ).strip()

    return initial
```

- [ ] **Step 2: 验证 — 编译检查**

```bash
cd "D:\codex\project\小红书内容分享\实施\xhs-agent" && D:\Anaconda\envs\ContentShare\python.exe -c "from app.api import _build_run_request, _initial_state_from_request; p = _build_run_request({'topic': 'test', 'stage_override': 'monetization_ready', 'product_name': '辅食机'}); s = _initial_state_from_request(p); print('stage:', s.get('stage_override'), 'product:', s.get('user_product_name'))"
```

预期：`stage: monetization_ready product: 辅食机`

- [ ] **Step 3: 提交**

```bash
git add app/api.py
git commit -m "feat: pass stage_override and product fields through API"
```

---

### Task 15: 端到端验证 — 冷启动回归 + 编译检查

**Files:**
- (无新建文件)

- [ ] **Step 1: 全量编译检查**

```bash
cd "D:\codex\project\小红书内容分享\实施\xhs-agent" && D:\Anaconda\envs\ContentShare\python.exe -m compileall -q app nodes routers platforms memory llm
```

预期：无错误输出

- [ ] **Step 2: 运行冷启动回归测试**

```bash
cd "D:\codex\project\小红书内容分享\实施\xhs-agent" && D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/ -v --ignore=tests/test_qianfan_mock.py --ignore=tests/test_pugongying_mock.py --ignore=tests/test_product_node.py --ignore=tests/test_soft_ad_node.py -x
```

预期：全部 PASS（确保现有 333 个测试没有回归）

- [ ] **Step 3: 运行新增测试**

```bash
cd "D:\codex\project\小红书内容分享\实施\xhs-agent" && D:\Anaconda\envs\ContentShare\python.exe -m pytest tests/test_qianfan_mock.py tests/test_pugongying_mock.py tests/test_product_node.py tests/test_soft_ad_node.py -v
```

预期：全部 PASS

- [ ] **Step 4: 提交**

```bash
git add -A
git commit -m "test: verify m6 changes don't regress existing tests"
```

---

### Task 16: 端到端 smoke — 软广链路完整跑通

- [ ] **Step 1: 运行 mock 模式软广 CLI**

```bash
cd "D:\codex\project\小红书内容分享\实施\xhs-agent" && D:\Anaconda\envs\ContentShare\python.exe -m app.main --topic "宝宝辅食" --stage monetization_ready --product-name "辅食机" --product-selling-points "一键操作节省时间" --engine local --approve
```

预期：
- `content_type: soft_ad`
- `compliance_risk_level: low`（模板内容合规）
- `publish_status: success`
- `operation_memory_written: True`

- [ ] **Step 2: 验证输出**

检查 `output/markdown_exports/` 目录中最新生成的 Markdown 文件，确认：
- 标题包含软广特征
- 正文包含商品信息和广告标识
- 标签包含"好物分享"或"理性种草"

- [ ] **Step 3: 运行 .env 配置检查脚本（如已有）**

```bash
cd "D:\codex\project\小红书内容分享\实施\xhs-agent" && D:\Anaconda\envs\ContentShare\python.exe scripts/check_api_run.py --require-stage-override --stage monetization_ready
```

- [ ] **Step 4: 提交**

```bash
git add -A
git commit -m "smoke: verify soft_ad end-to-end pipeline"
```

---

### 已规划但未在本次计划中实现

1. **蒲公英达人匹配在 soft_ad_node 中的集成**：设计中预留了 `darwin_candidates` 字段和 `pugongying.py` adapter，但 soft_ad_node 当前只处理图文生成。达人匹配逻辑可以在后续任务中集成到 soft_ad_node 或作为一个独立的可选节点。

2. **软广视频脚本生成**：当前 soft_ad_node 只生成图文内容。视频脚本可参照 `video_node.py` 的思路后续扩展。

3. **.env.example 更新**：新增的环境变量（`QIANFAN_MODE`、`XHS_QIANFAN_COOKIES`、`PUGONGYING_MODE`、`XHS_PUGONGYING_COOKIES`）需要在 `.env.example` 中添加说明，但这不是阻塞项。
