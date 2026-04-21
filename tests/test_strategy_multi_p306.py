#!/usr/bin/env python3
"""P3-06: constraints for `multi:` strategy_id values."""

import importlib.util
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
SRC_REG = ROOT / "references" / "experience-registry.md"

if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from autoloop_strategy_multi import (  # noqa: E402
    parse_multi_strategy_components,
    validate_multi_strategy_id,
)


def _load_experience():
    spec = importlib.util.spec_from_file_location(
        "al_exp_p306", SCRIPTS / "autoloop-experience.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestStrategyMultiParse(unittest.TestCase):
    def test_plus_and_comma(self):
        self.assertEqual(
            parse_multi_strategy_components("multi:{S01-a+S02-b}"),
            ["S01-a", "S02-b"],
        )
        self.assertEqual(
            parse_multi_strategy_components("Multi:{S01-a, S02-b}"),
            ["S01-a", "S02-b"],
        )

    def test_invalid_wrappers(self):
        self.assertIsNone(parse_multi_strategy_components("multi:S01-a,S02-b"))
        self.assertIsNone(parse_multi_strategy_components("multi:{}"))
        self.assertEqual(parse_multi_strategy_components("multi:{S01-a}"), ["S01-a"])
        ok1, msg1 = validate_multi_strategy_id("multi:{S01-a}")
        self.assertFalse(ok1)
        self.assertIn("2", msg1)

    def test_validate_two_distinct_snn(self):
        ok, _ = validate_multi_strategy_id("multi:{S01-a,S02-b}")
        self.assertTrue(ok)

    def test_validate_rejects_duplicate(self):
        ok, msg = validate_multi_strategy_id("multi:{S01-a,S01-a}")
        self.assertFalse(ok)
        self.assertIn("duplicate", msg.lower())

    def test_validate_rejects_bad_child(self):
        ok, msg = validate_multi_strategy_id("multi:{S01-a,foo}")
        self.assertFalse(ok)
        self.assertIn("child strategy", msg.lower())


class TestExperienceWriteMultiConstraints(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.mkdtemp(prefix="al_p306_")
        self.reg = os.path.join(self.td, "experience-registry.md")
        shutil.copy(SRC_REG, self.reg)
        self.mod = _load_experience()

    def tearDown(self):
        shutil.rmtree(self.td, ignore_errors=True)

    def test_valid_multi_writes_audit(self):
        ok = self.mod.cmd_write(
            self.reg,
            "multi:{S01-a,S02-b}",
            "Pending Validation",
            "0",
            None,
            template="T1",
            dimension="—",
            tags=None,
        )
        self.assertTrue(ok)

    def test_invalid_multi_rejected(self):
        ok = self.mod.cmd_write(
            self.reg,
            "multi:{S01-a}",
            "Pending Validation",
            "0",
            None,
            template="T1",
            dimension="—",
            tags=None,
        )
        self.assertFalse(ok)

    def test_multi_rejects_status(self):
        ok = self.mod.cmd_write(
            self.reg,
            "multi:{S01-a,S02-b}",
            "Pending Validation",
            "0",
            None,
            status="Observation",
            template="T1",
            dimension="—",
            tags=None,
        )
        self.assertFalse(ok)


class TestValidateJsonMultiComponents(unittest.TestCase):
    def test_tsv_multi_requires_children_in_findings(self):
        spec = importlib.util.spec_from_file_location(
            "val_p306", SCRIPTS / "autoloop-validate.py"
        )
        val = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(val)

        state = {
            "plan": {"strategy_history": []},
            "findings": {
                "rounds": [
                    {"findings": [{"strategy_id": "S01-a"}]},
                ],
                "strategy_evaluations": [],
            },
            "iterations": [],
            "results_tsv": [
                {"strategy_id": "multi:{S01-a,S02-b}"},
            ],
        }
        errors = []
        val._check_primary_key_consistency(state, errors)
        self.assertTrue(
            any("S02-b" in e and "multi" in e for e in errors),
            errors,
        )


if __name__ == "__main__":
    unittest.main()
