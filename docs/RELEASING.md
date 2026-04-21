# AutoLoop Release and Version Alignment

## Skill / Repository / gate-manifest mapping

- **Repository version**: the `version` in the root `pyproject.toml` (often `0.0.0` as a development placeholder).
- **Protocol and gate SSOT**: `references/gate-manifest.json` may maintain a `version` field (if missing, use the git tag or CHANGELOG as the source of truth).
- **Skill**: `.claude/skills/autoloop/SKILL.md` (or the same file under your install path) should match the current repository at the **same commit** or the same **git tag** so threshold / phase descriptions do not drift from the manifest.

**Recommended convention**: tag reproducible releases as `vX.Y.Z` and note a "manifest-compatible change summary" in the corresponding CHANGELOG entry.

## Pre-release Checklist

1. `python3 -m unittest discover -s tests -v`
2. Update `CHANGELOG.md` (user-visible behavior, breaking changes, migration notes)
3. If gates or default rounds changed, sync `references/gate-manifest.json` and `references/parameters.md`
4. Create the tag: `git tag -a vX.Y.Z -m "..." && git push origin vX.Y.Z`

## Optional GitHub Release Notes Template

```markdown
## AutoLoop vX.Y.Z

### Highlights
- …

### Migration
- …

### Validation
- Python >=3.10; runtime scripts have no third-party dependencies (the MCP service additionally requires `pip install mcp`).
```
