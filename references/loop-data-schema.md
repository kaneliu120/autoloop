# Loop Data Schema — 数据格式与词汇规范

> 从 loop-protocol.md 分离的数据层规范。状态机和 OODA 阶段定义见 `loop-protocol.md`。

# Loop Protocol — OODA 迭代循环规范

**协议版本**：1.0.0

### 版本语义定义（唯一权威）

| 级别 | 触发条件 | 示例 | 方向 |
|------|---------|------|------|
| major (X.0.0) | 循环流程结构变更 | 阶段增减、阶段顺序调整 | 仅递增 |
| minor (0.X.0) | 门禁/维度/参数变更 | 新增评分维度、修改阈值、调整权重 | 仅递增 |
| patch (0.0.X) | 校准数据变更 | 锚点样本、策略经验、评分校准 | 仅递增 |

**不可递减规则**: 版本号只能递增，不可递减。回滚通过递增版本号实现（如 1.2.3 回滚 → 1.3.0）。
回滚记录格式: `{新版本号} (rollback from {旧版本号}, reason: {原因})`

> 变更记录见 evolution-rules.md。

## 统一参数词汇表

**规则**：所有 AutoLoop 文件（commands/、references/、assets/）中涉及下列概念时，必须使用下表中的变量名，不得自行发明同义词。

| 变量名 | 类型 | 用途 | 收集时机 | 适用模板 |
|--------|------|------|---------|---------|
| deploy_target | string | 部署目标主机/环境（如 sip-server、prod-01）| plan | T5 |
| deploy_command | string | 部署执行命令（完整命令，如 gcloud compute ssh ...）| plan | T5 |
| service_list | string[] | 服务名称列表（如 [sip-backend, sip-worker]）| plan | T5 |
| service_count | int | 服务数量（自动计算 = len(service_list)，不手动填写）| 自动 | T5 |
| health_check_url | string | 健康检查 URL（如 https://example.com/api/health）| plan | T5 |
| acceptance_url | string | 线上验收 URL（如 https://example.com）| plan | T5 |
| doc_output_path | string | 方案文档输出目录（绝对路径）| plan | T5 |
| syntax_check_cmd | string | 语法检查命令（如 python3 -m py_compile {file} 或 npx tsc --noEmit）| plan | T5/T6/T7 |
| syntax_check_file_arg | boolean | 语法检查命令是否接受单文件参数（python3 -m py_compile → true；npx tsc --noEmit → false）| plan | T5/T6/T7 |
| new_router_name | string | 本次新增的 router 变量名（如 comments_router；无新路由填 N/A）| plan | T5 |
| main_entry_file | string | 主入口文件绝对路径（如 /project/backend/main.py 或 /project/src/app.ts）| plan | T5/T6 |
| output_path | string | 输出目录绝对路径（默认 {工作目录}/autoloop-output/）| plan | T4 |
| naming_pattern | string | 文件命名规则（如 {template_name}-{index}.md）| plan | T4 |
| key_assumptions | list[{name, current_value, unit}] | T2 对比中的关键假设（结构化列表，每项含名称+当前值+单位，用于敏感性分析）| plan | T2 |
| migration_check_cmd | string | 数据库迁移状态验证命令（如 python -m alembic current && python -m alembic check；无迁移填 N/A）| plan | T5 |
| frontend_dir | string | 前端代码目录绝对路径（如 /project/frontend）| plan | T5 |

---

## 统一状态枚举

所有文件中涉及问题状态和策略评价时，必须使用下列枚举值，不得使用其他说法。

**问题状态（Problem Status）**：
```
新发现 | 已修复 | 待处理 | 跨轮遗留
```

**策略评价（Strategy Rating）**：
```
保持 | 避免 | 待验证
```

---

## 统一输出文件命名规则（规范来源）

所有文件在引用最终报告文件名时，必须引用本表，不得在其他文件中重新定义。

| 模板 | 最终报告文件名 | 过程文件 |
|------|--------------|---------|
| T1 Research | `autoloop-report-{topic}-{date}.md` | plan + findings + progress + results.tsv |
| T2 Compare | `autoloop-report-{topic}-{date}.md` | 同上 |
| T3 Iterate | `autoloop-report-{topic}-{date}.md` | 同上 |
| T4 Generate | `{output_path}/{naming_pattern}` (生成内容) + `autoloop-report-{topic}-{date}.md` (汇总报告) | 同上 |
| T5 Deliver | `autoloop-delivery-{feature}-{date}.md` | 同上 |
| T6 Quality | `autoloop-audit-{date}.md` | 同上 |
| T7 Optimize | `autoloop-audit-{date}.md` | 同上 |

其中 `{date}` = `YYYYMMDD`，`{topic}` / `{feature}` 从 plan 的一句话目标中提取（空格替换为 `-`，小写）。

---

## 统一 TSV Schema（规范来源）

所有模板写入 `autoloop-results.tsv` 时必须使用以下统一列结构，不得在其他文件中重新定义。

```
iteration	phase	status	dimension	metric_value	delta	strategy_id	action_summary	side_effect	evidence_ref	unit_id	protocol_version	score_variance	confidence	details
```

| 列 | 说明 | 示例 |
|---|---|---|
| iteration | 轮次编号（从 1 开始） | 1 |
| phase | 阶段或子步骤标识 | scan / generate / compare |
| status | 状态（检查结果枚举）：通过 / 未通过 / 待检查 / 待审查 | 通过 |
| dimension | 评分维度名 | 安全性 / 覆盖率 / score |
| metric_value | 指标值（数字或百分比） | 8.5 / 85% |
| delta | 与上轮的变化（首轮填 — ） | +1.2 |
| strategy_id | 本轮使用的策略标识（与 findings.md 策略评估表一致） | S01-sql-scan |
| action_summary | 具体执行动作摘要 | 扫描全部SQL拼接并替换为参数化 |
| side_effect | 对其他维度的影响（无副作用填"无"） | 可维护性-0.5 |
| evidence_ref | 证据引用（findings.md 中的问题ID） | S001, R003 |
| unit_id | T2选项名/T4单元编号（其他模板填 —） | 选项A / 001 / — |
| protocol_version | 当前协议版本号 | 1.0.0 |
| score_variance | 多evaluator评分方差（单evaluator填0） | 0.5 |
| confidence | 评分置信度百分比 | 85% |
| details | 补充说明 | 首轮基线采集 |

**使用约定（各模板行粒度）**：

- T1/T3/T5/T6/T7：每轮**每维度**一行，确保每个维度的分数变化和策略归因都可追踪
- T2 Compare：每轮每选项每维度一行，`unit_id` = 选项名
- T4 Generate：每生成单元一行，`unit_id` = 生成单元 ID（001/002/...），`dimension` = `score`
- strategy_id 必须与 findings.md 中策略评估表的策略名一致
- side_effect 字段强制填写（无副作用填"无"）
- 首轮基线采集时，strategy_id 填"baseline"，action_summary 填"基线测量"

额外的原始数据（变量值、证据来源等）写入 `autoloop-findings.md`，不放在 results.tsv。

### 跨文件主键规范

所有AutoLoop输出文件（results.tsv、findings.md、progress.md、plan.md）共享以下主键体系，确保跨文件可追溯、可join：

| 主键 | 格式 | 定义时机 | 贯穿文件 |
|------|------|---------|---------|
| iteration | 整数（从1递增） | 每轮开始时自动递增 | 全部四文件 |
| strategy_id | S{NN}-{简短描述} | DECIDE阶段命名 | 全部四文件 |
| problem_id | {维度缩写}{NNN}（如S001） | findings发现时命名 | findings + results.tsv |
| dimension | 与quality-gates.md维度名完全一致 | quality-gates.md定义 | results.tsv + findings |

**引用规则**：
- results.tsv 的 evidence_ref 必须引用 findings.md 中已定义的 problem_id
- progress.md 每轮记录必须在标题中注明 iteration 编号
- plan.md 策略历史的 strategy_id 必须与 findings.md 策略评估表一致
- 任何文件中出现的 dimension 名称必须与 quality-gates.md 完全匹配，不得使用同义词

---

## Bootstrap 规则（plan 完成后立即执行）

**plan 向导完成后，立即创建以下文件（不等待第 1 轮 OBSERVE）：**

```
1. autoloop-plan.md         （已由向导创建）
2. autoloop-findings.md     （包含：执行摘要、每轮发现记录、工程问题清单、信息缺口汇总、拓展方向、策略评估、模式识别、经验教训）
3. autoloop-progress.md     （包含：质量门禁总览、基线记录、每轮 8 阶段迭代循环、任务完成记录、策略历史）
4. autoloop-results.tsv     （写入表头行：iteration\tphase\tstatus\tdimension\tmetric_value\tdelta\tstrategy_id\taction_summary\tside_effect\tevidence_ref\tunit_id\tprotocol_version\tscore_variance\tconfidence\tdetails）
```

所有 4 个文件必须在第 1 轮 OBSERVE 开始前存在。创建后在 autoloop-plan.md 的"输出文件"表中将状态从"待创建"更新为"已创建"。

### SSOT 可选模式

当 `autoloop-plan.md` 设置 `ssot_mode: true` 时，启用结构化单一事实源模式：

- **数据源**：`autoloop-state.json`（JSON 格式），包含 plan/iterations/findings/results 全部数据
- **写操作**：所有状态变更通过 `scripts/autoloop-state.py` 写入 JSON，不直接编辑 MD 文件
- **渲染**：每轮结束时运行 `scripts/autoloop-render.py` 从 JSON 生成 4 个可读 MD 文件
- **读操作**：OBSERVE 阶段仍可读取 MD 文件（渲染后与 JSON 同步）
- **向后兼容**：未设置 `ssot_mode` 时，行为完全不变，直接读写 4 个 MD 文件
- **优势**：消除跨文件信息重复和不一致，支持 `query` 命令快速检索任意字段
- **初始化**：使用 `autoloop-state.py init` 替代 `autoloop-init.py`，自动创建 JSON + 4 个 MD

