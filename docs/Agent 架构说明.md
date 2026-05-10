# Agent 架构说明

## Agent 定位

Knowledge Integration Agent 是一个面向教师的教材整合智能体。它不只是聊天机器人，而是围绕教材处理任务组织多个能力模块：解析、抽取、整合、检索、反馈和报告。系统通过 LangGraph 把这些能力串成稳定流水线，并通过前端工作台暴露给教师使用。

## 能力模块

### 1. 教材解析 Agent

- 输入：PDF、Markdown、TXT 教材文件。
- 输出：`Textbook` 与 `Chapter` 结构化数据。
- 设计：Demo Mode 限制页数，Quality Mode 处理更多内容；解析失败会写入教材状态和错误信息。

### 2. 知识图谱抽取 Agent

- 输入：教材标题、章节标题、章节正文。
- 输出：知识点节点和关系边。
- 模型：优先使用 DeepSeek；无 Key 或调用失败时使用 fallback。
- 约束：输出标准化为 nodes/edges，关系类型限定为 prerequisite、parallel、contains、applies_to。

### 3. 跨教材整合 Agent

- 输入：多本教材生成的知识节点。
- 输出：整合后的节点、边和 `IntegrationDecision`。
- 策略：利用文本向量相似度和规则识别可合并节点，记录 action、affected_node_ids、reason、confidence。
- 目标：减少重复概念，保留来源信息，给教师可审查的决策依据。

### 4. RAG 检索 Agent

- 输入：章节正文和教师问题。
- 处理：章节按 500-800 字切分，chunk 间保留 80 字重叠；每个 chunk 存储轻量向量。
- 输出：回答、citations、source_chunks。
- 引用：包含教材、章节、页码范围和 chunk_id，支持教师追溯答案来源。

### 5. 教师反馈 Agent

- 输入：教师自然语言反馈和可选决策 ID。
- 输出：助手回复、更新状态、决策快照。
- 行为：能识别 `merge_001`、`keep_001`、`remove_001` 等决策编号；当教师表达保留或撤销合并时，将对应决策覆盖为 keep 并标记 `teacher_overridden=True`。

### 6. 报告 Agent

- 输入：教材、图谱、整合决策、RAG 索引状态。
- 输出：整合报告 Markdown 文本。
- 内容：处理摘要、知识点覆盖、整合结论、风险提示和教学建议。

## LangGraph 编排

流水线节点顺序如下：

```text
START -> parse -> graph -> integrate -> rag -> report -> END
```

每个节点只负责一个阶段，并通过 `PipelineState` 传递 `run_id`、`textbook_ids`、`errors` 和 `summary`。即使某阶段出现可捕获错误，系统也会记录错误并进入后续汇总，避免演示流程直接中断。

## 前后端交互

1. 前端上传教材并选择 Demo/Quality 模式。
2. 后端创建 `Textbook`，保存文件到 media。
3. 前端调用 `/api/pipeline/run`，后端同步执行 LangGraph 流水线。
4. 前端刷新 `/api/graph`、`/api/report`、`/api/pipeline/status`。
5. 教师通过 `/api/rag/query` 提问，通过 `/api/teacher/chat` 反馈整合结果。

## 可解释性设计

- 知识节点保留 textbook、chapter、page、frequency。
- 整合决策保留理由、置信度和 affected_node_ids。
- RAG 回答保留 citations 和 source_chunks。
- 教师覆盖通过 `teacher_overridden` 显式记录，避免 AI 决策覆盖人工判断。

## 演示优势

- Demo Mode 确保快速出结果。
- DeepSeek fallback 确保无外部凭据也可演示。
- ECharts 图谱让评委直观看到结构化成果。
- RAG 引用和教师反馈体现教育场景中的可信、可控需求。
