#!/usr/bin/env python3
"""AutoLoop 多模板评分器 — 支持 SSOT JSON + markdown 双模式

用法:
  autoloop-score.py <工作目录>              从 SSOT JSON 评分（优先）或 markdown 回退
  autoloop-score.py <文件路径>              兼容旧模式，直接评分 findings.md
  autoloop-score.py <工作目录> --json       JSON 输出
"""

import json
import os
import re
import sys
import urllib.parse

_score_dir = os.path.dirname(os.path.abspath(__file__))
if _score_dir not in sys.path:
    sys.path.insert(0, _score_dir)

from autoloop_kpi import (
    kpi_row_satisfied,
    plan_gate_is_exempt,
    results_tsv_last_row_fail_closed,
)

# ---------------------------------------------------------------------------
# 门禁定义 — 从 gate-manifest.json（SSOT）加载
# ---------------------------------------------------------------------------

# manifest dimension → scorer internal dim 映射（处理命名差异）
_MANIFEST_DIM_MAP = {
    "security": "security_score",
    "reliability": "reliability_score",
    "maintainability": "maintainability_score",
    "p1_count": "p1_all",
    "syntax_errors": "syntax",
}

# manifest dimension → 中文标签
_MANIFEST_LABEL_MAP = {
    "coverage": "覆盖率",
    "credibility": "可信度",
    "consistency": "一致性",
    "completeness": "完整性",
    "bias_check": "偏见检查",
    "sensitivity": "敏感性分析",
    "kpi_target": "KPI达标",
    "pass_rate": "通过率",
    "avg_score": "平均分",
    "syntax_errors": "语法验证",
    "p1_p2_issues": "P1/P2问题",
    "service_health": "服务健康",
    "user_acceptance": "人工验收",
    "security": "安全性",
    "reliability": "可靠性",
    "maintainability": "可维护性",
    "p1_count": "P1问题(全维度)",
    "security_p2": "安全P2问题",
    "reliability_p2": "可靠性P2问题",
    "maintainability_p2": "可维护性P2问题",
    "architecture": "架构",
    "performance": "性能",
    "stability": "稳定性",
    # T3 产品设计类
    "design_completeness": "设计完整度",
    "feasibility_score": "技术可行性",
    "requirement_coverage": "需求覆盖度",
    "scope_precision": "范围精确度",
    "validation_evidence": "验证证据",
}

# manifest unit → scorer unit 映射
_MANIFEST_UNIT_MAP = {
    "%": "%",
    "/10": "/10",
    "bool": "bool",
    "count": "count",
    "user_defined": "user_defined",
}


def _load_gate_manifest():
    """Load gate definitions from canonical manifest (SSOT)."""
    manifest_path = os.path.join(os.path.dirname(__file__), "..", "references", "gate-manifest.json")
    with open(manifest_path, "r", encoding="utf-8") as f:
        return json.load(f)


def _manifest_to_scorer_gates(manifest):
    """Convert manifest templates to scorer's internal TEMPLATE_GATES format."""
    result = {}
    for tkey, tdef in manifest["templates"].items():
        gates = []
        for g in tdef["gates"]:
            dim_raw = g["dimension"]
            dim = _MANIFEST_DIM_MAP.get(dim_raw, dim_raw)
            unit = _MANIFEST_UNIT_MAP.get(g["unit"], g["unit"])
            gate_type = g["type"]  # hard/soft
            threshold = g["threshold"]
            label = _MANIFEST_LABEL_MAP.get(dim_raw, dim_raw)
            entry = {
                "dim": dim,
                "manifest_dimension": dim_raw,
                "threshold": threshold,
                "unit": unit,
                "gate": gate_type,
                "label": label,
                "comparator": g.get("comparator", ">="),
            }
            if "llm_grader" in g:
                entry["llm_grader"] = g["llm_grader"]
            gates.append(entry)
        result[tkey] = gates
    return result


_MANIFEST = _load_gate_manifest()
TEMPLATE_GATES = _manifest_to_scorer_gates(_MANIFEST)

# 模板别名映射（用户可能写 "T1 Research" 而非 "T1"）
_TEMPLATE_ALIAS = {}
for _k in TEMPLATE_GATES:
    _TEMPLATE_ALIAS[_k] = _k
    _TEMPLATE_ALIAS[_k.lower()] = _k
_TEMPLATE_ALIAS.update({
    "t1 research": "T1", "t1-research": "T1", "research": "T1",
    "t2 compare": "T2", "t2-compare": "T2", "compare": "T2",
    "t3 design": "T3", "t3-design": "T3", "t3 product design": "T3", "t3-product-design": "T3",
    "t4 deliver": "T4", "t4-deliver": "T4", "deliver": "T4",
    "t5 iterate": "T5", "t5-iterate": "T5", "iterate": "T5",
    "t6 generate": "T6", "t6-generate": "T6", "generate": "T6",
    "t7 quality": "T7", "t7-quality": "T7", "quality": "T7",
    "t8 optimize": "T8", "t8-optimize": "T8", "optimize": "T8",
})


def resolve_template(raw):
    """将模板字符串标准化为 T1-T8 键"""
    if not raw:
        return None
    key = raw.strip().lower()
    return _TEMPLATE_ALIAS.get(key)


def plan_gates_for_ssot_init(template_raw):
    """从 manifest 生成 plan.gates，dim 与 scorer JSON dimension / iterations.scores 键一致。

    每条含 manifest_dimension 供 controller 反查 manifest comparator。
    """
    tkey = resolve_template(template_raw)
    if not tkey:
        tr = (template_raw or "").strip()
        if tr in TEMPLATE_GATES:
            tkey = tr
    tmpl = _MANIFEST.get("templates", {})
    if not tkey or tkey not in tmpl:
        return []
    out = []
    for g in tmpl[tkey]["gates"]:
        dim_raw = g["dimension"]
        dim = _MANIFEST_DIM_MAP.get(dim_raw, dim_raw)
        unit = _MANIFEST_UNIT_MAP.get(g["unit"], g["unit"])
        row = {
            "dim": dim,
            "dimension": dim,
            "manifest_dimension": dim_raw,
            "label": _MANIFEST_LABEL_MAP.get(dim_raw, dim_raw),
            "threshold": g["threshold"],
            "unit": unit,
            "gate": g["type"],
            "comparator": g.get("comparator", ">="),
            "current": None,
            "status": "未达标",
        }
        if g["threshold"] is None:
            row["target"] = None
        out.append(row)
    return out


# =====================================================================
# 模式检测
# =====================================================================

def detect_mode(path):
    """判断输入路径的评分模式。

    返回 ("ssot", state_dict, work_dir)
         ("markdown", content_str, findings_path)
         ("error", message, None)
    """
    if os.path.isdir(path):
        state_path = os.path.join(path, "autoloop-state.json")
        if os.path.exists(state_path):
            with open(state_path, "r", encoding="utf-8") as f:
                state = json.load(f)
            return "ssot", state, path
        # 目录但无 state.json — 尝试找 findings.md 作为回退
        findings_path = os.path.join(path, "autoloop-findings.md")
        if os.path.exists(findings_path):
            with open(findings_path, "r", encoding="utf-8") as f:
                content = f.read()
            return "markdown", content, findings_path
        return "error", "目录中未找到 autoloop-state.json 或 autoloop-findings.md: {}".format(path), None

    if os.path.isfile(path):
        if path.endswith(".json"):
            with open(path, "r", encoding="utf-8") as f:
                state = json.load(f)
            return "ssot", state, os.path.dirname(path)
        abspath = os.path.abspath(path)
        dir_ = os.path.dirname(abspath) or "."
        state_sidecar = os.path.join(dir_, "autoloop-state.json")
        if os.path.isfile(state_sidecar):
            with open(state_sidecar, "r", encoding="utf-8") as f:
                state = json.load(f)
            return "ssot", state, dir_
        # 无同目录 SSOT 时视为纯 markdown findings
        with open(abspath, "r", encoding="utf-8") as f:
            content = f.read()
        return "markdown", content, path

    return "error", "路径不存在: {}".format(path), None


# =====================================================================
# SSOT 评分引擎（主路径）
# =====================================================================

def _get_latest_scores(state):
    """从 iterations[-1].scores 获取最新评分字典"""
    iterations = state.get("iterations", [])
    if not iterations:
        return {}
    return iterations[-1].get("scores", {})


def _finding_body_text(finding):
    """findings 条目 canonical 正文：summary → content → description（与 loop-data-schema / validate 一致）。"""
    if not isinstance(finding, dict):
        return ""
    for k in ("summary", "content", "description"):
        v = finding.get(k)
        if v not in (None, ""):
            return str(v).strip()
    return ""


def _finding_substantive_info_count(finding):
    """每条 finding 的实质信息量（用于 coverage / completeness 严格口径）。"""
    body = _finding_body_text(finding) or ""
    lines = body.split("\n")
    bullets = sum(
        1 for line in lines
        if line.strip().startswith("- ") and len(line.strip()) > 10
    )
    if bullets >= 2:
        return bullets
    paras = sum(
        1 for line in lines
        if line.strip() and len(line.strip()) > 10
        and not line.strip().startswith("#")
        and not line.strip().startswith("|")
    )
    return max(bullets, paras)


def _find_plan_gate_row(plan_gates, dim, manifest_dimension=None):
    """在 plan.gates 中查找与模板维度对应的行（dim 或 manifest_dimension）。"""
    if not plan_gates:
        return None
    md = manifest_dimension or dim
    for pg in plan_gates:
        pd = pg.get("dim") or pg.get("dimension", "")
        if pd == dim:
            return pg
        if manifest_dimension and pg.get("manifest_dimension") == md:
            return pg
    return None


def _get_plan_gates(state):
    """从 plan.gates 获取用户定义的门禁目标"""
    return state.get("plan", {}).get("gates", [])


def _count_issues_by_severity(state, category=None):
    """统计 findings.engineering_issues 中的问题数量。

    category: "security" / "reliability" / "maintainability" / "architecture"
              / "performance" / "stability" / None(全部)
    返回 {"P1": n, "P2": n, "P3": n}
    """
    eng = state.get("findings", {}).get("engineering_issues", {})
    counts = {"P1": 0, "P2": 0, "P3": 0}

    categories = [category] if category else list(eng.keys())
    for cat in categories:
        issues = eng.get(cat, [])
        for issue in issues:
            sev = issue.get("severity", "P3") if isinstance(issue, dict) else "P3"
            if sev in counts:
                counts[sev] += 1
    return counts


def _count_findings_coverage(state):
    """从 findings.rounds 计算维度覆盖：每维至少 2 条实质信息点才算覆盖。"""
    plan_dims = state.get("plan", {}).get("dimensions", [])
    rounds = state.get("findings", {}).get("rounds", [])
    dim_best = {}
    for rnd in rounds:
        for finding in rnd.get("findings", []):
            dim = finding.get("dimension", "")
            if not dim:
                continue
            n = _finding_substantive_info_count(finding)
            dim_best[dim] = max(dim_best.get(dim, 0), n)
    # Detect: if plan.dimensions are gate dimension names (not research scope),
    # fall back to counting all unique finding dimensions
    template_raw = state.get("plan", {}).get("template", "")
    tkey = resolve_template(template_raw)
    if tkey and tkey in TEMPLATE_GATES and plan_dims:
        gate_dim_names = set()
        for g in TEMPLATE_GATES[tkey]:
            gate_dim_names.add(g["dim"])
            md = g.get("manifest_dimension")
            if md:
                gate_dim_names.add(md)
        # If plan.dimensions are all gate dimension names → not research scope → use fallback
        if set(plan_dims) <= gate_dim_names:
            plan_dims = []

    if plan_dims:
        total = len(plan_dims)
        covered = sum(1 for d in plan_dims if dim_best.get(d, 0) >= 2)
    else:
        if not dim_best:
            return 0, 0
        total = len(dim_best)
        covered = sum(1 for _, n in dim_best.items() if n >= 2)
    return covered, total


def _count_findings_credibility(state):
    """计算有多源支撑的发现比例（多 URL、多域名或分号/逗号分隔多来源）。"""
    rounds = state.get("findings", {}).get("rounds", [])
    total = 0
    multi_source = 0
    for rnd in rounds:
        for finding in rnd.get("findings", []):
            total += 1
            source = finding.get("source", "") or ""
            blob = source + " " + _finding_body_text(finding)
            if not blob.strip():
                continue
            urls = re.findall(r"https?://[^\s)\]>]+", blob)
            domains = set()
            for u in urls:
                try:
                    domains.add(urllib.parse.urlparse(u).netloc.lower())
                except Exception:
                    pass
            if (
                len(urls) >= 2
                or len(domains) >= 2
                or ";" in source
                or "," in source
            ):
                multi_source += 1
    return multi_source, total


def _count_findings_consistency(state):
    """计算无矛盾维度比例"""
    rounds = state.get("findings", {}).get("rounds", [])
    all_dims = set()
    for rnd in rounds:
        for finding in rnd.get("findings", []):
            dim = finding.get("dimension", "")
            if dim:
                all_dims.add(dim)

    contradictions = state.get("findings", {}).get("disputes", [])
    contradiction_dims = set()
    for c in contradictions:
        dim = c.get("dimension", "") if isinstance(c, dict) else ""
        if dim:
            contradiction_dims.add(dim)

    total = len(all_dims)
    consistent = total - len(contradiction_dims & all_dims)
    return consistent, total


def _count_findings_completeness(state):
    """有来源引用且至少 1 个实质信息点的发现比例。"""
    rounds = state.get("findings", {}).get("rounds", [])
    total = 0
    sourced = 0
    for rnd in rounds:
        for finding in rnd.get("findings", []):
            total += 1
            source = (finding.get("source") or "").strip()
            body = _finding_body_text(finding)
            has_ref = bool(
                source or (body and re.search(r"https?://|来源|Source|arXiv", body, re.I))
            )
            if has_ref and _finding_substantive_info_count(finding) >= 1:
                sourced += 1
    return sourced, total


def _confidence_for_dim(dim):
    """根据评分维度的数据来源，返回 (confidence, margin)。

    三级置信度：
    - empirical (margin ≤ 0.3): 基于工具实际输出（syntax_check_cmd、测试通过率、lint 错误数等）
    - heuristic (margin ≤ 1.5): 基于内容分析模式匹配（来源计数、关键词覆盖率、文本模式匹配）
    - binary (margin = None): 只能判通过/不通过（无量化工具支持时的回退）
    """
    # empirical: T4/T7/T8 中基于工具输出的维度
    _EMPIRICAL_DIMS = {
        "syntax",              # T4: syntax_check_cmd 实际输出
        "p1_p2_issues",        # T4: 工程问题清单计数
        "service_health",      # T4: 健康检查 URL 实际响应
        "p1_all",              # T7: 全维度 P1 计数
        "security_p2",         # T7: 安全 P2 计数
        "reliability_p2",      # T7: 可靠性 P2 计数
        "maintainability_p2",  # T7: 可维护性 P2 计数
    }
    # heuristic: T1/T2/T3/T5/T6 中基于内容分析的维度，以及 T7/T8 的评审打分
    _HEURISTIC_DIMS = {
        "coverage",            # T1/T2: 来源计数 / 维度覆盖率
        "credibility",         # T1/T2: 多源支撑比例
        "consistency",         # T1/T2: 无矛盾维度比例
        "completeness",        # T1/T2: 来源引用比例
        "sensitivity",         # T2: 敏感性分析
        "kpi_target",          # T5: KPI 达标（混合判定）
        "pass_rate",           # T6: 通过率
        "avg_score",           # T6: 平均分
        "security_score",      # T7: 安全性评审打分
        "reliability_score",   # T7: 可靠性评审打分
        "maintainability_score",  # T7: 可维护性评审打分
        "architecture",        # T8: 架构评审打分
        "performance",         # T8: 性能评审打分
        "stability",           # T8: 稳定性评审打分
        "design_completeness",      # T3: 设计完整度
        "feasibility_score",        # T3: 技术可行性
        "requirement_coverage",     # T3: 需求覆盖度
        "scope_precision",          # T3: 范围精确度
        "validation_evidence",      # T3: 验证证据
    }
    # binary: 只能判 pass/fail
    _BINARY_DIMS = {
        "bias_check",          # T2: 偏见检查（bool 门禁）
        "user_acceptance",     # T4: 人工验收（bool 门禁）
    }

    if dim in _EMPIRICAL_DIMS:
        return "empirical", 0.3
    if dim in _HEURISTIC_DIMS:
        return "heuristic", 1.5
    if dim in _BINARY_DIMS:
        return "binary", None
    # 未知维度默认为 heuristic
    return "heuristic", 1.5


def _eval_gate(gate_def, value, evidence=""):
    """评估单个门禁，返回结果 dict。

    value: 实际值（百分比 / 分数 / 计数 / bool）
    """
    dim = gate_def["dim"]
    manifest_dimension = gate_def.get("manifest_dimension", dim)
    threshold = gate_def["threshold"]
    unit = gate_def["unit"]
    gate_type = gate_def["gate"]
    label = gate_def["label"]
    confidence, margin = _confidence_for_dim(dim)

    # threshold 为 None 表示用户自定义（T5 KPI）
    # T5 KPI 的数值比较在 score_from_ssot() 中完成（plan_gates 循环），
    # value 到达此处时已是 bool（kpi_pass）。
    # controller.py check_gates_passed 中有平行的数值比较路径（plan.gates[].target）。
    if threshold is None:
        passed = value is not None and bool(value)
        return {
            "dimension": dim,
            "manifest_dimension": manifest_dimension,
            "label": label,
            "value": value,
            "threshold": "用户定义",
            "unit": unit,
            "gate_type": gate_type,
            "pass": passed,
            "evidence": evidence,
            "confidence": confidence,
            "margin": margin,
        }

    # 使用 manifest comparator 字段进行比较（SSOT），unit 作为回退
    comparator = gate_def.get("comparator", ">=")
    if unit == "bool":
        # bool + ==：与 threshold 严格相等（避免 float 偏见分被 bool() 误判为 True）
        if comparator == "==":
            passed = value == threshold
        else:
            passed = bool(value)
    elif comparator == ">=":
        passed = value >= threshold
    elif comparator == "<=":
        passed = value <= threshold
    elif comparator == "==":
        passed = value == threshold
    elif comparator == "<":
        passed = value < threshold
    elif comparator == ">":
        passed = value > threshold
    else:
        passed = value >= threshold

    # 格式化 threshold 显示
    if unit == "%":
        thr_display = "{}%".format(threshold)
        val_display = "{:.1f}%".format(value)
    elif unit == "/10":
        thr_display = "{}/10".format(threshold)
        val_display = "{:.1f}/10".format(value)
    elif unit == "score":
        comparator_display = gate_def.get("comparator", ">=")
        thr_display = "{} {}".format(comparator_display, threshold)
        val_display = "{:.1f}".format(float(value) if isinstance(value, (int, float)) else 0.0)
    elif unit in ("errors", "count"):
        thr_display = "{} {}".format(comparator, threshold)
        val_display = str(int(value))
    elif unit == "bool":
        thr_display = "True"
        val_display = str(bool(value))
    else:
        thr_display = str(threshold)
        val_display = str(value)

    return {
        "dimension": dim,
        "manifest_dimension": manifest_dimension,
        "label": label,
        "value": value,
        "value_display": val_display,
        "threshold": threshold,
        "threshold_display": thr_display,
        "unit": unit,
        "gate_type": gate_type,
        "pass": passed,
        "evidence": evidence,
        "confidence": confidence,
        "margin": margin,
    }


LLM_GRADER_WEIGHT = 0.7
HEURISTIC_WEIGHT = 1.0 - LLM_GRADER_WEIGHT  # 0.3


def _prepare_llm_grader(gate_def, result, state, work_dir):
    """为 heuristic 维度准备 LLM Grader 评估请求。

    当 gate 有 llm_grader.enabled=true 且当前评分 confidence 为 heuristic 时：
    1. 读取 grader prompt 文件
    2. 构建评估上下文（从 findings 提取当前维度的相关内容）
    3. 将 grader prompt + 评估上下文写入 state.json 的 metadata.pending_llm_grader
    4. 打印提示让 controller 在 VERIFY 阶段委派 subagent 执行评分

    返回 pending entry dict（供写入 state），如果不触发则返回 None。
    """
    grader_cfg = gate_def.get("llm_grader")
    if not grader_cfg or not grader_cfg.get("enabled", False):
        return None

    trigger = grader_cfg.get("trigger", "when_confidence_is_heuristic")
    confidence = result.get("confidence", "")

    # 仅在 confidence 匹配 trigger 时触发
    if trigger == "when_confidence_is_heuristic" and confidence != "heuristic":
        return None

    dim = result.get("dimension", gate_def.get("dim", "unknown"))
    prompt_file = grader_cfg.get("prompt_file", "")

    # 读取 grader prompt 文件
    prompt_content = ""
    if prompt_file:
        assets_dir = os.path.join(os.path.dirname(__file__), "..", "assets")
        prompt_path = os.path.join(assets_dir, prompt_file)
        if os.path.exists(prompt_path):
            with open(prompt_path, "r", encoding="utf-8") as f:
                prompt_content = f.read()

    # 提取当前维度的 findings 作为评估上下文
    context_lines = []
    rounds = state.get("findings", {}).get("rounds", [])
    for rnd in rounds:
        for finding in rnd.get("findings", []):
            dim_tag = finding.get("dimension", "")
            body = finding.get("body", finding.get("content", ""))
            if isinstance(body, list):
                body = "\n".join(str(b) for b in body)
            if dim in dim_tag or gate_def.get("manifest_dimension", "") in dim_tag:
                context_lines.append(str(body)[:500])
    # 如果没有精确匹配，取最近一轮的全部 findings 作为上下文
    if not context_lines and rounds:
        last_round = rounds[-1]
        for finding in last_round.get("findings", []):
            body = finding.get("body", finding.get("content", ""))
            if isinstance(body, list):
                body = "\n".join(str(b) for b in body)
            context_lines.append(str(body)[:500])

    context_text = "\n---\n".join(context_lines[:10])  # 最多10段，避免过长

    print("[LLM Grader] Evaluating dimension '{}' with grader: {}".format(dim, prompt_file))
    print("[LLM Grader] → Controller should delegate a subagent in VERIFY phase.")
    print("[LLM Grader] → Fusion formula: final = heuristic * {:.1f} + llm * {:.1f}".format(
        HEURISTIC_WEIGHT, LLM_GRADER_WEIGHT))

    return {
        "dimension": dim,
        "prompt_file": prompt_file,
        "prompt_content": prompt_content,
        "context": context_text,
        "heuristic_score": result.get("value"),
        "fusion_weights": {"heuristic": HEURISTIC_WEIGHT, "llm": LLM_GRADER_WEIGHT},
    }


def score_from_ssot(state):
    """从 SSOT JSON 评分，返回 (template, results_list)。

    results_list: [{dimension, label, value, threshold, gate_type, pass, evidence, confidence, margin}, ...]
    """
    template_raw = state.get("plan", {}).get("template", "")
    template = resolve_template(template_raw)

    if not template:
        return None, [{"error": "无法识别模板类型: '{}'".format(template_raw)}]

    gates = TEMPLATE_GATES[template]
    scores = _get_latest_scores(state)
    plan_gates = _get_plan_gates(state)
    results = []

    for gate_def in gates:
        dim = gate_def["dim"]
        pg = _find_plan_gate_row(plan_gates, dim, gate_def.get("manifest_dimension"))
        if pg and plan_gate_is_exempt(pg):
            conf, marg = _confidence_for_dim(dim)
            results.append(
                {
                    "dimension": dim,
                    "manifest_dimension": gate_def.get("manifest_dimension", dim),
                    "label": gate_def["label"],
                    "value": None,
                    "threshold": gate_def["threshold"],
                    "unit": gate_def["unit"],
                    "gate_type": gate_def["gate"],
                    "pass": True,
                    "evidence": "plan.gates.status=豁免（rollup 视同通过）",
                    "confidence": conf,
                    "margin": marg,
                }
            )
            continue

        value = None
        evidence = ""

        # --- T1/T2 知识类: 从 findings 计算 ---
        if dim == "coverage":
            covered, total = _count_findings_coverage(state)
            value = (covered / total * 100) if total > 0 else 0.0
            evidence = "{}/{}维度有实质内容".format(covered, total)

        elif dim == "credibility":
            multi, total = _count_findings_credibility(state)
            value = (multi / total * 100) if total > 0 else 0.0
            evidence = "{}/{}发现有多源支撑".format(multi, total)

        elif dim == "consistency":
            consistent, total = _count_findings_consistency(state)
            value = (consistent / total * 100) if total > 0 else 0.0
            evidence = "{}/{}维度无矛盾".format(consistent, total)

        elif dim == "completeness":
            sourced, total = _count_findings_completeness(state)
            value = (sourced / total * 100) if total > 0 else 0.0
            evidence = "{}/{}发现有来源引用".format(sourced, total)

        # --- T2 专属 ---
        elif dim == "bias_check":
            # bool + ==1：数值须先归一为「偏见<0.15」布尔（quality-gates.md）
            raw = scores.get("bias_check", scores.get("bias_score", 0.0))
            if isinstance(raw, bool):
                value = raw
                evidence = "偏见检查={}".format("通过" if raw else "未通过")
            elif isinstance(raw, (int, float)):
                value = raw < 0.15
                evidence = "最大偏见分数={:.3f} → {}".format(
                    raw, "通过" if value else "未通过")
            else:
                value = False
                evidence = "无偏见检查数据"

        elif dim == "sensitivity":
            value = scores.get("sensitivity", scores.get("sensitivity_pass", False))
            if isinstance(value, bool):
                evidence = "敏感性分析{}".format("通过" if value else "未通过")
            else:
                value = bool(value)
                evidence = "敏感性分析={}".format(value)

        # --- T5 KPI ---
        elif dim == "kpi_target":
            kpi_rows = [pg for pg in plan_gates if pg.get("threshold") is None]
            if not kpi_rows:
                value = False
                evidence = "无KPI定义（plan.gates 无 threshold=null 行）"
            else:
                kpi_pass = True
                kpi_details = []
                for pg in kpi_rows:
                    pg_dim = pg.get("dimension", pg.get("dim", ""))
                    override = scores.get(pg_dim)
                    met = kpi_row_satisfied(pg, override)
                    if not met:
                        kpi_pass = False
                    cur = (
                        override if override is not None else pg.get("current")
                    )
                    tgt = pg.get("target")
                    kpi_details.append("{}:{}→{}({})".format(
                        pg_dim, cur, tgt, "✓" if met else "✗"))
                value = kpi_pass
                evidence = "; ".join(kpi_details)

        # --- T6 生成类 ---
        elif dim == "pass_rate":
            value = scores.get("pass_rate", 0.0)
            if isinstance(value, (int, float)):
                evidence = "通过率={:.1f}%".format(value)
            else:
                value = 0.0
                evidence = "无通过率数据"

        elif dim == "avg_score":
            value = scores.get("avg_score", scores.get("average_score", 0.0))
            if isinstance(value, (int, float)):
                evidence = "平均分={:.1f}/10".format(value)
            else:
                value = 0.0
                evidence = "无平均分数据"

        # --- T4 交付类 ---
        elif dim == "syntax":
            value = scores.get("syntax_errors", scores.get("syntax", 0))
            if isinstance(value, (int, float)):
                value = int(value)
                evidence = "语法错误={}个".format(value)
            else:
                value = 0
                evidence = "无语法检查数据"

        elif dim == "p1_p2_issues":
            counts = _count_issues_by_severity(state)
            value = counts["P1"] + counts["P2"]
            evidence = "P1={}, P2={}".format(counts["P1"], counts["P2"])

        elif dim == "service_health":
            value = scores.get("service_health", scores.get("services_healthy", False))
            if isinstance(value, bool):
                evidence = "服务状态={}".format("健康" if value else "异常")
            else:
                value = bool(value)
                evidence = "服务状态={}".format(value)

        elif dim == "user_acceptance":
            value = scores.get("user_acceptance", scores.get("user_confirmed", False))
            if isinstance(value, bool):
                evidence = "用户验收={}".format("已确认" if value else "未确认")
            else:
                value = bool(value)
                evidence = "用户验收={}".format(value)

        # --- T7 质量类 ---
        elif dim == "security_score":
            value = scores.get("security_score", scores.get("security", 0.0))
            value = float(value) if isinstance(value, (int, float)) else 0.0
            evidence = "安全性得分={:.1f}/10".format(value)

        elif dim == "reliability_score":
            value = scores.get("reliability_score", scores.get("reliability", 0.0))
            value = float(value) if isinstance(value, (int, float)) else 0.0
            evidence = "可靠性得分={:.1f}/10".format(value)

        elif dim == "maintainability_score":
            value = scores.get("maintainability_score", scores.get("maintainability", 0.0))
            value = float(value) if isinstance(value, (int, float)) else 0.0
            evidence = "可维护性得分={:.1f}/10".format(value)

        elif dim == "p1_all":
            counts = _count_issues_by_severity(state)
            value = counts["P1"]
            evidence = "全维度P1问题={}个".format(value)

        elif dim == "security_p2":
            counts = _count_issues_by_severity(state, "security")
            value = counts["P2"]
            evidence = "安全P2问题={}个".format(value)

        elif dim == "reliability_p2":
            counts = _count_issues_by_severity(state, "reliability")
            value = counts["P2"]
            evidence = "可靠性P2问题={}个".format(value)

        elif dim == "maintainability_p2":
            counts = _count_issues_by_severity(state, "maintainability")
            value = counts["P2"]
            evidence = "可维护性P2问题={}个".format(value)

        # --- T8 优化类 ---
        elif dim == "architecture":
            value = scores.get("architecture", scores.get("architecture_score", 0.0))
            value = float(value) if isinstance(value, (int, float)) else 0.0
            evidence = "架构得分={:.1f}/10".format(value)

        elif dim == "performance":
            value = scores.get("performance", scores.get("performance_score", 0.0))
            value = float(value) if isinstance(value, (int, float)) else 0.0
            evidence = "性能得分={:.1f}/10".format(value)

        elif dim == "stability":
            value = scores.get("stability", scores.get("stability_score", 0.0))
            value = float(value) if isinstance(value, (int, float)) else 0.0
            evidence = "稳定性得分={:.1f}/10".format(value)

        # --- T3 产品设计类 ---
        elif dim == "design_completeness":
            # 检查 findings 中有多少需求条目有对应的设计描述
            raw = scores.get("design_completeness", scores.get("design_complete", None))
            if raw is not None and isinstance(raw, (int, float)):
                value = float(raw)
                evidence = "设计完整度={:.1f}/10（来自 scores）".format(value)
            else:
                rounds = state.get("findings", {}).get("rounds", [])
                req_entries = 0
                design_entries = 0
                for rnd in rounds:
                    for finding in rnd.get("findings", []):
                        body = _finding_body_text(finding)
                        dim_tag = finding.get("dimension", "")
                        if any(kw in dim_tag or kw in body for kw in
                               ("需求", "requirement", "功能", "feature", "user story")):
                            req_entries += 1
                            if any(kw in body for kw in
                                   ("方案", "设计", "design", "spec", "实现", "架构", "approach")):
                                design_entries += 1
                if req_entries > 0:
                    value = min(10.0, (design_entries / req_entries) * 10.0)
                    evidence = "{}/{}需求条目有设计描述 → {:.1f}/10".format(
                        design_entries, req_entries, value)
                else:
                    value = 0.0
                    evidence = "未找到需求条目（findings 中无需求维度标注）"

        elif dim == "feasibility_score":
            # 检查是否有技术可行性分析内容
            raw = scores.get("feasibility_score", scores.get("feasibility", None))
            if raw is not None and isinstance(raw, (int, float)):
                value = float(raw)
                evidence = "技术可行性={:.1f}/10（来自 scores）".format(value)
            else:
                rounds = state.get("findings", {}).get("rounds", [])
                feasibility_signals = 0
                for rnd in rounds:
                    for finding in rnd.get("findings", []):
                        body = _finding_body_text(finding)
                        dim_tag = finding.get("dimension", "")
                        if any(kw in dim_tag or kw in body for kw in
                               ("可行性", "feasibility", "风险", "risk", "技术约束",
                                "constraint", "依赖", "dependency", "架构", "architecture")):
                            feasibility_signals += _finding_substantive_info_count(finding)
                if feasibility_signals >= 6:
                    value = 9.0
                elif feasibility_signals >= 4:
                    value = 7.5
                elif feasibility_signals >= 2:
                    value = 6.0
                elif feasibility_signals >= 1:
                    value = 4.0
                else:
                    value = 0.0
                evidence = "可行性相关信息点={}个 → {:.1f}/10".format(feasibility_signals, value)

        elif dim == "requirement_coverage":
            # 检查需求到设计的追溯链（每条需求可追溯到文档章节）
            raw = scores.get("requirement_coverage", scores.get("req_coverage", None))
            if raw is not None and isinstance(raw, (int, float)):
                value = float(raw)
                evidence = "需求覆盖度={:.1f}/10（来自 scores）".format(value)
            else:
                covered, total = _count_findings_coverage(state)
                value = (covered / total * 10.0) if total > 0 else 0.0
                evidence = "{}/{}维度有追溯记录 → {:.1f}/10".format(covered, total, value)

        elif dim == "scope_precision":
            # 检查是否有明确的 IN/OUT 范围定义
            raw = scores.get("scope_precision", scores.get("scope", None))
            if raw is not None and isinstance(raw, (int, float)):
                value = float(raw)
                evidence = "范围精确度={:.1f}/10（来自 scores）".format(value)
            else:
                rounds = state.get("findings", {}).get("rounds", [])
                scope_signals = 0
                for rnd in rounds:
                    for finding in rnd.get("findings", []):
                        body = _finding_body_text(finding)
                        dim_tag = finding.get("dimension", "")
                        if any(kw in dim_tag or kw in body for kw in
                               ("范围", "scope", "IN scope", "OUT scope", "边界", "boundary",
                                "不包含", "排除", "exclude", "明确")):
                            scope_signals += _finding_substantive_info_count(finding)
                if scope_signals >= 4:
                    value = 9.0
                elif scope_signals >= 2:
                    value = 7.0
                elif scope_signals >= 1:
                    value = 5.0
                else:
                    value = 0.0
                evidence = "范围定义信息点={}个 → {:.1f}/10".format(scope_signals, value)

        elif dim == "validation_evidence":
            # 检查是否有独立评审记录（可行性检查 + 风险评估已完成）
            raw = scores.get("validation_evidence", scores.get("validation", None))
            if raw is not None and isinstance(raw, (int, float)):
                value = float(raw)
                evidence = "验证证据={:.1f}/10（来自 scores）".format(value)
            else:
                rounds = state.get("findings", {}).get("rounds", [])
                validation_signals = 0
                for rnd in rounds:
                    for finding in rnd.get("findings", []):
                        body = _finding_body_text(finding)
                        dim_tag = finding.get("dimension", "")
                        if any(kw in dim_tag or kw in body for kw in
                               ("评审", "review", "验证", "validation", "检查", "check",
                                "风险评估", "risk assessment", "可行性检查", "feasibility check")):
                            validation_signals += _finding_substantive_info_count(finding)
                if validation_signals >= 4:
                    value = 9.0
                elif validation_signals >= 2:
                    value = 7.0
                elif validation_signals >= 1:
                    value = 5.0
                else:
                    value = 0.0
                evidence = "评审/验证信息点={}个 → {:.1f}/10".format(validation_signals, value)

        else:
            # 未知维度 — 尝试从 scores 中直接读取
            value = scores.get(dim, 0)
            evidence = "从 scores 直接读取: {}={}".format(dim, value)

        results.append(_eval_gate(gate_def, value, evidence))

    # --- LLM Grader 准备阶段 ---
    # 遍历已评分的 gates，为启用了 llm_grader 且 confidence=heuristic 的维度
    # 准备 grader prompt + 上下文，写入 state.metadata.pending_llm_grader
    work_dir = state.get("_work_dir", "")
    pending_graders = []
    for gate_def, result in zip(gates, results):
        entry = _prepare_llm_grader(gate_def, result, state, work_dir)
        if entry:
            pending_graders.append(entry)

    if pending_graders:
        if "metadata" not in state:
            state["metadata"] = {}
        state["metadata"]["pending_llm_grader"] = pending_graders

    return template, results


# =====================================================================
# Markdown 回退评分（兼容旧模式）
# =====================================================================

# 非维度章节关键词
_SKIP_KEYWORDS = [
    "执行摘要", "来源清单", "策略评估", "信息缺口", "争议", "拓展方向",
    "问题清单", "修复记录", "模式识别", "经验教训", "问题追踪",
]
_ROUND_HEADER_RE = re.compile(r'^第\s*\d+\s*轮')


def _split_all_sections(content):
    """将 markdown 内容按 ## 和 ### 标题分割为 (level, heading, body) 列表"""
    pattern = re.compile(r'^(#{2,3})\s+(.+)$', re.MULTILINE)
    sections = []
    matches = list(pattern.finditer(content))
    for i, m in enumerate(matches):
        heading_level = len(m.group(1))
        heading_text = m.group(2).strip()
        body_start = m.end()
        body_end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        body = content[body_start:body_end].strip()
        sections.append((heading_level, heading_text, body))
    return sections


def _is_dimension_section(level, heading, body):
    """判断章节是否为维度章节"""
    if any(skip in heading for skip in _SKIP_KEYWORDS):
        return False
    if _ROUND_HEADER_RE.match(heading):
        return False
    if level == 3 and re.search(r'\[.+\]', heading):
        return True
    if "维度" in heading or "Dimension" in heading or "关键发现" in heading:
        return True
    if level == 2 and len(body) > 20:
        return True
    return False


def _count_info_points(body):
    """计算章节中的信息点数量"""
    lines = body.split("\n")
    bullet_count = sum(1 for line in lines
                       if line.strip().startswith("- ") and len(line.strip()) > 10)
    if bullet_count >= 2:
        return bullet_count
    para_count = sum(1 for line in lines
                     if line.strip()
                     and not line.strip().startswith("来源:")
                     and not line.strip().startswith("来源：")
                     and not line.strip().startswith("策略:")
                     and not line.strip().startswith("策略：")
                     and not line.strip().startswith("ID:")
                     and not line.strip().startswith("ID：")
                     and not line.strip().startswith("|")
                     and not line.strip().startswith("#")
                     and len(line.strip()) > 10)
    return max(bullet_count, para_count)


def score_from_markdown(content):
    """从 markdown 内容评分（旧模式回退），返回 ("T1", results_list)。

    Markdown 模式只支持 T1 的 4 个维度（覆盖率/可信度/一致性/完整性）。
    """
    sections = _split_all_sections(content)

    # --- 覆盖率 ---
    total_dims = 0
    covered_dims = 0
    for level, heading, body in sections:
        if not _is_dimension_section(level, heading, body):
            continue
        total_dims += 1
        if _count_info_points(body) >= 2:
            covered_dims += 1

    cov_pct = (covered_dims / total_dims * 100) if total_dims > 0 else 0.0

    # --- 可信度 ---
    source_markers = ["http", "来源", "Source", "arXiv", "GitHub"]
    inline_findings = re.findall(r'- .+(?:来源|Source|http|arXiv|GitHub).+', content)
    ssot_findings = []
    for level, heading, body in sections:
        if not _is_dimension_section(level, heading, body):
            continue
        has_source = bool(re.search(
            r'(?:^来源[:：]|^Source[:：]|https?://)', body, re.MULTILINE))
        if has_source:
            ssot_findings.append(body)

    total_findings = max(len(inline_findings), len(ssot_findings))
    multi_source = 0
    for f_text in inline_findings:
        if (f_text.count("http") >= 2 or "多" in f_text or "multiple" in f_text.lower()
                or f_text.count("来源") >= 2 or f_text.count("Source") >= 2):
            multi_source += 1
    ssot_multi = 0
    for body in ssot_findings:
        url_count = len(re.findall(r'https?://', body))
        source_line_count = len(re.findall(r'^来源[:：]', body, re.MULTILINE))
        if (url_count >= 2 or source_line_count >= 2
                or "多" in body or "multiple" in body.lower()):
            ssot_multi += 1
    multi_source = max(multi_source, ssot_multi)
    cred_pct = (multi_source / total_findings * 100) if total_findings > 0 else 0.0

    # --- 一致性 ---
    contradictions = len(re.findall(
        r'矛盾|冲突|不一致|contradictory|conflict', content, re.IGNORECASE))
    consistent_dims = max(0, total_dims - contradictions)
    cons_pct = (consistent_dims / total_dims * 100) if total_dims > 0 else 0.0

    # --- 完整性 ---
    bullet_statements = re.findall(r'- .{20,}', content)
    bullet_total = len(bullet_statements)
    bullet_sourced = sum(1 for s in bullet_statements
                         if any(marker in s for marker in source_markers))
    ssot_total = 0
    ssot_sourced = 0
    for level, heading, body in sections:
        if not _is_dimension_section(level, heading, body):
            continue
        if _count_info_points(body) < 1:
            continue
        ssot_total += 1
        if any(marker in body for marker in source_markers):
            ssot_sourced += 1
    if ssot_total >= bullet_total:
        comp_sourced, comp_total = ssot_sourced, ssot_total
    else:
        comp_sourced, comp_total = bullet_sourced, bullet_total
    comp_pct = (comp_sourced / comp_total * 100) if comp_total > 0 else 0.0

    # 构建 T1 门禁结果
    gates = TEMPLATE_GATES["T1"]
    values = {
        "coverage": (cov_pct, "{}/{}维度有实质内容".format(covered_dims, total_dims)),
        "credibility": (cred_pct, "{}/{}发现有多源支撑".format(multi_source, total_findings)),
        "consistency": (cons_pct, "{}/{}维度无矛盾".format(consistent_dims, total_dims)),
        "completeness": (comp_pct, "{}/{}陈述有来源引用".format(comp_sourced, comp_total)),
    }

    results = []
    for gate_def in gates:
        val, ev = values[gate_def["dim"]]
        results.append(_eval_gate(gate_def, val, ev))

    return "T1", results


# =====================================================================
# 输出格式化
# =====================================================================

def _overall_pass(results):
    """判定总体是否通过：所有硬门禁通过即为通过"""
    for r in results:
        if isinstance(r, dict) and r.get("gate_type") == "hard" and not r.get("pass", False):
            return False
    return True


def print_results(template, results, mode="ssot", state=None):
    """格式化输出门禁结果"""
    payload = results_to_json(template, results, mode=mode, state=state)
    overall = payload["overall_pass"]
    mode_label = "SSOT" if mode == "ssot" else "Markdown(回退)"

    print("模板: {} | 模式: {} | 总判定: {}".format(
        template or "未知", mode_label, "PASS" if overall else "FAIL"))
    if mode == "ssot" and state is not None and payload.get("tsv_fail_closed"):
        print(
            "TSV fail-closed: {}（与 EVOLVE 终止 rollup 一致；门禁 alone 不足以判收敛）".format(
                payload.get("fail_closed_reason") or "方差/置信度"
            )
        )
    print()
    print("{:<16} {:>10} {:>10} {:>6} {:>6} {:>10} {:>6}  {}".format(
        "维度", "得分", "阈值", "类型", "状态", "置信度", "误差", "证据"))
    print("-" * 110)

    for r in results:
        if "error" in r:
            print("ERROR: {}".format(r["error"]))
            continue

        label = r.get("label", r.get("dimension", "?"))
        val_display = r.get("value_display", str(r.get("value", "?")))
        thr_display = r.get("threshold_display", str(r.get("threshold", "?")))
        gate_type = r.get("gate_type", "?")
        status = "✅" if r.get("pass") else "❌"
        evidence = r.get("evidence", "")
        confidence = r.get("confidence", "?")
        margin = r.get("margin")
        margin_display = "±{:.1f}".format(margin) if margin is not None else "N/A"

        print("{:<16} {:>10} {:>10} {:>6} {:>6} {:>10} {:>6}  {}".format(
            label, val_display, thr_display, gate_type, status, confidence, margin_display, evidence))

    # 软门禁未通过的提示
    soft_fails = [r for r in results
                  if isinstance(r, dict) and r.get("gate_type") == "soft" and not r.get("pass", False)]
    if soft_fails and payload.get("gates_pass"):
        print()
        print("注意: {}个软门禁未通过（已记录，不阻塞终止判定）:".format(len(soft_fails)))
        for r in soft_fails:
            print("  - {}: {}".format(r.get("label", r.get("dimension")), r.get("evidence", "")))

    print()


def results_to_json(template, results, mode="ssot", state=None):
    """将结果转为 JSON 可序列化的 dict。

    SSOT 模式下若 results_tsv 末行 fail-closed，则 overall_pass 为 false（与 controller phase_evolve 一致）。
    """
    gate_pass = _overall_pass(results)
    tsv_fc, tsv_reason = False, None
    if mode == "ssot" and state is not None:
        tsv_fc, tsv_reason = results_tsv_last_row_fail_closed(state)
    overall = gate_pass and not tsv_fc
    return {
        "template": template,
        "mode": mode,
        "gates_pass": gate_pass,
        "tsv_fail_closed": tsv_fc,
        "fail_closed_reason": tsv_reason if tsv_fc else None,
        "overall_pass": overall,
        "gates": results,
    }


# =====================================================================
# CLI 入口
# =====================================================================

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    target_path = sys.argv[1]
    json_output = "--json" in sys.argv

    mode, data, context = detect_mode(target_path)

    if mode == "error":
        print("ERROR: {}".format(data))
        sys.exit(1)

    if mode == "ssot":
        template, results = score_from_ssot(data)
    else:
        template, results = score_from_markdown(data)

    ssot_state = data if mode == "ssot" else None
    if json_output:
        output = results_to_json(template, results, mode, state=ssot_state)
        print(json.dumps(output, ensure_ascii=False, indent=2))
    else:
        print_results(template, results, mode, state=ssot_state)
        # 附加 JSON 行（供其他脚本消费）
        output = results_to_json(template, results, mode, state=ssot_state)
        print("---JSON---")
        print(json.dumps(output, ensure_ascii=False))

    sys.exit(0 if results_to_json(template, results, mode, state=ssot_state)["overall_pass"] else 1)


if __name__ == "__main__":
    main()
