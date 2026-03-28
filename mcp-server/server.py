#!/usr/bin/env python3
"""AutoLoop MCP Server — 将 5 个工具脚本封装为 MCP tools

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


def _run_script(script_name: str, args: list[str]) -> str:
    """执行 scripts/ 目录下的 Python 脚本，返回 stdout"""
    script_path = os.path.join(SCRIPTS_DIR, script_name)
    if not os.path.exists(script_path):
        return json.dumps({"error": f"脚本不存在: {script_path}"})
    try:
        result = subprocess.run(
            [sys.executable, script_path] + args,
            capture_output=True, text=True, timeout=30
        )
        output = result.stdout.strip()
        if result.returncode != 0:
            error = result.stderr.strip() or output
            return json.dumps({"success": False, "output": output, "error": error})
        return json.dumps({"success": True, "output": output})
    except subprocess.TimeoutExpired:
        return json.dumps({"error": "脚本执行超时（30s）"})
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def autoloop_init(work_dir: str, template: str, goal: str) -> str:
    """初始化 AutoLoop 任务，在工作目录创建 4 个运行时文件（plan/progress/findings/results.tsv）

    Args:
        work_dir: 工作目录路径
        template: 模板类型（T1-T7）
        goal: 一句话任务目标
    """
    return _run_script("autoloop-init.py", [work_dir, template, goal])


@mcp.tool()
def autoloop_score(findings_path: str, json_output: bool = True) -> str:
    """计算质量门禁得分（覆盖率、可信度、一致性、完整性）

    Args:
        findings_path: autoloop-findings.md 文件路径
        json_output: 是否输出 JSON 格式（默认 True）
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


if __name__ == "__main__":
    mcp.run(transport="stdio")
