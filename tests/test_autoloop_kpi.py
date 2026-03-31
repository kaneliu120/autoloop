#!/usr/bin/env python3
"""autoloop_kpi：T5 KPI 行与 controller/score 共用逻辑。"""

import importlib.util
import os
import unittest


def _load():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(root, "scripts", "autoloop_kpi.py")
    spec = importlib.util.spec_from_file_location("al_kpi_t", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestKpiRowSatisfied(unittest.TestCase):
    def setUp(self):
        self.m = _load()

    def test_numeric_met(self):
        self.assertTrue(
            self.m.kpi_row_satisfied(
                {"current": 90, "target": 80, "status": ""},
                current_override=90,
            )
        )

    def test_numeric_override(self):
        self.assertTrue(
            self.m.kpi_row_satisfied(
                {"current": 0, "target": 80, "status": ""},
                current_override=90,
            )
        )

    def test_exempt_status(self):
        self.assertTrue(
            self.m.kpi_row_satisfied(
                {"current": None, "target": None, "status": "豁免"}
            )
        )

    def test_missing_target_false(self):
        self.assertFalse(
            self.m.kpi_row_satisfied({"current": 5, "target": None, "status": ""})
        )


class TestResultsTsvLastRowFailClosed(unittest.TestCase):
    def setUp(self):
        self.m = _load()

    def test_variance_ge_2(self):
        st = {"results_tsv": [{"score_variance": "2.0", "confidence": "100"}]}
        fc, reason = self.m.results_tsv_last_row_fail_closed(st)
        self.assertTrue(fc)
        self.assertIn("score_variance", reason)

    def test_clean(self):
        st = {"results_tsv": [{"score_variance": "0.5", "confidence": "80"}]}
        fc, _ = self.m.results_tsv_last_row_fail_closed(st)
        self.assertFalse(fc)


class TestPlanGateIsExempt(unittest.TestCase):
    def setUp(self):
        self.m = _load()

    def test_cn_exempt(self):
        self.assertTrue(self.m.plan_gate_is_exempt({"status": "豁免"}))

    def test_en_exempt(self):
        self.assertTrue(self.m.plan_gate_is_exempt({"status": "Exempt"}))

    def test_not_exempt(self):
        self.assertFalse(self.m.plan_gate_is_exempt({"status": "未达标"}))


if __name__ == "__main__":
    unittest.main()
