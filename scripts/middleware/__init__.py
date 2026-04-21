"""AutoLoop Middleware — independent cross-cutting concern modules

Each middleware module owns one cross-cutting concern and can be enabled, disabled, or replaced independently.
The OODA 8-stage pipeline remains unchanged; middleware handles cross-stage logic around it.

Architecture references:
- OpenAI Symphony: 6-layer separation (Policy/Config/Coordination/Execution/Integration/Observability)
- LangChain Deep Agents: Middleware Stack (TodoList/Filesystem/SubAgent/Memory/Summarization)

Current modules:
- logging_mw: structured logging and progress writing
- cost_tracking: cost tracking and budget management
- evaluator_audit: scoring accuracy tracking (P1-05 Phase 2)
- failure_classification: failure typing and recovery strategies (P2-12 extension)

Middleware interface contract (shared by all modules):

    def __call__(phase: str, state: dict, work_dir: str, **kwargs) -> dict:
        returns {"proceed": True/False, "modifications": {...}}

    - if proceed=False, the middleware chain is interrupted and blocked_by is returned
    - key/value pairs in modifications are applied by the controller to state (dot-separated paths denote nesting)
    - enable/disable through the AUTOLOOP_MIDDLEWARE env var (comma-separated list)
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
