#!/usr/bin/env python3
"""AutoLoop Middleware — cross-cutting concern module (functional implementation)

Extracts cross-cutting logic from controller.py into independent, pluggable Middleware functions.
Each middleware can be enabled or disabled independently without affecting the core OODA pipeline.

Relationship to scripts/middleware/:
- This file (autoloop-middleware.py): functional implementation, runnable on its own and useful for CLI debugging,
  for future controller integration via run_middleware_chain()
- scripts/middleware/: class-based interface definitions (OOP), used when the architecture is refactored
  to replace inline controller logic with standalone modules
- Both are different implementation styles for the same design and will be unified when the controller is refactored (P3-08 Phase 2)

Current modules:
1. LoggingMiddleware — unified phase input/output logging
2. CostTrackingMiddleware — accumulated subagent call cost
3. EvaluatorAuditMiddleware — scoring event tracking (P1-05 extension)
4. FailureClassificationMiddleware — automatic ACT failure classification (P2-12 extension)
5. SecurityMiddleware — cross-platform security checks (P3-04/05 integration)

Middleware interface contract:
  Each middleware is a function with the signature:
    def middleware_name(phase: str, state: dict, work_dir: str, **kwargs) -> dict:
      # returns {"proceed": True/False, "modifications": {...}}
"""
import os
import sys
import json
import time


def logging_middleware(phase, state, work_dir, **kwargs):
    """Unified phase logging — record each phase's start/end time and key inputs."""
    template = state.get("plan", {}).get("template", "?")
    round_num = len(state.get("plan", {}).get("iterations", []))
    timestamp = time.strftime("%Y-%m-%dT%H:%M:%S")

    log_entry = {
        "timestamp": timestamp,
        "phase": phase,
        "template": template,
        "round": round_num,
    }

    # Append to the middleware log
    log_dir = os.path.join(work_dir, ".autoloop")
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "middleware.jsonl")
    with open(log_file, "a") as f:
        f.write(json.dumps(log_entry) + "\n")

    return {"proceed": True, "modifications": {}}


def cost_tracking_middleware(phase, state, work_dir, **kwargs):
    """Cost tracking — accumulate subagent call counts after ACT."""
    if phase != "ACT":
        return {"proceed": True, "modifications": {}}

    iterations = state.get("plan", {}).get("iterations", [])
    total_subagent_calls = sum(
        len(it.get("act", {}).get("subagent_results", []))
        for it in iterations
        if isinstance(it.get("act"), dict)
    )

    return {
        "proceed": True,
        "modifications": {"metadata.total_subagent_calls": total_subagent_calls},
    }


def evaluator_audit_middleware(phase, state, work_dir, **kwargs):
    """Evaluation audit — record scoring events after VERIFY."""
    if phase != "VERIFY":
        return {"proceed": True, "modifications": {}}

    iterations = state.get("plan", {}).get("iterations", [])
    if not iterations:
        return {"proceed": True, "modifications": {}}

    latest = iterations[-1]
    scores = latest.get("scores", {})

    # Detect scoring variance (cross-round differences within the same dimension)
    if len(iterations) >= 2:
        prev_scores = iterations[-2].get("scores", {})
        for dim, score_data in scores.items():
            if isinstance(score_data, dict) and dim in prev_scores:
                prev = prev_scores[dim]
                if isinstance(prev, dict):
                    curr_val = score_data.get("score", 0)
                    prev_val = prev.get("score", 0)
                    confidence = score_data.get("confidence", "heuristic")
                    margin = score_data.get("margin", 1.5)
                    # If variance exceeds 2x the margin, record it as an anomaly
                    if margin and abs(curr_val - prev_val) > margin * 2:
                        _log_evaluator_event(
                            work_dir,
                            "scoring_variance",
                            {
                                "dimension": dim,
                                "prev": prev_val,
                                "curr": curr_val,
                                "confidence": confidence,
                                "variance": abs(curr_val - prev_val),
                            },
                        )

    return {"proceed": True, "modifications": {}}


def failure_classification_middleware(phase, state, work_dir, **kwargs):
    """Failure classification — check for unclassified failures after ACT.

    Note: the full classify_failure logic lives in autoloop-controller.py.
    This middleware only detects and marks issues; it does not call controller internals directly.
    classify_failure may later be extracted into a shared module and called directly.
    """
    if phase != "ACT":
        return {"proceed": True, "modifications": {}}

    iterations = state.get("plan", {}).get("iterations", [])
    if not iterations:
        return {"proceed": True, "modifications": {}}

    latest_act = iterations[-1].get("act", {})
    if isinstance(latest_act, dict) and latest_act.get("failure_type") is None:
        error_msg = latest_act.get("error", "") or latest_act.get(
            "failure_detail", ""
        )
        if error_msg:
            # Mark it for classification so the controller can handle it next
            return {
                "proceed": True,
                "modifications": {
                    "metadata.unclassified_failure": True,
                    "metadata.failure_error_preview": error_msg[:200],
                },
            }

    return {"proceed": True, "modifications": {}}


def security_middleware(phase, state, work_dir, **kwargs):
    """Security check — intercept writes outside Claude Code."""
    platform = os.environ.get("AUTOLOOP_PLATFORM", "claude-code")
    if platform == "claude-code":
        return {"proceed": True, "modifications": {}}  # Claude Code is handled by the host

    # Non-Claude Code environment: inspect ACT-stage tool calls
    if phase == "ACT":
        return {"proceed": True, "modifications": {"security_check_required": True}}

    return {"proceed": True, "modifications": {}}


# --- Middleware Registry ---
MIDDLEWARE_REGISTRY = {
    "logging": logging_middleware,
    "cost_tracking": cost_tracking_middleware,
    "evaluator_audit": evaluator_audit_middleware,
    "failure_classification": failure_classification_middleware,
    "security": security_middleware,
}


def run_middleware_chain(phase, state, work_dir, enabled=None):
    """Execute the middleware chain.

    Args:
        phase: OODA phase name (OBSERVE, ORIENT, DECIDE, ACT, VERIFY, SYNTHESIZE, EVOLVE, REFLECT)
        state: contents of autoloop-state.json
        work_dir: work directory path
        enabled: list of middleware names to enable; all are enabled by default.
                 May also be set via the AUTOLOOP_MIDDLEWARE env var (comma-separated).

    Returns:
        {"proceed": True/False, "modifications": {...}, "blocked_by": str|None}
    """
    if enabled is None:
        env_middleware = os.environ.get("AUTOLOOP_MIDDLEWARE", "")
        if env_middleware:
            enabled = [m.strip() for m in env_middleware.split(",") if m.strip()]
        else:
            enabled = list(MIDDLEWARE_REGISTRY.keys())

    all_modifications = {}
    for name in enabled:
        mw = MIDDLEWARE_REGISTRY.get(name)
        if mw:
            result = mw(phase, state, work_dir)
            if not result.get("proceed", True):
                return {
                    "proceed": False,
                    "blocked_by": name,
                    "modifications": all_modifications,
                }
            all_modifications.update(result.get("modifications", {}))

    return {"proceed": True, "blocked_by": None, "modifications": all_modifications}


def _log_evaluator_event(work_dir, event_type, details):
    """Record an evaluation event."""
    log_dir = os.path.join(work_dir, ".autoloop")
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "evaluator-events.jsonl")
    entry = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "event": event_type,
        "details": details,
    }
    with open(log_file, "a") as f:
        f.write(json.dumps(entry) + "\n")


if __name__ == "__main__":
    print(__doc__)
    print("\nRegistered middleware:", list(MIDDLEWARE_REGISTRY.keys()))
