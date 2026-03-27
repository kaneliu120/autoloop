# AutoLoop 一致性底稿（Canonical Baseline）

> **用途**：所有 commands/templates 的修改必须对照本底稿验证。本文件从 protocols/ 提取，是修改和审查的唯一参照。
> **规则**：commands/templates 中不得复制本文件的内容，只能引用 protocols/ 链接。

---

## 1. 参数词汇表（真源：loop-protocol.md）

### 1.1 完整变量清单（16个）

| # | 变量名 | 适用模板 | 必填/可选 |
|---|--------|---------|----------|
| 1 | project_type | T5/T6/T7 | 必填 |
| 2 | deploy_target | T5 | 可选 |
| 3 | deploy_command | T5 | 可选 |
| 4 | service_list | T5 | 可选 |
| 5 | service_count | T5 | 自动 |
| 6 | health_check_url | T5 | 可选 |
| 7 | acceptance_url | T5 | 可选 |
| 8 | doc_output_path | T5 | 必填 |
| 9 | syntax_check_cmd | T5/T6/T7 | 必填 |
| 10 | syntax_check_file_arg | T5/T6/T7 | 必填 |
| 11 | new_router_name | T5 | 条件必填 |
| 12 | main_entry_file | T5/T6 | 条件必填 |
| 13 | output_path | T4 | 必填 |
| 14 | naming_pattern | T4 | 必填 |
| 15 | key_assumptions | T2 | 必填 |
| 16 | migration_check_cmd | T5 | 条件必填 |
| 17 | frontend_dir | T5 | 条件必填 |

### 1.2 激活矩阵（6 project_type × 10 变量）

| 变量 | backend-api | fullstack | frontend-only | script | data-pipeline | library |
|------|:-----------:|:---------:|:-------------:|:------:|:-------------:|:-------:|
| deploy_target | ✓ | ✓ | ✓ | ○ | ✓ | ○ |
| deploy_command | ✓ | ✓ | ✓ | ○ | ✓ | ○ |
| service_list | ✓ | ✓ | ○ | ○ | ○ | ○ |
| health_check_url | ✓ | ✓ | ○ | ○ | ○ | ○ |
| acceptance_url | ✓ | ✓ | ✓ | ○ | ○ | ○ |
| new_router_name | ✓ | ✓ | ○ | ○ | ○ | ○ |
| main_entry_file | ✓ | ✓ | ○ | ○ | ○ | ○ |
| migration_check_cmd | ✓ | ✓ | ○ | ○ | ✓ | ○ |
| frontend_dir | ○ | ✓ | ✓ | ○ | ○ | ○ |
| syntax_check_cmd | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |

✓ = 必填 ○ = 可选（N/A 跳过）

### 1.3 syntax_check_cmd 契约

- 存储格式：**裸命令**（如 `python3 -m py_compile`），不含 `{file}` 或 `{文件路径}`
- 文件参数追加：由 `syntax_check_file_arg` 控制（true=追加文件路径，false=不追加）
- commands/templates 中不得内联技术栈特定命令，只能引用 `{syntax_check_cmd}`

---

## 2. 门禁定义（真源：quality-gates.md）

### 2.1 验证层级

| 层级 | 名称 | 方法 | 通用规则 |
|------|------|------|---------|
| L1 | 近似检查 | grep/awk/文本搜索 | **所有 grep/awk/文本匹配型验证默认标注 [L1]** |
| L2 | 精确验证 | 框架特定/AST/运行时 | 最终验收或关键门禁 |

### 2.2 T5 门禁摘要

| Phase | 门禁 | 条件化 |
|-------|------|--------|
| Phase 0 | 文件识别+风险识别+验收标准 | 无条件 |
| Phase 0.5 | 文档完整+人工confirmed | 阻塞 |
| Phase 1 | 语法通过+路由注册[L1]+导出完整+无静默失败 | 路由/迁移按N/A跳过 |
| Phase 2 | P1=0, P2=0 | 无条件 |
| Phase 3 | 语法+路由[L1]+迁移 | 路由/迁移按N/A跳过 |
| Phase 4 | git push + deploy + service + health | **全部按N/A条件化** |
| Phase 5 | 按project_type验收 + 人工verified | **验收方式按type分流，人工确认无条件** |

### 2.3 T5 Phase5 验收分流

| project_type | 验收方式 |
|-------------|---------|
| backend-api / fullstack / frontend-only | 浏览器（桌面+手机）+ Console零错误 |
| script | CLI执行验证 + 错误输入测试 |
| data-pipeline | 批处理结果抽样 + 日志检查 |
| library | import验证 + 公共API调用 |
| **所有类型** | **人工输入 "verified"（不受N/A影响）** |

### 2.4 T6 复合判定

条件一（分数）：安全≥9, 可靠≥8, 可维护≥8
条件二（计数）：P1=0, 安全P2=0, 可靠P2≤3, 可维护P2≤5
两个条件必须同时满足。

### 2.5 T7 门禁

架构≥8, 性能≥8, 稳定≥8，任一未达标则继续。

---

## 3. 输出命名（真源：loop-protocol.md）

| 模板 | 最终报告 |
|------|---------|
| T1/T2/T3 | autoloop-report-{topic}-{date}.md |
| T4 | {output_path}/{naming_pattern} + autoloop-report-{topic}-{date}.md |
| T5 | autoloop-delivery-{feature}-{date}.md |
| T6/T7 | autoloop-audit-{date}.md |

---

## 4. 状态枚举（真源：loop-protocol.md）

- 问题状态：`新发现 | 已修复 | 待处理 | 跨轮遗留`
- 策略评价：`保持 | 避免 | 待验证`

---

## 5. commands/templates 引用规则（本次修复的核心）

### 5.1 commands 应该包含的内容（执行动作）

- subagent dispatch 的完整 prompt 模板
- 执行步骤的先后顺序和依赖关系
- 每个阶段的输入/输出格式
- 阻塞点的用户交互流程
- 错误处理和回退策略

### 5.2 commands 不应该包含的内容（规则定义 → 引用protocol）

- ✗ 门禁阈值（引用 quality-gates.md）
- ✗ 参数必填/可选规则（引用 loop-protocol.md 激活矩阵）
- ✗ 验证命令的具体 grep pattern（引用 quality-gates.md 路由注册门禁）
- ✗ 评分维度和公式（引用 quality-gates.md / enterprise-standard.md）
- ✗ 参数列表的手动子集（引用 loop-protocol.md 词汇表）

### 5.3 引用格式标准

当 command 需要引用 protocol 规则时，使用以下格式：
- 门禁：`门禁详情见 protocols/quality-gates.md {章节名}`
- 参数：`参数以 protocols/loop-protocol.md 统一参数词汇表为准`
- 验证：`验证方法见 protocols/quality-gates.md 路由注册门禁`
- 条件化：`必填性由 project_type 激活矩阵决定（见 protocols/loop-protocol.md）`

### 5.4 plan 向导字段收集规则

收集 project_type 后，执行以下流程：
1. 读取 `protocols/loop-protocol.md` 的"项目类型与变量激活矩阵"
2. 找到用户选择的 project_type 列
3. 标记为 ✓ 的变量 → 必须询问用户
4. 标记为 ○ 的变量 → 询问"是否适用？"，不适用则自动填 N/A
5. 不在当前模板适用范围的变量 → 跳过

---

## 6. 审查检查清单（修改后逐项验证）

- [ ] commands 中无门禁阈值硬编码（搜索：≥ 8, ≥ 9, = 0, ≤ 3, ≤ 5）
- [ ] commands 中无参数列表手动子集（搜索：变量枚举）
- [ ] commands 中无 grep pattern 硬编码（搜索：grep -n）→ 应引用 quality-gates.md
- [ ] commands 中无技术栈特定命令（搜索：py_compile, tsc, alembic）→ 应用 {syntax_check_cmd}
- [ ] 所有 grep/awk 验证标注 [L1]
- [ ] 所有条件化用统一格式：`（当 {variable} ≠ N/A 时）`
- [ ] plan 向导按激活矩阵动态生成问题，非必填字段不无条件询问
- [ ] delivery-template 人工验收不绑定 acceptance_url（所有 project_type 均需 verified）
- [ ] T6 终止规则引用 quality-gates.md 复合判定，不内联
