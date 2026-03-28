---
name: autoloop-generate
description: >
  AutoLoop T4: 批量内容生成。模板标准化 + 并行生成 + 逐项质量检查。
  Use when: "generate batch", "批量生成", "大批量", "成批".
---

# AutoLoop Generate (T4)

Read and follow the detailed execution protocol in `../commands/autoloop-generate.md`.

For shared protocols (quality gates, loop protocol, parameters, etc.), reference `../protocols/`.

For the full AutoLoop overview and core mechanisms, see `../SKILL.md`.

## 前置检查

执行本模板前，必须确认：
1. `autoloop-plan.md` 存在于工作目录（如不存在，先执行 `/autoloop:plan` 创建）
2. plan 中的模板类型与本命令匹配
3. 如跳过 plan 直接调用，在 progress.md 中记录"直接调用，未经路由确认"
