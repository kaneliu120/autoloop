"""Failure Classification Middleware — failure typing and recovery strategies

Reference implementation for failure classification and recovery logic extracted from controller.py.
This file currently provides docs and interface definitions; the real logic still lives in autoloop-controller.py.

Corresponding controller.py functions/constants:
- FAILURE_TYPES               → FailureClassificationMiddleware.FAILURE_TYPES
- RECOVERY_STRATEGIES         → FailureClassificationMiddleware.RECOVERY_STRATEGIES
- classify_failure()          → FailureClassificationMiddleware.classify
- log_act_failure()           → FailureClassificationMiddleware.log_failure
- process_act_completion()    → FailureClassificationMiddleware (partial)

Future extension directions (P2-12):
- Failure-pattern statistics (which failures occur most often)
- Adaptive recovery strategies (adjust based on historical success rate)
- Failure-chain detection (consecutive same-type failures → escalation)
"""

# Failure type enum (matches controller.py FAILURE_TYPES)
FAILURE_TYPES = {
    "timeout": "execution timed out",
    "capability_gap": "model capability gap",
    "resource_missing": "required resource missing",
    "external_error": "external service error (API/network)",
    "code_error": "code/script error",
    "partial_success": "partial success",
}

# Recovery strategy mapping (matches controller.py RECOVERY_STRATEGIES)
RECOVERY_STRATEGIES = {
    "timeout": "retry with a narrower scope",
    "capability_gap": "switch strategy or lower the target",
    "resource_missing": "search for alternative resources",
    "external_error": "wait and retry (exponential backoff)",
    "code_error": "log a bug and retry after fixing it",
    "partial_success": "continue from the checkpoint (keep the completed part)",
}


class FailureClassificationMiddleware:
    """Failure-classification middleware.

    Responsibilities:
    - Automatically classify failures from error text
    - Provide a matching recovery strategy
    - Record failure events for analysis
    - Detect failure chains (consecutive same-type failures)

    Interface:
    - classify(error_msg, exit_code) -> str
    - get_recovery_strategy(failure_type) -> str
    - log_failure(work_dir, state, failure_type, detail, completion_ratio) -> None
    - get_failure_stats() -> dict
    """

    def __init__(self, escalation_threshold: int = 3):
        """Initialize the failure-classification middleware.

        Args:
            escalation_threshold: trigger escalation when consecutive same-type failures exceed this count
        """
        self.escalation_threshold = escalation_threshold
        self._failure_log: list[dict] = []

    def classify(self, error_msg: str, exit_code: int | None = None) -> str:
        """Automatically classify a failure from error text.

        Matches controller.py classify_failure() logic:
        - exit_code 124 → timeout
        - keyword match → corresponding type
        - default → capability_gap

        Args:
            error_msg: error message text
            exit_code: process exit code (optional)

        Returns:
            failure type string (one of FAILURE_TYPES keys)
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
        """Return the recovery strategy for a failure type.

        Args:
            failure_type: failure type (one of FAILURE_TYPES keys)

        Returns:
            recovery strategy description text
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
        """Record a failure event.

        Args:
            work_dir: work directory path
            state: current state.json contents
            failure_type: failure type
            detail: error details
            completion_ratio: completion ratio (0-100)
        """
        pass  # Future migration from controller.log_act_failure()

    def get_failure_stats(self) -> dict:
        """Return failure statistics.

        Returns:
            {
                "total_failures": int,
                "by_type": {"timeout": int, "capability_gap": int, ...},
                "consecutive_same_type": int,  # current consecutive same-type failures
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
        """Unified middleware interface.

        Enabled only after the ACT phase; all other phases pass through.

        Returns:
            {"proceed": True, "modifications": {}}
        """
        return {"proceed": True, "modifications": {}}
