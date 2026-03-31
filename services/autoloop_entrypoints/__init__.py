"""Console entry points: run bundled ``scripts/*.py`` via subprocess (path from autoloop_scripts.locate)."""

from __future__ import annotations

import subprocess
import sys

from autoloop_scripts.locate import scripts_directory


def _run(script: str) -> int:
    target = scripts_directory() / script
    if not target.is_file():
        print("ERROR: 脚本不存在: {}".format(target), file=sys.stderr)
        return 127
    cmd = [sys.executable, str(target), *sys.argv[1:]]
    return subprocess.call(cmd)


def main_state() -> None:
    raise SystemExit(_run("autoloop-state.py"))


def main_validate() -> None:
    raise SystemExit(_run("autoloop-validate.py"))


def main_score() -> None:
    raise SystemExit(_run("autoloop-score.py"))


def main_controller() -> None:
    raise SystemExit(_run("autoloop-controller.py"))


def main_render() -> None:
    raise SystemExit(_run("autoloop-render.py"))


def main_init() -> None:
    raise SystemExit(_run("autoloop-init.py"))


def main_experience() -> None:
    raise SystemExit(_run("autoloop-experience.py"))


def main_finalize() -> None:
    raise SystemExit(_run("autoloop-finalize.py"))


def main_tsv() -> None:
    raise SystemExit(_run("autoloop-tsv.py"))


def main_variance() -> None:
    raise SystemExit(_run("autoloop-variance.py"))
