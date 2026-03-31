# Experience Registry — 全局经验库

## 概述

经验库是 AutoLoop 第二层反馈循环（方法论自身迭代）的核心组件。它实现经验的跨任务流动，使第 N 次执行比第 1 次更快、更准、更高效。

**与其他文件的关系**：
- `loop-protocol.md`：OBSERVE 阶段读取全局经验；REFLECT 阶段产出经验条目
- `evolution-rules.md`：定义经验分发后的协议变更审批流程
- `findings-template.md`：策略评估表中的 strategy_id 与本库的策略效果表对应

> 版本语义定义见 loop-protocol.md §版本语义定义（唯一权威）。

---

## 经验沉淀流程

```text
经验产出（REFLECT阶段）
  ↓
评估（类型 + 影响层级 + 置信度）
  ↓
分发（按类型和层级写入对应文件）
  ↓
验证（下次同类任务验证经验是否有效）
  ↓
淘汰（连续 2 次验证无效 → 标记废弃）
```

**写回规则**：策略 use_count 达到 2 时，必须补充 mechanism/preconditions/contraindications 三个必填字段（见下方"策略详细描述格式"）。

---

## 经验类型与分发目标

| 经验类型 | 分发目标 | 审批级别 | 示例 |
|---------|---------|---------|------|
| 评分标准缺陷 | quality-gates.md | 低风险：AI自动 | "T6 SQL注入检查容易漏报存储过程" |
| 参数校准 | parameters.md | 中风险：AI推进+下轮验证 | "T1用3轮比5轮效率更高" |
| 策略效果 | 本文件策略效果库 | 低风险：AI自动 | "分模块扫描比全量扫描提升30%" |
| 模板改进 | 对应template文件 | 低风险：AI自动 | "findings表增加根因列更有用" |
| 流程缺陷 | loop-protocol.md 或对应command | 高风险：用户确认 | "T5缺少数据库回滚验证步骤" |
| 门禁阈值调整 | quality-gates.md | 高风险：用户确认 | "T6安全性从9改为8" |

---

## 全局策略效果库

以下表格记录跨任务积累的策略效果数据，供 OBSERVE 阶段参考。

| strategy_id | template | dimension | description | avg_delta | side_effects | use_count | success_rate | status |
|------------|----------|-----------|-------------|-----------|-------------|-----------|-------------|--------|
| （初始为空，随任务执行积累） | | | | | | | | |

**P3-01 主表与审计（实现约定）**：
- **主表**：每个 `strategy_id` **仅保留一行**（`autoloop-experience.py write` 为 upsert，更新 `use_count` / `success_rate` / `avg_delta` / `description` / `status` 等聚合字段）。
- **审计**：与 `experience-registry.md` **同目录** 追加 `experience-audit.md`（每次 `write` 一条；`consolidate` 合并重复行时一条）。（此文件由 `autoloop-experience.py write` 首次调用时自动创建，无需手动创建。）
- **历史重复行**：可执行 `autoloop-experience.py <工作目录> consolidate [--dry-run]`（须能解析到本文件；工作目录下 `references/` 或技能包 `references/` 之一存在本文件）。合并时 **优先按审计**重算 `use_count` / `avg_delta` / `success_rate`；无审计时对各行已有 `avg_delta` 取算术平均（近似）。
- **`multi:`**：`strategy_id` 以 `multi:` 开头时**只写审计**、不修改主表（混合归因，见下文归因规则）。

**P3-06 `multi:` 策略约束（实现约定）**：
- **格式**：`multi:{SNN-描述,SNN-描述}` 或 `multi:{SNN-描述+SNN-描述}`（`+` / `,` 均可，可混用）；须 **恰好一层** 花括号；`multi:` 前缀大小写不敏感。
- **子策略**：至少 **2** 个；每个须匹配与单策略相同的 `SNN-描述` 形式；**不得重复**。
- **write**：`autoloop-experience.py write` 在校验通过前**拒绝**非法 `multi:`；**禁止**对 `multi:` 使用 `--status`（不入主表生命周期）。
- **validate**：`results.tsv` / SSOT `results_tsv` 中 `multi:` 行须通过上述格式校验，且每个子策略须在 findings（或 strategy_history）中可追溯；建议 `side_effect` 注明「混合归因」（与 loop-protocol 一致）。

**P3-02 context 匹配（实现约定）**：
- **`query`**：`--tags`（任务 context_tags）非空时，仅保留与策略 **description 内 context_tags**（`write --tags` 写入、紧跟 `@YYYY-MM-DD` 后的 `[…]`）**交集 ≥ 2** 的策略；无 `--tags` 时不做重叠过滤（首轮冷启动，与 loop-protocol 一致）。
- **context-scoped 补充表**：有效 status 取 **精确匹配**（任务标签集 = 表行标签集）优先；否则在 **任务标签 ⊇ 表行标签** 的行中选 **表行标签数最多** 的一行；再无匹配则用主表全局 `status`。
- **控制器**：`plan.context_tags` 为字符串或字符串列表时传给 `query --tags`；缺省不传（冷启动）。

**write `--mechanism`（可选）**：`autoloop-experience.py write --mechanism "…"` 将机制简述写入主表 `description` 中的 `[mechanism: …]` 片段，便于 `use_count≥2` 时满足「补充 mechanism」类文档要求（与下方策略详细描述格式一致）。**context-scoped 补充表**：当前仅 `query` 读取；**无**独立 `write` 路径将行写入 scoped 区；全量 scoped 写入与「归档区」迁移仍为 v2 / backlog（见清单 F08）。

**write 状态机与 use_count（实现约定）**：
- 无 `--status` 时自动转换的**起点状态**为主表该 `strategy_id` 当前行的 `status`（不得在无 `--status` 时用固定「观察」覆盖「已废弃」等）。
- 「连续 2 次 delta>0 / delta≤0」以 **`experience-audit.md` 中该策略最近一次 `write` 的 score** 与**本轮 `--score`** 比较；`use_count`、`avg_delta`、`success_rate` 亦由审计中同策略全部 `write` 的 score 序列（按时间顺序）+ 本轮重算，与主表仅保留一行 upsert 一致。
- **推荐后应保持**：`query` 将某策略标为 **保持** 后，除非后续 `write` 用 `--effect` 等显式改写，主表该行的 `status`/推荐语义应保持稳定，与「连续 2 次」淘汰逻辑独立（淘汰仅针对验证失败路径）。

**字段说明**：
- strategy_id：策略唯一标识，与 results.tsv 和 findings.md 一致
- template：适用模板（T1-T7，或"通用"）
- dimension：目标维度
- description：策略摘要（一句话，详细描述见下方"策略详细描述格式"）
- avg_delta：各轮写入时 `--score`（单轮分数变化量 delta）的**算术平均值**；与 `use_count`、`success_rate` 同源，**有 `experience-audit.md` 时以审计中该 `strategy_id` 全部 `write` 的 score 序列为准**（`write` 与主表聚合一致）。
- side_effects：已知副作用列表
- use_count：累计使用次数（= 上述 score 序列长度）
- success_rate：产生正向效果的比例（各轮 delta **>** 0 的占比；与晋升规则「delta > 0」一致）
- status：推荐 / 候选默认 / 观察 / 已废弃（生命周期状态枚举）

**扩展字段**：

- avg_cost：平均执行成本（轮次数），当前默认 —（v2 预留，待数据积累后启用）
- confidence：效果数据置信度（低/中/高），**运行时计算**（cmd_write 内部根据 use_count 自动推导，不持久化到表列）— 见下方"confidence 自动计算与升格门槛"
- context_tags：适用上下文标签列表（如 [python, backend, security]），**已激活**（通过 --tags 参数写入 description 字段）— 见下方"context_tags 标准词汇表"
- side_effect_severity：副作用严重度（无/低/中/高），当前默认 无（v2 预留，待数据积累后启用）

### 策略详细描述格式

当策略的 use_count ≥ 2 时，必须补充以下结构化描述（写在策略效果库表格下方，按 strategy_id 索引）：

| 字段 | 必填 | 说明 |
|------|------|------|
| mechanism | 是 | 策略生效的机制（为什么有效） |
| preconditions | 是 | 策略生效的前提条件（什么情况下该用） |
| contraindications | 是 | 策略的禁忌条件（什么情况下不该用） |
| optimal_context | 否 | 最佳使用场景（从成功案例中提炼） |
| failure_mode | 否 | 失败时的典型表现（从失败案例中提炼） |

**示例**：

**S01-parallel-scan**：
- mechanism：将独立维度分配给不同 subagent 并行扫描，利用任务无依赖特性缩短总耗时
- preconditions：维度之间无数据依赖；可用 subagent 数 ≥ 维度数
- contraindications：维度间存在强依赖（如安全扫描需要先完成架构分析）；总维度数 ≤ 2（并行开销超过收益）

---

### context_tags 标准词汇表

以下标签用于标注策略的适用上下文，OBSERVE阶段按标签重叠度过滤推荐策略：

**语言**：`python` | `typescript` | `javascript` | `go` | `rust` | `java`
**层级**：`backend` | `frontend` | `database` | `infrastructure` | `fullstack`
**领域**：`security` | `performance` | `reliability` | `maintainability` | `architecture`
**任务**：`api-design` | `data-model` | `testing` | `deployment` | `migration` | `refactoring`
**规模**：`small(<1K行)` | `medium(1K-10K行)` | `large(>10K行)`

标注规则：每条策略至少标注1个语言+1个层级+1个领域标签。根据涉及文件路径自动推断。

### confidence 自动计算与升格门槛

**自动计算**：
- use_count = 1 → confidence = 低
- use_count = 2-3 → confidence = 中
- use_count ≥ 4 → confidence = 高

**升格门槛**：策略从"观察"升格为"推荐"必须满足：
- confidence ≥ 中（即 use_count ≥ 2）
- 连续2次 delta > 0

use_count = 1 时 success_rate 无统计意义，不作为升格依据。

**排序规则**：

- 当前版本：按 success_rate 降序（简单版）
- 未来版本（数据充足后）：success_rate × confidence × (1 - side_effect_penalty) / avg_cost

**归因规则**：
- 只有单策略轮次（strategy_id 为单一策略）的结果才能更新 avg_delta 和 success_rate
- 多策略并行轮次（strategy_id 为 `multi:...`）的结果标记为"混合归因"，不更新聚合指标，仅记录为参考数据
- 此规则确保策略效果库中的数据可归因、可复现

**状态转换规则**（生命周期状态枚举：推荐 / 候选默认 / 观察 / 已废弃）：
- 新策略默认"观察"
- 升格为"推荐"必须满足：confidence ≥ 中（use_count ≥ 2）且连续 2 次 delta > 0
- 连续 2 次 delta ≤ 0 → "已废弃"
- "已废弃"策略在新上下文中 delta > 0 → 回到"观察"

### context-scoped 状态

策略的 status 可以按 context_tags 组合细分。当同一策略在不同上下文中表现不同时，使用以下扩展机制：

**全局 status**：仍保留在策略效果库主表中，作为无上下文匹配时的默认值。

**上下文特定 status**：在策略效果库表格之外，维护一个补充表：

| strategy_id | context_tags | status | evidence | last_validated |
|-------------|-------------|--------|----------|----------------|
| S01-parallel-scan | [python, backend, security] | 推荐 | 3次正向 | 2026-03-28 |
| S01-parallel-scan | [typescript, frontend, performance] | 已废弃 | 2次负向 | 2026-03-28 |

**查询优先级**：
1. 精确匹配：当前任务的 context_tags 与补充表的 context_tags 完全匹配 → 使用该行 status
2. 子集匹配：当前任务的 context_tags 是补充表某行的超集 → 使用该行 status
3. 无匹配：使用全局 status（策略效果库表格中的 status 字段）

**状态转换规则扩展**：
- 上下文特定 status 的转换规则与全局规则相同（连续 2 次 delta > 0 → 推荐，连续 2 次 delta ≤ 0 → 已废弃）
- 但只基于该特定上下文的使用数据，不受其他上下文影响
- 新上下文首次使用 → 继承全局 status，第二次使用后产生独立上下文 status

### 经验自动晋升链

```text
入库(自动,观察,低置信) → 推荐(连续2次delta>0+use>=2) → 候选默认(success>=80%+use>=4+高置信) → [v2] 金丝雀验证(1次同类任务) → [v2] 升级(写入command,用户确认,patch+1)
```

**v1 已实现**: 入库 → 观察 → 推荐 → 候选默认（自动晋升）；连续2次负向 → 已废弃（自动废弃）；已废弃 + 正向 → 观察（自动恢复）。
**v2 预留**: 金丝雀验证、command 文件写入升级、升级后回滚。
**回滚**（v2）：升级后连续 2 次 delta <= 0 → 从 command 移除，回退到推荐，patch+1。

---

## 记忆分层（MUSE 三层分级）

经验库中的每条策略按影响层级分为三层，不同层级的经验在 OBSERVE 阶段有不同的读取优先级和衰减速率。

| 层级 | 标签 | 含义 | 示例 | 衰减速率 |
|------|------|------|------|---------|
| L1 | `strategic` | 方法论级别的认知，影响整体方向 | "fail-closed评分比宽容评分更能驱动质量" | 慢（180d） |
| L2 | `procedural` | 流程级别的经验，影响执行步骤 | "并行扫描比串行扫描在T6中提速40%" | 中（90d） |
| L3 | `tool` | 工具/技巧级别，影响具体操作 | "grep -rn 比 find + xargs 更快定位问题" | 快（30d） |

**标注规则**（v2 预留）：每条策略在入库时标注一个层级标签。判断标准：
- 改变了"做不做" → strategic
- 改变了"怎么做" → procedural
- 改变了"用什么做" → tool

**读取优先级**（v2 预留）：OBSERVE 阶段读取经验时，strategic > procedural > tool。当预算紧张时，优先应用高层级经验。

> **v1 状态**: MUSE 分层为设计文档，`memory_layer` 字段未写入表列。v1 使用扁平排序（success_rate × 时间衰减）。

### 时间衰减机制

策略效果随时间递减，避免过时经验干扰决策。

**衰减规则**（基于 last_validated_date）：

| 距今天数 | 衰减系数 | 效果 |
|---------|---------|------|
| 0-30d | ×1.0 | 完全有效 |
| 31-60d | ×0.8 | 略微衰减 |
| 61-90d | ×0.5 | 显著衰减 |
| >90d | 降级 | status 自动从"推荐"降为"观察" |

**衰减应用**：
- 排序时：实际排序分 = success_rate × 衰减系数
- 降级触发：>90d 未验证的"推荐"策略自动降为"观察"，下次使用时需重新验证
- 重新验证：使用后 delta > 0 → last_validated_date 更新为当天，衰减重置
- strategic 层级豁免：L1 经验的衰减周期为上表的 2 倍（60d/120d/180d）

**扩展字段**（v2 预留）：策略效果库计划新增 `memory_layer`（L1/L2/L3）和 `last_validated_date`（ISO 8601 日期）两个字段。v1 中 `last_validated_date` 通过 description 字段的 `@YYYY-MM-DD` 标签实现等效功能（cmd_query 解析此标签进行时间衰减排序）。

---

## 策略组合与消融（v2 预留）

### 策略组合（composed_from）

当多个基础策略组合使用效果更好时，可以创建组合策略：

**扩展字段**：策略效果库新增 `composed_from` 字段（strategy_id 列表，如 `[S01-parallel-scan, S03-cache-first]`）。

**组合规则**：
- 组合策略的 strategy_id 使用 `C{NN}-{描述}` 格式（C 表示 Composed）
- composed_from 中的每个基础策略必须在策略效果库中独立存在
- 组合策略的 avg_delta 独立计算，不影响基础策略的 avg_delta
- 组合策略的 success_rate 独立跟踪

**示例**：
```
strategy_id: C01-parallel-cached-scan
composed_from: [S01-parallel-scan, S03-cache-first]
description: 并行扫描 + 缓存优先的组合策略
```

### 消融协议（Ablation Protocol）

组合策略连续 2 次 delta > 0 时触发（需预算>=50%+用户未跳过）。依次移除组合中一个基础策略执行一轮，对比 delta 变化：无显著变化(<阈值20%)=低贡献(移除简化)；显著下降=关键组成(保留)。仅一个有贡献时解散组合，该策略直接升格。

---

## 经验评估标准

| 评估维度 | 判据 |
|---------|------|
| 类型 | 见上方"经验类型与分发目标"表 |
| 影响层级 | 低：补充锚点/样本；中：调整参数（±20%以内）；高：改变规则/门禁/流程 |
| 置信度 | 基于验证次数：1次=低，2-3次=中，≥4次=高 |
| 分发优先级 | 高风险高置信 > 低风险高置信 > 中风险中置信 > 其他 |

---

## 跨任务经验读取规则

OBSERVE 阶段读取顺序（写入 loop-protocol.md）：

```text
1. 当前任务的 findings.md（任务本地经验）
2. references/experience-registry.md 全局策略效果库（跨任务经验）
3. 同模板 + context_tags重叠 的"推荐"策略（按 success_rate 降序）
   - context_tags重叠 = 当前任务的标签与策略的context_tags至少有2个相同标签
   - 无重叠标签的策略不推荐，避免跨上下文误迁移
   - 如果策略有 context-scoped status，优先使用与当前上下文匹配的 status，而非全局 status

首轮冷启动时：
- 无任务本地经验
- 读取全局经验库中同模板 + context_tags重叠的推荐策略
- 以全局经验作为首轮策略选择依据
```

---

## 经验淘汰机制

- 连续 2 次在不同任务中验证无效（delta ≤ 0）→ status 改为"已废弃"
- "已废弃"状态持续 5 次任务未被重新验证 → 移至归档区
- 废弃经验不删除，保留在归档区供审计

---

## 协议变更效果追踪表（v2 预留）

记录每次协议变更的预期目标和实际效果，支持结果验证。v1 中协议变更通过 git commit history 追踪。

| change_id          | protocol_version | 变更内容 | 预期目标 | 验证窗口 | 实际效果 | 状态 |
|--------------------|------------------|----------|----------|----------|----------|------|
| （随协议变更积累） |                  |          |          |          |          |      |

**状态枚举**：验证中 / 已达标（固化）/ 未达标（回滚评估中）/ 已回滚

**change_id格式**：CH{NNN}-{简短描述}（如 CH001-anchor-t4）。前缀 CH = Change，与组合策略的 C{NN} 前缀（C = Composed）区分，避免命名冲突。
