"""OpenAI Chat Completions：JSON 输出、429/5xx 退避（实施手册 §6）。"""

from __future__ import annotations

import json
import random
import re
import time
from typing import Any


def _extract_json_object(text: str) -> dict[str, Any]:
    text = (text or "").strip()
    m = re.search(r"\{[\s\S]*\}\s*$", text)
    if m:
        text = m.group(0)
    return json.loads(text)


def chat_json(
    *,
    system: str,
    user: str,
    model: str,
    api_key: str,
    base_url: str | None,
    timeout: float = 120.0,
    max_tokens: int = 2048,
    temperature: float = 0.3,
    max_retries: int = 5,
) -> tuple[dict[str, Any], dict[str, Any]]:
    try:
        from openai import OpenAI
    except ImportError as e:
        raise RuntimeError(
            "需要安装 openai 包: pip install 'autoloop[runner]'"
        ) from e

    client = OpenAI(api_key=api_key, base_url=base_url, timeout=timeout)
    delay = 1.0
    last_err: Exception | None = None
    for attempt in range(max_retries):
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                max_tokens=max_tokens,
                temperature=temperature,
                response_format={"type": "json_object"},
            )
            choice = resp.choices[0].message.content or "{}"
            usage: dict[str, Any] = {"model": model}
            u = getattr(resp, "usage", None)
            if u is not None:
                usage["prompt_tokens"] = int(getattr(u, "prompt_tokens", 0) or 0)
                usage["completion_tokens"] = int(
                    getattr(u, "completion_tokens", 0) or 0
                )
            rid = getattr(resp, "id", None)
            if rid:
                usage["request_id"] = str(rid)
            return _extract_json_object(choice), usage
        except Exception as e:
            last_err = e
            msg = str(e).lower()
            retriable = (
                "429" in msg
                or "rate" in msg
                or "timeout" in msg
                or "503" in msg
                or "502" in msg
                or "500" in msg
            )
            if not retriable or attempt == max_retries - 1:
                raise
            time.sleep(delay + random.uniform(0, 0.5))
            delay = min(delay * 2, 60.0)
    raise last_err  # pragma: no cover
