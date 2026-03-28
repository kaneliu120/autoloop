# Experience Registry — 全局经验库

## 概述

经验库是 AutoLoop 第二层反馈循环（方法论自身迭代）的核心组件。它实现经验的跨任务流动，使第 N 次执行比第 1 次更快、更准、更高效。

**与其他文件的关系**：
- `loop-protocol.md`：OBSERVE 阶段读取全局经验；REFLECT 阶段产出经验条目
- `evolution-rules.md`：定义经验分发后的协议变更审批流程
- `findings-template.md`：策略评估表中的 strategy_id 与本库的策略效果表对应

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

**写回规则**：策略 use_count 达到 2 时，必须补充 mechanism/preconditions/contraindications 三个必���字段��见下方"策略详细描述格式"）。

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

**字段说明**：
- strategy_id：策略唯一标识，与 results.tsv 和 findings.md 一致
- template：适用模板（T1-T7，或"通用"）
- dimension：目标维度
- description：策略摘要（一句话，详细描述见下方"策略详细描述格式"）
- avg_delta：历次使用的平均分数变化
- side_effects：已知副作用列表
- use_count：累计使用次数
- success_rate：产生正向效果的比例（use_count 中 delta > 0 的占比）
- status：推荐 / 待验证 / 避免

**扩展字段**：

- avg_cost：平均执行成本（轮次数），当前默认 —（预留，待数据积累后启用）
- confidence：效果数据置信度（低/中/高），**已激活** — 见下方"confidence 自动计算与升格门槛"
- context_tags：适用上下文标签列表（如 [python, backend, security]），**已激活** — 见下方"context_tags 标准词汇表"
- side_effect_severity：副作用严重度（无/低/中/高），当前默认 无（预留，待数据积累后启用）

### ���略详细描述格式

当策略的 use_count ≥ 2 ���，必须补充以下结构化描述（写在策略效果库表格下方，按 strategy_id 索引）：

| 字段 | 必填 | ��明 |
|------|------|------|
| mechanism | 是 | 策略生效的机制（为什么有效） |
| preconditions | 是 | 策略生效的前提条件（什么情况下该用） |
| contraindications | 是 | 策略的禁忌条件��什么情况下不该用） |
| optimal_context | 否 | 最佳使用场景（从成功案例中提炼） |
| failure_mode | 否 | 失败时的典��表现（从失败案��中提炼） |

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

**升格门槛**：策略从"待验证"升格为"推荐"必须满足：
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

**状态转换规则**：
- 新策略默认"待验证"
- 升格为"推荐"必须满足：confidence ≥ 中（use_count ≥ 2）且连续 2 次 delta > 0
- 连续 2 次 delta ≤ 0 → "避免"
- "避免"策略在新上下文中 delta > 0 → 回到"待验证"

### context-scoped 状态

策略的 status 可以按 context_tags 组合细分。当同一策略在不同上下文中表现不同时，使用以下扩展机制：

**全局 status**：仍保留在策略效果库主表中，作为无上下文匹配时的默认值。

**上下文特定 status**：在策略效果库表格之外，维护一个补充表：

| strategy_id | context_tags | status | evidence | last_validated |
|-------------|-------------|--------|----------|----------------|
| S01-parallel-scan | [python, backend, security] | 推荐 | 3次正向 | 2026-03-28 |
| S01-parallel-scan | [typescript, frontend, performance] | 避免 | 2次负向 | 2026-03-28 |

**查询优先级**：
1. 精确匹配：当前任务的 context_tags 与补充表的 context_tags 完全匹配 → 使用该行 status
2. 子集匹配：当前任务的 context_tags 是补充表某行的超集 → 使用该行 status
3. 无匹配：使用全局 status（策略效果库表格中的 status 字段）

**状态转换规则扩展**：
- 上下文特定 status 的转换规则与全局规则相同（连续 2 次 delta > 0 → 推荐，连续 2 次 delta ≤ 0 → 避免）
- 但只基于该特定上下文的使用数据，不受其他上下文影响
- 新上下文首次使用 → 继承全局 status，第二次使用后产生独立上下文 status

### 经验自动晋升链

策略从入库到成为协议默认策略的完整生命周期：

```text
[入库] → [候选默认] → [金丝雀验证] → [升级] 或 [回滚]
```

**阶段 1：入库（自动）**
- 触发：REFLECT 阶段产出新策略效果数据
- 状态：待验证，confidence = 低
- 无需人工确认

**阶段 2：候选默认（自动晋升条件）**
- 条件：success_rate ≥ 80% + use_count ≥ 4 + confidence = 高
- 状态：从"推荐"升格为"候选默认"
- 记录：在策略效果库中标注 `candidate_default: true`

**阶段 3：金丝雀验证（1 次任务验证）**
- 触发：策略达到候选默认条件
- 操作：在下一个同模板+同context_tags任务中，以"默认策略"身份优先使用
- 验证标准：delta > 0 且无负面 side_effect
- 通过 → 进入阶段 4；失败 → 回退到"推荐"状态，candidate_default 置 false

**阶段 4：升级（写入协议，需用户确认）**
- 操作：将策略写入对应 command 文件的"推荐默认策略"章节
- 审批：高风险变更（见 evolution-rules.md），需用户确认
- protocol_version patch+1

**回滚**：
- 触发：升级后连续 2 次任务中 delta ≤ 0
- 操作：从 command 文件移除，状态回退到"推荐"
- protocol_version patch+1

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
2. protocols/experience-registry.md 全局策略效果库（跨任务经验）
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

- 连续 2 次在不同任务中验证无效（delta ≤ 0）→ status 改为"避免"
- "避免"状态持续 5 次任务未被重新验证 → 标记为"废弃"并移至归档区
- 废弃经验不删除，保留在归档区供审计

---

## 协议变更效果追踪表

记录每次协议变更的预期目标和实际效果，支持结果验证。

| change_id          | protocol_version | 变更内容 | 预期目标 | 验证窗口 | 实际效果 | 状态 |
|--------------------|------------------|----------|----------|----------|----------|------|
| （随协议变更积累） |                  |          |          |          |          |      |

**状态枚举**：验证中 / 已达标（固化）/ 未达标（回滚评估中）/ 已回滚

**change_id格式**：C{NNN}-{简短描述}（如 C001-anchor-t4）
