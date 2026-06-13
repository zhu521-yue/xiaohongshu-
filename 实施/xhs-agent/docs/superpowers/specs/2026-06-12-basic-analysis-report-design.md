# 基础数据分析报告设计

## 目标

在采集候选池评分初版完成后，新增一层确定性的基础数据分析报告，让每次 run 能解释采集样本的来源、候选池质量、评论质量、痛点可信度和内容结构建议。

本轮只做后端可解释报告，不做复杂 UI、不做数据库落表、不接入 LLM 评审。报告必须可测试、可复现，并能直接出现在 run/API 的 `insights` 中，供工作台、诊断脚本和后续数据库结构化沉淀复用。

## 范围

本轮包含：
- 新增确定性分析模块，从 `collection_candidates`、`raw_notes`、`raw_comments`、`comment_insights`、`pain_points`、`comment_fetch_errors` 生成 `analysis_report`。
- 在 insight 节点成功采集和兜底失败两条路径都返回 `analysis_report`。
- 在 `XHSState` 和 API insight payload 中暴露 `analysis_report`。
- 在 `scripts/check_collector.py` 的搜索/评论诊断结果中输出同一套分析摘要。
- 新增测试覆盖报告结构、置信度分级、采集失败兜底和 API payload 透传。

本轮不包含：
- 不新增数据库表，不迁移 run store 或 operation memory。
- 不新增 LLM/embedding/GraphRAG 语义分析。
- 不新增工作台复杂展示，只保证 API/run 数据可读。
- 不改变候选池评分排序规则，除非报告生成需要读取已有字段。
- 不触发任何真实发布或平台写入。

## 报告结构

`analysis_report` 建议为一个 dict，包含以下字段：

- `sample_selection`
  - `candidate_count`：候选笔记数量。
  - `selected_count`：入选笔记数量。
  - `top_score`：候选最高分。
  - `selected_titles`：入选笔记标题，最多 5 条。
  - `selection_reason`：一句话解释样本选择依据。
- `comment_quality`
  - `raw_comments_count`：采集到的评论数量。
  - `insight_count`：评论洞察数量。
  - `pain_point_count`：痛点数量。
  - `evidence_count`：洞察证据评论总数。
  - `quality_level`：`high`、`medium`、`low`。
  - `quality_reason`：一句话解释评论质量。
- `pain_point_confidence`
  - `level`：`high`、`medium`、`low`。
  - `score`：0-100 的确定性分数。
  - `reason`：一句话解释可信度。
- `content_structure_hint`
  - `recommended_type`：建议内容结构，例如 `avoid_mistakes`、`step_tutorial`、`qa_education`、`knowledge_share`。
  - `reason`：一句话解释建议原因。
- `risks`
  - 字符串列表，记录采集质量风险，例如候选少、评论少、痛点证据少、评论抓取失败。
- `summary`
  - 面向用户的一句话总览。

字段保持确定性和短文本，不把原始 Cookie、token、xsec_token、用户标识等敏感数据写入报告。

## 评分和分级规则

### 评论质量

初版规则使用已有数据，不引入新模型：

- `high`：`raw_comments_count >= 20` 且 `evidence_count >= 5` 且没有评论抓取错误。
- `medium`：`raw_comments_count >= 5` 且 `evidence_count >= 2`。
- `low`：不满足上述条件。

若存在 `comment_fetch_errors`，质量等级最多为 `medium`，并在 `risks` 中提示。

### 痛点可信度

初版置信度分数：

- 基础分来自证据评论数量：每条证据 12 分，最多 48 分。
- 痛点数量加分：每个痛点 10 分，最多 30 分。
- 入选样本加分：每个入选候选 6 分，最多 18 分。
- 如果存在评论抓取错误，扣 15 分。
- 如果没有候选池或没有评论，分数上限为 45。

等级：
- `high`：`score >= 70`
- `medium`：`score >= 45`
- `low`：低于 45

### 内容结构建议

初版规则：

- 如果痛点或标题中包含“坑”“避开”“误区”“判断”，推荐 `avoid_mistakes`。
- 如果痛点或标题中包含“步骤”“怎么”“方法”“从哪里开始”，推荐 `step_tutorial`。
- 如果评论证据中问号较多，推荐 `qa_education`。
- 其它情况推荐 `knowledge_share`。

该建议只是分析报告提示，不覆盖现有 strategy 节点的最终内容类型决策。

## 数据流

1. 采集层返回候选池、笔记、评论、评论洞察、痛点和抓取错误。
2. `nodes.insight_node.analyze_topic_and_pain_points()` 调用报告生成函数。
3. 返回 state 时加入 `analysis_report`。
4. `app.api._insight_payload()` 把 `analysis_report` 放入 run/API 的 `insights`。
5. `scripts/check_collector.py` 在诊断输出中调用同一报告函数，保证脚本和 run 口径一致。

## 错误处理

- 采集异常兜底时也生成低置信度报告，说明真实采集失败、评论质量低、需要重新采集。
- 输入字段缺失时按空列表处理，不抛出二次异常。
- 报告只依赖已脱敏数据，不读取 `.env`，不触发网络请求。
- 如果候选池为空但有 `raw_notes`，报告仍可根据笔记和评论生成低到中等置信度结果。

## 测试计划

单元测试：
- 高质量候选和评论能生成 `high` 评论质量、较高痛点可信度和明确样本选择摘要。
- 评论少或无证据时生成 `low`，并包含评论不足风险。
- 存在 `comment_fetch_errors` 时降低质量等级并输出风险。
- 内容结构建议能根据“避坑/步骤/问答”信号选择合理类型。

节点测试：
- insight 节点成功采集结果包含 `analysis_report`。
- insight 节点采集异常兜底结果包含低置信度 `analysis_report`。

API/脚本测试：
- `_insight_payload()` 透传 `analysis_report`。
- `scripts/check_collector.py` 输出包含 `analysis_report`。

## 验收标准

- 运行一次 mock 或真实采集 run 后，`insights.analysis_report` 存在且字段完整。
- 报告能解释候选池、评论质量、痛点可信度、内容结构建议和风险。
- 旧字段 `collection_candidates`、`comment_insights`、`pain_points` 行为保持兼容。
- 全量测试通过。
