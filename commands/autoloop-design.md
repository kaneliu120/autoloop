---
name: autoloop-design
description: >
  AutoLoop T3: 产品设计模板。从 T1/T2 调研结论出发，通过需求分析、方案设计、可行性评审三个阶段，
  产出可直接交给 T4 开发交付的确认方案文档。
  方法论：JTBD 问题界定 + RICE 优先级 + Shape Up 范围控制 + Spec-Driven 产出。
  质量门禁阈值见 references/gate-manifest.json T3。
  触发：/autoloop:design 或任何需要产品设计/方案文档化的任务。
---

# AutoLoop T3: Design — 产品设计

## 执行前提
读取 `autoloop-plan.md` 获取任务参数。

Round 2+ 的 OBSERVE 起点：先读取 `autoloop-findings.md` 反思章节和 `references/experience-registry.md`。

## Phase 1: 需求分析与提炼

### 目标
从 T1/T2 产出 + 用户需求中提取结构化需求。

### 方法论
- JTBD 问题界定：When [situation], I want [motivation], so I can [outcome]
- RICE 优先级：Reach × Impact / Confidence / Effort

### 执行

**并行 subagent**：

planner subagent：
- 读取 T1 findings 和 T2 决策推荐
- 提取核心需求和用户痛点
- 生成 JTBD 定义
- 按 RICE 排序需求清单
- 生成用户故事（As a/I want/So that + Given-When-Then 验收标准，INVEST 标准）
- 定义范围边界（IN/OUT 列表）

researcher subagent（如有信息缺口）：
- 补充 T1/T2 未覆盖的技术或市场信息

### 产出

- **问题重述（Problem Restatement）**：用一段话重述用户的需求，确认理解。格式：
  - "用户想要解决的问题是：{...}"
  - "范围内（IN）：{列表}"
  - "范围外（OUT）：{列表}"
  - "关键假设：{列表}"
  
  此重述在 Phase 2 开始前由用户确认。如果 planner 对需求有疑问，应在此阶段主动列出。
- 问题陈述（Problem Statement）
- JTBD 定义
- 需求清单（RICE 排序）
- 用户故事 + 验收标准
- 范围定义（IN/OUT）

### Phase 1 门禁
- [ ] 问题陈述明确（1 段话：什么问题、为谁、为什么现在、成功指标）
- [ ] 至少 3 条用户故事，每条有 Given-When-Then 验收标准
- [ ] 范围边界已定义（IN + OUT + 理由）
- [ ] 需求按优先级排序

## Phase 2: 方案设计

### 目标
技术方案 + 产品方案，形成完整设计文档。

### 方法论
- Shape Up 范围控制：固定时间，可变范围
- Spec-Driven 产出：结构化规格驱动实现

### 执行

**并行 subagent**：

technical-architect subagent：
- 读取 Phase 1 需求清单
- 读取目标代码库（如已有）
- 设计数据模型
- 设计 API Schema 和路由
- 制定迁移策略
- 评估技术风险

frontend-architect subagent（如涉及前端）：
- 组件结构设计
- 状态管理方案
- API 调用模式

db-specialist subagent（如涉及数据库变更）：
- 数据模型详细设计
- 迁移脚本骨架
- 性能影响评估

### Phase 2 可选：多方案竞争模式

当用户在 autoloop-plan.md 中设置 `attempt_mode: true` 时，Phase 2 采用竞争模式：

1. **并行派遣**：同时启动 2-3 个 technical-architect subagent，每个独立设计方案
   - 每个 subagent 收到相同的需求输入（Phase 1 产出）
   - 每个 subagent 独立工作，互不可见
   - 使用 `isolation: "worktree"` 确保文件隔离

2. **评分选优**：所有方案完成后，VERIFY 阶段对每个方案独立评分
   - 使用 T3 的 5 个质量门禁维度评分
   - 选择总分最高的方案进入 Phase 3

3. **记录备选**：未选中的方案摘要记入 findings.md，作为备选参考

**注意**：

- 此模式消耗 2-3x 的 API 预算，仅在方案质量极为关键时启用
- 不改变 OODA 循环的单策略隔离（经验归因仍然有效）
- 默认不启用，需在 plan 中显式设置

### 产出
方案文档（使用 `assets/delivery-template.md` 格式）：
- 问题描述（含 T1/T2 上下文）
- 影响范围（修改文件、DB 变更、API 变更、前端变更）
- 具体方案（数据模型、API Schema、路由、迁移策略）
- 实施步骤（含依赖关系排序）
- 风险与缓解
- 验收标准（功能 + 技术）

### Phase 2 门禁
- [ ] 方案文档 5 个必要章节齐全（问题/影响/方案/步骤/验收）
- [ ] 数据模型已定义（如涉及 DB 变更）
- [ ] API 接口已定义（路径、方法、Schema）
- [ ] 实施步骤有依赖关系排序
- [ ] 风险已识别并有缓解方案

## Phase 3: 可行性评审

### 目标
独立评审方案的完整性、可行性、需求覆盖率。

### 方法论
- Definition of Ready 检查
- 独立评估者原则（评审 agent ≠ 设计 agent）

### 执行

feasibility-reviewer subagent（独立评审）：
- 逐条检查需求覆盖率（每条需求是否映射到设计方案）
- 评估技术可行性（架构是否合理、依赖是否可控）
- 检查范围精确度（IN/OUT 是否明确、工作量是否可估）
- 验证风险评估完整性
- 打出 5 维度评分

### 产出
- 评审报告（通过/需修改）
- 5 维度评分
- 最终确认的方案文档 → T4 Phase 1 的输入

### Phase 3 门禁
质量门禁阈值见 `references/gate-manifest.json` T3：
- Hard: design_completeness ≥ 7, feasibility_score ≥ 7, requirement_coverage ≥ 7
- Soft: scope_precision ≥ 7, validation_evidence ≥ 7

## 质量门禁评分

CHECK 阶段由独立 evaluator 按以下维度评分（0-10）：

| 维度 | 1-3 (不通过) | 4-6 (部分) | 7-8 (通过) | 9-10 (优秀) |
|------|-------------|-----------|-----------|------------|
| design_completeness | 多数需求无设计映射 | 部分需求有设计 | ≥90% 需求有完整设计 | 100% + 边界情况 |
| feasibility_score | 技术方案不可行 | 部分可行有风险 | 架构合理，风险可控 | 已验证 + POC |
| requirement_coverage | 需求断裂严重 | 50-80% 可追溯 | ≥95% 可追溯 | 100% 双向追溯 |
| scope_precision | 无范围定义 | 部分 IN/OUT | 完整 + 依赖已识别 | + 工作量估算 |
| validation_evidence | 无评审 | 自评审 | 独立评审 + 风险评估 | + POC 验证 |

## 每轮 REFLECT 执行规范

T3 Phase 1（探索期）的 REFLECT 与 T1 类似：策略归因可选，重点写反思摘要。
Phase 2-3 的 REFLECT 推荐写完整结构化反思（strategy_id + effect + delta）。

写入 `autoloop-findings.md` 的 4 层反思结构表。

## 交付物

T3 完成后产出的核心文件：
- 方案文档（`{doc_output_path}/{功能名}-{date}.md`，delivery-template.md 格式）
- `autoloop-findings.md`（需求分析过程、设计决策、评审结论）
- `autoloop-progress.md`（每阶段进度记录）

方案文档作为 T4 Deliver Phase 1 的直接输入。
