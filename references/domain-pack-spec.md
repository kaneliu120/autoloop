# Domain Packs — Technology-Stack-Specific Detection Rules

## Overview

A domain pack is a technology-stack-specific extension of the generic penalty rules in `enterprise-standard.md`. Each pack targets one stack (for example Python/FastAPI or Next.js/TypeScript) and provides dedicated detection commands, weight adjustments, and additional checks.

## Loading Mechanism

### Loading Mechanism

1. **Automatic detection** (default): during OBSERVE, scan the working directory for stack features (`package.json` → nextjs-typescript, `requirements.txt` + fastapi → python-fastapi) and automatically load the matching domain pack
2. **Manual override**: set `domain_pack: {pack-name}` in autoloop-plan.md to override auto-detection
3. **Explicit disable**: set `domain_pack: none` to skip the domain pack (the reason must be stated in the plan)

> **Important**: if `domain_pack` is omitted, automatic detection runs by default; generic rules are no longer used as a fallback.
> If automatic detection does not match any pack, use the generic rules and record "no domain pack matched" in findings.md.

### Loading Priority

1. The detection commands in the pack **replace** the corresponding "technology-stack-specific detection" commands in enterprise-standard.md
2. The weight adjustments in the pack **override** the generic weights
3. The additional checks in the pack are **appended** to the generic penalty rules

## Backward Compatibility

- The generic rules are always the baseline; packs only make incremental adjustments
- If automatic detection does not match, fall back to the generic rules, but record it in findings.md

## Pack File Structure

Each pack file contains the following sections:

```markdown
# {technology stack name} Domain Pack

## Scope
- Stack: {language + framework}
- Applicable templates: T7 Quality / T8 Optimize

## Detection Coverage
### Security checks
### Reliability checks
### Maintainability checks
### Architecture checks (T8)
### Performance checks (T8)
### Stability checks (T8)

## Weight Adjustments
| Dimension | Generic weight | Pack weight | Reason for adjustment |

## Additional Checks
| Check | Penalty | Severity | Description |
```

## Naming Rules

`{language}-{framework}.md`, all lowercase and hyphen-separated.

| File name | Stack |
|--------|--------|
| `python-fastapi.md` | Python + FastAPI + SQLAlchemy |
| `nextjs-typescript.md` | Next.js + TypeScript + React |
| `go-gin.md` | Go + Gin (future) |
| `rust-axum.md` | Rust + Axum (future) |

## Custom Packs

Users can create their own pack files in this directory, as long as they follow the structure above.
