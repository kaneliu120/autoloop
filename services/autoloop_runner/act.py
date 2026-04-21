"""ACT: execute planned commands through an allowlist (shell=False)."""

from __future__ import annotations

import fnmatch
import json
import os
import shlex
import subprocess
from dataclasses import dataclass
from typing import Any, Sequence


@dataclass
class CommandResult:
    cmd: str
    returncode: int
    stdout: str
    stderr: str
    allowed: bool
    error: str | None = None


def _command_allowed(cmd: str, patterns: Sequence[str]) -> bool:
    if not patterns:
        return False
    for p in patterns:
        if fnmatch.fnmatch(cmd, p) or fnmatch.fnmatch(cmd.strip(), p):
            return True
        # Also allow the pattern as a substring (manual: fragment matching)
        if p in cmd:
            return True
    return False


def run_planned_commands(
    work_dir: str,
    commands: Sequence[str],
    allowed_globs: Sequence[str] | None,
    *,
    timeout_per_cmd: int = 300,
    env: dict[str, str] | None = None,
) -> list[CommandResult]:
    """Execute planned_commands; commands failing the allowlist are recorded as errors but not raised."""
    wd = os.path.abspath(work_dir)
    merged_env = {**os.environ, **(env or {})}
    results: list[CommandResult] = []
    globs = list(allowed_globs or [])

    for raw in commands:
        cmd = (raw or "").strip()
        if not cmd:
            continue
        if not _command_allowed(cmd, globs):
            results.append(
                CommandResult(
                    cmd=cmd,
                    returncode=-1,
                    stdout="",
                    stderr="",
                    allowed=False,
                    error="command_not_allowlisted",
                )
            )
            continue
        try:
            argv = shlex.split(cmd, posix=os.name != "nt")
        except ValueError as e:
            results.append(
                CommandResult(
                    cmd=cmd,
                    returncode=-1,
                    stdout="",
                    stderr=str(e),
                    allowed=True,
                    error="shlex_parse_error",
                )
            )
            continue
        if not argv:
            continue
        try:
            proc = subprocess.run(
                argv,
                cwd=wd,
                shell=False,
                capture_output=True,
                text=True,
                timeout=timeout_per_cmd,
                env=merged_env,
            )
            results.append(
                CommandResult(
                    cmd=cmd,
                    returncode=proc.returncode,
                    stdout=proc.stdout or "",
                    stderr=proc.stderr or "",
                    allowed=True,
                    error=None if proc.returncode == 0 else "nonzero_rc",
                )
            )
        except subprocess.TimeoutExpired:
            results.append(
                CommandResult(
                    cmd=cmd,
                    returncode=124,
                    stdout="",
                    stderr="timeout",
                    allowed=True,
                    error="timeout",
                )
            )
        except OSError as e:
            results.append(
                CommandResult(
                    cmd=cmd,
                    returncode=-1,
                    stdout="",
                    stderr=str(e),
                    allowed=True,
                    error="os_error",
                )
            )
    return results


def summarize_act_for_state(results: list[CommandResult]) -> dict[str, Any]:
    """Write a compact JSON-serializable summary into iterations[-1].act."""
    return {
        "runner_executed": True,
        "commands": [
            {
                "cmd": r.cmd,
                "returncode": r.returncode,
                "allowed": r.allowed,
                "error": r.error,
                "stderr_preview": (r.stderr or "")[:500],
            }
            for r in results
        ],
    }
