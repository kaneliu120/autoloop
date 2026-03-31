"""Resolve the directory containing autoloop-*.py tools (wheel, editable, or env override)."""

from __future__ import annotations

import os
from pathlib import Path

_MARKER = "autoloop-state.py"


def scripts_directory() -> Path:
    """Return the directory that contains ``autoloop-state.py`` and sibling tools.

    Resolution order:
    1. ``AUTOLOOP_SCRIPTS_DIR`` if set and valid
    2. ``<package>/bundled`` when shipped in the wheel (symlink to ``scripts/`` in dev)
    3. Walk parents from this file to find a ``scripts/`` directory (editable/git checkout)
    """
    raw = (os.environ.get("AUTOLOOP_SCRIPTS_DIR") or "").strip()
    if raw:
        p = Path(raw).expanduser().resolve()
        if (p / _MARKER).is_file():
            return p
    here = Path(__file__).resolve().parent
    bundled = here / "bundled"
    if bundled.is_dir() and (bundled / _MARKER).is_file():
        return bundled.resolve()
    for parent in (here, *here.parents):
        cand = parent / "scripts"
        if (cand / _MARKER).is_file():
            return cand.resolve()
    raise RuntimeError(
        "AutoLoop scripts directory not found. Install the autoloop package, run from a "
        "checkout, or set AUTOLOOP_SCRIPTS_DIR to the directory containing autoloop-state.py."
    )
