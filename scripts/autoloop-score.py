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

# ---------------------------------------------------------------------------
# 门禁定义（SSOT — 来自 quality-gates.md）
# 每个门禁: dimension, threshold, gate_type(hard/soft), unit, description
# ---------------------------------------------------------------------------

TEMPLATE_GATES = {
    "T1": [
        {"dim": "coverage",      "threshold": 85,   "unit": "%",   "gate": "hard", "label": "覆盖率"},
        {"dim": "credibility",   "threshold": 80,   "unit": "%",   "gate": "hard", "label": "可信度"},
        {"dim": "consistency",   "threshold": 90,   "unit": "%",   "gate": "soft", "label": "一致性"},
        {"dim": "completeness",  "threshold": 85,   "unit": "%",   "gate": "soft", "label": "完整性"},
    ],
    "T2": [
        {"dim": "coverage",         "threshold": 100,  "unit": "%",    "gate": "hard", "label": "覆盖率"},
        {"dim": "credibility",      "threshold": 80,   "unit": "%",    "gate": "hard", "label": "可信度"},
        {"dim": "bias_check",       "threshold": 0.15, "unit": "score","gate": "hard", "label": "偏见检查"},
        {"dim": "sensitivity",      "threshold": 1,    "unit": "bool", "gate": "soft", "label": "敏感性分析"},
    ],
    "T3": [
        {"dim": "kpi_target",  "threshold": None, "unit": "user_defined", "gate": "hard", "label": "KPI达标"},
    ],
    "T4": [
        {"dim": "pass_rate",  "threshold": 95,  "unit": "%",    "gate": "hard", "label": "通过率"},
        {"dim": "avg_score",  "threshold": 7.0, "unit": "/10",  "gate": "hard", "label": "平均分"},
    ],
    "T5": [
        {"dim": "syntax",            "threshold": 0,  "unit": "errors",  "gate": "hard", "label": "语法验证"},
        {"dim": "p1_p2_issues",      "threshold": 0,  "unit": "count",   "gate": "hard", "label": "P1/P2问题"},
        {"dim": "service_health",    "threshold": 1,  "unit": "bool",    "gate": "soft", "label": "服务健康"},
        {"dim": "user_acceptance",   "threshold": 1,  "unit": "bool",    "gate": "hard", "label": "人工验收"},
    ],
    "T6": [
        {"dim": "security_score",       "threshold": 9.0,  "unit": "/10",  "gate": "hard", "label": "安全性"},
        {"dim": "reliability_score",    "threshold": 8.0,  "unit": "/10",  "gate": "hard", "label": "可靠性"},
        {"dim": "maintainability_score","threshold": 8.0,  "unit": "/10",  "gate": "hard", "label": "可维护性"},
        {"dim": "p1_all",               "threshold": 0,    "unit": "count","gate": "hard", "label": "P1问题(全维度)"},
        {"dim": "security_p2",          "threshold": 0,    "unit": "count","gate": "hard", "label": "安全P2问题"},
        {"dim": "reliability_p2",       "threshold": 3,    "unit": "count","gate": "soft", "label": "可靠性P2问题"},
        {"dim": "maintainability_p2",   "threshold": 5,    "unit": "count","gate": "soft", "label": "可维护性P2问题"},
    ],
    "T7": [
        {"dim": "architecture",  "threshold": 8.0, "unit": "/10", "gate": "hard", "label": "架构"},
        {"dim": "performance",   "threshold": 8.0, "unit": "/10", "gate": "hard", "label": "性能"},
        {"dim": "stability",     "threshold": 8.0, "unit": "/10", "gate": "hard", "label": "稳定性"},
    ],
}

# 模板别名映射（用户可能写 "T1 Research" 而非 "T1"）
_TEMPLATE_ALIAS = {}
for _k in TEMPLATE_GATES:
    _TEMPLATE_ALIAS[_k] = _k
    _TEMPLATE_ALIAS[_k.lower()] = _k
_TEMPLATE_ALIAS.update({
    "t1 research": "T1", "t1-research": "T1", "research": "T1",
    "t2 compare": "T2", "t2-compare": "T2", "compare": "T2",
    "t3 iterate": "T3", "t3-iterate": "T3", "iterate": "T3",
    "t4 generate": "T4", "t4-generate": "T4", "generate": "T4",
    "t5 deliver": "T5", "t5-deliver": "T5", "deliver": "T5",
    "t6 quality": "T6", "t6-quality": "T6", "quality": "T6",
    "t7 optimize": "T7", "t7-optimize": "T7", "optimize": "T7",
})


def resolve_template(raw):
    """将模板字符串标准化为 T1-T7 键"""
    if not raw:
        return None
    key = raw.strip().lower()
    return _TEMPLATE_ALIAS.get(key)


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
        # 视为 markdown
        with open(path, "r", encoding="utf-8") as f:
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
    """从 findings.rounds 计算维度覆盖情况"""
    plan_dims = state.get("plan", {}).get("dimensions", [])
    total_dims = len(plan_dims) if plan_dims else 0

    # 收集所有 round 中出现的维度
    covered_dims = set()
    rounds = state.get("findings", {}).get("rounds", [])
    for rnd in rounds:
        for finding in rnd.get("findings", []):
            dim = finding.get("dimension", "")
            if dim:
                covered_dims.add(dim)

    # 如果 plan 没定义 dimensions，就用 findings 中出现的维度数作为 total
    if total_dims == 0:
        total_dims = len(covered_dims)

    return len(covered_dims), total_dims


def _count_findings_credibility(state):
    """计算有多源支撑的发现比例"""
    rounds = state.get("findings", {}).get("rounds", [])
    total = 0
    multi_source = 0
    for rnd in rounds:
        for finding in rnd.get("findings", []):
            total += 1
            source = finding.get("source", "")
            # 多源检测：多个 URL 或明确标注
            url_count = len(re.findall(r'https?://', source)) if source else 0
            if url_count >= 2 or ";" in source or "," in source:
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
    """计算有来源引用的发现比例"""
    rounds = state.get("findings", {}).get("rounds", [])
    total = 0
    sourced = 0
    for rnd in rounds:
        for finding in rnd.get("findings", []):
            total += 1
            source = finding.get("source", "")
            if source and len(source.strip()) > 0:
                sourced += 1
    return sourced, total


def _eval_gate(gate_def, value, evidence=""):
    """评估单个门禁，返回结果 dict。

    value: 实际值（百分比 / 分数 / 计数 / bool）
    """
    dim = gate_def["dim"]
    threshold = gate_def["threshold"]
    unit = gate_def["unit"]
    gate_type = gate_def["gate"]
    label = gate_def["label"]

    # threshold 为 None 表示用户自定义（T3 KPI）
    if threshold is None:
        passed = value is not None and value is True
        return {
            "dimension": dim,
            "label": label,
            "value": value,
            "threshold": "用户定义",
            "unit": unit,
            "gate_type": gate_type,
            "pass": passed,
            "evidence": evidence,
        }

    # 根据 unit 决定比较方式
    if unit in ("%", "/10"):
        # 值越大越好
        passed = value >= threshold
    elif unit == "bool":
        passed = bool(value)
    elif unit in ("errors", "count"):
        # 值越小越好（≤ threshold）
        passed = value <= threshold
    elif unit == "score":
        # bias_check: 值越小越好（< threshold）
        passed = value < threshold
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
        thr_display = "< {}".format(threshold)
        val_display = "{:.3f}".format(value)
    elif unit in ("errors", "count"):
        thr_display = "<= {}".format(threshold)
        val_display = str(int(value))
    elif unit == "bool":
        thr_display = "True"
        val_display = str(bool(value))
    else:
        thr_display = str(threshold)
        val_display = str(value)

    return {
        "dimension": dim,
        "label": label,
        "value": value,
        "value_display": val_display,
        "threshold": threshold,
        "threshold_display": thr_display,
        "unit": unit,
        "gate_type": gate_type,
        "pass": passed,
        "evidence": evidence,
    }


def score_from_ssot(state):
    """从 SSOT JSON 评分，返回 (template, results_list)。

    results_list: [{dimension, label, value, threshold, gate_type, pass, evidence}, ...]
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
            # 从 scores 或 plan_gates 读取偏见分数（max across options）
            value = scores.get("bias_check", scores.get("bias_score", 0.0))
            if isinstance(value, (int, float)):
                evidence = "最大偏见分数={:.3f}".format(value)
            else:
                value = 0.0
                evidence = "无偏见检查数据"

        elif dim == "sensitivity":
            value = scores.get("sensitivity", scores.get("sensitivity_pass", False))
            if isinstance(value, bool):
                evidence = "敏感性分析{}".format("通过" if value else "未通过")
            else:
                value = bool(value)
                evidence = "敏感性分析={}".format(value)

        # --- T3 KPI ---
        elif dim == "kpi_target":
            # 检查 plan.gates 中用户定义的 KPI 是否全部达标
            kpi_pass = True
            kpi_details = []
            for pg in plan_gates:
                pg_dim = pg.get("dimension", "")
                current = pg.get("current")
                target = pg.get("target")
                status = pg.get("status", "")
                if current is not None and target is not None:
                    try:
                        met = float(current) >= float(target)
                    except (ValueError, TypeError):
                        met = status in ("达标", "通过", "pass", "passed")
                    if not met:
                        kpi_pass = False
                    kpi_details.append("{}:{}→{}({})".format(
                        pg_dim, current, target, "✓" if met else "✗"))
                else:
                    kpi_pass = False
                    kpi_details.append("{}:未定义目标值".format(pg_dim))
            value = kpi_pass
            evidence = "; ".join(kpi_details) if kpi_details else "无KPI定义"

        # --- T4 生成类 ---
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

        # --- T5 交付类 ---
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

        # --- T6 质量类 ---
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

        # --- T7 优化类 ---
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

        else:
            # 未知维度 — 尝试从 scores 中直接读取
            value = scores.get(dim, 0)
            evidence = "从 scores 直接读取: {}={}".format(dim, value)

        results.append(_eval_gate(gate_def, value, evidence))

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


def print_results(template, results, mode="ssot"):
    """格式化输出门禁结果"""
    overall = _overall_pass(results)
    mode_label = "SSOT" if mode == "ssot" else "Markdown(回退)"

    print("模板: {} | 模式: {} | 总判定: {}".format(
        template or "未知", mode_label, "PASS" if overall else "FAIL"))
    print()
    print("{:<16} {:>10} {:>10} {:>6} {:>6}  {}".format(
        "维度", "得分", "阈值", "类型", "状态", "证据"))
    print("-" * 90)

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

        print("{:<16} {:>10} {:>10} {:>6} {:>6}  {}".format(
            label, val_display, thr_display, gate_type, status, evidence))

    # 软门禁未通过的提示
    soft_fails = [r for r in results
                  if isinstance(r, dict) and r.get("gate_type") == "soft" and not r.get("pass", False)]
    if soft_fails and overall:
        print()
        print("注意: {}个软门禁未通过（已记录，不阻塞终止判定）:".format(len(soft_fails)))
        for r in soft_fails:
            print("  - {}: {}".format(r.get("label", r.get("dimension")), r.get("evidence", "")))

    print()


def results_to_json(template, results, mode="ssot"):
    """将结果转为 JSON 可序列化的 dict"""
    return {
        "template": template,
        "mode": mode,
        "overall_pass": _overall_pass(results),
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

    if json_output:
        output = results_to_json(template, results, mode)
        print(json.dumps(output, ensure_ascii=False, indent=2))
    else:
        print_results(template, results, mode)
        # 附加 JSON 行（供其他脚本消费）
        output = results_to_json(template, results, mode)
        print("---JSON---")
        print(json.dumps(output, ensure_ascii=False))

    sys.exit(0 if _overall_pass(results) else 1)


if __name__ == "__main__":
    main()
