# Delivery Phases — 交付阶段规范

## 概述

本文档定义 AutoLoop T5（Deliver）的完整交付阶段，严格映射 CLAUDE.md 的强制开发流程。每个阶段有明确的输入、输出、质量门禁和阻塞条件。

---

## 阶段映射关系

| AutoLoop 阶段 | CLAUDE.md 阶段 | 说明 |
|-------------|--------------|------|
| Phase 0: 分析 | 阶段 0: 分析 | planner + researcher 并行 |
| Phase 0.5: 文档化 | 阶段 0.5: 方案文档化 | 必须人工确认 |
| Phase 1: 开发 | 阶段 1: 开发 | backend + frontend + db 并行 |
| Phase 2: 审查 | 阶段 2: 审查 | code-reviewer 串行审查 |
| Phase 3: 测试 | 阶段 3: 测试验证 | verifier 执行 |
| Phase 4: 部署 | 阶段 4: 部署上线 | git push + {deploy_command} |
| Phase 5: 验收 | 阶段 5: 线上验收 | verifier + 人工确认 |

---

## Phase 0: 分析

### 输入
- 功能需求描述（来自 autoloop-plan.md）
- 代码库路径（绝对路径）
- 技术栈信息
- **T5 必须额外收集（在 plan 阶段）**：所有 T5 参数见 `protocols/loop-protocol.md` 统一参数词汇表（deploy_target、deploy_command、service_list、health_check_url、acceptance_url、doc_output_path、syntax_check_cmd、new_router_name、main_entry_file）

### 执行（并行）

**planner subagent（必须）**：
- 读取代码库的关键模块（main.py、相关路由、相关 model）
- 识别影响范围（修改文件 + 新建文件）
- 识别数据库变更需求（描述变更内容，无需写 SQL — SQL 在 Phase 0.5 产出）
- 识别 API 接口（路径/方法，无需完整 schema — schema 在 Phase 0.5 产出）
- 识别实施顺序和依赖关系
- 识别风险

**researcher subagent（按需）**：
- 调研实现该功能的最佳实践
- 调研框架特定的实现方式
- 调研安全注意事项

### 输出
- 技术方案（写入 autoloop-findings.md 的"分析结果"部分）
- 影响文件列表（绝对路径）
- API 接口列表（路径/方法，无需完整 schema）
- 数据库变更描述（变更内容说明，无需 SQL）
- 风险清单

### 质量门禁
- [ ] 所有需要修改的文件已识别（通过读取代码确认，不是猜测）
- [ ] 数据库变更已描述（描述变更内容和原因，无需具体 SQL — SQL 在 Phase 0.5 方案文档中产出）
- [ ] 新增/修改路由已列出（路径和方法，无需完整 schema — schema 在 Phase 0.5 方案文档中产出）
- [ ] 风险已识别
- [ ] 实施顺序已解决依赖关系冲突
- [ ] 验收标准已明确（可测量的功能验收条件）

### 阻塞条件
无（自动进入 Phase 0.5）

---

## Phase 0.5: 文档化（阻塞点）

### 输入
- Phase 0 的分析结果

### 执行
生成方案文档，写入：
`{doc_output_path}/{功能名}-{YYYY-MM-DD}.md`

其中 `{doc_output_path}` 的值来自 `autoloop-plan.md` 的 `doc_output_path` 字段（唯一来源，见 `protocols/loop-protocol.md` 统一参数词汇表）。不得在此处硬编码任何路径。

文档格式参见 `templates/delivery-template.md`

### 输出
方案文档文件（完整，可独立阅读）

### 质量门禁
- [ ] 文档包含：问题描述、影响范围、具体方案、实施步骤、验收标准
- [ ] 数据库变更有具体 SQL（CREATE TABLE / ALTER TABLE 语句，有则必须，无变更则标注"无"）
- [ ] API 接口有明确定义（路径、方法、请求/响应 schema，有则必须，无新路由则标注"无"）
- [ ] 有回滚方案

### 阻塞条件
**必须人工确认才能进入 Phase 1。**

输出阻塞提示：
```
方案文档已生成：{路径}

请审阅后回复 "confirmed" 开始开发，或说明需要调整的内容。
```

---

## Phase 1: 开发

### 输入
- Phase 0.5 确认的方案文档
- 代码库路径

### 执行顺序（依赖性决定顺序）

**1a. 数据库迁移（最先，其他开发依赖）**：
- db-migrator subagent
- 创建迁移脚本（upgrade + downgrade 都实现）
- 验证脚本语法（`{syntax_check_cmd}`）

**1b. 后端开发（数据库迁移完成后）**：
- backend-dev subagent
- 按方案逐一实现后端功能
- 每个文件修改后立即运行 `{syntax_check_cmd}` 验证（按 `syntax_check_file_arg` 决定是否附加文件参数）
- 新路由在 `{main_entry_file}` 注册（按项目技术栈规范）
- 新文件在模块导出文件中声明（按项目技术栈规范）

**1c. 前端开发（可与 1b 并行，如果不依赖后端接口变化）**：
- frontend-dev subagent
- 类型标注正确，无 `any` 滥用
- API 调用通过代理层（不直接暴露后端地址）
- 每个文件修改后立即运行前端语法验证（`{syntax_check_cmd}`）

### 输出
- 所有修改/新建的文件（绝对路径列表）
- 每个文件的语法验证结果（`{syntax_check_cmd}`）
- `{main_entry_file}` 路由注册状态

### 质量门禁
- [ ] 所有修改文件语法验证通过（`{syntax_check_cmd}`，零错误）
- [ ] 新路由已在主入口文件注册（`grep -n "{new_router_name}" {main_entry_file}`）
- [ ] 新文件已在模块导出文件声明
- [ ] 迁移脚本有 downgrade 实现
- [ ] 无静默失败（空 catch/except）/ 无类型逃逸（`any` / `# type: ignore`）滥用

### 阻塞条件
任何文件语法验证失败 → 修复后重验证，不进入 Phase 2

---

## Phase 2: 审查

### 输入
- Phase 1 产出的所有文件列表

### 执行
code-reviewer subagent 对所有修改文件进行全量审查：

**审查维度**：
1. 安全性（SQL注入/命令注入/XSS/路径穿越/敏感数据）
2. 可靠性（try/except 覆盖/静默失败/降级回退）
3. 接口一致性（async def/返回类型/命名规范）
4. 完整性（路由注册/模块导出/迁移完整性）

**审查输出格式**：

```markdown
## Phase 2 审查报告

### 审查文件列表
- {文件 1}（新建/修改）
- {文件 2}

### 问题清单
| ID | 文件 | 行号 | 类型 | P级别 | 描述 | 修复建议 |

### 审查结论
P1: {N}，P2: {N}，P3: {N}
结论：{通过 / 需修复（必须修复 P1 和 P2）}
```

### 质量门禁
- [ ] P1 问题 = 0（安全漏洞/数据丢失风险）
- [ ] P2 问题 = 0（功能缺陷/错误处理缺失）
- [ ] P3 问题已记录（不阻塞，但记入最终报告）

### 阻塞条件
有 P1 或 P2 问题 → 返回 Phase 1 针对性修复（最多 3 轮修复-审查循环；T5 因含人工确认环节，允许此例外，见 loop-protocol.md 统一重试上限规则）

---

## Phase 3: 测试验证

### 输入
- Phase 1 产出的所有文件列表
- `{main_entry_file}` 路径（来自 autoloop-plan.md）

### 执行（verifier subagent）

**必须执行的验证**：

```bash
# 1. 语法检查（所有修改文件）
{syntax_check_cmd} {每个文件}        # syntax_check_file_arg=true 时附加文件参数
# 或：{syntax_check_cmd}             # syntax_check_file_arg=false 时在项目根目录运行

# 2. 路由注册验证（{new_router_name} = 本次新增的路由/模块名，在 plan 中收集）
grep -n "{new_router_name}" {main_entry_file}

# 3. 迁移状态检查（如有数据库迁移）
{migration_check_cmd}
# 示例：python -m alembic check（Python）；npx drizzle-kit check（Node.js）
```

**按条件执行**：

```bash
# 如果后端服务正在运行，执行 API 冒烟测试
curl -X GET {API端点} \
  -H "{auth_header}: {测试Key}" \
  -H "Content-Type: application/json"

# 期望：HTTP 200，响应格式与设计一致
```

### 输出
每步验证结果（命令 + 输出 + 状态）

### 质量门禁
- [ ] 语法验证：全部文件通过，零错误（`{syntax_check_cmd}`）
- [ ] 路由注册：grep 找到 `{new_router_name}` 注册语句（无新路由则 N/A）
- [ ] 迁移状态检查：无冲突（无迁移则 N/A）
- [ ] API 冒烟测试（如可执行）：HTTP 2xx

### 阻塞条件
任何验证失败 → 修复后重验证，不进入 Phase 4

---

## Phase 4: 部署

### 输入
- Phase 3 通过的验证结果

### 执行（人工或自动）

> 以下变量在 plan 收集阶段定义（T5需额外收集：deploy_target, deploy_command, service_list, health_check_url）

```bash
# 1. 提交代码
git add {所有修改文件（明确列出，不用 git add -A）}
git status  # 确认只有预期的文件
git commit -m "$(cat <<'EOF'
feat({模块}): {功能描述}

Co-Authored-By: AutoLoop <noreply@autoloop>
EOF
)"

# 2. 推送
git push origin main

# 3. 线上部署
{deploy_command}
# deploy_command 示例（在 plan 中收集）：
#   SIP 项目：gcloud compute ssh {deploy_target} --zone=... --command="cd /opt/sip && git pull && sudo bash deploy.sh"
#   其他项目：ssh {deploy_target} "cd {project_path} && git pull && bash deploy.sh"

# 4. 服务健康检查
# 检查 service_list 中每个服务全部 active（服务名称在 plan 中的 service_list 定义）
```

### 输出
- git commit hash
- 部署命令执行结果
- 服务状态（{service_list} 中全部 active）
- Health check 响应（{health_check_url}）

### 质量门禁
- [ ] git push 成功
- [ ] {deploy_command} 执行无报错
- [ ] {service_list} 中所有服务全部 active（systemctl status）
- [ ] Health check 返回 HTTP 200（{health_check_url}）

### 阻塞条件
服务未全部 active → 检查日志，修复后重部署

---

## Phase 5: 线上验收（阻塞点）

### 输入
- 验收标准（来自 autoloop-plan.md）
- 线上环境 URL

### 执行

**自动验证（verifier subagent）**：

调用方式：`Agent(subagent_type="code-reviewer", prompt="你是线上验收测试员。使用浏览器工具验证以下功能...")`
可选工具：Chrome DevTools MCP（如果已配置）

- 访问相关页面，验证新功能是否可见
- 执行功能操作，验证结果正确
- 检查浏览器 Console 无错误
- 检查相关 API 响应时间（< 500ms 为正常）

**人工确认（阻塞）**：

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Phase 5 阻塞：需要人工验收
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

自动验证结果：{通过/有问题}

请在浏览器（桌面 + 手机）访问 {URL}：

验收清单：
□ {验收标准 1}
□ {验收标准 2}
□ {验收标准 3}

Console 无红色错误
现有功能无回归

全部确认后输入 "verified" 完成任务。
如有问题，描述问题内容。
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### 质量门禁
- [ ] 自动验证通过（或已解释例外）
- [ ] 人工在浏览器（桌面）确认新功能正常
- [ ] 人工在浏览器（手机）确认布局正常
- [ ] Console 零红色错误
- [ ] 现有功能无回归（核心路径手动测试）

### 阻塞条件
人工未确认 → 任务不算完成

---

## 阶段间的回退规则

| 发现问题的阶段 | 回退到 | 回退范围 |
|-------------|--------|---------|
| Phase 2 发现 P1/P2 | Phase 1 | 仅修复对应文件 |
| Phase 3 验证失败 | Phase 1 或 Phase 2 | 修复 + 重审 |
| Phase 4 部署失败 | Phase 3（修复后重测试）| 修复 + 重测 + 重部署 |
| Phase 5 线上有问题 | Phase 4（回滚）or Phase 1（修复）| 用户决定回滚还是热修复 |

**最大回退次数**：每个阶段最多回退 2 次（遵守 loop-protocol.md 统一重试上限规则）；Phase 2 修复-审查循环例外，最多 3 轮。超过上限则向用户报告并等待人工决策。
