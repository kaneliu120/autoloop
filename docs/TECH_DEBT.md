# 技术债与 Backlog（仓库 SSOT）

与 Obsidian 笔记 `AutoLoop-待办事项02-技术债与Backlog-2026-03-29.md` 对照使用：**本文件跟踪已在仓库落地或仍开放的实现项**；Epic 级 v2 仍以 `docs/backlog-experience-v2.md` 为准。

| 主题 | 状态 | 说明 |
|------|------|------|
| 经验库 v2 Epic | 开放 | `docs/backlog-experience-v2.md` |
| context-scoped 写 / 归档 | 开放 | `references/experience-registry.md` |
| `stagnation_max_explore`（T3/T6/T7） | **已接入** | `references/gate-manifest.json` + `phase_evolve`；计数 `metadata.stagnation_explore_switches`，停滞解除时清零 |
| Markdown-only 无 SSOT | 开放（legacy） | 推荐 `autoloop-state.py init`；见 `SKILL.md` |
| DECIDE 硬约束偏 LLM（B11） | 开放 | 诊断见 `docs/AutoLoop-自动化断点分析与控制器方案-2026-03-28.md` |
| D-03 mechanism 强制 | **可选** | `AUTOLOOP_EXPERIENCE_REQUIRE_MECHANISM=1` 时 `use_count≥2` 须 `--mechanism` |
| D-04 子进程超时 | 已满足 | `AUTOLOOP_SUBPROCESS_TIMEOUT` / `AUTOLOOP_TIMEOUT_VALIDATE` |
| `build/` 误提交 | 已缓解 | `.gitignore` 含 `build/`、`dist/` |
| R8 修复方案文 | 归档 | 文首已有「以仓库为准」说明；勿当唯一 backlog |
| Runner ↔ strict | 已注记 | 见 `docs/RUNNER.md`「与 controller / validate strict 对齐」 |
