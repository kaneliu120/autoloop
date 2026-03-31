"""P2-2：Runner 指标（Prometheus 文本导出 + SSOT metadata）。"""

from __future__ import annotations

import json

from autoloop_runner import stateutil


def _escape_label_value(s: str) -> str:
    return (
        str(s)
        .replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", " ")
        .replace("\r", " ")
    )


def record_runner_outcome(work_dir: str, rc: int) -> None:
    """按 tick 退出码累计 pauses / failures / lock_denied（成功 rc=0 不计）。"""
    if rc == 0:
        return
    try:
        sp = stateutil.state_path(work_dir)
        st = stateutil.load_json(sp)
    except OSError:
        return
    meta = st.setdefault("metadata", {})
    m = meta.setdefault("runner_metrics", {})
    if rc == 11:
        m["lock_denied_total"] = int(m.get("lock_denied_total", 0)) + 1
    elif rc in (10, 12):
        m["pauses_total"] = int(m.get("pauses_total", 0)) + 1
    else:
        m["failures_total"] = int(m.get("failures_total", 0)) + 1
    meta["runner_metrics"] = m
    meta["updated_at"] = stateutil.now_iso()
    st["metadata"] = meta
    try:
        with open(sp, "w", encoding="utf-8") as f:
            json.dump(st, f, ensure_ascii=False, indent=2)
    except OSError:
        return


def record_api_call(work_dir: str, latency_ms: float) -> None:
    try:
        sp = stateutil.state_path(work_dir)
        st = stateutil.load_json(sp)
    except OSError:
        return
    meta = st.setdefault("metadata", {})
    m = meta.setdefault("runner_metrics", {})
    m["api_calls_total"] = int(m.get("api_calls_total", 0)) + 1
    m["api_latency_ms_sum"] = float(m.get("api_latency_ms_sum", 0.0)) + float(
        latency_ms
    )
    meta["runner_metrics"] = m
    meta["updated_at"] = stateutil.now_iso()
    st["metadata"] = meta
    try:
        with open(sp, "w", encoding="utf-8") as f:
            json.dump(st, f, ensure_ascii=False, indent=2)
    except OSError:
        return


def render_prometheus_text(work_dir: str) -> str:
    """OpenMetrics/Prometheus exposition（无 HTTP 服务，供 file_sd 或 sidecar 抓取）。"""
    try:
        sp = stateutil.state_path(work_dir)
        st = stateutil.load_json(sp)
    except OSError:
        return "# autoloop_runner: missing or unreadable autoloop-state.json\n"
    plan = st.get("plan", {})
    tid = _escape_label_value(str(plan.get("task_id", "unknown")))
    meta = st.get("metadata", {})
    m = meta.get("runner_metrics") or {}
    slices = int(meta.get("runner_tick_count", 0) or 0)
    lines = [
        "# HELP autoloop_runner_tick_slices_total Successful runner tick slices",
        "# TYPE autoloop_runner_tick_slices_total counter",
        'autoloop_runner_tick_slices_total{{task_id="{}"}} {}'.format(tid, slices),
        "# HELP autoloop_runner_api_calls_total OpenAI API calls (chat completions)",
        "# TYPE autoloop_runner_api_calls_total counter",
        'autoloop_runner_api_calls_total{{task_id="{}"}} {}'.format(
            tid, int(m.get("api_calls_total", 0) or 0)
        ),
        "# HELP autoloop_runner_api_latency_ms_sum Sum of API latencies (ms)",
        "# TYPE autoloop_runner_api_latency_ms_sum counter",
        'autoloop_runner_api_latency_ms_sum{{task_id="{}"}} {}'.format(
            tid, float(m.get("api_latency_ms_sum", 0.0) or 0.0)
        ),
        "# HELP autoloop_runner_pauses_total Tick exits with pause or cost cap (10/12)",
        "# TYPE autoloop_runner_pauses_total counter",
        'autoloop_runner_pauses_total{{task_id="{}"}} {}'.format(
            tid, int(m.get("pauses_total", 0) or 0)
        ),
        "# HELP autoloop_runner_failures_total Tick exits with error (1)",
        "# TYPE autoloop_runner_failures_total counter",
        'autoloop_runner_failures_total{{task_id="{}"}} {}'.format(
            tid, int(m.get("failures_total", 0) or 0)
        ),
        "# HELP autoloop_runner_lock_denied_total Workdir lock not acquired (11)",
        "# TYPE autoloop_runner_lock_denied_total counter",
        'autoloop_runner_lock_denied_total{{task_id="{}"}} {}'.format(
            tid, int(m.get("lock_denied_total", 0) or 0)
        ),
        "# HELP autoloop_runner_estimated_cost_usd Cumulative crude API cost estimate",
        "# TYPE autoloop_runner_estimated_cost_usd gauge",
        'autoloop_runner_estimated_cost_usd{{task_id="{}"}} {}'.format(
            tid, float(meta.get("runner_estimated_cost_usd", 0.0) or 0.0)
        ),
    ]
    return "\n".join(lines) + "\n"
