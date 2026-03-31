"""P1-3：SYNTHESIZE 最小写回 — findings.rounds + add-finding。"""

from __future__ import annotations

import json
import logging
from typing import Any

from autoloop_runner import stateutil

log = logging.getLogger("autoloop_runner")


def build_round_summary(state: dict[str, Any]) -> str:
    """从末轮 scores + gates 生成一行摘要（确定性，无 LLM）。"""
    plan = state.get("plan", {})
    gates = plan.get("gates", [])
    iters = state.get("iterations") or []
    scores = iters[-1].get("scores", {}) if iters else {}
    parts = []
    for g in gates:
        d = g.get("dimension") or g.get("dim", "")
        cur = g.get("current")
        thr = g.get("threshold")
        st = g.get("status", "")
        if d:
            parts.append("{}:当前={} 目标={} {}".format(d, cur, thr, st))
    return "SYNTHESIZE(runner-minimal) scores={} gates={}".format(
        json.dumps(scores, ensure_ascii=False),
        "; ".join(parts[:12]) or "—",
    )


def synthesize_minimal(work_dir: str, python_exe: str | None = None) -> bool:
    """向末轮追加一条 add-finding（dimension=runner_synthesize）。"""
    sp = stateutil.state_path(work_dir)
    state = stateutil.load_json(sp)
    content = build_round_summary(state)
    finding = {
        "dimension": "runner_synthesize",
        "content": content[:8000],
        "source": "autoloop-runner",
        "confidence": "中",
        "type": "finding",
    }
    rc = stateutil.run_add_finding(
        work_dir, json.dumps(finding, ensure_ascii=False), python_exe=python_exe
    )
    if rc != 0:
        log.warning("add-finding (minimal synthesize) rc=%s", rc)
    return rc == 0


def synthesize_llm(
    work_dir: str,
    *,
    chat_json_fn,
    python_exe: str | None = None,
) -> bool:
    """可选：模型产出 dimension+content，再 add-finding。"""
    state = stateutil.load_json(stateutil.state_path(work_dir))
    summary = build_round_summary(state)
    system = (
        "你是 AutoLoop SYNTHESIZE 助手。只输出 JSON，键: dimension（短字符串）, "
        "content（本轮综合发现，中文一段）。不要 markdown。"
    )
    user = "基于摘要写一条可写入 findings 的综合:\n{}".format(summary[:6000])
    try:
        obj = chat_json_fn(system=system, user=user)
    except Exception:
        log.exception("synthesize_llm failed")
        return False
    dim = str(obj.get("dimension", "")).strip()
    content = str(obj.get("content", "")).strip()
    if not dim or not content:
        return False
    finding = {
        "dimension": dim[:120],
        "content": content[:8000],
        "source": "autoloop-runner-llm",
        "confidence": str(obj.get("confidence", "中")),
        "type": "finding",
    }
    rc = stateutil.run_add_finding(
        work_dir, json.dumps(finding, ensure_ascii=False), python_exe=python_exe
    )
    return rc == 0
