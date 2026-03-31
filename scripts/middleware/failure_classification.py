"""Failure Classification Middleware — 失败类型分类和恢复策略

从 controller.py 中抽离的失败分类和恢复逻辑的参考实现。
当前为文档+接口定义，实际逻辑仍在 autoloop-controller.py 中。

对应 controller.py 中的函数/常量：
- FAILURE_TYPES               → FailureClassificationMiddleware.FAILURE_TYPES
- RECOVERY_STRATEGIES         → FailureClassificationMiddleware.RECOVERY_STRATEGIES
- classify_failure()          → FailureClassificationMiddleware.classify
- log_act_failure()           → FailureClassificationMiddleware.log_failure
- process_act_completion()    → FailureClassificationMiddleware（部分）

未来扩展方向（P2-12）：
- 失败模式统计（哪类失败最频繁）
- 自适应恢复策略（根据历史成功率调整）
- 失败链检测（连续同类失败 → 升级处理）
"""

# 失败类型枚举（与 controller.py FAILURE_TYPES 一致）
FAILURE_TYPES = {
    "timeout": "执行超时",
    "capability_gap": "模型能力不足",
    "resource_missing": "所需资源不存在",
    "external_error": "外部服务错误（API/网络）",
    "code_error": "代码/脚本错误",
    "partial_success": "部分完成",
}

# 恢复策略映射（与 controller.py RECOVERY_STRATEGIES 一致）
RECOVERY_STRATEGIES = {
    "timeout": "缩小范围后重试",
    "capability_gap": "切换策略或降级目标",
    "resource_missing": "搜索替代资源",
    "external_error": "等待后重试（指数退避）",
    "code_error": "记录 bug，修复后重试",
    "partial_success": "从断点继续（保留已完成部分）",
}


class FailureClassificationMiddleware:
    """失败分类 Middleware

    职责：
    - 根据错误信息自动分类失败类型
    - 提供对应的恢复策略
    - 记录失败事件用于统计分析
    - 检测失败链（连续同类失败）

    接口：
    - classify(error_msg, exit_code) -> str
    - get_recovery_strategy(failure_type) -> str
    - log_failure(work_dir, state, failure_type, detail, completion_ratio) -> None
    - get_failure_stats() -> dict
    """

    def __init__(self, escalation_threshold: int = 3):
        """初始化失败分类 Middleware。

        Args:
            escalation_threshold: 连续同类失败超过此次数时触发升级处理
        """
        self.escalation_threshold = escalation_threshold
        self._failure_log: list[dict] = []

    def classify(self, error_msg: str, exit_code: int | None = None) -> str:
        """根据错误信息自动分类失败类型。

        与 controller.py classify_failure() 逻辑一致：
        - exit_code 124 → timeout
        - 关键词匹配 → 对应类型
        - 默认 → capability_gap

        Args:
            error_msg: 错误信息文本
            exit_code: 进程退出码（可选）

        Returns:
            失败类型字符串（FAILURE_TYPES 的键之一）
        """
        if exit_code and exit_code == 124:
            return "timeout"
        error_lower = (error_msg or "").lower()
        if any(k in error_lower for k in ("timeout", "timed out", "context limit")):
            return "timeout"
        if any(k in error_lower for k in ("rate limit", "429", "503", "network")):
            return "external_error"
        if any(k in error_lower for k in ("traceback", "syntax error", "import error")):
            return "code_error"
        if any(k in error_lower for k in ("not found", "permission denied", "no such file")):
            return "resource_missing"
        return "capability_gap"

    def get_recovery_strategy(self, failure_type: str) -> str:
        """根据失败类型返回恢复策略。

        Args:
            failure_type: 失败类型（FAILURE_TYPES 的键之一）

        Returns:
            恢复策略描述文本
        """
        return RECOVERY_STRATEGIES.get(failure_type, RECOVERY_STRATEGIES["capability_gap"])

    def log_failure(
        self,
        work_dir: str,
        state: dict,
        failure_type: str,
        detail: str = "",
        completion_ratio: int = 0,
    ) -> None:
        """记录失败事件。

        Args:
            work_dir: 工作目录路径
            state: 当前 state.json 内容
            failure_type: 失败类型
            detail: 错误详情
            completion_ratio: 完成比例 (0-100)
        """
        pass  # 未来从 controller.log_act_failure() 迁移

    def get_failure_stats(self) -> dict:
        """返回失败统计。

        Returns:
            {
                "total_failures": int,
                "by_type": {"timeout": int, "capability_gap": int, ...},
                "consecutive_same_type": int,  # 当前连续同类失败次数
                "escalation_triggered": bool,
            }
        """
        return {
            "total_failures": len(self._failure_log),
            "by_type": {},
            "consecutive_same_type": 0,
            "escalation_triggered": False,
        }

    def __call__(self, phase: str, state: dict, work_dir: str, **kwargs) -> dict:
        """统一 Middleware 接口。

        仅在 ACT 阶段后激活，其他阶段直通。

        Returns:
            {"proceed": True, "modifications": {}}
        """
        return {"proceed": True, "modifications": {}}
