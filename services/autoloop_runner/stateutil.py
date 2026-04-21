"""Read and write autoloop-state.json / checkpoint.json (runner side)."""

from __future__ import annotations

import datetime
import json
import os
import subprocess
import sys
from typing import Any

from autoloop_scripts.locate import scripts_directory


def now_iso() -> str:
    return datetime.datetime.now().isoformat(timespec="seconds")


def load_json(path: str) -> Any:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def state_path(work_dir: str) -> str:
    return os.path.join(os.path.abspath(work_dir), "autoloop-state.json")


def checkpoint_path(work_dir: str) -> str:
    return os.path.join(os.path.abspath(work_dir), "checkpoint.json")


def run_add_tsv_row(
    work_dir: str, row_json: str, python_exe: str | None = None
) -> int:
    exe = python_exe or sys.executable
    script = str(scripts_directory() / "autoloop-state.py")
    return subprocess.call(
        [exe, script, "add-tsv-row", os.path.abspath(work_dir), row_json],
        cwd=work_dir,
    )


def run_add_finding(
    work_dir: str, finding_json: str, python_exe: str | None = None
) -> int:
    exe = python_exe or sys.executable
    script = str(scripts_directory() / "autoloop-state.py")
    return subprocess.call(
        [exe, script, "add-finding", os.path.abspath(work_dir), finding_json],
        cwd=work_dir,
    )


def run_state_update(
    work_dir: str, field_path: str, value_json: str, python_exe: str | None = None
) -> int:
    exe = python_exe or sys.executable
    script = str(scripts_directory() / "autoloop-state.py")
    return subprocess.call(
        [exe, script, "update", work_dir, field_path, value_json],
        cwd=work_dir,
    )


def run_controller(
    work_dir: str,
    extra_args: list[str],
    python_exe: str | None = None,
    env: dict[str, str] | None = None,
) -> int:
    exe = python_exe or sys.executable
    script = str(scripts_directory() / "autoloop-controller.py")
    cmd = [exe, script, os.path.abspath(work_dir), *extra_args]
    merged = {**os.environ, **(env or {})}
    return subprocess.call(cmd, cwd=work_dir, env=merged)


def bump_runner_tick(work_dir: str) -> None:
    sp = state_path(work_dir)
    st = load_json(sp)
    meta = st.setdefault("metadata", {})
    meta["runner_tick_count"] = int(meta.get("runner_tick_count", 0)) + 1
    meta["updated_at"] = now_iso()
    st["metadata"] = meta
    with open(sp, "w", encoding="utf-8") as f:
        json.dump(st, f, ensure_ascii=False, indent=2)


def merge_iteration_act(work_dir: str, record: dict[str, Any]) -> None:
    """Append one runner execution record to iterations[-1].act.records."""
    sp = state_path(work_dir)
    st = load_json(sp)
    iters = st.get("iterations") or []
    if not iters:
        raise ValueError("no iterations")
    act = iters[-1].setdefault("act", {})
    act.setdefault("records", [])
    if isinstance(act["records"], list):
        act["records"].append(record)
    st["iterations"][-1]["act"] = act
    st.setdefault("metadata", {})["updated_at"] = now_iso()
    with open(sp, "w", encoding="utf-8") as f:
        json.dump(st, f, ensure_ascii=False, indent=2)


def set_metadata(
    work_dir: str,
    *,
    runner_status: str | None = None,
    pause_reason: str | None = None,
    python_exe: str | None = None,
) -> None:
    """Write metadata.runner_status / metadata.pause_reason (dot-paths must already exist)."""
    sp = state_path(work_dir)
    st = load_json(sp)
    meta = st.setdefault("metadata", {})
    if runner_status is not None:
        meta["runner_status"] = runner_status
    if pause_reason is not None:
        meta["pause_reason"] = pause_reason
    meta["updated_at"] = now_iso()
    st["metadata"] = meta
    with open(sp, "w", encoding="utf-8") as f:
        json.dump(st, f, ensure_ascii=False, indent=2)
