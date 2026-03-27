---
name: autoloop-research
description: >
  AutoLoop T1: 全景调研模板。多维度并行搜索 + 交叉验证 + 覆盖率驱动迭代。
  质量门禁阈值见 protocols/quality-gates.md T1 行。
  触发：/autoloop:research 或任何需要系统性调研的任务。
---

# AutoLoop T1: Research — 全景调研

## 执行前提

读取 `autoloop-plan.md` 获取任务参数。如果文件不存在，先通过 `/autoloop:plan` 配置。

**Round 2+ OBSERVE 起点**：先读取 `autoloop-findings.md` 反思章节，获取遗留问题、有效/无效策略、已识别模式、经验教训，再扫描当前状态。详见 `protocols/loop-protocol.md` OBSERVE Step 0 章节。

---

## 调研维度生成规则

如果用户没有指定维度，根据调研主题自动生成。

> 以下为非规范性示例，实际维度应根据调研主题动态生成。

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
将此作为 iteration 0 基线写入 `autoloop-progress.md`。详见 `protocols/loop-protocol.md` 第1轮 Bootstrap 规则。

### 1.1 维度规划

确定本次调研的维度列表（最多 8 个，少量精准好过多而泛）。

将维度写入 `autoloop-plan.md` 的"调研维度"字段。

### 1.2 并行搜索

#### 派遣

角色：researcher xN，每人负责一个维度（职责定义见 `protocols/agent-dispatch.md`）

#### 本次范围

- 调研主题：{主题}
- 维度列表：{每个 researcher 负责的具体维度}

#### 执行流程

1. 每个 researcher 并行执行，搜索对应维度的关键信息
2. 每个 researcher 找到至少 3 个独立信息来源，提取数据点，标注来源 URL 和可信度
3. 按角色定义的输出格式交付：关键发现 + 数据点 + 信息缺口 + 相关维度

### 1.3 结果整合

所有 researcher 完成后：
1. 将所有发现追加到 `autoloop-findings.md`
2. 计算初始覆盖率得分（计算方法见 `protocols/quality-gates.md` 覆盖率门禁章节）
3. 识别信息缺口和矛盾

---

## 质量门禁评分

质量门禁阈值见 `protocols/quality-gates.md` 知识类任务门禁章节（T1 行）。

计分示例（非规范性示例，具体阈值和计算规则以 protocols/quality-gates.md T1 行为准）：
- 覆盖率 7/8 维度有内容 → 87.5%（示例值，阈值见 protocols/quality-gates.md）
- 可信度 12/15 关键发现有多源印证 → 80%（示例值，阈值见 protocols/quality-gates.md）
- 一致性 1/8 维度有矛盾 → 87.5%（示例值，阈值见 protocols/quality-gates.md）
- 完整性 43/50 陈述有来源 → 86%（示例值，阈值见 protocols/quality-gates.md）

---

## 轮间决策规则

每轮结束后，根据得分决定下一步（终止层级完整定义见 `protocols/quality-gates.md` 概述章节）：

### 场景 A：全部达标

```text
覆盖率、可信度、一致性、完整性均达到 protocols/quality-gates.md T1 行规定的阈值
→ 终止迭代，进入结果整合
```

### 场景 B：覆盖率不足

```text
→ 对覆盖不足的维度分配新的 researcher
→ 更换搜索策略（不同关键词、不同信息源）
→ 检查是否需要新增维度（来自 researcher 发现的"相关维度"）
```

### 场景 C：可信度不足

```text
→ 对只有单一来源的关键发现进行交叉验证
→ 优先搜索一手资料（官方文档、学术论文、原始数据）
→ 标注置信度，在报告中说明不确定性
```

### 场景 D：一致性不足

```text
→ 深入调查矛盾维度
→ 识别矛盾来源（时间不同、场景不同、观点不同）
→ 在报告中明确列出争议点，不强行统一
```

### 场景 E：完整性不足

```text
→ 对未标注来源的陈述逐一找来源
→ 无法找到来源的陈述改为"待验证"或删除
```

---

## 第 2-N 轮执行

```text
OBSERVE：
  读取 autoloop-findings.md 的反思章节（上轮 REFLECT 记录）
  获取遗留问题、有效/无效策略、已识别模式、经验教训
  （Step 0 规范见 protocols/loop-protocol.md OBSERVE Step 0 章节）
  计算当前各维度得分（计算方法见 protocols/quality-gates.md 各门禁章节）
  识别最低分维度

ORIENT：
  确定本轮优先处理的维度（最多 3 个）
  制定具体改进策略（不是"继续搜索"，是"搜索 X 来源，用 Y 关键词"）
  排除上轮标记为"避免"的策略

DECIDE：
  分配 researcher（独立维度并行，关联维度串行）
  并行/串行判断规则见 protocols/agent-dispatch.md
  优先使用上轮标记为"保持"的策略

ACT：
  执行搜索，整合到 autoloop-findings.md

VERIFY：
  重新计算所有维度得分（计算方法见 protocols/quality-gates.md）
  对比上轮得分，计算改进量

EVOLVE：
  终止层级判断见 protocols/quality-gates.md 概述章节
  如某维度连续 2 轮改进 < 3%（相对值），切换策略
  如发现重要新维度，添加到范围
  如预算剩余 < 20%，聚焦到最高优先级维度

REFLECT：
  写入 autoloop-findings.md 的4层反思结构表（见下方 REFLECT 规范）
```

---

## 交叉验证机制

### 派遣

角色：analyst（职责定义见 `protocols/agent-dispatch.md`，T1 兼任交叉验证 + 最终质量门禁）

### 执行流程

1. 读取 `autoloop-findings.md` 中的所有关键发现
2. 识别同一事实的不同说法
3. 对每个矛盾：确认矛盾存在 → 分析原因 → 给出处理建议
4. 输出矛盾报告表（编号 / 维度 / 说法A / 说法B / 分析 / 处理建议）

---

## 信息来源优先级

可信度分级完整定义见 `protocols/quality-gates.md` 可信度门禁章节（信息来源可信度分级）。执行搜索时按可信度从高到低优先选择来源（官方文档 > 同行评审报告 > 知名技术媒体 > 专家博客 > 社区高票回答 > 一般博客）。

---

## 结果整合

达到终止条件后，整合最终报告（文件名见 `protocols/loop-protocol.md` 统一输出文件命名章节）。

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
- {缺口 1}（影响：高/中/低）

## 推荐阅读

按重要性排序的关键资源。
```

---

## 进度追踪格式

每轮在 `autoloop-progress.md` 中追加完整 8 阶段记录（OBSERVE/ORIENT/DECIDE/ACT/VERIFY/SYNTHESIZE/EVOLVE/REFLECT），格式见 `protocols/loop-protocol.md` 循环日志格式章节。以下为 T1 Research 的简化摘要示例（实际记录必须包含所有 8 个阶段）：

```markdown
## 第 {N} 轮 — {开始时间}

**本轮目标**：提升 {维度} 覆盖率

**执行记录**：
- {researcher 1}：{任务} → {结果}
- {researcher 2}：{任务} → {结果}

**本轮得分**：
- 覆盖率：{上轮} → {本轮}（{+/-变化}）
- 可信度：{上轮} → {本轮}
- 一致性：{上轮} → {本轮}
- 完整性：{上轮} → {本轮}

**决策**：{继续 / 达标终止 / 预算耗尽 / 用户终止 / 无法继续}
**下一轮重点**：{具体计划}

---
```

---

## 每轮 REFLECT 执行规范

每轮（包括第一轮）结束后，在 EVOLVE/终止判断之后执行。REFLECT 必须写入文件，不能只在思考中完成（规范见 `protocols/loop-protocol.md` REFLECT 章节）：

写入 `autoloop-findings.md` 的4层反思结构表（问题登记/策略复盘/模式识别/经验教训），格式见 `templates/findings-template.md`：

- **问题登记**：记录本轮发现的信息空白、来源冲突、数据质量问题
- **策略复盘**：搜索策略/验证方法/整合方式的效果评估（保持 | 避免 | 待验证）（策略评价枚举见 protocols/loop-protocol.md 统一状态枚举）
- **模式识别**：哪些来源一直提供高质量信息、哪些维度反复出现空白
- **经验教训**：搜索关键词/数据源/分析方法的有效性总结
