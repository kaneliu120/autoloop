#!/usr/bin/env python3
"""autoloop-experience cmd_write：状态机与审计 score 链。"""

import importlib.util
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
SRC_REG = ROOT / "references" / "experience-registry.md"


def _load_experience():
    spec = importlib.util.spec_from_file_location(
        "al_exp_write_fsm", SCRIPTS / "autoloop-experience.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _row(mod, reg, sid):
    with open(reg, encoding="utf-8") as f:
        rows = mod._parse_strategy_table(f.read())
    for r in rows:
        if r.get("strategy_id") == sid:
            return r
    return None


class TestWriteFsm(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.mkdtemp(prefix="al_exp_fsm_")
        self.reg = os.path.join(self.td, "experience-registry.md")
        shutil.copy(SRC_REG, self.reg)
        self.mod = _load_experience()

    def tearDown(self):
        shutil.rmtree(self.td, ignore_errors=True)

    def test_first_write_observation(self):
        m = self.mod
        ok = m.cmd_write(
            self.reg, "S-fsm-a", "保持", "0.5", None,
            template="T1", dimension="d", tags=None,
        )
        self.assertTrue(ok)
        r = _row(m, self.reg, "S-fsm-a")
        self.assertEqual(r.get("status"), "观察")
        self.assertEqual(r.get("use_count"), "1")

    def test_two_positive_deltas_promote_to_recommended(self):
        m = self.mod
        m.cmd_write(
            self.reg, "S-fsm-b", "保持", "0.5", None,
            template="T1", dimension="d", tags=None,
        )
        m.cmd_write(
            self.reg, "S-fsm-b", "待验证", "0.3", None,
            template="T1", dimension="d", tags=None,
        )
        r = _row(m, self.reg, "S-fsm-b")
        self.assertEqual(r.get("status"), "推荐")
        self.assertEqual(r.get("use_count"), "2")

    def test_two_nonpositive_deltas_deprecate(self):
        m = self.mod
        m.cmd_write(
            self.reg, "S-fsm-c", "待验证", "0.5", None,
            template="T1", dimension="d", tags=None,
        )
        m.cmd_write(
            self.reg, "S-fsm-c", "避免", "-0.2", None,
            template="T1", dimension="d", tags=None,
        )
        m.cmd_write(
            self.reg, "S-fsm-c", "避免", "-0.1", None,
            template="T1", dimension="d", tags=None,
        )
        r = _row(m, self.reg, "S-fsm-c")
        self.assertEqual(r.get("status"), "已废弃")

    def test_deprecated_stays_deprecated_on_further_negative(self):
        m = self.mod
        sid = "S-fsm-d"
        m.cmd_write(self.reg, sid, "保持", "1", None, template="T1", dimension="d", tags=None)
        m.cmd_write(self.reg, sid, "避免", "-0.5", None, template="T1", dimension="d", tags=None)
        m.cmd_write(self.reg, sid, "避免", "-0.5", None, template="T1", dimension="d", tags=None)
        self.assertEqual(_row(m, self.reg, sid).get("status"), "已废弃")
        m.cmd_write(self.reg, sid, "避免", "-0.5", None, template="T1", dimension="d", tags=None)
        self.assertEqual(_row(m, self.reg, sid).get("status"), "已废弃")

    def test_deprecated_recovers_on_positive_delta(self):
        m = self.mod
        sid = "S-fsm-e"
        m.cmd_write(self.reg, sid, "保持", "1", None, template="T1", dimension="d", tags=None)
        m.cmd_write(self.reg, sid, "避免", "-0.5", None, template="T1", dimension="d", tags=None)
        m.cmd_write(self.reg, sid, "避免", "-0.5", None, template="T1", dimension="d", tags=None)
        self.assertEqual(_row(m, self.reg, sid).get("status"), "已废弃")
        m.cmd_write(self.reg, sid, "待验证", "0.5", None, template="T1", dimension="d", tags=None)
        self.assertEqual(_row(m, self.reg, sid).get("status"), "观察")

    def test_audit_write_scores_chronological(self):
        m = self.mod
        ap = m._audit_path(self.reg)
        m.cmd_write(
            self.reg, "S-fsm-z", "保持", "2.25", None,
            template="T1", dimension="d", tags=None,
        )
        self.assertEqual(m._audit_write_scores_chronological(ap, "S-fsm-z"), [2.25])
        m.cmd_write(
            self.reg, "S-fsm-z", "保持", "0.25", None,
            template="T1", dimension="d", tags=None,
        )
        self.assertEqual(m._audit_write_scores_chronological(ap, "S-fsm-z"), [2.25, 0.25])

    def test_avg_delta_is_mean_of_per_round_scores(self):
        m = self.mod
        sid = "S-fsm-avg"
        for sc in ("1", "2", "4"):
            m.cmd_write(
                self.reg, sid, "待验证", sc, None,
                template="T1", dimension="d", tags=None,
            )
        r = _row(m, self.reg, sid)
        self.assertEqual(r.get("use_count"), "3")
        self.assertAlmostEqual(float(r.get("avg_delta")), (1 + 2 + 4) / 3, places=3)

    def test_four_writes_promote_to_candidate_default(self):
        m = self.mod
        sid = "S-fsm-cand"
        for sc in ("1", "1", "1", "1"):
            m.cmd_write(
                self.reg, sid, "待验证", sc, None,
                template="T1", dimension="d", tags=None,
            )
        r = _row(m, self.reg, sid)
        self.assertEqual(r.get("status"), "候选默认")
        self.assertEqual(r.get("use_count"), "4")

    def test_require_mechanism_blocks_write_when_use_count_ge_2(self):
        """AUTOLOOP_EXPERIENCE_REQUIRE_MECHANISM=1：合并后 use_count≥2 须带 mechanism。"""
        m = self.mod
        sid = "S-fsm-mech"
        m.cmd_write(
            self.reg, sid, "保持", "0.5", None,
            template="T1", dimension="d", tags=None,
        )
        m.cmd_write(
            self.reg, sid, "保持", "0.5", None,
            template="T1", dimension="d", tags=None,
        )
        self.assertEqual(_row(m, self.reg, sid).get("use_count"), "2")
        with patch.dict(os.environ, {"AUTOLOOP_EXPERIENCE_REQUIRE_MECHANISM": "1"}):
            ok = m.cmd_write(
                self.reg, sid, "保持", "0.5", None,
                template="T1", dimension="d", tags=None,
            )
        self.assertFalse(ok)
        with patch.dict(os.environ, {"AUTOLOOP_EXPERIENCE_REQUIRE_MECHANISM": "1"}):
            ok = m.cmd_write(
                self.reg, sid, "保持", "0.5", None,
                template="T1", dimension="d", tags=None,
                mechanism="cache layer",
            )
        self.assertTrue(ok)

    def test_explicit_status_skips_automatic_transitions(self):
        m = self.mod
        sid = "S-fsm-manual"
        m.cmd_write(
            self.reg, sid, "避免", "-1", None,
            status="推荐", template="T1", dimension="d", tags=None,
        )
        m.cmd_write(
            self.reg, sid, "避免", "-1", None,
            status="推荐", template="T1", dimension="d", tags=None,
        )
        r = _row(m, self.reg, sid)
        self.assertEqual(r.get("status"), "推荐")


if __name__ == "__main__":
    unittest.main()
