"""Single-step tick: advance according to checkpoint.last_completed_phase (implementation manual §5 strategy α + P1)."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from typing import Any, Callable

from autoloop_runner.act import run_planned_commands
from autoloop_runner.decide import handoff_to_state_json, validate_handoff
from autoloop_runner.llm_openai import chat_json
from autoloop_runner.lock import WorkdirLock
from autoloop_runner.metrics import record_api_call, record_runner_outcome
from autoloop_scripts.locate import scripts_directory
from autoloop_runner.reflect import normalize_reflect, validate_reflect
from autoloop_runner import runner_log
from autoloop_runner import stateutil
from autoloop_runner import synthesize
from autoloop_runner.tsv_auto import apply_auto_tsv_after_verify
from autoloop_runner.usage import accumulate_usage, check_cost_budget

log = logging.getLogger("autoloop_runner")


def _load_checkpoint(work_dir: str) -> dict[str, Any]:
    p = stateutil.checkpoint_path(work_dir)
    if not os.path.isfile(p):
        return {}
    return stateutil.load_json(p)


def _accumulate_llm_usage(work_dir: str, usage: dict[str, Any]) -> None:
    pt = int(usage.get("prompt_tokens", 0) or 0)
    ct = int(usage.get("completion_tokens", 0) or 0)
    if pt == 0 and ct == 0:
        return
    accumulate_usage(
        work_dir,
        prompt_tokens=pt,
        completion_tokens=ct,
        model=str(usage.get("model", "")),
        request_id=usage.get("request_id"),
    )


def _chat_json(
    work_dir: str, _chat_json_impl: Callable[..., Any] = chat_json, **kwargs: Any
) -> dict[str, Any]:
    t0 = time.monotonic()
    try:
        obj, usage = _chat_json_impl(**kwargs)
    except Exception as e:
        dt = (time.monotonic() - t0) * 1000.0
        runner_log.emit(
            work_dir,
            "openai_chat_error",
            latency_ms=dt,
            extra={"error": str(e)[:300]},
        )
        raise
    dt = (time.monotonic() - t0) * 1000.0
    _accumulate_llm_usage(work_dir, usage)
    pt = int(usage.get("prompt_tokens", 0) or 0)
    ct = int(usage.get("completion_tokens", 0) or 0)
    if pt + ct > 0:
        record_api_call(work_dir, dt)
    runner_log.emit(
        work_dir,
        "openai_chat_complete",
        request_id=usage.get("request_id"),
        latency_ms=dt,
    )
    return obj


def _mock_decide_json(work_dir: str, round_num: int) -> dict[str, Any]:
    render = scripts_directory() / "autoloop-render.py"
    return {
        "strategy_id": "S{:02d}-mock-runner".format(round_num),
        "hypothesis": "Mock tick without OpenAI",
        "planned_commands": [
            "python3 {} {}".format(render, work_dir),
        ],
        "impacted_dimensions": ["syntax"],
    }


def _build_decide_prompt(work_dir: str) -> tuple[str, str]:
    st_path = stateutil.state_path(work_dir)
    state = stateutil.load_json(st_path)
    plan = state.get("plan", {})
    goal = plan.get("goal", "")
    template = plan.get("template", "T1")
    gates = plan.get("gates", [])
    hist = plan.get("strategy_history", [])[-5:]
    ctx = json.dumps(
        {"goal": goal, "template": template, "gates": gates, "strategy_history": hist},
        ensure_ascii=False,
        indent=2,
    )
    system = (
        "You are the AutoLoop strategy orchestration assistant. Output only one JSON object, with keys: "
        "strategy_id (S + two-digit round number + short name), hypothesis, planned_commands (string array), "
        "impacted_dimensions (string array; do not use an empty list, and use a concrete dimension such as syntax). "
        "Do not use markdown or code blocks."
    )
    user = "Task context:\n{}\n\nPlease provide the DECIDE handoff JSON for this round.".format(ctx)
    return system, user


def _build_reflect_prompt(work_dir: str, round_num: int) -> tuple[str, str]:
    st = stateutil.load_json(stateutil.state_path(work_dir))
    iters = st.get("iterations", [])
    last_scores = iters[-1].get("scores", {}) if iters else {}
    handoff = st.get("plan", {}).get("decide_act_handoff") or {}
    sid = handoff.get("strategy_id", "S{:02d}-unknown".format(round_num))
    evolve = iters[-1].get("evolve", {}) if iters else {}
    system = (
        "You are the AutoLoop REFLECT assistant. Output only one JSON object; all of these keys must be present: "
        "strategy_id (string), effect (must be one of \u4fdd\u6301, \u907f\u514d, \u5f85\u9a8c\u8bc1), "
        "score (string, such as +0.5 or 0), dimension (string, such as syntax), "
        "context (string, one-sentence retrospective). "
        "Do not use markdown or code blocks."
    )
    user = "This round's strategy_id={} scores={} evolve={}".format(
        sid,
        json.dumps(last_scores, ensure_ascii=False),
        json.dumps(evolve, ensure_ascii=False),
    )
    return system, user


def _sync_post_controller(work_dir: str, rc: int) -> None:
    """P1-4: write metadata.runner_status and pause_reason when paused or errored."""
    if rc == 0:
        stateutil.set_metadata(work_dir, runner_status="RUNNING", pause_reason="")
        return
    if rc == 10:
        cp = _load_checkpoint(work_dir)
        rs = cp.get("pause_state") or {}
        reason = str(rs.get("reason", "pause"))[:2000]
        stateutil.set_metadata(
            work_dir, runner_status="PAUSED", pause_reason=reason
        )
        return
    if rc == 1:
        stateutil.set_metadata(
            work_dir,
            runner_status="ERROR",
            pause_reason="controller_exit_1",
        )


def run_tick(
    work_dir: str,
    *,
    python_exe: str | None = None,
    strict: bool = True,
    lock_blocking: bool = True,
) -> int:
    """
    Execute exactly one advancement slice. Returns:
      0 success, 1 error, 10 pause required, 11 lock not acquired, 12 cost/budget cap (P1-5).
    """
    work_dir = os.path.abspath(work_dir)
    ok_budget, br = check_cost_budget(work_dir)
    if not ok_budget:
        log.warning("cost budget: %s", br)
        stateutil.set_metadata(
            work_dir, runner_status="PAUSED", pause_reason=br or "cost_cap"
        )
        record_runner_outcome(work_dir, 12)
        return 12

    wl = WorkdirLock(work_dir)
    if not wl.acquire(blocking=lock_blocking):
        log.warning("work_dir lock busy: %s", work_dir)
        record_runner_outcome(work_dir, 11)
        return 11
    try:
        rc = _tick_unlocked(work_dir, python_exe=python_exe, strict=strict)
        record_runner_outcome(work_dir, rc)
        return rc
    finally:
        wl.release()


def _tick_unlocked(
    work_dir: str,
    *,
    python_exe: str | None = None,
    strict: bool,
) -> int:
    cp = _load_checkpoint(work_dir)
    if cp.get("pause_state"):
        stateutil.set_metadata(
            work_dir,
            runner_status="PAUSED",
            pause_reason=str(cp["pause_state"].get("reason", "")),
        )
        log.info("checkpoint paused; exit 10")
        return 10

    last = cp.get("last_completed_phase", "INIT")
    runner_log.emit(work_dir, "tick_slice", phase=last)

    env = os.environ.copy()
    if strict:
        env["AUTOLOOP_STRICT"] = "1"
    env["AUTOLOOP_EXIT_CODES"] = "1"

    extra_strict = ["--strict"] if strict else []

    def controller(*args: str) -> int:
        return stateutil.run_controller(
            work_dir, list(args) + extra_strict, python_exe=python_exe, env=env
        )

    def run_verify_with_retry() -> int:
        """P1-1: do not skip VERIFY; optional RUNNER_VERIFY_RETRY retries."""
        retries = max(0, int(os.environ.get("RUNNER_VERIFY_RETRY", "0")))
        delay = float(os.environ.get("RUNNER_VERIFY_RETRY_DELAY_SEC", "2"))
        last_rc = 1
        for attempt in range(retries + 1):
            last_rc = controller("--stop-after", "VERIFY")
            if last_rc == 0:
                return 0
            if attempt < retries:
                log.warning(
                    "VERIFY slice rc=%s, retry %s/%s",
                    last_rc,
                    attempt + 1,
                    retries,
                )
                time.sleep(delay)
        return last_rc

    rc_ctrl = 0

    if last == "INIT":
        rc_ctrl = controller("--stop-after", "ORIENT")
        _sync_post_controller(work_dir, rc_ctrl)
        if rc_ctrl == 0:
            stateutil.bump_runner_tick(work_dir)
        return _map_controller_rc(rc_ctrl)

    if last == "ORIENT":
        if not _runner_decide(work_dir, python_exe):
            stateutil.set_metadata(
                work_dir, runner_status="PAUSED", pause_reason="decide_failed"
            )
            return 10
        rc_ctrl = controller("--stop-after", "DECIDE")
        _sync_post_controller(work_dir, rc_ctrl)
        if rc_ctrl == 0:
            stateutil.bump_runner_tick(work_dir)
        return _map_controller_rc(rc_ctrl)

    if last == "DECIDE":
        if not _runner_act(work_dir, python_exe):
            stateutil.set_metadata(
                work_dir, runner_status="PAUSED", pause_reason="act_allowlist"
            )
            return 10
        rc_ctrl = controller("--stop-after", "ACT")
        _sync_post_controller(work_dir, rc_ctrl)
        if rc_ctrl == 0:
            stateutil.bump_runner_tick(work_dir)
        return _map_controller_rc(rc_ctrl)

    if last == "ACT":
        # P1-1: VERIFY is executed fully by the controller (including score/validate/variance)
        rc_ctrl = run_verify_with_retry()
        _sync_post_controller(work_dir, rc_ctrl)
        if rc_ctrl == 0:
            ok_tsv, tsv_reason = apply_auto_tsv_after_verify(
                work_dir, strict=strict, python_exe=python_exe
            )
            if not ok_tsv:
                stateutil.set_metadata(
                    work_dir,
                    runner_status="ERROR",
                    pause_reason="auto_tsv_failed",
                )
                _sync_post_controller(work_dir, 1)
                return 1
            runner_log.emit(
                work_dir,
                "verify_auto_tsv",
                phase="VERIFY",
                extra={"tsv_auto": tsv_reason},
            )
            stateutil.bump_runner_tick(work_dir)
        return _map_controller_rc(rc_ctrl)

    if last == "VERIFY":
        mode = os.environ.get("RUNNER_SYNTHESIZE_MODE", "minimal").strip().lower()
        if mode == "llm" and (
            os.environ.get("OPENAI_API_KEY", "").strip()
            or os.environ.get("RUNNER_MOCK_LLM", "").lower() in ("1", "true")
        ):
            if os.environ.get("RUNNER_MOCK_LLM", "").lower() in ("1", "true"):
                synthesize.synthesize_minimal(work_dir, python_exe=python_exe)
            else:

                def _fn(system: str, user: str) -> dict[str, Any]:
                    return _chat_json(
                        work_dir,
                        system=system,
                        user=user,
                        model=os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
                        api_key=os.environ.get("OPENAI_API_KEY", ""),
                        base_url=os.environ.get("OPENAI_BASE_URL") or None,
                        timeout=float(os.environ.get("RUNNER_OPENAI_TIMEOUT", "120")),
                        max_tokens=int(os.environ.get("RUNNER_MAX_TOKENS", "1024")),
                        temperature=float(os.environ.get("RUNNER_TEMPERATURE", "0.25")),
                    )

                synthesize.synthesize_llm(
                    work_dir, chat_json_fn=_fn, python_exe=python_exe
                )
        elif mode == "minimal":
            synthesize.synthesize_minimal(work_dir, python_exe=python_exe)
        elif mode == "skip":
            log.info("RUNNER_SYNTHESIZE_MODE=skip")
        else:
            log.warning("unknown RUNNER_SYNTHESIZE_MODE=%s, using minimal", mode)
            synthesize.synthesize_minimal(work_dir, python_exe=python_exe)

        rc_ctrl = controller("--stop-after", "SYNTHESIZE")
        _sync_post_controller(work_dir, rc_ctrl)
        if rc_ctrl == 0:
            stateutil.bump_runner_tick(work_dir)
        return _map_controller_rc(rc_ctrl)

    if last == "SYNTHESIZE":
        rc_ctrl = controller("--stop-after", "EVOLVE")
        _sync_post_controller(work_dir, rc_ctrl)
        if rc_ctrl == 0:
            stateutil.bump_runner_tick(work_dir)
        return _map_controller_rc(rc_ctrl)

    if last == "EVOLVE":
        if not _runner_reflect(work_dir, python_exe):
            log.warning("reflect skipped or failed; continuing REFLECT phase")
        rc_ctrl = controller("--stop-after", "REFLECT")
        _sync_post_controller(work_dir, rc_ctrl)
        if rc_ctrl == 0:
            stateutil.bump_runner_tick(work_dir)
        return _map_controller_rc(rc_ctrl)

    if last == "REFLECT":
        rc_ctrl = controller("--stop-after", "ORIENT")
        _sync_post_controller(work_dir, rc_ctrl)
        if rc_ctrl == 0:
            stateutil.bump_runner_tick(work_dir)
        return _map_controller_rc(rc_ctrl)

    log.warning("unknown last_completed_phase=%s", last)
    rc_ctrl = controller("--stop-after", "ORIENT")
    _sync_post_controller(work_dir, rc_ctrl)
    if rc_ctrl == 0:
        stateutil.bump_runner_tick(work_dir)
    return _map_controller_rc(rc_ctrl)


def _map_controller_rc(rc: int) -> int:
    if rc == 10:
        return 10
    if rc != 0:
        return 1
    return 0


def _runner_decide(work_dir: str, python_exe: str | None) -> bool:
    if os.environ.get("RUNNER_MOCK_LLM", "").strip().lower() in ("1", "true", "yes"):
        st = stateutil.load_json(stateutil.state_path(work_dir))
        r = len(st.get("iterations", []))
        obj = _mock_decide_json(work_dir, max(r, 1))
    else:
        key = (os.environ.get("OPENAI_API_KEY") or "").strip()
        if not key:
            log.error("OPENAI_API_KEY is not set and RUNNER_MOCK_LLM=1 is not enabled")
            return False
        system, user = _build_decide_prompt(work_dir)
        user_hash = hashlib.sha256(user.encode("utf-8")).hexdigest()[:16]
        log.info("decide prompt_hash=%s", user_hash)
        try:
            obj = _chat_json(
                work_dir,
                system=system,
                user=user,
                model=os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
                api_key=key,
                base_url=os.environ.get("OPENAI_BASE_URL") or None,
                timeout=float(os.environ.get("RUNNER_OPENAI_TIMEOUT", "120")),
                max_tokens=int(os.environ.get("RUNNER_MAX_TOKENS", "2048")),
                temperature=float(os.environ.get("RUNNER_TEMPERATURE", "0.3")),
                max_retries=int(os.environ.get("RUNNER_OPENAI_RETRIES", "5")),
            )
        except Exception as e:
            log.exception("OpenAI decide failed: %s", e)
            return False

    ok, reason = validate_handoff(obj)
    if not ok:
        log.error("handoff invalid: %s %s", reason, obj)
        return False
    payload = handoff_to_state_json(obj)
    rc = stateutil.run_state_update(
        work_dir, "plan.decide_act_handoff", payload, python_exe=python_exe
    )
    return rc == 0


def _allowed_globs(work_dir: str) -> list[str]:
    st = stateutil.load_json(stateutil.state_path(work_dir))
    tp = st.get("plan", {}).get("template_params") or {}
    g = tp.get("allowed_script_globs") or tp.get("allowed_commands")
    if isinstance(g, list):
        return [str(x) for x in g]
    if isinstance(g, str) and g.strip():
        return [g.strip()]
    sd = str(scripts_directory())
    return [
        "python3 scripts/autoloop-*.py *",
        "python3 {}/autoloop-*.py *".format(sd),
    ]


def _runner_act(work_dir: str, python_exe: str | None) -> bool:
    st = stateutil.load_json(stateutil.state_path(work_dir))
    handoff = st.get("plan", {}).get("decide_act_handoff") or {}
    cmds = handoff.get("planned_commands") or []
    if not isinstance(cmds, list):
        return False
    timeout = int(os.environ.get("RUNNER_ACT_TIMEOUT", "300"))
    results = run_planned_commands(
        work_dir, cmds, _allowed_globs(work_dir), timeout_per_cmd=timeout
    )
    bad = [r for r in results if not r.allowed or r.error]
    if bad:
        err_line = "; ".join(
            "{}:{}".format(r.cmd, r.error or r.stderr[:80]) for r in bad
        )
        meta_err = json.dumps(
            {
                "script": "autoloop-runner.act",
                "returncode": -1,
                "stderr": err_line,
                "time": "",
            },
            ensure_ascii=False,
        )
        stateutil.run_state_update(
            work_dir, "metadata.last_error", meta_err, python_exe=python_exe
        )
        return False
    try:
        stateutil.merge_iteration_act(
            work_dir,
            {
                "runner": True,
                "commands": [
                    {
                        "cmd": r.cmd,
                        "returncode": r.returncode,
                        "allowed": r.allowed,
                    }
                    for r in results
                ],
            },
        )
    except Exception as e:
        log.exception("merge_iteration_act: %s", e)
        return False
    return True


def _runner_reflect(work_dir: str, python_exe: str | None) -> bool:
    st = stateutil.load_json(stateutil.state_path(work_dir))
    round_num = len(st.get("iterations", [])) or 1
    if os.environ.get("RUNNER_MOCK_LLM", "").strip().lower() in ("1", "true", "yes"):
        ref = {
            "strategy_id": (st.get("plan", {}).get("decide_act_handoff") or {}).get(
                "strategy_id", "S01-mock"
            ),
            "effect": "\u5f85\u9a8c\u8bc1",
            "score": "0",
            "dimension": "syntax",
            "context": "mock reflect",
        }
    else:
        key = (os.environ.get("OPENAI_API_KEY") or "").strip()
        if not key:
            return False
        system, user = _build_reflect_prompt(work_dir, round_num)
        try:
            ref = _chat_json(
                work_dir,
                system=system,
                user=user,
                model=os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
                api_key=key,
                base_url=os.environ.get("OPENAI_BASE_URL") or None,
                timeout=float(os.environ.get("RUNNER_OPENAI_TIMEOUT", "120")),
                max_tokens=int(os.environ.get("RUNNER_MAX_TOKENS", "1024")),
                temperature=float(os.environ.get("RUNNER_TEMPERATURE", "0.2")),
            )
        except Exception:
            log.exception("reflect LLM failed")
            return False

    ref = normalize_reflect(ref)
    ok, rreason = validate_reflect(ref)
    if not ok:
        log.error("reflect invalid: %s %s", rreason, ref)
        return False
    payload = json.dumps(ref, ensure_ascii=False, separators=(",", ":"))
    rc = stateutil.run_state_update(
        work_dir, "iterations[-1].reflect", payload, python_exe=python_exe
    )
    return rc == 0
