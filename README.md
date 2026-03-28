# AutoLoop — 自主迭代引擎

AutoLoop 是一个 Claude Code skill，将模糊目标转化为精确执行计划，通过 OODA 循环持续迭代，调度专业 subagent 并行执行，直到质量门禁全部通过。

## 安装

### 方法一：直接复制到 skills 目录（推荐）

```bash
# 克隆仓库
git clone https://github.com/kaneliu120/autoloop.git

# 复制到 Claude Code skills 目录
cp -r autoloop ~/.claude/skills/autoloop

# 重启 Claude Code 会话使技能生效
```

### 方法二：符号链接（开发模式）

```bash
git clone https://github.com/kaneliu120/autoloop.git ~/Projects/autoloop
ln -s ~/Projects/autoloop ~/.claude/skills/autoloop
```

### 验证安装

在 Claude Code 中输入 `/autoloop`，如果技能被识别则安装成功。

---

## 快速上手

### 交互式启动

```
/autoloop
```

AutoLoop 会询问你想做什么，自动选择模板并开始执行。

### 直接指定模板

```
/autoloop:research  调研 LLM embedding 模型选型
/autoloop:quality   对 backend/api/ 目录做企业级质量审查
/autoloop:deliver   实现用户评论系统，从数据库到前端
/autoloop:optimize  对 SIP 后端做性能诊断和优化
```

### 配置向导

```
/autoloop:plan
```

通过交互式向导精确配置任务参数（目标、范围、质量标准、预算），生成 `autoloop-plan.md` 后开始执行。

---

## 7 个任务模板

| 模板 | 命令 | 适用场景 | 质量门禁（阈值见 quality-gates.md）|
|------|------|---------|---------|
| **Research** | `/autoloop:research` | 系统性调研某个领域/技术 | 覆盖率、可信度、一致性、完整性 |
| **Compare** | `/autoloop:compare` | 在多个选项中做决策 | 全维度覆盖、偏见检查、敏感性分析 |
| **Iterate** | `/autoloop:iterate` | KPI 驱动反复改进 | KPI 达目标值 |
| **Generate** | `/autoloop:generate` | 批量生成同类内容 | 通过率、平均分 |
| **Deliver** | `/autoloop:deliver` | 需求到生产全流程交付 | 7 阶段全通过、人工验收 |
| **Quality** | `/autoloop:quality` | 代码提升到企业级质量 | 安全性、可靠性、可维护性（复合判定）|
| **Optimize** | `/autoloop:optimize` | 系统架构/性能/稳定性优化 | 架构、性能、稳定性 |

---

## 使用示例

### 示例 1：技术选型调研

```
/autoloop:research

调研主题：Python 异步任务队列选型（Celery vs ARQ vs Dramatiq vs RQ）
我的技术栈：FastAPI + PostgreSQL + Redis，Python 3.11
核心需求：任务优先级、定时任务、失败重试、监控界面
```

AutoLoop 将：
1. 自动生成 8 个调研维度
2. 并行调度 8 个 researcher subagents
3. 交叉验证矛盾信息
4. 计算覆盖率/可信度/一致性/完整性
5. 迭代直到全部达标（阈值见 protocols/quality-gates.md T1 行）
6. 输出带证据的推荐报告

---

### 示例 2：企业级质量审查

```
/autoloop:quality

代码库路径：/Users/kane/Projects/sip/backend
重点模块：backend/api/ backend/core/
当前已知问题：有些 Redis 操作没有 try/except
```

AutoLoop 将：
1. 并行运行安全/可靠/可维护三个 reviewer
2. 初始评分：安全 7.5/可靠 6.2/可维护 7.8
3. 按 P1 → P2 → P3 优先级修复
4. 每次修复后 py_compile 验证无回归
5. 每 5 个修复后 checkpoint 重新评分
6. 迭代直到三维度全部达标
7. 输出企业级审计报告

---

### 示例 3：功能全流程交付

```
/autoloop:deliver

功能：为 SIP 平台添加公司标签系统
  - 用户可以给公司打标签（最多 10 个）
  - 可以按标签筛选公司列表
  - 标签数据持久化到 PostgreSQL

代码库：/Users/kane/Projects/sip
后端：FastAPI + SQLAlchemy 2.0 + PostgreSQL
前端：Next.js + TanStack Query
```

AutoLoop 将：
1. 分析现有代码库架构
2. 生成方案文档（等待确认）
3. 并行开发：后端 API + 前端组件
4. 代码审查（P1/P2 = 0 才进入下一步）
5. 语法验证（py_compile + tsc）
6. 提交并部署到 GCP
7. 线上验收（等待人工确认）

---

## 工作文件

每次 AutoLoop 任务在工作目录生成以下文件：

```
./
├── autoloop-plan.md          # 任务配置（范围、质量标准、预算）
├── autoloop-progress.md      # 每轮迭代详细记录
├── autoloop-findings.md      # 调研发现/问题清单（持续追加）
├── autoloop-results.tsv      # 结构化迭代日志（15 列 TSV，schema 见 loop-protocol.md）
└── autoloop-report-{topic}-{date}.md  # 最终报告（文件命名见 protocols/loop-protocol.md 统一输出文件命名章节）
```

---

## 核心设计原则

### 协议版本

当前协议版本：**1.0.0**（定义见 `protocols/loop-protocol.md`）。版本格式：`{major}.{minor}.{patch}`，变更须经 REFLECT 提案 + 用户确认（流程见 `protocols/evolution-rules.md`）。

### OODA 循环 + 认知积累反馈

每轮迭代严格执行 8 个阶段：
```
OBSERVE → ORIENT → DECIDE → ACT → VERIFY → SYNTHESIZE → EVOLVE → REFLECT
    ↑                                                                   |
    └───────────── 认知积累反馈 ──────────────────────────────────────────┘
```

不跳步，不合并，每步有明确的输入/输出。REFLECT 是强制环节，每轮必须写入 `autoloop-findings.md`，下一轮 OBSERVE 首先读取。跨任务经验沉淀到 `protocols/experience-registry.md`。

### 并行优先

独立任务一定并行，有依赖的任务串行。
不做无依据的串行等待。

### 单策略隔离

每轮 DECIDE 阶段只选择一个主策略执行，实现可归因的 A/B 验证。多策略并行无法归因分数变化。

### 质量门禁数字化 + Fail-Closed

所有门禁是数字，不是"感觉好了"（精确阈值见 `protocols/quality-gates.md`）：
- 一致性 87.5%（是否达标见 quality-gates.md T1 行一致性门禁）
- 安全得分 9.2/10（是否达标见 quality-gates.md T6 安全性门禁）

评分必须附带证据。无证据或低置信的评分视为未通过（fail-closed），必须下轮补充后重评。偏见检查中差异过大时运行独立评估仲裁。

### 人工确认点设计

T5 Deliver 有 2 个强制人工确认：
- 阶段 0.5：方案文档确认后才开发
- 阶段 5：线上验收才算完成

不绕过，不自动假设确认。

---

## 文件结构

```
autoloop/
├── SKILL.md                        # 主技能定义（入口）
├── README.md                       # 本文件
├── commands/
│   ├── autoloop.md                 # 主入口
│   ├── autoloop-plan.md            # 配置向导
│   ├── autoloop-research.md        # T1: 全景调研
│   ├── autoloop-compare.md         # T2: 多方案对比
│   ├── autoloop-iterate.md         # T3: 目标驱动迭代
│   ├── autoloop-generate.md        # T4: 批量内容生成
│   ├── autoloop-deliver.md         # T5: 全流程交付
│   ├── autoloop-quality.md         # T6: 企业级质量迭代
│   └── autoloop-optimize.md        # T7: 架构/性能/稳定性优化
├── protocols/
│   ├── loop-protocol.md            # OODA 循环规范（含协议版本 + 统一 TSV schema + 参数词汇表）
│   ├── quality-gates.md            # 质量门禁定义
│   ├── agent-dispatch.md           # Subagent 调度规范
│   ├── evolution-rules.md          # 轮间进化规则
│   ├── enterprise-standard.md      # 企业级标准评分体系
│   ├── delivery-phases.md          # 交付阶段规范（T5）
│   ├── experience-registry.md      # 全局经验库（跨任务经验沉淀与淘汰）
│   └── parameters.md               # 统一参数定义
└── templates/
    ├── plan-template.md            # 任务计划模板
    ├── findings-template.md        # 发现记录模板
    ├── progress-template.md        # 进度追踪模板
    ├── report-template.md          # 最终报告模板
    ├── audit-template.md           # 企业级审计报告模板
    └── delivery-template.md        # 交付方案文档模板
```

---

## 与 CLAUDE.md 的集成

AutoLoop 是 CLAUDE.md Orchestrator-First 模式的具体实现：

- **AutoLoop = 编排者**：规划、委派、审核
- **Subagents = 执行者**：backend-dev、frontend-dev、researcher 等
- **T5 Deliver = CLAUDE.md 强制开发流程**：7 阶段完全对应

结合项目 CLAUDE.md 使用 AutoLoop 时，所有工程决策遵循该项目的代码约定（技术栈在 `autoloop-plan.md` 中收集，T5/T6/T7 执行时以 plan 中的参数为准）。

> 示例（以实际项目为准）：如项目使用 FastAPI + SQLAlchemy，则 T5 的 syntax_check_cmd 填 `python3 -m py_compile`，main_entry_file 填实际主入口路径。

---

## 理念来源

AutoLoop 融合了三个框架：

1. **OODA 循环**（John Boyd）：在不确定环境下快速决策的军事框架
2. **Autoresearch 模式**（Karpathy）：AI 自主研究的迭代方法
3. **Orchestrator-First**（CLAUDE.md）：编排者优先，subagent 执行的多智能体架构

结合这三者，AutoLoop 在每轮迭代中：观察现状 → 分析差距 → 制定策略 → 并行执行 → 量化验证 → 动态调整。
