"""Regression coverage for the unattended Runner's security boundaries."""

import unittest
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVICES = ROOT / "services"
if str(SERVICES) not in sys.path:
    sys.path.insert(0, str(SERVICES))

from autoloop_runner.act import _command_allowed
from autoloop_runner.security import (
    resolve_openai_base_url,
    sanitized_child_environment,
)


class TestRunnerCommandAllowlist(unittest.TestCase):
    def test_allows_complete_glob_match(self):
        self.assertTrue(
            _command_allowed(
                "python3 /opt/autoloop/scripts/autoloop-render.py /tmp/task",
                ["python3 /opt/autoloop/scripts/autoloop-*.py *"],
            )
        )

    def test_rejects_substring_match(self):
        self.assertFalse(
            _command_allowed(
                "python3 /tmp/untrusted.py",
                ["python3"],
            )
        )


class TestRunnerCredentialBoundary(unittest.TestCase):
    def test_removes_known_credentials_from_child_environment(self):
        child_env = sanitized_child_environment(
            {
                "PATH": "/usr/bin",
                "OPENAI_API_KEY": "do-not-pass",
                "GITHUB_TOKEN": "do-not-pass",
                "CUSTOM_SECRET": "do-not-pass",
                "AWS_SECRET_ACCESS_KEY": "do-not-pass",
                "AWS_SESSION_TOKEN": "do-not-pass",
                "SAFE_FLAG": "ok",
            },
            {"ANTHROPIC_API_KEY": "do-not-pass", "EXTRA": "kept"},
        )
        self.assertEqual(child_env, {"PATH": "/usr/bin", "SAFE_FLAG": "ok", "EXTRA": "kept"})


class TestOpenAIBaseUrlBoundary(unittest.TestCase):
    def test_allows_openai_and_azure_https_endpoints(self):
        self.assertEqual(
            resolve_openai_base_url({"OPENAI_BASE_URL": "https://api.openai.com/v1"}),
            "https://api.openai.com/v1",
        )
        self.assertEqual(
            resolve_openai_base_url({"OPENAI_BASE_URL": "https://example.openai.azure.com/openai/v1"}),
            "https://example.openai.azure.com/openai/v1",
        )

    def test_rejects_unreviewed_or_insecure_endpoint(self):
        with self.assertRaises(ValueError):
            resolve_openai_base_url({"OPENAI_BASE_URL": "http://api.openai.com/v1"})
        with self.assertRaises(ValueError):
            resolve_openai_base_url({"OPENAI_BASE_URL": "https://proxy.example/v1"})

    def test_allows_custom_endpoint_only_with_explicit_opt_in(self):
        self.assertEqual(
            resolve_openai_base_url(
                {
                    "OPENAI_BASE_URL": "https://proxy.example/v1",
                    "AUTOLOOP_ALLOW_CUSTOM_OPENAI_BASE_URL": "1",
                }
            ),
            "https://proxy.example/v1",
        )
