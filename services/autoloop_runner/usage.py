"""P1-5: API token accumulation and a rough cost cap."""

from __future__ import annotations

import json
import os
from typing import Any

from autoloop_runner import stateutil

# Default pricing: gpt-4o-mini scale (USD / 1K tokens), overridable via env vars
_DEFAULT_IN_1K = float(os.environ.get("RUNNER_PRICE_INPUT_PER_1K", "0.00015"))
_DEFAULT_OUT_1K = float(os.environ.get("RUNNER_PRICE_OUTPUT_PER_1K", "0.0006"))


def estimate_cost_usd(
    prompt_tokens: int, completion_tokens: int, *, model: str | None = None
) -> float:
    _ = model
    return (prompt_tokens / 1000.0) * _DEFAULT_IN_1K + (
        completion_tokens / 1000.0
    ) * _DEFAULT_OUT_1K


def accumulate_usage(
    work_dir: str,
    *,
    prompt_tokens: int,
    completion_tokens: int,
    model: str,
    request_id: str | None = None,
) -> None:
    sp = stateutil.state_path(work_dir)
    st = stateutil.load_json(sp)
    meta = st.setdefault("metadata", {})
    meta["runner_api_prompt_tokens"] = int(
        meta.get("runner_api_prompt_tokens", 0)
    ) + int(prompt_tokens)
    meta["runner_api_completion_tokens"] = int(
        meta.get("runner_api_completion_tokens", 0)
    ) + int(completion_tokens)
    delta = estimate_cost_usd(prompt_tokens, completion_tokens, model=model)
    prev = float(meta.get("runner_estimated_cost_usd", 0) or 0)
    meta["runner_estimated_cost_usd"] = round(prev + delta, 8)
    if request_id:
        log = meta.setdefault("runner_api_request_log", [])
        if isinstance(log, list) and len(log) < 500:
            log.append(
                {
                    "model": model,
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "request_id": request_id,
                }
            )
    meta["updated_at"] = stateutil.now_iso()
    st["metadata"] = meta
    with open(sp, "w", encoding="utf-8") as f:
        json.dump(st, f, ensure_ascii=False, indent=2)


def check_cost_budget(work_dir: str) -> tuple[bool, str]:
    """Return (False, reason) if RUNNER_MAX_ESTIMATED_USD is exceeded."""
    cap = os.environ.get("RUNNER_MAX_ESTIMATED_USD", "").strip()
    if not cap:
        return True, ""
    try:
        mx = float(cap)
    except ValueError:
        return True, ""
    if mx <= 0:
        return True, ""
    st = stateutil.load_json(stateutil.state_path(work_dir))
    spent = float(st.get("metadata", {}).get("runner_estimated_cost_usd", 0) or 0)
    if spent >= mx:
        return False, "runner_cost_cap:{}>={}".format(spent, mx)
    return True, ""
