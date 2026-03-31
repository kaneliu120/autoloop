"""manifest.stagnation_max_explore：EVOLVE 中停滞时 strategy 切换计数与 pause。"""

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
CONTROLLER = SCRIPTS / "autoloop-controller.py"
STATE_FILE = "autoloop-state.json"


def _load_controller():
    spec = importlib.util.spec_from_file_location("al_ctrl_stag", CONTROLLER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _init_workdir(template: str) -> str:
    td = tempfile.mkdtemp(prefix="al_stag_")
    subprocess.run(
        [sys.executable, str(SCRIPTS / "autoloop-state.py"), "init", td, template, "stagtest"],
        check=True,
        capture_output=True,
    )
    return td


def _load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


class TestStagnationMaxExplore(unittest.TestCase):
    def setUp(self):
        self._dirs = []

    def tearDown(self):
        for d in self._dirs:
            shutil.rmtree(d, ignore_errors=True)

    def _work_t5(self):
        td = _init_workdir("T5")
        self._dirs.append(td)
        return td

    def test_t1_no_limit_returns_unchanged_and_no_disk_touch(self):
        mod = _load_controller()
        td = _init_workdir("T1")
        self._dirs.append(td)
        path = os.path.join(td, STATE_FILE)
        st = _load_json(path)
        st["iterations"] = [
            {"strategy": {"strategy_id": "S-A"}},
            {"strategy": {"strategy_id": "S-B"}},
        ]
        st.setdefault("metadata", {})["stagnation_explore_switches"] = 99
        _save_json(path, st)
        st = _load_json(path)
        d, r = mod._stagnation_max_explore_apply(
            td, st, [("kpi", 0, "stagnating")], "continue", []
        )
        self.assertEqual(d, "continue")
        self.assertEqual(r, [])
        st2 = _load_json(path)
        self.assertEqual(st2.get("metadata", {}).get("stagnation_explore_switches"), 99)

    def test_pause_when_switch_count_reaches_manifest_limit_t5(self):
        mod = _load_controller()
        td = self._work_t5()
        path = os.path.join(td, STATE_FILE)
        st = _load_json(path)
        st["iterations"] = [
            {"strategy": {"strategy_id": "S1"}},
            {"strategy": {"strategy_id": "S2"}},
        ]
        st.setdefault("metadata", {})["stagnation_explore_switches"] = 2
        _save_json(path, st)
        st = _load_json(path)
        d, r = mod._stagnation_max_explore_apply(
            td, st, [("dim", 0, "stagnating")], "continue", []
        )
        self.assertEqual(d, "pause")
        self.assertTrue(any("stagnation_max_explore" in x for x in r))
        st2 = _load_json(path)
        self.assertEqual(st2.get("metadata", {}).get("stagnation_explore_switches"), 3)

    def test_continue_below_limit_increments_on_strategy_change(self):
        mod = _load_controller()
        td = self._work_t5()
        path = os.path.join(td, STATE_FILE)
        st = _load_json(path)
        st["iterations"] = [
            {"strategy": {"strategy_id": "A"}},
            {"strategy": {"strategy_id": "B"}},
        ]
        st.setdefault("metadata", {})["stagnation_explore_switches"] = 0
        _save_json(path, st)
        st = _load_json(path)
        d, r = mod._stagnation_max_explore_apply(
            td, st, [("d", 0, "stagnating")], "continue", []
        )
        self.assertEqual(d, "continue")
        st2 = _load_json(path)
        self.assertEqual(st2.get("metadata", {}).get("stagnation_explore_switches"), 1)

    def test_no_increment_when_last_two_strategies_same(self):
        mod = _load_controller()
        td = self._work_t5()
        path = os.path.join(td, STATE_FILE)
        st = _load_json(path)
        st["iterations"] = [
            {"strategy": {"strategy_id": "S"}},
            {"strategy": {"strategy_id": "S"}},
        ]
        # 低于 manifest T5 上限，避免「未切换却仍 pause」与用例意图混淆
        st.setdefault("metadata", {})["stagnation_explore_switches"] = 1
        _save_json(path, st)
        st = _load_json(path)
        d, r = mod._stagnation_max_explore_apply(
            td, st, [("d", 0, "stagnating")], "continue", []
        )
        self.assertEqual(d, "continue")
        st2 = _load_json(path)
        self.assertEqual(st2.get("metadata", {}).get("stagnation_explore_switches"), 1)

    def test_clears_counter_when_no_stagnating_rows(self):
        mod = _load_controller()
        td = self._work_t5()
        path = os.path.join(td, STATE_FILE)
        st = _load_json(path)
        st.setdefault("metadata", {})["stagnation_explore_switches"] = 4
        _save_json(path, st)
        st = _load_json(path)
        d, r = mod._stagnation_max_explore_apply(td, st, [], "continue", [])
        self.assertEqual(d, "continue")
        st2 = _load_json(path)
        self.assertEqual(st2.get("metadata", {}).get("stagnation_explore_switches"), 0)

    def test_stop_decision_preserved_at_limit(self):
        mod = _load_controller()
        td = self._work_t5()
        path = os.path.join(td, STATE_FILE)
        st = _load_json(path)
        st["iterations"] = [
            {"strategy": {"strategy_id": "S1"}},
            {"strategy": {"strategy_id": "S2"}},
        ]
        st.setdefault("metadata", {})["stagnation_explore_switches"] = 2
        _save_json(path, st)
        st = _load_json(path)
        d, r = mod._stagnation_max_explore_apply(
            td, st, [("d", 0, "stagnating")], "stop", ["所有 hard gate 已通过"]
        )
        self.assertEqual(d, "stop")
        self.assertIn("所有 hard gate 已通过", r)


if __name__ == "__main__":
    unittest.main()
