# Technical Debt and Backlog (Repository SSOT)

Use this file alongside the Obsidian note `AutoLoop-TODO-02-Technical-Debt-and-Backlog-2026-03-29.md`: **this file tracks implementation items that are already in the repository or still open**; Epic-level v2 remains governed by `docs/backlog-experience-v2.md`.

| Topic | Status | Notes |
|------|--------|------|
| Experience registry v2 Epic | Open | `docs/backlog-experience-v2.md` |
| context-scoped write / archive | Open | `references/experience-registry.md` |
| `stagnation_max_explore` (T3/T6/T7) | **Integrated** | `references/gate-manifest.json` + `phase_evolve`; count `metadata.stagnation_explore_switches`, reset when stagnation clears |
| Markdown-only, no SSOT | Open (legacy) | `autoloop-state.py init` recommended; see `SKILL.md` |
| DECIDE hard constraints still lean LLM-heavy (B11) | Open | See `docs/AutoLoop-Automation-Breakpoint-Analysis-and-Controller-Plan-2026-03-28.md` for diagnosis |
| D-03 mechanism enforcement | **Optional** | When `AUTOLOOP_EXPERIENCE_REQUIRE_MECHANISM=1`, `use_count≥2` must include `--mechanism` |
| D-04 subprocess timeout | Satisfied | `AUTOLOOP_SUBPROCESS_TIMEOUT` / `AUTOLOOP_TIMEOUT_VALIDATE` |
| Accidental `build/` commits | Mitigated | `.gitignore` includes `build/` and `dist/` |
| R8 repair plan document | Archived | The file header already says "follow the repository"; do not treat it as the only backlog |
| Runner ↔ strict | Noted | See `docs/RUNNER.md` for alignment with controller / validate strict |
