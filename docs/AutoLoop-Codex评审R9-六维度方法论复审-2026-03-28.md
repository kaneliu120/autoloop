# AutoLoop Codex 评审 R9 — 六维度方法论复审

**评审日期**: 2026-03-28
**评审工具**: OpenAI Codex CLI (xhigh reasoning effort + web_search_cached)
**评审范围**: ~/Projects/autoloop 全仓 49 文件（R8 修复后复审）
**Token 消耗**: 350,642
**评审模式**: 静态源码审查（read-only）
**前序评审**: R8 (3.7/10) → 23 项修复 → 本轮 R9 复审

---

## 总分

| 维度 | 权重 | R8 得分 | R9 得分 | Delta | 加权(R9) |
|------|------|--------|--------|-------|---------|
| 度量效度与一致性 | 20% | 4.0 | **5.0** | +1.0 | 1.00 |
| 数据到策略的闭环性 | 20% | 3.0 | **4.8** | +1.8 | 0.96 |
| 收敛性能 | 20% | 4.0 | **5.5** | +1.5 | 1.10 |
| 门禁判别力 | 10% | 4.0 | **4.0** | 0.0 | 0.40 |
| 任务模型适配度 | 10% | 5.0 | **5.0** | 0.0 | 0.50 |
| 自进化与复利能力 | 20% | 3.0 | **4.8** | +1.8 | 0.96 |
| **加权总分** | **100%** | **3.7** | **4.9** | **+1.2** | **4.92** |

---

## R8 修复项验证结果

| # | R8 Issue | 修复状态 | 说明 |
|---|----------|---------|------|
| 7 | TSV 列数 13→15 | **已修复** | 全仓统一为 15 列 |
| 1 | Scorer/renderer 格式不兼容 | **部分修复** | 基本格式适配了，但单段落 findings 仍触发"≥2 信息点"规则；completeness 仍误处理独立 `来源:` 行 |
| 2 | 经验注册表未嵌入命令层 | **部分修复** | 7 个命令有 OBSERVE/REFLECT 引用，但模板无审计字段记录 registry I/O |
| 3 | 停滞阈值未接入 EVOLVE | **部分修复** | 阈值已接入，但 evolution-rules 仍有冲突的 rollback 逻辑 |
| 6 | 自进化未嵌入执行路径 | **部分修复** | registry lifecycle 完善了，但 dispatch 未要求 registry-derived context |
| 10 | 治理交叉引用 | **部分修复** | scope 声明已添加，但 rollback 语义和版本递增仍分裂 |
| 4 | Gate 策略矛盾 | **未解决** | hard/soft 矩阵添加了，但行内仍有 T1/T2/T5 暂停规则交叉；`豁免` 无 roll-up 规则 |
| 5 | 任务模型绕过 | **未解决** | 直接子命令仍可绕过路由；README 仍宣传"直接指定模板" |
| 8 | add-finding 丢数据 | **未解决** | guard 加了，但 render 丢失 strategy_id → validate 找不到 → 链路断裂 |
| 9 | 版本语义漂移 | **未解决** | loop-protocol 有唯一定义，但 state.py/init.py 仍有旧版本引用 |

---

## 各维度详细评审

### 1. 度量效度与一致性 (5.0/10, +1.0)

**改善**:
- scorer 新增 `_split_all_sections` / `_is_dimension_section` / `_count_info_points` 三个 helper，适配 render.py 的 `###` 维度 + 独立 `来源:` 格式 (autoloop-score.py:38, 145)
- TSV schema 全仓对齐为 15 列 (autoloop-state.py:25, autoloop-render.py:181, autoloop-tsv.py:9)

**仍需改进**:
- 单段落 findings 触发"≥2 信息点"规则导致低估 (autoloop-score.py:86, 115)
- completeness 仍误处理独立 `来源:` 行 (autoloop-score.py:212)
- add-finding 存储的 IDs 被 render.py 丢弃 (state.py:459 → render.py:155)，而 validate.py:95 期望它们在 markdown 中
- state.py:23 和 init.py:26 的版本引用与 loop-protocol 唯一定义不一致

---

### 2. 数据到策略的闭环性 (4.8/10, +1.8)

**改善**:
- 经验注册表在协议层成为强制 OBSERVE 输入和 REFLECT 输出 (loop-protocol.md:297, 581)
- 7 个命令文件都有经验库读写引用 (autoloop-research.md:13, autoloop-optimize.md:14, autoloop-iterate.md:14, autoloop-quality.md:14)
- experience-registry.md 不再是死端附录，有完整 lifecycle 语义 (experience-registry.md:19, 23, 25, 27, 294)

**仍需改进**:
- 运行时模板无 registry I/O 审计字段 (progress-template.md:139, findings-template.md:176)
- pipeline 仅最终写入一次 (autoloop-pipeline.md:73)，无 pipeline 级 OBSERVE 读取
- dispatch 仍要求本地 reflection context 而非全局 registry context (agent-dispatch.md:614, 847)
- state→render→validate 链路丢失 strategy_id，可追溯性未闭合

---

### 3. 收敛性能 (5.5/10, +1.5)

**改善**:
- 模板特定停滞阈值真正接入协议路径 (loop-protocol.md:581)
- T3(<2%)/T6(<0.3)/T7(<0.5) 有具体值 (parameters.md:137, 139, 141, 153)
- 停滞状态机指向替换策略而非纯声明 (parameters.md:153)

**仍需改进**:
- evolution-rules 仍有冲突的 rollback 行为：中风险变更说"自动回滚"又说"进入回滚评估" (evolution-rules.md:247, 253)
- 同一节"固化"成功规则变更用 `patch+1`，与版本 SSOT 不完全一致 (evolution-rules.md:340, 367)

---

### 4. 门禁判别力 (4.0/10, 0.0)

**改善**:
- T5 delivery 路径更严格明确 (autoloop-deliver.md:121, 328, 445)
- 门禁分类总览矩阵已在 quality-gates.md 顶部

**仍需改进**:
- hard/soft 语义仍有交叉矛盾：soft 定义为非阻塞且 roll-up 为 `通过`，但快速矩阵仍暂停 T1/T2/T5 的任何未满足门禁 (quality-gates.md:26, 112, 146, 576, 628)
- `gate_status` 包含 `豁免` 但无 roll-up 规则
- T5 Phase 4 仍将服务检查硬化为阻塞门禁 (delivery-phases.md:271, 274, 275)
- orchestration.md 的 `gate_override` 允许放松门禁 (orchestration.md:69)

---

### 5. 任务模型适配度 (5.0/10, 0.0)

**改善**:
- plan 路径更好地集中了模板推理和确认 (autoloop-plan.md:41, 108)
- domain-pack hooks 存在 (enterprise-standard.md:13)

**仍需改进**:
- 直接模板绕过仍完全可用 (autoloop.md:108, 128; plan/SKILL.md:1; deliver/SKILL.md:1)
- README 仍宣传"直接指定模板"为正常用法 (README.md:42)
- domain pack 仍为 opt-in (domain-packs/README.md:9)，省略 pack 会丢失 P1/P2 级别的栈特定检查

---

### 6. 自进化与复利能力 (4.8/10, +1.8)

**改善**:
- registry 不再是死端附录，有 lifecycle 语义 (experience-registry.md:23, 25, 27)
- 命令路径有 writeback 描述
- 版本语义有唯一权威定义 (loop-protocol.md:5)

**仍需改进**:
- dispatch 不要求 registry-derived context (agent-dispatch.md:618, 849)
- pipeline 无 registry-fed 循环
- 模板不让学习 I/O 可审计
- findings projection 有损 → 学习的 IDs/links 不能存活到下游验证

---

## Top 3 剩余系统性问题

| # | 问题 | 根因 | 影响维度 |
|---|------|------|---------|
| 1 | **state→render→validate 链路有损** | state.py 存储 finding IDs → render.py 丢弃 → validate.py 要求它们存在于 markdown | 度量效度 + 闭环性 |
| 2 | **门禁语义内部矛盾** | quality-gates 矩阵说 soft 非阻塞，但行内仍有暂停规则；`豁免` 无 roll-up 规则 | 门禁判别力 |
| 3 | **任务/模板/domain-pack 绕过可操作** | 直接子命令暴露 + README 宣传 + domain pack opt-in | 任务适配度 |

## Top 3 下一步改进

| # | 改进 | 预期影响 |
|---|------|---------|
| 1 | **JSON state 成为唯一验证契约**，或让 render 输出所有 ID/链接。停止验证 render 未输出的字段 | 度量+闭环 +1.5 |
| 2 | **门禁语义合并为一个 SSOT**，定义 hard/soft/豁免的精确 roll-up 规则，orchestration 遵守 | 门禁 +1.5 |
| 3 | **所有入口强制 plan-derived 模板选择 + domain-pack 加载**，模板中增加 registry I/O 审计字段 | 适配度+自进化 +1.0 |

---

## 历次评审对比

| 轮次 | 日期 | 评分 | Delta | 主要变化 |
|------|------|------|-------|---------|
| R2 (Codex) | 03-26 | 2.9/10 | — | 初始架构缺陷 |
| R3-R7 (Claude) | 03-28 | 6.8/10 | — | 协议文档成熟度（不同评审框架） |
| R8 (Codex) | 03-28 | 3.7/10 | — | 六维度方法论有效性（新框架） |
| **R9 (Codex)** | **03-28** | **4.9/10** | **+1.2** | **23 项修复后复审** |

---

## 修复投入产出分析

**投入**: 23 项修复，25 文件，+397/-150 行
**产出**: +1.2 分（3.7→4.9）

| 维度 | 投入修复项 | 产出 Delta | ROI |
|------|-----------|-----------|-----|
| 闭环性 | F5+F2+F6+L1 (4项) | +1.8 | 高 |
| 自进化 | F5+F8+F10+L3 (4项) | +1.8 | 高 |
| 收敛性能 | F7+F6 (2项) | +1.5 | 最高 |
| 度量效度 | F1+F3+L5+F4+L4 (5项) | +1.0 | 中 |
| 门禁判别力 | F4+L11 (2项) | 0.0 | 低（需更深层修复） |
| 任务适配度 | F9+L6+F11+F12+L2 (5项) | 0.0 | 低（需结构性变更） |

**结论**: 协议层声明修复 ROI 高（闭环+自进化+收敛），但门禁和任务适配度需要**链路末端的结构性修复**（render/validate/dispatch/template），不是添加引用就能解决的。
