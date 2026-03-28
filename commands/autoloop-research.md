---
name: autoloop-research
description: >
  AutoLoop T1: 全景调研模板。多维度并行搜索 + 交叉验证 + 覆盖率驱动迭代。
  质量门禁阈值见 references/quality-gates.md T1 行。
  触发：/autoloop:research 或任何需要系统性调研的任务。
---

# AutoLoop T1: Research — 全景调研

## 执行前提

读取 `autoloop-plan.md` 获取任务参数。如果文件不存在，先通过 `/autoloop:plan` 配置。

**Round 2+ OBSERVE 起点**：先读取 `autoloop-findings.md` 反思章节，获取遗留问题、有效/无效策略、已识别模式、经验教训，再扫描当前状态。详见 `references/loop-protocol.md` OBSERVE Step 0 章节。

- **经验库读取**: 读取 `references/experience-registry.md` 中与当前任务类型和目标维度匹配的条目，识别状态为「推荐」或「候选默认」的策略，传递到 DECIDE 阶段参考

---

## 调研维度生成规则

如果用户没有指定维度，根据调研主题自动生成。以下是常见主题的标准维度集：

### 技术/工具选型
1. 功能完整性（核心功能覆盖）
2. 性能指标（基准测试数据）
3. 成熟度与稳定性（版本历史、issue 活跃度）
4. 社区与生态（GitHub stars、npm下载量、贡献者数）
5. 文档质量（官方文档、教程、示例）
6. 商业支持（许可证、企业支持、SLA）
7. 与目标系统的兼容性
8. 迁移成本（从现有方案迁移的难度）

### 市场/商业调研
1. 市场规模与增长率
2. 主要玩家分析（TOP 5）
3. 用户需求画像
4. 定价模型分析
5. 技术壁垒
6. 监管环境
7. 成功案例研究
8. 失败案例与风险

### 竞品分析
1. 功能对比矩阵
2. 定价策略
3. 目标用户群
4. 技术架构差异
5. 市场占有率
6. 用户评价（G2、Capterra、Reddit）
7. 增长轨迹
8. 差异化优势

### 问题/解决方案调研
1. 问题根因分析
2. 已有解决方案清单
3. 每种方案的优缺点
4. 实施复杂度
5. 成本估算
6. 风险评估
7. 推荐方案

---

## 第一轮：维度规划 + 初始搜索

### OBSERVE（第1轮基线采集）

第1轮无历史数据，执行基线采集：当前发现数 = 0，已覆盖维度 = 0，所有质量门禁得分 = 0。
将此作为 iteration 0 基线写入 `autoloop-progress.md`。详见 `references/loop-protocol.md` 第1轮 Bootstrap 规则。

### 1.1 维度规划

确定本次调研的维度列表（最多 8 个，少量精准好过多而泛）。

将维度写入 `autoloop-plan.md` 的"调研维度"字段。

### 1.2 并行搜索

为每个维度分配一个 researcher subagent，并行执行（调度规范见 `references/agent-dispatch.md`）。每个 subagent 的指令：

```
你是 researcher subagent，负责调研以下维度：

主题：{调研主题}
维度：{具体维度名称}
任务：搜索并整理这个维度下的关键信息

要求：
1. 找到至少 3 个独立信息来源
2. 提取关键数据点（数字、事实、引用）
3. 标注每个信息点的来源 URL 和可信度（{N}%）
4. 如果发现矛盾信息，同时列出并说明

输出格式：
## {维度名称}

### 关键发现
- {发现 1}（来源：{URL}，可信度：高）
- {发现 2}（来源：{URL}，可信度：中）

### 数据点
- {数据 1}：{值}（来源：{URL}）

### 信息缺口
- {哪些重要信息未找到}

### 相关维度
- {发现的其他相关主题，供主循环扩展范围用}
```

### 1.3 结果整合

所有 researcher subagent 完成后：
1. 将所有发现追加到 `autoloop-findings.md`
2. 计算初始覆盖率得分（计算方法见 `references/quality-gates.md` 覆盖率门禁章节）
3. 识别信息缺口和矛盾

---

## 质量门禁评分

质量门禁阈值见 `references/quality-gates.md` 知识类任务门禁章节（T1 行）。

CHECK阶段由独立的 research-evaluator subagent 执行评分（调度方式见 references/agent-dispatch.md 独立评分器章节）。research-evaluator 只接收 findings.md 产出物，不接收执行过程信息，按 quality-gates.md 锚点盲评。

评分时必须同时输出分数、判据（命中哪个锚点区间）、证据（来源URL或文件行号）。缺少任一项的评分无效，该维度记为待检查。

计分示例（说明性，计算规则以 quality-gates.md 为准）：
- 覆盖率 7/8 维度有内容 → 87.5%（是否达标见 quality-gates.md T1 行）
- 可信度 12/15 关键发现有多源印证 → 80%（是否达标见 quality-gates.md T1 行）
- 一致性 1/8 维度有矛盾 → 87.5%（是否达标见 quality-gates.md T1 行）
- 完整性 43/50 陈述有来源 → 86%（是否达标见 quality-gates.md T1 行）

---

## 轮间决策规则

每轮结束后，根据得分决定下一步（终止层级完整定义见 `references/quality-gates.md` 概述章节）：

### 场景 A：全部达标
```
覆盖率、可信度、一致性、完整性均达到 references/quality-gates.md T1 行规定的阈值
→ 终止迭代，进入结果整合
```

### 场景 B：覆盖率不足
```
→ 对覆盖不足的维度分配新的 researcher subagent
→ 更换搜索策略（不同关键词、不同信息源）
→ 检查是否需要新增维度（来自 subagent 发现的"相关维度"）
```

### 场景 C：可信度不足
```
→ 对只有单一来源的关键发现进行交叉验证
→ 优先搜索一手资料（官方文档、学术论文、原始数据）
→ 标注置信度，在报告中说明不确定性
```

### 场景 D：一致性不足
```
→ 深入调查矛盾维度
→ 识别矛盾来源（时间不同、场景不同、观点不同）
→ 在报告中明确列出争议点，不强行统一
```

### 场景 E：完整性不足
```
→ 对未标注来源的陈述逐一找来源
→ 无法找到来源的陈述改为"待验证"或删除
```

---

## 第 2-N 轮执行

```
OBSERVE：
  读取 autoloop-findings.md 的反思章节（上轮 REFLECT 记录）
  获取遗留问题、有效/无效策略、已识别模式、经验教训
  （Step 0 规范见 references/loop-protocol.md OBSERVE Step 0 章节）
  计算当前各维度得分（计算方法见 references/quality-gates.md 各门禁章节）
  识别最低分维度

ORIENT：
  确定本轮优先处理的维度（最多 3 个）
  制定具体改进策略（不是"继续搜索"，是"搜索 X 来源，用 Y 关键词"）
  排除上轮标记为"避免"的策略

DECIDE：
  分配 subagent（独立维度并行，关联维度串行）
  并行/串行判断规则见 references/agent-dispatch.md
  优先使用上轮标记为"保持"的策略

ACT：
  - **工单生成**: 按 `references/agent-dispatch.md` 对应角色模板生成委派工单，填充任务目标、输入数据、输出格式、质量标准、范围限制、当前轮次、上下文摘要
  执行搜索，整合到 autoloop-findings.md

VERIFY：
  重新计算所有维度得分（计算方法见 references/quality-gates.md）
  对比上轮得分，计算改进量

EVOLVE：
  终止层级判断见 references/quality-gates.md 概述章节
  如某维度连续 2 轮改进 < 3%（相对值），切换策略
  如发现重要新维度，添加到范围
  如预算剩余 < 20%，聚焦到最高优先级维度

REFLECT：
  写入 autoloop-findings.md 的4层反思结构表（见下方 REFLECT 规范）
```

---

## 交叉验证机制

在每轮结束时，运行 cross-verifier subagent（调度方式见 `references/agent-dispatch.md` cross-verifier 章节）：

```
你是 cross-verifier subagent。

任务：检查 autoloop-findings.md 中的关键发现是否存在矛盾。

步骤：
1. 读取所有关键发现
2. 识别同一事实的不同说法
3. 对每个矛盾：
   a. 确认矛盾确实存在（不是措辞不同导致的表面矛盾）
   b. 分析矛盾原因（时间差异/场景差异/方法论差异/真实争议）
   c. 给出处理建议：采用哪个/两者都保留并说明/需要进一步调研

输出矛盾清单：
## 矛盾报告

| 编号 | 维度 | 说法 A（来源） | 说法 B（来源） | 分析 | 处理建议 |
|------|------|-------------|-------------|------|---------|
```

---

## 信息来源优先级

可信度分级完整定义见 `references/quality-gates.md` 可信度门禁章节（信息来源可信度分级）：

1. 官方文档、官方博客、官方 GitHub
2. 经过同行评审的研究报告（Gartner、Forrester、IDC）
3. 知名技术媒体（TechCrunch、HN、InfoQ）
4. 专家博客（有具体作者、有技术背书）
5. Reddit/Stack Overflow 高票回答
6. 一般博客文章
7. 未注明来源的内容（可信度：低，必须交叉验证）

---

## 结果整合

达到终止条件后，整合最终报告（文件名见 `references/loop-protocol.md` 统一输出文件命名章节）。

### findings.md 最终结构：

```markdown
# AutoLoop Research Findings

## 执行摘要
- 主题：{调研主题}
- 调研轮次：{N} 轮
- 最终得分：覆盖率 {X}% / 可信度 {X}% / 一致性 {X}% / 完整性 {X}%
- 关键结论（3-5条）

## 维度详情

### {维度 1}
{整合后的内容，按重要性排序}

来源清单：
- [{来源名}]({URL}) — 可信度：高

### {维度 2}
...

## 争议与不确定性

| 议题 | 说法 A | 说法 B | 本报告立场 |
|------|--------|--------|----------|

## 信息缺口

以下重要信息未能找到或验证：
- {缺口 1}（影响级别：P1/P2/P3）

## 推荐阅读

按重要性排序的关键资源。
```

---

## 进度追踪格式

每轮在 `autoloop-progress.md` 中追加完整 8 阶段记录（OBSERVE/ORIENT/DECIDE/ACT/VERIFY/SYNTHESIZE/EVOLVE/REFLECT），格式见 `references/loop-protocol.md` 循环日志格式章节。以下为 T1 Research 的简化摘要示例（实际记录必须包含所有 8 个阶段）：

```markdown
## 第 {N} 轮 — {开始时间}

**本轮目标**：提升 {维度} 覆盖率

**执行记录**：
- {subagent 1}：{任务} → {结果}
- {subagent 2}：{任务} → {结果}

**本轮得分**：
- 覆盖率：{上轮} → {本轮}（{+/-变化}）
- 可信度：{上轮} → {本轮}
- 一致性：{上轮} → {本轮}
- 完整性：{上轮} → {本轮}

**决策**：{继续迭代/终止原因}
**下一轮重点**：{具体计划}

---
```

---

## 每轮 REFLECT 执行规范

每轮（包括第一轮）结束后，在 EVOLVE/终止判断之后执行。REFLECT 必须写入文件，不能只在思考中完成（规范见 `references/loop-protocol.md` REFLECT 章节）：

写入 `autoloop-findings.md` 的4层反思结构表（问题登记/策略复盘/模式识别/经验教训），格式见 `assets/findings-template.md`：

- **问题登记**：记录本轮发现的信息空白、来源冲突、数据质量问题
- **策略复盘**：搜索策略/验证方法/整合方式的效果评估（保持 | 避免 | 待验证）（策略评价枚举见 references/loop-data-schema.md 统一状态枚举）
- **模式识别**：哪些来源一直提供高质量信息、哪些维度反复出现空白
- **经验教训**：搜索关键词/数据源/分析方法的有效性总结
- **经验写回**: 将本轮策略效果写入 `references/experience-registry.md`（策略ID、适用场景、效果评分、执行上下文，遵循效果记录表格式）
