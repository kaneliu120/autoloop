# MCP 工具与 CLI 参数对照

`mcp-server/server.py` 通过子进程调用 `scripts/*.py`。下列为常用映射（参数顺序以脚本为准）。

| MCP tool | 底层脚本 | 备注 |
|----------|----------|------|
| `autoloop_init` | `autoloop-init.py <work_dir> <template> <goal>` | |
| `autoloop_score` | `autoloop-score.py <path> [--json]` | 传入 findings **文件**路径或工作目录 |
| `autoloop_validate` | `autoloop-validate.py <work_dir>` | MCP 未暴露 `--strict`；CLI 可用 |
| `autoloop_state` | `autoloop-state.py <command> <work_dir> …` | `args` 经 shlex 拆分 |
| `autoloop_controller` | `autoloop-controller.py …` | `mode=init` **必须**传 `template`；缺省时返回 JSON `success: false` |
| `autoloop_render` | `autoloop-render.py <work_dir> [--file …]` | |
| `autoloop_experience` | `autoloop-experience.py <work_dir> <command> …` | |

**子进程超时**：默认 `AUTOLOOP_MCP_SCRIPT_TIMEOUT`（秒，默认 30）。`autoloop-validate.py` 单独使用 `AUTOLOOP_MCP_VALIDATE_TIMEOUT`（默认 **300**，与大仓库/controller 对齐）。

**契约测试**：`tests/test_mcp_contract.py` 在可导入 `mcp` 时运行（CI 已 `pip install mcp`）。本地可执行：

```bash
pip install -e ".[dev]"   # 含 mcp，与 pyproject optional-dependencies 一致
python3 -m unittest tests.test_mcp_contract -v
```

`tests/test_autoloop_regression.py` 中 `TestMcpControllerInitContract` 另做静态源码断言（不依赖 `mcp` 包）。
