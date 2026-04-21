"""Logging Middleware — structured logging and progress writing

Reference implementation for the logging-related logic extracted from controller.py.
This file currently provides docs and interface definitions; the real logic still lives in autoloop-controller.py.
During the next refactor, controller calls to info()/warn()/error() will be replaced with this module.

Corresponding controller.py functions:
- info(msg)          → LoggingMiddleware.on_phase_start / on_phase_end
- warn(msg)          → LoggingMiddleware.on_error
- banner()           → LoggingMiddleware.on_phase_start (structured replacement)
- prompt_block()     → LoggingMiddleware.on_action_required
- progress.md writes → LoggingMiddleware.write_progress
"""


class LoggingMiddleware:
    """Structured logging middleware.

    Responsibilities:
    - Log the start/end of each OODA phase
    - Append to progress.md automatically
    - Emit structured JSON logs (optional)
    - Record metadata.audit[] log events

    Interface:
    - on_phase_start(phase_name, state) -> None
    - on_phase_end(phase_name, state, result) -> None
    - on_error(phase_name, error) -> None
    - on_action_required(title, content) -> None
    - write_progress(work_dir, entry) -> None
    """

    def __init__(self, log_level="info", json_output=False):
        """Initialize the logging middleware.

        Args:
            log_level: log level ("debug", "info", "warn", "error")
            json_output: whether to emit structured JSON logs (for machine parsing)
        """
        self.log_level = log_level
        self.json_output = json_output

    def on_phase_start(self, phase_name: str, state: dict) -> None:
        """Called when an OODA phase starts.

        Args:
            phase_name: phase name (OBSERVE/ORIENT/DECIDE/ACT/VERIFY/SYNTHESIZE/EVOLVE/REFLECT)
            state: current state.json contents
        """
        pass  # Future migration from controller.banner() + info()

    def on_phase_end(self, phase_name: str, state: dict, result: dict) -> None:
        """Called when an OODA phase ends.

        Args:
            phase_name: phase name
            state: current state.json contents
            result: phase execution result (phase-specific dict)
        """
        pass  # Future migration from the tail-end logging in controller phase_* functions

    def on_error(self, phase_name: str, error: str) -> None:
        """Called when a phase errors.

        Args:
            phase_name: phase name where the error occurred
            error: error description
        """
        pass  # Future migration from controller.error() + warn()

    def on_action_required(self, title: str, content: str) -> None:
        """Called when LLM or user action is required.

        Args:
            title: action title
            content: detailed action content
        """
        pass  # Future migration from controller.prompt_block()

    def write_progress(self, work_dir: str, entry: str) -> None:
        """Append a progress entry to progress.md.

        Args:
            work_dir: work directory path
            entry: progress entry text (Markdown format)
        """
        pass  # Future migration from the scattered progress.md writing logic in controller

    def __call__(self, phase: str, state: dict, work_dir: str, **kwargs) -> dict:
        """Unified middleware interface.

        Returns:
            {"proceed": True, "modifications": {}}
            Logging middleware never blocks the pipeline.
        """
        self.on_phase_start(phase, state)
        return {"proceed": True, "modifications": {}}
