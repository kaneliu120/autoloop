#!/usr/bin/env python3
"""P3-02: experience query matches the context_tags / context-scoped spec."""

import importlib.util
import os
import tempfile
import unittest


def _load_experience():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(root, "scripts", "autoloop-experience.py")
    spec = importlib.util.spec_from_file_location("al_exp_p302", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_MINIMAL_HEAD = """# X

| strategy_id | template | dimension | description | avg_delta | side_effects | use_count | success_rate | status |
|-------------|----------|-----------|-------------|-----------|--------------|-----------|--------------|--------|
"""


class TestExperienceP302ContextMatch(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.mkdtemp(prefix="al_exp302_")
        self.reg = os.path.join(self.td, "experience-registry.md")
        self.mod = _load_experience()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.td, ignore_errors=True)

    def _write_reg(self, body_rows, suffix=""):
        with open(self.reg, "w", encoding="utf-8") as f:
            f.write(_MINIMAL_HEAD + body_rows + suffix)

    def test_overlap_at_least_two_filters_strategies(self):
        m = self.mod
        rows = (
            "| S-a | T1 | d | [Keep] @2026-03-15 [python,backend,security] | 1 | — | 2 | 100% | Recommended |\n"
            "| S-b | T1 | d | [Keep] @2026-03-15 [go,frontend,performance] | 1 | — | 2 | 100% | Recommended |\n"
        )
        self._write_reg(rows)
        r_all = m.cmd_query(self.reg, "T1", [])
        self.assertEqual({x["strategy_id"] for x in r_all}, {"S-a", "S-b"})
        r_pb = m.cmd_query(self.reg, "T1", ["python", "backend"])
        self.assertEqual({x["strategy_id"] for x in r_pb}, {"S-a"})
        r_one = m.cmd_query(self.reg, "T1", ["python"])
        self.assertEqual(r_one, [])

    def test_tag_overlap_case_insensitive(self):
        m = self.mod
        rows = (
            "| S-a | T1 | d | [Keep] @2026-03-15 [python,backend] | 1 | — | 2 | 100% | Recommended |\n"
        )
        self._write_reg(rows)
        r = m.cmd_query(self.reg, "T1", ["PYTHON", "BACKEND", "security"])
        self.assertEqual(len(r), 1)
        self.assertEqual(r[0]["strategy_id"], "S-a")

    def test_scoped_exact_overrides_global(self):
        m = self.mod
        rows = (
            "| S-z | T1 | d | [Keep] @2026-02-01 [python,backend,security] | 1 | — | 2 | 100% | Observation |\n"
        )
        scoped = """
| strategy_id | context_tags | status | evidence | last_validated |
|-------------|--------------|--------|----------|----------------|
| S-z | [python, backend, security] | Recommended | x | 2026-02-01 |
"""
        self._write_reg(rows, scoped)
        r = m.cmd_query(self.reg, "T1", ["python", "backend", "security"])
        self.assertEqual(len(r), 1)
        self.assertEqual(r[0]["effective_status"], "Recommended")

    def test_scoped_subset_pick_longest_row(self):
        m = self.mod
        rows = (
            "| S-z | T1 | d | [Keep] @2026-02-01 [python,backend,security] | 1 | — | 2 | 100% | Observation |\n"
        )
        scoped = """
| strategy_id | context_tags | status | evidence | last_validated |
|-------------|--------------|--------|----------|----------------|
| S-z | [python] | Candidate Default | a | 2026-02-01 |
| S-z | [python, backend] | Recommended | b | 2026-02-01 |
"""
        self._write_reg(rows, scoped)
        r = m.cmd_query(self.reg, "T1", ["python", "backend", "security"])
        self.assertEqual(len(r), 1)
        self.assertEqual(r[0]["effective_status"], "Recommended")

    def test_extract_tags_fallback_bracket_with_comma(self):
        m = self.mod
        desc = "note [Keep] @2026-02-01 [rust,backend]"
        self.assertEqual(
            m._extract_context_tags_from_description(desc),
            ["rust", "backend"],
        )

    def test_query_excludes_observation_by_default(self):
        m = self.mod
        rows = (
            "| S-obs | T1 | d | [Keep] @2026-02-01 [python,backend,security] | 1 | — | 2 | 100% | Observation |\n"
        )
        self._write_reg(rows)
        r = m.cmd_query(self.reg, "T1", ["python", "backend", "security"])
        self.assertEqual(r, [])

    def test_query_include_observation_returns_obs_row(self):
        m = self.mod
        rows = (
            "| S-obs | T1 | d | [Keep] @2026-02-01 [python,backend,security] | 1 | — | 2 | 100% | Observation |\n"
        )
        self._write_reg(rows)
        r = m.cmd_query(
            self.reg,
            "T1",
            ["python", "backend", "security"],
            include_observation=True,
        )
        self.assertEqual(len(r), 1)
        self.assertEqual(r[0]["strategy_id"], "S-obs")

    def test_decay_downgrade_not_in_default_results(self):
        """>90d recommended strategies are downgraded to observation inside query and should disappear from the default list (P0-03)."""
        m = self.mod
        rows = (
            "| S-old | T1 | d | [Keep] @2020-01-01 [python,backend,security] | 1 | — | 2 | 100% | Recommended |\n"
        )
        self._write_reg(rows)
        r = m.cmd_query(self.reg, "T1", ["python", "backend", "security"])
        self.assertEqual(r, [])
        r_obs = m.cmd_query(
            self.reg,
            "T1",
            ["python", "backend", "security"],
            include_observation=True,
        )
        self.assertEqual(len(r_obs), 1)
        self.assertEqual(r_obs[0].get("effective_status"), "Observation")


if __name__ == "__main__":
    unittest.main()
