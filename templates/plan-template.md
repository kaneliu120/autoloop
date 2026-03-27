# AutoLoop 任务计划

## 元信息

| 字段 | 值 |
|------|-----|
| 任务 ID | autoloop-{YYYYMMDD-HHMMSS} |
| 模板 | T{N}: {名称} |
| 状态 | 准备开始 / 进行中 / 完成 / 预算耗尽 / 用户中断 |
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
- {标准 3}：{具体判断方法}

---

## 任务参数

### 模板特定参数

**T1 Research**：
- 核心主题：{主题}
- 调研维度：
  1. {维度 1}
  2. {维度 2}
  3. {维度 3}
- 排除范围：{不调研的内容}
- 时间范围：最近 {N} 年

**T2 Compare**：
- 选项 A：{描述}
- 选项 B：{描述}
- 评估维度：{维度 1}（权重 {X}%）、{维度 2}（权重 {Y}%）...
- 决策标准：{最重要的因素}
- key_assumptions（关键假设表，用于敏感性分析）：

| 假设名称 | 当前值 | 单位 | 敏感性区间（±20% 范围）|
|---------|--------|------|----------------------|
| {假设 1，如市场增长率} | {当前值，如 15} | {单位，如 %/年} | {低值} ~ {高值} |
| {假设 2，如实施周期} | {当前值，如 6} | {单位，如 月} | {低值} ~ {高值} |
| {假设 3，如团队规模} | {当前值，如 5} | {单位，如 人} | {低值} ~ {高值} |

**T3 Iterate**：
- KPI：{指标名} = {目标值}
- 当前基线：{基线值}（{测量时间}）
- 测量方法：{命令或步骤}
- 改动约束：{允许 / 不允许的改动范围}

**T4 Generate**：
- 内容类型：{类型}
- 数量：{N} 个
- 变量：{变量 1}、{变量 2}
- 质量阈值：{N}/10
- output_path：{输出目录绝对路径，默认 {工作目录}/autoloop-output/}
- naming_pattern：{文件命名规则，如 {template_name}-{index}.md}

**T5 Deliver**：
- project_type：{backend-api / fullstack / frontend-only / script / data-pipeline / library}（枚举值和激活矩阵见 protocols/loop-protocol.md）
- 功能描述：{详细需求}
- 代码库路径：{绝对路径}
- 新增路由：{是/否}，路由前缀：{前缀}
- new_router_name：{本次新增的 router 变量名，如 comments_router}
- main_entry_file：{主入口文件绝对路径，如 /project/backend/main.py 或 /project/src/app.ts}
- 数据库变更：{是/否}，变更内容：{描述}
- syntax_check_cmd：{语法检查裸命令，如 python3 -m py_compile 或 npx tsc --noEmit，不含文件参数占位符；文件参数由 syntax_check_file_arg 控制}
- syntax_check_file_arg：{true/false，语法检查命令是否接受单文件参数；python3 -m py_compile → true，npx tsc --noEmit → false}
- deploy_target：{部署目标主机/环境，如 prod-server}
- deploy_command：{完整部署执行命令，如 gcloud compute ssh ... --command="cd /opt/sip && git pull && sudo bash deploy.sh"}
- service_list：{服务名称列表，如 [backend-api, worker, scheduler, frontend]；不适用则填 N/A}
- service_count：{自动计算，= len(service_list)；service_list = N/A 时此项也 N/A}（与 protocols/loop-protocol.md 统一参数词汇表一致）
- health_check_url：{健康检查 URL，如 https://example.com/api/health；不适用则留空}
- acceptance_url：{线上验收 URL，如 https://example.com}
- doc_output_path：{方案文档输出目录绝对路径}

**T6 Quality**：
- project_type：{backend-api / fullstack / frontend-only / script / data-pipeline / library}（枚举值和激活矩阵见 protocols/loop-protocol.md）
- 代码库路径：{绝对路径}
- 审查模块：{模块列表 / 全量}
- syntax_check_cmd：{语法检查裸命令，如 python3 -m py_compile 或 npx tsc --noEmit，不含文件参数占位符；文件参数由 syntax_check_file_arg 控制}
- syntax_check_file_arg：{true/false，语法检查命令是否接受单文件参数}
- 已知问题：{描述 / 无}
- 特殊约束：{约束 / 无}

**T7 Optimize**：
- project_type：{backend-api / fullstack / frontend-only / script / data-pipeline / library}（枚举值和激活矩阵见 protocols/loop-protocol.md）
- 系统路径：{绝对路径}
- syntax_check_cmd：{语法检查裸命令，如 python3 -m py_compile 或 npx tsc --noEmit，不含文件参数占位符；文件参数由 syntax_check_file_arg 控制}
- syntax_check_file_arg：{true/false，语法检查命令是否接受单文件参数}
- 当前性能：{指标：值}
- 优先方向：{全部 / 架构 / 性能 / 稳定性}
- 不可修改：{内容}

---

## 范围定义

**包含**：
- {范围 1}
- {范围 2}

**排除**：
- {排除项 1}（原因：{原因}）
- {排除项 2}

**扩展维度**（迭代中新增）：
- {新维度}（第 {N} 轮新增，原因：{原因}）

---

## 质量门禁

| 维度 | 目标分数 | 当前分数 | 目标阈值 | 状态 |
|------|---------|---------|---------|------|
| {维度 1} | — | — | ≥ {阈值} | 待启动 |
| {维度 2} | — | — | ≥ {阈值} | 待启动 |
| {维度 3} | — | — | ≥ {阈值} | 待启动 |

**全部达标条件**：所有维度同时达到目标阈值

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

| 文件 | 路径 | 用途 | 状态 |
|------|------|------|------|
| autoloop-plan.md | {工作目录}/autoloop-plan.md | 任务计划（本文件）| 已创建 |
| autoloop-progress.md | {工作目录}/autoloop-progress.md | 迭代进度 | 待创建 |
| autoloop-findings.md | {工作目录}/autoloop-findings.md | 发现记录 | 待创建 |
| 最终报告 | {工作目录}/ | 最终报告（文件命名见 protocols/loop-protocol.md 统一输出文件命名章节）| 待创建 |
| autoloop-results.tsv | {工作目录}/autoloop-results.tsv | 结构化迭代日志（所有模板通用）| 待创建 |

---

## 策略历史（已尝试方法）

| 轮次 | 维度 | 策略 | 结果 | 弃用原因 |
|------|------|------|------|---------|
| — | — | — | — | — |

---

## 变更记录

| 时间 | 字段 | 变更前 | 变更后 | 原因 |
|------|------|--------|--------|------|
| {时间} | 初始创建 | — | — | — |
