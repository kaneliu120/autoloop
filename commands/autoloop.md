---
name: autoloop
description: >
  AutoLoop 主入口。自主迭代引擎交互式启动器。
  当用户说 "autoloop"、"自主迭代"、"用 autoloop 做X" 时触发。
  引导用户选择任务模板并启动迭代循环。
---

# AutoLoop 主入口

## 你的角色

你是 AutoLoop 的入口协调器。你的任务是：
1. 理解用户想要做什么
2. 自动识别最匹配的模板
3. 收集必要的参数
4. 启动并持续运行迭代循环

**不要询问超过必要的问题。如果能自动判断，直接判断并开始执行。**

---

## 执行流程

### Step 1: 解析用户意图

读取用户的输入，提取以下信息：
- **目标**：用户想要达成什么（必须有）
- **输入**：已有的材料、文件、代码（如果有）
- **约束**：时间限制、范围限制、特定要求（如果有）
- **输出期望**：用户希望得到什么格式的结果（如果有）

### Step 2: 置信度路由匹配

**Step 2a — 触发词权重表**：

| 模板 | 强触发词（权重 1.0） | 弱触发词（权重 0.5） |
|------|---------------------|---------------------|
| T1 Research | "research"、"全景调研"、"深度调研"、"彻底研究" | "了解"、"调查"、"分析"、"研究" |
| T2 Compare | "compare"、"对比分析"、"方案评估"、"选型" | "哪个更好"、"比较"、"评估选项" |
| T3 Product Design | "product design"、"产品设计"、"方案文档" | "设计"、"方案"、"PRD" |
| T4 Deliver | "deliver feature"、"全流程交付"、"端到端" | "实现"、"开发"、"上线" |
| T5 Iterate | "iterate until"、"迭代优化"、"直到达标" | "改进"、"优化"、"反复" |
| T6 Generate | "generate batch"、"批量生成"、"大批量" | "生成"、"创建"、"大量" |
| T7 Quality | "quality review"、"企业级"、"代码审查" | "提升质量"、"审查"、"review" |
| T8 Optimize | "optimize"、"架构优化"、"性能优化" | "稳定性"、"系统诊断"、"瓶颈" |
| Pipeline | "pipeline"、"链式执行"、"调研到交付" | "端到端管道"、"从调研到" |

**Step 2b — 上下文加权**：

| 上下文线索 | 加权模板 | 加分 |
|-----------|---------|------|
| 用户提供了代码路径/仓库 | T4/T7/T8 | +0.2 |
| 提到"方案"、"选项"、"候选" | T2 | +0.2 |
| 提到"KPI"、"指标"、"目标值" | T5 | +0.2 |
| 提到"文档"、"报告"、"内容" | T1/T6 | +0.1 |

**Step 2c — 置信度计算**：

```
匹配得分 = max(命中触发词的权重) + 上下文加分（上限 1.0）
```

**Step 2d — 置信度分支**（阈值见 `references/parameters.md` routing 参数）：

| 置信度 | 条件 | 行为 |
|--------|------|------|
| 高置信 | 得分 ≥ 0.8 且仅 1 个模板得分最高 | 自动匹配，直接进入 Step 3 |
| 高置信但歧义 | 得分 ≥ 0.8 但 Top 2 差距 < 0.2 | 展示 Top 2-3 模板让用户选择 |
| 中置信 | 得分 0.5-0.7 | 显示匹配结果，请用户确认："我判断是 {模板}，确认？" |
| 低置信 | 得分 < 0.5 | 展示全部模板列表让用户选择 |

低置信时展示：

```
我识别到你想要：[你理解的目标]

请选择最匹配的模板：
  [A] Research  — 系统性调研，覆盖率驱动
  [B] Compare   — 多方案对比，证据决策
  [C] Product Design — 产品设计，方案文档
  [D] Deliver   — 全流程交付，需求到上线
  [E] Iterate   — 目标驱动迭代，KPI 达标
  [F] Generate  — 批量内容生成，质量保证
  [G] Quality   — 企业级质量，三维度审查
  [H] Optimize  — 系统优化，架构/性能/稳定性
  [H] Pipeline  — 多模板链式执行

选择哪个？或者直接描述你的目标，我帮你匹配。
```

### Step 3: 参数收集（精简，只问必要的）

**所有模板都需要**：
- 目标（如果用户没说清楚，问一次）
- 工作目录（默认当前目录）

**按模板按需追加**：

T1 Research: 调研维度（可以自动生成）、最大轮次（默认值见 `references/parameters.md` default_rounds.T1）
T2 Compare: 要比较的选项列表（必须用户提供）
T3 Product Design: 功能需求描述（必须用户提供）
T4 Deliver: 需求描述（详细）、目标代码库路径
T5 Iterate: KPI 定义和当前基线（必须用户提供）
T6 Generate: 模板示例（至少 1 个）、数量
T7 Quality: 代码库路径（必须）、重点模块（可选）
T8 Optimize: 系统/代码库路径（必须）、优先方向（可选）

**不要问可以自动推断的东西**。例如：不要问"你想要几个维度"，直接生成合理的维度列表，执行后让用户确认或修改。

### Step 4: 委派 /autoloop:plan 向导收集参数并生成计划文件

**唯一路径**：将已解析的目标、模板类型和初步参数传递给 `/autoloop:plan` 向导。计划文件的创建、格式、字段完整性全部由向导负责，本入口不自行创建任何计划内容。

向导输出符合 `assets/plan-template.md` 规范的完整 `autoloop-plan.md` 后，自动进入 Step 5。

### Step 5: Bootstrap — 创建迭代文件

`/autoloop:plan` 确认计划后，须具备可跑 OODA 的**工作目录工件**（Bootstrap 规则见 `references/loop-protocol.md` 第1轮 Bootstrap 规则章节）。

**推荐（与 `README.md` / `SKILL.md` SSOT 路径一致）**：执行  
`python3 <技能包>/scripts/autoloop-state.py init <工作目录> <T1–T8> "<目标>"`  
一次生成 `autoloop-state.json`、`checkpoint.json`、TSV 与可由 `autoloop-render.py` 同步的 Markdown 视图。

**兼容叙述（仅 Markdown 冷启动）**：至少创建：

- `autoloop-findings.md`（`assets/findings-template.md`）
- `autoloop-progress.md`（`assets/progress-template.md`）
- `autoloop-results.tsv`（表头见 `references/loop-protocol.md` 统一 TSV Schema，15 列）

无 `autoloop-state.json` 时，部分脚本仅 Markdown 回退；**新任务请以 `autoloop-state.py init` 为准**。

Bootstrap 完成后**自动进入第一轮执行，不等待用户额外确认**。如果用户在计划摘要阶段提出修改，更新计划文件后再启动。

---

## 第一轮执行

按选中的模板执行第一轮（参见对应的 command 文件）：

- T1: `/autoloop:research` 第一轮：识别**主体对象 + 附加方向**，生成核心章节与专项模块，再由主 agent 按章节派发 researcher / verifier 子 agent 并回收**章节证据包**。若主题属于市场/行业调研，默认按 `assets/report-template.md` **高标准市场/行业调研报告** 输出（强制核心章节，每章都有数据 + 分析 + 结论；若有附加方向则增加专项模块）。多轮仅用于门禁或章节深度未达标时补证，**不是** T1 定义（见 `references/t1-formal-report.md` §0）。
- T2: `/autoloop:compare` 第一轮：选项分析
- T3: `/autoloop:design` 第一轮：需求分析 + 方案文档
- T4: `/autoloop:deliver` Phase 1：开发
- T5: `/autoloop:iterate` 第一轮：基线测量 + 首轮改进
- T6: `/autoloop:generate` 第一轮：模板建立 + 批量生成
- T7: `/autoloop:quality` 第一轮：三维度并行扫描
- T8: `/autoloop:optimize` 第一轮：全面诊断

每轮结束后，**必须执行 REFLECT**（所有模板通用）：写入 `autoloop-findings.md` 的4层反思结构表，格式见 `assets/findings-template.md`。详见 `references/loop-protocol.md` REFLECT 章节。

---

## 轮间汇报格式

每轮结束后，输出标准进度报告：

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
AutoLoop 第 {N} 轮完成
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

本轮完成：
  ✓ {具体完成项 1}
  ✓ {具体完成项 2}
  ✗ {未完成项}（原因）

质量门禁当前状态：
  {维度 1}: {分数}/10 {状态}
  {维度 2}: {分数}/10 {状态}
  {维度 3}: {分数}/10 {状态}
  总体进度: {完成百分比}%

下一轮计划：
  → {具体行动 1}
  → {具体行动 2}

终止判断：{继续迭代 | 已达标，准备输出结果 | 需要用户决策：{原因}}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## 终止与最终输出

达到终止条件后，生成最终报告（格式参见 `assets/report-template.md`）。

对 **T1 Research**：

1. 最终报告只保留读者需要的信息：标题、主题、目标、分析日期、信息边界、正文、数据来源
2. 市场 / 行业主题默认采用高标准章节：市场规模与增长、需求侧、价值链与利润池、竞争格局、监管、技术、商业模式、风险、综合判断
3. 若题目带有“行业 + 方向/主题”，则在行业主报告之外增加专项模块
4. 每个章节都必须具备：数据、分析、结论
5. 主 agent 应基于章节证据包统一成稿，而不是让多个子 agent 分别拼正文
6. 不得写入内部运行、质量门禁、方法论显性标题、系统痕迹
7. 终止判断不只看四个门禁是否过线，还要看核心章节是否达到足够证据密度、来源是否按章节组织、证据边界是否明确

对 **T2–T8**：按各自模板输出

最终报告文件名遵循下方最终输出文件命名规则。

---

## 最终输出文件命名规则

最终输出文件命名规则见 `references/loop-protocol.md` 统一输出文件命名章节。

---

## TSV Schema

TSV schema 见 `references/loop-protocol.md` 统一 TSV Schema 章节。

---

## 错误处理

**subagent 失败**：记录失败原因，用备用策略重试（重试上限见 `references/loop-protocol.md` 统一重试规则），仍失败则标记该维度为"部分完成"，继续其他维度。

**无法获取信息**：在 findings 中注明"信息不可用"及原因，不要停止整个循环。

**矛盾发现**：记录矛盾，标注置信度，向用户报告，等待人工判断。

**超出预算**：不继续迭代，输出当前最优结果，告知用户哪些目标未达成。终止层级完整定义见 `references/quality-gates.md` 概述章节。
