"""Cost Tracking Middleware — 成本追踪和预算管理

从 controller.py 中抽离的成本/预算相关逻辑的参考实现。
当前为文档+接口定义，实际逻辑仍在 autoloop-controller.py 中。

对应 controller.py 中的函数/逻辑：
- print_cost_summary(state)              → CostTrackingMiddleware.get_summary
- plan.budget.max_rounds / current_round → CostTrackingMiddleware 内部状态
- get_max_rounds() / get_current_round() → CostTrackingMiddleware.remaining_budget_pct

未来扩展方向：
- 每个 subagent 的 token 用量追踪（输入/输出分开计）
- 按模型计费（不同 provider 不同单价）
- 累计成本写入 metadata.json 用于跨任务分析
"""


class CostTrackingMiddleware:
    """成本追踪 Middleware

    职责：
    - 记录每个 subagent 调用的 token 用量和成本
    - 计算累计成本和剩余预算百分比
    - 预算耗尽时发出警告（不阻断管道）
    - 生成成本摘要报告

    接口：
    - on_subagent_start(subagent_id, model, task_type) -> None
    - on_subagent_end(subagent_id, tokens_in, tokens_out, cost_usd) -> None
    - get_summary() -> dict
    - remaining_budget_pct() -> float
    """

    def __init__(self, max_rounds: int = 0, warn_threshold: float = 0.2):
        """初始化成本追踪 Middleware。

        Args:
            max_rounds: 最大轮次预算（0 = 从 manifest 读取默认值）
            warn_threshold: 剩余预算低于此比例时发出警告 (0.0-1.0)
        """
        self.max_rounds = max_rounds
        self.warn_threshold = warn_threshold
        self._records: list[dict] = []

    def on_subagent_start(self, subagent_id: str, model: str, task_type: str) -> None:
        """Subagent 开始执行时调用。

        Args:
            subagent_id: subagent 标识（如 "round_2_act_1"）
            model: 使用的模型名（如 "claude-sonnet-4-20250514"）
            task_type: 任务类型（如 "research", "coding"）
        """
        pass  # 未来从 controller.phase_act() 迁移

    def on_subagent_end(
        self,
        subagent_id: str,
        tokens_in: int = 0,
        tokens_out: int = 0,
        cost_usd: float = 0.0,
    ) -> None:
        """Subagent 执行结束时调用。

        Args:
            subagent_id: subagent 标识
            tokens_in: 输入 token 数
            tokens_out: 输出 token 数
            cost_usd: 本次调用成本（美元）
        """
        pass  # 未来从 controller 迁移

    def get_summary(self) -> dict:
        """返回成本摘要。

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
        """计算剩余预算百分比。

        Args:
            current_round: 当前轮次

        Returns:
            剩余预算比例 (0.0 - 1.0)，max_rounds=0 时返回 1.0
        """
        if self.max_rounds <= 0:
            return 1.0
        return max(0.0, 1.0 - current_round / self.max_rounds)

    def __call__(self, phase: str, state: dict, work_dir: str, **kwargs) -> dict:
        """统一 Middleware 接口。

        Returns:
            {"proceed": True, "modifications": {}}
            成本 Middleware 永远不阻断管道（仅警告）。
        """
        return {"proceed": True, "modifications": {}}
