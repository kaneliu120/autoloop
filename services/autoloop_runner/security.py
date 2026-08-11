"""Security boundaries shared by the unattended Runner.

The Runner calls a model and may later execute an allowlisted command.  Keep
the model-facing network configuration and child-process environment narrow so
that a bad handoff cannot silently inherit credentials or redirect them to an
unreviewed endpoint.
"""

from __future__ import annotations

import os
import re
from collections.abc import Mapping
from urllib.parse import urlparse


_TRUE_VALUES = frozenset({"1", "true", "yes", "on"})
_SENSITIVE_ENV_PARTS = frozenset(
    {"API", "KEY", "TOKEN", "SECRET", "PASSWORD", "CREDENTIAL", "CREDENTIALS", "PRIVATE"}
)
_ALLOWED_OPENAI_HOSTS = ("api.openai.com",)


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
    }


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
