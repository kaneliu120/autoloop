"""P2-09: MCP server JSON contract (skip the module if `mcp` is unavailable)."""

import importlib.util
import json
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SERVER_PATH = ROOT / "mcp-server" / "server.py"


def _load_server():
    spec = importlib.util.spec_from_file_location("autoloop_mcp_server", SERVER_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_SKIP = None
try:
    _SERVER = _load_server()
except Exception as exc:  # pragma: no cover - ImportError and similar
    _SERVER = None
    _SKIP = str(exc)


@unittest.skipIf(
    _SERVER is None,
    "mcp server not importable: " + (_SKIP or "unknown"),
)
class TestMcpContract(unittest.TestCase):
    def test_controller_init_requires_template(self):
        raw = _SERVER.autoloop_controller(
            "/tmp/autoloop-mcp-contract-nonexistent-wd",
            mode="init",
            template="",
            goal="",
        )
        data = json.loads(raw)
        self.assertFalse(data.get("success"), data)
        err = (data.get("error") or "").lower()
        self.assertIn("template", err)

    def test_run_script_missing_returns_failure_shape(self):
        raw = _SERVER._run_script("nonexistent-autoloop-tool.py", [])
        data = json.loads(raw)
        self.assertFalse(data.get("success"))
        self.assertIn("error", data)

    def test_run_script_success_shape(self):
        raw = _SERVER._run_script("autoloop-variance.py", ["compute", "7", "8", "--evidence", "2"])
        data = json.loads(raw)
        self.assertTrue(data.get("success"), data)
        self.assertIn("output", data)

    def test_mcp_requires_a_configured_workspace_root(self):
        with patch.dict(os.environ, {}, clear=True):
            raw = _SERVER.autoloop_validate("/tmp")
        data = json.loads(raw)
        self.assertFalse(data.get("success"))
        self.assertIn("AUTOLOOP_MCP_WORKDIR_ROOT", data.get("error", ""))

    def test_mcp_rejects_paths_outside_its_workspace_root(self):
        with TemporaryDirectory() as root:
            with patch.dict(
                os.environ,
                {"AUTOLOOP_MCP_WORKDIR_ROOT": root},
                clear=True,
            ):
                raw = _SERVER.autoloop_validate("/tmp")
        data = json.loads(raw)
        self.assertFalse(data.get("success"))
        self.assertIn("must resolve inside", data.get("error", ""))

    def test_mcp_rejects_a_symlink_escape(self):
        with TemporaryDirectory() as root:
            escape = Path(root) / "escape"
            escape.symlink_to("/tmp", target_is_directory=True)
            with patch.dict(
                os.environ,
                {"AUTOLOOP_MCP_WORKDIR_ROOT": root},
                clear=True,
            ):
                raw = _SERVER.autoloop_validate(str(escape))
        data = json.loads(raw)
        self.assertFalse(data.get("success"))
        self.assertIn("must resolve inside", data.get("error", ""))

    def test_mcp_blocks_writes_until_explicitly_enabled(self):
        with TemporaryDirectory() as root:
            with patch.dict(
                os.environ,
                {"AUTOLOOP_MCP_WORKDIR_ROOT": root},
                clear=True,
            ):
                raw = _SERVER.autoloop_init(root, "T1", "test")
        data = json.loads(raw)
        self.assertFalse(data.get("success"))
        self.assertIn("AUTOLOOP_MCP_ALLOW_WRITE", data.get("error", ""))

    def test_mcp_allows_a_write_inside_the_configured_root(self):
        with TemporaryDirectory() as root:
            with patch.dict(
                os.environ,
                {
                    "AUTOLOOP_MCP_WORKDIR_ROOT": root,
                    "AUTOLOOP_MCP_ALLOW_WRITE": "1",
                },
                clear=True,
            ):
                raw = _SERVER.autoloop_init(root, "T1", "test")
            data = json.loads(raw)
            self.assertTrue(data.get("success"), data)
            for filename in (
                "autoloop-plan.md",
                "autoloop-findings.md",
                "autoloop-progress.md",
                "autoloop-results.tsv",
            ):
                self.assertTrue(Path(root, filename).is_file(), filename)
