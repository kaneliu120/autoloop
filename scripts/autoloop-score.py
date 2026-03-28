#!/usr/bin/env python3
"""AutoLoop 质量门禁计算工具"""

import sys
import os
import re
import json


def count_dimensions_with_content(findings_path):
    """从findings.md中计算有实质内容的维度数"""
    if not os.path.exists(findings_path):
        return 0, 0

    with open(findings_path, "r", encoding="utf-8") as f:
        content = f.read()

    # 匹配 ## 维度名称 或 ### 维度名称 格式的章节
    sections = re.split(r'\n##\s+', content)
    total_dims = 0
    covered_dims = 0

    for section in sections[1:]:  # 跳过文件头
        # 跳过非维度章节（执行摘要、来源清单等）
        if any(skip in section[:50] for skip in ["执行摘要", "来源清单", "策略评估", "信息缺口", "争议", "拓展方向", "问题清单", "修复记录", "模式识别", "经验教训"]):
            continue

        # 计算信息点数量（以 - 开头的行，且有实质内容）
        lines = section.split("\n")
        info_points = sum(1 for line in lines
                         if line.strip().startswith("- ") and len(line.strip()) > 10)

        if "维度" in section[:100] or "Dimension" in section[:100] or "关键发现" in section[:200]:
            total_dims += 1
            if info_points >= 2:
                covered_dims += 1

    return covered_dims, total_dims


def count_credibility(findings_path):
    """计算可信度：有多个独立来源的关键发现比例"""
    if not os.path.exists(findings_path):
        return 0, 0

    with open(findings_path, "r", encoding="utf-8") as f:
        content = f.read()

    # 匹配关键发现（以 - 开头，包含来源标注）
    findings = re.findall(r'- .+(?:来源|Source|http|arXiv|GitHub).+', content)
    total_findings = len(findings)

    # 有多源印证的发现（包含多个URL或"多个来源"等标注）
    multi_source = sum(1 for f in findings
                       if f.count("http") >= 2 or "多" in f or "multiple" in f.lower()
                       or f.count("来源") >= 2 or f.count("Source") >= 2)

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
    """计算完整性：有引用来源的关键陈述比例"""
    if not os.path.exists(findings_path):
        return 0, 0

    with open(findings_path, "r", encoding="utf-8") as f:
        content = f.read()

    # 匹配所有关键陈述（- 开头的列表项）
    statements = re.findall(r'- .{20,}', content)
    total = len(statements)

    # 有来源引用的陈述
    with_source = sum(1 for s in statements
                      if any(marker in s for marker in ["http", "来源", "Source", "arXiv", "GitHub", "论文", "paper"]))

    return with_source, total


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
