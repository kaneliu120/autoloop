---
name: autoloop-research
description: >
  AutoLoop T1: 全景调研。多维度并行搜索 + 交叉验证 + 覆盖率驱动迭代。
  Use when: "research X thoroughly", "全景调研", "深度调研", "彻底研究".
---

# AutoLoop Research (T1)

Read and follow the detailed execution protocol in `../commands/autoloop-research.md`.

For shared protocols (quality gates, loop protocol, parameters, etc.), reference `../protocols/`.

For the full AutoLoop overview and core mechanisms, see `../SKILL.md`.

## 前置检查

执行本模板前，必须确认：
1. `autoloop-plan.md` 存在于工作目录（如不存在，先执行 `/autoloop:plan` 创建）
2. plan 中的模板类型与本命令匹配
3. 如跳过 plan 直接调用，在 progress.md 中记录"直接调用，未经路由确认"
