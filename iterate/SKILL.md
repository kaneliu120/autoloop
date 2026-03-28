---
name: autoloop-iterate
description: >
  AutoLoop T3: 目标驱动迭代。定义KPI + 基线测量 + 每轮改进 + 收益递减检测。
  Use when: "iterate until", "迭代优化", "反复改进", "直到达标".
---

# AutoLoop Iterate (T3)

Read and follow the detailed execution protocol in `../commands/autoloop-iterate.md`.

For shared protocols (quality gates, loop protocol, parameters, etc.), reference `../protocols/`.

For the full AutoLoop overview and core mechanisms, see `../SKILL.md`.

## 前置检查

执行本模板前，必须确认：
1. `autoloop-plan.md` 存在于工作目录（如不存在，先执行 `/autoloop:plan` 创建）
2. plan 中的模板类型与本命令匹配
3. 如跳过 plan 直接调用，在 progress.md 中记录"直接调用，未经路由确认"
