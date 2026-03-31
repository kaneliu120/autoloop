"""P2-1：结构化日志（task_id / round / phase / request_id）。"""

from __future__ import annotations

import json
import os
import sys
from typing import Any

from autoloop_runner import stateutil


def _json_log_enabled() -> bool:
    return os.environ.get("RUNNER_JSON_LOG", "").strip().lower() in (
        "1",
        "true",
        "yes",
    )


def _json_log_path() -> str | None:
    p = os.environ.get("RUNNER_JSON_LOG_FILE", "").strip()
    return p or None


def emit(
    work_dir: str | None,
    event: str,
    *,
    phase: str | None = None,
    request_id: str | None = None,
    latency_ms: float | None = None,
    extra: dict[str, Any] | None = None,
) -> None:
    """输出一行 JSON 到 stderr 或 RUNNER_JSON_LOG_FILE（需 RUNNER_JSON_LOG=1）。"""
    if not _json_log_enabled():
        return
    row: dict[str, Any] = {
        "event": event,
        "ts": stateutil.now_iso(),
    }
    if work_dir:
        try:
            st = stateutil.load_json(stateutil.state_path(work_dir))
            plan = st.get("plan", {})
            row["task_id"] = plan.get("task_id", "")
            row["round"] = plan.get("budget", {}).get("current_round")
        except OSError:
            row["task_id"] = ""
            row["round"] = None
        try:
            cp = stateutil.load_json(stateutil.checkpoint_path(work_dir))
            row["checkpoint_phase"] = cp.get("current_phase") or cp.get(
                "last_completed_phase"
            )
        except OSError:
            row["checkpoint_phase"] = None
    if phase is not None:
        row["phase"] = phase
    if request_id:
        row["request_id"] = request_id
    if latency_ms is not None:
        row["latency_ms"] = round(latency_ms, 3)
    if extra:
        for k, v in extra.items():
            if k not in row:
                row[k] = v
    line = json.dumps(row, ensure_ascii=False)
    path = _json_log_path()
    if path:
        with open(path, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    else:
        print(line, file=sys.stderr, flush=True)
