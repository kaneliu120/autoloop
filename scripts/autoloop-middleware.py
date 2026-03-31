#!/usr/bin/env python3
"""AutoLoop Middleware — 横切关注点模块（函数式实现）

将 controller.py 中的横切逻辑抽象为独立、可插拔的 Middleware 函数。
每个 Middleware 可独立启用/禁用，不影响核心 OODA 管道。

与 scripts/middleware/ 目录的关系：
- 本文件（autoloop-middleware.py）: 函数式实现，可独立运行和 CLI 调试，
  用于未来 controller 集成 run_middleware_chain() 调用
- scripts/middleware/: 类基接口定义（OOP），用于未来架构重构时
  替换 controller 中的内联逻辑为独立模块
- 两者是同一设计的不同实现风格，待 controller 重构（P3-08 Phase 2）时统一

当前包含：
1. LoggingMiddleware — 统一的阶段输入/输出日志
2. CostTrackingMiddleware — subagent 调用成本累加
3. EvaluatorAuditMiddleware — 评分事件记录（P1-05 扩展）
4. FailureClassificationMiddleware — ACT 失败自动分类（P2-12 扩展）
5. SecurityMiddleware — 跨平台安全检查（P3-04/05 集成）

Middleware 接口约定：
  每个 Middleware 是一个函数，签名为:
    def middleware_name(phase: str, state: dict, work_dir: str, **kwargs) -> dict:
      # 返回 {"proceed": True/False, "modifications": {...}}
"""
import os
import sys
import json
import time


def logging_middleware(phase, state, work_dir, **kwargs):
    """统一阶段日志 — 记录每个阶段的开始/结束时间和关键输入"""
    template = state.get("plan", {}).get("template", "?")
    round_num = len(state.get("plan", {}).get("iterations", []))
    timestamp = time.strftime("%Y-%m-%dT%H:%M:%S")

    log_entry = {
        "timestamp": timestamp,
        "phase": phase,
        "template": template,
        "round": round_num,
    }

    # 追加到 middleware 日志
    log_dir = os.path.join(work_dir, ".autoloop")
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "middleware.jsonl")
    with open(log_file, "a") as f:
        f.write(json.dumps(log_entry) + "\n")

    return {"proceed": True, "modifications": {}}


def cost_tracking_middleware(phase, state, work_dir, **kwargs):
    """成本追踪 — 在 ACT 阶段后累加 subagent 调用计数"""
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
    """评估审计 — 在 VERIFY 阶段后记录评分事件"""
    if phase != "VERIFY":
        return {"proceed": True, "modifications": {}}

    iterations = state.get("plan", {}).get("iterations", [])
    if not iterations:
        return {"proceed": True, "modifications": {}}

    latest = iterations[-1]
    scores = latest.get("scores", {})

    # 检测评分方差（同维度跨轮差异）
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
                    # 如果方差超过 margin 的 2 倍，记录为异常
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
    """失败分类 — 在 ACT 阶段后检查是否有未分类的失败

    注：完整的 classify_failure 逻辑在 autoloop-controller.py 中。
    此 Middleware 仅做检测和标记，不直接调用 controller 内部函数。
    未来可将 classify_failure 提取为共享模块后直接调用。
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
            # 标记需要分类，由 controller 在下一步处理
            return {
                "proceed": True,
                "modifications": {
                    "metadata.unclassified_failure": True,
                    "metadata.failure_error_preview": error_msg[:200],
                },
            }

    return {"proceed": True, "modifications": {}}


def security_middleware(phase, state, work_dir, **kwargs):
    """安全检查 — 非 Claude Code 环境中的写操作拦截"""
    platform = os.environ.get("AUTOLOOP_PLATFORM", "claude-code")
    if platform == "claude-code":
        return {"proceed": True, "modifications": {}}  # Claude Code 由宿主处理

    # 非 Claude Code 环境：检查 ACT 阶段的工具调用
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
    """执行 Middleware 链

    Args:
        phase: OODA 阶段名称 (OBSERVE, ORIENT, DECIDE, ACT, VERIFY, SYNTHESIZE, EVOLVE, REFLECT)
        state: autoloop-state.json 的内容
        work_dir: 工作目录路径
        enabled: 要启用的 middleware 名称列表，默认全部启用。
                 也可通过 AUTOLOOP_MIDDLEWARE 环境变量设置（逗号分隔）。

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
    """记录评估事件"""
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
