"""Logging Middleware — 结构化日志和进度写入

从 controller.py 中抽离的日志相关逻辑的参考实现。
当前为文档+接口定义，实际逻辑仍在 autoloop-controller.py 中。
未来重构时将 controller 中的 info()/warn()/error() 调用替换为此模块。

对应 controller.py 中的函数：
- info(msg)          → LoggingMiddleware.on_phase_start / on_phase_end
- warn(msg)          → LoggingMiddleware.on_error
- banner()           → LoggingMiddleware.on_phase_start (结构化替代)
- prompt_block()     → LoggingMiddleware.on_action_required
- progress.md 写入   → LoggingMiddleware.write_progress
"""


class LoggingMiddleware:
    """结构化日志 Middleware

    职责：
    - 每个 OODA 阶段的开始/结束日志
    - progress.md 的自动追加
    - 结构化 JSON 日志输出（可选）
    - metadata.audit[] 日志事件记录

    接口：
    - on_phase_start(phase_name, state) -> None
    - on_phase_end(phase_name, state, result) -> None
    - on_error(phase_name, error) -> None
    - on_action_required(title, content) -> None
    - write_progress(work_dir, entry) -> None
    """

    def __init__(self, log_level="info", json_output=False):
        """初始化日志 Middleware。

        Args:
            log_level: 日志级别 ("debug", "info", "warn", "error")
            json_output: 是否输出结构化 JSON 日志（用于机器解析）
        """
        self.log_level = log_level
        self.json_output = json_output

    def on_phase_start(self, phase_name: str, state: dict) -> None:
        """OODA 阶段开始时调用。

        Args:
            phase_name: 阶段名 (OBSERVE/ORIENT/DECIDE/ACT/VERIFY/SYNTHESIZE/EVOLVE/REFLECT)
            state: 当前 state.json 内容
        """
        pass  # 未来从 controller.banner() + info() 迁移

    def on_phase_end(self, phase_name: str, state: dict, result: dict) -> None:
        """OODA 阶段结束时调用。

        Args:
            phase_name: 阶段名
            state: 当前 state.json 内容
            result: 阶段执行结果（阶段特定字典）
        """
        pass  # 未来从 controller 各 phase_* 函数末尾日志迁移

    def on_error(self, phase_name: str, error: str) -> None:
        """阶段错误时调用。

        Args:
            phase_name: 发生错误的阶段名
            error: 错误描述
        """
        pass  # 未来从 controller.error() + warn() 迁移

    def on_action_required(self, title: str, content: str) -> None:
        """需要 LLM/用户操作时调用。

        Args:
            title: 操作标题
            content: 操作详细内容
        """
        pass  # 未来从 controller.prompt_block() 迁移

    def write_progress(self, work_dir: str, entry: str) -> None:
        """向 progress.md 追加进度条目。

        Args:
            work_dir: 工作目录路径
            entry: 进度条目文本（Markdown 格式）
        """
        pass  # 未来从 controller 中散布的 progress.md 写入逻辑迁移

    def __call__(self, phase: str, state: dict, work_dir: str, **kwargs) -> dict:
        """统一 Middleware 接口。

        Returns:
            {"proceed": True, "modifications": {}}
            日志 Middleware 永远不阻断管道。
        """
        self.on_phase_start(phase, state)
        return {"proceed": True, "modifications": {}}
