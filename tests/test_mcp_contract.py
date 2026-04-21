"""P2-09: MCP server JSON contract (skip the module if `mcp` is unavailable)."""

import importlib.util
import json
import unittest
from pathlib import Path

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
