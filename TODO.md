# AutoLoop 完整待完成事项

**日期**：2026-03-28
**来源**：9份运行文档汇总 + skill注册检查
**总计**：~85项（已完成~15项，待执行~50项，远期规划~20项）

---

## 一、基础设施（立即执行）

### 1.1 Skill子命令注册修复

**问题**：`/autoloop:research`、`/autoloop:compare`等子命令无法独立调用，只有`/autoloop`是入口。

**根因**：Claude Code skill发现只识别`~/.claude/skills/*/SKILL.md`，AutoLoop的commands/下的.md文件不是SKILL.md，不会被注册为独立skill。

**检查结果**：以下8个子命令全部无法独立调用：
- `/autoloop:research`（T1）
- `/autoloop:compare`（T2）
- `/autoloop:iterate`（T3）
- `/autoloop:generate`（T4）
- `/autoloop:deliver`（T5）
- `/autoloop:quality`（T6）
- `/autoloop:optimize`（T7）
- `/autoloop:plan`

**修复方案**（参考gstack模式）：为每个子命令创建独立目录+SKILL.md，通过symlink注册：

```
~/.claude/skills/autoloop-research/SKILL.md  → name: autoloop-research
~/.claude/skills/autoloop-compare/SKILL.md   → name: autoloop-compare
~/.claude/skills/autoloop-iterate/SKILL.md   → name: autoloop-iterate
~/.claude/skills/autoloop-generate/SKILL.md  → name: autoloop-generate
~/.claude/skills/autoloop-deliver/SKILL.md   → name: autoloop-deliver
~/.claude/skills/autoloop-quality/SKILL.md   → name: autoloop-quality
~/.claude/skills/autoloop-optimize/SKILL.md  → name: autoloop-optimize
~/.claude/skills/autoloop-plan/SKILL.md      → name: autoloop-plan
```

每个SKILL.md引用共享协议：`../autoloop/protocols/`

**优先级**：P0
**工作量**：~1小时

### 1.2 Python工具脚本开发

**决策**：T2对比结果推荐Option A（Python脚本，8.35/10），已确认。

| 脚本 | 功能 | 优先级 | 代码量 |
|------|------|--------|--------|
| `scripts/autoloop-tsv.py` | TSV读写校验（15列） | P0 | ~80行 |
| `scripts/autoloop-score.py` | 质量门禁计算 | P0 | ~100行 |
| `scripts/autoloop-init.py` | Bootstrap创建4个文件 | P0 | ~60行 |
| `scripts/autoloop-validate.py` | 跨文件主键校验 | P1 | ~80行 |
| `scripts/autoloop-variance.py` | 评分方差+置信度计算 | P1 | ~40行 |
| `scripts/autoloop-registry.py` | 经验库状态转换 | P2 | ~80行 |
| `scripts/autoloop-tags.py` | context_tags自动标注 | P2 | ~60行 |

**总计**：~500行Python stdlib代码
**工作量**：~3小时

### 1.3 SKILL.md增加脚本调用指令

在SKILL.md中增加MANDATORY脚本调用指令：
- "每轮结束后必须运行`autoloop-score.py`计算质量门禁"
- "写入TSV前必须运行`autoloop-tsv.py validate`校验格式"
- "无scripts/时LLM手动执行（降级模式）"

**优先级**：P0（与1.2同步）
**工作量**：~15分钟

---

## 二、经验迁移系统（本周）

### 2.1 激活context_tags + confidence

**来源**：T2跨任务经验迁移对比（P0）

| 任务 | 具体内容 | 工作量 |
|------|---------|--------|
| 激活context_tags | 定义标签词汇表（python/typescript/backend/frontend/security/performance等），OBSERVE按标签过滤 | ~15分钟 |
| 激活confidence | use_count=1→低，2-3→中，≥4→高；要求≥中等才升格"推荐" | ~15分钟 |
| 更新OBSERVE规则 | "同模板+context_tags重叠+推荐+按success_rate"替代"同模板+推荐+按success_rate" | ~10分钟 |

**优先级**：P0
**工作量**：~30分钟

### 2.2 策略描述增强 + context-scoped状态

**来源**：T2跨任务经验迁移对比（P1）

| 任务 | 具体内容 | 工作量 |
|------|---------|--------|
| 增加mechanism/preconditions/contraindications字段 | 策略描述从一行扩展为结构化块 | ~30分钟 |
| context-scoped状态 | 同一策略在不同context_tag组合下可同时是"推荐"和"避免" | ~1小时 |

**优先级**：P1
**工作量**：~1.5小时

### 2.3 记忆分层 + 时间衰减

**来源**：T2跨任务经验迁移对比（P2）

| 任务 | 具体内容 | 工作量 |
|------|---------|--------|
| MUSE三层分级 | strategic/procedural/tool层级标签 | ~30分钟 |
| 时间衰减 | last_validated_date，30d→×0.8，60d→×0.5，90d→降级 | ~30分钟 |

**优先级**：P2
**工作量**：~1小时

### 2.4 策略组合 + 消融协议

**来源**：T2跨任务经验迁移对比（P3）

| 任务 | 具体内容 | 工作量 |
|------|---------|--------|
| composed_from字段 | 策略可引用其他策略为构建块 | ~1小时 |
| 消融协议 | 多策略成功后逐个测试归因 | ~1小时 |

**优先级**：P3
**工作量**：~2小时

---

## 三、评分系统（本周）

### 3.1 评分语义统一

**来源**：R7评审建议#1（所有维度的上游约束）

- 统一quality_score/confidence/severity/gate_status四种语义
- 统一分歧仲裁协议，只保留一种仲裁链
- 为每个模板补齐分数档位的证据锚点

**优先级**：P1
**工作量**：~2小时

### 3.2 硬门禁 vs 软门禁区分

**来源**：R7评审建议

- 明确哪些门禁必须通过（硬），哪些是建议通过（软）
- 禁止混合解释
- 硬门禁失败=整轮不通过；软门禁失败=记录但可继续

**优先级**：P2
**工作量**：~1小时

### 3.3 跨模型评分一致性机制

**来源**：跨模型验证测试+Codex T1调研发现

- 结构化rubric > 自由提示（已验证）
- 异构panel > 单一judge（PoLL论文验证）
- "结构化标准 + 去偏校准 + 晚聚合"写入评审框架
- 交换顺序去偏（swap augmentation）

**优先级**：P2
**工作量**：~1.5小时

---

## 四、收敛控制（下周）

### 4.1 模板级停滞阈值

**来源**：R7评审建议#3

- T3/T6/T7分别设定独立停滞阈值（不共用3%）
- 设定最大探索深度
- 统一停滞状态机：切换→探索→再验证→终止

**优先级**：P2
**工作量**：~1小时

### 4.2 振荡检测 + 跨维度回归

**来源**：R6/R7评审

- 振荡检测：连续N轮分数在±0.5范围内波动→报告振荡
- "改A坏B"自动检测：任何受影响维度跌破门禁阈值→视为回归
- 基线建立后锁定范围，扩维只在独立分支

**优先级**：P3
**工作量**：~1.5小时

---

## 五、自进化落地（下周）

### 5.1 结果验证完善

**来源**：R6方案#4（已写入evolution-rules.md，需补充细节）

- 协议变更效果追踪表实际使用
- 验证窗口内的指标跟踪流程
- 回滚评估的具体判据

**优先级**：P2
**工作量**：~1小时

### 5.2 经验自动晋升链

**来源**：R7评审建议#2

```
经验入库 → 候选默认策略 → 金丝雀验证 → 升级/回滚
```

- 定义晋升条件（success_rate≥80% + use_count≥4 + confidence=高）
- 金丝雀验证：在1个任务中以"推荐"身份使用，验证效果
- 升级：写入对应protocol/command文件
- 回滚：效果不达预期则撤销

**优先级**：P2
**工作量**：~2小时

---

## 六、状态机一致性（持续）

### 6.1 残留二次定义清理

**来源**：R4方案+R6 Batch5

- 全仓grep搜索：百分比数字、英文状态、硬编码轮次
- 每处判断：是否为权威定义？有则保留，否则改为引用
- 重点文件：commands/全部、SKILL.md、README.md

**优先级**：P2
**工作量**：~1小时

### 6.2 确认token统一

**来源**：R5/R6

- Phase 5确认token已改为"已验证"
- 检查所有文件中的confirmed/verified/用户确认等变体
- 统一为一套中文枚举

**优先级**：P2
**工作量**：~30分钟

---

## 七、外部发布（1-2周内）

### 7.1 GitHub公开发布

**来源**：T1竞品分析行动建议

- 创建独立GitHub repo
- README写清定位："Protocol-layer autonomous iteration methodology"
- 与autoresearch/Ralph Wiggum明确区分

**优先级**：P1
**工作量**：~2小时

### 7.2 提交awesome-autoresearch

**来源**：T1竞品分析行动建议#1（Immediate）

- 提交到awesome-autoresearch列表
- 定位文案："Protocol-layer autonomous iteration methodology — works with any agent (Claude Code, Codex, Gemini CLI)"

**优先级**：P1
**工作量**：~30分钟

### 7.3 对比文档

**来源**：T1竞品分析行动建议#2（This week）

- "AutoLoop vs autoresearch vs Ralph Wiggum"对比文档
- 突出架构差异：单指标vs多门禁、无进化vs可控进化、代码only vs 7模板

**优先级**：P1
**工作量**：~1小时

---

## 八、验证积累（持续）

### 8.1 实际任务运行积累

**来源**：T2对比报告（"验证是从设计分到实际分的唯一路径"）

- 目标：累计10+个端到端任务运行
- 当前：T1（竞品调研）✅ + T2×3（竞品对比+经验迁移+代码实现）✅ = 4次
- 每次运行记录实际门禁得分
- 逐步从"拍脑袋阈值"过渡到"数据校准阈值"

**优先级**：持续
**状态**：进行中

### 8.2 跨模型验证补充

**来源**：跨模型验证测试报告

| 测试 | 状态 |
|------|------|
| Codex执行T1协议 | ✅ 通过（会话23） |
| 同一产出物跨模型评分一致性 | ⚠️ 部分通过：模拟数据测试通过（Claude 6.0 vs Codex 5.0，差异1.0 < 2.0阈值），但测试材料为简化模拟而非真实产出物 |
| 多轮迭代在Codex中持续执行 | ⚠️ 协议理解通过但实际写入阻塞：Codex 正确执行 2 轮 OODA + 策略命名 + TSV 格式，但只读沙箱阻止文件写入 |
| TSV实际写入+跨轮读取 | ❌ 阻塞：Codex exec 只读沙箱限制，无法验证实际文件 I/O |
| 独立evaluator在Codex中分离 | ❌ 未测试：需要 Codex 内部启动两个独立进程，当前架构不支持 |

**优先级**：P3
**工作量**：每项~30分钟

---

## 九、远期规划（1-3月）

| # | 任务 | 来源 |
|---|------|------|
| 1 | 多模板编排协议（T1→T2→T5链式执行） | T1对比，已确认后置 |
| 2 | 领域适配从主模板拆成独立domain pack | R7建议 |
| 3 | 结构化单一事实源（4文件→1数据源生成） | R7建议#4 |
| 4 | 路由置信度+降级分支 | R7建议 |
| 5 | 可选hooks增强（Claude Code用户奖励） | T2代码方案 |
| 6 | 用户自定义模板（T8+） | T2对比发现 |
| 7 | MCP Server迁移（功能扩展到需要时） | T2代码方案 |

---

## 执行优先级总览

| 优先级 | 任务组 | 预计工作量 |
|--------|--------|-----------|
| **P0（立即）** | Skill子命令注册 + Python脚本P0 + context_tags/confidence激活 | ~4.5小时 |
| **P1（本周）** | 经验描述增强 + 评分语义统一 + GitHub发布 + awesome提交 + 对比文档 | ~7小时 |
| **P2（下周）** | 硬软门禁 + 跨模型一致性 + 停滞阈值 + 结果验证 + 自动晋升链 + 二次定义清理 | ~9小时 |
| **P3（2周内）** | 记忆分层 + 振荡检测 + 策略组合 + 跨模型验证补充 | ~7小时 |
| **远期** | 多模板编排 + domain pack + 单一事实源 + MCP | 未估 |
