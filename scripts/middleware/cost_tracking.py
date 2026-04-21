"""Cost Tracking Middleware — cost tracking and budget management

Reference implementation for the cost/budget logic extracted from controller.py.
This file currently provides docs and interface definitions; the real logic still lives in autoloop-controller.py.

Corresponding controller.py functions/logic:
- print_cost_summary(state)              → CostTrackingMiddleware.get_summary
- plan.budget.max_rounds / current_round → internal state in CostTrackingMiddleware
- get_max_rounds() / get_current_round() → CostTrackingMiddleware.remaining_budget_pct

Future extension directions:
- Track token usage for each subagent (separate input/output counts)
- Bill by model (different providers, different prices)
- Write cumulative cost to metadata.json for cross-task analysis
"""


class CostTrackingMiddleware:
    """Cost-tracking middleware.

    Responsibilities:
    - Record token usage and cost for each subagent call
    - Compute cumulative cost and remaining budget percentage
    - Warn when budget is exhausted (without blocking the pipeline)
    - Produce a cost summary report

    Interface:
    - on_subagent_start(subagent_id, model, task_type) -> None
    - on_subagent_end(subagent_id, tokens_in, tokens_out, cost_usd) -> None
    - get_summary() -> dict
    - remaining_budget_pct() -> float
    """

    def __init__(self, max_rounds: int = 0, warn_threshold: float = 0.2):
        """Initialize the cost-tracking middleware.

        Args:
            max_rounds: maximum round budget (0 = read default from manifest)
            warn_threshold: warn when remaining budget falls below this ratio (0.0-1.0)
        """
        self.max_rounds = max_rounds
        self.warn_threshold = warn_threshold
        self._records: list[dict] = []

    def on_subagent_start(self, subagent_id: str, model: str, task_type: str) -> None:
        """Called when a subagent starts.

        Args:
            subagent_id: subagent identifier (e.g. "round_2_act_1")
            model: model name in use (e.g. "claude-sonnet-4-20250514")
            task_type: task type (e.g. "research", "coding")
        """
        pass  # Future migration from controller.phase_act()

    def on_subagent_end(
        self,
        subagent_id: str,
        tokens_in: int = 0,
        tokens_out: int = 0,
        cost_usd: float = 0.0,
    ) -> None:
        """Called when a subagent finishes.

        Args:
            subagent_id: subagent identifier
            tokens_in: input token count
            tokens_out: output token count
            cost_usd: cost of this call (USD)
        """
        pass  # Future migration from controller

    def get_summary(self) -> dict:
        """Return a cost summary.

        Returns:
            {
                "total_rounds": int,
                "total_subagent_calls": int,
                "total_tokens_in": int,
                "total_tokens_out": int,
                "total_cost_usd": float,
                "cost_per_round": list[float],
            }
        """
        return {
            "total_rounds": 0,
            "total_subagent_calls": len(self._records),
            "total_tokens_in": 0,
            "total_tokens_out": 0,
            "total_cost_usd": 0.0,
            "cost_per_round": [],
        }

    def remaining_budget_pct(self, current_round: int) -> float:
        """Compute the remaining budget percentage.

        Args:
            current_round: current round

        Returns:
            Remaining budget ratio (0.0 - 1.0); returns 1.0 when max_rounds=0
        """
        if self.max_rounds <= 0:
            return 1.0
        return max(0.0, 1.0 - current_round / self.max_rounds)

    def __call__(self, phase: str, state: dict, work_dir: str, **kwargs) -> dict:
        """Unified middleware interface.

        Returns:
            {"proceed": True, "modifications": {}}
            Cost middleware never blocks the pipeline (warnings only).
        """
        return {"proceed": True, "modifications": {}}
