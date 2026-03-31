#!/usr/bin/env python3
"""P1/P2/P3 回归：维度键对齐、bool 门禁、MCP init 契约。"""

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
MCP_SERVER = ROOT / "mcp-server" / "server.py"


def _load_score_module():
    path = SCRIPTS / "autoloop-score.py"
    spec = importlib.util.spec_from_file_location("al_score_regression", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _load_controller_module():
    path = SCRIPTS / "autoloop-controller.py"
    spec = importlib.util.spec_from_file_location("al_controller_regression", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _load_render_module():
    path = SCRIPTS / "autoloop-render.py"
    spec = importlib.util.spec_from_file_location("al_render_regression", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _phase_orient_captured_output(state, round_num=1):
    """运行 phase_orient，收集所有 print 输出（含 banner/info）。"""
    ctl = _load_controller_module()
    captured = []

    def cap(*args, **kwargs):
        captured.append(" ".join(str(a) for a in args))

    with patch("builtins.print", side_effect=cap):
        ctl.phase_orient("/tmp", state, round_num)
    return "\n".join(captured)


class TestBoolGateEval(unittest.TestCase):
    """P2: bool + == 须严格等于 threshold，不得对 float 用 truthiness。"""

    def setUp(self):
        self.score = _load_score_module()

    def test_eval_gate_raw_bias_float_not_equal_one(self):
        """_eval_gate 不对 float 做偏见归一；0.07 == 1 为假。"""
        gate_def = {
            "dim": "bias_check",
            "threshold": 1,
            "unit": "bool",
            "gate": "hard",
            "label": "偏见检查",
            "comparator": "==",
        }
        r = self.score._eval_gate(gate_def, 0.07, "")
        self.assertFalse(r["pass"])

    def test_score_bias_check_normalizes_float(self):
        """score_from_ssot：偏见分 <0.15 归一为 True 再过 bool 门禁。"""
        score = _load_score_module()
        base = {
            "plan": {"template": "T2"},
            "findings": {"rounds": []},
        }
        _, res_ok = score.score_from_ssot({
            **base,
            "iterations": [{"scores": {"bias_check": 0.05}}],
        })
        bias_ok = next(x for x in res_ok if x.get("dimension") == "bias_check")
        self.assertTrue(bias_ok.get("pass"))
        _, res_bad = score.score_from_ssot({
            **base,
            "iterations": [{"scores": {"bias_check": 0.2}}],
        })
        bias_bad = next(x for x in res_bad if x.get("dimension") == "bias_check")
        self.assertFalse(bias_bad.get("pass"))

    def test_bool_true_passes_eq_one(self):
        gate_def = {
            "dim": "sensitivity",
            "threshold": 1,
            "unit": "bool",
            "gate": "soft",
            "label": "敏感性",
            "comparator": "==",
        }
        r = self.score._eval_gate(gate_def, True, "")
        self.assertTrue(r["pass"])

    def test_int_one_passes_eq_one(self):
        gate_def = {
            "dim": "sensitivity",
            "threshold": 1,
            "unit": "bool",
            "gate": "soft",
            "label": "敏感性",
            "comparator": "==",
        }
        r = self.score._eval_gate(gate_def, 1, "")
        self.assertTrue(r["pass"])


class TestPlanGatesInit(unittest.TestCase):
    """P1: plan.gates dim 与 scorer dimension 一致（如 syntax 非 syntax_errors）。"""

    def test_t4_syntax_internal_dim(self):
        score = _load_score_module()
        gates = score.plan_gates_for_ssot_init("T4")
        dims = [g["dim"] for g in gates]
        self.assertIn("syntax", dims)
        self.assertNotIn("syntax_errors", dims)
        for g in gates:
            self.assertEqual(g["dimension"], g["dim"])
            self.assertIn("manifest_dimension", g)
            self.assertEqual(g["status"], "未达标")

    def test_state_init_populates_gates(self):
        """集成：autoloop-state init 写入非空 gates。"""
        d = tempfile.mkdtemp(prefix="altest_")
        self.addCleanup(lambda: shutil.rmtree(d, ignore_errors=True))
        rc = subprocess.run(
            [sys.executable, str(SCRIPTS / "autoloop-state.py"), "init", d, "T1", "goal"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(rc.returncode, 0, rc.stderr + rc.stdout)
        with open(os.path.join(d, "autoloop-state.json"), encoding="utf-8") as f:
            state = json.load(f)
        pg = state["plan"]["gates"]
        self.assertGreater(len(pg), 0)
        self.assertTrue(all("manifest_dimension" in g for g in pg))


class TestScoreJsonManifestDimension(unittest.TestCase):
    """C3: 评分结果含 manifest_dimension，与 gate-manifest 原始名一致。"""

    def test_eval_gate_includes_manifest_dimension(self):
        score = _load_score_module()
        gate_def = {
            "dim": "syntax",
            "manifest_dimension": "syntax_errors",
            "threshold": 0,
            "unit": "count",
            "gate": "hard",
            "label": "语法",
            "comparator": "==",
        }
        r = score._eval_gate(gate_def, 0, "")
        self.assertEqual(r.get("dimension"), "syntax")
        self.assertEqual(r.get("manifest_dimension"), "syntax_errors")


class TestValidatePlanGatesContract(unittest.TestCase):
    """C2: 旧 plan.gates 契约产生 warning。"""

    @staticmethod
    def _load_validate():
        path = SCRIPTS / "autoloop-validate.py"
        spec = importlib.util.spec_from_file_location("al_validate", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def test_warns_missing_manifest_dimension(self):
        mod = self._load_validate()
        w, e = [], []
        mod._check_plan_gates_contract(
            {"plan": {"gates": [{"dim": "coverage", "label": "覆盖率"}]}},
            w, e, strict=False,
        )
        self.assertTrue(any("manifest_dimension" in x for x in w))

    def test_warns_raw_manifest_dim(self):
        mod = self._load_validate()
        w, e = [], []
        mod._check_plan_gates_contract(
            {
                "plan": {
                    "gates": [
                        {
                            "dim": "syntax_errors",
                            "manifest_dimension": "syntax_errors",
                            "label": "x",
                        }
                    ]
                }
            },
            w, e, strict=False,
        )
        self.assertTrue(any("原始名" in x or "分裂" in x for x in w))

    def test_strict_dimension_only_gate_errors(self):
        mod = self._load_validate()
        w, e = [], []
        mod._check_plan_gates_contract(
            {"plan": {"gates": [{"dimension": "coverage", "label": "x"}]}},
            w, e, strict=True,
        )
        self.assertTrue(any("dim" in x for x in e))


class TestPhaseOrientThresholdNone(unittest.TestCase):
    """ORIENT：plan.gates[].threshold is None 时按 target vs 当前分分桶。"""

    def _base_state(self, scores, gates):
        return {
            "plan": {"template": "T1", "gates": gates},
            "iterations": [{"round": 1, "scores": scores}],
        }

    def test_kpi_met_goes_to_passed(self):
        state = self._base_state(
            {"kpi_x": 90},
            [
                {
                    "dim": "kpi_x",
                    "threshold": None,
                    "target": 80,
                    "label": "KPI X",
                    "gate": "soft",
                }
            ],
        )
        out = _phase_orient_captured_output(state)
        self.assertIn("PASSED", out)
        self.assertIn("KPI X", out)
        self.assertIn("PASS", out)

    def test_kpi_gap_buckets_by_percent(self):
        # gap 60% → CRITICAL
        s1 = self._base_state(
            {"kpi_a": 40},
            [{"dim": "kpi_a", "threshold": None, "target": 100, "label": "A"}],
        )
        self.assertIn("CRITICAL", _phase_orient_captured_output(s1))
        self.assertIn("60%", _phase_orient_captured_output(s1))

        # gap 30% → MODERATE (20–50)
        s2 = self._base_state(
            {"kpi_b": 70},
            [{"dim": "kpi_b", "threshold": None, "target": 100, "label": "B"}],
        )
        self.assertIn("MODERATE", _phase_orient_captured_output(s2))
        self.assertIn("30%", _phase_orient_captured_output(s2))

        # gap 12% → MINOR
        s3 = self._base_state(
            {"kpi_c": 88},
            [{"dim": "kpi_c", "threshold": None, "target": 100, "label": "C"}],
        )
        self.assertIn("MINOR", _phase_orient_captured_output(s3))
        self.assertIn("12%", _phase_orient_captured_output(s3))

    def test_no_target_lists_moderate(self):
        state = self._base_state(
            {"kpi_u": 5},
            [{"dim": "kpi_u", "threshold": None, "label": "U"}],
        )
        out = _phase_orient_captured_output(state)
        self.assertIn("未配置 target", out)

    def test_missing_cur_and_target(self):
        # scores 非空但缺少该 dim → cur is None 且 target is None
        state = self._base_state(
            {"other_dim": 1},
            [{"dim": "kpi_m", "threshold": None, "label": "M"}],
        )
        out = _phase_orient_captured_output(state)
        self.assertIn("待定义 KPI", out)

    def test_non_numeric_kpi_moderate(self):
        state = self._base_state(
            {"kpi_n": "bad"},
            [{"dim": "kpi_n", "threshold": None, "target": 10, "label": "N"}],
        )
        out = _phase_orient_captured_output(state)
        self.assertIn("KPI 非数值", out)


class TestGateManifestT4DefaultRounds(unittest.TestCase):
    """P2-04/T4：manifest 默认 OODA 轮次与交付阶段对齐（T4 瘦身后 Phase 1-5 = 5 轮）。"""

    def test_t4_is_five(self):
        path = ROOT / "references" / "gate-manifest.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(data["default_rounds"]["T4"], 5)


class TestScoreOverallFailClosed(unittest.TestCase):
    """autoloop-score：SSOT overall_pass 与 EVOLVE 一致纳入 TSV fail-closed。"""

    def test_gates_pass_but_tsv_blocks_overall(self):
        score = _load_score_module()
        results = [{"gate_type": "hard", "pass": True, "label": "x"}]
        state = {
            "results_tsv": [{"score_variance": "2.1", "confidence": "80"}],
        }
        out = score.results_to_json("T1", results, mode="ssot", state=state)
        self.assertTrue(out["gates_pass"])
        self.assertTrue(out["tsv_fail_closed"])
        self.assertFalse(out["overall_pass"])
        self.assertIsNotNone(out["fail_closed_reason"])


class TestLatestTsvFailClosed(unittest.TestCase):
    """EVOLVE：TSV fail-closed 否决仅凭门禁成功终止。"""

    def test_high_variance_triggers(self):
        ctl = _load_controller_module()
        st = {
            "results_tsv": [
                {"score_variance": "2.5", "confidence": "80"},
            ]
        }
        self.assertTrue(ctl._latest_tsv_fail_closed(st))

    def test_low_confidence_triggers(self):
        ctl = _load_controller_module()
        st = {"results_tsv": [{"score_variance": "0", "confidence": "40"}]}
        self.assertTrue(ctl._latest_tsv_fail_closed(st))

    def test_clean_row_false(self):
        ctl = _load_controller_module()
        st = {"results_tsv": [{"score_variance": "0.5", "confidence": "85"}]}
        self.assertFalse(ctl._latest_tsv_fail_closed(st))


class TestAddTsvRowVarianceGuard(unittest.TestCase):
    """P2-03：add-tsv-row 拒绝 fail-closed 行。"""

    def test_rejects_high_variance(self):
        td = tempfile.mkdtemp(prefix="al_tsv_")
        self.addCleanup(shutil.rmtree, td, ignore_errors=True)
        subprocess.run(
            [sys.executable, str(SCRIPTS / "autoloop-state.py"), "init", td, "T1", "t"],
            check=True,
            capture_output=True,
            text=True,
        )
        row = {
            "iteration": 1,
            "phase": "VERIFY",
            "status": "通过",
            "dimension": "coverage",
            "metric_value": 1,
            "delta": 0,
            "strategy_id": "—",
            "action_summary": "—",
            "side_effect": "—",
            "evidence_ref": "—",
            "unit_id": "—",
            "protocol_version": "1.0.0",
            "score_variance": "3",
            "confidence": "80",
            "details": "—",
        }
        r = subprocess.run(
            [
                sys.executable,
                str(SCRIPTS / "autoloop-state.py"),
                "add-tsv-row",
                td,
                json.dumps(row),
            ],
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(r.returncode, 0)


class TestE2EInitValidateStrict(unittest.TestCase):
    """P2-07：init 后 strict validate 可通过。"""

    def test_init_then_validate_strict(self):
        td = tempfile.mkdtemp(prefix="al_e2e_")
        self.addCleanup(shutil.rmtree, td, ignore_errors=True)
        subprocess.run(
            [sys.executable, str(SCRIPTS / "autoloop-state.py"), "init", td, "T1", "goal"],
            check=True,
            capture_output=True,
            text=True,
        )
        r = subprocess.run(
            [sys.executable, str(SCRIPTS / "autoloop-validate.py"), td, "--strict"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(r.returncode, 0, msg=r.stdout + r.stderr)


class TestMigrateDryRun(unittest.TestCase):
    """P1-08：migrate --dry-run 可执行。"""

    def test_migrate_prints_proposed_gates(self):
        td = tempfile.mkdtemp(prefix="al_mig_")
        self.addCleanup(shutil.rmtree, td, ignore_errors=True)
        subprocess.run(
            [sys.executable, str(SCRIPTS / "autoloop-state.py"), "init", td, "T2", "x"],
            check=True,
            capture_output=True,
            text=True,
        )
        r = subprocess.run(
            [
                sys.executable,
                str(SCRIPTS / "autoloop-state.py"),
                "migrate",
                td,
                "--dry-run",
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(r.returncode, 0)
        self.assertIn("SSOT", r.stdout)


class TestMcpControllerInitContract(unittest.TestCase):
    """P3: server.py 须在 init 时传 --template（源码契约）。"""

    def test_autoloop_controller_contains_init_template_argv(self):
        text = MCP_SERVER.read_text(encoding="utf-8")
        self.assertIn('"--template"', text)
        self.assertIn("mode == \"init\"", text)
        self.assertIn("template.strip()", text)

    def test_init_without_template_returns_json_error_snippet(self):
        text = MCP_SERVER.read_text(encoding="utf-8")
        self.assertIn('"success": False', text)
        self.assertIn("template", text.lower())


class TestPhaseArtifactsExtended(unittest.TestCase):
    """P0-01：阶段产物与 checkpoint 对齐。"""

    @staticmethod
    def _load_validate():
        path = SCRIPTS / "autoloop-validate.py"
        spec = importlib.util.spec_from_file_location("al_validate_pa", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def test_act_missing_strategy_strict_errors(self):
        mod = self._load_validate()
        err, warn = [], []
        st = {
            "plan": {"decide_act_handoff": {}},
            "iterations": [{"phase": "ACT", "strategy": {"strategy_id": ""}}],
        }
        mod._check_phase_artifacts("/tmp", st, err, warn, strict=True)
        self.assertTrue(any("strategy_id" in x for x in err), err)

    def test_synthesize_missing_scores_strict(self):
        mod = self._load_validate()
        err, warn = [], []
        st = {
            "plan": {"decide_act_handoff": {"strategy_id": "S01-x"}},
            "iterations": [{"phase": "SYNTHESIZE", "strategy": {"strategy_id": "S01-x"}, "scores": {}}],
        }
        mod._check_phase_artifacts("/tmp", st, err, warn, strict=True)
        self.assertTrue(any("scores" in x for x in err), err)

    def test_checkpoint_phase_mismatch_warns(self):
        mod = self._load_validate()
        td = tempfile.mkdtemp(prefix="al_ck_")
        self.addCleanup(lambda: shutil.rmtree(td, ignore_errors=True))
        ck = os.path.join(td, "checkpoint.json")
        with open(ck, "w", encoding="utf-8") as f:
            json.dump({"current_phase": "OBSERVE"}, f)
        st = {
            "plan": {},
            "iterations": [
                {"phase": "ACT", "strategy": {"strategy_id": "S01-x"}},
            ],
        }
        err, warn = [], []
        mod._check_phase_artifacts(td, st, err, warn, strict=False)
        self.assertTrue(any("checkpoint" in x for x in warn), warn)


class TestEvolveT4LinearPhases(unittest.TestCase):
    """P2-04：T4 + linear_phases 预算耗尽时暂停。"""

    def test_budget_pause_when_linear_incomplete(self):
        ctl = _load_controller_module()
        fake_state = {
            "plan": {
                "template": "T4",
                "template_mode": "linear_phases",
                "linear_delivery_complete": False,
                "budget": {"max_rounds": 1},
                "gates": [{"dim": "syntax", "threshold": 0, "gate": "hard", "label": "s"}],
            },
            "iterations": [{"scores": {"syntax": 1}}],
            "results_tsv": [],
        }
        detail = {
            "passed": False,
            "label": "syntax",
            "current": 1,
            "threshold": 0,
            "gate": "hard",
        }
        with patch.object(ctl, "load_state", return_value=fake_state):
            with patch.object(ctl, "check_gates_passed", return_value=(False, [detail])):
                with patch.object(ctl, "get_max_rounds", return_value=1):
                    d, r = ctl.phase_evolve("/tmp", fake_state, 1)
        self.assertEqual(d, "pause")
        self.assertTrue(any("linear_phases" in x for x in r), r)


class TestEvolveMultiStagnationStop(unittest.TestCase):
    """所有可监控维度均停滞且 hard 未全时 EVOLVE 决策为 stop（与 loop-protocol 一致）。"""

    def test_all_eligible_stagnating_stops(self):
        ctl = _load_controller_module()
        detail = {
            "dim": "coverage",
            "label": "覆盖率",
            "threshold": 85,
            "current": 50,
            "gate": "hard",
            "passed": False,
        }
        fake_state = {
            "plan": {
                "template": "T1",
                "budget": {"max_rounds": 99},
                "gates": [detail],
            },
            "iterations": [{"scores": {"coverage": 50}}],
            "results_tsv": [],
        }
        stag_ret = (
            [
                ("coverage", [50.0, 50.0, 50.0], "stagnating"),
                ("credibility", [40.0, 40.0, 40.0], "stagnating"),
            ],
            {"coverage", "credibility"},
        )
        with patch.object(ctl, "load_state", return_value=fake_state):
            with patch.object(ctl, "check_gates_passed", return_value=(False, [detail])):
                with patch.object(
                    ctl,
                    "detect_stagnation",
                    return_value=stag_ret,
                ):
                    with patch.object(ctl, "detect_oscillation", return_value=[]):
                        with patch("builtins.print"):
                            d, r = ctl.phase_evolve("/tmp", fake_state, 1)
        self.assertEqual(d, "stop")
        self.assertTrue(any("无法继续" in x for x in r), msg=r)

    def test_partial_stagnation_does_not_stop(self):
        ctl = _load_controller_module()
        detail_cov = {
            "dim": "coverage",
            "label": "覆盖率",
            "threshold": 85,
            "current": 50,
            "gate": "hard",
            "passed": False,
        }
        detail_cred = {
            "dim": "credibility",
            "label": "可信度",
            "threshold": 80,
            "current": 40,
            "gate": "hard",
            "passed": False,
        }
        fake_state = {
            "plan": {
                "template": "T1",
                "budget": {"max_rounds": 99},
                "gates": [detail_cov, detail_cred],
            },
            "iterations": [{"scores": {"coverage": 50, "credibility": 40}}],
            "results_tsv": [],
        }
        stag_ret = (
            [("coverage", [50.0, 50.0, 50.0], "stagnating")],
            {"coverage", "credibility"},
        )
        with patch.object(ctl, "load_state", return_value=fake_state):
            with patch.object(
                ctl,
                "check_gates_passed",
                return_value=(False, [detail_cov, detail_cred]),
            ):
                with patch.object(
                    ctl,
                    "detect_stagnation",
                    return_value=stag_ret,
                ):
                    with patch.object(ctl, "detect_oscillation", return_value=[]):
                        with patch("builtins.print"):
                            d, r = ctl.phase_evolve("/tmp", fake_state, 1)
        self.assertEqual(d, "continue")
        self.assertFalse(any("无法继续" in x for x in r), msg=r)

    def test_single_eligible_stagnating_does_not_global_stop(self):
        """T5 等仅 1 维 KPI 可监控时：该维停滞不触发「全体可监控维停滞→stop」。"""
        ctl = _load_controller_module()
        detail = {
            "dim": "kpi_target",
            "label": "KPI",
            "threshold": None,
            "target": 9.0,
            "current": 8.0,
            "gate": "hard",
            "passed": False,
        }
        fake_state = {
            "plan": {
                "template": "T5",
                "budget": {"max_rounds": 99},
                "gates": [detail],
            },
            "iterations": [{"scores": {"kpi_target": 8.0}}],
            "results_tsv": [],
            "findings": {"rounds": [{"round": 1, "findings": [{"summary": "x"}], "contradictions": []}]},
        }
        stag_ret = (
            [("kpi_target", [7.9, 8.0, 8.0], "stagnating")],
            {"kpi_target"},
        )
        with patch.object(ctl, "load_state", return_value=fake_state):
            with patch.object(ctl, "check_gates_passed", return_value=(False, [detail])):
                with patch.object(
                    ctl,
                    "detect_stagnation",
                    return_value=stag_ret,
                ):
                    with patch.object(ctl, "detect_oscillation", return_value=[]):
                        with patch("builtins.print"):
                            d, r = ctl.phase_evolve("/tmp", fake_state, 7)
        self.assertEqual(d, "continue")
        self.assertFalse(any("无法继续" in x for x in r), msg=r)


def _p208_t4_iteration(scores):
    """单轮迭代骨架，与 autoloop-state add-iteration 结构兼容，供 P2-08 fixture 使用。"""
    return {
        "round": 1,
        "start_time": "",
        "end_time": "",
        "status": "进行中",
        "phase": "EVOLVE",
        "scores": scores,
        "strategy": {
            "strategy_id": "S01-p208",
            "name": "",
            "description": "",
            "target_dimension": "",
        },
        "observe": {
            "gaps": [],
            "budget_remaining_pct": 0,
            "focus": "",
            "carryover": "",
        },
        "orient": {
            "gap_cause": "",
            "strategy": "",
            "scope_adjustment": "无",
            "expected_improvement": "",
        },
        "decide": {"actions": []},
        "act": {"records": [], "failures": []},
        "verify": {"score_updates": [], "verification_method": "", "new_issues": []},
        "synthesize": {
            "contradictions_found": [],
            "contradictions_resolved": [],
            "merged_data": [],
            "new_insights": [],
        },
        "evolve": {
            "termination": "继续",
            "next_focus": "",
            "strategy_adjustment": "无",
            "scope_change": "无",
        },
        "reflect": {
            "problem_registry": {"new": 0, "fixed": 0, "remaining": 0},
            "strategy_review": {"rating": 0, "verdict": "待验证", "reason": ""},
            "pattern_recognition": "",
            "lesson_learned": "",
            "next_round_guidance": "",
        },
        "findings": [],
        "evolution_decisions": [],
        "tsv_rows": [],
    }


class TestP208T4EvolveHardFailRound1(unittest.TestCase):
    """P2-08：T4 + 至少一条 hard 未达标 + 第 1 轮 EVOLVE 行为锁定。

    与 `references/gate-manifest.json` default_rounds.T4=5 一致：plan.budget.max_rounds 为 0 时
    get_max_rounds 退回 manifest 的 5，故 round_num=1 不会触发预算耗尽 stop。
    """

    def _fixture_dir(self, scores, results_tsv):
        td = tempfile.mkdtemp(prefix="al_p208_")
        self.addCleanup(lambda: shutil.rmtree(td, ignore_errors=True))
        subprocess.run(
            [sys.executable, str(SCRIPTS / "autoloop-state.py"), "init", td, "T4", "p208"],
            check=True,
            capture_output=True,
            text=True,
        )
        path = os.path.join(td, "autoloop-state.json")
        with open(path, encoding="utf-8") as f:
            st = json.load(f)
        st["iterations"] = [_p208_t4_iteration(scores)]
        st["results_tsv"] = results_tsv
        st["plan"]["budget"]["current_round"] = 1
        st["plan"]["budget"]["max_rounds"] = 0
        with open(path, "w", encoding="utf-8") as f:
            json.dump(st, f, ensure_ascii=False, indent=2)
        return td

    def test_continue_when_hard_gate_fails_round1(self):
        """hard 未通过时不得因「全部门禁通过」而 stop，第 1 轮应为 continue。"""
        scores = {
            "syntax": 2,
            "p1_all": 0,
            "service_health": 1,
            "user_acceptance": 1,
        }
        td = self._fixture_dir(scores, [])
        ctl = _load_controller_module()
        with patch("builtins.print"):
            decision, reasons = ctl.phase_evolve(td, {}, 1)
        self.assertEqual(
            decision,
            "continue",
            msg="hard 未达标且首轮不应 stop/pause（无振荡/停滞/预算用尽）；got reasons={}".format(
                reasons
            ),
        )
        self.assertFalse(
            any("所有 hard gate 已通过" in r for r in reasons),
            msg=reasons,
        )

    def test_tsv_fail_closed_blocks_success_stop_when_scores_pass_round1(self):
        """门禁数值全过但 TSV fail-closed 时不得成功终止（防误报全通过）。"""
        scores = {
            "syntax": 0,
            "p1_all": 0,
            "service_health": 1,
            "user_acceptance": 1,
        }
        tsv_row = {
            "iteration": 1,
            "phase": "VERIFY",
            "status": "通过",
            "dimension": "syntax",
            "metric_value": 0,
            "delta": 0,
            "strategy_id": "S01-p208",
            "action_summary": "—",
            "side_effect": "无",
            "evidence_ref": "—",
            "unit_id": "—",
            "protocol_version": "1.0.0",
            "score_variance": "2.5",
            "confidence": "80",
            "details": "p208",
        }
        td = self._fixture_dir(scores, [tsv_row])
        ctl = _load_controller_module()
        with patch("builtins.print"):
            decision, reasons = ctl.phase_evolve(td, {}, 1)
        self.assertNotEqual(
            decision,
            "stop",
            msg="TSV 方差 fail-closed 时不应 stop；reasons={}".format(reasons),
        )
        self.assertTrue(
            any("TSV" in r and "fail-closed" in r for r in reasons)
            or any("方差" in r for r in reasons),
            msg=reasons,
        )
        self.assertFalse(
            any("所有 hard gate 已通过" in r for r in reasons),
            msg=reasons,
        )


class TestE2EInitScoreValidate(unittest.TestCase):
    """P2-07：init → add-iteration → findings → score → validate strict。"""

    def test_chain(self):
        td = tempfile.mkdtemp(prefix="al_sc_")
        self.addCleanup(lambda: shutil.rmtree(td, ignore_errors=True))
        subprocess.run(
            [sys.executable, str(SCRIPTS / "autoloop-state.py"), "init", td, "T1", "g"],
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            [sys.executable, str(SCRIPTS / "autoloop-state.py"), "add-iteration", td],
            check=True,
            capture_output=True,
            text=True,
        )
        path = os.path.join(td, "autoloop-state.json")
        with open(path, encoding="utf-8") as f:
            st = json.load(f)
        st["findings"]["rounds"] = [
            {
                "round": 1,
                "findings": [
                    {
                        "dimension": "coverage",
                        "summary": "cov",
                        "source": "https://a.com https://b.com",
                    },
                    {
                        "dimension": "credibility",
                        "summary": "cred",
                        "source": "https://x.com",
                    },
                    {
                        "dimension": "consistency",
                        "summary": "con",
                        "source": "src",
                    },
                    {
                        "dimension": "completeness",
                        "summary": "cmp",
                        "source": "https://z.com",
                    },
                ],
            }
        ]
        with open(path, "w", encoding="utf-8") as f:
            json.dump(st, f, ensure_ascii=False, indent=2)
        sc = subprocess.run(
            [sys.executable, str(SCRIPTS / "autoloop-score.py"), td, "--json"],
            capture_output=True,
            text=True,
        )
        self.assertIn('"gates"', sc.stdout)
        va = subprocess.run(
            [sys.executable, str(SCRIPTS / "autoloop-validate.py"), td, "--strict"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(va.returncode, 0, msg=va.stdout + va.stderr)


class TestT5KpiScoreMatchesController(unittest.TestCase):
    """P0-01：kpi_target 与 check_gates_passed 均优先 iterations[-1].scores。"""

    def test_scores_override_when_plan_current_null(self):
        score_m = _load_score_module()
        ctl = _load_controller_module()
        state = {
            "plan": {
                "template": "T5",
                "gates": [{
                    "dim": "latency",
                    "dimension": "latency",
                    "threshold": None,
                    "target": 80,
                    "gate": "hard",
                    "status": "未达标",
                    "current": None,
                }],
            },
            "iterations": [{"scores": {"latency": 90}}],
            "findings": {"rounds": []},
        }
        _, res = score_m.score_from_ssot(state)
        kg = next(x for x in res if x.get("dimension") == "kpi_target")
        ap, det = ctl.check_gates_passed(state)
        self.assertTrue(kg["pass"], msg=kg)
        self.assertTrue(ap)
        self.assertTrue(det[0]["passed"])


class TestGetCurrentScoresT5GateFallback(unittest.TestCase):
    """T5 新轮 scores 空时从 plan.gates[].current 回填（ORIENT 用）。"""

    def test_empty_iteration_scores_use_gate_current(self):
        ctl = _load_controller_module()
        st = {
            "plan": {
                "template": "T5",
                "gates": [
                    {
                        "dim": "kpi_target",
                        "dimension": "kpi_target",
                        "current": 8.0,
                        "target": 9.0,
                        "threshold": None,
                        "gate": "hard",
                    }
                ],
            },
            "iterations": [{"round": 8, "scores": {}}],
        }
        self.assertEqual(ctl.get_current_scores(st), {"kpi_target": 8.0})

    def test_nonempty_scores_unchanged(self):
        ctl = _load_controller_module()
        st = {
            "plan": {
                "template": "T5",
                "gates": [{"dim": "kpi_target", "current": 7.0}],
            },
            "iterations": [{"round": 8, "scores": {"kpi_target": 8.5}}],
        }
        self.assertEqual(ctl.get_current_scores(st), {"kpi_target": 8.5})


class TestDetectStagnationT5KpiSkip(unittest.TestCase):
    """P1-01：threshold=null 且 KPI 已满足的维度不参与停滞。"""

    def test_met_kpi_dimension_excluded(self):
        ctl = _load_controller_module()
        gates = [{
            "dim": "latency",
            "dimension": "latency",
            "threshold": None,
            "target": 80,
            "status": "未达标",
            "gate": "hard",
        }]
        history = [{"latency": 90.0}, {"latency": 90.0}, {"latency": 90.0}]
        r, el = ctl.detect_stagnation(history, gates, template_key="T5")
        self.assertEqual(r, [])
        self.assertEqual(el, set())


class TestValidateReflectStrict(unittest.TestCase):
    """E-01：strict + REFLECT 要求 strategy_id 与 effect。"""

    def _mod(self):
        path = SCRIPTS / "autoloop-validate.py"
        spec = importlib.util.spec_from_file_location("al_val_refl", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def test_reflect_strict_missing_keys_errors(self):
        mod = self._mod()
        err, warn = [], []
        st = {
            "plan": {},
            "iterations": [{"phase": "REFLECT", "reflect": {"strategy_id": "", "effect": ""}}],
        }
        mod._check_phase_artifacts("/tmp", st, err, warn, strict=True)
        self.assertTrue(any("strategy_id" in x and "effect" in x for x in err), err)

    def test_reflect_strict_requires_delta_or_likert(self):
        mod = self._mod()
        err, warn = [], []
        st = {
            "plan": {},
            "iterations": [
                {
                    "phase": "REFLECT",
                    "strategy": {"strategy_id": "S01-x"},
                    "scores": {"coverage": 1.0},
                    "reflect": {"strategy_id": "S01-x", "effect": "保持"},
                }
            ],
        }
        mod._check_phase_artifacts("/tmp", st, err, warn, strict=True)
        self.assertTrue(any("strict 要求 reflect 含 delta" in x for x in err), err)

    def test_reflect_strict_ok_with_delta(self):
        mod = self._mod()
        err, warn = [], []
        st = {
            "plan": {},
            "iterations": [
                {
                    "phase": "REFLECT",
                    "strategy": {"strategy_id": "S01-x"},
                    "scores": {"coverage": 1.0},
                    "reflect": {
                        "strategy_id": "S01-x",
                        "effect": "保持",
                        "delta": 0.25,
                    },
                }
            ],
        }
        mod._check_phase_artifacts("/tmp", st, err, warn, strict=True)
        self.assertFalse(any("strict 要求 reflect 含 delta" in x for x in err), err)

    def test_side_effect_vs_handoff_strict(self):
        mod = self._mod()
        err, warn = [], []
        st = {
            "plan": {
                "decide_act_handoff": {"impacted_dimensions": ["coverage"], "strategy_id": "S01-x"},
            },
            "results_tsv": [
                {
                    "iteration": 1,
                    "phase": "VERIFY",
                    "side_effect": "无",
                    "strategy_id": "S01-x",
                    "status": "通过",
                    "dimension": "coverage",
                    "metric_value": 0,
                    "delta": 0,
                    "action_summary": "—",
                    "evidence_ref": "—",
                    "unit_id": "—",
                    "protocol_version": "1.0.0",
                    "score_variance": "0",
                    "confidence": "80",
                    "details": "—",
                }
            ],
        }
        mod._check_side_effect_vs_handoff(st, err, warn, strict=True)
        self.assertTrue(err, err)


class TestScoreDetectModeSidecar(unittest.TestCase):
    """findings.md 同目录存在 autoloop-state.json 时走 SSOT 路径。"""

    def test_md_path_with_sidecar_uses_ssot(self):
        score = _load_score_module()
        with tempfile.TemporaryDirectory() as d:
            md = os.path.join(d, "autoloop-findings.md")
            st_path = os.path.join(d, "autoloop-state.json")
            with open(md, "w", encoding="utf-8") as f:
                f.write("# findings\n")
            with open(st_path, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "plan": {"template": "T1"},
                        "findings": {"rounds": []},
                        "iterations": [],
                    },
                    f,
                )
            mode, data, ctx = score.detect_mode(md)
            self.assertEqual(mode, "ssot")
            self.assertEqual(data.get("plan", {}).get("template"), "T1")
            self.assertEqual(os.path.abspath(ctx), os.path.abspath(d))


class TestPhaseActStrict(unittest.TestCase):
    """ACT 在 strict 下对缺失 handoff 与 run_loop 一致。"""

    def test_missing_handoff_strict_false_continues(self):
        ctl = _load_controller_module()
        state = {"plan": {"template": "T1"}}
        with patch.object(ctl, "banner"):
            with patch.object(ctl, "info"):
                with patch.object(ctl, "prompt_block"):
                    ok = ctl.phase_act("/tmp/w", state, 1, strict=False)
        self.assertTrue(ok)

    def test_missing_handoff_strict_true_aborts(self):
        ctl = _load_controller_module()
        state = {"plan": {"template": "T1"}}
        with patch.object(ctl, "banner"):
            with patch.object(ctl, "error"):
                with patch.object(ctl, "prompt_block"):
                    ok = ctl.phase_act("/tmp/w", state, 1, strict=True)
        self.assertFalse(ok)


class TestReflectExperienceWriteDelta(unittest.TestCase):
    """经验库 write 仅用 delta；Likert 不触发 run_tool。"""

    def test_only_rating_skips_experience_write(self):
        ctl = _load_controller_module()
        state = {
            "iterations": [
                {
                    "reflect": {
                        "strategy_id": "S01-x",
                        "effect": "保持",
                        "rating_1_to_5": 4,
                    }
                }
            ]
        }
        with patch.object(ctl, "info"):
            with patch.object(ctl, "run_tool") as rt:
                ctl._maybe_reflect_experience_write("/w", state, "T1")
        rt.assert_not_called()

    def test_legacy_score_one_to_five_skips(self):
        ctl = _load_controller_module()
        state = {
            "iterations": [
                {"reflect": {"strategy_id": "S01-x", "effect": "避免", "score": 3}}
            ]
        }
        with patch.object(ctl, "info"):
            with patch.object(ctl, "run_tool") as rt:
                ctl._maybe_reflect_experience_write("/w", state, "T1")
        rt.assert_not_called()

    def test_delta_calls_experience_write(self):
        ctl = _load_controller_module()
        state = {
            "iterations": [
                {"reflect": {"strategy_id": "S01-x", "effect": "保持", "delta": 0.5}}
            ]
        }
        with patch.object(ctl, "info"):
            with patch.object(ctl, "run_tool", return_value=("", 0)) as rt:
                ctl._maybe_reflect_experience_write("/w", state, "T1")
        rt.assert_called_once()
        call = rt.call_args
        self.assertEqual(call[0][0], "autoloop-experience.py")
        self.assertIn("--score", call[0][1])
        self.assertIn("0.5", call[0][1])


class TestAddFindingSummaryField(unittest.TestCase):
    """add-finding 接受 summary（无 content）。"""

    def test_summary_only_ok(self):
        with tempfile.TemporaryDirectory() as d:
            subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "autoloop-state.py"),
                    "init",
                    d,
                    "T1",
                    "goal",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "autoloop-state.py"),
                    "add-iteration",
                    d,
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            payload = json.dumps(
                {"dimension": "coverage", "summary": "short note for schema parity"}
            )
            r = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "autoloop-state.py"),
                    "add-finding",
                    d,
                    payload,
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(r.returncode, 0, r.stderr + r.stdout)


class TestGetMaxRoundsT6Items(unittest.TestCase):
    """P-04：T6 按 items×2 推导默认 max_rounds（有上限）。"""

    def test_items_times_two_capped(self):
        ctl = _load_controller_module()
        st = {
            "plan": {
                "template": "T6",
                "budget": {"max_rounds": 0},
                "generation_items": 10,
            }
        }
        self.assertEqual(ctl.get_max_rounds(st), 20)
        st2 = {
            "plan": {
                "template": "T6",
                "budget": {"max_rounds": 0},
                "template_params": {"items": 80},
            }
        }
        self.assertEqual(ctl.get_max_rounds(st2), 99)


class TestPlanGateExemptAndCrossDim(unittest.TestCase):
    """豁免 rollup；跨维回归（handoff.impacted_dimensions）。"""

    def test_check_gates_exempt_hard_passes(self):
        ctl = _load_controller_module()
        state = {
            "plan": {
                "template": "T7",
                "gates": [
                    {
                        "dim": "reliability_score",
                        "dimension": "reliability_score",
                        "threshold": 8,
                        "comparator": ">=",
                        "gate": "hard",
                        "unit": "/10",
                        "status": "豁免",
                        "label": "可靠性",
                    },
                ],
            },
            "iterations": [{"scores": {"reliability_score": 3.0}}],
        }
        ok, details = ctl.check_gates_passed(state)
        self.assertTrue(ok)
        self.assertTrue(details[0]["passed"])

    def test_detect_cross_dimension_regression_with_handoff(self):
        ctl = _load_controller_module()
        state = {
            "plan": {
                "template": "T7",
                "decide_act_handoff": {
                    "impacted_dimensions": ["reliability_score"],
                },
                "gates": [
                    {
                        "dim": "reliability_score",
                        "threshold": 8,
                        "comparator": ">=",
                        "gate": "hard",
                        "unit": "/10",
                        "label": "可靠性",
                    },
                ],
            },
            "iterations": [
                {"scores": {"reliability_score": 9.0}},
                {"scores": {"reliability_score": 7.0}},
            ],
        }
        hit, dims = ctl.detect_cross_dimension_regression(state)
        self.assertTrue(hit)
        self.assertIn("reliability_score", dims)

    def test_detect_cross_dimension_regression_infers_without_handoff(self):
        ctl = _load_controller_module()
        state = {
            "plan": {
                "template": "T7",
                "gates": [
                    {
                        "dim": "reliability_score",
                        "threshold": 8,
                        "comparator": ">=",
                        "gate": "hard",
                        "unit": "/10",
                        "label": "可靠性",
                    },
                ],
            },
            "iterations": [
                {"scores": {"reliability_score": 9.0}},
                {"scores": {"reliability_score": 7.0}},
            ],
        }
        hit, dims = ctl.detect_cross_dimension_regression(state)
        self.assertTrue(hit)
        self.assertIn("reliability_score", dims)


class TestStrictEvolveFindingsGate(unittest.TestCase):
    """STRICT：EVOLVE 前须已有 finding（评审建议 #4）。"""

    def test_strict_evolve_requires_findings_false(self):
        ctl = _load_controller_module()
        state = {"iterations": [{"scores": {}}], "findings": {"rounds": []}}
        self.assertFalse(ctl._strict_evolve_requires_findings(state))

    def test_strict_evolve_requires_findings_from_iterations(self):
        ctl = _load_controller_module()
        state = {
            "iterations": [{"findings": [{"id": "f1"}]}],
            "findings": {"rounds": []},
        }
        self.assertTrue(ctl._strict_evolve_requires_findings(state))

    def test_strict_evolve_requires_findings_from_rounds(self):
        ctl = _load_controller_module()
        state = {
            "iterations": [],
            "findings": {"rounds": [{"round": 1, "findings": [{"id": "x"}]}]},
        }
        self.assertTrue(ctl._strict_evolve_requires_findings(state))

    def test_findings_md_protocol_version_snippet(self):
        ctl = _load_controller_module()
        text = "# x\n协议版本: 2.1.0\n"
        self.assertEqual(ctl._findings_md_protocol_version(text), "2.1.0")

    def test_phase_evolve_strict_pauses_without_findings(self):
        ctl = _load_controller_module()
        disk_state = {
            "iterations": [{"round": 1, "scores": {}}],
            "findings": {"rounds": []},
            "plan": {"template": "T5", "gates": []},
            "metadata": {},
        }
        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, "autoloop-state.json")
            with open(p, "w", encoding="utf-8") as f:
                json.dump(disk_state, f)
            with patch("builtins.print"):
                decision, reasons = ctl.phase_evolve(td, disk_state, 1, strict=True)
            self.assertEqual(decision, "pause")
            self.assertTrue(any("finding" in r.lower() for r in reasons))

    def test_phase_evolve_strict_pauses_when_tsv_round_mismatch(self):
        ctl = _load_controller_module()
        disk_state = {
            "iterations": [{"round": 1, "scores": {}, "findings": [{"id": "f1"}]}],
            "findings": {"rounds": [{"round": 1, "findings": [{"id": "x"}]}]},
            "plan": {"template": "T5", "gates": []},
            "results_tsv": [{"iteration": 99, "score_variance": "0", "confidence": "100"}],
            "metadata": {},
        }
        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, "autoloop-state.json")
            with open(p, "w", encoding="utf-8") as f:
                json.dump(disk_state, f)
            with patch("builtins.print"):
                decision, reasons = ctl.phase_evolve(td, disk_state, 1, strict=True)
            self.assertEqual(decision, "pause")
            self.assertTrue(any("TSV" in r or "iteration" in r for r in reasons), msg=reasons)


def _load_validate_module():
    path = SCRIPTS / "autoloop-validate.py"
    spec = importlib.util.spec_from_file_location("al_validate_side", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestSideEffectHandoffCoverage(unittest.TestCase):
    """strict：side_effect 须覆盖 handoff.impacted_dimensions（token 级）。"""

    def test_covers_by_full_or_token(self):
        val = _load_validate_module()
        self.assertTrue(
            val._side_effect_text_covers_dimension("kpi_target; reliability", "kpi_target")
        )
        self.assertTrue(
            val._side_effect_text_covers_dimension("reliability noted", "reliability_score")
        )
        self.assertFalse(val._side_effect_text_covers_dimension("kpi only", "maintainability"))

    def test_check_side_effect_strict_missing_dim(self):
        val = _load_validate_module()
        state = {
            "plan": {
                "decide_act_handoff": {
                    "impacted_dimensions": ["kpi_target", "maintainability"],
                }
            },
            "results_tsv": [{"side_effect": "kpi_target only"}],
        }
        err, warn = [], []
        val._check_side_effect_vs_handoff(state, err, warn, strict=True)
        self.assertTrue(any("未覆盖" in e for e in err))


class TestFindingsMdFourLayerStats(unittest.TestCase):
    """OBSERVE：findings.md 四层 H2 节内表格行估计。"""

    def test_four_layer_counts_pipe_tables(self):
        ctl = _load_controller_module()
        md = """# x
## 问题清单
| a | b |
| --- | --- |
| 1 | 2 |
## 策略评估
| u | v |
| --- | --- |
| 3 | 4 |
## 模式识别
| p | q |
| --- | --- |
| 5 | 6 |
## 经验教训
| r | s |
| --- | --- |
| 7 | 8 |
"""
        st = ctl._findings_md_four_layer_table_stats(md)
        self.assertEqual(st.get("L1问题清单"), 1)
        self.assertEqual(st.get("L2策略评估"), 1)
        self.assertEqual(st.get("L3模式识别"), 1)
        self.assertEqual(st.get("L4经验教训"), 1)


class TestRenderFindingsReflectFooter(unittest.TestCase):
    """render_findings 末尾追加四层表，OBSERVE 可计数。"""

    def test_render_appends_four_layer_tables(self):
        rmod = _load_render_module()
        ctl = _load_controller_module()
        td = tempfile.mkdtemp(prefix="al_rf_")
        self.addCleanup(shutil.rmtree, td, ignore_errors=True)
        rmod.render_findings(
            {
                "metadata": {"protocol_version": "2.0.0"},
                "findings": {"executive_summary": {"topic": "待填写"}, "rounds": []},
            },
            td,
        )
        path = os.path.join(td, "autoloop-findings.md")
        self.assertTrue(os.path.isfile(path))
        text = Path(path).read_text(encoding="utf-8")
        self.assertIn("## 问题清单（REFLECT 第 1 层）", text)
        self.assertIn("协议版本（findings 侧）: 2.0.0", text)
        stats = ctl._findings_md_four_layer_table_stats(text)
        self.assertGreaterEqual(stats.get("L1问题清单", 0), 1)
        self.assertGreaterEqual(stats.get("L4经验教训", 0), 1)


class TestRenderPanorama(unittest.TestCase):
    """render_panorama 全景视图输出正确。"""

    def _make_state(self):
        return {
            "metadata": {"protocol_version": "2.0.0", "completion_authority": "human_review"},
            "plan": {
                "task_id": "test-task-001",
                "template": "T3",
                "goal": "测试全景视图",
                "status": "进行中",
                "budget": {"max_rounds": 10, "current_round": 3, "time_limit": "无限制"},
                "gates": [
                    {
                        "dim": "coverage",
                        "dimension": "coverage",
                        "gate": "hard",
                        "target": 7.0,
                        "current": 7.2,
                        "status": "达标",
                        "unit": "heuristic",
                    }
                ],
            },
            "iterations": [
                {
                    "round": 1,
                    "phase": "VERIFY",
                    "status": "完成",
                    "scores": {"coverage": 6.5},
                    "strategy": {"strategy_id": "S01", "name": "初始策略", "description": "覆盖率提升"},
                    "reflect": {"lesson_learned": "需要更多测试", "strategy_review": {"rating": 4, "verdict": "有效"}},
                },
                {
                    "round": 2,
                    "phase": "VERIFY",
                    "status": "完成",
                    "scores": {"coverage": 7.0},
                    "strategy": {"strategy_id": "S02", "name": "深度策略", "description": "补充边界"},
                    "reflect": {"lesson_learned": "边界覆盖有效", "strategy_review": {"rating": 5, "verdict": "有效"}},
                },
                {
                    "round": 3,
                    "phase": "ACT",
                    "status": "进行中",
                    "scores": {"coverage": 7.2},
                    "strategy": {"strategy_id": "S03", "name": "巩固策略", "description": "回归修复"},
                    "reflect": {"lesson_learned": "", "strategy_review": {"rating": 0, "verdict": ""}},
                },
            ],
            "findings": {
                "executive_summary": {"topic": "测试", "total_rounds": 3},
                "rounds": [],
                "problem_tracker": [
                    {"id": "P-01", "description": "未覆盖模块 X", "status": "open"},
                    {"id": "P-02", "description": "已修复的问题", "status": "fixed"},
                ],
            },
        }

    def test_panorama_basic_output(self):
        rmod = _load_render_module()
        state = self._make_state()
        import io
        from contextlib import redirect_stdout
        buf = io.StringIO()
        with redirect_stdout(buf):
            result = rmod.render_panorama(state)
        output = buf.getvalue()
        # 基本信息
        self.assertIn("test-task-001", output)
        self.assertIn("T3", output)
        self.assertIn("Round 3/10", output)
        # 门禁
        self.assertIn("coverage", output)
        self.assertIn("7.2", output)
        self.assertIn("7.0", output)
        # 趋势 (近3轮 6.5→7.0→7.2)
        self.assertIn("6.5", output)
        self.assertIn("↑", output)
        # 策略
        self.assertIn("S03", output)
        # 未解决问题
        self.assertIn("P-01", output)
        self.assertIn("未覆盖模块 X", output)
        # 已修复的不应在 open 列表
        self.assertNotIn("P-02", output)
        # 资源
        self.assertIn("轮次: 3/10 (30%)", output)
        self.assertIn("human_review", output)

    def test_panorama_no_rounds(self):
        rmod = _load_render_module()
        state = {
            "metadata": {},
            "plan": {
                "task_id": "empty-task",
                "template": "T1",
                "status": "初始化",
                "budget": {"max_rounds": 0, "current_round": 0},
                "gates": [],
            },
            "iterations": [],
            "findings": {"executive_summary": {"topic": "待填写"}, "rounds": [], "problem_tracker": []},
        }
        import io
        from contextlib import redirect_stdout
        buf = io.StringIO()
        with redirect_stdout(buf):
            rmod.render_panorama(state)
        output = buf.getvalue()
        self.assertIn("empty-task", output)
        self.assertIn("T1", output)
        self.assertIn("轮次: 0 (无上限)", output)

    def test_panorama_returns_string(self):
        rmod = _load_render_module()
        state = self._make_state()
        import io
        from contextlib import redirect_stdout
        buf = io.StringIO()
        with redirect_stdout(buf):
            result = rmod.render_panorama(state)
        self.assertIsInstance(result, str)
        self.assertIn("test-task-001", result)


if __name__ == "__main__":
    unittest.main()
