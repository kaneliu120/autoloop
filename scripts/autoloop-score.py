#!/usr/bin/env python3
"""AutoLoop 质量门禁计算工具"""

import sys
import os
import re
import json


def _split_all_sections(content):
    """将markdown内容按 ## 和 ### 标题分割为 (heading, body) 列表。

    同时处理旧格式（## 维度名）和SSOT渲染格式（### 维度名 [confidence]）。
    """
    # 匹配 ## 或 ### 开头的标题行，捕获标题级别和内容
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


# 非维度章节关键词（用于过滤）
_SKIP_KEYWORDS = [
    "执行摘要", "来源清单", "策略评估", "信息缺口", "争议", "拓展方向",
    "问题清单", "修复记录", "模式识别", "经验教训", "问题追踪",
]

# SSOT渲染器的轮次标题模式：## 第 X 轮发现
_ROUND_HEADER_RE = re.compile(r'^第\s*\d+\s*轮')


def _is_dimension_section(level, heading, body):
    """判断一个章节是否为维度章节。

    支持两种格式：
    - 旧格式：## 维度名（heading包含"维度"/"Dimension"/"关键发现"）
    - SSOT格式：### 维度名 [confidence]（level==3，非轮次/非跳过标题）
    """
    # 跳过非维度章节
    if any(skip in heading for skip in _SKIP_KEYWORDS):
        return False
    # 跳过轮次标题（## 第 X 轮发现）
    if _ROUND_HEADER_RE.match(heading):
        return False

    # SSOT渲染格式：### 维度名 [confidence]
    if level == 3 and re.search(r'\[.+\]', heading):
        return True

    # 旧格式：## 维度名 / Dimension / 关键发现
    if "维度" in heading or "Dimension" in heading or "关键发现" in heading:
        return True

    # 旧格式兜底：## 级别，且body有实质内容
    if level == 2 and len(body) > 20:
        return True

    return False


def _count_info_points(body):
    """计算章节中的信息点数量。

    支持两种格式：
    - 旧格式：以 '- ' 开头的列表项
    - SSOT格式：非空段落文本（非来源行、非空行）
    """
    lines = body.split("\n")
    # 统计 bullet 列表项
    bullet_count = sum(1 for line in lines
                       if line.strip().startswith("- ") and len(line.strip()) > 10)

    if bullet_count >= 2:
        return bullet_count

    # SSOT格式：统计有实质内容的段落行（排除来源行、元数据行、空行、表格行）
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


def count_dimensions_with_content(findings_path):
    """从findings.md中计算有实质内容的维度数"""
    if not os.path.exists(findings_path):
        return 0, 0

    with open(findings_path, "r", encoding="utf-8") as f:
        content = f.read()

    sections = _split_all_sections(content)
    total_dims = 0
    covered_dims = 0

    for level, heading, body in sections:
        if not _is_dimension_section(level, heading, body):
            continue

        total_dims += 1
        info_points = _count_info_points(body)
        if info_points >= 2:
            covered_dims += 1

    return covered_dims, total_dims


def count_credibility(findings_path):
    """计算可信度：有多个独立来源的关键发现比例。

    支持两种格式：
    - 旧格式：inline来源（- Finding with 来源 or http://...）
    - SSOT格式：来源在单独行（来源: URL），关联到前面的段落内容
    """
    if not os.path.exists(findings_path):
        return 0, 0

    with open(findings_path, "r", encoding="utf-8") as f:
        content = f.read()

    # 方式1：旧格式 — bullet行内嵌来源
    inline_findings = re.findall(r'- .+(?:来源|Source|http|arXiv|GitHub).+', content)

    # 方式2：SSOT格式 — 维度章节中有独立来源行
    sections = _split_all_sections(content)
    ssot_findings = []
    for level, heading, body in sections:
        if not _is_dimension_section(level, heading, body):
            continue
        # 检查该维度是否有来源行
        has_source = bool(re.search(
            r'(?:^来源[:：]|^Source[:：]|https?://)', body, re.MULTILINE))
        if has_source:
            ssot_findings.append(body)

    # 合并去重：取较大的计数（同一文件不会同时有大量两种格式）
    total_findings = max(len(inline_findings), len(ssot_findings))
    if total_findings == 0:
        return 0, 0

    # 多源印证统计
    multi_source = 0

    # 旧格式多源检测
    for f in inline_findings:
        if (f.count("http") >= 2 or "多" in f or "multiple" in f.lower()
                or f.count("来源") >= 2 or f.count("Source") >= 2):
            multi_source += 1

    # SSOT格式多源检测：一个维度body中有多个URL或多个来源行
    ssot_multi = 0
    for body in ssot_findings:
        url_count = len(re.findall(r'https?://', body))
        source_line_count = len(re.findall(r'^来源[:：]', body, re.MULTILINE))
        if (url_count >= 2 or source_line_count >= 2
                or "多" in body or "multiple" in body.lower()):
            ssot_multi += 1

    multi_source = max(multi_source, ssot_multi)
    return multi_source, total_findings


def count_consistency(findings_path):
    """计算一致性：无矛盾的维度比例"""
    if not os.path.exists(findings_path):
        return 0, 0

    with open(findings_path, "r", encoding="utf-8") as f:
        content = f.read()

    # 搜索矛盾记录章节
    contradictions = len(re.findall(r'矛盾|冲突|不一致|contradictory|conflict', content, re.IGNORECASE))
    # 粗略估算：总维度数 - 有矛盾的维度数
    _, total_dims = count_dimensions_with_content(findings_path)
    if total_dims == 0:
        return 0, 0

    # 保守估计：每个矛盾标记影响1个维度
    consistent_dims = max(0, total_dims - contradictions)
    return consistent_dims, total_dims


def count_completeness(findings_path):
    """计算完整性：有引用来源的关键陈述比例。

    支持两种格式：
    - 旧格式：bullet行自带来源标注
    - SSOT格式：维度章节整体是否有来源行，来源关联到整个维度内容
    """
    if not os.path.exists(findings_path):
        return 0, 0

    with open(findings_path, "r", encoding="utf-8") as f:
        content = f.read()

    source_markers = ["http", "来源", "Source", "arXiv", "GitHub", "论文", "paper"]

    # 方式1：旧格式 — bullet陈述
    bullet_statements = re.findall(r'- .{20,}', content)
    bullet_total = len(bullet_statements)
    bullet_sourced = sum(1 for s in bullet_statements
                         if any(marker in s for marker in source_markers))

    # 方式2：SSOT格式 — 每个维度章节作为一个"陈述单元"
    sections = _split_all_sections(content)
    ssot_total = 0
    ssot_sourced = 0
    for level, heading, body in sections:
        if not _is_dimension_section(level, heading, body):
            continue
        if _count_info_points(body) < 1:
            continue
        ssot_total += 1
        # 检查该维度是否有来源标注（独立来源行或body内嵌URL）
        if any(marker in body for marker in source_markers):
            ssot_sourced += 1

    # 取较大的计数集
    if ssot_total >= bullet_total:
        return ssot_sourced, ssot_total
    return bullet_sourced, bullet_total


def calculate_gates(findings_path, gates_config=None):
    """计算所有质量门禁"""
    if gates_config is None:
        gates_config = {
            "coverage": {"threshold": 85, "label": "覆盖率"},
            "credibility": {"threshold": 80, "label": "可信度"},
            "consistency": {"threshold": 90, "label": "一致性"},
            "completeness": {"threshold": 80, "label": "完整性"},
        }

    results = {}

    # 覆盖率
    covered, total = count_dimensions_with_content(findings_path)
    pct = (covered / total * 100) if total > 0 else 0
    results["coverage"] = {
        "value": round(pct, 1),
        "detail": f"{covered}/{total}维度有实质内容",
        "threshold": gates_config["coverage"]["threshold"],
        "pass": pct >= gates_config["coverage"]["threshold"]
    }

    # 可信度
    multi, total_f = count_credibility(findings_path)
    pct = (multi / total_f * 100) if total_f > 0 else 0
    results["credibility"] = {
        "value": round(pct, 1),
        "detail": f"{multi}/{total_f}关键发现有多源印证",
        "threshold": gates_config["credibility"]["threshold"],
        "pass": pct >= gates_config["credibility"]["threshold"]
    }

    # 一致性
    consistent, total_d = count_consistency(findings_path)
    pct = (consistent / total_d * 100) if total_d > 0 else 0
    results["consistency"] = {
        "value": round(pct, 1),
        "detail": f"{consistent}/{total_d}维度无矛盾",
        "threshold": gates_config["consistency"]["threshold"],
        "pass": pct >= gates_config["consistency"]["threshold"]
    }

    # 完整性
    sourced, total_s = count_completeness(findings_path)
    pct = (sourced / total_s * 100) if total_s > 0 else 0
    results["completeness"] = {
        "value": round(pct, 1),
        "detail": f"{sourced}/{total_s}陈述有来源引用",
        "threshold": gates_config["completeness"]["threshold"],
        "pass": pct >= gates_config["completeness"]["threshold"]
    }

    return results


def print_results(results):
    """格式化输出门禁结果"""
    all_pass = all(r["pass"] for r in results.values())
    print(f"{'PASS' if all_pass else 'FAIL'}: 质量门禁{'全部达标' if all_pass else '部分未达标'}\n")

    print(f"{'维度':<12} {'得分':>8} {'阈值':>8} {'状态':>6} {'明细'}")
    print("-" * 70)
    for key, r in results.items():
        status = "✅" if r["pass"] else "❌"
        label = {"coverage": "覆盖率", "credibility": "可信度",
                 "consistency": "一致性", "completeness": "完整性"}.get(key, key)
        print(f"{label:<12} {r['value']:>7.1f}% {r['threshold']:>7}% {status:>6} {r['detail']}")

    # JSON输出（供其他脚本消费）
    print(f"\n---JSON---\n{json.dumps(results, ensure_ascii=False)}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法:")
        print("  autoloop-score.py <findings.md路径>")
        print("  autoloop-score.py <findings.md路径> --json  (仅输出JSON)")
        sys.exit(1)

    findings_path = sys.argv[1]
    if not os.path.exists(findings_path):
        print(f"ERROR: 文件不存在: {findings_path}")
        sys.exit(1)

    results = calculate_gates(findings_path)

    if "--json" in sys.argv:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        print_results(results)

    all_pass = all(r["pass"] for r in results.values())
    sys.exit(0 if all_pass else 1)
