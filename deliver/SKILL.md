---
name: autoloop-deliver
description: >
  AutoLoop T5: 全流程交付。分析→文档化→开发→审查→测试→部署→验收。
  Use when: "deliver feature", "全流程交付", "端到端", "从需求到上线".
---

# AutoLoop Deliver (T5)

Read and follow the detailed execution protocol in `../commands/autoloop-deliver.md`.

For shared protocols (quality gates, loop protocol, parameters, etc.), reference `../protocols/`.

For the full AutoLoop overview and core mechanisms, see `../SKILL.md`.

## 前置检查

执行本模板前，必须确认：
1. `autoloop-plan.md` 存在于工作目录（如不存在，先执行 `/autoloop:plan` 创建）
2. plan 中的模板类型与本命令匹配
3. 如跳过 plan 直接调用，在 progress.md 中记录"直接调用，未经路由确认"
