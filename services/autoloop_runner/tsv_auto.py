"""P2-3: auto-write a TSV row after VERIFY when handoff.impacted_dimensions is set (side_effect must be non-empty)."""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from autoloop_runner import stateutil

log = logging.getLogger("autoloop_runner")

_BAD_SIDE_EFFECT = frozenset({"", "\u65e0", "—", "-", "none", "n/a", "na"})


def _normalize_impacted(handoff: dict[str, Any]) -> list[str]:
    raw = handoff.get("impacted_dimensions")
    if raw is None:
        raw = handoff.get("target_dimensions")
    if raw is None:
        return []
    if isinstance(raw, str):
        s = raw.strip()
        return [s] if s else []
    if isinstance(raw, list):
        return [str(x).strip() for x in raw if str(x).strip()]
    return []


def needs_auto_tsv_row(state: dict[str, Any]) -> bool:
    """If the last TSV row has an empty/no side_effect, an additional row must be written (aligned with strict autoloop-validate)."""
    handoff = state.get("plan", {}).get("decide_act_handoff") or {}
    if not isinstance(handoff, dict):
        return False
    impacted = _normalize_impacted(handoff)
    if not impacted:
        return False
    rows = state.get("results_tsv") or []
    if not rows:
        return True
    last = rows[-1]
    se = (last.get("side_effect") or "").strip().lower()
    if se in _BAD_SIDE_EFFECT:
        return True
    return False


def build_verify_tsv_row(state: dict[str, Any]) -> dict[str, Any] | None:
    handoff = state.get("plan", {}).get("decide_act_handoff") or {}
    if not isinstance(handoff, dict):
        return None
    impacted = _normalize_impacted(handoff)
    if not impacted:
        return None
    iters = state.get("iterations") or []
    if not iters:
        return None
    scores = iters[-1].get("scores") or {}
    dim = impacted[0]
    if dim not in scores and scores:
        dim = next(iter(scores.keys()))
    val = scores.get(dim, "—")
    sid = str(handoff.get("strategy_id", "") or "—")
    side_effect = "Cross-dimension impact: {}".format(",".join(impacted))
    proto = str(state.get("metadata", {}).get("protocol_version", "1.0.0"))
    iteration = len(iters)
    return {
        "iteration": iteration,
        "phase": "VERIFY",
        "status": "Pass",
        "dimension": dim,
        "metric_value": str(val),
        "delta": "—",
        "strategy_id": sid,
        "action_summary": "runner:auto-tsv(P2-3)",
        "side_effect": side_effect,
        "evidence_ref": "—",
        "unit_id": "—",
        "protocol_version": proto,
        "score_variance": "0",
        "confidence": "100",
        "details": json.dumps(
            {"impacted_dimensions": impacted, "source": "autoloop-runner"},
            ensure_ascii=False,
        ),
    }


def apply_auto_tsv_after_verify(
    work_dir: str,
    *,
    strict: bool,
    python_exe: str | None = None,
) -> tuple[bool, str]:
    """
    Call after VERIFY succeeds. Under strict mode, add-tsv-row failure returns (False, reason).
    """
    if os.environ.get("RUNNER_SKIP_AUTO_TSV", "").strip().lower() in (
        "1",
        "true",
        "yes",
    ):
        return True, "skipped"

    sp = stateutil.state_path(work_dir)
    st = stateutil.load_json(sp)
    if not needs_auto_tsv_row(st):
        return True, "not_needed"
    row = build_verify_tsv_row(st)
    if not row:
        return True, "no_row"
    payload = json.dumps(row, ensure_ascii=False, separators=(",", ":"))
    rc = stateutil.run_add_tsv_row(work_dir, payload, python_exe=python_exe)
    if rc != 0:
        msg = "add-tsv-row failed rc={}".format(rc)
        log.error(msg)
        if strict:
            return False, msg
        return True, "warn:" + msg
    return True, "ok"
