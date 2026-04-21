#!/usr/bin/env python3
"""P3-01: main-table upsert + `experience-audit.md`."""

import importlib.util
import os
import shutil
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
SRC_REG = ROOT / "references" / "experience-registry.md"


def _load_experience():
    path = SCRIPTS / "autoloop-experience.py"
    spec = importlib.util.spec_from_file_location("al_exp_p301", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestExperienceP301UpsertAudit(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.mkdtemp(prefix="al_exp301_")
        self.reg = os.path.join(self.td, "experience-registry.md")
        shutil.copy(SRC_REG, self.reg)
        self.mod = _load_experience()

    def tearDown(self):
        shutil.rmtree(self.td, ignore_errors=True)

    def test_two_writes_one_main_row_and_two_audit_blocks(self):
        m = self.mod
        ok1 = m.cmd_write(
            self.reg, "S99-p301", "Keep", "0.5", None,
            status=None, template="T1", dimension="coverage", tags=None,
        )
        self.assertTrue(ok1)
        ok2 = m.cmd_write(
            self.reg, "S99-p301", "Keep", "0.3", None,
            status=None, template="T1", dimension="coverage", tags=None,
        )
        self.assertTrue(ok2)
        with open(self.reg, encoding="utf-8") as f:
            rows = m._parse_strategy_table(f.read())
        p301 = [r for r in rows if r.get("strategy_id") == "S99-p301"]
        self.assertEqual(len(p301), 1, p301)
        self.assertEqual(p301[0].get("use_count"), "2")
        audit_path = m._audit_path(self.reg)
        self.assertTrue(os.path.isfile(audit_path))
        with open(audit_path, encoding="utf-8") as af:
            aud = af.read()
        self.assertGreaterEqual(aud.count("### "), 2)
        self.assertIn("S99-p301", aud)

    def test_multi_prefix_audit_only(self):
        m = self.mod
        with open(self.reg, encoding="utf-8") as f:
            before = m._parse_strategy_table(f.read())
        n_before = len(before)
        ok = m.cmd_write(
            self.reg, "multi:{S01-a,S02-b}", "Pending Validation", "0", None,
            template="T1", dimension="—", tags=None,
        )
        self.assertTrue(ok)
        with open(self.reg, encoding="utf-8") as f:
            after = m._parse_strategy_table(f.read())
        self.assertEqual(len(after), n_before)
        with open(m._audit_path(self.reg), encoding="utf-8") as af:
            aud = af.read()
        self.assertIn("multi:", aud)
        self.assertIn("write_multi_reference", aud)

    def test_consolidate_merges_duplicate_rows(self):
        m = self.mod
        m.cmd_write(
            self.reg, "S98-dup", "Keep", "1", None,
            template="T2", dimension="x", tags=None,
        )
        with open(self.reg, encoding="utf-8") as f:
            lines = f.read().split("\n")
        insert_at = None
        for i, line in enumerate(lines):
            if "S98-dup" in line and line.strip().startswith("|"):
                insert_at = i + 1
                break
        self.assertIsNotNone(insert_at)
        dup_line = (
            "| S98-dup | T2 | x | [Keep] @2099-01-01 | 0 | — | 1 | 50% | Observation |"
        )
        lines.insert(insert_at, dup_line)
        with open(self.reg, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        with open(self.reg, encoding="utf-8") as f:
            raw = m._parse_strategy_table(f.read())
        self.assertEqual(len([r for r in raw if r.get("strategy_id") == "S98-dup"]), 2)
        self.assertTrue(m.cmd_consolidate(self.reg, dry_run=False))
        with open(self.reg, encoding="utf-8") as f:
            raw2 = m._parse_strategy_table(f.read())
        dup_after = [r for r in raw2 if r.get("strategy_id") == "S98-dup"]
        self.assertEqual(len(dup_after), 1)
        # Only one audited write(score=1); after consolidation avg_delta must stay the mean of the round deltas (=1), not the mean of the two row averages.
        self.assertEqual(dup_after[0].get("use_count"), "1")
        self.assertEqual(dup_after[0].get("avg_delta"), "1")


class TestExperienceListDedupe(unittest.TestCase):
    def test_cmd_list_dedupes(self):
        mod = _load_experience()
        td = tempfile.mkdtemp(prefix="al_list_")
        self.addCleanup(lambda: shutil.rmtree(td, ignore_errors=True))
        reg = os.path.join(td, "experience-registry.md")
        shutil.copy(SRC_REG, reg)
        mod.cmd_write(reg, "S97-l", "Keep", "1", None, template="T1", dimension="d", tags=None)
        mod.cmd_write(reg, "S97-l", "Avoid", "-1", None, template="T1", dimension="d", tags=None)
        lst = mod.cmd_list(reg)
        s97 = [x for x in lst if x.get("strategy_id") == "S97-l"]
        self.assertEqual(len(s97), 1)


if __name__ == "__main__":
    unittest.main()
