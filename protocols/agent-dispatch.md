# Agent Dispatch — 角色制度与团队配置

## 概述

本文档是 AutoLoop 的"岗位说明书"：定义所有可用角色及其职责边界，按任务模板配置标准团队，并规定协作规则。

Commands 在运行时根据本文件的角色定义 + 其他 protocol 动态生成派工指令，本文件不包含具体的 prompt 模板。

---

## 第一部分：角色总表

| 角色ID | 职责（一句话） | 知识来源 |
|--------|---------------|---------|
| researcher | 多源信息搜索与采集 | quality-gates.md 覆盖率/可信度门禁 |
| analyst | 数据分析、交叉验证、偏见检查 | quality-gates.md 分析门禁 |
| planner | 技术方案设计与任务分解 | delivery-phases.md Phase 0 |
| backend-dev | 后端代码实现 | enterprise-standard.md |
| frontend-dev | 前端代码实现 | enterprise-standard.md |
| db-migrator | 数据库迁移脚本 | enterprise-standard.md |
| code-reviewer | 安全+质量审查 | quality-gates.md + enterprise-standard.md |
| verifier | 语法检查、路由验证、线上验收 | quality-gates.md 验证门禁 |
| scanner | 架构/性能/稳定性问题扫描 | enterprise-standard.md |
| fixer | 最小化问题修复 | enterprise-standard.md + quality-gates.md |
| generator | 批量内容生成 | quality-gates.md T4 门禁 |
| scorer | 独立质量评分 | quality-gates.md 评分规则 |

---

## 第二部分：角色详细定义

### researcher

**职责**：多维度信息搜索与采集，确保来源多样性和可信度标注
**能力范围**：网络调研、竞品分析、多源搜索、数据验证
**知识来源**：运行时读取 `protocols/quality-gates.md` 覆盖率/可信度门禁章节
**输出格式**：结构化搜索结果（关键发现 + 数据点 + 信息缺口 + 相关发现），每条标注来源URL和可信度
**协作约束**：多个 researcher 搜索不同维度时必须并行

### analyst

**职责**：数据分析、交叉验证、矛盾检测、偏见检查、敏感性分析
**能力范围**：矛盾识别（同一事实的不同说法）、评分偏见检测、多源验证状态标注（confirmed/contradicted/unverified）
**知识来源**：运行时读取 `protocols/quality-gates.md` 分析门禁章节
**输出格式**：分析报告（矛盾报告表 + 验证状态汇总）或偏见评估报告
**协作约束**：不分析自己参与搜索的数据；T1 兼任最终质量门禁

### planner

**职责**：技术方案设计、影响面分析、依赖识别、风险评估
**能力范围**：架构理解、接口定义、实施顺序编排、模板提取（T4）
**知识来源**：运行时读取 `protocols/delivery-phases.md` Phase 0 章节
**输出格式**：技术方案（影响范围 + 接口定义 + 实施顺序与依赖 + 风险识别）
**协作约束**：方案须经用户确认后才能进入开发阶段

### backend-dev

**职责**：后端/服务端核心代码实现
**能力范围**：Python/FastAPI 开发、数据库操作、API 实现、异步编程
**知识来源**：运行时读取 `protocols/enterprise-standard.md` 后端规范章节
**输出格式**：代码实现 + 每个文件的语法验证结果 + 入口注册确认
**协作约束**：每个文件修改后立即执行 syntax_check_cmd 验证；可与 frontend-dev 并行

### frontend-dev

**职责**：前端代码实现
**能力范围**：Next.js/TypeScript 开发、组件实现、状态管理、UI/UX
**知识来源**：运行时读取 `protocols/enterprise-standard.md` 前端规范章节
**输出格式**：代码实现 + 语法验证结果（tsc --noEmit 必须通过）
**协作约束**：可与 backend-dev 并行；修改后立即验证

### db-migrator

**职责**：数据库迁移脚本创建、执行和验证
**能力范围**：DDL 设计、Alembic 迁移、upgrade/downgrade 实现、回滚支持
**知识来源**：运行时读取 `protocols/enterprise-standard.md` 数据库规范章节
**输出格式**：迁移文件路径 + upgrade()/downgrade() 实现 + 验证结果
**协作约束**：必须在 backend-dev 之前完成（代码依赖新数据库结构）；必须实现 downgrade() 支持回滚

### code-reviewer

**职责**：代码安全性+质量审查，按维度出具审查报告
**能力范围**：安全性（注入/XSS/路径穿越）、可靠性（异常处理/超时/降级）、可维护性（注册/导出/类型/重复）
**知识来源**：运行时读取 `protocols/quality-gates.md` 门禁评估矩阵 + `protocols/enterprise-standard.md` 对应维度扣分规则
**输出格式**：审查报告（问题清单表[ID/文件/行号/类型/P1-P3/描述/建议] + 维度评分 + 总结）
**协作约束**：不审查自己产出的代码；T6/T7 可角色化为单维度专家（安全/可靠性/可维护性）并行扫描

### verifier

**职责**：语法验证、路由注册验证、线上验收
**能力范围**：编译检查、路由抽查、冒烟测试、浏览器线上验收（可选用 Chrome DevTools MCP）
**知识来源**：运行时读取 `protocols/quality-gates.md` 验证门禁章节
**输出格式**：每步验证结果（通过/失败+具体输出）+ 总体结论
**协作约束**：线上验收须等待用户输入 'verified' 才算通过

### scanner

**职责**：系统级问题扫描诊断（不修复，只发现和分类）
**能力范围**：架构诊断（分层/耦合/API一致性）、性能诊断（N+1/连接池/缓存/阻塞）、稳定性诊断（降级/错误处理/超时）
**知识来源**：运行时读取 `protocols/enterprise-standard.md` 对应维度诊断项 + `protocols/quality-gates.md` 门禁标准
**输出格式**：问题清单（按严重级别 P1/P2/P3 分类）+ 维度评分
**协作约束**：三个维度可角色化并行扫描；只输出诊断结果，不执行修复

### fixer

**职责**：针对扫描/审查发现的具体问题执行最小化修复
**能力范围**：定点修复、回归验证、影响范围控制
**知识来源**：运行时读取 `protocols/enterprise-standard.md` + `protocols/quality-gates.md` 修复标准
**输出格式**：修复 diff + 语法验证结果 + 是否引入新问题（是/否）
**协作约束**：只修改标注的问题，不做额外改动；不改变函数签名和 API 接口；按 P1->P2->P3 顺序串行修复同一文件

### generator

**职责**：批量内容生成，附带质量自评
**能力范围**：模板化生成、变量填充、质量标准自评
**知识来源**：运行时读取 `protocols/quality-gates.md` T4 门禁章节
**输出格式**：生成内容（UNIT-START/UNIT-END 包裹）+ 质量自评分（各标准得分 + 综合得分）
**协作约束**：自评分与 scorer 独立评分分歧 > 2 分时，以 scorer 为准

### scorer

**职责**：独立质量评分，检测生成内容偏差
**能力范围**：按标准逐项评分、分歧标注、改进建议
**知识来源**：运行时读取 `protocols/quality-gates.md` 评分规则
**输出格式**：评分表（各标准得分 + 综合得分 + 通过/需改进/重生成）+ 改进建议
**协作约束**：评分独立于 generator 的自评；8-10 通过，7 标注改进点，5-6 需改进，1-4 需重生成

---

## 第二部分：任务团队配置

### T1 Research 团队

| 角色 | 职责 | 阶段 | 并行/串行 |
|------|------|------|----------|
| researcher (xN) | 多维度并行搜索，每人负责一个维度 | OBSERVE/ACT | 多个 researcher 并行 |
| analyst | 交叉验证（矛盾检测+多源验证）+ 最终质量门禁 | VERIFY/SYNTHESIZE | 串行于 researcher 之后 |

### T2 Compare 团队

| 角色 | 职责 | 阶段 | 并行/串行 |
|------|------|------|----------|
| researcher (xN) | 各选项数据收集，每人负责一个选项 | OBSERVE | 并行 |
| analyst | 偏见检查 + 敏感性分析 | VERIFY | 串行于 researcher 之后 |
| scorer | 独立评分（与 analyst 交叉校验） | ACT | 可与 analyst 并行 |

### T3 Decide 团队

| 角色 | 职责 | 阶段 | 并行/串行 |
|------|------|------|----------|
| analyst | 综合分析，输出决策建议 | ACT/SYNTHESIZE | 单角色 |

### T4 Generate 团队

| 角色 | 职责 | 阶段 | 并行/串行 |
|------|------|------|----------|
| planner | 从示例提取模板+变量+质量标准 | OBSERVE | 首先执行 |
| generator (xN) | 批量生成，每人负责一批单元 | ACT | 并行 |
| scorer | 独立质量评分 | VERIFY | 每个单元生成后串行评分 |

### T5 Deliver 团队

| 角色 | 职责 | 阶段 | 并行/串行 |
|------|------|------|----------|
| planner | 技术方案设计 | Phase 0 | 首先执行 |
| db-migrator | 数据库迁移（按需） | Phase 1 前置 | 串行于 planner 之后 |
| backend-dev | 后端实现 | Phase 1 | 串行于 db-migrator 之后；可与 frontend-dev 并行 |
| frontend-dev | 前端实现（按需） | Phase 1 | 可与 backend-dev 并行 |
| code-reviewer | 安全+质量审查 | Phase 2 | 串行于实现之后 |
| verifier | 语法验证 + 线上验收 | Phase 3/5 | 串行于审查之后 |

### T6 Quality 团队

| 角色 | 职责 | 阶段 | 并行/串行 |
|------|------|------|----------|
| scanner (x3) | 安全/可靠性/可维护性三维度扫描 | OBSERVE/ACT | 三维度并行 |
| fixer | 按 P1->P2->P3 顺序修复 | ACT | 同文件串行，不同文件可并行 |
| code-reviewer | 回归验证 | VERIFY | 每轮修复后串行验证 |

**scanner 角色化说明**：三个维度通过 prompt 参数角色化实现，不需要独立角色定义：
- 安全审查：prompt 指定只关注安全维度，读取 enterprise-standard.md 安全性章节
- 可靠性审查：prompt 指定只关注可靠性维度，读取 enterprise-standard.md 可靠性章节
- 可维护性审查：prompt 指定只关注可维护性维度，读取 enterprise-standard.md 可维护性章节

### T7 Optimize 团队

| 角色 | 职责 | 阶段 | 并行/串行 |
|------|------|------|----------|
| scanner (x3) | 架构/性能/稳定性三维度诊断 | OBSERVE/ACT | 三维度并行 |
| fixer | 按综合优先级顺序修复 | ACT | 同文件串行，不同文件可并行 |
| code-reviewer | 回归验证 | VERIFY | 每轮修复后串行验证 |

**scanner 角色化说明**：同 T6，三维度通过 prompt 参数角色化：
- 架构诊断：读取 enterprise-standard.md 架构维度
- 性能诊断：读取 enterprise-standard.md 性能维度
- 稳定性诊断：读取 enterprise-standard.md 稳定性维度

---

## 第三部分：协作规则

### 并行 vs 串行判断

**必须并行**（满足任一即并行）：
1. **输出独立**：A 的输出不是 B 的输入
2. **文件独立**：操作完全不同的文件集合
3. **维度独立**：搜索不同维度 / 扫描不同模块
4. **层次独立**：backend-dev 与 frontend-dev

**必须串行**（满足任一即串行）：
1. **输出依赖**：B 需要 A 的输出才能开始
2. **文件冲突**：A 和 B 修改同一个文件
3. **状态依赖**：B 的结果取决于 A 修改后的系统状态
4. **优先级依赖**：P1 修复完成前不开始 P2

### 角色隔离

1. **code-reviewer 不审查自己产出的代码** -- 实现和审查必须由不同角色执行
2. **scorer 独立于 generator** -- 评分不受生成者自评影响
3. **scanner 只诊断不修复** -- 诊断和修复职责分离

### 角色化调度

同一底层角色可通过 prompt 参数角色化为专项专家：
- code-reviewer -> 安全审查专家 / 可靠性审查专家 / 可维护性审查专家
- scanner -> 架构诊断专家 / 性能诊断专家 / 稳定性诊断专家
- researcher -> 正向分析者 / 批判性分析者（T2 偏见检查）

### 按需激活

标记"按需"的角色由任务的 project_type 激活矩阵决定是否启用：
- db-migrator：仅当任务涉及数据库变更时激活
- frontend-dev：仅当任务涉及前端变更时激活

### 角色调整

如需增减角色，通过 REFLECT 提案 -> 用户确认 -> 更新本文件。

### 失败处理

| 失败类型 | 处理策略 |
|---------|---------|
| 无法找到信息 | 换关键词/换来源/标注"信息不可用" |
| 输出格式错误 | 提取可用部分，补充缺失字段 |
| 代码验证失败 | 返回详细错误要求修复（重试上限 2 次，见 loop-protocol.md） |
| 超时 | 标记"部分完成"，记录进度，继续其他任务 |
| 并行冲突 | 以改动更小的为准，记录两种方案 |

### 上下文完整性（每次调度前检查）

每次派工必须包含：
- [ ] 角色定义（"你是 X 角色"）
- [ ] 具体任务（可操作的指令）
- [ ] 所有相关文件的**绝对路径**
- [ ] 约束（什么不能改）
- [ ] 验收标准
- [ ] 输出格式
- [ ] 当前迭代轮次
- [ ] 上下文摘要（遗留问题 + 有效/无效策略 + 已识别模式）

**缺少任一项 -> 重写指令再调度。**

---

## 附录：技术栈变量示例

本附录提供具体技术栈下的变量填充示例，供 commands 运行时参考。

### Python/FastAPI

| 变量 | 填充值 |
|------|--------|
| `syntax_check_cmd` | `python3 -m py_compile` |
| `main_entry_file` | `{codebase_path}/backend/main.py` |
| `migration_check_cmd` | `python -m alembic current && python -m alembic check` |
| `tech_constraints` | async def 路由函数；SQLAlchemy 2.0 async session；配置从 settings 获取；新路由在 main.py 注册 |

### Next.js/TypeScript

| 变量 | 填充值 |
|------|--------|
| `syntax_check_cmd` | `npx tsc --noEmit` |
| `main_entry_file` | `{codebase_path}/app/layout.tsx` |
| `tech_constraints` | TypeScript 不使用 any；API 调用通过 /api/* 路由；TanStack Query v5；Tailwind CSS v4 |

### Node.js/TypeScript

| 变量 | 填充值 |
|------|--------|
| `syntax_check_cmd` | `npx tsc --noEmit` |
| `main_entry_file` | `{codebase_path}/src/index.ts` |
| `migration_check_cmd` | `npx drizzle-kit check` 或 `npx knex migrate:status` |
| `tech_constraints` | TypeScript 不使用 any；新路由在入口文件注册；async/await 异步操作 |
