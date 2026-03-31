#!/usr/bin/env python3
"""AutoLoop MCP Server — 将 10 个工具脚本封装为 MCP tools

安装：pip install mcp
启动：python3 server.py（由 Claude Code MCP 配置自动启动）
"""

import json
import os
import subprocess
import sys

from mcp.server.fastmcp import FastMCP

SCRIPTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts")

mcp = FastMCP("autoloop", instructions="AutoLoop 自主迭代引擎的确定性工具集。提供质量门禁计算、TSV 校验、跨文件校验等功能。")


def _default_mcp_timeout() -> int:
    raw = os.environ.get("AUTOLOOP_MCP_SCRIPT_TIMEOUT", "30").strip()
    try:
        n = int(raw, 10)
        return max(1, min(n, 3600))
    except ValueError:
        return 30


def _script_timeout_seconds(script_name: str) -> int:
    """validate 与 controller 子进程对齐，默认放宽到 300s（大仓库/CI）。"""
    if script_name == "autoloop-validate.py":
        raw = os.environ.get("AUTOLOOP_MCP_VALIDATE_TIMEOUT", "300").strip()
        try:
            n = int(raw, 10)
            return max(1, min(n, 3600))
        except ValueError:
            return 300
    return _default_mcp_timeout()


def _run_script(script_name: str, args: list[str]) -> str:
    """执行 scripts/ 目录下的 Python 脚本，返回 stdout"""
    script_path = os.path.join(SCRIPTS_DIR, script_name)
    timeout_sec = _script_timeout_seconds(script_name)
    if not os.path.exists(script_path):
        return json.dumps({
            "success": False,
            "error": f"脚本不存在: {script_path}",
        })
    try:
        result = subprocess.run(
            [sys.executable, script_path] + args,
            capture_output=True, text=True, timeout=timeout_sec
        )
        output = result.stdout.strip()
        if result.returncode != 0:
            error = result.stderr.strip() or output
            return json.dumps({"success": False, "output": output, "error": error})
        return json.dumps({"success": True, "output": output})
    except subprocess.TimeoutExpired:
        hint = (
            "AUTOLOOP_MCP_VALIDATE_TIMEOUT"
            if script_name == "autoloop-validate.py"
            else "AUTOLOOP_MCP_SCRIPT_TIMEOUT"
        )
        return json.dumps({
            "success": False,
            "error": f"脚本执行超时（{timeout_sec}s，可用 {hint} 调整）",
        })
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


@mcp.tool()
def autoloop_init(work_dir: str, template: str, goal: str) -> str:
    """初始化 AutoLoop 任务，在工作目录创建 4 个运行时文件（plan/progress/findings/results.tsv）

    Args:
        work_dir: 工作目录路径
        template: 模板类型（T1-T8）
        goal: 一句话任务目标
    """
    return _run_script("autoloop-init.py", [work_dir, template, goal])


@mcp.tool()
def autoloop_score(findings_path: str, json_output: bool = True) -> str:
    """运行 autoloop-score：对工作目录或 autoloop-state.json 路径评分。

    门禁维度与阈值由 `references/gate-manifest.json`（SSOT）及当前 `plan.template`
    决定，覆盖 T1–T7（非仅 T1 四维 findings 口径）。

    Args:
        findings_path: 工作目录路径，或 `autoloop-state.json` / `autoloop-findings.md` 文件路径
        json_output: 为 True 时附加 `--json`，输出结构化门禁结果
    """
    args = [findings_path]
    if json_output:
        args.append("--json")
    return _run_script("autoloop-score.py", args)


@mcp.tool()
def autoloop_tsv(command: str, file_path: str, row_json: str = "") -> str:
    """TSV 文件操作：校验格式、创建文件、读取摘要、追加行

    Args:
        command: 操作命令 - validate（校验）| create（创建）| summary（摘要）| append（追加）
        file_path: autoloop-results.tsv 文件路径
        row_json: 追加行时的 JSON 数据（仅 append 命令使用）
    """
    args = [command, file_path]
    if command == "append" and row_json:
        args.append(row_json)
    return _run_script("autoloop-tsv.py", args)


@mcp.tool()
def autoloop_validate(work_dir: str) -> str:
    """跨文件主键校验：检查 4 个运行时文件的主键一致性

    Args:
        work_dir: 包含 autoloop 运行时文件的工作目录
    """
    return _run_script("autoloop-validate.py", [work_dir])


@mcp.tool()
def autoloop_variance(command: str, scores: str = "", evidence: int = 0, tsv_path: str = "") -> str:
    """评分方差和置信度计算

    Args:
        command: 操作命令 - compute（计算方差+置信度）| check（检查 TSV 合规性）
        scores: compute 时的评分列表，空格分隔（如 "7.5 8.0 7.8"）
        evidence: compute 时的证据数量
        tsv_path: check 时的 TSV 文件路径
    """
    if command == "compute":
        args = ["compute"] + scores.split()
        if evidence > 0:
            args.extend(["--evidence", str(evidence)])
        return _run_script("autoloop-variance.py", args)
    elif command == "check":
        return _run_script("autoloop-variance.py", ["check", tsv_path])
    else:
        return json.dumps({"error": f"未知命令: {command}，可选: compute / check"})


@mcp.tool()
def autoloop_state(work_dir: str, command: str, args: str = "") -> str:
    """SSOT 状态管理 — init/update/query/add-iteration/add-finding/add-tsv-row

    Args:
        work_dir: 工作目录路径
        command: 操作命令 - init|update|query|add-iteration|add-finding|add-tsv-row
        args: 命令参数（JSON 字符串或其他格式，取决于 command）
    """
    cmd_args = [command, work_dir]
    if args:
        import shlex
        cmd_args.extend(shlex.split(args))
    return _run_script("autoloop-state.py", cmd_args)


@mcp.tool()
def autoloop_render(work_dir: str, file_type: str = "") -> str:
    """从 autoloop-state.json 渲染可读文件 — plan/progress/findings/tsv 或全部

    Args:
        work_dir: 工作目录路径
        file_type: 渲染目标文件类型（plan|progress|findings|tsv），留空则渲染全部
    """
    cmd_args = [work_dir]
    if file_type:
        cmd_args.extend(["--file", file_type])
    return _run_script("autoloop-render.py", cmd_args)


@mcp.tool()
def autoloop_experience(work_dir: str, command: str, args: str = "") -> str:
    """经验库读写 — query（查询推荐策略）/ write（追加策略记录）/ list（列出所有策略）

    Args:
        work_dir: 工作目录路径
        command: 操作命令 - query|write|list
        args: 命令参数（空格分隔），例如 query: '--template T1 --tags web,api'（默认不含「观察」策略；需含观察加时加 '--include-observation'）；write: '--strategy-id S01-xxx --effect 保持 --score 0.5'（--score 为 **delta** 变化量，非绝对分；可选 '--mechanism "…"'）；list: '--json'（可选）
    """
    cmd_args = [work_dir, command]
    if args:
        import shlex
        cmd_args.extend(shlex.split(args))
    return _run_script("autoloop-experience.py", cmd_args)


@mcp.tool()
def autoloop_finalize(work_dir: str, json_output: bool = False) -> str:
    """生成最终报告 — 从 autoloop-state.json 整合迭代轨迹、策略有效性、关键发现

    Args:
        work_dir: 工作目录路径
        json_output: 是否输出 JSON 格式（默认 False，输出 Markdown 并写入 autoloop-report.md）
    """
    cmd_args = [work_dir]
    if json_output:
        cmd_args.append("--json")
    return _run_script("autoloop-finalize.py", cmd_args)


@mcp.tool()
def autoloop_controller(
    work_dir: str,
    mode: str = "run",
    template: str = "",
    goal: str = "",
) -> str:
    """主循环控制器 — init/run/resume/status

    Args:
        work_dir: 工作目录路径
        mode: 运行模式 - run（默认，启动/继续循环）| init（须传 template）| resume（从暂停恢复）| status（查看状态）
        template: mode=init 时必填，如 T1、T2
        goal: mode=init 时可选的一行任务目标
    """
    if mode == "init":
        if not template.strip():
            return json.dumps({
                "success": False,
                "error": "mode=init 时必须提供 template（例如 T1、T5）",
            })
        cmd = [work_dir, "--init", "--template", template.strip()]
        if goal.strip():
            cmd.extend(["--goal", goal.strip()])
        return _run_script("autoloop-controller.py", cmd)
    elif mode == "resume":
        return _run_script("autoloop-controller.py", [work_dir, "--resume"])
    elif mode == "status":
        return _run_script("autoloop-controller.py", [work_dir, "--status"])
    else:
        return _run_script("autoloop-controller.py", [work_dir])


if __name__ == "__main__":
    mcp.run(transport="stdio")
