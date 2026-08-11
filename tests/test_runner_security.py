"""Regression coverage for the unattended Runner's security boundaries."""

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SERVICES = ROOT / "services"
if str(SERVICES) not in sys.path:
    sys.path.insert(0, str(SERVICES))

from autoloop_runner.act import _command_allowed
from autoloop_runner.security import (
    RUNNER_ALLOWED_COMMANDS_ENV,
    RUNNER_WORKDIR_ROOT_ENV,
    resolve_openai_base_url,
    resolve_runner_command_patterns,
    resolve_trusted_work_dir,
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
            {"VENDOR_API_KEY": "do-not-pass", "EXTRA": "kept"},
        )
        self.assertEqual(child_env, {"PATH": "/usr/bin", "SAFE_FLAG": "ok", "EXTRA": "kept"})
        self.assertNotIn(RUNNER_ALLOWED_COMMANDS_ENV, sanitized_child_environment(
            {"PATH": "/usr/bin", RUNNER_ALLOWED_COMMANDS_ENV: '["*"]'}
        ))


class TestRunnerOperatorPolicy(unittest.TestCase):
    def test_task_state_cannot_supply_the_runner_policy(self):
        self.assertEqual(
            resolve_runner_command_patterns(["python3 /opt/autoloop/*.py *"], {}),
            ["python3 /opt/autoloop/*.py *"],
        )

    def test_runner_uses_the_builtin_policy_when_state_is_untrusted(self):
        from autoloop_runner.tick import _allowed_globs

        with patch.dict(os.environ, {}, clear=True):
            patterns = _allowed_globs("/task-state-is-not-read")
        self.assertEqual(len(patterns), 1)
        self.assertIn("autoloop-*.py", patterns[0])

    def test_custom_policy_requires_valid_json_and_rejects_global_glob(self):
        with self.assertRaises(ValueError):
            resolve_runner_command_patterns(["default"], {RUNNER_ALLOWED_COMMANDS_ENV: "*"})
        with self.assertRaises(ValueError):
            resolve_runner_command_patterns(
                ["default"], {RUNNER_ALLOWED_COMMANDS_ENV: '["*"]'}
            )


class TestRunnerWorkdirBoundary(unittest.TestCase):
    def test_workdir_must_resolve_within_operator_root(self):
        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as root:
            child = Path(root) / "task"
            child.mkdir()
            env = {RUNNER_WORKDIR_ROOT_ENV: root}
            self.assertEqual(resolve_trusted_work_dir(str(child), env), str(child.resolve()))
            with self.assertRaises(ValueError):
                resolve_trusted_work_dir("/tmp", env)

            escape = Path(root) / "escape"
            escape.symlink_to("/tmp", target_is_directory=True)
            with self.assertRaises(ValueError):
                resolve_trusted_work_dir(str(escape), env)

    def test_missing_root_is_rejected(self):
        with self.assertRaises(ValueError):
            resolve_trusted_work_dir("/tmp", {})


class TestStateAuthorizationFields(unittest.TestCase):
    def test_state_update_cannot_restore_legacy_allowlist_fields(self):
        with tempfile.TemporaryDirectory() as work_dir:
            init = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "autoloop-state.py"),
                    "init",
                    work_dir,
                    "T1",
                    "test",
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(init.returncode, 0, init.stderr + init.stdout)
            update = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "autoloop-state.py"),
                    "update",
                    work_dir,
                    "plan.template_params.allowed_commands",
                    '["*"]',
                ],
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(update.returncode, 0)
            self.assertIn("Cannot update protected path", update.stdout)


class TestRunnerSensitiveDataBoundary(unittest.TestCase):
    def test_busy_lock_does_not_log_the_workdir(self):
        from autoloop_runner import tick

        with tempfile.TemporaryDirectory() as root:
            work_dir = Path(root) / "project-with-secret-sk-test-value"
            work_dir.mkdir()
            with patch.dict(
                os.environ, {RUNNER_WORKDIR_ROOT_ENV: root}, clear=False
            ), patch.object(tick.WorkdirLock, "acquire", return_value=False), self.assertLogs(
                "autoloop_runner", level="WARNING"
            ) as captured:
                self.assertEqual(tick.run_tick(str(work_dir)), 11)
        self.assertNotIn("sk-test-value", "\n".join(captured.output))

    def test_invalid_handoff_does_not_log_model_payload(self):
        from autoloop_runner import tick

        with tempfile.TemporaryDirectory() as work_dir:
            Path(work_dir, "autoloop-state.json").write_text(
                '{"iterations": []}', encoding="utf-8"
            )
            invalid_payload = {
                "strategy_id": "S01-test",
                "hypothesis": "contains sk-test-value",
                "planned_commands": "not-a-list",
            }
            with patch.dict(os.environ, {"RUNNER_MOCK_LLM": "1"}, clear=False), patch.object(
                tick, "_mock_decide_json", return_value=invalid_payload
            ), self.assertLogs("autoloop_runner", level="ERROR") as captured:
                self.assertFalse(tick._runner_decide(work_dir, None))
        self.assertNotIn("sk-test-value", "\n".join(captured.output))

    def test_openai_error_event_omits_exception_text(self):
        from autoloop_runner import tick

        def failing_chat(**_kwargs):
            raise RuntimeError("Bearer sk-test-value")

        with patch.object(tick.runner_log, "emit") as emit:
            with self.assertRaises(RuntimeError):
                tick._chat_json("/tmp", _chat_json_impl=failing_chat)
        self.assertEqual(emit.call_args.args[1], "openai_chat_error")
        self.assertEqual(
            emit.call_args.kwargs["extra"], {"error_type": "RuntimeError"}
        )


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
