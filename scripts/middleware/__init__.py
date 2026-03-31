"""AutoLoop Middleware — 横切关注点独立模块

每个 Middleware 模块负责一个横切关注点，可独立启用/禁用/替换。
OODA 8阶段管道保持不变，Middleware 在管道外围处理跨阶段逻辑。

架构参考：
- OpenAI Symphony: 6层分离 (Policy/Config/Coordination/Execution/Integration/Observability)
- LangChain Deep Agents: Middleware Stack (TodoList/Filesystem/SubAgent/Memory/Summarization)

当前模块：
- logging_mw: 结构化日志和进度写入
- cost_tracking: 成本追踪和预算管理
- evaluator_audit: 评分准确性追踪（P1-05 Phase 2）
- failure_classification: 失败类型分类和恢复策略（P2-12 扩展）

Middleware 接口约定（所有模块统一）：

    def __call__(phase: str, state: dict, work_dir: str, **kwargs) -> dict:
        返回 {"proceed": True/False, "modifications": {...}}

    - proceed=False 时中断 Middleware 链，返回 blocked_by 标识
    - modifications 中的键值会被 controller 应用到 state（点号分隔路径表示嵌套）
    - 通过 AUTOLOOP_MIDDLEWARE 环境变量启用/禁用（逗号分隔列表）
"""

from .logging_mw import LoggingMiddleware
from .cost_tracking import CostTrackingMiddleware
from .evaluator_audit import EvaluatorAuditMiddleware
from .failure_classification import FailureClassificationMiddleware

__all__ = [
    "LoggingMiddleware",
    "CostTrackingMiddleware",
    "EvaluatorAuditMiddleware",
    "FailureClassificationMiddleware",
]
