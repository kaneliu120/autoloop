#!/usr/bin/env python3
"""无人值守 Runner、--stop-after、文件锁（实施手册）。"""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
SERVICES = ROOT / "services"


class TestTsvAutoP2(unittest.TestCase):
    def test_needs_auto_when_impacted_empty_side_effect(self):
        try:
            from autoloop_runner import tsv_auto
        except ImportError:
            sys.path.insert(0, str(SERVICES))
            from autoloop_runner import tsv_auto

        st = {
            "plan": {
                "decide_act_handoff": {
                    "strategy_id": "S01-x",
                    "impacted_dimensions": ["syntax"],
                }
            },
            "iterations": [{"scores": {"syntax": 0}}],
            "results_tsv": [],
        }
        self.assertTrue(tsv_auto.needs_auto_tsv_row(st))
        row = tsv_auto.build_verify_tsv_row(st)
        self.assertIsNotNone(row)
        self.assertIn("跨维影响", row["side_effect"])

    def test_skip_when_side_effect_ok(self):
        try:
            from autoloop_runner import tsv_auto
        except ImportError:
            sys.path.insert(0, str(SERVICES))
            from autoloop_runner import tsv_auto

        st = {
            "plan": {
                "decide_act_handoff": {
                    "impacted_dimensions": ["syntax"],
                }
            },
            "iterations": [{"scores": {}}],
            "results_tsv": [
                {"side_effect": "跨维影响: syntax,coverage", "iteration": 1}
            ],
        }
        self.assertFalse(tsv_auto.needs_auto_tsv_row(st))

    def test_apply_auto_tsv_subprocess(self):
        try:
            from autoloop_runner.tsv_auto import apply_auto_tsv_after_verify
        except ImportError:
            sys.path.insert(0, str(SERVICES))
            from autoloop_runner.tsv_auto import apply_auto_tsv_after_verify

        env = _runner_subprocess_env()
        with tempfile.TemporaryDirectory() as td:
            td = str(Path(td).resolve())
            subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "autoloop-state.py"),
                    "init",
                    td,
                    "T1",
                    "tsv",
                ],
                cwd=ROOT,
                check=True,
                env=env,
            )
            subprocess.run(
                [sys.executable, str(SCRIPTS / "autoloop-state.py"), "add-iteration", td],
                cwd=ROOT,
                check=True,
                env=env,
            )
            st = json.loads(Path(td, "autoloop-state.json").read_text(encoding="utf-8"))
            st["plan"]["decide_act_handoff"] = {
                "strategy_id": "S01-p2",
                "hypothesis": "h",
                "planned_commands": [],
                "impacted_dimensions": ["coverage"],
            }
            st["iterations"][-1]["scores"] = {"coverage": 80}
            Path(td, "autoloop-state.json").write_text(
                json.dumps(st, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            ok, _ = apply_auto_tsv_after_verify(td, strict=True, python_exe=sys.executable)
            self.assertTrue(ok)
            st2 = json.loads(Path(td, "autoloop-state.json").read_text(encoding="utf-8"))
            self.assertTrue(len(st2.get("results_tsv", [])) >= 1)
            last = st2["results_tsv"][-1]
            self.assertIn("跨维影响", last.get("side_effect", ""))


class TestPrometheusMetrics(unittest.TestCase):
    def test_render_contains_counters(self):
        try:
            from autoloop_runner.metrics import render_prometheus_text
        except ImportError:
            sys.path.insert(0, str(SERVICES))
            from autoloop_runner.metrics import render_prometheus_text

        env = _runner_subprocess_env()
        with tempfile.TemporaryDirectory() as td:
            td = str(Path(td).resolve())
            subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "autoloop-state.py"),
                    "init",
                    td,
                    "T1",
                    "m",
                ],
                cwd=ROOT,
                check=True,
                env=env,
            )
            text = render_prometheus_text(td)
            self.assertIn("autoloop_runner_tick_slices_total", text)
            self.assertIn("autoloop_runner_api_calls_total", text)


class TestControllerStopAfter(unittest.TestCase):
    def test_stop_after_orient_updates_checkpoint(self):
        with tempfile.TemporaryDirectory() as td:
            td = str(Path(td).resolve())
            r = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "autoloop-controller.py"),
                    td,
                    "--init",
                    "--template",
                    "T1",
                    "--goal",
                    "t",
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
            self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
            r2 = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "autoloop-controller.py"),
                    td,
                    "--stop-after",
                    "ORIENT",
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
            self.assertEqual(r2.returncode, 0, r2.stderr + r2.stdout)
            cp = json.loads(Path(td, "checkpoint.json").read_text(encoding="utf-8"))
            self.assertEqual(cp.get("last_completed_phase"), "ORIENT")


class TestWorkdirLock(unittest.TestCase):
    def test_second_lock_nonblocking_fails(self):
        try:
            from autoloop_runner.lock import WorkdirLock
        except ImportError:
            sys.path.insert(0, str(SERVICES))
            from autoloop_runner.lock import WorkdirLock

        with tempfile.TemporaryDirectory() as td:
            td = str(Path(td).resolve())
            a = WorkdirLock(td)
            self.assertTrue(a.acquire(blocking=True))
            b = WorkdirLock(td)
            self.assertFalse(b.acquire(blocking=False))
            a.release()
            self.assertTrue(b.acquire(blocking=False))
            b.release()


class TestReflectValidate(unittest.TestCase):
    def test_validate_reflect_ok(self):
        try:
            from autoloop_runner.reflect import normalize_reflect, validate_reflect
        except ImportError:
            sys.path.insert(0, str(SERVICES))
            from autoloop_runner.reflect import normalize_reflect, validate_reflect

        r = normalize_reflect(
            {
                "strategy_id": "S01-a",
                "effect": "待验证",
                "score": 0,
                "dimension": "syntax",
            }
        )
        ok, _ = validate_reflect(r)
        self.assertTrue(ok)
        self.assertIsInstance(r["score"], str)

    def test_validate_reflect_bad_effect(self):
        try:
            from autoloop_runner.reflect import validate_reflect
        except ImportError:
            sys.path.insert(0, str(SERVICES))
            from autoloop_runner.reflect import validate_reflect

        ok, reason = validate_reflect(
            {
                "strategy_id": "S01-a",
                "effect": "bad",
                "score": "0",
                "dimension": "x",
            }
        )
        self.assertFalse(ok)
        self.assertIn("effect", reason)


class TestSynthesizeMinimal(unittest.TestCase):
    def test_add_finding_runner_synthesize(self):
        try:
            from autoloop_runner import synthesize
        except ImportError:
            sys.path.insert(0, str(SERVICES))
            from autoloop_runner import synthesize

        env = _runner_subprocess_env()
        with tempfile.TemporaryDirectory() as td:
            td = str(Path(td).resolve())
            subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "autoloop-state.py"),
                    "init",
                    td,
                    "T1",
                    "syn",
                ],
                cwd=ROOT,
                check=True,
                env=env,
            )
            subprocess.run(
                [sys.executable, str(SCRIPTS / "autoloop-state.py"), "add-iteration", td],
                cwd=ROOT,
                check=True,
                env=env,
            )
            ok = synthesize.synthesize_minimal(td, python_exe=sys.executable)
            self.assertTrue(ok)
            st = json.loads(Path(td, "autoloop-state.json").read_text(encoding="utf-8"))
            last_f = st["iterations"][-1]["findings"][-1]
            self.assertEqual(last_f.get("dimension"), "runner_synthesize")


class TestCostBudget(unittest.TestCase):
    def test_tick_exits_12_when_over_cap(self):
        try:
            from autoloop_runner.tick import run_tick
        except ImportError:
            sys.path.insert(0, str(SERVICES))
            from autoloop_runner.tick import run_tick

        env = _runner_subprocess_env()
        with tempfile.TemporaryDirectory() as td:
            td = str(Path(td).resolve())
            subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "autoloop-controller.py"),
                    td,
                    "--init",
                    "--template",
                    "T1",
                    "--goal",
                    "c",
                ],
                cwd=ROOT,
                check=True,
                env=env,
            )
            st = json.loads(Path(td, "autoloop-state.json").read_text(encoding="utf-8"))
            st.setdefault("metadata", {})["runner_estimated_cost_usd"] = 999.0
            Path(td, "autoloop-state.json").write_text(
                json.dumps(st, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            old = os.environ.get("RUNNER_MAX_ESTIMATED_USD")
            os.environ["RUNNER_MAX_ESTIMATED_USD"] = "1"
            try:
                rc = run_tick(td, strict=False, lock_blocking=True)
            finally:
                if old is None:
                    os.environ.pop("RUNNER_MAX_ESTIMATED_USD", None)
                else:
                    os.environ["RUNNER_MAX_ESTIMATED_USD"] = old
            self.assertEqual(rc, 12)


class TestDecideHandoffValidate(unittest.TestCase):
    def test_validate_handoff(self):
        try:
            from autoloop_runner.decide import validate_handoff
        except ImportError:
            sys.path.insert(0, str(SERVICES))
            from autoloop_runner.decide import validate_handoff

        ok, _ = validate_handoff(
            {
                "strategy_id": "S01-x",
                "hypothesis": "h",
                "planned_commands": ["echo hi"],
                "impacted_dimensions": ["syntax"],
            }
        )
        self.assertTrue(ok)
        ok2, reason = validate_handoff({"strategy_id": "S01-x"})
        self.assertFalse(ok2)
        self.assertIn("missing", reason)


def _runner_subprocess_env():
    """子进程需能 import autoloop_runner（editable 安装或 PYTHONPATH=services）。"""
    e = dict(os.environ)
    p = str(SERVICES)
    prev = e.get("PYTHONPATH", "")
    e["PYTHONPATH"] = p + (os.pathsep + prev if prev else "")
    return e


class TestRunnerTickFirstStep(unittest.TestCase):
    """INIT → tick 仅需 controller 切片，无需 OpenAI。"""

    def test_tick_from_init_completes_orient(self):
        env = _runner_subprocess_env()
        with tempfile.TemporaryDirectory() as td:
            td = str(Path(td).resolve())
            subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "autoloop-controller.py"),
                    td,
                    "--init",
                    "--template",
                    "T1",
                    "--goal",
                    "tick",
                ],
                cwd=ROOT,
                check=True,
                env=env,
            )
            r = subprocess.run(
                [sys.executable, "-m", "autoloop_runner.cli", "tick", td],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
            )
            self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
            cp = json.loads(Path(td, "checkpoint.json").read_text(encoding="utf-8"))
            self.assertEqual(cp.get("last_completed_phase"), "ORIENT")


@unittest.skipUnless(
    os.environ.get("RUN_FULL_RUNNER_TICK") == "1",
    "set RUN_FULL_RUNNER_TICK=1 for DECIDE+ mock LLM chain",
)
class TestRunnerTickMockIntegration(unittest.TestCase):
    def test_two_ticks_mock_llm_reaches_decide_complete(self):
        env = {**_runner_subprocess_env(), "RUNNER_MOCK_LLM": "1"}
        with tempfile.TemporaryDirectory() as td:
            td = str(Path(td).resolve())
            subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "autoloop-controller.py"),
                    td,
                    "--init",
                    "--template",
                    "T1",
                    "--goal",
                    "tick",
                ],
                cwd=ROOT,
                check=True,
                env=env,
            )
            env2 = {**env, "RUNNER_MOCK_LLM": "1"}
            r1 = subprocess.run(
                [sys.executable, "-m", "autoloop_runner.cli", "tick", td],
                cwd=ROOT,
                env=env2,
                capture_output=True,
                text=True,
            )
            self.assertEqual(r1.returncode, 0, r1.stderr + r1.stdout)
            r2 = subprocess.run(
                [sys.executable, "-m", "autoloop_runner.cli", "tick", td],
                cwd=ROOT,
                env=env2,
                capture_output=True,
                text=True,
            )
            self.assertEqual(r2.returncode, 0, r2.stderr + r2.stdout)
            cp = json.loads(Path(td, "checkpoint.json").read_text(encoding="utf-8"))
            self.assertEqual(cp.get("last_completed_phase"), "DECIDE")
