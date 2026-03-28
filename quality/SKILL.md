---
name: autoloop-quality
description: >
  AutoLoop T6: 企业级质量迭代。安全性+可靠性+可维护性三维度并行扫描+迭代修复。
  Use when: "quality review", "企业级", "代码审查", "提升质量".
---

# AutoLoop Quality (T6)

Read and follow the detailed execution protocol in `../commands/autoloop-quality.md`.

For shared protocols (quality gates, loop protocol, parameters, etc.), reference `../protocols/`.

For the full AutoLoop overview and core mechanisms, see `../SKILL.md`.

## 前置检查

执行本模板前，必须确认：
1. `autoloop-plan.md` 存在于工作目录（如不存在，先执行 `/autoloop:plan` 创建）
2. plan 中的模板类型与本命令匹配
3. 如跳过 plan 直接调用，在 progress.md 中记录"直接调用，未经路由确认"
