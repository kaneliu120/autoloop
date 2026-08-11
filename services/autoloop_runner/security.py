"""Security boundaries shared by the unattended Runner.

The Runner calls a model and may later execute an allowlisted command.  Keep
the model-facing network configuration and child-process environment narrow so
that a bad handoff cannot silently inherit credentials or redirect them to an
unreviewed endpoint.
"""

from __future__ import annotations

import json
import os
import re
from collections.abc import Mapping
from pathlib import Path
from urllib.parse import urlparse


_TRUE_VALUES = frozenset({"1", "true", "yes", "on"})
_SENSITIVE_ENV_PARTS = frozenset(
    {"API", "KEY", "TOKEN", "SECRET", "PASSWORD", "CREDENTIAL", "CREDENTIALS", "PRIVATE"}
)
_ALLOWED_OPENAI_HOSTS = ("api.openai.com",)
RUNNER_WORKDIR_ROOT_ENV = "AUTOLOOP_RUNNER_WORKDIR_ROOT"
RUNNER_ALLOWED_COMMANDS_ENV = "AUTOLOOP_RUNNER_ALLOWED_COMMANDS_JSON"


def _is_true(value: object) -> bool:
    return str(value or "").strip().lower() in _TRUE_VALUES


def is_sensitive_environment_variable(name: str) -> bool:
    """Recognize common credential variable names without logging their values."""
    parts = {part for part in re.split(r"_+", str(name).upper()) if part}
    return bool(parts & _SENSITIVE_ENV_PARTS)


def sanitized_child_environment(
    environ: Mapping[str, str] | None = None,
    additions: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Return an environment for planned subprocesses with credentials removed.

    Planned commands do not need the Runner's API credentials.  Callers that
    intentionally need another credential must launch that operation outside
    the model-generated command path.
    """
    merged = dict(os.environ if environ is None else environ)
    if additions:
        merged.update(additions)
    return {
        str(key): str(value)
        for key, value in merged.items()
        if not is_sensitive_environment_variable(str(key))
        and str(key) != RUNNER_ALLOWED_COMMANDS_ENV
    }


def resolve_trusted_work_dir(
    work_dir: str,
    environ: Mapping[str, str] | None = None,
    *,
    root_env: str = RUNNER_WORKDIR_ROOT_ENV,
) -> str:
    """Resolve a Runner work directory and require it to stay under an operator root.

    The Runner executes model-proposed commands and writes task state.  It must
    not accept an arbitrary path from a task or an orchestration layer.  The
    configured root is intentionally process-level policy, not task-state
    configuration that a model can later modify.
    """
    env = os.environ if environ is None else environ
    raw_root = str(env.get(root_env, "") or "").strip()
    if not raw_root:
        raise ValueError(
            f"{root_env} must name the directory containing trusted task workdirs"
        )

    root = Path(raw_root).expanduser().resolve(strict=False)
    if not root.is_dir():
        raise ValueError(f"{root_env} is not an existing directory: {root}")

    candidate = Path(work_dir).expanduser().resolve(strict=False)
    if not candidate.is_dir():
        raise ValueError(f"work_dir is not an existing directory: {candidate}")
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ValueError(
            f"work_dir must be inside {root_env}: {root}"
        ) from exc
    return str(candidate)


def resolve_runner_command_patterns(
    default_patterns: list[str],
    environ: Mapping[str, str] | None = None,
) -> list[str]:
    """Return an operator-owned command policy, never a task-state policy.

    A custom policy is a JSON string array in the Runner process environment.
    It is deliberately excluded from child processes and cannot be changed by
    a model through ``autoloop-state.py update``.
    """
    env = os.environ if environ is None else environ
    raw = str(env.get(RUNNER_ALLOWED_COMMANDS_ENV, "") or "").strip()
    if not raw:
        return list(default_patterns)

    try:
        patterns = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"{RUNNER_ALLOWED_COMMANDS_ENV} must be a JSON string array"
        ) from exc
    if not isinstance(patterns, list) or not patterns:
        raise ValueError(
            f"{RUNNER_ALLOWED_COMMANDS_ENV} must be a non-empty JSON string array"
        )

    cleaned: list[str] = []
    for value in patterns:
        pattern = str(value or "").strip()
        if not pattern or pattern == "*" or "\x00" in pattern:
            raise ValueError("Runner command policy contains an unsafe pattern")
        cleaned.append(pattern)
    return cleaned


def resolve_openai_base_url(environ: Mapping[str, str] | None = None) -> str | None:
    """Validate an optional OpenAI-compatible base URL before sending an API key.

    OpenAI and Azure OpenAI endpoints are accepted by default.  A different
    endpoint needs an explicit operator opt-in because the OpenAI client sends
    the API key to the configured host.
    """
    env = os.environ if environ is None else environ
    raw = str(env.get("OPENAI_BASE_URL", "") or "").strip()
    if not raw:
        return None

    parsed = urlparse(raw)
    host = (parsed.hostname or "").lower()
    if (
        parsed.scheme != "https"
        or not host
        or parsed.username is not None
        or parsed.password is not None
    ):
        raise ValueError("OPENAI_BASE_URL must be an HTTPS URL without embedded credentials")

    if host in _ALLOWED_OPENAI_HOSTS or host.endswith(".openai.azure.com"):
        return raw
    if _is_true(env.get("AUTOLOOP_ALLOW_CUSTOM_OPENAI_BASE_URL")):
        return raw
    raise ValueError(
        "OPENAI_BASE_URL is not an OpenAI or Azure OpenAI endpoint; set "
        "AUTOLOOP_ALLOW_CUSTOM_OPENAI_BASE_URL=1 only after reviewing that host"
    )
