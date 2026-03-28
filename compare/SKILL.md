---
name: autoloop-compare
description: >
  AutoLoop T2: 多方案对比。多维度评分 + 证据支撑 + 敏感性分析 + 明确推荐。
  Use when: "compare options", "对比分析", "方案评估", "选型".
---

# AutoLoop Compare (T2)

Read and follow the detailed execution protocol in `../commands/autoloop-compare.md`.

For shared protocols (quality gates, loop protocol, parameters, etc.), reference `../protocols/`.

For the full AutoLoop overview and core mechanisms, see `../SKILL.md`.

## 前置检查

执行本模板前，必须确认：
1. `autoloop-plan.md` 存在于工作目录（如不存在，先执行 `/autoloop:plan` 创建）
2. plan 中的模板类型与本命令匹配
3. 如跳过 plan 直接调用，在 progress.md 中记录"直接调用，未经路由确认"
