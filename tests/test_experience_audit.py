#!/usr/bin/env python3
"""P2-05: audit 子命令 — 持续学习闭环自动审计。"""

import importlib.util
import os
import shutil
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"

REGISTRY_TEMPLATE = """\
# Experience Registry — 全局经验库

## 全局策略效果库

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
    """规则 1: use_count>=4, success_rate>80%, status=推荐 → 候选默认"""

    def setUp(self):
        self.td = tempfile.mkdtemp(prefix="al_audit_")
        self.mod = _load_experience()

    def tearDown(self):
        shutil.rmtree(self.td, ignore_errors=True)

    def test_promote_recommended_to_candidate_default(self):
        row = "| S01-test | T1 | cov | [保持] @2026-03-20 desc | 1.5 | — | 5 | 90% | 推荐 |"
        reg = _make_registry(self.td, row)
        result = self.mod.cmd_audit(reg, dry_run=True)
        self.assertEqual(len(result), 1)
        self.assertIn("候选默认", result[0]["action"])

    def test_no_promote_if_use_count_below_4(self):
        row = "| S02-test | T1 | cov | [保持] @2026-03-20 desc | 1 | — | 3 | 90% | 推荐 |"
        reg = _make_registry(self.td, row)
        result = self.mod.cmd_audit(reg, dry_run=True)
        # use_count=3 < 4, should not suggest promotion
        promote = [r for r in result if "候选默认" in r["action"]]
        self.assertEqual(len(promote), 0)

    def test_no_promote_if_success_rate_not_above_80(self):
        row = "| S03-test | T1 | cov | [保持] @2026-03-20 desc | 1 | — | 5 | 80% | 推荐 |"
        reg = _make_registry(self.td, row)
        result = self.mod.cmd_audit(reg, dry_run=True)
        promote = [r for r in result if "候选默认" in r["action"]]
        self.assertEqual(len(promote), 0, "80% is not >80%, should not promote")


class TestAuditDeprecate(unittest.TestCase):
    """规则 2: use_count>=3, success_rate<30%, status!=已废弃 → 已废弃"""

    def setUp(self):
        self.td = tempfile.mkdtemp(prefix="al_audit_")
        self.mod = _load_experience()

    def tearDown(self):
        shutil.rmtree(self.td, ignore_errors=True)

    def test_deprecate_low_success_rate(self):
        row = "| S04-test | T2 | acc | [避免] @2026-03-20 desc | -0.5 | — | 4 | 20% | 观察 |"
        reg = _make_registry(self.td, row)
        result = self.mod.cmd_audit(reg, dry_run=True)
        self.assertEqual(len(result), 1)
        self.assertIn("已废弃", result[0]["action"])

    def test_skip_already_deprecated(self):
        row = "| S05-test | T2 | acc | [避免] @2026-03-20 desc | -1 | — | 5 | 10% | 已废弃 |"
        reg = _make_registry(self.td, row)
        result = self.mod.cmd_audit(reg, dry_run=True)
        deprecate = [r for r in result if "已废弃" in r["action"]]
        self.assertEqual(len(deprecate), 0, "Already deprecated, should not suggest again")


class TestAuditDecayToObservation(unittest.TestCase):
    """规则 3: status=推荐, 最后验证 >90天前 → 降为观察"""

    def setUp(self):
        self.td = tempfile.mkdtemp(prefix="al_audit_")
        self.mod = _load_experience()

    def tearDown(self):
        shutil.rmtree(self.td, ignore_errors=True)

    def test_decay_old_recommended(self):
        # 91 days ago from today
        row = "| S06-test | T3 | qual | [保持] @2025-12-01 old strategy | 0.5 | — | 2 | 60% | 推荐 |"
        reg = _make_registry(self.td, row)
        result = self.mod.cmd_audit(reg, dry_run=True)
        decay = [r for r in result if "观察" in r["action"]]
        self.assertEqual(len(decay), 1)

    def test_no_decay_recent(self):
        row = "| S07-test | T3 | qual | [保持] @2026-03-25 recent | 0.5 | — | 2 | 60% | 推荐 |"
        reg = _make_registry(self.td, row)
        result = self.mod.cmd_audit(reg, dry_run=True)
        decay = [r for r in result if "观察" in r["action"]]
        self.assertEqual(len(decay), 0, "Recent strategy should not decay")


class TestAuditNoSuggestions(unittest.TestCase):
    """无需调整的场景"""

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
            "| S08-test | T1 | cov | [保持] @2026-03-20 ok | 0.5 | — | 2 | 60% | 观察 |\n"
            "| S09-test | T2 | acc | [保持] @2026-03-20 fine | 1.0 | — | 3 | 70% | 推荐 |"
        )
        reg = _make_registry(self.td, rows)
        result = self.mod.cmd_audit(reg, dry_run=True)
        self.assertEqual(len(result), 0, "All strategies are healthy")


class TestAuditExecuteMode(unittest.TestCase):
    """非 dry-run 模式：执行变更并写审计日志"""

    def setUp(self):
        self.td = tempfile.mkdtemp(prefix="al_audit_")
        self.mod = _load_experience()

    def tearDown(self):
        shutil.rmtree(self.td, ignore_errors=True)

    def test_execute_writes_changes_and_audit(self):
        row = "| S10-test | T1 | cov | [保持] @2026-03-20 desc | 1.5 | — | 5 | 90% | 推荐 |"
        reg = _make_registry(self.td, row)
        result = self.mod.cmd_audit(reg, dry_run=False)
        self.assertEqual(len(result), 1)

        # Verify main table was updated
        with open(reg, encoding="utf-8") as f:
            content = f.read()
        rows = self.mod._parse_strategy_table(content)
        s10 = [r for r in rows if r.get("strategy_id") == "S10-test"]
        self.assertEqual(len(s10), 1)
        self.assertEqual(s10[0]["status"], "候选默认")

        # Verify audit log was written
        audit_path = self.mod._audit_path(reg)
        self.assertTrue(os.path.isfile(audit_path))
        with open(audit_path, encoding="utf-8") as f:
            audit_content = f.read()
        self.assertIn("audit", audit_content)
        self.assertIn("S10-test", audit_content)


class TestAuditRulePriority(unittest.TestCase):
    """规则优先级：晋升/淘汰优先于衰减"""

    def setUp(self):
        self.td = tempfile.mkdtemp(prefix="al_audit_")
        self.mod = _load_experience()

    def tearDown(self):
        shutil.rmtree(self.td, ignore_errors=True)

    def test_promote_beats_decay(self):
        """推荐+高成功率+高使用次数：即使超90天也应晋升而非降级"""
        row = "| S11-test | T1 | cov | [保持] @2025-12-01 old but good | 2.0 | — | 6 | 95% | 推荐 |"
        reg = _make_registry(self.td, row)
        result = self.mod.cmd_audit(reg, dry_run=True)
        self.assertEqual(len(result), 1)
        # Should promote, not decay (promotion rule checked first via continue)
        self.assertIn("候选默认", result[0]["action"])


if __name__ == "__main__":
    unittest.main()
