---
name: autoloop-optimize
description: >
  AutoLoop T7: 架构/性能/稳定性优化。三维度并行诊断+跨维度协同修复。
  Use when: "optimize", "架构优化", "性能优化", "稳定性", "系统诊断".
---

# AutoLoop Optimize (T7)

Read and follow the detailed execution protocol in `../commands/autoloop-optimize.md`.

For shared protocols (quality gates, loop protocol, parameters, etc.), reference `../protocols/`.

For the full AutoLoop overview and core mechanisms, see `../SKILL.md`.

## 前置检查

执行本模板前，必须确认：
1. `autoloop-plan.md` 存在于工作目录（如不存在，先执行 `/autoloop:plan` 创建）
2. plan 中的模板类型与本命令匹配
3. 如跳过 plan 直接调用，在 progress.md 中记录"直接调用，未经路由确认"
