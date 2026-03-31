"""Evaluator Audit Middleware — 评分准确性追踪

P1-05 Phase 2 的独立模块：追踪 autoloop-score.py 的评分准确性，
检测评分膨胀/漂移，为评分校准提供数据支撑。

当前为文档+接口定义，实际逻辑仍在 autoloop-controller.py 中。

对应 controller.py 中的逻辑：
- _metadata_append_audit_structured()  → EvaluatorAuditMiddleware.on_score
- VERIFY 阶段的评分记录            → EvaluatorAuditMiddleware.on_score
- metadata.audit[] 中的评分事件     → EvaluatorAuditMiddleware 内部存储

未来扩展方向：
- 交付后问题追踪（post_delivery_issue）反馈评分偏差
- 评分膨胀检测（连续多轮评分单调递增但无实质改进）
- 跨任务评分一致性比较
"""


class EvaluatorAuditMiddleware:
    """评估审计 Middleware

    职责：
    - 记录每次评分事件（维度、分数、轮次）
    - 记录人工覆写事件（原始分数 vs 覆写分数）
    - 追踪交付后问题（评分通过但实际存在问题）
    - 计算评分准确率

    接口：
    - on_score(round_num, dimension, score, max_score, gate_passed) -> None
    - on_override(round_num, dimension, original_score, override_score, reason) -> None
    - on_post_delivery_issue(task_id, dimension, expected_score, actual_quality) -> None
    - get_accuracy() -> dict
    """

    def __init__(self):
        """初始化评估审计 Middleware。"""
        self._score_events: list[dict] = []
        self._overrides: list[dict] = []
        self._post_delivery_issues: list[dict] = []

    def on_score(
        self,
        round_num: int,
        dimension: str,
        score: float,
        max_score: float,
        gate_passed: bool,
    ) -> None:
        """评分事件发生时调用。

        Args:
            round_num: 当前轮次
            dimension: 评分维度（如 "completeness", "accuracy"）
            score: 实际得分
            max_score: 该维度满分
            gate_passed: 是否通过门禁阈值
        """
        pass  # 未来从 controller VERIFY 阶段迁移

    def on_override(
        self,
        round_num: int,
        dimension: str,
        original_score: float,
        override_score: float,
        reason: str,
    ) -> None:
        """人工覆写评分时调用。

        Args:
            round_num: 当前轮次
            dimension: 评分维度
            original_score: 系统评分
            override_score: 人工覆写分数
            reason: 覆写原因
        """
        pass  # 未来扩展

    def on_post_delivery_issue(
        self,
        task_id: str,
        dimension: str,
        expected_score: float,
        actual_quality: str,
    ) -> None:
        """交付后发现问题时调用（用于校准评分准确性）。

        Args:
            task_id: 任务标识
            dimension: 出问题的维度
            expected_score: 评分系统给出的分数
            actual_quality: 实际质量描述（"pass"/"fail"/"partial"）
        """
        pass  # 未来扩展

    def get_accuracy(self) -> dict:
        """计算评分准确率。

        Returns:
            {
                "total_scores": int,
                "overrides": int,
                "override_rate": float,        # 覆写率
                "post_delivery_issues": int,
                "false_positive_rate": float,  # 评分通过但实际有问题的比率
                "per_dimension": {
                    "dimension_name": {
                        "avg_score": float,
                        "override_count": int,
                        "issue_count": int,
                    }
                },
            }
        """
        return {
            "total_scores": len(self._score_events),
            "overrides": len(self._overrides),
            "override_rate": 0.0,
            "post_delivery_issues": len(self._post_delivery_issues),
            "false_positive_rate": 0.0,
            "per_dimension": {},
        }

    def __call__(self, phase: str, state: dict, work_dir: str, **kwargs) -> dict:
        """统一 Middleware 接口。

        仅在 VERIFY 阶段后激活，其他阶段直通。

        Returns:
            {"proceed": True, "modifications": {}}
        """
        return {"proceed": True, "modifications": {}}
