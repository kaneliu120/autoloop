#!/usr/bin/env python3
"""AutoLoop SSOT 单一数据源管理工具

用法:
  autoloop-state.py init <工作目录> <模板> <目标>
  autoloop-state.py update <工作目录> <字段路径> <值>
  autoloop-state.py query <工作目录> <查询表达式>
  autoloop-state.py add-iteration <工作目录>
  autoloop-state.py add-finding <工作目录> <JSON>
  autoloop-state.py add-tsv-row <工作目录> <JSON>
  autoloop-state.py migrate <工作目录> [--dry-run]

数据源文件: <工作目录>/autoloop-state.json
"""

import datetime
import importlib.util
import json
import os
import re
import sys


STATE_FILE = "autoloop-state.json"
PROTOCOL_VERSION = "1.0.0"

TSV_COLUMNS = [
    "iteration", "phase", "status", "dimension", "metric_value", "delta",
    "strategy_id", "action_summary", "side_effect", "evidence_ref",
    "unit_id", "protocol_version", "score_variance", "confidence", "details"
]

PHASES = ["OBSERVE", "ORIENT", "DECIDE", "ACT", "VERIFY", "SYNTHESIZE", "EVOLVE", "REFLECT"]


def now_iso():
    return datetime.datetime.now().isoformat(timespec="seconds")


def task_id_now():
    return "autoloop-{}".format(datetime.datetime.now().strftime("%Y%m%d-%H%M%S"))


def validate_phase_transition(current, target):
    """验证阶段转换合法性（参照 loop-protocol.md §阶段转换约束）"""
    if current not in PHASES or target not in PHASES:
        return False, "未知阶段: {} → {}".format(current, target)
    ci, ti = PHASES.index(current), PHASES.index(target)
    if ti == ci + 1:
        return True, ""
    if target == "OBSERVE" and current == "REFLECT":
        return True, "进入下一轮"
    return False, "非法转换: {} → {}（必须按顺序推进）".format(current, target)


def initial_state(template, goal, work_dir):
    """创建初始 SSOT JSON 结构，覆盖 plan/progress/findings/results.tsv 所有信息"""
    now = now_iso()
    tid = task_id_now()

    return {
        "plan": {
            "task_id": tid,
            "template": template,
            "goal": goal,
            "detailed_background": "",
            "success_criteria": [],
            "status": "准备开始",
            "work_dir": work_dir,
            "plan_version": "1.0",
            "dimensions": [],
            "gates": [],
            "budget": {
                "max_rounds": 0,
                "current_round": 0,
                "time_limit": "无限制",
                "exhaustion_strategy": "输出当前最优"
            },
            "scope": {
                "includes": [],
                "excludes": [],
                "extensions": []
            },
            "template_params": {},
            "template_mode": "ooda_rounds",
            "linear_delivery_complete": False,
            "output_files": {
                "plan": {"path": "autoloop-plan.md", "status": "已创建"},
                "progress": {"path": "autoloop-progress.md", "status": "待创建"},
                "findings": {"path": "autoloop-findings.md", "status": "待创建"},
                "results_tsv": {"path": "autoloop-results.tsv", "status": "待创建"}
            },
            "strategy_history": [],
            "decide_act_handoff": None,
            "change_log": [
                {"time": now, "field": "初始创建", "before": "", "after": "", "reason": ""}
            ]
        },
        "iterations": [],
        "findings": {
            "executive_summary": {
                "topic": "待填写",
                "total_rounds": 0,
                "final_scores": {},
                "top_conclusions": []
            },
            "rounds": [],
            "engineering_issues": {
                "security": [],
                "reliability": [],
                "maintainability": [],
                "architecture": [],
                "performance": [],
                "stability": []
            },
            "fix_records": [],
            "disputes": [],
            "info_gaps": [],
            "expansion_directions": [],
            "sources": {"high": [], "medium": [], "low": []},
            "problem_tracker": [],
            "strategy_evaluations": [],
            "pattern_recognition": {
                "recurring_problems": [],
                "diminishing_returns": [],
                "cross_dimension": [],
                "bottlenecks": []
            },
            "lessons_learned": {
                "verified_hypotheses": [],
                "generalizable_methods": [],
                "process_improvements": []
            }
        },
        "experience": [],
        "results_tsv": [],
        "metadata": {
            "protocol_version": PROTOCOL_VERSION,
            "created_at": now,
            "updated_at": now,
            "ssot_version": "1.0.0"
        }
    }


def load_state(work_dir):
    """加载 state.json，不存在时报错退出"""
    path = os.path.join(work_dir, STATE_FILE)
    if not os.path.exists(path):
        print("ERROR: 数据源文件不存在: {}".format(path))
        print("提示: 先运行 autoloop-state.py init <工作目录> <模板> <目标>")
        sys.exit(1)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_state(work_dir, state):
    """保存 state.json，自动更新 updated_at"""
    state["metadata"]["updated_at"] = now_iso()
    path = os.path.join(work_dir, STATE_FILE)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    return path


# --- 字段路径解析 ---

def _parse_path_segment(segment):
    """解析路径段，支持 key[N] 格式的数组索引"""
    m = re.match(r"^(\w+)\[(-?\d+)\]$", segment)
    if m:
        return m.group(1), int(m.group(2))
    return segment, None


def resolve_path(obj, path_str):
    """
    按点分路径遍历嵌套 dict/list，返回 (parent, key, value)。

    支持语法:
      plan.goal                     -> state["plan"]["goal"]
      iterations[-1].scores         -> state["iterations"][-1]["scores"]
      findings.rounds[0].findings   -> state["findings"]["rounds"][0]["findings"]
    """
    segments = path_str.split(".")
    current = obj
    parent = None
    last_key = None

    for seg in segments:
        parent = current
        key, idx = _parse_path_segment(seg)

        if isinstance(current, dict):
            if key not in current:
                return None, None, None
            current = current[key]
        elif isinstance(current, list):
            try:
                current = current[int(key)]
            except (ValueError, IndexError):
                return None, None, None
        else:
            return None, None, None

        last_key = key

        if idx is not None:
            parent = current
            last_key = idx
            try:
                current = current[idx]
            except (IndexError, TypeError):
                return None, None, None

    return parent, last_key, current


def set_by_path(obj, path_str, value):
    """按点分路径设置值"""
    segments = path_str.split(".")
    current = obj

    for seg in segments[:-1]:
        key, idx = _parse_path_segment(seg)
        if isinstance(current, dict):
            current = current[key]
        elif isinstance(current, list):
            current = current[int(key)]
        if idx is not None:
            current = current[idx]

    last_seg = segments[-1]
    key, idx = _parse_path_segment(last_seg)

    if idx is not None:
        current[key][idx] = value
    elif isinstance(current, dict):
        current[key] = value
    elif isinstance(current, list):
        current[int(key)] = value


def _auto_convert(value_str):
    """尝试将字符串转为合适的 Python 类型"""
    if value_str.lower() in ("true", "false"):
        return value_str.lower() == "true"
    try:
        return int(value_str)
    except ValueError:
        pass
    try:
        return float(value_str)
    except ValueError:
        pass
    if value_str.startswith(("{", "[")):
        try:
            return json.loads(value_str)
        except json.JSONDecodeError:
            pass
    return value_str


# --- 子命令实现 ---

def _load_plan_gates_for_template(template):
    """从 autoloop-score 加载与 scorer 对齐的 plan.gates（避免维度键分裂）。"""
    score_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "autoloop-score.py")
    spec = importlib.util.spec_from_file_location("al_score_ssot", score_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.plan_gates_for_ssot_init(template)


def cmd_init(work_dir, template, goal):
    """初始化 autoloop-state.json"""
    if not os.path.isdir(work_dir):
        print("ERROR: 目录不存在: {}".format(work_dir))
        return False

    path = os.path.join(work_dir, STATE_FILE)
    if os.path.exists(path):
        print("WARNING: 数据源已存在: {}".format(path))
        print("如需重新初始化，请先删除该文件。")
        return False

    state = initial_state(template, goal, work_dir)
    gates = _load_plan_gates_for_template(template)
    state["plan"]["gates"] = gates
    # 从 gates 推导 dimensions（manifest_dimension 优先，fallback dimension/dim）
    state["plan"]["dimensions"] = [
        g.get("manifest_dimension") or g.get("dimension") or g.get("dim", "")
        for g in gates
        if g.get("manifest_dimension") or g.get("dimension") or g.get("dim")
    ]
    # 从 gate-manifest.json 读取模板默认轮次
    if state["plan"]["budget"]["max_rounds"] <= 0:
        manifest_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "..", "references", "gate-manifest.json"
        )
        try:
            with open(manifest_path, "r", encoding="utf-8") as mf:
                manifest = json.load(mf)
            default_rounds = manifest.get("default_rounds", {}).get(template, 3)
            state["plan"]["budget"]["max_rounds"] = default_rounds
        except (OSError, json.JSONDecodeError):
            state["plan"]["budget"]["max_rounds"] = 3  # fallback
    saved = save_state(work_dir, state)
    print("OK: SSOT 数据源已创建: {}".format(saved))
    print("  任务 ID: {}".format(state["plan"]["task_id"]))
    print("  模板: {}".format(template))
    print("  目标: {}".format(goal))
    return True


PROTECTED_PATH_PATTERNS = [
    re.compile(r"^plan\.gates\[\d+\]\.threshold$"),
    re.compile(r"^plan\.budget\.max_rounds$"),
]


def cmd_update(work_dir, field_path, value_str):
    """更新数据源中的特定字段"""
    for pat in PROTECTED_PATH_PATTERNS:
        if pat.match(field_path):
            print("WARNING: Cannot update protected path '{}' via update command.".format(field_path))
            print("Gate thresholds can only be modified by editing gate-manifest.json directly (leaves git audit trail).")
            sys.exit(1)

    state = load_state(work_dir)

    parent, key, old_value = resolve_path(state, field_path)
    if parent is None:
        print("ERROR: 字段路径不存在: {}".format(field_path))
        print("提示: 使用 query 命令查看现有结构")
        sys.exit(1)

    new_value = _auto_convert(value_str)

    if field_path.endswith("phase"):
        if isinstance(old_value, str) and isinstance(new_value, str):
            ok, msg = validate_phase_transition(old_value, new_value)
            if not ok:
                print("ERROR: 阶段转换验证失败: {}".format(msg))
                sys.exit(1)
            if msg:
                print("INFO: {}".format(msg))

    set_by_path(state, field_path, new_value)

    state["plan"]["change_log"].append({
        "time": now_iso(),
        "field": field_path,
        "before": str(old_value) if old_value is not None else "",
        "after": str(new_value),
        "reason": "autoloop-state update"
    })

    save_state(work_dir, state)
    print("OK: {}".format(field_path))
    print("  旧值: {}".format(old_value))
    print("  新值: {}".format(new_value))

    return True


def cmd_query(work_dir, query_expr):
    """查询数据源字段"""
    state = load_state(work_dir)

    if query_expr == "summary":
        plan = state["plan"]
        meta = state["metadata"]
        n_iter = len(state["iterations"])
        n_findings = sum(
            len(r.get("findings", []))
            for r in state["findings"]["rounds"]
        )
        n_tsv = len(state["results_tsv"])
        print("任务 ID: {}".format(plan["task_id"]))
        print("模板: {}".format(plan["template"]))
        print("状态: {}".format(plan["status"]))
        print("目标: {}".format(plan["goal"]))
        print("迭代轮次: {}".format(n_iter))
        print("发现总数: {}".format(n_findings))
        print("TSV 记录数: {}".format(n_tsv))
        print("协议版本: {}".format(meta["protocol_version"]))
        print("创建时间: {}".format(meta["created_at"]))
        print("更新时间: {}".format(meta["updated_at"]))
        return True

    if query_expr == "dimensions":
        gates = state["plan"].get("gates", [])
        if not gates:
            print("未设置质量门禁维度")
            return True
        for g in gates:
            dim_label = g.get("dimension", g.get("dim", "?"))
            print("  {}: 当前={} 目标={} 状态={}".format(
                dim_label,
                g.get("current", "—"),
                g.get("target", "—"),
                g.get("status", "—")
            ))
        return True

    _, _, value = resolve_path(state, query_expr)
    if value is None:
        print("未找到: {}".format(query_expr))
        return False

    if isinstance(value, (dict, list)):
        print(json.dumps(value, ensure_ascii=False, indent=2))
    else:
        print(value)
    return True


def cmd_add_iteration(work_dir):
    """添加新一轮迭代记录"""
    state = load_state(work_dir)

    round_num = len(state["iterations"]) + 1
    now = now_iso()

    iteration = {
        "round": round_num,
        "start_time": now,
        "end_time": "",
        "status": "进行中",
        "phase": "OBSERVE",
        "scores": {},
        "strategy": {
            "strategy_id": "",
            "name": "",
            "description": "",
            "target_dimension": ""
        },
        "observe": {
            "gaps": [],
            "budget_remaining_pct": 0,
            "focus": "",
            "carryover": ""
        },
        "orient": {
            "gap_cause": "",
            "strategy": "",
            "scope_adjustment": "无",
            "expected_improvement": ""
        },
        "decide": {
            "actions": []
        },
        "act": {
            "records": [],
            "failures": []
        },
        "verify": {
            "score_updates": [],
            "verification_method": "",
            "new_issues": []
        },
        "synthesize": {
            "contradictions_found": [],
            "contradictions_resolved": [],
            "merged_data": [],
            "new_insights": []
        },
        "evolve": {
            "termination": "继续",
            "next_focus": "",
            "strategy_adjustment": "无",
            "scope_change": "无"
        },
        "reflect": {
            "problem_registry": {"new": 0, "fixed": 0, "remaining": 0},
            "strategy_review": {"rating": 0, "verdict": "待验证", "reason": ""},
            "pattern_recognition": "",
            "lesson_learned": "",
            "next_round_guidance": ""
        },
        "findings": [],
        "evolution_decisions": [],
        "tsv_rows": []
    }

    state["iterations"].append(iteration)
    state["plan"]["budget"]["current_round"] = round_num
    state["plan"]["status"] = "进行中"

    save_state(work_dir, state)
    print("OK: 已添加第 {} 轮迭代".format(round_num))
    print("  状态: 进行中")
    print("  阶段: OBSERVE")
    return True


def cmd_add_finding(work_dir, finding_json):
    """添加新发现到当前轮次"""
    state = load_state(work_dir)

    if not state["iterations"]:
        print("ERROR: 尚未创建迭代，请先执行 add-iteration")
        sys.exit(1)

    try:
        finding = json.loads(finding_json)
    except json.JSONDecodeError as e:
        print("ERROR: JSON 解析失败: {}".format(e))
        sys.exit(1)

    if "dimension" not in finding:
        print("ERROR: 缺少必需字段: dimension")
        print(
            '格式: {"dimension": "维度名", "content"|"summary"|"description": "正文", '
            '"source": "来源", "confidence": "高/中/低", '
            '"type": "finding/issue/gap"}'
        )
        sys.exit(1)
    body_keys = ("summary", "description", "content")
    if not any(
        finding.get(k) not in (None, "")
        for k in body_keys
    ):
        print("ERROR: 缺少正文字段: 须提供 summary、description 或 content 之一")
        print(
            '格式: {"dimension": "...", "summary": "...", ...} '
            "（与 loop-data-schema / validate 口径一致）"
        )
        sys.exit(1)
    if not finding.get("content"):
        for k in ("summary", "description"):
            v = finding.get(k)
            if v not in (None, ""):
                finding["content"] = v
                break

    finding.setdefault("source", "")
    finding.setdefault("confidence", "中")
    finding.setdefault("type", "finding")
    finding.setdefault("time", now_iso())
    finding.setdefault("round", len(state["iterations"]))

    if state["iterations"]:
        state["iterations"][-1]["findings"].append(finding)

    round_num = finding["round"]
    while len(state["findings"]["rounds"]) < round_num:
        state["findings"]["rounds"].append({
            "round": len(state["findings"]["rounds"]) + 1,
            "time": now_iso(),
            "findings": [],
            "contradictions": []
        })

    if 0 < round_num <= len(state["findings"]["rounds"]):
        state["findings"]["rounds"][round_num - 1]["findings"].append(finding)

    save_state(work_dir, state)
    preview = (
        finding.get("content")
        or finding.get("summary")
        or finding.get("description")
        or ""
    )
    print("OK: 已添加发现 (第 {} 轮, 维度: {})".format(
        round_num, finding["dimension"]))
    print("  内容: {}...".format(str(preview)[:80]))
    return True


def _tsv_row_variance_fail_closed(row):
    """与 autoloop-variance check 对齐的 fail-closed（方差≥2 或 0<置信度<50）。"""
    sv = str(row.get("score_variance", "0")).strip()
    conf = str(row.get("confidence", "100")).replace("%", "").strip()
    try:
        var = float(sv) if sv and sv != "—" else 0.0
    except ValueError:
        return True, "score_variance 非数字"
    try:
        c = float(conf) if conf and conf != "—" else 100.0
    except ValueError:
        return True, "confidence 非数字"
    if var >= 2.0:
        return True, "score_variance≥2.0"
    if c < 50 and c != 0:
        return True, "confidence<50%"
    return False, ""


def cmd_add_tsv_row(work_dir, row_json):
    """添加 TSV 行记录"""
    state = load_state(work_dir)

    try:
        row = json.loads(row_json)
    except json.JSONDecodeError as e:
        print("ERROR: JSON 解析失败: {}".format(e))
        sys.exit(1)

    for col in TSV_COLUMNS:
        row.setdefault(col, "—")

    fc, reason = _tsv_row_variance_fail_closed(row)
    if fc:
        print("ERROR: TSV 行未通过方差/置信度校验: {}".format(reason))
        print("  请修正 score_variance / confidence 后重试（见 autoloop-variance.py check）")
        sys.exit(1)

    row.setdefault("protocol_version", PROTOCOL_VERSION)
    state["results_tsv"].append(row)

    if state["iterations"]:
        state["iterations"][-1]["tsv_rows"].append(row)

    save_state(work_dir, state)
    print("OK: 已添加 TSV 记录 (iteration={}, dimension={})".format(
        row.get("iteration", "—"), row.get("dimension", "—")))
    return True


# --- 主入口 ---

USAGE = """用法:
  autoloop-state.py init <工作目录> <模板> <目标>
  autoloop-state.py update <工作目录> <字段路径> <值>
  autoloop-state.py query <工作目录> <查询表达式>
  autoloop-state.py add-iteration <工作目录>
  autoloop-state.py add-finding <工作目录> '<JSON>'
  autoloop-state.py add-tsv-row <工作目录> '<JSON>'
  autoloop-state.py migrate <工作目录> --dry-run

查询示例:
  autoloop-state.py query /path summary
  autoloop-state.py query /path dimensions
  autoloop-state.py query /path plan.goal
  autoloop-state.py query /path iterations[-1].scores
  autoloop-state.py query /path metadata.protocol_version

更新示例:
  autoloop-state.py update /path plan.status 进行中
  autoloop-state.py update /path plan.budget.max_rounds 7
  autoloop-state.py update /path iterations[-1].phase ORIENT

迁移示例:
  autoloop-state.py migrate /path --dry-run   # 打印当前 plan.gates 与 SSOT 建议的差异预览
"""


def cmd_migrate(work_dir, dry_run):
    """对比 plan.gates 与 gate-manifest 初始化建议（不自动写回）。"""
    import importlib.util

    state = load_state(work_dir)
    tmpl = state.get("plan", {}).get("template", "T1")
    scripts_dir = os.path.dirname(os.path.abspath(__file__))
    score_path = os.path.join(scripts_dir, "autoloop-score.py")
    spec = importlib.util.spec_from_file_location("al_score_migrate", score_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    proposed = mod.plan_gates_for_ssot_init(tmpl)
    current = state.get("plan", {}).get("gates", [])

    print("模板: {}".format(tmpl))
    print("当前 plan.gates 条数: {}".format(len(current)))
    print("SSOT 建议条数: {}".format(len(proposed)))
    if dry_run:
        print("\n--- 建议 plan.gates（预览，完整见下方 JSON）---")
        print(json.dumps(proposed, ensure_ascii=False, indent=2))
        print(
            "\n（dry-run）未修改文件。若需对齐，请手工合并或重新 init；"
            "详见 references/loop-data-schema.md §迁移"
        )
    return True


def main():
    if len(sys.argv) < 2:
        print(USAGE)
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "init":
        if len(sys.argv) < 5:
            print("用法: autoloop-state.py init <工作目录> <模板> <目标>")
            sys.exit(1)
        ok = cmd_init(sys.argv[2], sys.argv[3], sys.argv[4])
        sys.exit(0 if ok else 1)

    elif cmd == "update":
        if len(sys.argv) < 5:
            print("用法: autoloop-state.py update <工作目录> <字段路径> <值>")
            sys.exit(1)
        ok = cmd_update(sys.argv[2], sys.argv[3], sys.argv[4])
        sys.exit(0 if ok else 1)

    elif cmd == "query":
        if len(sys.argv) < 4:
            print("用法: autoloop-state.py query <工作目录> <查询表达式>")
            sys.exit(1)
        ok = cmd_query(sys.argv[2], sys.argv[3])
        sys.exit(0 if ok else 1)

    elif cmd == "add-iteration":
        if len(sys.argv) < 3:
            print("用法: autoloop-state.py add-iteration <工作目录>")
            sys.exit(1)
        ok = cmd_add_iteration(sys.argv[2])
        sys.exit(0 if ok else 1)

    elif cmd == "add-finding":
        if len(sys.argv) < 4:
            print("用法: autoloop-state.py add-finding <工作目录> '<JSON>'")
            sys.exit(1)
        ok = cmd_add_finding(sys.argv[2], sys.argv[3])
        sys.exit(0 if ok else 1)

    elif cmd == "add-tsv-row":
        if len(sys.argv) < 4:
            print("用法: autoloop-state.py add-tsv-row <工作目录> '<JSON>'")
            sys.exit(1)
        ok = cmd_add_tsv_row(sys.argv[2], sys.argv[3])
        sys.exit(0 if ok else 1)

    elif cmd == "migrate":
        if len(sys.argv) < 3:
            print("用法: autoloop-state.py migrate <工作目录> [--dry-run]")
            sys.exit(1)
        dry = "--dry-run" in sys.argv
        ok = cmd_migrate(sys.argv[2], dry)
        sys.exit(0 if ok else 1)

    else:
        print("未知命令: {}".format(cmd))
        print(USAGE)
        sys.exit(1)


if __name__ == "__main__":
    main()
