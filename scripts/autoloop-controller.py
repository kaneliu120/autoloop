#!/usr/bin/env python3
"""AutoLoop 主循环控制器 — 自动驱动 8 阶段 OODA 循环

用法:
  autoloop-controller.py <work_dir>                         启动/继续循环
  autoloop-controller.py <work_dir> --init --template T{N}  初始化新任务
  autoloop-controller.py <work_dir> --resume                从 checkpoint 恢复
  autoloop-controller.py <work_dir> --status                查看当前状态

核心设计:
  - 编排脚本，非独立守护进程。确定性阶段自动执行，LLM阶段输出结构化提示。
  - checkpoint.json 在每个阶段完成后更新，支持断点恢复。
  - 振荡/停滞检测基于 parameters.md 定义的阈值。
"""

import datetime
import json
import os
import subprocess
import sys
import textwrap

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

PHASES = ["OBSERVE", "ORIENT", "DECIDE", "ACT", "VERIFY", "SYNTHESIZE", "EVOLVE", "REFLECT"]

STATE_FILE = "autoloop-state.json"
CHECKPOINT_FILE = "checkpoint.json"
EXPERIENCE_REGISTRY = "references/experience-registry.md"

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))

# parameters.md 中定义的默认轮次
DEFAULT_ROUNDS = {
    "T1": 3, "T2": 2, "T3": 99, "T4": 99,
    "T5": 1, "T6": 99, "T7": 99,
}

# ---------------------------------------------------------------------------
# 门禁清单加载 — 从 gate-manifest.json（SSOT）读取振荡/停滞阈值
# ---------------------------------------------------------------------------

def _load_gate_manifest():
    """Load gate definitions from canonical manifest (SSOT)."""
    manifest_path = os.path.join(os.path.dirname(__file__), "..", "references", "gate-manifest.json")
    with open(manifest_path, "r", encoding="utf-8") as f:
        return json.load(f)

_MANIFEST = _load_gate_manifest()

# 振荡检测阈值（来自 manifest.oscillation）
OSCILLATION_WINDOW = _MANIFEST["oscillation"]["window"]        # 连续轮数
OSCILLATION_BAND = _MANIFEST["oscillation"]["band"]            # ±分数波动带宽

# 停滞检测阈值（从 manifest.stagnation_thresholds 取默认值）
STAGNATION_CONSECUTIVE = _MANIFEST.get("stagnation_consecutive", 2)  # 从 manifest 加载
# 默认使用 T1 的 3% 相对阈值；运行时按模板动态查找
STAGNATION_THRESHOLD_PCT = 0.03

def _get_stagnation_threshold(template_key):
    """按模板获取停滞阈值，返回 (value, type)。type: 'relative'|'absolute'"""
    stag = _MANIFEST.get("stagnation_thresholds", {}).get(template_key)
    if stag:
        return stag["value"] / 100 if stag["type"] == "relative" else stag["value"], stag["type"]
    return STAGNATION_THRESHOLD_PCT, "relative"

# ANSI 颜色
C_RESET = "\033[0m"
C_BOLD = "\033[1m"
C_GREEN = "\033[32m"
C_YELLOW = "\033[33m"
C_RED = "\033[31m"
C_CYAN = "\033[36m"
C_DIM = "\033[2m"

# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------

def now_iso():
    return datetime.datetime.now().isoformat(timespec="seconds")


def banner(round_num, phase, msg=""):
    """打印阶段横幅"""
    idx = PHASES.index(phase) + 1
    label = f"[Round {round_num}] ({idx}/8) {phase}"
    if msg:
        label += f" — {msg}"
    width = max(len(label) + 4, 60)
    print(f"\n{C_BOLD}{C_CYAN}{'=' * width}")
    print(f"  {label}")
    print(f"{'=' * width}{C_RESET}\n")


def info(msg):
    print(f"{C_GREEN}[INFO]{C_RESET} {msg}")


def warn(msg):
    print(f"{C_YELLOW}[WARN]{C_RESET} {msg}")


def error(msg):
    print(f"{C_RED}[ERROR]{C_RESET} {msg}")


def prompt_block(title, content):
    """输出 LLM 需要执行的结构化提示块"""
    print(f"\n{C_BOLD}>>> LLM ACTION REQUIRED: {title}{C_RESET}")
    print(f"{C_DIM}{'─' * 60}{C_RESET}")
    print(textwrap.dedent(content).strip())
    print(f"{C_DIM}{'─' * 60}{C_RESET}\n")


# ---------------------------------------------------------------------------
# 文件 I/O
# ---------------------------------------------------------------------------

def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    info(f"已写入: {path}")


def load_state(work_dir):
    path = os.path.join(work_dir, STATE_FILE)
    if not os.path.exists(path):
        error(f"状态文件不存在: {path}")
        sys.exit(1)
    return load_json(path)


def load_checkpoint(work_dir):
    path = os.path.join(work_dir, CHECKPOINT_FILE)
    if not os.path.exists(path):
        return None
    return load_json(path)


def save_checkpoint(work_dir, checkpoint):
    checkpoint["timestamp"] = now_iso()
    save_json(os.path.join(work_dir, CHECKPOINT_FILE), checkpoint)


def make_checkpoint(task_id, round_num, phase, last_completed):
    return {
        "task_id": task_id,
        "current_round": round_num,
        "current_phase": phase,
        "last_completed_phase": last_completed,
        "timestamp": now_iso(),
        "evolve_history": [],
        "pause_state": None,
    }


# ---------------------------------------------------------------------------
# 子工具调用
# ---------------------------------------------------------------------------

def run_tool(script_name, args, capture=False):
    """调用同目录下的 autoloop-*.py 脚本"""
    script_path = os.path.join(SCRIPTS_DIR, script_name)
    cmd = [sys.executable, script_path] + [str(a) for a in args]
    info(f"调用: {' '.join(cmd)}")
    if capture:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            warn(f"工具返回非零退出码: {result.returncode}")
            if result.stderr:
                warn(f"  stderr: {result.stderr.strip()}")
        return result.stdout, result.returncode
    else:
        result = subprocess.run(cmd)
        return "", result.returncode


# ---------------------------------------------------------------------------
# 得分/门禁读取
# ---------------------------------------------------------------------------

def get_current_scores(state):
    """从 iterations[-1].scores 获取最新评分"""
    iters = state.get("iterations", [])
    if not iters:
        return {}
    return iters[-1].get("scores", {})


def get_gates(state):
    """从 plan.gates 获取门禁定义"""
    return state.get("plan", {}).get("gates", [])


def get_template(state):
    return state.get("plan", {}).get("template", "T1")


def get_max_rounds(state):
    budget = state.get("plan", {}).get("budget", {})
    max_r = budget.get("max_rounds", 0)
    if max_r > 0:
        return max_r
    tmpl = get_template(state)
    return DEFAULT_ROUNDS.get(tmpl, 5)


def get_current_round(state):
    budget = state.get("plan", {}).get("budget", {})
    return budget.get("current_round", 0)


def get_score_history(state):
    """返回 [{dim: score, ...}, ...] 按轮次排列"""
    history = []
    for it in state.get("iterations", []):
        scores = it.get("scores", {})
        if scores:
            history.append(scores)
    return history


# ---------------------------------------------------------------------------
# 振荡 & 停滞检测
# ---------------------------------------------------------------------------

def detect_oscillation(score_history):
    """检测最近 OSCILLATION_WINDOW 轮中是否有维度振荡

    振荡定义（parameters.md §五）: 连续 3 轮在 ±0.5 分范围内波动
    返回: [(dim, scores, is_oscillating), ...]
    """
    if len(score_history) < OSCILLATION_WINDOW:
        return []

    recent = score_history[-OSCILLATION_WINDOW:]
    all_dims = set()
    for s in recent:
        all_dims.update(s.keys())

    results = []
    for dim in sorted(all_dims):
        vals = [s.get(dim) for s in recent]
        # 跳过缺失值
        vals = [v for v in vals if v is not None]
        if len(vals) < OSCILLATION_WINDOW:
            continue
        vmin, vmax = min(vals), max(vals)
        is_osc = (vmax - vmin) <= (OSCILLATION_BAND * 2)
        if is_osc:
            results.append((dim, vals, True))
    return results


def detect_stagnation(score_history, gates):
    """检测是否存在停滞

    停滞定义（parameters.md §2.3）: 同一维度连续 2 轮改进 < 3%（相对值）
    返回: [(dim, recent_scores, is_stagnating), ...]
    """
    if len(score_history) < STAGNATION_CONSECUTIVE + 1:
        return []

    window = score_history[-(STAGNATION_CONSECUTIVE + 1):]
    all_dims = set()
    for s in window:
        all_dims.update(s.keys())

    results = []
    for dim in sorted(all_dims):
        vals = [s.get(dim) for s in window]
        vals = [v for v in vals if v is not None]
        if len(vals) < STAGNATION_CONSECUTIVE + 1:
            continue

        stagnating = True
        for i in range(1, len(vals)):
            prev = vals[i - 1]
            curr = vals[i]
            if prev == 0:
                if curr != 0:
                    stagnating = False
                    break
                continue
            improvement = abs(curr - prev) / abs(prev)
            if improvement >= STAGNATION_THRESHOLD_PCT:
                stagnating = False
                break

        if stagnating:
            results.append((dim, vals, True))
    return results


def check_gates_passed(state):
    """检查所有 hard gate 是否已通过，返回 (all_passed, details)"""
    scores = get_current_scores(state)
    gates = get_gates(state)
    if not gates:
        return True, []

    details = []
    all_hard_passed = True
    for g in gates:
        dim = g.get("dim", "")
        threshold = g.get("threshold")
        gate_type = g.get("gate", "soft")
        current = scores.get(dim)
        label = g.get("label", dim)

        if current is None:
            passed = False
        elif threshold is None:
            passed = True  # user_defined, 无法自动判定
        elif g.get("unit") == "bool":
            passed = bool(current)
        elif g.get("unit") == "count" or g.get("unit") == "errors":
            passed = current <= threshold
        else:
            passed = current >= threshold

        details.append({
            "dim": dim, "label": label, "threshold": threshold,
            "current": current, "gate": gate_type, "passed": passed,
        })
        if gate_type == "hard" and not passed:
            all_hard_passed = False

    return all_hard_passed, details


# ---------------------------------------------------------------------------
# 阶段执行器
# ---------------------------------------------------------------------------

def phase_observe(work_dir, state, round_num):
    """OBSERVE: 输出当前得分 vs 目标，读取经验库推荐"""
    banner(round_num, "OBSERVE", "采集当前状态")

    scores = get_current_scores(state)
    gates = get_gates(state)
    template = get_template(state)

    # 1. 当前分数 vs 门禁目标
    info(f"模板: {template} | 轮次: {round_num}/{get_max_rounds(state)}")
    if scores:
        print(f"\n{'维度':<20} {'当前':>8} {'目标':>8} {'差距':>8} {'门禁':>6}")
        print("─" * 56)
        for g in gates:
            dim = g["dim"]
            cur = scores.get(dim, "—")
            thr = g.get("threshold", "—")
            gap = ""
            if isinstance(cur, (int, float)) and isinstance(thr, (int, float)) and thr != 0:
                gap_pct = ((thr - cur) / thr) * 100 if thr > cur else 0
                gap = f"{gap_pct:+.1f}%" if gap_pct > 0 else "PASS"
            print(f"{g.get('label', dim):<20} {str(cur):>8} {str(thr):>8} {gap:>8} {g['gate']:>6}")
    else:
        warn("无历史评分数据（首轮）")

    # 2. 经验库推荐
    exp_path = os.path.join(os.path.dirname(SCRIPTS_DIR), EXPERIENCE_REGISTRY)
    if os.path.exists(exp_path):
        info(f"经验库路径: {exp_path}")
        prompt_block("读取经验库", f"""\
            请阅读经验库文件，查找与模板 {template} 和当前维度相关的策略推荐:
            文件: {exp_path}
            关注: 策略效果库中 use_count > 0 且 avg_delta > 0 的条目
        """)
    else:
        info("经验库文件不存在，跳过推荐")


def phase_orient(work_dir, state, round_num):
    """ORIENT: 计算差距百分比，分类优先级"""
    banner(round_num, "ORIENT", "差距分析与优先级分类")

    scores = get_current_scores(state)
    gates = get_gates(state)

    if not scores or not gates:
        warn("无评分或门禁数据，跳过差距计算")
        return

    critical = []   # >50% 差距
    moderate = []   # 20-50% 差距
    minor = []      # <20% 差距
    passed = []     # 已达标

    for g in gates:
        dim = g["dim"]
        cur = scores.get(dim)
        thr = g.get("threshold")
        label = g.get("label", dim)

        if cur is None or thr is None:
            critical.append((label, dim, "无数据", "—"))
            continue

        if g.get("unit") == "bool":
            if not cur:
                critical.append((label, dim, cur, "未达标"))
            else:
                passed.append((label, dim, cur, "PASS"))
            continue

        if g.get("unit") in ("count", "errors"):
            # 越少越好
            if cur <= thr:
                passed.append((label, dim, cur, "PASS"))
            else:
                gap_pct = ((cur - thr) / max(cur, 1)) * 100
                bucket = critical if gap_pct > 50 else moderate if gap_pct > 20 else minor
                bucket.append((label, dim, cur, f"{gap_pct:.0f}%"))
            continue

        # 越高越好（百分比或分数）
        if thr == 0:
            passed.append((label, dim, cur, "PASS"))
            continue

        if cur >= thr:
            passed.append((label, dim, cur, "PASS"))
        else:
            gap_pct = ((thr - cur) / thr) * 100
            bucket = critical if gap_pct > 50 else moderate if gap_pct > 20 else minor
            bucket.append((label, dim, cur, f"{gap_pct:.0f}%"))

    def _print_bucket(name, color, items):
        if not items:
            return
        print(f"\n{color}{C_BOLD}{name}{C_RESET}")
        for label, dim, cur, gap in items:
            print(f"  {label:<20} 当前={cur:<8} 差距={gap}")

    _print_bucket("CRITICAL (>50%)", C_RED, critical)
    _print_bucket("MODERATE (20-50%)", C_YELLOW, moderate)
    _print_bucket("MINOR (<20%)", C_GREEN, minor)
    _print_bucket("PASSED", C_DIM, passed)

    # 振荡 & 停滞检测
    history = get_score_history(state)
    osc = detect_oscillation(history)
    stag = detect_stagnation(history, gates)

    if osc:
        warn("振荡检测:")
        for dim, vals, _ in osc:
            warn(f"  {dim}: 最近 {OSCILLATION_WINDOW} 轮评分 {vals} — 波动 ≤ ±{OSCILLATION_BAND}")
    if stag:
        warn("停滞检测:")
        for dim, vals, _ in stag:
            warn(f"  {dim}: 最近评分 {vals} — 改进 < {STAGNATION_THRESHOLD_PCT*100:.0f}%")


def phase_decide(work_dir, state, round_num):
    """DECIDE: 输出策略选择提示（LLM 填充）"""
    banner(round_num, "DECIDE", "策略选择")

    scores = get_current_scores(state)
    template = get_template(state)
    strategy_history = state.get("plan", {}).get("strategy_history", [])

    history_summary = "无" if not strategy_history else "\n".join(
        f"  Round {s.get('round', '?')}: {s.get('strategy_id', '?')} — {s.get('result', '?')}"
        for s in strategy_history[-5:]
    )

    prompt_block("选择本轮策略", f"""\
        基于 ORIENT 阶段的差距分析，为本轮选择改进策略:

        模板: {template}
        当前轮次: {round_num}/{get_max_rounds(state)}
        当前评分: {json.dumps(scores, ensure_ascii=False)}
        历史策略（最近5轮）:
        {history_summary}

        要求:
        1. 优先攻击 CRITICAL 差距维度
        2. 策略ID格式: S{round_num:02d}-<简短描述>
        3. 明确预期提升幅度（如 coverage +15%）
        4. 如存在振荡/停滞，必须切换策略（不重复上轮策略）
        5. 输出格式:
           策略ID: S{round_num:02d}-xxx
           目标维度: [dim1, dim2]
           预期提升: dim1 +X%, dim2 +Y%
           执行方法: ...
           风险: ...
    """)


def phase_act(work_dir, state, round_num):
    """ACT: 输出 subagent 调度指令（LLM 执行）"""
    banner(round_num, "ACT", "执行改进")

    template = get_template(state)

    prompt_block("执行策略", f"""\
        根据 DECIDE 阶段选定的策略，执行改进操作:

        工作目录: {work_dir}
        模板: {template}

        执行要求:
        1. 按策略中定义的执行方法逐步操作
        2. 每个修改立即验证（py_compile / tsc --noEmit）
        3. 记录所有变更到 state.json 的当前迭代
        4. 完成后更新评分相关的 findings

        完成后运行:
          autoloop-state.py update {work_dir} plan.budget.current_round {round_num}
    """)


def phase_verify(work_dir, state, round_num):
    """VERIFY: 自动调用评分器和方差计算"""
    banner(round_num, "VERIFY", "评分验证")

    # 1. 调用评分器
    info("运行评分器...")
    stdout, rc = run_tool("autoloop-score.py", [work_dir, "--json"], capture=True)
    score_results = []
    if rc in (0, 1) and stdout.strip():
        try:
            score_result = json.loads(stdout.strip())
            info(f"评分结果: {json.dumps(score_result, ensure_ascii=False, indent=2)}")
            score_results = score_result.get("gates", [])
        except json.JSONDecodeError:
            info(f"评分输出:\n{stdout}")
    else:
        warn(f"评分器未返回 JSON 输出 (rc={rc})")
        if stdout.strip():
            print(stdout)

    # FIX 2: 将评分写回 state.json iterations[-1].scores
    if score_results:
        info("写回评分到 state.json...")
        for gate_result in score_results:
            if "error" in gate_result:
                continue
            dim = gate_result.get("dimension", "")
            value = gate_result.get("value")
            if dim and value is not None:
                _, wrc = run_tool("autoloop-state.py", [
                    "update", work_dir,
                    f"iterations[-1].scores.{dim}", str(value)
                ], capture=True)
                if wrc != 0:
                    warn(f"写回评分失败: {dim}={value}")

    # FIX 3: 更新 plan.gates 中的 current 值和状态
    if score_results:
        info("更新门禁状态...")
        # 重新加载 state 以获取 gates 定义
        state_fresh = load_state(work_dir)
        plan_gates = get_gates(state_fresh)
        for idx, gate_def in enumerate(plan_gates):
            gate_dim = gate_def.get("dim", "")
            # 在 score_results 中查找对应维度
            for gate_result in score_results:
                if gate_result.get("dimension") == gate_dim:
                    current_val = gate_result.get("value")
                    passed = gate_result.get("pass", False)
                    if current_val is not None:
                        run_tool("autoloop-state.py", [
                            "update", work_dir,
                            f"plan.gates[{idx}].current", str(current_val)
                        ], capture=True)
                        status_label = "达标" if passed else "未达标"
                        run_tool("autoloop-state.py", [
                            "update", work_dir,
                            f"plan.gates[{idx}].status", status_label
                        ], capture=True)
                    break

    # 2. 调用验证器
    info("运行验证器...")
    run_tool("autoloop-validate.py", [work_dir])

    # 3. 调用方差计算
    tsv_path = os.path.join(work_dir, "autoloop-results.tsv")
    if os.path.exists(tsv_path):
        info("运行方差检查...")
        run_tool("autoloop-variance.py", ["check", tsv_path])
    else:
        info("TSV 文件不存在，跳过方差检查")

    # 4. 渲染可读文件
    info("渲染输出文件...")
    run_tool("autoloop-render.py", [work_dir])

    # 5. 提示追加 TSV 行
    prompt_block("追加 TSV 记录", f"""\
        请基于本轮评分结果，调用:
          autoloop-state.py add-tsv-row {work_dir} '<JSON>'

        JSON 字段: iteration, phase, status, dimension, metric_value, delta,
                   strategy_id, action_summary, side_effect, evidence_ref,
                   unit_id, protocol_version, score_variance, confidence, details
    """)


def phase_synthesize(work_dir, state, round_num):
    """SYNTHESIZE: 输出综合分析提示（LLM 填充）"""
    banner(round_num, "SYNTHESIZE", "综合分析")

    scores = get_current_scores(state)
    _, gate_details = check_gates_passed(state)
    passed_count = sum(1 for d in gate_details if d["passed"])
    total_count = len(gate_details)

    prompt_block("综合本轮发现", f"""\
        综合本轮改进结果，更新 findings:

        当前评分: {json.dumps(scores, ensure_ascii=False)}
        门禁通过: {passed_count}/{total_count}

        要求:
        1. 总结本轮改进的有效性（哪些策略奏效，哪些无效）
        2. 更新 executive_summary.final_scores
        3. 记录新发现的问题到 engineering_issues
        4. 更新 pattern_recognition（反复出现的问题、瓶颈）
        5. 评估策略 ROI：投入 vs 收益

        调用:
          autoloop-state.py add-finding {work_dir} '<JSON>'
    """)


def phase_evolve(work_dir, state, round_num):
    """EVOLVE: 自动检查终止条件"""
    banner(round_num, "EVOLVE", "终止条件评估")

    max_rounds = get_max_rounds(state)
    all_passed, gate_details = check_gates_passed(state)
    history = get_score_history(state)
    osc = detect_oscillation(history)
    stag = detect_stagnation(history, get_gates(state))

    decision = "continue"
    reasons = []

    # 1. 门禁全通过 → 成功终止
    if all_passed and gate_details:
        decision = "stop"
        reasons.append("所有 hard gate 已通过")

    # 2. 预算耗尽
    if round_num >= max_rounds:
        decision = "stop"
        reasons.append(f"已达最大轮次 {max_rounds}")

    # 3. 振荡检测
    if len(osc) >= 2:
        reasons.append(f"检测到 {len(osc)} 个维度振荡")
        if decision == "continue":
            decision = "pause"

    # 4. 停滞检测
    if len(stag) >= 2:
        reasons.append(f"检测到 {len(stag)} 个维度停滞")
        if decision == "continue":
            decision = "pause"

    # 输出决策
    decision_color = {
        "continue": C_GREEN, "stop": C_RED, "pause": C_YELLOW,
    }.get(decision, C_RESET)
    print(f"\n{C_BOLD}终止条件评估结果:{C_RESET}")
    print(f"  决策: {decision_color}{C_BOLD}{decision.upper()}{C_RESET}")
    for r in reasons:
        print(f"  原因: {r}")

    # 门禁详情
    if gate_details:
        print(f"\n{'门禁':<20} {'状态':>6} {'当前':>8} {'目标':>8} {'类型':>6}")
        print("─" * 52)
        for d in gate_details:
            status = f"{C_GREEN}PASS{C_RESET}" if d["passed"] else f"{C_RED}FAIL{C_RESET}"
            print(f"  {d['label']:<18} {status:>15} {str(d['current']):>8} {str(d['threshold']):>8} {d['gate']:>6}")

    return decision, reasons


def phase_reflect(work_dir, state, round_num):
    """REFLECT: 输出反思提示，更新经验库"""
    banner(round_num, "REFLECT", "反思与经验沉淀")

    history = get_score_history(state)
    prev_scores = history[-2] if len(history) >= 2 else {}
    curr_scores = history[-1] if history else {}

    # 计算本轮变化
    deltas = {}
    for dim in set(list(prev_scores.keys()) + list(curr_scores.keys())):
        p = prev_scores.get(dim)
        c = curr_scores.get(dim)
        if isinstance(p, (int, float)) and isinstance(c, (int, float)):
            deltas[dim] = round(c - p, 2)

    prompt_block("反思与经验沉淀", f"""\
        本轮变化: {json.dumps(deltas, ensure_ascii=False)}

        反思要求:
        1. 本轮策略是否达到预期？差异原因是什么？
        2. 发现了哪些可泛化的方法？
        3. 有哪些假设被验证或推翻？
        4. 下一轮应该改变什么？

        经验沉淀（如有）:
        - 策略效果 → 更新经验库策略效果表
        - 评分标准缺陷 → 提议修改 quality-gates.md
        - 参数校准 → 提议修改 parameters.md

        调用:
          autoloop-state.py update {work_dir} findings.lessons_learned.verified_hypotheses '[...]'
    """)


# ---------------------------------------------------------------------------
# 主循环
# ---------------------------------------------------------------------------

def run_init(work_dir, template, goal=""):
    """初始化新任务"""
    os.makedirs(work_dir, exist_ok=True)

    # 1. 调用 autoloop-state.py init
    args = ["init", work_dir, template]
    if goal:
        args.append(goal)
    _, rc = run_tool("autoloop-state.py", args)
    if rc != 0:
        error("初始化状态失败")
        sys.exit(1)

    # 2. 加载生成的 state 以获取 task_id
    state = load_state(work_dir)
    task_id = state.get("plan", {}).get("task_id", "unknown")

    # 3. 创建 checkpoint
    checkpoint = make_checkpoint(task_id, 0, "OBSERVE", "INIT")
    save_checkpoint(work_dir, checkpoint)

    info(f"任务已初始化: {task_id}")
    info(f"模板: {template}")
    info(f"工作目录: {work_dir}")
    info(f"下一步: autoloop-controller.py {work_dir}")


def run_status(work_dir):
    """查看当前状态"""
    state = load_state(work_dir)
    checkpoint = load_checkpoint(work_dir)

    plan = state.get("plan", {})
    task_id = plan.get("task_id", "unknown")
    template = plan.get("template", "?")
    status = plan.get("status", "?")
    round_num = plan.get("budget", {}).get("current_round", 0)
    max_rounds = get_max_rounds(state)

    print(f"\n{C_BOLD}AutoLoop 任务状态{C_RESET}")
    print(f"{'─' * 40}")
    print(f"  任务ID:   {task_id}")
    print(f"  模板:     {template}")
    print(f"  状态:     {status}")
    print(f"  轮次:     {round_num}/{max_rounds}")

    if checkpoint:
        print(f"  检查点:   Round {checkpoint.get('current_round', '?')} / {checkpoint.get('current_phase', '?')}")
        print(f"  上次完成: {checkpoint.get('last_completed_phase', '?')}")
        print(f"  时间戳:   {checkpoint.get('timestamp', '?')}")

        # 打印 evolve 历史
        evolve_hist = checkpoint.get("evolve_history", [])
        if evolve_hist:
            print(f"\n  EVOLVE 历史:")
            for eh in evolve_hist[-5:]:
                print(f"    Round {eh.get('round', '?')}: {eh.get('decision', '?')} — {eh.get('reason', '')}")
    else:
        print(f"  检查点:   无")

    # 当前评分
    scores = get_current_scores(state)
    if scores:
        print(f"\n  当前评分:")
        for dim, val in sorted(scores.items()):
            print(f"    {dim}: {val}")

    # 门禁状态
    all_passed, details = check_gates_passed(state)
    if details:
        passed = sum(1 for d in details if d["passed"])
        print(f"\n  门禁: {passed}/{len(details)} 通过 {'(全部通过)' if all_passed else ''}")

    print()


def run_loop(work_dir, start_phase=None, start_round=None):
    """主循环执行"""
    state = load_state(work_dir)
    checkpoint = load_checkpoint(work_dir)

    # 确定起始位置
    if start_round is not None:
        round_num = start_round
    elif checkpoint:
        round_num = checkpoint.get("current_round", 1)
    else:
        round_num = 1

    if start_phase is not None:
        phase_start_idx = PHASES.index(start_phase)
    elif checkpoint:
        last = checkpoint.get("last_completed_phase", "INIT")
        if last == "INIT":
            phase_start_idx = 0
        elif last == "REFLECT":
            # 上一轮完成，进入下一轮
            round_num += 1
            phase_start_idx = 0
        elif last in PHASES:
            phase_start_idx = PHASES.index(last) + 1
            if phase_start_idx >= len(PHASES):
                round_num += 1
                phase_start_idx = 0
        else:
            phase_start_idx = 0
    else:
        phase_start_idx = 0

    max_rounds = get_max_rounds(state)
    task_id = state.get("plan", {}).get("task_id", "unknown")

    if not checkpoint:
        checkpoint = make_checkpoint(task_id, round_num, PHASES[phase_start_idx], "INIT")

    info(f"启动 AutoLoop 循环: {task_id}")
    info(f"起始: Round {round_num}, Phase {PHASES[phase_start_idx]}")
    info(f"预算: {max_rounds} 轮")
    print()

    # 主循环
    while round_num <= max_rounds:
        # FIX 1: 每轮开始前自动创建 iteration 记录
        info(f"自动创建 Round {round_num} 迭代记录...")
        _, rc = run_tool("autoloop-state.py", ["add-iteration", work_dir], capture=True)
        if rc != 0:
            warn(f"add-iteration 返回非零退出码 (rc={rc})，可能已存在")

        # 更新 current_round
        run_tool("autoloop-state.py", [
            "update", work_dir, "plan.budget.current_round", str(round_num)
        ], capture=True)

        for phase_idx in range(phase_start_idx, len(PHASES)):
            phase = PHASES[phase_idx]

            # 更新 checkpoint: 当前阶段
            checkpoint["current_round"] = round_num
            checkpoint["current_phase"] = phase
            save_checkpoint(work_dir, checkpoint)

            # 重新加载 state（其他工具可能已修改）
            state = load_state(work_dir)

            # 执行阶段
            evolve_decision = None
            evolve_reasons = []

            if phase == "OBSERVE":
                phase_observe(work_dir, state, round_num)
            elif phase == "ORIENT":
                phase_orient(work_dir, state, round_num)
            elif phase == "DECIDE":
                phase_decide(work_dir, state, round_num)
            elif phase == "ACT":
                phase_act(work_dir, state, round_num)
            elif phase == "VERIFY":
                phase_verify(work_dir, state, round_num)
            elif phase == "SYNTHESIZE":
                phase_synthesize(work_dir, state, round_num)
            elif phase == "EVOLVE":
                evolve_decision, evolve_reasons = phase_evolve(work_dir, state, round_num)
            elif phase == "REFLECT":
                phase_reflect(work_dir, state, round_num)
                # FIX 4: REFLECT 完成后自动渲染可读文件
                info("REFLECT 后自动渲染...")
                run_tool("autoloop-render.py", [work_dir])

            # 更新 checkpoint: 阶段完成
            checkpoint["last_completed_phase"] = phase
            save_checkpoint(work_dir, checkpoint)

            # EVOLVE 决策处理
            if phase == "EVOLVE" and evolve_decision:
                checkpoint.setdefault("evolve_history", []).append({
                    "round": round_num,
                    "decision": evolve_decision,
                    "reason": "; ".join(evolve_reasons),
                })
                save_checkpoint(work_dir, checkpoint)

                if evolve_decision == "stop":
                    print(f"\n{C_BOLD}{C_GREEN}{'=' * 60}")
                    print(f"  AutoLoop 循环终止 — Round {round_num}")
                    print(f"  原因: {'; '.join(evolve_reasons)}")
                    print(f"{'=' * 60}{C_RESET}\n")
                    return

                if evolve_decision == "pause":
                    print(f"\n{C_BOLD}{C_YELLOW}{'=' * 60}")
                    print(f"  AutoLoop 循环暂停 — Round {round_num}")
                    print(f"  原因: {'; '.join(evolve_reasons)}")
                    print(f"  恢复: autoloop-controller.py {work_dir} --resume")
                    print(f"{'=' * 60}{C_RESET}\n")
                    checkpoint["pause_state"] = {
                        "reason": "; ".join(evolve_reasons),
                        "required_confirmation": "用户确认继续或调整策略",
                        "paused_at": now_iso(),
                    }
                    save_checkpoint(work_dir, checkpoint)
                    return

        # 本轮完成，重置 phase_start_idx 为 0（下一轮从 OBSERVE 开始）
        phase_start_idx = 0
        round_num += 1

    # 预算耗尽
    print(f"\n{C_BOLD}{C_RED}{'=' * 60}")
    print(f"  AutoLoop 预算耗尽 — {round_num - 1} 轮已完成")
    print(f"  输出当前最优结果")
    print(f"{'=' * 60}{C_RESET}\n")


# ---------------------------------------------------------------------------
# CLI 入口
# ---------------------------------------------------------------------------

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    work_dir = os.path.abspath(sys.argv[1])

    # 解析命令行参数
    args = sys.argv[2:]
    mode = "run"
    template = None
    goal = ""

    i = 0
    while i < len(args):
        arg = args[i]
        if arg == "--init":
            mode = "init"
        elif arg == "--resume":
            mode = "resume"
        elif arg == "--status":
            mode = "status"
        elif arg == "--template" and i + 1 < len(args):
            template = args[i + 1]
            i += 1
        elif arg == "--goal" and i + 1 < len(args):
            goal = args[i + 1]
            i += 1
        else:
            # 未知参数视为 goal 的一部分
            if mode == "init" and not goal:
                goal = arg
        i += 1

    if mode == "init":
        if not template:
            error("--init 模式需要 --template 参数")
            sys.exit(1)
        run_init(work_dir, template, goal)

    elif mode == "status":
        run_status(work_dir)

    elif mode == "resume":
        checkpoint = load_checkpoint(work_dir)
        if not checkpoint:
            error(f"未找到 checkpoint: {os.path.join(work_dir, CHECKPOINT_FILE)}")
            sys.exit(1)
        # 清除暂停状态
        if checkpoint.get("pause_state"):
            info("清除暂停状态，继续循环")
            checkpoint["pause_state"] = None
            save_checkpoint(work_dir, checkpoint)
        run_loop(work_dir)

    elif mode == "run":
        if not os.path.exists(os.path.join(work_dir, STATE_FILE)):
            error(f"状态文件不存在: {os.path.join(work_dir, STATE_FILE)}")
            error("请先运行 --init 初始化任务")
            sys.exit(1)
        run_loop(work_dir)

    else:
        error(f"未知模式: {mode}")
        sys.exit(1)


if __name__ == "__main__":
    main()
