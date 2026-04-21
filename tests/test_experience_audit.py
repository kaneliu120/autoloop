#!/usr/bin/env python3
"""P2-05: audit subcommand for closed-loop continuous-learning checks."""

import importlib.util
import os
import shutil
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"

REGISTRY_TEMPLATE = """\
# Experience Registry - global experience registry

## Global Strategy Effect Registry

| strategy_id | template | dimension | description | avg_delta | side_effects | use_count | success_rate | status |
|------------|----------|-----------|-------------|-----------|-------------|-----------|-------------|--------|
{rows}
"""


def _load_experience():
    path = SCRIPTS / "autoloop-experience.py"
    spec = importlib.util.spec_from_file_location("al_exp_audit", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _make_registry(tmpdir, rows_str):
    reg = os.path.join(tmpdir, "references", "experience-registry.md")
    os.makedirs(os.path.dirname(reg), exist_ok=True)
    with open(reg, "w", encoding="utf-8") as f:
        f.write(REGISTRY_TEMPLATE.format(rows=rows_str))
    return reg


class TestAuditPromoteToCandidateDefault(unittest.TestCase):
    """Rule 1: use_count>=4, success_rate>80%, status=Recommended -> Candidate Default."""

    def setUp(self):
        self.td = tempfile.mkdtemp(prefix="al_audit_")
        self.mod = _load_experience()

    def tearDown(self):
        shutil.rmtree(self.td, ignore_errors=True)

    def test_promote_recommended_to_candidate_default(self):
        row = "| S01-test | T1 | cov | [Keep] @2026-03-20 desc | 1.5 | — | 5 | 90% | Recommended |"
        reg = _make_registry(self.td, row)
        result = self.mod.cmd_audit(reg, dry_run=True)
        self.assertEqual(len(result), 1)
        self.assertIn("Candidate Default", result[0]["action"])

    def test_no_promote_if_use_count_below_4(self):
        row = "| S02-test | T1 | cov | [Keep] @2026-03-20 desc | 1 | — | 3 | 90% | Recommended |"
        reg = _make_registry(self.td, row)
        result = self.mod.cmd_audit(reg, dry_run=True)
        # use_count=3 < 4, should not suggest promotion
        promote = [r for r in result if "Candidate Default" in r["action"]]
        self.assertEqual(len(promote), 0)

    def test_no_promote_if_success_rate_not_above_80(self):
        row = "| S03-test | T1 | cov | [Keep] @2026-03-20 desc | 1 | — | 5 | 80% | Recommended |"
        reg = _make_registry(self.td, row)
        result = self.mod.cmd_audit(reg, dry_run=True)
        promote = [r for r in result if "Candidate Default" in r["action"]]
        self.assertEqual(len(promote), 0, "80% is not >80%, should not promote")


class TestAuditDeprecate(unittest.TestCase):
    """Rule 2: use_count>=3, success_rate<30%, status!=Deprecated -> Deprecated."""

    def setUp(self):
        self.td = tempfile.mkdtemp(prefix="al_audit_")
        self.mod = _load_experience()

    def tearDown(self):
        shutil.rmtree(self.td, ignore_errors=True)

    def test_deprecate_low_success_rate(self):
        row = "| S04-test | T2 | acc | [Avoid] @2026-03-20 desc | -0.5 | — | 4 | 20% | Observation |"
        reg = _make_registry(self.td, row)
        result = self.mod.cmd_audit(reg, dry_run=True)
        self.assertEqual(len(result), 1)
        self.assertIn("Deprecated", result[0]["action"])

    def test_skip_already_deprecated(self):
        row = "| S05-test | T2 | acc | [Avoid] @2026-03-20 desc | -1 | — | 5 | 10% | Deprecated |"
        reg = _make_registry(self.td, row)
        result = self.mod.cmd_audit(reg, dry_run=True)
        deprecate = [r for r in result if "Deprecated" in r["action"]]
        self.assertEqual(len(deprecate), 0, "Already deprecated, should not suggest again")


class TestAuditDecayToObservation(unittest.TestCase):
    """Rule 3: status=Recommended and last validation >90 days ago -> Observation."""

    def setUp(self):
        self.td = tempfile.mkdtemp(prefix="al_audit_")
        self.mod = _load_experience()

    def tearDown(self):
        shutil.rmtree(self.td, ignore_errors=True)

    def test_decay_old_recommended(self):
        # 91 days ago from today
        row = "| S06-test | T3 | qual | [Keep] @2025-12-01 old strategy | 0.5 | — | 2 | 60% | Recommended |"
        reg = _make_registry(self.td, row)
        result = self.mod.cmd_audit(reg, dry_run=True)
        decay = [r for r in result if "Observation" in r["action"]]
        self.assertEqual(len(decay), 1)

    def test_no_decay_recent(self):
        row = "| S07-test | T3 | qual | [Keep] @2026-03-25 recent | 0.5 | — | 2 | 60% | Recommended |"
        reg = _make_registry(self.td, row)
        result = self.mod.cmd_audit(reg, dry_run=True)
        decay = [r for r in result if "Observation" in r["action"]]
        self.assertEqual(len(decay), 0, "Recent strategy should not decay")


class TestAuditNoSuggestions(unittest.TestCase):
    """Cases that should not trigger changes."""

    def setUp(self):
        self.td = tempfile.mkdtemp(prefix="al_audit_")
        self.mod = _load_experience()

    def tearDown(self):
        shutil.rmtree(self.td, ignore_errors=True)

    def test_empty_registry(self):
        reg = _make_registry(self.td, "")
        result = self.mod.cmd_audit(reg, dry_run=True)
        self.assertEqual(len(result), 0)

    def test_healthy_strategies(self):
        rows = (
            "| S08-test | T1 | cov | [Keep] @2026-03-20 ok | 0.5 | — | 2 | 60% | Observation |\n"
            "| S09-test | T2 | acc | [Keep] @2026-03-20 fine | 1.0 | — | 3 | 70% | Recommended |"
        )
        reg = _make_registry(self.td, rows)
        result = self.mod.cmd_audit(reg, dry_run=True)
        self.assertEqual(len(result), 0, "All strategies are healthy")


class TestAuditExecuteMode(unittest.TestCase):
    """Non-dry-run mode applies changes and writes an audit log."""

    def setUp(self):
        self.td = tempfile.mkdtemp(prefix="al_audit_")
        self.mod = _load_experience()

    def tearDown(self):
        shutil.rmtree(self.td, ignore_errors=True)

    def test_execute_writes_changes_and_audit(self):
        row = "| S10-test | T1 | cov | [Keep] @2026-03-20 desc | 1.5 | — | 5 | 90% | Recommended |"
        reg = _make_registry(self.td, row)
        result = self.mod.cmd_audit(reg, dry_run=False)
        self.assertEqual(len(result), 1)

        # Verify main table was updated
        with open(reg, encoding="utf-8") as f:
            content = f.read()
        rows = self.mod._parse_strategy_table(content)
        s10 = [r for r in rows if r.get("strategy_id") == "S10-test"]
        self.assertEqual(len(s10), 1)
        self.assertEqual(s10[0]["status"], "Candidate Default")

        # Verify audit log was written
        audit_path = self.mod._audit_path(reg)
        self.assertTrue(os.path.isfile(audit_path))
        with open(audit_path, encoding="utf-8") as f:
            audit_content = f.read()
        self.assertIn("audit", audit_content)
        self.assertIn("S10-test", audit_content)


class TestAuditRulePriority(unittest.TestCase):
    """Rule priority: promotion/deprecation wins over decay."""

    def setUp(self):
        self.td = tempfile.mkdtemp(prefix="al_audit_")
        self.mod = _load_experience()

    def tearDown(self):
        shutil.rmtree(self.td, ignore_errors=True)

    def test_promote_beats_decay(self):
        """Recommended + high success + high usage should promote even if older than 90 days."""
        row = "| S11-test | T1 | cov | [Keep] @2025-12-01 old but good | 2.0 | — | 6 | 95% | Recommended |"
        reg = _make_registry(self.td, row)
        result = self.mod.cmd_audit(reg, dry_run=True)
        self.assertEqual(len(result), 1)
        # Should promote, not decay (promotion rule checked first via continue)
        self.assertIn("Candidate Default", result[0]["action"])


if __name__ == "__main__":
    unittest.main()
