# AutoLoop 安全说明

## 威胁模型（简要）

AutoLoop 脚本主要在 **用户本机** 上运行，由 Claude Code / MCP / CLI 调用。输入通常包括：

- 工作目录路径  
- `autoloop-state.json` 及渲染出的 Markdown/TSV 内容  
- 通过 `autoloop-state.py update` 等写入的字段路径与值  

## 用户可控路径与子进程

以下入口会将外部传入路径用于文件读写或 `subprocess`：

- `autoloop-controller.py`、`autoloop-state.py`、`autoloop-score.py`、`autoloop-validate.py` 等均以 **第一个参数为工作目录** 打开 `autoloop-state.json` 及邻接文件。  
- `autoloop-controller.py` 的 `run_tool` 调用同目录下固定脚本名，不执行任意 shell 字符串。  
- **严格模式**（`AUTOLOOP_STRICT` / `--strict`）可在 VERIFY 失败时阻断后续阶段，降低「带病继续」风险；ACT 仍由操作者自行约束命令，建议仅调用白名单脚本与项目内命令。

**建议**：仅在可信工作目录运行；自动化场景下对工作目录路径做规范化并拒绝包含 `..` 的逃逸（若未来暴露多租户接口，应在集成层强制）。

## 可选：ACT 命令白名单（配置）

在 SSOT 中可设置 `plan.template_params.allowed_script_globs`（字符串数组）或 `allowed_commands`（字符串片段列表），供 `autoloop-controller.py` **ACT 阶段提示**引用；控制器不据此自动执行 shell。未配置时行为与旧版一致，仍由操作者在 ACT 中自行约束命令来源。

## 凭据与密钥

- 勿将 API 密钥写入 `autoloop-state.json` 或提交到 Git。  
- `.gitignore` 已忽略常见运行时文件；敏感环境使用独立工作目录。

## 报告问题

若发现命令注入、路径穿越或子进程滥用，请通过你的团队渠道私下报告。
