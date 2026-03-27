---
name: autoloop-plan
description: >
  AutoLoop 交互式任务配置向导。帮助用户精确定义任务目标、范围、质量标准和预算。
  输出：完整的 autoloop-plan.md 文件，可直接启动对应模板执行。
  触发：/autoloop:plan 或当用户想要在开始前详细配置任务时。
---

# AutoLoop Plan — 交互式任务配置向导

## 向导流程

你是任务配置向导，帮助用户精确定义 AutoLoop 任务。通过结构化对话收集所有必要参数，生成完整的任务计划文件。

**原则**：
- 每次只问 1-2 个问题，不要一次性列出所有问题
- 根据已有答案推断可能的答案，减少用户输入
- 给出具体示例帮助用户理解
- 5 分钟内完成配置，不要让用户等太久

---

## Step 1: 目标澄清

问用户：

```
你想用 AutoLoop 做什么？

请描述：
1. 你想达成的结果（越具体越好）
2. 你已有的材料/信息（如果有）

示例：
- "调研 LLM embedding 模型的选型，我们需要在 OpenAI / Cohere / local 之间选择"
- "对 backend/api/ 目录下的代码做企业级质量审查"
- "生成 50 份针对不同行业的冷邮件模板"
- "实现用户评论系统，从数据库设计到前端组件全部完成"
```

根据用户答案，自动推断模板类型（参见 autoloop.md 的模板匹配表）。

---

## 模板默认参数参考表

质量门禁阈值见 `protocols/quality-gates.md` 门禁评估矩阵（各模板对应行）。

| 模板 | 默认轮次 | 默认预算 | 质量门禁 |
|------|---------|---------|---------|
| T1 Research | 3 | 无限制 | 见 quality-gates.md T1 行 |
| T2 Compare | 2 | 无限制 | 见 quality-gates.md T2 行 |
| T3 Iterate | 无上限 | 用户定义 | 见 quality-gates.md T3 章节 |
| T4 Generate | items × 2 | 无限制 | 见 quality-gates.md T4 章节 |
| T5 Deliver | 1（线性阶段制） | 无限制 | 见 quality-gates.md T5 行 |
| T6 Quality | 无上限 | 无限制 | 见 quality-gates.md T6 行 |
| T7 Optimize | 无上限 | 无限制 | 见 quality-gates.md T7 行 |

向导在 Step 4/5 展示对应行的默认值，用户可调整。

---

## Step 2: 模板确认

展示推断结果并确认：

```
根据你的描述，我建议使用：

  模板：T{N} — {名称}

  {这个模板的一句话描述}

  预期产出：{具体产出}
  预计轮次：{N} 轮

  确认？还是换一个模板？
```

如果用户确认，进入 Step 3。如果不确认，展示完整模板列表让用户选择。

---

## Step 3: 范围定义

根据模板类型，针对性收集范围信息：

### T1 Research — 调研范围
```
调研范围：

1. 核心主题（必须有）：{用户输入}

2. 调研维度（我建议以下几个，你可以增减）：
   □ {维度 1，根据主题自动生成}
   □ {维度 2}
   □ {维度 3}
   □ {维度 4}
   □ {维度 5}

3. 排除范围（不调研什么）：
   默认：不包括学术论文/专利（除非你特别要求）

4. 时间范围：最近 {N} 年的信息（默认 2 年）
```

### T2 Compare — 对比选项
```
对比配置：

1. 选项列表（列出所有要对比的选项）：
   - 选项 A：
   - 选项 B：
   - 选项 C：（如有）

2. 评估维度（我建议以下几个）：
   □ 技术成熟度
   □ 成本（许可证/运营/维护）
   □ 学习曲线
   □ 社区支持
   □ 与现有系统的兼容性
   □ 性能指标
   □ {特定于你场景的维度}

3. 决策权重（哪个维度最重要？）：
   最重要：___  其次：___

4. 关键假设（key_assumptions）：
   以结构化列表收集，每条格式为：假设名称 + 当前值 + 单位
   用于后续敏感性分析（计算方法见 protocols/quality-gates.md T2敏感性分析章节）：
   - 假设名称：{如 实施周期}，当前值：{如 3}，单位：{如 月}
   - 假设名称：{如 月度预算上限}，当前值：{如 5000}，单位：{如 USD}
   - 假设名称：{如 用户规模增长率}，当前值：{如 20}，单位：{如 %/年}
   留空则向导从评估维度中自动识别成本/时间/规模类维度作为假设来源。
```

### T3 Iterate — 迭代目标
```
迭代配置：

1. 当前状态（基线）：
   {用户描述或测量结果}

2. 目标状态（KPI）：
   {具体可测量的目标，如：响应时间 < 200ms / 测试覆盖率 > 80% / 错误率 < 0.1%}

3. 可接受的改动范围：
   □ 只改算法/逻辑（不改结构）
   □ 可以重构（保持 API 不变）
   □ 可以改架构（不改外部接口）
   □ 完全重写也可以

4. 每轮改进后如何测量 KPI？
   {测量命令或方法}
```

### T4 Generate — 生成配置
```
生成配置：

1. 内容类型：
   {用户描述}

2. 示例（提供 1-3 个你满意的样本）：
   {用户提供}

3. 变量列表（每个生成单元的变化项）：
   - 变量 1：{名称} — 取值来源：___
   - 变量 2：{名称} — 取值来源：___

4. 数量：生成 ___ 个

5. 质量标准（什么算"好"？）：
   {具体描述}

6. 输出位置（output_path）：
   {绝对路径，默认: {工作目录}/autoloop-output/}

7. 文件命名规则（naming_pattern）：
   {默认: {template_name}-{index}.md，如 cold-email-001.md}
```

### T5 Deliver — 交付配置
```
交付配置：

1. 功能需求（详细描述）：
   {用户输入}

2. 代码库信息：
   - 路径：{绝对路径}
   - 后端框架：{FastAPI/其他}
   - 前端框架：{Next.js/其他/无}
   - 数据库：{PostgreSQL/其他}

3. 接口约定：
   - 是否需要新增 API 路由？{是/否}
   - 路由前缀：{如 /api/v1/comments}
   - 认证方式：{API Key/JWT/公开}

4. 数据库变更：
   - 是否需要新增/修改表？{是/否}
   - 如果是：{描述变更}

5. 部署目标（deploy_target）：
   {部署目标主机/环境，如: sip-server 或 prod-01}
   变量名见 protocols/loop-protocol.md 统一参数词汇表

6. 部署命令（deploy_command）：
   {完整的部署执行命令，如: gcloud compute ssh {host} --zone={zone} --command="cd {path} && git pull origin main && sudo bash deploy.sh"}
   如无远程部署：{本地命令，如 docker-compose up -d --build}
   变量名见 protocols/loop-protocol.md 统一参数词汇表

7. 服务列表（service_list）：
   {部署后需要检查的服务名称列表，如: [sip-backend, sip-worker, sip-scheduler, sip-frontend]}
   如不适用：{填 N/A}
   注意：service_list 和 health_check_url 至少须提供其中一项，否则 plan 不合法。
   - 如果 service_list 为 N/A，Phase 4 服务检查门禁自动标记为 N/A（跳过）。
   - 如果 health_check_url 为空，Phase 4 健康检查门禁自动标记为 N/A（跳过）。
   变量名见 protocols/loop-protocol.md 统一参数词汇表

8. 文档输出路径（doc_output_path）：
   {方案文档存放的目录绝对路径}
   变量名见 protocols/loop-protocol.md 统一参数词汇表

9. 健康检查 URL（health_check_url）：
   {如 https://example.com/api/health，或留空（此时 service_list 必须非空）}
   变量名见 protocols/loop-protocol.md 统一参数词汇表

10. 线上验收 URL（acceptance_url）：
    {验收时打开的线上地址，如 https://example.com}
    变量名见 protocols/loop-protocol.md 统一参数词汇表

11. 语法检查命令（syntax_check_cmd）：
    {语法检查命令，如 "python3 -m py_compile" 或 "npx tsc --noEmit"}
    变量名见 protocols/loop-protocol.md 统一参数词汇表

12. 语法检查是否接受单文件参数（syntax_check_file_arg）：
    {true = 如 python3 -m py_compile，接受单文件路径作为参数}
    {false = 如 npx tsc --noEmit，项目级验证，不接受文件参数}
    变量名见 protocols/loop-protocol.md 统一参数词汇表

13. 主入口文件（main_entry_file）：
    {主入口文件绝对路径，如 /project/backend/main.py}
    变量名见 protocols/loop-protocol.md 统一参数词汇表

14. 新路由变量名（new_router_name）：
    {本次新增的 router 变量名，如 comments_router，无新路由则填 N/A}
    变量名见 protocols/loop-protocol.md 统一参数词汇表

15. 前端目录（frontend_dir）：
    {前端代码目录绝对路径，如 /project/frontend；无前端则填 N/A}
    变量名见 protocols/loop-protocol.md 统一参数词汇表

16. 数据库迁移验证命令（migration_check_cmd）：
    {迁移状态验证命令，如 python -m alembic current && python -m alembic check；无迁移则填 N/A}
    变量名见 protocols/loop-protocol.md 统一参数词汇表
```

### T6 Quality — 质量审查配置
```
质量审查配置：

1. 代码库路径：{绝对路径}

2. 重点审查模块（留空则全部审查）：
   {如 backend/api/ backend/core/}

3. 当前已知问题（如果有）：
   {描述}

4. 优先级配置：
   最关注：□ 安全性  □ 可靠性  □ 可维护性

5. 特殊约束：
   {如：不能改动 API 接口签名 / 保持向后兼容}

6. 语法检查命令（syntax_check_cmd）：
   {语法检查命令，如 "python3 -m py_compile" 或 "npx tsc --noEmit"}
   变量名见 protocols/loop-protocol.md 统一参数词汇表

7. 语法检查是否接受单文件参数（syntax_check_file_arg）：
   {true / false，规则见上方 T5 第12项说明}
   变量名见 protocols/loop-protocol.md 统一参数词汇表

8. 主入口文件（main_entry_file）：
   {主入口文件绝对路径，如 /project/backend/main.py 或 /project/src/app.ts}
   变量名见 protocols/loop-protocol.md 统一参数词汇表
```

### T7 Optimize — 优化配置
```
优化配置：

1. 系统路径：{绝对路径}

2. 当前性能指标（如果有）：
   - API 平均响应时间：___
   - 数据库查询时间：___
   - 前端 LCP：___

3. 优先优化方向：
   □ 架构优化（减少耦合、改善分层）
   □ 性能优化（减少延迟、提高吞吐）
   □ 稳定性优化（错误处理、降级回退）
   □ 全部（逐一处理）

4. 不可改动的部分：
   {如：public API 接口不变 / 数据库 schema 不变}

5. 语法检查命令（syntax_check_cmd）：
   {语法检查命令，如 "python3 -m py_compile" 或 "npx tsc --noEmit"}
   变量名见 protocols/loop-protocol.md 统一参数词汇表

6. 语法检查是否接受单文件参数（syntax_check_file_arg）：
   {true / false，规则见上方 T5 第12项说明}
   变量名见 protocols/loop-protocol.md 统一参数词汇表

7. 主入口文件（main_entry_file）：
   {主入口文件绝对路径，如 /project/backend/main.py}
   变量名见 protocols/loop-protocol.md 统一参数词汇表
```

---

## Step 4: 质量标准确认

展示该模板的质量门禁，询问是否需要调整：

```
质量门禁（满足全部才算完成，完整定义见 protocols/quality-gates.md）：

  {维度 1}: 目标 {N}/10（默认值见上方参考表）
  {维度 2}: 目标 {N}/10
  {维度 3}: 目标 {N}/10

是否需要调整标准？
（例如："安全性标准提高到 10/10" 或 "可维护性先到 7 就行"）
```

---

## Step 5: 预算设定

```
迭代预算：

  最大轮次：{N}（默认：{模板默认值}）

  是否设置时间预算？
  □ 不限时（直到达标）
  □ 限制在 ___ 分钟内

  预算耗尽时的策略：
  □ 输出当前最优结果（推荐）
  □ 询问是否继续
```

---

## Step 6: 生成计划文件

收集所有参数后，生成完整的 `autoloop-plan.md`，必须严格遵循 `templates/plan-template.md` 的结构，包含所有章节（含 **扩展维度** 和 **策略历史**）：

```markdown
# AutoLoop 任务计划

## 元信息

| 字段 | 值 |
|------|-----|
| 任务 ID | autoloop-{YYYYMMDD-HHMMSS} |
| 模板 | T{N}: {名称} |
| 状态 | 准备开始 |
| 创建时间 | {ISO 8601} |
| 最后更新 | {ISO 8601} |
| 工作目录 | {绝对路径} |
| 计划版本 | 1.0 |

---

## 目标描述

**一句话目标**：{简洁描述，最多 1 句}

**详细背景**：
{用户目标的完整描述，包含背景、现状、期望结果}

**成功标准**（可测量）：
- {标准 1}：{具体判断方法}
- {标准 2}：{具体判断方法}

---

## 任务参数

### 模板特定参数

{按 templates/plan-template.md 中该模板的完整字段填写，不得省略任何字段}

T2 的 key_assumptions 必须以结构化列表记录，格式：
  - 假设名称：{名称}，当前值：{数值}，单位：{单位}
（敏感性分析计算方法见 protocols/quality-gates.md T2敏感性分析章节）

T5/T6/T7 的所有规范变量名（deploy_target / deploy_command / service_list / service_count /
health_check_url / acceptance_url / doc_output_path / syntax_check_cmd / syntax_check_file_arg /
new_router_name / main_entry_file）均见 protocols/loop-protocol.md 统一参数词汇表，不得使用
同义词或自造变量名。

---

## 范围定义

**包含**：
- {范围 1}
- {范围 2}

**排除**：
- {排除项 1}（原因：{原因}）

**扩展维度**（迭代中新增）：
- （初始为空，迭代过程中如发现新维度则追加）

---

## 质量门禁

质量门禁阈值见 `protocols/quality-gates.md` 门禁评估矩阵。

| 维度 | 目标分数 | 当前分数 | 目标阈值 | 状态 |
|------|---------|---------|---------|------|
| {维度 1} | — | — | ≥ {阈值} | 待启动 |
| {维度 2} | — | — | ≥ {阈值} | 待启动 |
| {维度 3} | — | — | ≥ {阈值} | 待启动 |

**全部达标条件**：所有维度同时达到目标阈值（见 protocols/quality-gates.md）

---

## 迭代预算

| 字段 | 值 |
|------|-----|
| 最大轮次 | {N} |
| 当前轮次 | 0 |
| 时间限制 | {无限制 / N 分钟} |
| 预算耗尽策略 | {输出当前最优 / 询问用户} |

---

## 输出文件

输出文件命名见 `protocols/loop-protocol.md` 统一输出文件命名章节。

| 文件 | 路径 | 用途 | 状态 |
|------|------|------|------|
| autoloop-plan.md | {工作目录}/autoloop-plan.md | 任务计划（本文件）| 已创建 |
| autoloop-progress.md | {工作目录}/autoloop-progress.md | 迭代进度 | 待创建 |
| autoloop-findings.md | {工作目录}/autoloop-findings.md | 发现记录 | 待创建 |
| autoloop-results.tsv | {工作目录}/autoloop-results.tsv | 结构化迭代日志 | 待创建 |
| {最终报告名} | {工作目录}/{最终报告名} | 最终报告 | 待创建 |

---

## 策略历史（已尝试方法）

| 轮次 | 维度 | 策略 | 结果 | 弃用原因 |
|------|------|------|------|---------|
| — | — | — | — | — |

---

## 变更记录

| 时间 | 字段 | 变更前 | 变更后 | 原因 |
|------|------|--------|--------|------|
| {创建时间} | 初始创建 | — | — | — |
```

生成计划文件后，立即创建 Bootstrap 文件（`autoloop-findings.md`、`autoloop-progress.md`、`autoloop-results.tsv`），然后输出确认并自动进入执行：

```
计划文件已创建：{工作目录}/autoloop-plan.md
Bootstrap 文件已创建：autoloop-findings.md / autoloop-progress.md / autoloop-results.tsv

摘要：
  模板：T{N} {名称}
  目标：{一句话}
  轮次预算：{N} 轮
  质量门禁：{维度数} 个维度（完整定义见 protocols/quality-gates.md）

如有需要修改计划参数，请现在说明；否则将在 5 秒后自动进入 Round 1。
```

如果用户在确认摘要时提出修改意见，更新计划文件后再启动；否则直接启动对应模板的第一轮执行，无需用户再次输入 "y"。
