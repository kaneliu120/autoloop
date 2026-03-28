# AutoLoop Skill 标准化改进框架

**日期**: 2026-03-28
**依据**: agentskills.io best practices + AutoLoop 当前结构审计
**目标**: 将 AutoLoop 从"大型文档集"重构为符合 agent skill 最佳实践的标准化结构

---

## 一、Best Practices 核心原则 vs AutoLoop 现状

| 原则 | Best Practice 要求 | AutoLoop 现状 | 差距 |
|------|-------------------|-------------|------|
| SKILL.md < 500 行 | 主文件精简，仅导航+高层流程 | 405 行（勉强合规），但承载了太多定义 | 中 |
| 扁平一级目录 | scripts/ references/ assets/ 各一级 | protocols/ 有二级（domain-packs/），commands/ 有 10 个文件 | 高 |
| 渐进式加载（JiT） | 仅在需要时读取辅助文件 | 所有协议被 SKILL.md 引用但无明确"何时读取"指令 | 高 |
| 脚本 = 确定性 CLI | 小型单用途 CLI，stdout/stderr 反馈 | 7 个脚本符合，但无统一 CLI 接口标准 | 中 |
| 第三人称祈使句 | "Extract the text..." 而非 "You should..." | 混合使用中文描述 + 第二人称 | 低 |
| 无人类文档 | 不创建 README/CHANGELOG | 有 README.md + TODO.md | 中 |
| 触发词优化 | description 含正/负触发词 | 有正触发词，缺负触发词 | 低 |
| 元数据验证脚本 | 自动化校验 name/description | 无 | 高 |
| 错误处理章节 | SKILL.md 底部有 Error Handling | 无专门错误处理章节 | 高 |

---

## 二、当前目录结构问题

```
autoloop/                          # 49 文件，结构混乱
├── SKILL.md                       # 405 行，勉强合规
├── README.md                      # ❌ 人类文档，不应存在
├── TODO.md                        # ❌ 人类文档，不应存在
├── autoloop-plan.md               # ❌ 运行时产物，不应在仓库中
├── autoloop-progress.md           # ❌ 运行时产物
├── autoloop-findings.md           # ❌ 运行时产物
│
├── commands/                      # 10 个命令文件 — 职责模糊
│   ├── autoloop.md               # 入口路由（应在 SKILL.md 中）
│   ├── autoloop-plan.md          # 计划向导（500+ 行，过大）
│   └── autoloop-{template}.md    # 7 个模板命令（每个 200-500 行）
│
├── protocols/                     # 12 个协议文件 — 是 references 还是 protocols？
│   ├── domain-packs/             # ❌ 二级目录，违反扁平原则
│   │   ├── README.md
│   │   ├── python-fastapi.md
│   │   └── nextjs-typescript.md
│   ├── loop-protocol.md          # 核心循环（680+ 行，过大）
│   ├── quality-gates.md          # 门禁定义（650+ 行，过大）
│   └── ...
│
├── templates/                     # 6 个模板文件 — 应为 assets
│
├── scripts/                       # 7 个脚本 — 基本符合，但缺统一接口
│
├── mcp-server/                    # ❌ 非标准目录
│
├── {compare,deliver,...}/SKILL.md # 8 个子命令 SKILL — 几乎是空包装
│   └── SKILL.md                  # 每个 ~15 行，纯 passthrough
│
└── plan/SKILL.md                  # 同上
```

### 核心问题

1. **职责混乱**: `commands/` 和 `protocols/` 的界限不清 — 命令文件包含协议内容，协议文件包含执行指令
2. **上下文膨胀**: protocols/ 总计 ~4,500 行，一次全加载会爆掉上下文窗口
3. **运行时产物污染仓库**: autoloop-plan/progress/findings.md 是运行时文件，不应 commit
4. **子命令 SKILL.md 无价值**: 8 个子命令目录各含一个 ~15 行的 passthrough SKILL.md
5. **二级目录**: domain-packs/ 违反扁平一级原则
6. **人类文档**: README.md、TODO.md 不应出现在 skill 中

---

## 三、改进后的标准目录结构

```
autoloop/
├── SKILL.md                       # 入口 — 导航+路由+核心循环概要 (<500行)
│
├── scripts/                       # 确定性工具 — 小型 CLI，stdout/stderr 反馈
│   ├── autoloop-controller.py    # 🆕 主循环控制器（核心引擎）
│   ├── autoloop-state.py         # SSOT 状态管理
│   ├── autoloop-score.py         # 多模板评分器
│   ├── autoloop-validate.py      # 跨文件验证器
│   ├── autoloop-render.py        # SSOT → markdown 渲染
│   ├── autoloop-init.py          # Bootstrap（增强版）
│   ├── autoloop-tsv.py           # TSV 操作
│   ├── autoloop-variance.py      # 方差/置信度
│   ├── autoloop-experience.py    # 🆕 经验库读写
│   ├── autoloop-finalize.py      # 🆕 最终报告生成
│   └── validate-metadata.py      # 🆕 元数据校验（from best practices）
│
├── references/                    # JiT 加载的协议/规范（只在需要时读取）
│   ├── loop-protocol.md          # 核心循环定义（精简版，<300行）
│   ├── quality-gates.md          # 门禁定义+阈值+hard/soft 矩阵
│   ├── agent-dispatch.md         # subagent 调度规范
│   ├── enterprise-standard.md    # T6/T7 评分细则
│   ├── evolution-rules.md        # 协议进化规则
│   ├── experience-registry.md    # 策略经验库
│   ├── parameters.md             # 参数集中定义
│   ├── delivery-phases.md        # T5 交付阶段
│   ├── orchestration.md          # Pipeline 编排
│   ├── domain-pack-fastapi.md    # Python/FastAPI 检测规则（扁平化）
│   ├── domain-pack-nextjs.md     # Next.js/TypeScript 检测规则（扁平化）
│   ├── domain-pack-spec.md       # Domain Pack 框架定义（原 README.md）
│   └── checklist.md              # 🆕 技能质量检查清单
│
├── assets/                        # 输出模板 + 静态文件
│   ├── plan-template.md          # Plan 输出模板
│   ├── progress-template.md      # Progress 输出模板
│   ├── findings-template.md      # Findings 输出模板
│   ├── report-template.md        # 最终报告模板
│   ├── audit-template.md         # T6 审计模板
│   ├── delivery-template.md      # T5 交付模板
│   └── checkpoint-schema.json    # 🆕 检查点 JSON schema
│
└── mcp-server/                    # MCP 集成（可选增强层）
    ├── server.py
    ├── install.sh
    └── mcp-config.json
```

### 变更对照

| 当前 | 改进后 | 变更类型 |
|------|--------|---------|
| `commands/autoloop.md` | 合并入 `SKILL.md` | 删除，内容上移 |
| `commands/autoloop-plan.md` | 精简后合并入 `SKILL.md` Step 1 | 删除，精简上移 |
| `commands/autoloop-{template}.md` × 7 | 合并入 `SKILL.md` 各模板段 + JiT 引用 references/ | 删除，精简上移 |
| `protocols/` × 12 | → `references/` | 重命名，扁平化 |
| `protocols/domain-packs/` (二级) | → `references/domain-pack-*.md` | 扁平化 |
| `templates/` × 6 | → `assets/` | 重命名 |
| `{compare,deliver,...}/SKILL.md` × 8 | 删除 | 子命令路由在主 SKILL.md 中处理 |
| `README.md` | 删除 | 人类文档 |
| `TODO.md` | 删除（内容迁移到项目管理工具） | 人类文档 |
| `autoloop-plan/progress/findings.md` | `.gitignore` | 运行时产物 |

---

## 四、SKILL.md 标准化框架

```markdown
---
name: autoloop
description: >
  Autonomous iteration engine combining OODA loop with subagent parallel execution.
  7 task templates: research, compare, iterate, generate, deliver, quality, optimize.
  Executes multi-round improvement cycles with quality gates until targets are met.
  Use when tasks require systematic iteration, quality-gated delivery, or multi-dimensional optimization.
  Do not use for single-shot tasks, simple questions, or tasks without measurable quality criteria.
---

# AutoLoop — 自主迭代引擎

## Step 0: 初始化

1. 确定任务类型（T1-T7），匹配规则见下方路由表
2. 如果工作目录无 `autoloop-state.json`：
   执行 `python3 scripts/autoloop-controller.py <work_dir> --init --template T{N}`
3. 如果存在 `checkpoint.json`（中断恢复）：
   执行 `python3 scripts/autoloop-controller.py <work_dir> --resume`

## Step 1: 路由与模板选择

[精简的路由表 — 触发词 → 模板映射]
[置信度匹配规则 — 引用 references/parameters.md §路由匹配参数]

## Step 2: 计划配置

[精简的 plan 收集流程 — 引用 assets/plan-template.md]
[门禁阈值自动注入 — 由 controller 从 references/quality-gates.md 读取]

## Step 3: 执行循环

执行 `python3 scripts/autoloop-controller.py <work_dir>` 启动主循环。
控制器自动驱动 8 阶段 OODA 循环。

### 各阶段 Agent 职责

[精简表格：OBSERVE/ORIENT/DECIDE/ACT/VERIFY/SYNTHESIZE/EVOLVE/REFLECT]
[每个阶段只写 2-3 行核心职责，详细规范 JiT 引用 references/]

### 模板特定行为

[T1-T7 差异表 — 仅列关键差异，详细见 references/]

## Step 4: 终止与报告

1. 控制器判断终止条件（全部 Hard Gate 通过 / 预算耗尽 / 用户中断）
2. 执行 `python3 scripts/autoloop-finalize.py <work_dir>`
3. 输出最终报告（格式见 assets/report-template.md）

## Step 5: 经验沉淀

控制器自动将策略效果写入 `references/experience-registry.md`
（详细规则见 references/experience-registry.md §效果记录）

## Error Handling

* 如果 `autoloop-controller.py` 在 ACT 阶段失败（subagent 超时/报错）：
  读取 checkpoint.json，从失败阶段的 OBSERVE 重新开始
* 如果 `autoloop-score.py` 返回全维度 0 分：
  读取 references/quality-gates.md 确认门禁定义是否与模板匹配
* 如果 `autoloop-state.json` 与 markdown 视图不同步：
  执行 `python3 scripts/autoloop-render.py <work_dir>` 重新生成
* 如果 experience-registry.md 为空（首次运行）：
  跳过经验读取，DECIDE 使用默认策略

## Quick Reference

/autoloop          → 交互式入口
/autoloop:plan     → 向导式配置
/autoloop:research → T1 全景调研
/autoloop:compare  → T2 多方案对比
/autoloop:iterate  → T3 目标驱动迭代
/autoloop:generate → T4 批量生成
/autoloop:deliver  → T5 全流程交付
/autoloop:quality  → T6 企业级质量
/autoloop:optimize → T7 架构优化
/autoloop:pipeline → 多模板链式执行
```

---

## 五、JiT 加载规范

每个 references/ 文件标注"何时加载"：

| 文件 | 加载时机 | 触发条件 |
|------|---------|---------|
| loop-protocol.md | Step 3 执行循环 | 控制器需要阶段转换规则时 |
| quality-gates.md | Step 2 计划配置 + VERIFY | 需要门禁阈值时 |
| agent-dispatch.md | ACT 阶段 | 委派 subagent 时 |
| enterprise-standard.md | T6/T7 OBSERVE | 需要评分细则时 |
| evolution-rules.md | EVOLVE 阶段 | 需要进化/终止规则时 |
| experience-registry.md | OBSERVE + REFLECT | 读取推荐策略 / 写入策略效果 |
| parameters.md | Step 1 路由 + EVOLVE | 需要阈值/参数时 |
| delivery-phases.md | T5 ACT 阶段 | T5 特定阶段规则 |
| orchestration.md | Pipeline 模式 | 多模板链式执行时 |
| domain-pack-*.md | T6/T7 OBSERVE | 自动检测技术栈时 |
| checklist.md | 发布前验证 | Skill 修改后自查 |

---

## 六、脚本 CLI 标准

所有 scripts/ 遵循统一接口：

```
用法: autoloop-{tool}.py <work_dir> [command] [args] [--json]

退出码:
  0 = 成功
  1 = 验证失败（gates 未通过、数据不一致）
  2 = 参数错误

输出:
  stdout = 结构化结果（默认人类可读，--json 为 JSON）
  stderr = 错误信息（供 agent 自纠正）
```

### 新增脚本接口

```
autoloop-controller.py <work_dir>                    # 启动/继续主循环
autoloop-controller.py <work_dir> --init --template T{N}  # 初始化
autoloop-controller.py <work_dir> --resume           # 从 checkpoint 恢复
autoloop-controller.py <work_dir> --status           # 查看当前状态

autoloop-experience.py <work_dir> query --template T{N} [--tags tag1,tag2]  # 查询推荐策略
autoloop-experience.py <work_dir> write --strategy-id S01 --effect 保持 --score 8  # 写入效果

autoloop-finalize.py <work_dir>                      # 生成最终报告
autoloop-finalize.py <work_dir> --json               # JSON 输出

validate-metadata.py --name "autoloop" --description "..."  # 元数据校验
```

---

## 七、质量检查清单（AutoLoop 专用）

### 1. 元数据与发现性
- [ ] name 字段 = 目录名 = "autoloop"
- [ ] description < 1024 字符，含正触发词 + 负触发词
- [ ] 第三人称祈使句，无 "I/you/我/你"

### 2. 文件结构
- [ ] 所有文件扁平一级（无 references/subfolder/）
- [ ] 仅使用 scripts/ references/ assets/ mcp-server/
- [ ] 无 README.md / TODO.md / CHANGELOG.md
- [ ] 运行时产物（autoloop-plan.md 等）在 .gitignore 中
- [ ] 所有路径使用正斜杠 `/`

### 3. SKILL.md 逻辑
- [ ] < 500 行
- [ ] 祈使句指令（"执行..."、"读取..."、"验证..."）
- [ ] 编号步骤序列，决策树明确
- [ ] 大型规范在 references/ 中，JiT 加载
- [ ] 术语一致（单一概念单一名称）

### 4. 脚本确定性
- [ ] 每个脚本是独立 CLI，接受参数
- [ ] 成功 → stdout 人类可读 + --json 可选
- [ ] 失败 → stderr 描述性错误，供 agent 自纠正
- [ ] 无库代码，单一用途
- [ ] controller.py 驱动完整循环，无需 LLM 手动推进

### 5. 错误处理
- [ ] SKILL.md 含 Error Handling 章节
- [ ] 每个常见失败状态有恢复步骤
- [ ] checkpoint.json 支持中断恢复
- [ ] 验证脚本在关键步骤前运行

### 6. AutoLoop 专属
- [ ] 8 阶段 OODA 循环由 controller.py 自动驱动
- [ ] 经验库读写由 autoloop-experience.py 执行（非 LLM 手动）
- [ ] VERIFY 自动调用 score.py（非 LLM 记忆）
- [ ] SSOT JSON 为唯一写入权威，markdown 为派生视图
- [ ] Hard Gate 失败 → 自动暂停 + checkpoint
- [ ] 门禁定义唯一来源 = quality-gates.md（score.py 消费，非重复定义）

---

## 八、实施路径

| 阶段 | 内容 | 文件变更 |
|------|------|---------|
| **Phase 1** | 目录重构：protocols/ → references/，templates/ → assets/，删除子命令 SKILL.md | 重命名 ~20 文件 |
| **Phase 2** | SKILL.md 重写：从 405 行的定义文档 → 标准 Step 1-5 流程 + JiT 引用 | 1 文件重写 |
| **Phase 3** | 编写 controller.py（核心引擎） | 1 新文件 ~500 行 |
| **Phase 4** | 编写 experience.py + finalize.py + validate-metadata.py | 3 新文件 |
| **Phase 5** | references/ 文件精简（每个 < 300 行，拆分过大文件） | ~5 文件精简 |
| **Phase 6** | 清理：删除 README.md/TODO.md，.gitignore 运行时产物 | 删除 + gitignore |
| **Phase 7** | Codex R12 验证 | 评审 |

### 预期文件数变化

| 维度 | 当前 | 改进后 | 变化 |
|------|------|--------|------|
| 总文件数 | 49 | ~30 | -19 |
| 目录数 | 12 | 4 | -8 |
| SKILL.md 行数 | 405 | <400 | 精简 |
| protocols 最大文件 | 680 行 | <300 行 | 拆分 |
| 人类文档 | 2 | 0 | 删除 |
| 运行时产物 | 3 | 0（gitignore） | 隔离 |
| 子命令 SKILL.md | 8 | 0 | 合并入主 SKILL.md |
