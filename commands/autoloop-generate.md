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

### 派遣

角色：planner（职责定义见 `protocols/agent-dispatch.md`，T4 兼任模板提取）

### 本次范围

- 用户提供的示例：{示例内容}

### 执行流程

1. 分析示例，识别固定部分和变量部分（用 `{{variable_name}}` 标记）
2. 提取质量标准（什么让示例是"好的"）和常见错误（什么会让输出变差）
3. 输出：模板结构 + 变量定义表 + 质量标准 + 常见错误

在开始批量生成前，将模板展示给用户并自动进入第二步：

```text
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

生成变量数据表（写入 `autoloop-results.tsv`，TSV schema 见 `protocols/loop-protocol.md` 统一 TSV Schema 章节）。

变量数据写入 `autoloop-findings.md`，不进 TSV。TSV 的 details 列使用 `key=value;key=value` 格式（如 `unit_id=001;quality=通过`），不记录变量键值对。

---

## 第三步：并行批量生成

### 派遣

角色：generator xN，每人负责一批单元（职责定义见 `protocols/agent-dispatch.md`）

### 本次范围

- 模板：{模板内容}
- 变量数据：{每个单元的变量值}
- 质量标准：{标准列表}
- 常见错误：{错误列表}

### 执行流程

1. 每批最多 5 个 generator 并行（防止输出质量因并行过多下降）
2. 每个 generator 严格按模板结构生成，变量自然融入内容
3. 生成后自行检查是否满足所有质量标准
4. 按角色定义的输出格式交付：UNIT-START/UNIT-END 包裹的内容 + 质量自评分

---

## 第四步：逐项质量评分

### 派遣

角色：scorer，独立于 generator（职责定义见 `protocols/agent-dispatch.md`）

### 执行流程

1. 读取 `protocols/quality-gates.md` T4 专属门禁（通过率、平均分）
2. 对每个生成内容独立评分，不受 generator 自评影响
3. 分歧 > 2 分时以 scorer 评分为准
4. 按门禁阈值判定：通过 / 需改进 / 重生成

---

## 重试机制

重试上限见 `protocols/loop-protocol.md` 统一重试规则（默认 2 次）。对于评分低于 `protocols/quality-gates.md` T4 专属门禁中平均分阈值的单元，触发重试：

**第 1 次重试**：
- 将 scorer 的问题反馈给 generator
- 保留原模板，针对具体问题修改

**第 2 次重试（最后一次）**：
- 换一个不同的生成策略
- 完全重新生成，不参考之前的版本
- 如果仍低于阈值，标注为"需人工审查"，继续其他单元

---

## 批次进度追踪

实时更新 `autoloop-results.tsv`（TSV schema 见 `protocols/loop-protocol.md` 统一 TSV Schema 章节）。

每完成 10% 输出进度：

```text
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
| 一次通过（达标）| {N} | {%} |
| 重试后通过 | {N} | {%} |
| 需人工审查 | {N} | {%} |
| **总计** | {总N} | 100% |

通过率：{X}%（目标阈值见 protocols/quality-gates.md T4 通过率门禁）
平均得分：{X}/10（目标阈值见 protocols/quality-gates.md T4 平均分门禁）

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

所有通过的内容已写入：{output_path}（来自 autoloop-plan.md）
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
