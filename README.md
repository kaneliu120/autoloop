# AutoLoop

自主迭代引擎（Claude Code Skill）：OODA 八阶段循环 + 质量门禁收敛，支持模板 T1（调研）～ T8（架构优化）及 Pipeline 链式执行。

## 目录结构

| 路径 | 说明 |
|------|------|
| `SKILL.md` | 技能总协议与强制脚本调用 |
| `commands/` | 入口与各模板命令（Markdown） |
| `references/` | 协议与 SSOT（含 `gate-manifest.json`） |
| `scripts/` | 确定性 Python 工具（标准库为主） |
| `mcp-server/` | MCP 封装 |
| `assets/` | 计划 / findings / 进度等模板 |
| `tests/` | `unittest` 回归 |
| `services/autoloop_runner/` | L1 无人值守 Runner（OpenAI + `tick`/`loop`） |
| `docs/RUNNER.md` | Runner 用法与 `--stop-after` 约定 |

## 技能目录 vs 工作目录

- **技能目录**：本仓库克隆路径（含 `scripts/`、`references/experience-registry.md` 等）。  
- **工作目录**：具体任务所在目录，存放 `autoloop-state.json`、`autoloop-plan.md`、`autoloop-results.tsv` 等运行时文件（默认被 `.gitignore` 忽略）。

经验库可被 `autoloop-experience.py` 在 **技能包 `references/`** 或 **工作目录 `references/`** 下解析。

## 环境

- **Python**：3.10+（CI 在 3.10 与 3.11 上跑同一测试套件）。
- **依赖**：`scripts/` 下工具为 **Python 标准库**，无第三方运行时依赖。使用 **`mcp-server/`** 时需单独 `pip install mcp`。
- **可选安装**：在仓库根目录执行 `pip install -e .` 后，可使用 `autoloop-state`、`autoloop-validate` 等 console 入口（见 `autoloop_entrypoints.py`，内部仍调用 `scripts/*.py`）。无人值守：`pip install -e ".[runner]"` 后见 [docs/RUNNER.md](docs/RUNNER.md)（`autoloop-runner tick|loop|metrics`）。
- **严格模式**：`AUTOLOOP_STRICT=1` 或 `autoloop-controller.py <dir> --strict` — VERIFY 任一硬步骤失败则中止本轮后续阶段。校验侧：`AUTOLOOP_VALIDATE_STRICT=1` 或 `autoloop-validate.py <dir> --strict`。

## 快速开始（SSOT）

```bash
cd /path/to/your/task-dir
python3 /path/to/autoloop/scripts/autoloop-state.py init . T1 "你的目标"
python3 /path/to/autoloop/scripts/autoloop-controller.py . --status
```

- 旧 `plan.gates` 预览对齐：`python3 scripts/autoloop-state.py migrate . --dry-run`

MCP：`autoloop_controller` 在 `mode=init` 时必须提供 `template`（可选 `goal`）。

## 校验与评分

以下命令需在 **已 bootstrap** 的目录执行（存在 `autoloop-state.json`；完整流程还需 TSV 等见 `autoloop-validate.py` 说明）：

```bash
python3 scripts/autoloop-validate.py <工作目录>
python3 scripts/autoloop-score.py <工作目录> --json
```

## 测试

```bash
python3 -m unittest discover -s tests -v
```

## 旧 state 迁移

若 `plan.gates` 与当前 scorer 键不一致，见 [references/loop-data-schema.md](references/loop-data-schema.md) 中的 **「autoloop-state.json 迁移」** 小节。

## 文档与变更

- 变更记录：[CHANGELOG.md](CHANGELOG.md)  
- 安全提示：[docs/SECURITY.md](docs/SECURITY.md)  
- Schema ↔ 校验对照：[docs/schema-validate-map.md](docs/schema-validate-map.md)  
- 发布与版本对齐：[docs/RELEASING.md](docs/RELEASING.md)  
- MCP 与 CLI 参数：[docs/mcp-cli-parity.md](docs/mcp-cli-parity.md)  
- 最小 SSOT 样例：`examples/minimal-state.json`
