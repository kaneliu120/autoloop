"""P3-15：run_tool 写入 metadata.audit（tool_start / tool_finish / tool_timeout）。"""

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from subprocess import TimeoutExpired
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
CONTROLLER_PATH = SCRIPTS / "autoloop-controller.py"


def _load_controller():
    spec = importlib.util.spec_from_file_location("autoloop_controller_mod", CONTROLLER_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestRunToolMetadataAudit(unittest.TestCase):
    def setUp(self):
        self._c = _load_controller()

    def test_tool_start_finish_on_success(self):
        td = tempfile.mkdtemp()
        try:
            subprocess.run(
                [sys.executable, str(SCRIPTS / "autoloop-state.py"), "init", td, "T1", "audit"],
                check=True,
                capture_output=True,
            )
            self._c.run_tool("autoloop-validate.py", [td], capture=True, work_dir=td)
            with open(os.path.join(td, "autoloop-state.json"), encoding="utf-8") as f:
                state = json.load(f)
            events = [r.get("event") for r in state.get("metadata", {}).get("audit", [])]
            self.assertIn("tool_start", events)
            self.assertIn("tool_finish", events)
            finishes = [r for r in state["metadata"]["audit"] if r.get("event") == "tool_finish"]
            self.assertTrue(finishes)
            self.assertEqual(finishes[-1].get("returncode"), 0)
            self.assertIs(finishes[-1].get("timeout"), False)
        finally:
            shutil.rmtree(td, ignore_errors=True)

    def test_tool_finish_on_nonzero(self):
        td = tempfile.mkdtemp()
        try:
            subprocess.run(
                [sys.executable, str(SCRIPTS / "autoloop-state.py"), "init", td, "T1", "audit"],
                check=True,
                capture_output=True,
            )
            _out, rc = self._c.run_tool(
                "autoloop-state.py",
                ["invalid_subcommand_xyz", td],
                capture=True,
                work_dir=td,
            )
            self.assertNotEqual(rc, 0)
            with open(os.path.join(td, "autoloop-state.json"), encoding="utf-8") as f:
                state = json.load(f)
            last = [r for r in state.get("metadata", {}).get("audit", []) if r.get("event") == "tool_finish"][-1]
            self.assertEqual(last.get("returncode"), rc)
            le = state.get("metadata", {}).get("last_error")
            self.assertIsNotNone(le)
            self.assertEqual(le.get("script"), "autoloop-state.py")
        finally:
            shutil.rmtree(td, ignore_errors=True)

    def test_tool_timeout_audit(self):
        td = tempfile.mkdtemp()
        try:
            subprocess.run(
                [sys.executable, str(SCRIPTS / "autoloop-state.py"), "init", td, "T1", "audit"],
                check=True,
                capture_output=True,
            )
            with patch.object(self._c.subprocess, "run", side_effect=TimeoutExpired(cmd="x", timeout=1)):
                _out, rc = self._c.run_tool("autoloop-validate.py", [td], capture=True, work_dir=td)
            self.assertEqual(rc, 124)
            with open(os.path.join(td, "autoloop-state.json"), encoding="utf-8") as f:
                state = json.load(f)
            timeouts = [r for r in state.get("metadata", {}).get("audit", []) if r.get("event") == "tool_timeout"]
            self.assertTrue(timeouts)
            self.assertTrue(timeouts[-1].get("timeout"))
        finally:
            shutil.rmtree(td, ignore_errors=True)
