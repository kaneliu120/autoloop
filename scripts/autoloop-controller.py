#!/usr/bin/env python3
"""AutoLoop 主循环控制器 — 自动驱动 8 阶段 OODA 循环

用法:
  autoloop-controller.py <work_dir>                         启动/继续循环
  autoloop-controller.py <work_dir> --init --template T{N}  初始化新任务
  autoloop-controller.py <work_dir> --resume                从 checkpoint 恢复
  autoloop-controller.py <work_dir> --status                查看当前状态
  autoloop-controller.py <work_dir> --strict                VERIFY 失败则中止后续阶段（或设 AUTOLOOP_STRICT=1）
  autoloop-controller.py <work_dir> --enforce-strategy-history   DECIDE 前强校验 strategy_history 与 handoff（或 AUTOLOOP_ENFORCE_STRATEGY_HISTORY=1）
  autoloop-controller.py <work_dir> --stop-after <PHASE>   执行至该阶段结束并写 checkpoint 后退出（供 Runner 切片调用；PHASE 为 OBSERVE…REFLECT）
  autoloop-controller.py <work_dir> --exit-codes           进程退出码：0 正常/终止/切片结束，1 中止，10 暂停（亦设 AUTOLOOP_EXIT_CODES=1）

核心设计:
  - 编排脚本，非独立守护进程。确定性阶段自动执行，LLM阶段输出结构化提示。
  - checkpoint.json 在每个阶段完成后更新，支持断点恢复。
  - 振荡/停滞检测基于 parameters.md 定义的阈值。
"""

import datetime
import json
import os
import re
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
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)
from autoloop_kpi import (  # noqa: E402
    kpi_row_satisfied,
    plan_gate_is_exempt,
    results_tsv_last_row_fail_closed,
)

# 默认轮次从 gate-manifest.json 加载（SSOT），回退到硬编码值
_FALLBACK_ROUNDS = {"T1": 3, "T2": 2, "T4": 5, "T5": 99, "T6": 99, "T7": 99, "T8": 99}

# ---------------------------------------------------------------------------
# 门禁清单加载 — 从 gate-manifest.json（SSOT）读取振荡/停滞阈值
# ---------------------------------------------------------------------------

def _load_gate_manifest():
    """Load gate definitions from canonical manifest (SSOT)."""
    manifest_path = os.path.join(os.path.dirname(__file__), "..", "references", "gate-manifest.json")
    with open(manifest_path, "r", encoding="utf-8") as f:
        return json.load(f)

_MANIFEST = _load_gate_manifest()

# manifest dimension → scorer 内部 dim（与 autoloop-score._MANIFEST_DIM_MAP 一致，用于 comparator 反查）
_MANIFEST_DIM_TO_INTERNAL = {
    "syntax_errors": "syntax",
    "p1_count": "p1_all",
    "security": "security_score",
    "reliability": "reliability_score",
    "maintainability": "maintainability_score",
}

# 默认轮次（从 manifest 加载，回退到硬编码）
DEFAULT_ROUNDS = _MANIFEST.get("default_rounds", _FALLBACK_ROUNDS)

# 子进程超时（秒）；防 score/validate 挂死。validate 大仓库可能较慢，单独放宽（D-04）。
SUBPROCESS_TIMEOUT_DEFAULT = int(os.environ.get("AUTOLOOP_SUBPROCESS_TIMEOUT", "120"))
SUBPROCESS_TIMEOUT_VALIDATE = int(os.environ.get("AUTOLOOP_TIMEOUT_VALIDATE", "300"))


def subprocess_timeout_for(script_name):
    if script_name == "autoloop-validate.py":
        return SUBPROCESS_TIMEOUT_VALIDATE
    return SUBPROCESS_TIMEOUT_DEFAULT

# STRICT：VERIFY 失败（评分无 JSON、validate 非零、方差检查非零）则中止后续阶段
def _strict_enabled(cli_strict=False):
    env_on = os.environ.get("AUTOLOOP_STRICT", "").strip().lower() in ("1", "true", "yes")
    return bool(cli_strict or env_on)


def _enforce_strategy_history_enabled(cli_flag=False):
    env_on = os.environ.get("AUTOLOOP_ENFORCE_STRATEGY_HISTORY", "").strip().lower() in (
        "1", "true", "yes",
    )
    return bool(cli_flag or env_on)

# 振荡检测阈值（来自 manifest.oscillation）
OSCILLATION_WINDOW = _MANIFEST["oscillation"]["window"]        # 连续轮数
OSCILLATION_BAND = _MANIFEST["oscillation"]["band"]            # ±分数波动带宽

# 停滞检测阈值（从 manifest.stagnation_thresholds 取默认值）
STAGNATION_CONSECUTIVE = _MANIFEST.get("stagnation_consecutive", 2)  # 从 manifest 加载
# 默认使用 T1 的 3% 相对阈值；运行时按模板动态查找
STAGNATION_THRESHOLD_PCT = 0.03

def _lookup_manifest_comparator(template_key, dim, manifest_dimension=None):
    """从 gate-manifest.json 查找 comparator。

    dim: plan.gates 与 scorer 使用的内部键；manifest_dimension: manifest 原始 dimension 名。
    """
    tdef = _MANIFEST.get("templates", {}).get(template_key, {})
    if manifest_dimension:
        for g in tdef.get("gates", []):
            if g["dimension"] == manifest_dimension:
                return g.get("comparator")
    for g in tdef.get("gates", []):
        dr = g["dimension"]
        if dr == dim:
            return g.get("comparator")
        if _MANIFEST_DIM_TO_INTERNAL.get(dr, dr) == dim:
            return g.get("comparator")
    return None


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

def _append_evolve_progress_md(work_dir, round_num, decision, reasons, gate_details):
    """P-01: 将 EVOLVE 结论追加到 autoloop-progress.md（与 state init 中 output_files.progress 一致）。"""
    if os.environ.get("AUTOLOOP_SKIP_PROGRESS_LOG", "").strip().lower() in ("1", "true", "yes"):
        return
    path = os.path.join(work_dir, "autoloop-progress.md")
    lines = [
        "",
        "## EVOLVE — Round {} — {}".format(round_num, now_iso()),
        "",
        "- **决策**: `{}`".format(decision),
    ]
    if reasons:
        lines.append("- **原因**:")
        for r in reasons:
            lines.append("  - {}".format(r))
    else:
        lines.append("- **原因**: （无）")
    lines.append("")
    if gate_details:
        lines.append("| 门禁 | 通过 | 当前 | 目标 |")
        lines.append("|------|------|------|------|")
        for d in gate_details[:24]:
            lines.append(
                "| {} | {} | {} | {} |".format(
                    d.get("label", d.get("dim", "")),
                    "是" if d.get("passed") else "否",
                    d.get("current"),
                    d.get("threshold"),
                )
            )
        lines.append("")
    block = "\n".join(lines) + "\n"
    try:
        with open(path, "a", encoding="utf-8") as f:
            f.write(block)
    except OSError as exc:
        warn("无法追加 autoloop-progress.md: {}".format(exc))


def _decide_strategy_preflight(state, hard_checks):
    """P-02: strategy_history 中「避免」与重复 strategy_id 的提示；hard 时对 handoff 报错。"""
    history = state.get("plan", {}).get("strategy_history") or []
    if not isinstance(history, list):
        return
    avoided = set()
    for entry in history:
        if not isinstance(entry, dict):
            continue
        res = str(entry.get("result", ""))
        sid = (entry.get("strategy_id") or "").strip()
        if sid and ("避免" in res):
            avoided.add(sid)
    if avoided:
        warn(
            "策略历史中存在「避免」记录，勿再选同一 strategy_id: "
            + ", ".join(sorted(avoided))
        )
    recent = [h for h in history[-3:] if isinstance(h, dict)]
    sids = [(h.get("strategy_id") or "").strip() for h in recent if h.get("strategy_id")]
    if len(sids) >= 2 and sids[-1] and sids[-1] == sids[-2]:
        warn(
            "最近两轮 strategy_id 均为「{}」，建议评估是否切换策略（loop-protocol）".format(
                sids[-1]
            )
        )
    if not hard_checks:
        return
    handoff = state.get("plan", {}).get("decide_act_handoff") or {}
    if isinstance(handoff, dict):
        hsid = (handoff.get("strategy_id") or "").strip()
        if hsid and hsid in avoided:
            error(
                "DECIDE 预检: plan.decide_act_handoff.strategy_id={} 与历史「避免」冲突，"
                "请更新交接 JSON 或清空 handoff 后重试".format(hsid)
            )


def now_iso():
    return datetime.datetime.now().isoformat(timespec="seconds")


def _plan_context_tags_csv(plan):
    """SSOT plan.context_tags：list[str] 或逗号分隔字符串；空表示冷启动不传 query --tags。"""
    if not isinstance(plan, dict):
        return None
    raw = plan.get("context_tags")
    if raw is None:
        return None
    if isinstance(raw, str):
        s = raw.strip()
        return s if s else None
    if isinstance(raw, list):
        parts = [str(x).strip() for x in raw if str(x).strip()]
        return ",".join(parts) if parts else None
    return None


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

def run_tool(script_name, args, capture=False, env=None, work_dir=None):
    """调用同目录下的 autoloop-*.py 脚本。work_dir 传入时非零退出/超时写入 metadata.last_error，并追加 tool_* 审计行。"""
    script_path = os.path.join(SCRIPTS_DIR, script_name)
    cmd = [sys.executable, script_path] + [str(a) for a in args]
    argv_audit = [str(a) for a in args]
    info(f"调用: {' '.join(cmd)}")
    run_env = os.environ.copy()
    if env:
        run_env.update(env)
    if work_dir:
        _metadata_append_audit_structured(work_dir, {
            "event": "tool_start",
            "script": script_name,
            "argv": argv_audit,
            "work_dir": work_dir,
        })
    timeout_sec = subprocess_timeout_for(script_name)
    try:
        if capture:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=timeout_sec, env=run_env
            )
            if work_dir:
                _metadata_append_audit_structured(work_dir, {
                    "event": "tool_finish",
                    "script": script_name,
                    "argv": argv_audit,
                    "work_dir": work_dir,
                    "returncode": result.returncode,
                    "timeout": False,
                    "stderr": ((result.stderr or "")[:500]),
                })
            if result.returncode != 0:
                warn(f"工具返回非零退出码: {result.returncode}")
                if result.stderr:
                    warn(f"  stderr: {result.stderr.strip()}")
                if work_dir:
                    _metadata_set_last_error(
                        work_dir, script_name, result.returncode, (result.stderr or "")[:2000]
                    )
            return result.stdout, result.returncode
        result = subprocess.run(cmd, timeout=timeout_sec, env=run_env)
        if work_dir:
            _metadata_append_audit_structured(work_dir, {
                "event": "tool_finish",
                "script": script_name,
                "argv": argv_audit,
                "work_dir": work_dir,
                "returncode": result.returncode,
                "timeout": False,
                "stderr": "",
            })
        if work_dir and result.returncode != 0:
            _metadata_set_last_error(work_dir, script_name, result.returncode, "")
        return "", result.returncode
    except subprocess.TimeoutExpired:
        warn(f"工具超时 ({timeout_sec}s): {script_name}")
        if work_dir:
            _metadata_append_audit_structured(work_dir, {
                "event": "tool_timeout",
                "script": script_name,
                "argv": argv_audit,
                "work_dir": work_dir,
                "returncode": 124,
                "timeout": True,
                "stderr": "",
            })
            _metadata_set_last_error(work_dir, script_name, 124, "subprocess timeout")
        return "", 124


def _record_state_metadata(work_dir, mutator):
    """就地更新 autoloop-state.json 的 metadata（失败静默）。"""
    path = os.path.join(work_dir, STATE_FILE)
    if not os.path.isfile(path):
        return
    try:
        data = load_json(path)
        mutator(data)
        save_json(path, data)
    except (OSError, ValueError, TypeError, KeyError):
        pass


def _metadata_set_last_error(work_dir, script_name, returncode, stderr_snip=""):
    def _m(state):
        meta = state.setdefault("metadata", {})
        meta["last_error"] = {
            "time": now_iso(),
            "script": script_name,
            "returncode": returncode,
            "stderr": (stderr_snip or "")[:500],
        }
    _record_state_metadata(work_dir, _m)


def _metadata_append_audit(work_dir, event, detail=""):
    def _m(state):
        meta = state.setdefault("metadata", {})
        meta.setdefault("audit", []).append({
            "time": now_iso(),
            "event": event,
            "detail": detail,
        })
    _record_state_metadata(work_dir, _m)


def _metadata_append_audit_structured(work_dir, record):
    """向 metadata.audit[] 追加一条结构化记录；record 须含 \"event\" 字符串键。"""
    def _m(state):
        meta = state.setdefault("metadata", {})
        row = {"time": now_iso()}
        row.update(record)
        meta.setdefault("audit", []).append(row)
    _record_state_metadata(work_dir, _m)


# ---------------------------------------------------------------------------
# 得分/门禁读取
# ---------------------------------------------------------------------------

def get_current_scores(state):
    """从 iterations[-1].scores 获取最新评分。

    T5：新轮 add-iteration 后 scores 常为空，ORIENT/停滞窗口用 plan.gates[].current 数值回填 kpi 等维（VERIFY 前仍可对 gap 与历史一致）。
    """
    iters = state.get("iterations", [])
    if not iters:
        return {}
    sc = iters[-1].get("scores") or {}
    if sc:
        return sc
    if get_template(state) != "T5":
        return {}
    merged = {}
    for g in get_gates(state):
        dim = g.get("dim") or g.get("dimension", "")
        cur = g.get("current")
        if dim and isinstance(cur, (int, float)):
            merged[dim] = float(cur)
    return merged


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
    # T6：parameters.md 约定可按生成单元数 items×2 推导预算，上限为 manifest default_rounds（P-04）
    if tmpl == "T6":
        plan = state.get("plan", {}) or {}
        tp = plan.get("template_params") or {}
        raw_items = plan.get("generation_items", tp.get("items", tp.get("generation_item_count")))
        try:
            n = int(raw_items)
            if n > 0:
                cap = int(DEFAULT_ROUNDS.get("T6", 99))
                return min(max(n * 2, 1), cap)
        except (TypeError, ValueError):
            pass
    # T4 与 delivery-phases.md 七阶段对齐；manifest default_rounds 亦为 7
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
        in_narrow_band = (vmax - vmin) <= (OSCILLATION_BAND * 2)

        # 检查方向交替：至少有一次方向变化（上→下或下→上）
        # 排除单调收敛（如 7.0→7.3→7.6）的误报
        direction_changes = 0
        for j in range(2, len(vals)):
            d_prev = vals[j - 1] - vals[j - 2]
            d_curr = vals[j] - vals[j - 1]
            if (d_prev > 0 and d_curr < 0) or (d_prev < 0 and d_curr > 0):
                direction_changes += 1

        is_osc = in_narrow_band and direction_changes >= 1
        if is_osc:
            results.append((dim, vals, True))
    return results


def _confidence_for_dim(dim):
    """根据评分维度的数据来源，返回 (confidence, margin)。

    与 autoloop-score.py 中的同名函数保持语义一致。
    因文件名含连字符无法直接 import，维护两份——修改时需同步。

    - empirical (margin ≤ 0.3): 基于工具实际输出
    - heuristic (margin ≤ 1.5): 基于内容分析模式匹配
    - binary (margin = None): 只能判通过/不通过
    """
    # P1-6: 规范化维度名（manifest名 → 内部名）
    dim = _MANIFEST_DIM_TO_INTERNAL.get(dim, dim)
    _EMPIRICAL = {
        "syntax", "p1_p2_issues", "service_health",
        "p1_all", "security_p2", "reliability_p2", "maintainability_p2",
    }
    _BINARY = {"bias_check", "user_acceptance"}
    if dim in _EMPIRICAL:
        return "empirical", 0.3
    if dim in _BINARY:
        return "binary", None
    return "heuristic", 1.5


def detect_stagnation(score_history, gates, template_key=None):
    """检测停滞和回归

    停滞：同一维度连续 N 轮改进低于模板特定阈值（平台期）。
    回归：同一维度连续 N 轮分数下降。
    T6/T4 不适用。

    置信度适配（P1-05）：停滞阈值取 max(固定阈值, margin)。
    - empirical (margin=0.3): 保留现有固定阈值
    - heuristic (margin=1.5): 阈值放大到 margin，避免假阳性
    - binary (margin=None): 只看方向（improving/declining），不做数值比较

    返回: (results, eligible_dims)
        results: [(dim, recent_scores, signal_type), ...]，signal_type 为 'stagnating' | 'regressing'
        eligible_dims: 参与本窗口停滞/回归判定的维度集合（已达标 / KPI 已满足者已排除）
    """
    if template_key in ("T6", "T4"):
        return [], set()

    # "连续 N 轮改善 < 阈值"需要 N+1 个数据点来检查 N 次转换
    # STAGNATION_CONSECUTIVE=2 → 需要 3 个数据点，检查 2 次 R(n-1)→R(n) 转换
    if len(score_history) < STAGNATION_CONSECUTIVE + 1:
        return [], set()

    threshold, threshold_type = _get_stagnation_threshold(template_key) if template_key else (STAGNATION_THRESHOLD_PCT, "relative")

    window = score_history[-(STAGNATION_CONSECUTIVE + 1):]
    all_dims = set()
    for s in window:
        all_dims.update(s.keys())

    results = []
    eligible_dims = set()
    # 构建维度→门禁阈值映射，用于跳过已达标维度
    gate_thresholds = {}
    for g in (gates or []):
        g_dim = g.get("dim") or g.get("dimension", "")
        if not g_dim:
            continue
        g_thr = g.get("threshold")
        g_comp = g.get("comparator", ">=")
        if g_thr is not None:
            gate_thresholds[g_dim] = (g_thr, g_comp)

    for dim in sorted(all_dims):
        vals = [s.get(dim) for s in window]
        vals = [v for v in vals if v is not None]
        if len(vals) < STAGNATION_CONSECUTIVE + 1:
            continue

        # 跳过已达标维度：当前值满足门禁，无需报告停滞
        if dim in gate_thresholds:
            thr, comp = gate_thresholds[dim]
            current_val = vals[-1]
            if comp == ">=" and current_val >= thr:
                continue
            elif comp == "<=" and current_val <= thr:
                continue
            elif comp == "==" and current_val == thr:
                continue

        # T5 KPI 行（threshold null）：与 score/controller 一致，已满足则跳过停滞检测
        kpi_gate = None
        for g in (gates or []):
            gd = g.get("dim") or g.get("dimension", "")
            if gd == dim and g.get("threshold") is None:
                kpi_gate = g
                break
        if kpi_gate is not None and kpi_row_satisfied(kpi_gate, vals[-1]):
            continue

        eligible_dims.add(dim)

        # P1-05: 获取维度的置信度和误差范围
        confidence, margin = _confidence_for_dim(dim)

        # binary 维度：只看方向（整体改善 vs 整体恶化），不做数值比较
        if confidence == "binary":
            all_regressing = all(
                vals[i] < vals[i - 1] for i in range(1, len(vals))
            )
            if all_regressing:
                results.append((dim, vals, 'regressing'))
            # binary 维度不参与数值停滞判定
            continue

        # 检查是否所有转换都是回归（分数持续下降）
        all_regressing = all(
            vals[i] < vals[i - 1] for i in range(1, len(vals))
        )
        if all_regressing:
            results.append((dim, vals, 'regressing'))
            continue

        # P1-05: 停滞阈值适配 margin — 取 max(固定阈值, margin)
        # empirical (margin=0.3) 通常不影响现有阈值（固定阈值已 ≥ 0.3）
        # heuristic (margin=1.5) 放大阈值，避免误差范围内的波动被误判为停滞
        effective_threshold = threshold
        effective_type = threshold_type
        if margin is not None and threshold_type == "absolute":
            effective_threshold = max(threshold, margin)
        elif margin is not None and threshold_type == "relative":
            # 将 margin 转换为可比较的绝对值：用窗口内最小非零值估算
            min_nonzero = min((v for v in vals if v > 0), default=1.0)
            relative_as_absolute = threshold * min_nonzero
            if margin > relative_as_absolute:
                effective_threshold = margin
                effective_type = "absolute"

        # 检查停滞：无足够正向改进
        has_sufficient_improvement = False
        for i in range(1, len(vals)):
            delta = vals[i] - vals[i - 1]
            if delta <= 0:
                continue
            if effective_type == "absolute":
                if delta >= effective_threshold:
                    has_sufficient_improvement = True
                    break
            else:
                if vals[i - 1] == 0:
                    has_sufficient_improvement = True
                    break
                improvement = delta / vals[i - 1]
                if improvement >= effective_threshold:
                    has_sufficient_improvement = True
                    break

        if not has_sufficient_improvement:
            results.append((dim, vals, 'stagnating'))

    return results, eligible_dims


def _bool_gate_eval(cur, g, state):
    """bool 门禁当前值：bias_check 的 float 先按 <0.15 归一，再按 comparator/threshold 判定。"""
    dim = g.get("dim") or g.get("dimension", "")
    if dim == "bias_check" and isinstance(cur, (int, float)) and not isinstance(cur, bool):
        cur = cur < 0.15
    comp = g.get("comparator")
    if not comp:
        comp = _lookup_manifest_comparator(
            get_template(state), dim, g.get("manifest_dimension")
        ) or ">="
    thr = g.get("threshold")
    if comp == "==" and thr is not None:
        return cur == thr
    return bool(cur)


def _plan_numeric_gate_pass_at(cur, g, state):
    """threshold 非 None 时，单值 cur 是否满足该门禁（与 check_gates_passed 数值分支一致）。"""
    thr = g.get("threshold")
    dim = g.get("dim") or g.get("dimension", "")
    if cur is None:
        return False
    if g.get("unit") == "bool":
        return _bool_gate_eval(cur, g, state)
    comp = g.get("comparator")
    if not comp:
        comp = _lookup_manifest_comparator(
            get_template(state), dim, g.get("manifest_dimension")
        ) or ">="
    if comp == ">=":
        return cur >= thr
    if comp == "<=":
        return cur <= thr
    if comp == "==":
        return cur == thr
    if comp == "<":
        return cur < thr
    if comp == ">":
        return cur > thr
    return cur >= thr


def detect_cross_dimension_regression(state):
    """hard 数值门禁：上一轮满足、本轮不满足（pass→fail）。

    若 plan.decide_act_handoff.impacted_dimensions 非空，与推断的回归维合并后仍只报告实际发生 pass→fail 的维；
    若 handoff 未填，则按 VERIFY 后分数历史 **推断** 所有 hard 非豁免维的 pass→fail（与 loop-protocol 补齐契约）。
    """
    hist = get_score_history(state)
    if len(hist) < 2:
        return False, []
    prev, cur = hist[-2], hist[-1]
    gates = get_gates(state)
    violated = []
    seen = set()
    for g in gates:
        if (g.get("gate") or "").lower() != "hard":
            continue
        if plan_gate_is_exempt(g):
            continue
        thr = g.get("threshold")
        if thr is None:
            continue
        dim = g.get("dim") or g.get("dimension", "")
        if not dim:
            continue
        pv, cv = prev.get(dim), cur.get(dim)
        if pv is None or cv is None:
            continue
        if _plan_numeric_gate_pass_at(pv, g, state) and not _plan_numeric_gate_pass_at(
            cv, g, state
        ):
            if dim not in seen:
                seen.add(dim)
                violated.append(dim)
    if not violated:
        return False, []
    return True, violated


def check_gates_passed(state):
    """检查所有 hard gate 是否已通过，返回 (all_passed, details)"""
    scores = get_current_scores(state)
    gates = get_gates(state)
    if not gates:
        return True, []

    details = []
    all_hard_passed = True
    for g in gates:
        dim = g.get("dim") or g.get("dimension", "")
        threshold = g.get("threshold")
        gate_type = g.get("gate", "soft")
        current = scores.get(dim)
        label = g.get("label", dim)

        if not dim:
            continue

        if plan_gate_is_exempt(g):
            passed = True
        # KPI 行：豁免等状态可先于 scores 判定；与 autoloop_kpi.kpi_row_satisfied 一致
        elif threshold is None:
            passed = kpi_row_satisfied(g, current)
        elif current is None:
            passed = False
        elif g.get("unit") == "bool":
            passed = _bool_gate_eval(current, g, state)
        else:
            # 使用 manifest comparator（与 score.py _eval_gate 一致）
            # 优先从 gate 定义取，回退到 manifest 查找，最后默认 >=
            comp = g.get("comparator")
            if not comp:
                comp = _lookup_manifest_comparator(
                    get_template(state), dim, g.get("manifest_dimension")
                ) or ">="
            if comp == ">=":
                passed = current >= threshold
            elif comp == "<=":
                passed = current <= threshold
            elif comp == "==":
                passed = current == threshold
            elif comp == "<":
                passed = current < threshold
            elif comp == ">":
                passed = current > threshold
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

def _plan_gate_matches_score_result(gate_def, gate_result):
    """plan.gates 行与评分 JSON 条目的匹配（内部 dim 或 manifest_dimension）。"""
    pg = gate_def.get("dim") or gate_def.get("dimension", "")
    if gate_result.get("dimension") == pg:
        return True
    sr_man = gate_result.get("manifest_dimension")
    gd_man = gate_def.get("manifest_dimension")
    if sr_man and gd_man and sr_man == gd_man:
        return True
    return False


def _observe_target_gap_cells(g, cur_display, template_key):
    """OBSERVE 表：目标列与差距列（与 ORIENT 语义对齐，差距为启发式）。"""
    dim = g.get("dim") or g.get("dimension", "")
    thr = g.get("threshold")
    tgt = g.get("target")
    comp = g.get("comparator")
    if not comp:
        comp = _lookup_manifest_comparator(
            template_key, dim, g.get("manifest_dimension")
        ) or ">="
    if thr is None and tgt is not None:
        disp_tgt = tgt
    else:
        disp_tgt = thr if thr is not None else "—"
    gap = ""
    if cur_display in ("—", "", None):
        return str(disp_tgt), gap
    try:
        cur = float(cur_display)
    except (ValueError, TypeError):
        return str(disp_tgt), gap
    if thr is None and tgt is not None:
        try:
            tnum = float(tgt)
            if cur >= tnum:
                gap = "PASS"
            elif abs(tnum) > 1e-9:
                gap = "{:.0f}%".format((tnum - cur) / abs(tnum) * 100)
        except (ValueError, TypeError):
            pass
        return str(disp_tgt), gap
    if not isinstance(thr, (int, float)):
        return str(disp_tgt), gap
    if comp == "==":
        gap = "PASS" if cur == thr else ("FAIL" if thr != 0 else "FAIL Δ={}".format(cur))
    elif comp == "<=":
        gap = "PASS" if cur <= thr else "FAIL"
    elif comp in (">", ">="):
        if cur >= thr:
            gap = "PASS"
        elif thr != 0:
            gap = "{:.1f}%".format(max(0.0, (thr - cur) / thr * 100))
        else:
            gap = "FAIL"
    else:
        if thr != 0 and cur < thr:
            gap = "{:.1f}%".format((thr - cur) / thr * 100)
        else:
            gap = "PASS" if cur >= thr else "FAIL"
    return str(disp_tgt), gap


def _latest_tsv_fail_closed(state):
    """与 autoloop-variance check 一致：方差≥2 或置信度<50%（且≠0）视为 fail-closed。"""
    fc, _ = results_tsv_last_row_fail_closed(state)
    return fc


def _record_lesson_quality_issue(work_dir, strategy_id, lesson, missing):
    """将 lesson_learned 质量不足记录到 autoloop-findings.md 的问题清单中。"""
    fpath = os.path.join(work_dir, "autoloop-findings.md")
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    entry = (
        "\n### lesson_learned 质量不足 — {} ({})\n"
        "- strategy_id: {}\n"
        "- 问题: {}\n"
        "- 当前内容: \"{}\"\n"
    ).format(now, strategy_id, strategy_id, "; ".join(missing), lesson[:200])
    try:
        with open(fpath, "a", encoding="utf-8") as f:
            f.write(entry)
    except OSError:
        pass  # findings.md 不存在时静默跳过（不阻塞主流程）


def _append_immediate_discovery(work_dir, round_num, text):
    """将即时发现追加到 autoloop-findings.md 的「即时发现」区域。"""
    fpath = os.path.join(work_dir, "autoloop-findings.md")
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    entry = f"\n[即时发现 R{round_num}] ({now}) {text}\n"
    try:
        with open(fpath, "a", encoding="utf-8") as f:
            f.write(entry)
    except OSError:
        pass  # findings.md 不存在时静默跳过


def _detect_cross_round_repeat_patterns(state, round_num):
    """检测跨轮重复模式：同一问题连续 2+ 轮出现。返回重复描述列表。"""
    if round_num < 2:
        return []
    rnds = (state.get("findings") or {}).get("rounds") or []
    if len(rnds) < 2:
        return []
    # 提取最近两轮的问题描述
    def _extract_problems(rnd):
        items = rnd.get("findings", [])
        return [
            (f.get("summary") or f.get("description") or f.get("content", "")).strip().lower()
            for f in items
            if isinstance(f, dict)
        ]

    prev = set(_extract_problems(rnds[-2])) if len(rnds) >= 2 else set()
    curr = set(_extract_problems(rnds[-1]))
    prev.discard("")
    curr.discard("")
    repeated = prev & curr
    return [p for p in repeated if p]


def _maybe_reflect_experience_write(work_dir, state, tmpl):
    """若 iterations[-1].reflect 为结构化 dict，则确定性调用 autoloop-experience write。

    ``--score`` 仅表示单轮 **delta**（与 experience-registry avg_delta 一致）。
    Likert 填 ``rating_1_to_5``，不得当作 delta 写入；遗留键 ``score`` 若为整数 1–5 视为 Likert并跳过。
    """
    iters = state.get("iterations", [])
    if not iters:
        return
    ref = iters[-1].get("reflect")
    if not isinstance(ref, dict):
        return
    sid = str(ref.get("strategy_id", "")).strip()
    effect = str(ref.get("effect", "")).strip()
    if not sid or effect not in ("保持", "避免", "待验证"):
        return

    delta = ref.get("delta")
    rating = ref.get("rating_1_to_5")
    legacy = ref.get("score")

    score_for_write = None
    if delta is not None:
        score_for_write = delta
    elif legacy is not None:
        try:
            fv = float(legacy)
            iv = int(fv)
        except (TypeError, ValueError):
            score_for_write = legacy
        else:
            if fv == iv and 1 <= iv <= 5:
                info(
                    "iterations[-1].reflect.score 为 1–5 整数，视为 Likert；"
                    "请使用 delta 记分数变化或单独填 rating_1_to_5；跳过经验库 delta 写入"
                )
                return
            score_for_write = legacy

    if score_for_write is None:
        if rating is not None:
            info(
                "iterations[-1].reflect 仅有 rating_1_to_5（Likert），"
                "不参与经验库 delta 聚合；跳过 autoloop-experience write"
            )
        return

    dimension = str(ref.get("dimension", "—"))
    context = str(ref.get("context", ""))
    args = [
        work_dir, "write",
        "--strategy-id", sid,
        "--effect", effect,
        "--score", str(score_for_write),
        "--template", tmpl,
        "--dimension", dimension,
    ]
    if context:
        args.extend(["--context", context])
    st = ref.get("status")
    if st:
        args.extend(["--status", str(st)])
    # --- lesson_learned 质量检查（effect="避免" 且 delta < 0 时强制）---
    lesson = str(ref.get("lesson_learned", "")).strip()
    if effect == "避免" and score_for_write is not None:
        try:
            delta_val = float(score_for_write)
        except (ValueError, TypeError):
            delta_val = 0.0
        if delta_val < 0:
            lesson_ok = True
            missing = []
            if not lesson or len(lesson) <= 20:
                lesson_ok = False
                missing.append("lesson_learned 为空或过短（≤20字符）")
            else:
                # 检查三要素信号：做了什么 / 为什么失败 / 替代建议
                has_what = any(kw in lesson for kw in ("尝试", "tried", "did", "做了", "执行", "adopted", "used", "applied"))
                has_why = any(kw in lesson for kw in ("因为", "because", "导致", "caused", "失败", "failed", "问题", "issue", "原因"))
                has_instead = any(kw in lesson for kw in ("改用", "instead", "替代", "应该", "should", "建议", "recommend", "better"))
                if not has_what:
                    missing.append("缺少'做了什么'描述")
                if not has_why:
                    missing.append("缺少'为什么失败'原因")
                if not has_instead:
                    missing.append("缺少'替代建议'")
            if not lesson_ok or missing:
                warn(
                    "Strategy marked as '避免' with negative delta but lesson_learned is insufficient.\n"
                    "  Required: describe (1) what was tried, (2) why it failed, (3) what to do instead.\n"
                    "  Current lesson_learned: \"{}\"\n"
                    "  Issues: {}".format(lesson[:120], "; ".join(missing))
                )
                # 记录到 findings 问题清单
                _record_lesson_quality_issue(work_dir, sid, lesson, missing)

    info("根据 iterations[-1].reflect 写入经验库...")
    _, rc = run_tool("autoloop-experience.py", args, capture=True, work_dir=work_dir)
    if rc != 0:
        warn("经验库 write 返回非零，仍请检查 reflect 字段与 experience-registry 路径")


def _t3_kpi_actionable(gates):
    """T5 至少有一条 KPI 行（threshold null）且已填 target（quality-gates.md）。"""
    rows = [g for g in (gates or []) if g.get("threshold") is None]
    if not rows:
        return False
    return any(g.get("target") is not None for g in rows)


def _findings_md_protocol_version(text):
    """从 findings.md 前部扫描协议版本号（如 1.0.0），供与 SSOT 比对。"""
    head = "\n".join(text.splitlines()[:120])
    for line in head.splitlines():
        s = line.strip()
        if "protocol" in s.lower() or "协议版本" in s:
            m = re.search(r"(\d+\.\d+\.\d+)", s)
            if m:
                return m.group(1)
    return None


def _findings_md_h2_section_lines(lines, keywords):
    """第一个匹配 ``## `` 标题且含任一 keyword 的节，返回到下一同级 ``## `` 为止的行（不含标题）。"""
    for i, line in enumerate(lines):
        if line.startswith("## ") and any(k in line for k in keywords):
            out = []
            for j in range(i + 1, len(lines)):
                ln = lines[j]
                if ln.startswith("## "):
                    break
                out.append(ln)
            return out
    return []


def _count_md_table_body_lines(section_lines):
    """H2 节内：计 markdown 管道表**数据行**（表头+|---| 之后；无分隔行则回退为管道行计数）。"""
    lines = section_lines
    sep_i = -1
    for i, line in enumerate(lines):
        if line.count("|") >= 2 and "---" in line:
            sep_i = i
            break
    start = sep_i + 1 if sep_i >= 0 else 0

    def _row(line):
        if line.count("|") < 2:
            return False
        s = line.strip()
        if "---" in s and line.count("|") >= 2:
            return False
        if re.match(r"^[\|\s\-:]+$", s):
            return False
        inner = "|".join(p.strip() for p in s.split("|"))
        return bool(inner) and not (set(inner) <= set("-: \t"))

    if sep_i >= 0:
        return sum(1 for line in lines[start:] if _row(line))
    return sum(1 for line in lines if _row(line))


def _findings_md_four_layer_table_stats(text):
    """四层反思：各层 H2 下表格行数估计（0=未找到节或无数表行）。"""
    lines = text.splitlines()
    specs = (
        ("L1问题清单", ("问题清单", "第1层", "REFLECT 第 1")),
        ("L2策略评估", ("策略评估", "第2层", "REFLECT 第 2")),
        ("L3模式识别", ("模式识别", "第3层", "REFLECT 第 3")),
        ("L4经验教训", ("经验教训", "第4层", "REFLECT 第 4")),
    )
    return {
        label: _count_md_table_body_lines(_findings_md_h2_section_lines(lines, kws))
        for label, kws in specs
    }


def _strict_evolve_requires_tsv_current_round(state, round_num):
    """STRICT：末行 results_tsv.iteration 须与当前 OODA 轮次一致（防 VERIFY 漏写行）。"""
    rows = state.get("results_tsv") or []
    if not rows:
        return False
    last = rows[-1]
    lit = last.get("iteration")
    try:
        return int(lit) == int(round_num)
    except (TypeError, ValueError):
        return str(lit).strip() == str(round_num).strip()


def _strict_evolve_requires_findings(state):
    """STRICT：EVOLVE 前须已有本轮结构化 finding（评审建议 #4 确定性校验点）。"""
    it = state.get("iterations") or []
    if it and it[-1].get("findings"):
        return True
    rnds = (state.get("findings") or {}).get("rounds") or []
    return bool(rnds and rnds[-1].get("findings"))


def _observe_report_findings_md(work_dir, state):
    """OBSERVE Step 0：探测 work_dir/autoloop-findings.md（loop-protocol 反思 4 层锚点）。"""
    path = os.path.join(work_dir, "autoloop-findings.md")
    if not os.path.isfile(path):
        info("OBSERVE Step 0: autoloop-findings.md 不存在（仅靠 SSOT findings + 后续 render）")
        return
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            text = f.read()
    except OSError as e:
        warn("OBSERVE Step 0: 无法读取 autoloop-findings.md — {}".format(e))
        return
    n = len(text)
    anchors = (
        ("问题清单/第1层", ("问题清单" in text) or ("REFLECT 第 1" in text)),
        ("策略评估/第2层", ("策略评估" in text) or ("REFLECT 第 2" in text)),
        ("模式识别/第3层", ("模式识别" in text) or ("REFLECT 第 3" in text)),
        ("经验教训/第4层", ("经验教训" in text) or ("REFLECT 第 4" in text)),
    )
    hits = [label for label, ok in anchors if ok]
    info(
        "OBSERVE Step 0: autoloop-findings.md 可读（{} 字符）；反思结构锚点: {}".format(
            n, "、".join(hits) if hits else "未命中（可补全 4 层表）"
        )
    )
    meta = state.get("metadata") or {}
    pv = meta.get("protocol_version")
    if pv:
        info("  SSOT metadata.protocol_version={}".format(pv))
    f_pv = _findings_md_protocol_version(text)
    if f_pv:
        info("  findings.md 探测到 protocol 版本片段: {}".format(f_pv))
    if f_pv and pv and str(f_pv) != str(pv):
        warn(
            "  findings.md 与 SSOT metadata.protocol_version 不一致 — 按 loop-protocol 考虑重基线"
        )
    stats = _findings_md_four_layer_table_stats(text)
    stat_s = "; ".join("{}={}".format(k, v) for k, v in stats.items())
    info("  四层表行数估计（H2 节内）: {}".format(stat_s))
    if sum(stats.values()) == 0:
        info(
            "  rebaseline 提示: 未识别到四层 ## 标题下表格行；可对照 loop-protocol 补全 "
            "「问题清单/策略评估/模式识别/经验教训」各一节"
        )

    def _persist_observe_snapshot(st):
        m = st.setdefault("metadata", {})
        m["observe_findings_snapshot"] = {
            "path": "autoloop-findings.md",
            "char_count": n,
            "anchors_hit": list(hits),
            "four_layer_table_stats": dict(stats),
            "findings_md_protocol_version": f_pv,
            "ssot_protocol_version": pv,
        }
        if f_pv and pv and str(f_pv) != str(pv):
            m["rebaseline_required"] = True
        elif f_pv and pv:
            m["rebaseline_required"] = False

    _record_state_metadata(work_dir, _persist_observe_snapshot)


def phase_observe(work_dir, state, round_num):
    """OBSERVE: 输出当前得分 vs 目标，读取经验库推荐。

    返回 (decision, reasons)：decision 为 \"continue\" 或 \"pause\"（T5 缺 KPI 时暂停）。
    """
    banner(round_num, "OBSERVE", "采集当前状态")

    le = state.get("metadata", {}).get("last_error")
    if isinstance(le, dict) and le.get("script"):
        warn(
            "最近子进程错误: {} rc={} @ {}".format(
                le.get("script"), le.get("returncode"), le.get("time", "")
            )
        )
        sn = (le.get("stderr") or "").strip()
        if sn:
            warn("  stderr: {}".format(sn[:400]))

    scores = get_current_scores(state)
    gates = get_gates(state)
    template = get_template(state)

    if template == "T5" and not _t3_kpi_actionable(gates):
        warn(
            "T5 未配置可执行 KPI：请在 plan.gates 中为 KPI 行填写 target 与 dim（测量维度键须与 iterations[].scores 一致）。"
        )
        error(
            "OBSERVE: KPI 未就绪 — 暂停任务（与 quality-gates.md T5「KPI 定义缺失时 OBSERVE 暂停」一致）"
        )
        return "pause", [
            "T5 缺少 KPI 定义或 target；请补全 plan.gates 后 autoloop-controller.py <work_dir> --resume"
        ]

    # 0. 首轮记录 gate-manifest.json mtime（用于 VERIFY 阶段防篡改检查）
    if round_num == 1:
        manifest_path = os.path.join(os.path.dirname(__file__), "..", "references", "gate-manifest.json")
        try:
            mtime = os.path.getmtime(manifest_path)
            state.setdefault("metadata", {})["manifest_mtime"] = mtime
            save_json(os.path.join(work_dir, STATE_FILE), state)
            info(f"已记录 gate-manifest.json mtime: {mtime}")
        except OSError:
            warn("无法读取 gate-manifest.json mtime")

    # 1. 当前分数 vs 门禁目标
    info(f"模板: {template} | 轮次: {round_num}/{get_max_rounds(state)}")
    if scores:
        print(f"\n{'维度':<20} {'当前':>8} {'目标':>8} {'差距':>8} {'门禁':>6}")
        print("─" * 56)
        for g in gates:
            dim = g.get("dim") or g.get("dimension", "")
            if not dim:
                continue
            cur = scores.get(dim, "—")
            tgt_s, gap = _observe_target_gap_cells(g, cur, template)
            print(f"{g.get('label', dim):<20} {str(cur):>8} {tgt_s:>8} {gap:>8} {g['gate']:>6}")
    else:
        warn("无历史评分数据（首轮）")

    # 1b. 上轮 findings 摘要（可选记忆）
    rnds = state.get("findings", {}).get("rounds", [])
    if rnds:
        last_r = rnds[-1]
        items = last_r.get("findings", [])
        if items:
            info("上轮 findings 摘要（最近 3 条）:")
            for f in items[-3:]:
                line = f.get("summary") or f.get("content") or f.get("description", "")
                d = f.get("dimension", "—")
                if line:
                    print(f"  [{d}] {str(line)[:120]}")

    # 1c. 结构化反思（SSOT）：lessons_learned + 上一轮 iterations.reflect
    ll = state.get("findings", {}).get("lessons_learned") or {}
    if isinstance(ll, dict):
        blocks = []
        for key, label in (
            ("verified_hypotheses", "已验证假设"),
            ("generalizable_methods", "可泛化方法"),
            ("process_improvements", "流程改进"),
        ):
            arr = ll.get(key)
            if isinstance(arr, list) and arr:
                preview = arr[:3]
                blocks.append("{}: {}".format(label, "; ".join(str(x)[:80] for x in preview)))
        if blocks:
            info("上轮反思结构（findings.lessons_learned）:")
            for b in blocks:
                print(f"  {b}")
    iters = state.get("iterations", [])
    if len(iters) >= 2:
        prev_ref = iters[-2].get("reflect")
        if isinstance(prev_ref, dict) and prev_ref:
            info("上一轮 iterations[-2].reflect 摘要:")
            for k in (
                "strategy_id",
                "effect",
                "lesson_learned",
                "delta",
                "rating_1_to_5",
                "score",
                "dimension",
            ):
                if prev_ref.get(k) not in (None, ""):
                    print(f"  {k}: {str(prev_ref.get(k))[:200]}")

    _observe_report_findings_md(work_dir, state)

    # 1d. 即时学习钩子：跨轮重复模式检测（Round 2+）
    if round_num >= 2:
        repeats = _detect_cross_round_repeat_patterns(state, round_num)
        if repeats:
            info(f"[即时学习] 检测到 {len(repeats)} 个跨轮重复模式，立即写入 findings.md 模式识别部分")
            for r in repeats:
                pattern_msg = f"跨轮重复模式：「{r[:120]}」连续 2+ 轮出现，可能存在系统性根因"
                _append_immediate_discovery(work_dir, round_num, pattern_msg)
                info(f"  → {pattern_msg[:150]}")

    # 2. 经验库推荐 — (同模板 OR applicable_templates匹配) + context_tags 重叠≥2（见 loop-protocol）；无 plan.context_tags 时为冷启动
    ctx_csv = _plan_context_tags_csv(state.get("plan") or {})
    qargs = [work_dir, "query", "--template", template, "--include-global"]
    if ctx_csv:
        qargs.extend(["--tags", ctx_csv])
        info("查询经验库 (模板={}, context_tags={}, include_global)...".format(template, ctx_csv))
    else:
        info("查询经验库 (模板={}, include_global)...".format(template))
    output, rc = run_tool(
        "autoloop-experience.py",
        qargs,
        capture=True,
        work_dir=work_dir,
    )
    if rc == 0 and output.strip():
        print(f"\n{C_DIM}{output.strip()}{C_RESET}\n")
    elif rc != 0:
        warn(
            "经验库查询失败或未找到 experience-registry.md"
            "（可置于工作目录 references/ 或技能包 references/）"
        )
    else:
        info("经验库无匹配策略（首轮冷启动）")

    # 3. OBSERVE 必须输出字段清单（P2-17）
    info("--- OBSERVE 必须输出字段 ---")
    info("1. current_scores: 各维度当前分数 (dict[str, float])")
    info("2. target_scores: 各维度目标分数 (dict[str, float])")
    info("3. remaining_budget_pct: 剩余预算% (float)")
    info("4. focus_dimensions: 本轮重点维度 (list[str])")
    info("5. carry_over_issues: 跨轮遗留问题 (list[str], 可选)")
    info("------------------------------")

    return "continue", []


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
        dim = g.get("dim") or g.get("dimension", "")
        if not dim:
            continue
        cur = scores.get(dim)
        thr = g.get("threshold")
        label = g.get("label", dim)

        # T5 / 用户自定义 KPI：threshold 为 None 时用 target 与当前分算差距（对齐 check_gates_passed）
        if thr is None:
            tgt = g.get("target")
            if tgt is not None and cur is not None:
                try:
                    tnum = float(tgt)
                    cnum = float(cur)
                except (ValueError, TypeError):
                    moderate.append((label, dim, cur, "KPI 非数值，待对齐"))
                    continue
                if cnum >= tnum:
                    passed.append((label, dim, cur, "PASS"))
                else:
                    gap_pct = ((tnum - cnum) / abs(tnum) * 100) if abs(tnum) > 1e-9 else 100.0
                    bucket = critical if gap_pct > 50 else moderate if gap_pct > 20 else minor
                    bucket.append((label, dim, cur, f"{gap_pct:.0f}%"))
                continue
            if cur is None and tgt is None:
                moderate.append((label, dim, "—", "待定义 KPI 目标与当前分"))
            elif cur is None:
                moderate.append((label, dim, "—", f"目标={tgt}，待采集当前分"))
            else:
                moderate.append((label, dim, cur, "未配置 target"))
            continue

        if cur is None:
            critical.append((label, dim, "无数据", "—"))
            continue

        if g.get("unit") == "bool":
            ok = _bool_gate_eval(cur, g, state)
            if ok:
                passed.append((label, dim, cur, "PASS"))
            else:
                critical.append((label, dim, cur, "未达标"))
            continue

        # 使用 comparator 判断 pass/fail 方向
        comp = g.get("comparator")
        if not comp:
            comp = _lookup_manifest_comparator(
                get_template(state), dim, g.get("manifest_dimension")
            ) or ">="

        if comp in ("<=", "=="):
            # 越少越好或精确匹配
            check_pass = (cur <= thr) if comp == "<=" else (cur == thr)
            if check_pass:
                passed.append((label, dim, cur, "PASS"))
            else:
                gap_pct = ((cur - thr) / max(cur, 1)) * 100
                bucket = critical if gap_pct > 50 else moderate if gap_pct > 20 else minor
                bucket.append((label, dim, cur, f"{gap_pct:.0f}%"))
            continue

        # 越高越好（>=, >）
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

    info(
        "说明: comparator 为 <= / == 的门禁，上表「差距」百分比为 ORIENT 启发式展示；"
        "正式通过/未通过以 VERIFY 阶段 autoloop-score 与 plan.gates 为准（E-02）。"
    )

    # 振荡 & 停滞检测
    history = get_score_history(state)
    tmpl = get_template(state)
    osc = detect_oscillation(history)
    stag, _eligible = detect_stagnation(history, gates, template_key=tmpl)
    stag_dims = {d for d, _, _ in stag} if stag else set()
    osc_for_display = [x for x in osc if x[0] not in stag_dims]

    if osc_for_display:
        warn("振荡检测（已与停滞/回归同维去重，与 EVOLVE 一致）:")
        for dim, vals, _ in osc_for_display:
            warn(f"  {dim}: 最近 {OSCILLATION_WINDOW} 轮评分 {vals} — 波动 ≤ ±{OSCILLATION_BAND}")
    if stag:
        threshold, threshold_type = _get_stagnation_threshold(tmpl)
        if threshold_type == "absolute":
            threshold_str = f"{threshold} 分（绝对值）"
        else:
            threshold_str = f"{threshold*100:.0f}%（相对值）"
        warn(f"停滞/回归检测（模板={tmpl}, 阈值={threshold_str}）:")
        for dim, vals, signal in stag:
            if signal == 'regressing':
                warn(f"  {C_RED}[回归]{C_RESET} {dim}: 最近评分 {vals} — 分数持续下降，需立即调查根因")
            else:
                warn(f"  [停滞] {dim}: 最近评分 {vals} — 改进低于阈值，建议切换策略")


def phase_decide(work_dir, state, round_num, strict_cli=False, enforce_strategy_history=False):
    """DECIDE: 输出策略选择提示（LLM 填充）"""
    banner(round_num, "DECIDE", "策略选择")

    st = _strict_enabled(strict_cli)
    hard = st or _enforce_strategy_history_enabled(enforce_strategy_history)
    _decide_strategy_preflight(state, hard)

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

        6. 【结构化交接 — 必做】将本轮决策写入 plan.decide_act_handoff（JSON）:
           autoloop-state.py update {work_dir} plan.decide_act_handoff '<JSON 单行>'

        7. 【可复制模板 — 固定键顺序】仅替换占位后整行执行:
           {{"strategy_id":"S{round_num:02d}-short-name","hypothesis":"本轮假设一句话","planned_commands":["命令1","可选命令2"],"impacted_dimensions":["dimA","dimB"]}}

           约束: strategy_id 须与上文「策略ID」一致且符合 SNN-描述；经验库推荐策略仅作参考，本轮只选一条主 strategy_id。
           若有跨维影响，填写 impacted_dimensions（字符串列表）；VERIFY 写入 TSV 时 side_effect 不得填「无」（strict 下 validate 会检查）。
    """)

    # DECIDE 必须输出字段清单（P2-17）
    info("--- DECIDE 必须输出字段 ---")
    info("1. strategy_id: S{NN}-{描述} 格式 (str)")
    info("2. action_plan: 具体行动列表 (list[str])")
    info("3. fallback: 备用策略 (str)")
    info("4. impacted_dimensions: 可能受影响的维度 (list[str])")
    info("------------------------------")


##############################################################################
# ACT 失败类型分类与差异化恢复
##############################################################################

FAILURE_TYPES = ("timeout", "capability_gap", "resource_missing", "external_error", "code_error", "partial_success")

RECOVERY_STRATEGIES = {
    "timeout": "拆分任务（任务太大），缩小范围后重试",
    "capability_gap": "换角色或调整工具配置",
    "resource_missing": "暂停并请求用户提供缺失资源",
    "external_error": "指数退避重试（delay = min(base * 2^attempt, 300)）",
    "code_error": "记录 bug，修复后重试",
    "partial_success": "从断点继续（保留已完成部分）",
}


def classify_failure(error_msg, exit_code=None):
    """根据错误信息自动分类失败类型（当 subagent 未显式返回 failure_type 时使用）。"""
    if exit_code and exit_code == 124:  # timeout exit code
        return "timeout"
    error_lower = (error_msg or "").lower()
    if any(k in error_lower for k in ("timeout", "timed out", "context limit")):
        return "timeout"
    if any(k in error_lower for k in ("rate limit", "429", "503", "network")):
        return "external_error"
    if any(k in error_lower for k in ("traceback", "syntax error", "import error")):
        return "code_error"
    if any(k in error_lower for k in ("not found", "permission denied", "no such file")):
        return "resource_missing"
    return "capability_gap"  # 默认


def parse_completion_ratio(state):
    """从 state.json 的 iterations[-1].act 中提取 completion_ratio。

    返回 int (0-100) 或 None（未找到/格式错误）。
    """
    iterations = state.get("iterations") or []
    if not iterations:
        return None
    act_data = iterations[-1].get("act")
    if not act_data:
        return None
    # act_data 可能是 dict 或 JSON 字符串
    if isinstance(act_data, str):
        try:
            act_data = json.loads(act_data)
        except (json.JSONDecodeError, TypeError):
            return None
    if not isinstance(act_data, dict):
        return None
    raw = act_data.get("completion_ratio")
    if raw is None:
        return None
    try:
        ratio = int(raw)
        return max(0, min(100, ratio))
    except (ValueError, TypeError):
        return None


def process_act_completion(work_dir, state):
    """ACT→VERIFY 过渡：解析 completion_ratio 并标注 partial / needs_replanning。

    返回 True 表示可继续进入 VERIFY，False 表示建议重新规划（但不阻断）。
    """
    ratio = parse_completion_ratio(state)
    if ratio is None:
        return True  # 未提供 completion_ratio，默认正常推进

    if ratio >= 80:
        info(f"Subagent 完成度: {ratio}% — 正常进入 VERIFY")
        return True
    elif ratio >= 50:
        warn(f"Subagent 完成度: {ratio}% — 部分完成，进入 VERIFY 但标注 partial")
        run_tool(
            "autoloop-state.py",
            ["update", work_dir, "iterations[-1].act.partial", "true"],
            work_dir=work_dir,
        )
        return True
    else:
        warn(f"Subagent 完成度: {ratio}% — 完成度不足，建议 DECIDE 重新规划")
        run_tool(
            "autoloop-state.py",
            ["update", work_dir, "iterations[-1].act.needs_replanning", "true"],
            work_dir=work_dir,
        )
        return False


def log_act_failure(work_dir, state, failure_type, failure_detail="", completion_ratio=0):
    """将失败类型和恢复策略写入 state.json 的 iterations[-1].act。"""
    recovery = RECOVERY_STRATEGIES.get(failure_type, RECOVERY_STRATEGIES["capability_gap"])
    warn(f"ACT 失败类型: {failure_type} — {failure_detail}")
    info(f"恢复策略: {recovery}")

    # 写入 state.json
    act_failure = json.dumps({
        "failure_type": failure_type,
        "failure_detail": failure_detail,
        "completion_ratio": completion_ratio,
        "recovery_action": recovery,
    }, ensure_ascii=False)
    run_tool("autoloop-state.py", ["update", work_dir, "iterations[-1].act", act_failure], work_dir=work_dir)


TASK_TYPE_MAP = {
    "T1": ("research", "优先使用 web_search 工具广泛收集信息"),
    "T2": ("analysis", "优先使用对比分析，关注差异和权衡"),
    "T3": ("design", "优先使用文档编写，产出结构化方案"),
    "T4": ("coding", "优先使用 edit_file 和 bash 工具"),
    "T5": ("iteration", "数据驱动，混合搜索和分析"),
    "T6": ("generation", "批量生成，注重效率和一致性"),
    "T7": ("review", "代码搜索和深度阅读，发现隐藏问题"),
    "T8": ("optimization", "重构和性能测试，验证改进效果"),
}


def get_recommended_model(template, phase="ACT"):
    """读取模型路由配置，返回推荐模型（信息性，不自动切换）。"""
    routing_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "..", "references", "model-routing.json",
    )
    if not os.path.exists(routing_path):
        return None
    try:
        with open(routing_path) as f:
            routing = json.load(f)
    except (json.JSONDecodeError, OSError):
        return None

    tmpl_config = routing.get("template_models", {}).get(template, {})
    if phase == "ACT" and tmpl_config.get("act_override"):
        return tmpl_config["act_override"]
    return tmpl_config.get("preferred", routing.get("default_model"))


def phase_act(work_dir, state, round_num, strict=False):
    """ACT: 输出 subagent 调度指令（LLM 执行）。strict 与 run_loop / CLI --strict 一致。"""
    banner(round_num, "ACT", "执行改进")

    template = get_template(state)
    handoff = state.get("plan", {}).get("decide_act_handoff")
    if handoff:
        info("已加载 plan.decide_act_handoff（DECIDE→ACT 交接）:")
        print(json.dumps(handoff, ensure_ascii=False, indent=2))
    elif strict:
        error(
            "STRICT: plan.decide_act_handoff 缺失 — 中止（请在 DECIDE 后写入 JSON 交接）"
        )
        return False

    tp = state.get("plan", {}).get("template_params") or {}
    globs = tp.get("allowed_script_globs") or tp.get("allowed_commands")
    if isinstance(globs, list) and globs:
        info("plan.template_params 白名单（脚本/命令 glob 或片段，执行时优先从此列表选用）:")
        for g in globs[:20]:
            print(f"  - {g}")
    elif isinstance(globs, str) and globs.strip():
        info("plan.template_params 白名单: {}".format(globs.strip()[:500]))

    sup = ""
    if template in ("T5", "T6", "T4"):
        sup = """
        交付类模板建议流程（可与 Superpowers 等技能对齐）:
        brainstorming → writing-plans → subagent-driven-development → TDD → requesting-code-review
        """

    task_type_hint = ""
    if template in TASK_TYPE_MAP:
        tt, hint = TASK_TYPE_MAP[template]
        task_type_hint = f"[任务类型: {tt}] {hint}"
        info(f"Task-Aware Dispatch: {task_type_hint}")

    cmd_chk = f"""\
        【推荐命令清单 — 按需复制】
          python3 scripts/autoloop-score.py {work_dir} --json
          python3 scripts/autoloop-validate.py {work_dir}
          python3 scripts/autoloop-validate.py {work_dir} --strict
          python3 scripts/autoloop-render.py {work_dir}
          python3 scripts/autoloop-variance.py check {work_dir}/autoloop-results.tsv
          python3 -m py_compile <你的.py>    # 或项目约定的 syntax_check_cmd
        （控制器不自动执行上述命令；VERIFY 阶段会调用 score/validate。）
    """

    model_hint = ""
    recommended = get_recommended_model(template, "ACT")
    if recommended:
        model_hint = f"推荐模型: {recommended}（信息性，需手动切换会话模型）"
        info(f"Model Routing: {model_hint}")

    prompt_block("执行策略", f"""\
        根据 DECIDE 阶段选定的策略，执行改进操作:

        工作目录: {work_dir}
        模板: {template}
        {task_type_hint}
        {model_hint}
        {sup}
        {cmd_chk}
        执行要求:
        1. 按策略中定义的执行方法逐步操作（可脚本化步骤优先用本仓库 autoloop-*.py / 测试命令）
        2. 每个修改立即验证（py_compile / tsc --noEmit）
        3. 记录所有变更到 state.json 的当前迭代
        4. 完成后更新评分相关的 findings

        失败时须返回结构化信息（写入 iterations[-1].act）:
          failure_type: timeout | capability_gap | resource_missing | external_error | code_error | partial_success
          failure_detail: 一句话描述
          completion_ratio: 0-100

        即时发现（可选）:
          如果 subagent 返回中包含 discoveries 列表（环境事实），会立即写入 findings.md，不等 REFLECT。
          详见 agent-dispatch.md「即时发现」规范。

        完成后运行:
          autoloop-state.py update {work_dir} plan.budget.current_round {round_num}
    """)
    # P2-03: ACT 完成后文件变更确认（T4/T7/T8）
    check_file_changes(work_dir, state)

    return True


def check_file_changes(work_dir, state):
    """检查 ACT 阶段是否有实际文件变更（仅 T4/T7/T8 工程类模板）。

    如果 git diff 为空，在 state 中标记 no_file_changes 并输出警告。
    """
    template = get_template(state)
    if template not in ("T4", "T7", "T8"):
        return  # 非工程模板不检查

    import subprocess
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", "HEAD"],
            cwd=work_dir, capture_output=True, text=True, timeout=10
        )
        changed_files = [f for f in result.stdout.strip().split("\n") if f]
    except (subprocess.TimeoutExpired, OSError) as e:
        warn(f"文件变更检查失败: {e}")
        return

    if not changed_files:
        warn("ACT 声称完成但未检测到文件变更（git diff 为空）。")
        warn("可能原因：subagent 未实际修改文件，或修改未保存。")
        # 写入 state: iterations[-1].act.no_file_changes = True
        iterations = state.get("plan", {}).get("iterations", [])
        if iterations:
            act = iterations[-1].setdefault("act", {})
            act["no_file_changes"] = True
            save_json(os.path.join(work_dir, STATE_FILE), state)
    else:
        info(f"ACT 文件变更确认: {len(changed_files)} 个文件已修改")
        for f in changed_files[:10]:
            info(f"  {f}")
        if len(changed_files) > 10:
            info(f"  ... 共 {len(changed_files)} 个文件")


def process_act_discoveries(work_dir, state, round_num, subagent_result):
    """ACT 即时学习钩子：处理 subagent 返回中的 discoveries 字段。

    从 subagent_result（dict 或 JSON str）中提取 discoveries 列表，
    立即写入 findings.md 和 state.json metadata.immediate_discoveries。
    """
    if isinstance(subagent_result, str):
        try:
            subagent_result = json.loads(subagent_result)
        except (json.JSONDecodeError, TypeError):
            return []
    if not isinstance(subagent_result, dict):
        return []
    discoveries = subagent_result.get("discoveries", [])
    if not isinstance(discoveries, list) or not discoveries:
        return []
    info(f"[即时学习] 发现 {len(discoveries)} 条环境事实")
    for d in discoveries:
        d_str = str(d).strip()
        if d_str:
            _append_immediate_discovery(work_dir, round_num, d_str)
            info(f"  → {d_str[:150]}")
    # 写入 state.json metadata
    state.setdefault("metadata", {}).setdefault("immediate_discoveries", []).extend(
        str(d).strip() for d in discoveries if str(d).strip()
    )
    save_json(os.path.join(work_dir, STATE_FILE), state)
    return discoveries


def _create_t3_scoring_findings(work_dir, state, round_num):
    """T3: 从 ACT 产出提取关键内容，创建 summary findings 供 score.py keyword 分析。"""
    # 从 iterations[-1].act.records 提取产出摘要
    iters = state.get("iterations", [])
    if not iters:
        return
    act_records = iters[-1].get("act", {}).get("records", [])

    # 收集所有 act 产出的描述/摘要
    summaries = []
    for rec in act_records:
        desc = rec.get("description", "") or rec.get("summary", "") or ""
        result = rec.get("result", "") or rec.get("output", "") or ""
        if desc:
            summaries.append(desc)
        if result and len(str(result)) < 2000:
            summaries.append(str(result))

    # 如果没有 act records，尝试从 output_files 读取
    if not summaries:
        output_files = state.get("plan", {}).get("output_files", {})
        for key, info_dict in output_files.items():
            if isinstance(info_dict, dict):
                fpath = info_dict.get("path", "")
                resolved = os.path.realpath(os.path.join(work_dir, fpath)) if fpath else ""
                if resolved and resolved.startswith(os.path.realpath(work_dir)) and os.path.exists(resolved):
                    try:
                        with open(resolved, "r", encoding="utf-8") as f:
                            content = f.read(3000)  # 前 3000 字符
                        summaries.append(content)
                    except OSError:
                        pass

    if not summaries:
        return

    combined = "\n".join(summaries)

    # 创建 5 个维度的 findings，包含可被 keyword 匹配的内容
    t3_dims = [
        ("design_completeness", "设计完整度：" + combined[:500]),
        ("feasibility_score", "技术可行性分析：架构设计、依赖分析、风险评估。" + combined[:300]),
        ("requirement_coverage", "需求覆盖：功能需求、用户故事、验收标准。" + combined[:300]),
        ("scope_precision", "范围定义：IN scope / OUT scope 边界明确。" + combined[:200]),
        ("validation_evidence", "验证证据：可行性检查、风险评估已完成。" + combined[:200]),
    ]

    for dim, content in t3_dims:
        finding_json = json.dumps({
            "dimension": dim,
            "content": content,
            "source": "auto-extracted from T3 ACT output",
            "confidence": "中",
            "type": "finding"
        }, ensure_ascii=False)
        run_tool("autoloop-state.py", ["add-finding", work_dir, finding_json],
                 capture=True, work_dir=work_dir)


def phase_verify(work_dir, state, round_num, strict=False):
    """VERIFY: 自动调用评分器和方差计算。返回 verify_ok（strict 时任一步失败为 False）。"""
    banner(round_num, "VERIFY", "评分验证")

    # T3: 自动从 ACT 产出创建评分 findings（score.py 需要 findings 做 keyword 分析）
    template = get_template(state)
    template_key = template.upper().split()[0] if template else ""
    if template_key == "T3" and round_num > 0:
        rounds = state.get("findings", {}).get("rounds", [])
        has_findings = any(
            rnd.get("findings") for rnd in rounds
        )
        if not has_findings:
            info("T3: findings.rounds 为空，从 ACT 产出创建评分 findings...")
            _create_t3_scoring_findings(work_dir, state, round_num)
            state = load_state(work_dir)  # reload after findings creation

    verify_ok = True

    # gate-manifest.json 防篡改 mtime 检查
    recorded_mtime = state.get("metadata", {}).get("manifest_mtime")
    if recorded_mtime is not None:
        manifest_path = os.path.join(os.path.dirname(__file__), "..", "references", "gate-manifest.json")
        try:
            current_mtime = os.path.getmtime(manifest_path)
            if current_mtime != recorded_mtime:
                warn(f"gate-manifest.json 已被修改（mtime {recorded_mtime} → {current_mtime}）。")
                warn("门禁 SSOT 在任务运行期间发生变更，请确认是否为预期操作。")
                warn("如确认合法，请 update metadata.manifest_mtime 或重新 init。暂停评分。")
                return False
        except OSError:
            warn("无法读取 gate-manifest.json mtime，跳过防篡改检查")

    info("运行评分器...")
    stdout, rc = run_tool(
        "autoloop-score.py", [work_dir, "--json"], capture=True, work_dir=work_dir
    )
    score_results = []
    score_parse_ok = False
    if rc in (0, 1) and stdout.strip():
        try:
            score_result = json.loads(stdout.strip())
            info(f"评分结果: {json.dumps(score_result, ensure_ascii=False, indent=2)}")
            score_results = score_result.get("gates", [])
            score_parse_ok = bool(score_results)
        except json.JSONDecodeError:
            info(f"评分输出:\n{stdout}")
    else:
        warn(f"评分器未返回 JSON 输出 (rc={rc})")
        if stdout.strip():
            print(stdout)
    if strict and not score_parse_ok:
        verify_ok = False
        error("STRICT: 评分器未返回可解析的 gates JSON")

    if score_results:
        info("写回评分到 state.json...")
        for gate_result in score_results:
            if "error" in gate_result:
                continue
            dim = gate_result.get("dimension", "")
            value = gate_result.get("value")
            # T5：kpi_target 在 score 中为汇总布尔，勿覆盖 iterations[].scores 中的数值 KPI
            if dim == "kpi_target" and isinstance(value, bool):
                continue
            if dim and value is not None:
                _, wrc = run_tool(
                    "autoloop-state.py",
                    ["update", work_dir, f"iterations[-1].scores.{dim}", str(value)],
                    capture=True,
                    work_dir=work_dir,
                )
                if wrc != 0:
                    warn(f"写回评分失败: {dim}={value}")
                    if strict:
                        verify_ok = False

    if score_results:
        info("更新门禁状态...")
        state_fresh = load_state(work_dir)
        plan_gates = get_gates(state_fresh)
        for idx, gate_def in enumerate(plan_gates):
            for gate_result in score_results:
                if _plan_gate_matches_score_result(gate_def, gate_result):
                    current_val = gate_result.get("value")
                    passed = gate_result.get("pass", False)
                    gd0 = gate_def.get("dim") or gate_def.get("dimension", "")
                    if gd0 == "kpi_target" and isinstance(current_val, bool):
                        numeric = get_current_scores(state_fresh).get("kpi_target")
                        current_val = numeric
                    if current_val is not None:
                        run_tool(
                            "autoloop-state.py",
                            [
                                "update",
                                work_dir,
                                f"plan.gates[{idx}].current",
                                str(current_val),
                            ],
                            capture=True,
                            work_dir=work_dir,
                        )
                        status_label = "达标" if passed else "未达标"
                        run_tool(
                            "autoloop-state.py",
                            [
                                "update",
                                work_dir,
                                f"plan.gates[{idx}].status",
                                status_label,
                            ],
                            capture=True,
                            work_dir=work_dir,
                        )
                    break

    # T5：score 对 kpi_target 常返回 bool，不写 iterations[].scores；从 plan.gates 数值回填
    # 须读 iterations[-1].scores 原文：get_current_scores 在 T5 空 scores 时会用 gate 回填，避免误判「已有 KPI」而跳过写回
    state_post = load_state(work_dir)
    if get_template(state_post) == "T5":
        iters = state_post.get("iterations") or []
        raw_sc = (iters[-1].get("scores") or {}) if iters else {}
        kt = raw_sc.get("kpi_target")
        if not isinstance(kt, (int, float)):
            for g in get_gates(state_post):
                gd = g.get("dim") or g.get("dimension", "")
                if gd != "kpi_target":
                    continue
                cur = g.get("current")
                if isinstance(cur, (int, float)):
                    merged = dict(raw_sc)
                    merged["kpi_target"] = float(cur)
                    run_tool(
                        "autoloop-state.py",
                        [
                            "update",
                            work_dir,
                            "iterations[-1].scores",
                            json.dumps(merged, ensure_ascii=False),
                        ],
                        capture=True,
                        work_dir=work_dir,
                    )
                break

    val_args = [work_dir]
    if strict:
        val_args.append("--strict")
    info("运行验证器...")
    _, val_rc = run_tool(
        "autoloop-validate.py", val_args, capture=True, work_dir=work_dir
    )
    if strict and val_rc != 0:
        verify_ok = False
        error("STRICT: autoloop-validate 未通过")
        _metadata_set_last_error(work_dir, "autoloop-validate.py", val_rc)

    tsv_path = os.path.join(work_dir, "autoloop-results.tsv")
    if os.path.exists(tsv_path):
        info("运行方差检查...")
        _, var_rc = run_tool(
            "autoloop-variance.py", ["check", tsv_path], capture=True, work_dir=work_dir
        )
        if strict and var_rc != 0:
            verify_ok = False
            error("STRICT: autoloop-variance check 未通过")
            _metadata_set_last_error(work_dir, "autoloop-variance.py", var_rc)
    else:
        info("TSV 文件不存在，跳过方差检查")

    info("渲染输出文件...")
    run_tool("autoloop-render.py", [work_dir], work_dir=work_dir)

    prompt_block("追加 TSV 记录", f"""\
        请基于本轮评分结果，调用:
          autoloop-state.py add-tsv-row {work_dir} '<JSON>'

        JSON 字段: iteration, phase, status, dimension, metric_value, delta,
                   strategy_id, action_summary, side_effect, evidence_ref,
                   unit_id, protocol_version, score_variance, confidence, details

        add-tsv-row 会按 TSV 规则做方差/置信度校验；失败时请修正后重试。
    """)

    return verify_ok


def _manifest_stagnation_max_explore(template_key):
    raw = _MANIFEST.get("stagnation_max_explore") or {}
    n = raw.get(template_key)
    try:
        return int(n) if n is not None and int(n) > 0 else None
    except (TypeError, ValueError):
        return None


def _stagnation_max_explore_apply(work_dir, state, stag, decision, reasons):
    """manifest.stagnation_max_explore：停滞中记录策略切换次数，超限则 pause（T5/T7/T8）。"""
    tpl = get_template(state)
    limit = _manifest_stagnation_max_explore(tpl)
    if not limit:
        return decision, reasons
    stagnating = [x for x in (stag or []) if len(x) > 2 and x[2] == "stagnating"]
    meta_key = "stagnation_explore_switches"

    def _read_count(st):
        return int((st.get("metadata") or {}).get(meta_key) or 0)

    if not stagnating:
        if _read_count(state) != 0:
            def _zero(st):
                st.setdefault("metadata", {})[meta_key] = 0

            _record_state_metadata(work_dir, _zero)
        return decision, reasons

    count = _read_count(state)
    iters = state.get("iterations") or []
    if len(iters) >= 2:
        p = ((iters[-2].get("strategy") or {}).get("strategy_id") or "").strip()
        c = ((iters[-1].get("strategy") or {}).get("strategy_id") or "").strip()
        if c and c != p:
            count += 1

            def _set(st):
                st.setdefault("metadata", {})[meta_key] = count

            _record_state_metadata(work_dir, _set)
    if count >= limit and decision == "continue":
        return "pause", reasons + [
            "已达 manifest stagnation_max_explore={}（停滞中 strategy_id 切换计数={}），"
            "请调整目标/预算或人工确认后继续".format(limit, count)
        ]
    return decision, reasons


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


def phase_evolve(work_dir, state, round_num, strict=False):
    """EVOLVE: 自动检查终止条件"""
    banner(round_num, "EVOLVE", "终止条件评估")

    state = load_state(work_dir)
    if _strict_enabled(strict) and not _strict_evolve_requires_findings(state):
        error(
            "STRICT: EVOLVE 前缺少 findings — SYNTHESIZE 后须 add-finding 或写入 findings.rounds"
        )
        return "pause", [
            "STRICT: 须至少一条结构化 finding（iterations[-1].findings 或 findings.rounds[-1]）"
        ]
    if _strict_enabled(strict) and not _strict_evolve_requires_tsv_current_round(
        state, round_num
    ):
        error(
            "STRICT: EVOLVE 前末行 TSV 的 iteration 须等于当前轮次 {}（请先 VERIFY 追加本轮行）".format(
                round_num
            )
        )
        return "pause", [
            "STRICT: results_tsv[-1].iteration 与当前 round 不一致或 TSV 为空"
        ]

    max_rounds = get_max_rounds(state)
    # 如果 budget.max_rounds=0，get_max_rounds 已 fallback 到 manifest default_rounds；记录警告
    raw_max = state.get("plan", {}).get("budget", {}).get("max_rounds", 0)
    if raw_max == 0:
        warn(
            "budget.max_rounds=0，已 fallback 到 manifest default_rounds[{}]={}（建议运行 "
            "autoloop-state.py update <dir> plan.budget.max_rounds {} 写入正确值）".format(
                get_template(state), max_rounds, max_rounds
            )
        )
    all_passed, gate_details = check_gates_passed(state)
    history = get_score_history(state)
    osc = detect_oscillation(history)
    stag, eligible_stag_dims = detect_stagnation(
        history, get_gates(state), template_key=get_template(state))
    stag_dims = {d for d, _, _ in stag} if stag else set()
    osc_filtered = [x for x in osc if x[0] not in stag_dims]

    decision = "continue"
    reasons = []

    tsv_fc = _latest_tsv_fail_closed(state)
    if tsv_fc and state.get("results_tsv"):
        reasons.append("TSV 方差≥2 或置信度 fail-closed，禁止仅凭门禁判定成功终止")

    cross_reg, cross_dims = detect_cross_dimension_regression(state)
    if cross_reg:
        reasons.append(
            "跨维度回归: 维度 {} 自上轮 hard 满足变为未满足（handoff.impacted_dimensions 建议显式声明；"
            "未填时由分数历史推断）".format(", ".join(cross_dims))
        )
        if decision == "continue":
            decision = "pause"

    # 1. 门禁全通过且非 TSV fail-closed → 根据 completion_authority 决策
    if all_passed and gate_details and not tsv_fc:
        tmpl = get_template(state)
        authority = _MANIFEST.get("completion_authority", {}).get(tmpl, "internal")
        if authority == "internal":
            decision = "stop"
            reasons.append("达标终止（internal authority）")
        elif authority == "human_review":
            decision = "pause"
            reasons.append("门禁达标，进入人工审查确认。请 Kane 审查关键发现后确认完成。")
        elif authority == "external_validation":
            decision = "pause"
            reasons.append("门禁达标，需外部验证（测试/部署）通过后确认完成。")
        else:
            decision = "stop"
            reasons.append("达标终止（未知 authority '{}'，fallback 到 internal）".format(authority))
    elif all_passed and gate_details and tsv_fc:
        reasons.append("门禁数值已通过，但 TSV fail-closed 阻止成功终止")

    # 2. 预算耗尽（T4 + linear_phases 且交付未标记完成时暂停，避免仅靠 OODA 轮次误停）
    if round_num >= max_rounds:
        tmpl = get_template(state)
        plan = state.get("plan", {})
        linear_pause = (
            tmpl == "T4"
            and plan.get("template_mode") == "linear_phases"
            and not plan.get("linear_delivery_complete", False)
            and not all_passed
        )
        if linear_pause:
            reasons.append(
                "已达最大轮次 {}，但 T4+template_mode=linear_phases 且 linear_delivery_complete=false — "
                "暂停（请推进交付阶段后 autoloop-state.py update … plan.linear_delivery_complete true，"
                "或提高 plan.budget.max_rounds）".format(max_rounds)
            )
            if decision == "continue":
                decision = "pause"
        elif decision != "stop":
            decision = "stop"
            reasons.append(f"已达最大轮次 {max_rounds}")

    # 3. 振荡检测（与停滞/回归同维时忽略振荡，优先停滞信号）
    if len(osc_filtered) >= 2:
        reasons.append(f"检测到 {len(osc_filtered)} 个维度振荡")
        if decision == "continue":
            decision = "pause"

    # 4. 停滞/回归检测（per-dimension）
    if stag:
        regressing = [(d, v, s) for d, v, s in stag if s == 'regressing']
        stagnating = [(d, v, s) for d, v, s in stag if s == 'stagnating']
        if regressing:
            reasons.append(f"回归: {', '.join(d for d, _, _ in regressing)} — 需立即调查根因")
            if decision == "continue":
                decision = "pause"  # 回归比停滞更严重，立即暂停
        if stagnating:
            reasons.append(f"停滞: {', '.join(d for d, _, _ in stagnating)}")
            stagnating_dims = {d for d, _, _ in stagnating}
            # loop-protocol：连续多轮「所有可监控维度」均无进展才算无法继续
            # 仅 1 个可监控维度（常见 T5 仅 kpi_target）时，eligible==stagnating 恒成立，不应判「全体停滞」终止
            if (
                decision == "continue"
                and eligible_stag_dims
                and stagnating_dims == eligible_stag_dims
                and len(eligible_stag_dims) > 1
            ):
                decision = "stop"
                reasons.append(
                    "无法继续：所有可监控维度连续停滞且 hard gate 未全部通过（见 loop-protocol 决策树）"
                )
            elif decision == "continue" and len(stagnating_dims) == 1:
                reasons.append("建议: 单维度停滞，DECIDE 阶段应切换该维度策略")

    decision, reasons = _stagnation_max_explore_apply(
        work_dir, state, stag, decision, reasons
    )

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

    # P2-13: EVOLVE 结构化建议输出
    if decision == "continue":
        failed_dims = [d["label"] for d in gate_details if not d["passed"]] if gate_details else []
        focus_dims = ", ".join(failed_dims[:3]) if failed_dims else "N/A"
        remaining_pct = round((1 - round_num / max_rounds) * 100) if max_rounds > 0 else 0
        info("--- EVOLVE 建议 ---")
        info("建议: 继续第 {} 轮，聚焦 {}".format(round_num + 1, focus_dims))
        info("理由: {}".format(", ".join(reasons) if reasons else "标准策略继续"))
        info("风险: 剩余预算 {}%".format(remaining_pct))
        info("替代: 如认为当前质量已足够，可手动暂停")
        info("-------------------")

    # P1-05: 任务终止时输出质量评估摘要（含置信度和误差范围）
    if decision in ("stop", "pause") and gate_details:
        print(f"\n{C_BOLD}评分质量摘要（置信度分层）:{C_RESET}")
        print(f"  {'维度':<20} {'当前':>8} {'目标':>8} {'置信度':>10} {'误差':>6}  {'可信度说明'}")
        print("  " + "─" * 80)
        needs_review = []
        for d in gate_details:
            dim = d.get("dim", d.get("dimension", ""))
            label = d.get("label", dim)
            current = str(d.get("current", "?"))
            target = str(d.get("threshold", "?"))
            confidence, margin = _confidence_for_dim(dim)
            margin_display = "±{:.1f}".format(margin) if margin is not None else "N/A"
            if confidence == "empirical":
                note = "工具输出，高可信"
            elif confidence == "heuristic":
                note = "启发式，建议人工复核"
                needs_review.append(label)
            else:
                note = "二元判定，仅看方向"
                needs_review.append(label)
            print(f"  {label:<20} {current:>8} {target:>8} {confidence:>10} {margin_display:>6}  {note}")
        if needs_review:
            print(f"\n  {C_YELLOW}⚠ 以下维度评分误差较大，建议人工复核: {', '.join(needs_review)}{C_RESET}")

    _append_evolve_progress_md(work_dir, round_num, decision, reasons, gate_details)

    # P2-04: 成本摘要
    print_cost_summary(state)

    return decision, reasons


def print_cost_summary(state):
    """打印成本摘要（轮次消耗 + subagent 调用数）。"""
    iterations = state.get("plan", {}).get("iterations", [])
    round_count = len(iterations)
    max_rounds = state.get("plan", {}).get("budget", {}).get("max_rounds", "?")

    # 统计 subagent 调用总数
    subagent_count = 0
    for it in iterations:
        act = it.get("act")
        if isinstance(act, dict):
            results = act.get("subagent_results", [])
            if isinstance(results, list):
                subagent_count += len(results)

    info("--- 资源消耗 ---")
    info(f"已用轮次: {round_count}/{max_rounds}")
    info(f"Subagent 调用总数: {subagent_count}")
    info("----------------")


def phase_reflect(work_dir, state, round_num):
    """REFLECT: 输出反思提示，更新经验库"""
    banner(round_num, "REFLECT", "反思与经验沉淀")

    state = load_state(work_dir)
    tmpl = get_template(state)
    _maybe_reflect_experience_write(work_dir, state, tmpl)

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

    # T1 探索期（Round 1，尚无历史分数）：只要求反思摘要，不强制策略归因
    t1_early = tmpl == "T1" and round_num <= 1
    if t1_early:
        prompt_block("反思与经验沉淀", f"""\
        本轮变化: {json.dumps(deltas, ensure_ascii=False)}
        当前模板: {tmpl}（探索期 — 策略归因为可选）

        反思要求:
        1. 本轮收集了哪些关键发现？覆盖了哪些维度？
        2. 哪些信息来源质量高？哪些需要交叉验证？
        3. 有哪些信息缺口需要下一轮补充？
        4. 下一轮的搜索方向和优先级是什么？

        经验沉淀（可选 — 如果本轮有明确可复用的策略，可填写）:
        - 写入 iterations[-1].reflect（JSON）:
          autoloop-state.py update {work_dir} iterations[-1].reflect '{{"strategy_id":"S{round_num:02d}-xxx","effect":"保持|避免|待验证","delta":0.5,"dimension":"coverage","context":"..."}}'
        - T1 探索期不强制填写 strategy_id/effect/delta，只写反思摘要即可

        调用:
          autoloop-state.py update {work_dir} findings.lessons_learned.verified_hypotheses '[...]'
    """)
    else:
        prompt_block("反思与经验沉淀", f"""\
        本轮变化: {json.dumps(deltas, ensure_ascii=False)}
        当前模板: {tmpl}

        反思要求:
        1. 本轮策略是否达到预期？差异原因是什么？
        2. 发现了哪些可泛化的方法？
        3. 有哪些假设被验证或推翻？
        4. 下一轮应该改变什么？

        经验沉淀（如有可泛化策略）:
        - 【推荐】写入 iterations[-1].reflect（JSON），下轮进入 REFLECT 时控制器将**自动**调用 experience write（--score 仅收 **delta**，Likert 用 rating_1_to_5）:
          autoloop-state.py update {work_dir} iterations[-1].reflect '{{"strategy_id":"S{round_num:02d}-xxx","effect":"保持|避免|待验证","delta":0.5,"rating_1_to_5":4,"dimension":"coverage","context":"..."}}'
        - 或手动: autoloop-experience.py {work_dir} write --strategy-id ... --effect ... --score ...
        - 评分语义 → references/quality-gates.md；阈值 SSOT → references/gate-manifest.json
        - 参数校准 → references/parameters.md

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
    _, rc = run_tool("autoloop-state.py", args, work_dir=work_dir)
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

    le = state.get("metadata", {}).get("last_error")
    if isinstance(le, dict) and le.get("script"):
        print(f"\n  最近工具错误: {le.get('script')} rc={le.get('returncode')} @ {le.get('time', '')}")

    print()


def run_loop(
    work_dir,
    start_phase=None,
    start_round=None,
    strict=False,
    enforce_strategy_history=False,
    stop_after_phase=None,
):
    """主循环执行。strict=True 时 VERIFY 任一硬步骤失败则中止任务。
    enforce_strategy_history: DECIDE 前对 strategy_history「避免」与 handoff 做强校验（亦可设 AUTOLOOP_ENFORCE_STRATEGY_HISTORY=1）。
    stop_after_phase: 完成该阶段（含 checkpoint.last_completed_phase）后退出；供 L1 Runner 按段调用。
    返回值: None 预算耗尽 | "pause" | "stop" | "abort" | "stop_after"
    """
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
        # 仅在新一轮从 OBSERVE 开始时创建 iteration；--stop-after 切片续跑同一轮时跳过，
        # 避免重复 add-iteration 清空 scores、导致 ORIENT/VERIFY 读不到 kpi_target。
        if phase_start_idx == 0:
            info(f"自动创建 Round {round_num} 迭代记录...")
            _, rc = run_tool(
                "autoloop-state.py", ["add-iteration", work_dir], capture=True, work_dir=work_dir
            )
            if rc != 0:
                warn(f"add-iteration 返回非零退出码 (rc={rc})，可能已存在")
        else:
            info(
                "续跑 Round {}：跳过 add-iteration（从 {} 继续）".format(
                    round_num, PHASES[phase_start_idx]
                )
            )

        # 更新 current_round
        run_tool(
            "autoloop-state.py",
            ["update", work_dir, "plan.budget.current_round", str(round_num)],
            capture=True,
            work_dir=work_dir,
        )

        abort_task = False
        for phase_idx in range(phase_start_idx, len(PHASES)):
            phase = PHASES[phase_idx]

            # 更新 checkpoint: 当前阶段
            checkpoint["current_round"] = round_num
            checkpoint["current_phase"] = phase
            save_checkpoint(work_dir, checkpoint)

            # 重新加载 state（其他工具可能已修改）
            state = load_state(work_dir)

            # strict validate：checkpoint.current_phase 须与 iterations[-1].phase 一致（单步推进）
            it_list = state.get("iterations") or []
            if it_list:
                cur_ph = (it_list[-1].get("phase") or "OBSERVE").strip()
                if cur_ph != phase:
                    run_tool(
                        "autoloop-state.py",
                        ["update", work_dir, "iterations[-1].phase", phase],
                        capture=True,
                        work_dir=work_dir,
                    )
                    state = load_state(work_dir)

            # 执行阶段
            evolve_decision = None
            evolve_reasons = []

            if phase == "OBSERVE":
                obs_decision, obs_reasons = phase_observe(work_dir, state, round_num)
                if obs_decision == "pause":
                    print(f"\n{C_BOLD}{C_YELLOW}{'=' * 60}")
                    print(f"  AutoLoop 循环暂停 — Round {round_num}（OBSERVE）")
                    print(f"  原因: {'; '.join(obs_reasons)}")
                    print(f"  恢复: autoloop-controller.py {work_dir} --resume")
                    print(f"{'=' * 60}{C_RESET}\n")
                    checkpoint["pause_state"] = {
                        "reason": "; ".join(obs_reasons),
                        "required_confirmation": "补全 T5 KPI 后继续",
                        "paused_at": now_iso(),
                    }
                    save_checkpoint(work_dir, checkpoint)
                    return "pause"
            elif phase == "ORIENT":
                phase_orient(work_dir, state, round_num)
            elif phase == "DECIDE":
                phase_decide(
                    work_dir,
                    state,
                    round_num,
                    strict_cli=strict,
                    enforce_strategy_history=enforce_strategy_history,
                )
            elif phase == "ACT":
                if not phase_act(work_dir, state, round_num, strict=strict):
                    abort_task = True
                else:
                    # ACT→VERIFY 过渡: 解析 subagent completion_ratio
                    state = load_state(work_dir)
                    process_act_completion(work_dir, state)
            elif phase == "VERIFY":
                vok = phase_verify(work_dir, state, round_num, strict=strict)
                if strict and not vok:
                    error("AUTOLOOP_STRICT: VERIFY 未通过，中止任务（不进入 SYNTHESIZE）")
                    abort_task = True
            elif phase == "SYNTHESIZE":
                phase_synthesize(work_dir, state, round_num)
            elif phase == "EVOLVE":
                evolve_decision, evolve_reasons = phase_evolve(
                    work_dir, state, round_num, strict=strict
                )
            elif phase == "REFLECT":
                phase_reflect(work_dir, state, round_num)
                # FIX 4: REFLECT 完成后自动渲染可读文件
                info("REFLECT 后自动渲染...")
                run_tool("autoloop-render.py", [work_dir], work_dir=work_dir)

            _metadata_append_audit(work_dir, "phase_complete", "{} round={}".format(phase, round_num))

            # 更新 checkpoint: 阶段完成
            checkpoint["last_completed_phase"] = phase
            save_checkpoint(work_dir, checkpoint)

            if abort_task:
                break

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
                    return "stop"

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
                    return "pause"

            if (
                stop_after_phase
                and phase.upper() == stop_after_phase.strip().upper()
            ):
                info(
                    "--stop-after {}: 阶段 {} 已完成并写入 checkpoint，退出".format(
                        stop_after_phase, phase
                    )
                )
                return "stop_after"

        if abort_task:
            return "abort"

        # 本轮完成，重置 phase_start_idx 为 0（下一轮从 OBSERVE 开始）
        phase_start_idx = 0
        round_num += 1

    # 预算耗尽
    print(f"\n{C_BOLD}{C_RED}{'=' * 60}")
    print(f"  AutoLoop 预算耗尽 — {round_num - 1} 轮已完成")
    print(f"  输出当前最优结果")
    print(f"{'=' * 60}{C_RESET}\n")
    return None


# ---------------------------------------------------------------------------
# Pipeline Worktree 管理（P3-01 并行隔离）
# ---------------------------------------------------------------------------


def create_pipeline_worktree(work_dir, template, timestamp=None):
    """为并行 pipeline 创建 Git Worktree。

    返回 (worktree_path, branch_name)。
    """
    import subprocess
    import time

    ts = timestamp or int(time.time())
    branch = f"autoloop-{template}-{ts}"
    wt_path = os.path.join(work_dir, ".worktrees", branch)
    os.makedirs(os.path.dirname(wt_path), exist_ok=True)
    subprocess.run(
        ["git", "worktree", "add", wt_path, "-b", branch],
        cwd=work_dir,
        check=True,
        capture_output=True,
    )
    info(f"Worktree 已创建: {wt_path} (branch: {branch})")
    return wt_path, branch


def remove_pipeline_worktree(work_dir, wt_path, branch):
    """清理 Git Worktree 及其临时分支。"""
    import subprocess

    result = subprocess.run(
        ["git", "worktree", "remove", wt_path],
        cwd=work_dir,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        warn(f"Worktree 清理失败 ({wt_path}): {result.stderr.strip()}")
    subprocess.run(
        ["git", "branch", "-d", branch],
        cwd=work_dir,
        capture_output=True,
    )
    info(f"Worktree 已清理: {branch}")


def merge_pipeline_worktree(work_dir, branch):
    """合并并行 pipeline 的 worktree 分支。

    返回 True 表示合并成功，False 表示有冲突需手动解决。
    """
    import subprocess

    result = subprocess.run(
        ["git", "merge", "--no-ff", branch, "-m",
         f"AutoLoop pipeline merge: {branch}"],
        cwd=work_dir,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        warn(f"Worktree 合并冲突: {branch}. 需要手动解决。")
        warn(f"  stderr: {result.stderr.strip()}")
        return False
    info(f"Worktree 分支已合并: {branch}")
    return True


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

    cli_strict = False
    cli_enforce_strategy_history = False
    stop_after_phase = None
    cli_exit_codes = False
    i = 0
    while i < len(args):
        arg = args[i]
        if arg == "--init":
            mode = "init"
        elif arg == "--resume":
            mode = "resume"
        elif arg == "--status":
            mode = "status"
        elif arg == "--strict":
            cli_strict = True
        elif arg == "--enforce-strategy-history":
            cli_enforce_strategy_history = True
        elif arg == "--exit-codes":
            cli_exit_codes = True
        elif arg == "--stop-after" and i + 1 < len(args):
            stop_after_phase = args[i + 1]
            i += 1
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

    def _apply_exit(outcome):
        use_codes = cli_exit_codes or os.environ.get(
            "AUTOLOOP_EXIT_CODES", ""
        ).strip().lower() in ("1", "true", "yes")
        if not use_codes:
            return
        if outcome == "pause":
            sys.exit(10)
        if outcome == "abort":
            sys.exit(1)
        sys.exit(0)

    if stop_after_phase:
        s = stop_after_phase.strip().upper()
        if s not in PHASES:
            error("--stop-after 必须是以下之一: {}".format(", ".join(PHASES)))
            sys.exit(1)
        stop_after_phase = s

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
        outcome = run_loop(
            work_dir,
            strict=_strict_enabled(cli_strict),
            enforce_strategy_history=cli_enforce_strategy_history,
            stop_after_phase=stop_after_phase,
        )
        _apply_exit(outcome)

    elif mode == "run":
        if not os.path.exists(os.path.join(work_dir, STATE_FILE)):
            error(f"状态文件不存在: {os.path.join(work_dir, STATE_FILE)}")
            error("请先运行 --init 初始化任务")
            sys.exit(1)
        outcome = run_loop(
            work_dir,
            strict=_strict_enabled(cli_strict),
            enforce_strategy_history=cli_enforce_strategy_history,
            stop_after_phase=stop_after_phase,
        )
        _apply_exit(outcome)

    else:
        error(f"未知模式: {mode}")
        sys.exit(1)


if __name__ == "__main__":
    main()
