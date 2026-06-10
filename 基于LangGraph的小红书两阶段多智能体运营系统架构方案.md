# 基于 LangGraph 的小红书两阶段多智能体运营系统架构方案

## 1. 项目背景

本方案基于前期关于“小红书知识分享与商品软广两阶段多智能体系统”的讨论整理而成。

项目面向一个刚起步的小红书账号，初期目标不是直接带货或批量自动发帖，而是通过知识分享内容完成账号冷启动，包括账号标签建立、用户信任积累、内容方向测试、用户痛点沉淀和 GraphRAG 运营记忆建设。

后续当账号具备一定内容基础和用户信任后，再逐步引入商品软广、商品选品、达人合作和商业化投放能力。

在技术架构上，建议使用 LangGraph 实现该系统。

---

## 2. 为什么适合使用 LangGraph

该系统并不是一个简单的线性流程：

```text
输入主题 → 生成文案 → 发布
```

而是一个包含状态判断、条件分支、人工审核、发布复盘和长期记忆回写的复杂工作流。

系统中存在大量非线性逻辑，例如：

```text
冷启动阶段 → 禁止软广
成长阶段 → 可以低频软广

用户选择图文 → 走图文生成流程
用户选择视频 → 走视频脚本生成流程

合规审核通过 → 进入人工确认
合规审核不通过 → 返回内容修改
人工审核通过 → 发布或排期
人工审核不通过 → 返回内容生成节点

发布成功 → 进入复盘
发布失败 → 进入错误处理
复盘完成 → 回写 GraphRAG
```

因此，该项目天然适合用“图结构工作流”来表达。

LangGraph 的优势主要体现在：

```text
1. 支持有状态工作流；
2. 支持条件分支；
3. 支持循环和回退；
4. 支持人工审核节点；
5. 支持工具调用；
6. 支持长期记忆和 checkpoint；
7. 适合构建多智能体协作系统；
8. 后期便于扩展平台接口、商品接口和达人接口。
```

---

## 3. 架构设计原则

使用 LangGraph 时，不建议把所有环节都设计成完全自由发挥的 Agent。

更稳妥的方式是：

```text
LangGraph 负责流程编排；
规则节点负责边界控制；
LLM 节点负责分析和生成；
工具节点负责平台操作；
人工节点负责最终确认；
GraphRAG 负责长期记忆。
```

也就是说：

```text
确定性流程：交给 LangGraph
策略判断：规则 + LLM
内容生成：交给 LLM
平台操作：交给 Tool Node
发布确认：交给人工审核
历史经验：交给 GraphRAG
```

核心原则是：

```text
不要让 Agent 完全自由行动，而是让 Agent 在 LangGraph 设计好的流程和规则内工作。
```

---

## 4. 总体系统架构

建议系统采用一个主图加多个子图的结构。

```text
main_graph
│
├── stage_check_node              # 判断账号阶段
├── topic_input_node              # 接收用户主题
├── strategy_subgraph             # 内容策略子图
├── insight_subgraph              # 选题与痛点分析子图
├── content_subgraph              # 内容生成子图
├── compliance_subgraph           # 合规审核子图
├── human_review_node             # 人工确认节点
├── publish_subgraph              # 发布子图
├── review_subgraph               # 数据复盘子图
└── memory_write_node             # 回写 GraphRAG
```

总体流程为：

```text
用户输入主题
↓
账号阶段判断
↓
GraphRAG 检索历史经验
↓
选题与痛点分析
↓
内容策略判断
↓
图文 / 视频 / 软广分支
↓
内容生成
↓
合规审核
↓
人工确认
↓
发布 / 排期
↓
数据复盘
↓
回写 GraphRAG
```

---

## 5. 两阶段运营逻辑

系统需要根据账号阶段采取不同策略。

---

# 阶段一：冷启动阶段

## 5.1 阶段一定位

阶段一只做知识分享，不做商品软广。

核心目标是：

```text
养账号
打标签
积累内容
测试用户痛点
提升收藏和评论
建立用户信任
训练 GraphRAG 运营记忆
```

## 5.2 阶段一内容类型

允许生成：

```text
知识分享型内容
经验总结型内容
避坑清单型内容
问答科普型内容
步骤教程型内容
```

禁止生成：

```text
商品软广
强种草
测评带货
合作邀请
分销内容
```

## 5.3 阶段一规则

```json
{
  "account_stage": "cold_start",
  "allow_soft_ad": false,
  "allowed_content_types": [
    "knowledge_share",
    "experience_summary",
    "avoid_mistakes",
    "qa_education",
    "step_tutorial"
  ],
  "allowed_formats": [
    "image_text",
    "video"
  ],
  "manual_review_required": true
}
```

## 5.4 阶段一 LangGraph 流程

```text
START
↓
load_user_input
↓
check_account_stage
↓
retrieve_graphrag_memory
↓
analyze_topic_and_pain_points
↓
decide_content_strategy
↓
route_content_format
    ├── generate_image_text
    └── generate_video_script
↓
compliance_check
↓
human_review
↓
save_output
↓
manual_publish_or_schedule
↓
collect_performance_manually
↓
review_and_write_memory
↓
END
```

---

# 阶段二：知识分享 + 商品软广阶段

## 5.5 阶段二定位

当账号积累一定内容基础和用户信任后，进入第二阶段。

第二阶段开始引入商品软广，但仍然以知识分享为主。

推荐内容比例：

```text
知识分享：70%
商品软广：30%
```

如果账号仍然较弱，可以更保守：

```text
知识分享：80%
商品软广：20%
```

## 5.6 进入阶段二的判断条件

建议满足以下条件后再允许软广：

```text
累计发布 ≥ 30 篇内容
至少有 3 个稳定高表现主题
收藏率明显高于账号平均水平
评论区开始出现“求推荐”“怎么买”“用什么”之类问题
账号内容标签比较稳定
用户对账号有一定信任感
```

## 5.7 阶段二规则

```json
{
  "account_stage": "growth_and_monetization",
  "allow_soft_ad": true,
  "knowledge_share_ratio": 0.7,
  "soft_ad_ratio": 0.3,
  "max_soft_ads_per_week": 2,
  "no_consecutive_soft_ads": true,
  "soft_ad_manual_review_required": true,
  "allowed_formats": [
    "image_text",
    "video"
  ]
}
```

## 5.8 阶段二 LangGraph 流程

```text
START
↓
load_user_input
↓
check_account_stage
↓
retrieve_graphrag_memory
↓
analyze_topic_and_pain_points
↓
decide_content_strategy
↓
route_content_type
    ├── knowledge_content_flow
    └── soft_ad_content_flow
↓
如果是知识分享：
    route_content_format
        ├── generate_image_text
        └── generate_video_script
↓
如果是商品软广：
    retrieve_product_info
    ↓
    match_product_with_pain_points
    ↓
    generate_soft_ad_content
↓
compliance_check
↓
commercial_compliance_check
↓
human_review
↓
publish_or_schedule
↓
collect_performance
↓
review_and_write_memory
↓
END
```

---

## 6. 推荐子图设计

整个系统建议拆成以下 6 个核心子图。

---

## 6.1 账号阶段判断子图

### 作用

判断账号当前处于哪个阶段。

### 输入

```text
已发布笔记数
最近 7 天内容表现
是否有稳定高表现主题
评论区是否出现购买意图
用户设置
```

### 输出

```text
cold_start
growth
monetization_ready
```

### 示例规则

```text
已发布 < 30 篇 → cold_start
已发布 ≥ 30 篇，但购买意图弱 → growth
已发布 ≥ 30 篇，且评论区出现求推荐 / 怎么买 / 用什么 → monetization_ready
```

### 输出示例

```json
{
  "account_stage": "cold_start",
  "allow_soft_ad": false,
  "reason": "账号累计发布内容不足 30 篇，仍处于冷启动阶段。"
}
```

---

## 6.2 内容策略子图

### 作用

决定今天应该生成什么内容。

### 输入

```text
用户主题
用户选择：图文 / 视频
账号阶段
最近内容表现
GraphRAG 历史经验
用户当天目标
```

### 输出

```text
内容类型
内容形式
是否允许软广
是否需要人工强审核
是否适合发布
```

### 内容类型

```text
knowledge_share
experience_summary
avoid_mistakes
qa_education
step_tutorial
soft_ad
```

### 内容形式

```text
image_text
video
```

### 硬规则

```text
如果 account_stage = cold_start，
则 content_type 只能是知识分享相关类型，
不能进入 soft_ad 分支。
```

---

## 6.3 选题与痛点分析子图

### 作用

分析主题下用户真正关心什么。

### 输入

```text
用户主题
导入的小红书样本
评论数据
GraphRAG 历史相关主题
```

### 处理任务

```text
清洗数据
筛选高互动内容
提取高关注子主题
分析用户评论
识别用户痛点
按痛点重要性排序
拆解爆款标题结构
识别内容缺口
```

### 输出

```text
top_subtopics
pain_points
title_patterns
content_opportunities
```

### 示例输出

```json
{
  "top_subtopics": [
    "宝宝湿疹和过敏怎么区分",
    "宝宝湿疹日常护理误区",
    "宝宝保湿霜怎么选"
  ],
  "pain_points": [
    {
      "pain": "不知道湿疹和过敏怎么区分",
      "priority": 1,
      "emotion": "焦虑",
      "content_opportunity": "适合做问答科普型内容"
    },
    {
      "pain": "担心乱涂药膏影响宝宝",
      "priority": 2,
      "emotion": "担心",
      "content_opportunity": "适合做避坑清单型内容"
    }
  ]
}
```

---

## 6.4 内容生成子图

### 作用

根据策略生成图文笔记、视频脚本或软广内容。

### 子节点

```text
content_subgraph
│
├── generate_image_text_node
├── generate_video_script_node
└── generate_soft_ad_node
```

### 图文笔记输出

```text
标题 5 个
封面文案 3 个
正文
图片页结构
每页图片文案
图片生成提示词
话题标签
评论区引导语
合规提醒
```

### 视频脚本输出

```text
视频标题
开头 3 秒钩子
30-60 秒口播脚本
分镜脚本
字幕文案
画面建议
封面文案
话题标签
评论区引导
合规提醒
```

### 软广内容输出

```text
标题 5 个
封面文案 3 个
正文
商品卖点拆解
用户痛点匹配说明
图片 / 视频脚本建议
话题标签
评论区引导
商业合规提醒
```

---

## 6.5 合规审核与人工确认子图

### 作用

保证内容不会违规发布。

### 流程

```text
内容生成
↓
合规审核
↓
风险等级判断
    ├── 低风险 → 人工确认
    ├── 中风险 → 自动修改后再次审核
    └── 高风险 → 停止发布
↓
人工确认
    ├── 通过 → 发布 / 排期
    └── 不通过 → 返回内容修改
```

### 审核维度

```text
是否虚假宣传
是否绝对化表达
是否涉及医疗诊断或治疗承诺
是否夸大产品效果
是否存在平台不鼓励的引流表达
是否疑似搬运或高度模仿
是否涉及未成年人隐私
是否需要商业推广标识
是否存在版权风险
是否适合发布
```

### 人工确认节点

人工确认节点应作为强制节点保留，尤其是在以下情况中：

```text
所有发布前
所有软广内容
所有涉及母婴 / 健康 / 教育 / 金融的内容
所有中风险修改后的内容
```

---

## 6.6 发布与复盘子图

### 作用

完成发布、记录和复盘。

### 阶段一

阶段一可以先不自动发布，而是输出内容，人工复制发布。

```text
save_output
↓
manual_publish
↓
manual_input_performance
↓
review_performance
↓
write_to_graphrag
```

### 阶段二或后期

可以接入创作者平台：

```text
creator_login
↓
upload_image_text / upload_video
↓
get_published_posts
↓
record_publish_status
↓
collect_performance
↓
review_performance
↓
write_to_graphrag
```

### 复盘周期

建议按以下时间点复盘：

```text
24 小时复盘
72 小时复盘
7 天复盘
```

### 复盘输出

```text
这个主题是否继续
这个标题结构是否有效
图文还是视频表现更好
用户评论里出现了什么新痛点
是否可以进入软广测试
是否需要回写 GraphRAG
```

---

## 7. LangGraph State 设计

LangGraph 的核心是 State，因此需要提前设计好全流程状态字段。

推荐 State 如下：

```python
from typing import TypedDict, Literal, List, Dict, Any, Optional

class XHSState(TypedDict, total=False):
    # 用户输入
    user_topic: str
    target_user: str
    user_selected_format: Literal["image_text", "video"]
    user_goal: str

    # 账号阶段
    account_stage: Literal["cold_start", "growth", "monetization_ready"]
    allow_soft_ad: bool

    # 数据分析结果
    raw_notes: List[Dict[str, Any]]
    raw_comments: List[Dict[str, Any]]
    cleaned_notes: List[Dict[str, Any]]
    top_subtopics: List[Dict[str, Any]]
    pain_points: List[Dict[str, Any]]

    # GraphRAG 检索结果
    retrieved_memory: List[Dict[str, Any]]
    successful_patterns: List[Dict[str, Any]]

    # 策略结果
    content_type: Literal[
        "knowledge_share",
        "experience_summary",
        "avoid_mistakes",
        "qa_education",
        "step_tutorial",
        "soft_ad"
    ]
    content_format: Literal["image_text", "video"]

    # 商品软广相关
    product_info: Optional[Dict[str, Any]]
    product_selling_points: List[str]
    product_pain_match: List[Dict[str, Any]]

    # 内容生成结果
    titles: List[str]
    cover_texts: List[str]
    body: str
    image_page_plan: List[Dict[str, Any]]
    image_prompts: List[str]
    video_script: Dict[str, Any]
    tags: List[str]
    comment_call: str

    # 合规审核
    compliance_risk_level: Literal["low", "medium", "high"]
    compliance_issues: List[str]
    revised_content: Optional[str]

    # 人工审核
    human_approved: bool
    human_feedback: Optional[str]

    # 发布结果
    publish_status: Literal["pending", "success", "failed"]
    post_id: Optional[str]
    publish_time: Optional[str]

    # 复盘结果
    performance_data: Dict[str, Any]
    review_summary: str
    next_action: str

    # 错误处理
    error_message: Optional[str]
```

---

## 8. 条件路由设计

LangGraph 中需要通过条件边控制流程走向。

---

## 8.1 内容形式路由

```python
def route_content_format(state: XHSState) -> str:
    if state["content_format"] == "image_text":
        return "generate_image_text"
    elif state["content_format"] == "video":
        return "generate_video_script"
    else:
        return "error_handler"
```

---

## 8.2 内容类型路由

```python
def route_content_type(state: XHSState) -> str:
    if state["content_type"] == "soft_ad":
        if not state.get("allow_soft_ad", False):
            return "force_knowledge_share"
        return "product_match"
    return "knowledge_content"
```

---

## 8.3 合规结果路由

```python
def route_compliance_result(state: XHSState) -> str:
    risk = state.get("compliance_risk_level")

    if risk == "low":
        return "human_review"
    elif risk == "medium":
        return "revise_content"
    elif risk == "high":
        return "stop_publish"
    else:
        return "error_handler"
```

---

## 8.4 人工审核结果路由

```python
def route_human_review(state: XHSState) -> str:
    if state.get("human_approved") is True:
        return "publish_or_schedule"
    else:
        return "revise_content"
```

---

## 9. 推荐主图伪代码

下面是简化版 LangGraph 主图伪代码。

```python
from langgraph.graph import StateGraph, START, END

graph = StateGraph(XHSState)

# 节点注册
graph.add_node("load_user_input", load_user_input)
graph.add_node("check_account_stage", check_account_stage)
graph.add_node("retrieve_graphrag_memory", retrieve_graphrag_memory)
graph.add_node("analyze_topic_and_pain_points", analyze_topic_and_pain_points)
graph.add_node("decide_content_strategy", decide_content_strategy)

graph.add_node("generate_image_text", generate_image_text)
graph.add_node("generate_video_script", generate_video_script)
graph.add_node("product_match", product_match)
graph.add_node("generate_soft_ad", generate_soft_ad)

graph.add_node("compliance_check", compliance_check)
graph.add_node("revise_content", revise_content)
graph.add_node("human_review", human_review)
graph.add_node("publish_or_schedule", publish_or_schedule)

graph.add_node("collect_performance", collect_performance)
graph.add_node("review_and_write_memory", review_and_write_memory)
graph.add_node("stop_publish", stop_publish)
graph.add_node("error_handler", error_handler)

# 主流程
graph.add_edge(START, "load_user_input")
graph.add_edge("load_user_input", "check_account_stage")
graph.add_edge("check_account_stage", "retrieve_graphrag_memory")
graph.add_edge("retrieve_graphrag_memory", "analyze_topic_and_pain_points")
graph.add_edge("analyze_topic_and_pain_points", "decide_content_strategy")

# 内容类型路由
graph.add_conditional_edges(
    "decide_content_strategy",
    route_content_type,
    {
        "knowledge_content": "route_format",
        "product_match": "product_match",
        "force_knowledge_share": "generate_image_text",
        "error_handler": "error_handler"
    }
)

# 注意：route_format 可以是一个独立节点，也可以直接在 decide_content_strategy 后做条件边
graph.add_conditional_edges(
    "route_format",
    route_content_format,
    {
        "generate_image_text": "generate_image_text",
        "generate_video_script": "generate_video_script",
        "error_handler": "error_handler"
    }
)

# 软广流程
graph.add_edge("product_match", "generate_soft_ad")

# 内容生成后进入合规审核
graph.add_edge("generate_image_text", "compliance_check")
graph.add_edge("generate_video_script", "compliance_check")
graph.add_edge("generate_soft_ad", "compliance_check")

# 合规路由
graph.add_conditional_edges(
    "compliance_check",
    route_compliance_result,
    {
        "human_review": "human_review",
        "revise_content": "revise_content",
        "stop_publish": "stop_publish",
        "error_handler": "error_handler"
    }
)

graph.add_edge("revise_content", "compliance_check")

# 人工审核路由
graph.add_conditional_edges(
    "human_review",
    route_human_review,
    {
        "publish_or_schedule": "publish_or_schedule",
        "revise_content": "revise_content"
    }
)

# 发布与复盘
graph.add_edge("publish_or_schedule", "collect_performance")
graph.add_edge("collect_performance", "review_and_write_memory")
graph.add_edge("review_and_write_memory", END)

# 停止与错误
graph.add_edge("stop_publish", END)
graph.add_edge("error_handler", END)

app = graph.compile()
```

注意：

```text
上面只是架构伪代码，真实代码中 route_format 需要作为可执行节点注册，或者直接把内容形式路由合并到 decide_content_strategy 的条件边中。
```

---

## 10. 节点职责设计

## 10.1 load_user_input

### 职责

读取用户输入。

### 输入

```text
主题
目标人群
内容目标
内容形式：图文 / 视频
账号阶段设置
```

### 输出

写入 State：

```text
user_topic
target_user
user_selected_format
user_goal
```

---

## 10.2 check_account_stage

### 职责

判断账号阶段。

### 规则

```text
如果已发布内容数量不足 30 篇，则为 cold_start；
如果内容数量足够，但用户购买意图弱，则为 growth；
如果内容数量足够，且用户购买意图明显，则为 monetization_ready。
```

### 输出

```text
account_stage
allow_soft_ad
```

---

## 10.3 retrieve_graphrag_memory

### 职责

从 GraphRAG 中检索相关运营经验。

### 检索内容

```text
相关主题
历史高表现标题
历史高表现内容结构
用户痛点
评论高频问题
合规风险记录
```

### 输出

```text
retrieved_memory
successful_patterns
```

---

## 10.4 analyze_topic_and_pain_points

### 职责

分析用户主题与痛点。

### 处理

```text
清洗小红书样本
提取高热子主题
分析评论
提取痛点
给痛点排序
输出内容机会
```

### 输出

```text
top_subtopics
pain_points
title_patterns
content_opportunities
```

---

## 10.5 decide_content_strategy

### 职责

判断今天生成什么内容。

### 输入

```text
账号阶段
用户主题
用户选择内容形式
历史表现
用户痛点
GraphRAG 结果
```

### 输出

```text
content_type
content_format
allow_soft_ad
manual_review_required
```

---

## 10.6 generate_image_text

### 职责

生成小红书图文笔记。

### 输出

```text
标题 5 个
封面文案 3 个
正文
图片页结构
每页图片文案
图片生成提示词
标签
评论区引导语
合规提醒
```

---

## 10.7 generate_video_script

### 职责

生成小红书短视频脚本。

### 输出

```text
视频标题
开头 3 秒钩子
口播脚本
分镜脚本
字幕文案
画面建议
封面文案
标签
评论区引导
合规提醒
```

---

## 10.8 product_match

### 职责

第二阶段使用，负责商品与用户痛点匹配。

### 输入

```text
用户主题
用户痛点
千帆商品信息
商品卖点
历史软广表现
```

### 输出

```text
product_info
product_selling_points
product_pain_match
```

---

## 10.9 generate_soft_ad

### 职责

生成软广内容。

### 原则

```text
先讲痛点
再讲解决思路
最后自然引出商品
不夸大效果
不承诺结果
必须提示商业合规风险
```

---

## 10.10 compliance_check

### 职责

审核内容是否适合发布。

### 输出

```text
compliance_risk_level
compliance_issues
revised_content
```

---

## 10.11 human_review

### 职责

人工确认是否发布。

### 处理方式

可以在第一版中简单实现为：

```text
输出 Markdown 文件，用户人工确认。
```

后续再接入 LangGraph interrupt，实现真正的中断等待人工输入。

---

## 10.12 publish_or_schedule

### 职责

发布或排期。

### 第一版

```text
保存为 Markdown
人工复制发布
```

### 后续版本

```text
创作者平台上传图文
创作者平台上传视频
获取已发布作品列表
记录发布状态
```

---

## 10.13 collect_performance

### 职责

收集发布后的表现数据。

### 第一版

人工录入：

```text
曝光量
点赞数
收藏数
评论数
关注数
发布时间
```

### 后续版本

平台自动获取。

---

## 10.14 review_and_write_memory

### 职责

复盘并回写 GraphRAG。

### 分析内容

```text
这个主题是否值得继续
哪个标题结构有效
图文还是视频表现更好
哪些痛点更容易触发收藏
哪些评论暴露出新问题
是否可以进入软广测试
```

---

## 11. 第一版 MVP 建议

第一版不要直接接入所有平台和所有自动化能力。

建议只实现：

```text
用户输入主题
↓
用户选择图文 / 视频
↓
系统默认 cold_start 阶段
↓
GraphRAG / JSON 历史记忆检索
↓
生成知识分享内容
↓
合规审核
↓
人工确认
↓
输出 Markdown
↓
人工发布
↓
手动录入数据
↓
复盘回写
```

第一版暂时不要做：

```text
自动爬虫
自动发布
蒲公英合作邀请
千帆商品分销
批量账号运营
全自动软广生成
```

这样更容易跑通，并且风险更低。

---

## 12. 分阶段开发路线

## 12.1 第一阶段：LangGraph 内容生成 MVP

实现节点：

```text
load_user_input
check_account_stage
retrieve_memory
decide_content_strategy
generate_image_text
generate_video_script
compliance_check
human_review
save_output
```

目标：

```text
跑通知识分享内容生成流程。
```

---

## 12.2 第二阶段：加入复盘闭环

新增节点：

```text
load_performance_data
analyze_performance
write_to_graphrag
recommend_next_topic
```

目标：

```text
让系统开始拥有运营记忆。
```

---

## 12.3 第三阶段：接入创作者平台

新增节点：

```text
creator_login
upload_image_text
upload_video
get_published_posts
record_publish_status
```

目标：

```text
实现发布和作品列表获取。
```

原则：

```text
发布前必须保留人工确认。
```

---

## 12.4 第四阶段：加入商品软广

新增节点：

```text
product_retrieval_node
product_pain_match_node
soft_ad_generation_node
commercial_compliance_node
```

硬规则：

```text
cold_start 阶段禁止软广
连续软广禁止发布
软广必须人工审核
涉及功效、健康、母婴内容必须严格合规审核
```

---

## 12.5 第五阶段：加入蒲公英达人投放

新增节点：

```text
kol_search_node
kol_profile_analysis_node
kol_match_node
brief_generation_node
cooperation_invite_node
```

目标：

```text
用于后期达人合作和商业化放大。
```

---

## 13. 技术目录结构建议

```text
xiaohongshu-langgraph-agent/
│
├── app/
│   ├── main.py
│   ├── graph.py
│   ├── state.py
│   └── config.py
│
├── nodes/
│   ├── input_node.py
│   ├── stage_node.py
│   ├── memory_node.py
│   ├── insight_node.py
│   ├── strategy_node.py
│   ├── content_node.py
│   ├── video_node.py
│   ├── product_node.py
│   ├── compliance_node.py
│   ├── human_review_node.py
│   ├── publish_node.py
│   └── review_node.py
│
├── routers/
│   ├── content_type_router.py
│   ├── content_format_router.py
│   ├── compliance_router.py
│   └── review_router.py
│
├── prompts/
│   ├── topic_analysis_prompt.md
│   ├── pain_point_prompt.md
│   ├── content_strategy_prompt.md
│   ├── image_text_generation_prompt.md
│   ├── video_script_prompt.md
│   ├── soft_ad_prompt.md
│   ├── compliance_check_prompt.md
│   └── review_prompt.md
│
├── tools/
│   ├── creator_platform_tool.py
│   ├── pugongying_tool.py
│   ├── qianfan_tool.py
│   ├── file_tool.py
│   └── database_tool.py
│
├── memory/
│   ├── graphrag/
│   ├── vector_db/
│   ├── graph_db/
│   └── operation_history.json
│
├── data/
│   ├── raw_notes.csv
│   ├── raw_comments.csv
│   ├── performance_logs.csv
│   ├── product_data.csv
│   └── kol_data.csv
│
├── output/
│   ├── image_text_notes/
│   ├── video_scripts/
│   ├── publish_plan/
│   ├── review_reports/
│   └── markdown_exports/
│
└── requirements.txt
```

---

## 14. 关键 Prompt 模板

## 14.1 内容策略判断 Prompt

```text
你是一个小红书内容策略智能体。

当前账号阶段：
{{account_stage}}

最近 7 天内容表现：
{{recent_performance}}

GraphRAG 中历史高表现主题：
{{historical_success_topics}}

用户今天输入的主题：
{{topic}}

用户可选择的内容形式：
{{allowed_formats}}

请判断今天适合生成什么内容：

1. 是否适合继续做知识分享；
2. 是否适合测试新主题；
3. 是否适合做图文笔记还是视频；
4. 如果账号处于冷启动阶段，禁止生成商品软广；
5. 如果账号处于商业化阶段，判断是否可以插入软广；
6. 输出推荐理由和内容生成要求。

请用 JSON 输出。
```

---

## 14.2 图文笔记生成 Prompt

```text
你是一个资深小红书图文笔记创作者。

用户主题：
{{topic}}

目标人群：
{{target_user}}

用户痛点：
{{pain_points}}

内容类型：
{{content_type}}

历史表现较好的内容结构：
{{successful_patterns}}

请生成一篇小红书图文笔记，要求：

1. 给出 5 个标题；
2. 给出 3 个封面文案；
3. 给出正文；
4. 给出图片页结构；
5. 给出每页图片文案；
6. 给出图片生成提示词；
7. 给出 5-10 个标签；
8. 给出评论区引导语；
9. 如果涉及健康、母婴、教育、金融等敏感领域，必须加入风险提示；
10. 输出 Markdown 格式。
```

---

## 14.3 视频脚本生成 Prompt

```text
你是一个小红书短视频脚本策划专家。

用户主题：
{{topic}}

目标人群：
{{target_user}}

用户痛点：
{{pain_points}}

视频时长：
{{video_duration}}

内容类型：
{{content_type}}

请生成一个小红书短视频脚本，要求：

1. 给出视频标题；
2. 给出开头 3 秒钩子；
3. 给出 30-60 秒口播脚本；
4. 给出分镜脚本；
5. 给出字幕文案；
6. 给出画面建议；
7. 给出封面文案；
8. 给出话题标签；
9. 给出评论区引导；
10. 给出合规提醒。
```

---

## 14.4 软广内容生成 Prompt

```text
你是一个小红书软广内容策划专家。

用户主题：
{{topic}}

产品或服务：
{{product}}

目标人群：
{{target_user}}

用户痛点：
{{pain_points}}

商品卖点：
{{selling_points}}

请生成一篇软广种草型小红书笔记，要求：

1. 不要一上来直接推产品；
2. 先从真实痛点切入；
3. 中间给出实用建议；
4. 最后自然引出产品或服务；
5. 不使用绝对化、夸大化表达；
6. 不承诺确定效果；
7. 如果属于商业推广，需要提醒用户进行广告或合作标识；
8. 输出标题、封面文案、正文、标签、评论引导和合规提醒。
```

---

## 14.5 合规审核 Prompt

```text
你是一个内容合规审核智能体。

请审核以下小红书笔记内容：

{{content}}

请从以下维度进行检查：

1. 是否存在虚假宣传；
2. 是否存在绝对化表达；
3. 是否涉及医疗诊断或治疗承诺；
4. 是否存在夸大产品效果；
5. 是否存在平台不鼓励的引流表达；
6. 是否疑似搬运或高度模仿；
7. 是否涉及未成年人隐私；
8. 是否需要商业推广标识；
9. 是否存在版权风险；
10. 是否建议发布。

请输出：
- 风险等级：低 / 中 / 高
- 主要风险点
- 修改建议
- 修改后的安全版本
```

---

## 14.6 数据复盘 Prompt

```text
你是一个小红书运营复盘智能体。

以下是某篇内容的发布数据：

主题：
{{topic}}

标题：
{{title}}

内容形式：
{{content_format}}

内容类型：
{{content_type}}

发布时间：
{{publish_time}}

数据表现：
{{performance_data}}

评论关键词：
{{comment_keywords}}

请完成以下任务：

1. 判断这篇内容表现属于高 / 中 / 低；
2. 分析表现好的原因或表现差的原因；
3. 判断该主题是否值得继续；
4. 判断标题结构是否值得复用；
5. 判断图文或视频形式是否适合该主题；
6. 提取新的用户痛点；
7. 给出下一篇内容建议；
8. 判断是否需要写入 GraphRAG。

请用 JSON 输出。
```

---

## 15. 合规与风控建议

该项目涉及小红书内容、用户评论、账号发布和后期软广，因此必须设置边界。

## 15.1 平台操作风险

避免：

```text
高频抓取
模拟登录绕过限制
批量采集用户信息
批量自动发布
搬运或高度仿写爆款内容
诱导站外引流
未标识商业推广
```

## 15.2 内容风险

尤其母婴、健康、教育、金融类内容，避免：

```text
绝对化表达
疗效承诺
制造焦虑
虚构经历
虚假测评
夸大产品效果
冒充专业人士
```

## 15.3 数据隐私风险

建议：

```text
只保留必要字段
评论去标识化
不存储用户主页、头像、昵称、账号 ID
不做人群画像和个人追踪
只做主题级别和内容级别分析
```

---

## 16. 最终结论

使用 LangGraph 实现该项目是合理的，而且非常适合。

原因是：

```text
1. 该系统具有明显的状态流转；
2. 该系统存在多分支内容策略；
3. 该系统需要合规审核和人工确认；
4. 该系统需要发布后的数据复盘；
5. 该系统需要长期运营记忆；
6. 该系统后期要接入创作者平台、千帆平台和蒲公英平台；
7. 该系统不是一次性内容生成，而是持续迭代的运营闭环。
```

最推荐的实现方式是：

```text
规则节点控制边界
LLM 节点负责生成和分析
工具节点负责平台操作
人工节点负责发布确认
GraphRAG 负责长期记忆
LangGraph 负责全流程编排
```

一句话总结：

```text
LangGraph 不是用来让 Agent 随意行动的，而是用来把小红书运营过程拆成可控、可回退、可审核、可复盘的多智能体工作流。
```
