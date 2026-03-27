---
name: autoloop-generate
description: >
  AutoLoop T4: 批量内容生成模板。模板驱动 + 并行生成 + 逐项质量检查 + 自动重试。
  每个生成单元独立评分，低分自动重生成，重试上限见 protocols/loop-protocol.md 统一重试规则（默认2次）。
  质量门禁阈值见 protocols/quality-gates.md T4 行。
  触发：/autoloop:generate 或任何需要批量生成同类内容的任务。
---

# AutoLoop T4: Generate — 批量内容生成

## 执行前提

读取 `autoloop-plan.md` 获取：
- 内容类型（报告/邮件/代码/数据/文案等）
- 变量列表（每个生成单元的变化项）
- 数量
- 质量标准（通过标准见 `protocols/quality-gates.md` T4 行）
- 示例（至少 1 个用户认可的样本）
- 输出位置（output_path，变量名见 `protocols/loop-protocol.md` 统一参数词汇表）
- 文件命名规则（naming_pattern，变量名见 `protocols/loop-protocol.md` 统一参数词汇表）

**Round 2+ OBSERVE 起点**：先读取 `autoloop-findings.md` 反思章节，获取遗留问题、有效/无效策略、已识别模式、经验教训，再扫描当前状态。详见 `protocols/loop-protocol.md` OBSERVE Step 0 章节。

---

## 第一步：模板标准化

从用户提供的示例中提取模板结构。

运行 template-extractor subagent（调度方式见 `protocols/agent-dispatch.md` template-extractor 章节）：

```
你是 template-extractor subagent。

任务：分析用户提供的示例，提取可复用的模板结构。

示例内容：
{用户提供的示例}

要求：
1. 识别固定部分（所有单元相同）和变量部分（每单元不同）
2. 用 {{variable_name}} 标记变量位置
3. 提取质量标准（什么让这个示例是"好的"）
4. 识别常见错误（什么会让输出变差）

输出：
## 模板结构

{提取的模板，变量用 {{name}} 标记}

## 变量定义

| 变量名 | 说明 | 取值规则 | 示例 |
|--------|------|---------|------|
| {{variable_1}} | {说明} | {规则} | {示例} |

## 质量标准（可量化）

1. {标准 1}：{如何判断 1-10 分}
2. {标准 2}：{如何判断 1-10 分}
3. {标准 3}：{如何判断 1-10 分}

## 常见错误

- {错误 1}：{如何避免}
- {错误 2}：{如何避免}
```

在开始批量生成前，将模板展示给用户并自动进入第二步：

```
我提取了以下模板，如需调整请现在说明；否则将自动进入变量数据准备阶段：

{模板预览}

变量：{变量列表}
质量标准：{标准列表}
```

---

## 第二步：变量数据准备

根据变量定义，准备每个生成单元的变量值。

如果变量来自文件/表格，读取并解析。
如果变量需要推断，使用规则生成。
如果变量需要用户提供，列出清单请用户确认。

生成变量数据表（写入 `autoloop-results.tsv`，TSV schema 见 `protocols/loop-protocol.md` 统一 TSV Schema 章节）：

```
（TSV 格式见 protocols/loop-protocol.md 统一 TSV Schema）
001          generate    pending    score          —               —        变量: {variable_1}={值}, {variable_2}={值}
002          generate    pending    score          —               —        变量: {variable_1}={值}, {variable_2}={值}
```

变量的完整取值记录到 `autoloop-findings.md`，不放在 results.tsv。

---

## 第三步：并行批量生成

将所有生成单元分配给 generator subagents，并行执行（调度规范见 `protocols/agent-dispatch.md`）。

每批并行数量：最多 5 个（防止输出质量因并行过多下降）。

每个 generator subagent 的指令：

```
你是 generator subagent，负责生成以下内容单元。

模板：
{模板内容}

本单元变量：
- {{variable_1}}: {值}
- {{variable_2}}: {值}

质量标准：
1. {标准 1}（满分 10 分）
2. {标准 2}（满分 10 分）
3. {标准 3}（满分 10 分）

常见错误（必须避免）：
- {错误 1}
- {错误 2}

要求：
1. 严格按模板结构生成
2. 变量值自然融入内容（不要机械地"填空"）
3. 保持语调/风格一致
4. 生成后自行检查是否满足所有质量标准

输出格式：
---UNIT-START-{unit_id}---
{生成内容}
---UNIT-END-{unit_id}---

---QUALITY-{unit_id}---
标准1得分: {N}/10 — {理由}
标准2得分: {N}/10 — {理由}
标准3得分: {N}/10 — {理由}
综合得分: {N}/10
存在问题: {如有}
---QUALITY-END-{unit_id}---
```

---

## 第四步：逐项质量评分

每个单元生成完成后，运行独立的 quality-checker subagent（调度方式见 `protocols/agent-dispatch.md` quality-checker 章节）：

```
你是 quality-checker subagent，对以下生成内容进行独立质量评分。

内容：
{生成的内容}

质量标准：
1. {标准 1}：{评分说明}
2. {标准 2}：{评分说明}
3. {标准 3}：{评分说明}

评分规则：
- 8-10：优秀，直接通过
- 7：及格，标注改进点
- 5-6：需要改进，标注主要问题
- 1-4：需要重新生成，说明原因

注意：你的评分独立于生成者的自评。如果分歧 > 2 分，以你的评分为准。

输出：
得分: {N}/10（{通过/需改进/重生成}）
主要问题（如有）：
- {问题 1}
- {问题 2}
改进建议：{具体建议}
```

---

## 重试机制

重试上限见 `protocols/loop-protocol.md` 统一重试规则（默认 2 次）。对于评分低于 `protocols/quality-gates.md` T4 单元通过阈值的单元，触发重试：

**第 1 次重试**：
- 将 quality-checker 的问题反馈给 generator
- 保留原模板，针对具体问题修改

```
上次生成有以下问题：
{quality-checker 的反馈}

请保留整体结构，重点改进：
{具体改进点}
```

**第 2 次重试（最后一次）**：
- 换一个不同的生成策略
- 完全重新生成，不参考之前的版本
- 如果仍低于 `protocols/quality-gates.md` T4 单元通过阈值，标注为"需人工审查"，继续其他单元

---

## 批次进度追踪

实时更新 `autoloop-results.tsv`（TSV schema 见 `protocols/loop-protocol.md` 统一 TSV Schema 章节）：

```
（TSV 格式见 protocols/loop-protocol.md 统一 TSV Schema）
001          generate    pass      score          8.5             —        重试0次
002          generate    pass      score          7.2             —        重试1次: 第一次生成语调不对
003          generate    review    score          6.0             —        重试2次仍未达标: 变量信息不足
004          generate    pending   score          —               —        生成中
```

每完成 10% 输出进度：

```
进度：{完成数}/{总数} ({百分比}%)
  通过：{N} 个（{平均分}/10）
  待重试：{N} 个
  需人工：{N} 个

预计完成时间：{估算}
```

---

## 最终汇总

所有单元完成后，生成汇总报告（文件名见 `protocols/loop-protocol.md` 统一输出文件命名章节）：

```markdown
## 批量生成完成报告

### 总体结果

| 状态 | 数量 | 占比 |
|------|------|------|
| 一次通过（≥7分）| {N} | {%} |
| 重试后通过 | {N} | {%} |
| 需人工审查 | {N} | {%} |
| **总计** | {总N} | 100% |

通过率：{X}%（目标阈值见 protocols/quality-gates.md T4 通过率章节）
平均得分：{X}/10（目标阈值见 protocols/quality-gates.md T4 平均分章节）

### 质量分布

| 分数段 | 数量 |
|--------|------|
| 9-10 | {N} |
| 8-9  | {N} |
| 7-8  | {N} |
| <7   | {N} |

### 常见问题（Top 3）

1. {最常见问题}：影响 {N} 个单元
2. {第二}：影响 {N} 个单元
3. {第三}：影响 {N} 个单元

### 需人工审查的单元

| 单元ID | 问题 | 建议 |
|--------|------|------|
| {ID}   | {问题} | {建议} |

### 输出文件

所有通过的内容已写入：{output_path}（来自 autoloop-plan.md，变量名见 protocols/loop-protocol.md）
```

---

## 每轮 REFLECT 执行规范

每批生成完成（或每完成 25% 进度）后执行。REFLECT 必须写入文件，不能只在思考中完成（规范见 `protocols/loop-protocol.md` REFLECT 章节）：

写入 `autoloop-findings.md` 的4层反思结构表（问题登记/策略复盘/模式识别/经验教训），格式见 `templates/findings-template.md`：

- **问题登记**：记录本批发现的模板缺陷、变量数据问题、质量评分异常
- **策略复盘**：生成策略/模板参数/质量标准的效果评估（保持 | 避免 | 待验证）（策略评价枚举见 protocols/loop-protocol.md 统一状态枚举）
- **模式识别**：哪类变量值容易导致低分、哪些质量标准是瓶颈
- **经验教训**：模板优化/生成提示词/质量评估方法的有效性总结

---

## 输出文件格式

根据内容类型选择输出格式：

- **文案/报告**：Markdown 文件，每个单元用 `---` 分隔
- **代码**：独立文件，每个单元一个文件
- **结构化数据**：TSV 或 JSON
- **邮件**：每封邮件独立 Markdown，包含 Subject / Body / Variables

所有输出文件写入 `{output_path}`（来自 `autoloop-plan.md` 的 `output_path` 字段，变量名见 `protocols/loop-protocol.md` 统一参数词汇表）。不使用 `./output/` 相对路径。
