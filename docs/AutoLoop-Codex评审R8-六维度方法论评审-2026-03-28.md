# AutoLoop Codex 评审 R8 — 六维度方法论深度评审

**评审日期**: 2026-03-28
**评审工具**: OpenAI Codex CLI (xhigh reasoning effort + web_search_cached)
**评审范围**: ~/Projects/autoloop 全仓 49 文件（协议12 + 命令11 + 模板6 + 脚本7 + MCP 3 + SKILL 9 + 文档1）
**Token 消耗**: 290,275
**评审模式**: 静态源码审查（read-only，未执行端到端运行）

---

## 评审框架

| 维度 | 权重 | 评审焦点 |
|------|------|---------|
| 度量效度与一致性 | 20% | 指标定义是否准确？评分标准是否真正度量其声称的内容？阈值是否有经验基础？跨文件一致性 |
| 数据到策略的闭环性 | 20% | 观测数据是否真正驱动策略选择？是否存在从结果回到决策的真实反馈闭环？ |
| 收敛性能 | 20% | 系统是否真正向质量目标收敛？是否有防止振荡、停滞、发散的机制？ |
| 门禁判别力 | 10% | 质量门禁能否真正区分好坏？通过/失败阈值是否有意义？ |
| 任务模型适配度 | 10% | 7个模板是否真正适配真实任务？是否有缺口、重叠、强制适配问题？ |
| 自进化与复利能力 | 20% | 系统是否真正从过去运行中学习？经验注册表是否有用？协议进化是否复利累积？ |

---

## 总分

| 维度 | 权重 | 得分 | 加权 |
|------|------|------|------|
| 度量效度与一致性 | 20% | 4/10 | 0.80 |
| 数据到策略的闭环性 | 20% | 3/10 | 0.60 |
| 收敛性能 | 20% | 4/10 | 0.80 |
| 门禁判别力 | 10% | 4/10 | 0.40 |
| 任务模型适配度 | 10% | 5/10 | 0.50 |
| 自进化与复利能力 | 20% | 3/10 | 0.60 |
| **加权总分** | **100%** | | **3.7/10** |

---

## 各维度详细评审

### 1. 度量效度与一致性 (4/10, 权重 20%)

**证据（强项）**:
- Fail-closed 评分明确定义于 quality-gates.md:40-62，每个评分必须包含分数+判据+证据
- 可度量的成功标准和门禁阈值表存在于 plan-template.md:24, 125
- 基线和每轮评分更新机制存在于 progress-template.md:20, 80

**关键缺陷**:

1. **评分器与渲染器格式不兼容**
   - `autoloop-score.py` 期望 `##` sections + 内联 source markers (score.py:19, 30, 50, 90)
   - `autoloop-render.py` 输出 `###` subheads + 独立 `来源:` 行 (render.py:152, 155, 161)
   - **后果**: SSOT 渲染的 findings 会系统性地被低估或评为零分

2. **阈值权威漂移**
   - README.md:63 和 report-template.md:5 说阈值应在 quality-gates.md
   - audit-template.md:15-17 硬编码了 T6 阈值
   - TODO.md:224, 229 已标记此问题但未修复

3. **评分词汇碎片化**
   - 混合使用: `/10` 分数、`%` 置信度、`高/中` 来源可信度、`P1/P2/P3` 严重级别、`1-5` 策略效果分
   - 来源: findings-template.md:14, 17, 30, 38, 138, 186
   - **后果**: 聚合和跨维度比较有歧义

4. **校准基础薄弱**
   - 仅 4 次端到端运行记录 (TODO.md:290, 292, 304, 306)
   - 阈值仍从猜测迁移到校准中
   - 评分语义和验证器仍未统一 (TODO.md:133, 140, 146)

**建议**:
- 定义一个规范化的度量 schema；从该 schema 生成模板、TSV header、验证器和报告
- 让评分器直接消费 SSOT（而非解析 markdown）
- 在标注语料库上校准阈值，发布每个门禁的误报/漏报行为

---

### 2. 数据到策略的闭环性 (3/10, 权重 20%)

**证据（强项）**:
- 协议规定 Round 2+ 必须先读取上轮 REFLECT 再开始观察 (loop-protocol.md:252, 265, 583)
- 根 skill 声明任务应读写全局经验注册表 (SKILL.md:35, 322)

**关键缺陷**:

1. **命令层未执行声明的闭环**
   - 命令主要重新读取 `autoloop-findings.md` 而非共享记忆
   - 证据: autoloop-research.md:15, autoloop-quality.md:30, autoloop-optimize.md:21
   - 仅 pipeline 完成时明确写入经验注册表 (autoloop-pipeline.md:76)

2. **两套竞争运行模式未统一**
   - Flat files 路径: `autoloop-init.py` 创建 4 个 markdown 文件 (init.py:129, 133)
   - SSOT JSON 路径: `autoloop-state.py` 创建 `autoloop-state.json` (state.py:247)
   - MCP server 暴露 flat-file 工具链但不暴露 state/render (server.py:41, 92)
   - **后果**: 操作路径绕过了状态引擎

3. **学习容器有 schema 无 reducer**
   - SSOT 包含 `strategy_history`、`pattern_recognition`、`lessons_learned`、`experience` (state.py:75, 104, 110, 116)
   - **但没有自动化的 reducer** 将每轮 reflect 数据提升到这些容器中 (state.py:403)
   - 渲染器也省略了大部分这些字段 (render.py:95, 138)

4. **add-finding 静默丢数据**
   - 无迭代时 round 默认为 0，存储到当前迭代被跳过
   - round-list append 逻辑仅对正数 round 有效 (state.py:448-467)

**建议**:
- 让一个控制器拥有每轮的全部状态
- 通过同一 API 暴露 state、render、score 和 experience updates
- 要求每轮发出结构化观测、选择一个策略、评分、持久化更新后的策略先验，才能开始下一轮

---

### 3. 收敛性能 (4/10, 权重 20%)

**证据（强项）**:
- 策略切换、振荡检测、终止逻辑存在于 loop-protocol.md:326, 544
- 模板特定停滞阈值存在于 parameters.md:137, 150
- 多层收敛控制：通用策略切换 + 模板特定停滞 + 最大探索 + "无法继续"终止

**关键缺陷**:

1. **模板特定控制未接入主 EVOLVE 路径**
   - parameters.md 添加了 T3/T6/T7 特定阈值
   - loop-protocol.md 仍然使用通用 3% 规则终止/切换 (loop-protocol.md:548)
   - **后果**: 精心定义的模板特定规则不生效

2. **状态层允许绕过排序**
   - 通用 `update` 命令可写入任意路径/值 (state.py:268, 272, 279)
   - 唯一的转换逻辑是"新轮次从 OBSERVE 开始" (state.py:359)
   - **后果**: 阶段序列可被完全绕过

3. **T3 可忽略附带损害终止**
   - 终止仅依赖 KPI 达标 (quality-gates.md:353)
   - 但其自身锚点也评分策略有效性和副作用控制 (quality-gates.md:400, 402)
   - **后果**: "命中 KPI，忽略附带损害"

4. **Pipeline 允许放松门禁**
   - `gate_override` 仅用于放松门禁 (orchestration.md:32)
   - 允许 `skip_and_continue` (orchestration.md:121, 127)
   - 禁止跨节点自动回滚 (orchestration.md:162)

**建议**:
- 将收敛逻辑从文档移入状态控制器
- 从 SSOT 计算边际增益、振荡、副作用回归
- 阻断终止除非目标改进和附带约束同时通过

---

### 4. 门禁判别力 (4/10, 权重 10%)

**证据（强项）**:
- 覆盖率和可信度有意分离 (quality-gates.md:118)
- T2 偏见/敏感性量化 (quality-gates.md:258)
- T6 使用评分+缺陷计数复合逻辑 (quality-gates.md:556)
- T5 有硬性用户确认阻塞 (autoloop-deliver.md:35, 149, 455)

**关键缺陷**:

1. **门禁策略自相矛盾**
   - T1/T2 "未满足门禁时暂停" (quality-gates.md:533-534)
   - 但后续部分又标记 T1 一致性/完整性和 T2 敏感性为非阻塞 (quality-gates.md:592-593)

2. **T6 矛盾**
   - "唯一规则"说分数和计数必须同时通过 (quality-gates.md:571)
   - 后续允许尽管计数未达标仍可通过 (quality-gates.md:597, 605)

3. **T5 部署规则冲突**
   - quality-gates 允许服务检查或健康检查之一为 N/A (quality-gates.md:537, 546)
   - delivery-phases Phase 4 仍列出两者为必需 (delivery-phases.md:274-275)

4. **无经验基础**
   - 无混淆率分析（误报/漏报率）
   - 阈值未基于已知好/已知差运行进行基准测试

**建议**:
- 对已知好/已知差运行进行门禁基准测试
- 计算混淆率
- 将硬/软语义合并为一张表
- 确保评分器评估引擎实际产出的产物

---

### 5. 任务模型适配度 (5/10, 权重 10%)

**证据（强项）**:
- 模板分类有意为之
- 路由阈值存在于 parameters.md:209
- T5 有自己的阶段模型 (delivery-phases.md:13)
- T6/T7 可通过 domain packs 特化 (domain-packs/README.md:10)

**关键缺陷**:

1. **容易绕过**
   - 直接模板命令在 SKILL.md:398-404 暴露
   - 每个模板 SKILL.md 是薄包装的 pass-through (research/SKILL.md:10, deliver/SKILL.md:10)
   - **后果**: 用户可跳过顶层路由和参数收集

2. **T2 违反"单策略隔离"原则**
   - 核心规则: 每轮 DECIDE 只选一个主策略 (SKILL.md:29)
   - T2 运行两个分析器 + 分歧时触发第三个 (autoloop-compare.md:39, 51, 96)

3. **T5 参数合约漏洞**
   - delivery-template 要求 `migration_check_cmd` (delivery-template.md:36)
   - plan-template T5 参数块未收集此参数 (plan-template.md:71, 78, 86)

4. **T6 报告权威分裂**
   - report-template 包含 T6 段 (report-template.md:103)
   - audit-template 是独立 T6 报告 (audit-template.md:1)
   - **后果**: 评分来源不明确

**建议**:
- 集中强制路由；让模板不可在未经验证的任务分类下被调用
- 关闭每个模板的参数漏洞
- 合并重叠的终态产物

---

### 6. 自进化与复利能力 (3/10, 权重 20%)

**证据（强项）**:
- 经验注册表支持提升、衰减、候选默认逻辑 (experience-registry.md:111, 123, 170, 223)
- 协议进化规则定义了协议升级机制 (evolution-rules.md:229, 327)
- 理论上是设计最强的元素

**关键缺陷**:

1. **执行路径中几乎无操作化**
   - 命令不一致地消费注册表；主要读取本地 findings (autoloop-research.md:15, autoloop-quality.md:30)
   - SSOT 有学习容器但无自动填充路径 (autoloop-state.py:75, 110, 403)

2. **治理不一致**
   - 协议变更需要用户确认 (loop-protocol.md:165)
   - 但 evolution-rules 允许低/中风险变更自动执行 (evolution-rules.md:233, 242)

3. **版本语义漂移**
   - Patch 定义为锚点/样本/经验（loop-protocol.md:5）
   - 但正式规则升级和命令默认值升级也递增 patch (evolution-rules.md:327, 354)
   - 回滚甚至递减 patch (experience-registry.md:183)

**建议**:
- 要求每轮自动更新策略效果统计
- 让注册表读写在控制器中成为强制步骤
- 仅在重复验证胜出后提升策略
- 统一协议进化治理和版本语义

---

## Top 3 系统性问题

| # | 问题 | 根因 |
|---|------|------|
| 1 | **"自主循环"未机械闭合** | 两套竞争运行模式(flat files vs SSOT)，MCP 暴露弱路径，关键状态转换依赖 agent 自觉而非 state enforcement |
| 2 | **度量契约内部不一致** | 阈值、TSV schema、报告产物、评分器输入在文档/模板/脚本间漂移，系统无法可靠度量其声称度量的内容 |
| 3 | **自进化是架构层虚构** | experience registry 和 evolution rules 是精致文档，但未嵌入主执行路径 |

## Top 3 最高杠杆改进

| # | 改进 | 预期影响 |
|---|------|---------|
| 1 | **用一个机器可读 SSOT 替代 markdown-first 路径** | 从同一数据模型生成 findings/progress/reports/TSV/scores，消除跨文件漂移 |
| 2 | **实现真正的轮次控制器** | 强制 OBSERVE→ORIENT→DECIDE→ACT→VERIFY→SYNTHESIZE→EVOLVE→REFLECT，自动更新策略记忆，阻断非法转换 |
| 3 | **构建经验门禁校准框架** | 标注历史运行、阈值拟合、方差分析、每个门禁的误报/漏报率报告 |

---

## 审查覆盖范围

### 子系统 A: 协议层（12 文件, ~4,500 行）
- loop-protocol.md, evolution-rules.md, enterprise-standard.md, agent-dispatch.md
- delivery-phases.md, experience-registry.md, quality-gates.md, orchestration.md
- parameters.md, domain-packs/README.md, python-fastapi.md, nextjs-typescript.md

### 子系统 B: 脚本与 MCP（10 文件, ~1,750 行）
- autoloop-variance.py, autoloop-score.py, autoloop-state.py, autoloop-init.py
- autoloop-tsv.py, autoloop-render.py, autoloop-validate.py
- server.py, install.sh, mcp-config.json

### 子系统 C: 文档与模板（8 文件）
- README.md, TODO.md
- plan-template.md, findings-template.md, progress-template.md
- delivery-template.md, audit-template.md, report-template.md

### 子系统 D: Skill 与命令层（19 文件）
- SKILL.md (root), 8 个子命令 SKILL.md
- 10 个命令文件 (autoloop.md, autoloop-plan.md, autoloop-research.md, etc.)

---

## 与历史评审对比

| 评审轮次 | 日期 | 评分 | 主要关注 |
|---------|------|------|---------|
| R2 (Codex) | 03-26 | 2.9/10 | 初始架构缺陷 |
| R3-R7 (Claude) | 03-28 | 6.8/10 | 协议成熟度 |
| **R8 (Codex)** | **03-28** | **3.7/10** | **六维度方法论有效性** |

> **注**: R8 与 R3-R7 评分差异大是因为评审维度完全不同。R3-R7 评估"协议文档是否完整一致"，R8 评估"系统是否真正作为自主迭代引擎运行"。R8 的低分反映的是**声明-执行断裂**问题，不是协议质量倒退。
