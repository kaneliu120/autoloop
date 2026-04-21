# MCP Tools and CLI Parameter Mapping

`mcp-server/server.py` invokes `scripts/*.py` through subprocesses. The table below lists the common mappings (argument order follows the script).

| MCP tool | Underlying script | Notes |
|----------|-------------------|-------|
| `autoloop_init` | `autoloop-init.py <work_dir> <template> <goal>` | |
| `autoloop_score` | `autoloop-score.py <path> [--json]` | Accepts a findings **file** path or a workdir |
| `autoloop_validate` | `autoloop-validate.py <work_dir>` | MCP does not expose `--strict`; the CLI does |
| `autoloop_state` | `autoloop-state.py <command> <work_dir> …` | `args` are split with shlex |
| `autoloop_controller` | `autoloop-controller.py …` | `mode=init` **must** include `template`; if omitted, returns JSON `success: false` |
| `autoloop_render` | `autoloop-render.py <work_dir> [--file …]` | |
| `autoloop_experience` | `autoloop-experience.py <work_dir> <command> …` | |

**Subprocess timeout**: default `AUTOLOOP_MCP_SCRIPT_TIMEOUT` (seconds, default 30). `autoloop-validate.py` uses `AUTOLOOP_MCP_VALIDATE_TIMEOUT` separately (default **300**, aligned with the large repo / controller).

**Contract tests**: `tests/test_mcp_contract.py` runs when `mcp` is importable (CI already runs `pip install mcp`). Locally:

```bash
pip install -e ".[dev]"   # includes mcp and matches pyproject optional-dependencies
python3 -m unittest tests.test_mcp_contract -v
```

`TestMcpControllerInitContract` in `tests/test_autoloop_regression.py` also asserts static source contracts (independent of the `mcp` package).
