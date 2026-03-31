# AutoLoop 发布与版本对齐

## Skill / 仓库 / gate-manifest 对应关系

- **仓库版本**：根目录 `pyproject.toml` 的 `version`（当前多为 `0.0.0` 开发占位）。
- **协议与门禁 SSOT**：`references/gate-manifest.json` 可维护字段 `version`（若缺失则以 git tag 或 CHANGELOG 为准）。
- **Skill**：`.claude/skills/autoloop/SKILL.md`（或你安装路径下的同名文件）应与当前仓库 **同一 commit** 或同一 **git tag**，避免阈值/阶段描述与 manifest 脱节。

**建议约定**：对外可复现发行版打 tag `vX.Y.Z`，并在 CHANGELOG 该条中写明「兼容 gate-manifest.json 变更摘要」。

## 发布前检查清单

1. `python3 -m unittest discover -s tests -v`
2. 更新 `CHANGELOG.md`（用户可见行为、破坏性变更、迁移说明）
3. 若改门禁或默认轮次：同步 `references/gate-manifest.json` 与 `references/parameters.md`
4. 打 tag：`git tag -a vX.Y.Z -m "..." && git push origin vX.Y.Z`

## GitHub Release 说明模板（可选）

```markdown
## AutoLoop vX.Y.Z

### 亮点
- …

### 迁移
- …

### 校验
- Python >=3.10；运行时脚本无第三方依赖（MCP 服务另需 `pip install mcp`）。
```
