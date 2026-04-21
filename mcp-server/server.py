#!/usr/bin/env python3
"""AutoLoop MCP Server - wraps 10 tool scripts as MCP tools

Install: `pip install mcp`
Start: `python3 server.py` (usually launched by the Claude Code MCP config)
"""

import json
import os
import subprocess
import sys

from mcp.server.fastmcp import FastMCP

SCRIPTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts")

mcp = FastMCP("autoloop", instructions="Deterministic tools for the AutoLoop autonomous iteration engine. Supports quality-gate scoring, TSV validation, and cross-file consistency checks.")


def _default_mcp_timeout() -> int:
    raw = os.environ.get("AUTOLOOP_MCP_SCRIPT_TIMEOUT", "30").strip()
    try:
        n = int(raw, 10)
        return max(1, min(n, 3600))
    except ValueError:
        return 30


def _script_timeout_seconds(script_name: str) -> int:
    """Match validate/controller subprocess timing; default to 300s for large repos or CI."""
    if script_name == "autoloop-validate.py":
        raw = os.environ.get("AUTOLOOP_MCP_VALIDATE_TIMEOUT", "300").strip()
        try:
            n = int(raw, 10)
            return max(1, min(n, 3600))
        except ValueError:
            return 300
    return _default_mcp_timeout()


def _run_script(script_name: str, args: list[str]) -> str:
    """Run a Python script from `scripts/` and return stdout."""
    script_path = os.path.join(SCRIPTS_DIR, script_name)
    timeout_sec = _script_timeout_seconds(script_name)
    if not os.path.exists(script_path):
        return json.dumps({
            "success": False,
            "error": f"Script not found: {script_path}",
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
            "error": f"Script timed out ({timeout_sec}s; adjust with {hint})",
        })
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


@mcp.tool()
def autoloop_init(work_dir: str, template: str, goal: str) -> str:
    """Initialize an AutoLoop task and create 4 runtime files in the workdir.

    Args:
        work_dir: Working directory path
        template: Template type (`T1`-`T8`)
        goal: One-line task goal
    """
    return _run_script("autoloop-init.py", [work_dir, template, goal])


@mcp.tool()
def autoloop_score(findings_path: str, json_output: bool = True) -> str:
    """Run `autoloop-score` against a workdir or `autoloop-state.json` path.

    Gate dimensions and thresholds come from `references/gate-manifest.json`
    (SSOT) plus the current `plan.template`, covering T1-T7 rather than only
    the legacy four T1 findings dimensions.

    Args:
        findings_path: Workdir path, or an `autoloop-state.json` /
            `autoloop-findings.md` file path
        json_output: Append `--json` when True to return structured gate data
    """
    args = [findings_path]
    if json_output:
        args.append("--json")
    return _run_script("autoloop-score.py", args)


@mcp.tool()
def autoloop_tsv(command: str, file_path: str, row_json: str = "") -> str:
    """Operate on TSV files: validate, create, summarize, or append rows.

    Args:
        command: `validate` | `create` | `summary` | `append`
        file_path: Path to `autoloop-results.tsv`
        row_json: JSON row payload for `append`
    """
    args = [command, file_path]
    if command == "append" and row_json:
        args.append(row_json)
    return _run_script("autoloop-tsv.py", args)


@mcp.tool()
def autoloop_validate(work_dir: str) -> str:
    """Run cross-file primary-key validation across the 4 runtime files.

    Args:
        work_dir: Workdir containing AutoLoop runtime files
    """
    return _run_script("autoloop-validate.py", [work_dir])


@mcp.tool()
def autoloop_variance(command: str, scores: str = "", evidence: int = 0, tsv_path: str = "") -> str:
    """Score variance and confidence utilities.

    Args:
        command: `compute` or `check`
        scores: Score list for `compute`, space-delimited
        evidence: Evidence count for `compute`
        tsv_path: TSV file path for `check`
    """
    if command == "compute":
        args = ["compute"] + scores.split()
        if evidence > 0:
            args.extend(["--evidence", str(evidence)])
        return _run_script("autoloop-variance.py", args)
    elif command == "check":
        return _run_script("autoloop-variance.py", ["check", tsv_path])
    else:
        return json.dumps({"error": f"Unknown command: {command}; expected compute / check"})


@mcp.tool()
def autoloop_state(work_dir: str, command: str, args: str = "") -> str:
    """SSOT state management: init/update/query/add-iteration/add-finding/add-tsv-row.

    Args:
        work_dir: Working directory path
        command: `init|update|query|add-iteration|add-finding|add-tsv-row`
        args: Command arguments, format depends on `command`
    """
    cmd_args = [command, work_dir]
    if args:
        import shlex
        cmd_args.extend(shlex.split(args))
    return _run_script("autoloop-state.py", cmd_args)


@mcp.tool()
def autoloop_render(work_dir: str, file_type: str = "") -> str:
    """Render readable files from `autoloop-state.json`.

    Args:
        work_dir: Working directory path
        file_type: `plan|progress|findings|tsv`; blank renders all
    """
    cmd_args = [work_dir]
    if file_type:
        cmd_args.extend(["--file", file_type])
    return _run_script("autoloop-render.py", cmd_args)


@mcp.tool()
def autoloop_experience(work_dir: str, command: str, args: str = "") -> str:
    """Experience registry access: query / write / list.

    Args:
        work_dir: Working directory path
        command: `query|write|list`
        args: Space-delimited args. For example, query:
            `--template T1 --tags web,api`; write:
            `--strategy-id S01-xxx --effect Keep --score 0.5`;
            list: `--json`
    """
    cmd_args = [work_dir, command]
    if args:
        import shlex
        cmd_args.extend(shlex.split(args))
    return _run_script("autoloop-experience.py", cmd_args)


@mcp.tool()
def autoloop_finalize(work_dir: str, json_output: bool = False) -> str:
    """Generate a final report from `autoloop-state.json`.

    Args:
        work_dir: Working directory path
        json_output: Return JSON when True; otherwise write Markdown
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
    """Main loop controller: init/run/resume/status.

    Args:
        work_dir: Working directory path
        mode: `run` (default) | `init` | `resume` | `status`
        template: Required when `mode=init`, for example `T1`, `T2`
        goal: Optional one-line goal for `mode=init`
    """
    if mode == "init":
        if not template.strip():
            return json.dumps({
                "success": False,
                "error": "template is required when mode=init (for example T1 or T5)",
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
