# AutoLoop

Autonomous iteration engine (Claude Code skill): an eight-stage OODA loop with quality-gated convergence, supporting templates T1 (research) through T8 (architecture optimization) plus chained Pipeline execution.

## Repository Layout

| Path | Description |
|------|------|
| `SKILL.md` | Top-level skill contract and mandatory script invocations |
| `commands/` | Entry points and per-template command docs (Markdown) |
| `references/` | Protocols and SSOT references (including `gate-manifest.json`) |
| `scripts/` | Deterministic Python tools (stdlib-first) |
| `mcp-server/` | MCP wrapper |
| `assets/` | Templates for plan, findings, progress, and related artifacts |
| `tests/` | `unittest` regression coverage |
| `services/autoloop_runner/` | L1 unattended runner (OpenAI + `tick`/`loop`) |
| `docs/RUNNER.md` | Runner usage and `--stop-after` behavior |

## Skill Directory vs. Work Directory

- **Skill directory**: the cloned repository path containing `scripts/`, `references/experience-registry.md`, and related assets.  
- **Work directory**: the concrete task directory that stores runtime files such as `autoloop-state.json`, `autoloop-plan.md`, and `autoloop-results.tsv` (ignored by default via `.gitignore`).

The experience registry can be resolved by `autoloop-experience.py` from either the skill package `references/` directory or the work directory `references/` directory.

## Environment

- **Python**: 3.10+ (CI runs the same test suite on 3.10 and 3.11).
- **Dependencies**: tools under `scripts/` use the **Python standard library** only and have no third-party runtime dependencies. Using **`mcp-server/`** requires a separate `pip install mcp`.
- **Optional install**: run `pip install -e .` from the repo root to expose console entry points such as `autoloop-state` and `autoloop-validate` (see `autoloop_entrypoints.py`; they still call `scripts/*.py` internally). For unattended mode, install `pip install -e ".[runner]"` and see [docs/RUNNER.md](docs/RUNNER.md) for `autoloop-runner tick|loop|metrics`.
- **Strict mode**: `AUTOLOOP_STRICT=1` or `autoloop-controller.py <dir> --strict` halts the rest of the round if any hard VERIFY step fails. On the validation side, use `AUTOLOOP_VALIDATE_STRICT=1` or `autoloop-validate.py <dir> --strict`.

## Quick Start (SSOT)

```bash
cd /path/to/your/task-dir
python3 /path/to/autoloop/scripts/autoloop-state.py init . T1 "your goal"
python3 /path/to/autoloop/scripts/autoloop-controller.py . --status
```

- Preview legacy `plan.gates` alignment: `python3 scripts/autoloop-state.py migrate . --dry-run`

MCP: `autoloop_controller` must receive `template` when `mode=init` is used (`goal` is optional).

## Validation and Scoring

Run the following commands inside a **bootstrapped** directory (one that already contains `autoloop-state.json`; for full workflow requirements, including TSV files, see `autoloop-validate.py`):

```bash
python3 scripts/autoloop-validate.py <work_dir>
python3 scripts/autoloop-score.py <work_dir> --json
```

## Tests

```bash
python3 -m unittest discover -s tests -v
```

## Legacy State Migration

If `plan.gates` does not match the current scorer keys, see the **"autoloop-state.json migration"** section in [references/loop-data-schema.md](references/loop-data-schema.md).

## Docs and Changes

- Changelog: [CHANGELOG.md](CHANGELOG.md)  
- Security notes: [docs/SECURITY.md](docs/SECURITY.md)  
- Schema ↔ validation map: [docs/schema-validate-map.md](docs/schema-validate-map.md)  
- Release/version alignment: [docs/RELEASING.md](docs/RELEASING.md)  
- MCP and CLI parity: [docs/mcp-cli-parity.md](docs/mcp-cli-parity.md)  
- Minimal SSOT example: `examples/minimal-state.json`
