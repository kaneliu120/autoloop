"""Scripts path for runner (same resolution as console entry points)."""

from __future__ import annotations

from pathlib import Path

from autoloop_scripts.locate import scripts_directory


def scripts_dir() -> Path:
    return scripts_directory()
