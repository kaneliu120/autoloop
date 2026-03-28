#!/usr/bin/env python3
"""AutoLoop 评分方差+置信度计算工具"""

import sys
import os
import csv
import math


def compute_variance(scores):
    """计算评分方差"""
    n = len(scores)
    if n < 2:
        return 0.0
    mean = sum(scores) / n
    variance = sum((s - mean) ** 2 for s in scores) / (n - 1)
    return variance


def compute_confidence(variance, evidence_count):
    """根据方差和证据数量计算置信度"""
    if evidence_count == 0 or variance >= 2.0:
        return 30, "低", True  # fail-closed
    elif evidence_count >= 3 and variance < 1.0:
        return 85, "高", False
    elif evidence_count >= 1 and variance < 2.0:
        return 65, "中", False
    else:
        return 30, "低", True


def cmd_compute(args):
    """compute <score1> <score2> [score3...] [--evidence N]"""
    evidence = 0
    scores = []
    i = 0
    while i < len(args):
        if args[i] == "--evidence" and i + 1 < len(args):
            evidence = int(args[i + 1])
            i += 2
        else:
            scores.append(float(args[i]))
            i += 1

    if len(scores) < 1:
        print("ERROR: 至少需要1个评分")
        return False

    mean = sum(scores) / len(scores)
    variance = compute_variance(scores)
    pct, level, fail_closed = compute_confidence(variance, evidence)

    status = "FAIL (fail-closed)" if fail_closed else "PASS"
    print(f"{status}: 置信度={pct}%（{level}）")
    print(f"  均值: {mean:.2f}")
    print(f"  方差: {variance:.4f}")
    print(f"  证据数: {evidence}")
    print(f"  推荐 score_variance: {variance:.2f}")
    print(f"  推荐 confidence: {pct}%")
    return not fail_closed


def cmd_check(tsv_path):
    """check <tsv文件> — 检查所有行的方差和置信度"""
    if not os.path.exists(tsv_path):
        print(f"ERROR: 文件不存在: {tsv_path}")
        return False

    issues = []
    with open(tsv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for line_num, row in enumerate(reader, start=2):
            sv = row.get("score_variance", "0").strip()
            conf = row.get("confidence", "0").strip()
            dim = row.get("dimension", "?").strip()
            it = row.get("iteration", "?").strip()

            try:
                variance = float(sv) if sv and sv != "—" else 0.0
            except ValueError:
                issues.append(f"行{line_num}: score_variance非数字: '{sv}'")
                continue

            try:
                confidence = float(conf.replace("%", "")) if conf and conf != "—" else 0.0
            except ValueError:
                issues.append(f"行{line_num}: confidence非数字: '{conf}'")
                continue

            if variance >= 2.0:
                issues.append(f"行{line_num} [iter={it}, dim={dim}]: 方差={variance} ≥ 2.0 → fail-closed")
            if confidence < 50 and confidence != 0:
                issues.append(f"行{line_num} [iter={it}, dim={dim}]: 置信度={confidence}% < 50% → fail-closed")
            if variance >= 2.0 and confidence >= 50:
                issues.append(f"行{line_num} [iter={it}, dim={dim}]: 方差≥2.0但置信度≥50%，数据矛盾")

    if issues:
        print(f"FAIL: {len(issues)}个问题")
        for issue in issues:
            print(f"  - {issue}")
        return False
    else:
        print("PASS: 所有行的方差和置信度合规")
        return True


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法:")
        print("  autoloop-variance.py compute <score1> <score2> [--evidence N]")
        print("  autoloop-variance.py check <tsv文件>")
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd == "compute" and len(sys.argv) >= 3:
        ok = cmd_compute(sys.argv[2:])
        sys.exit(0 if ok else 1)
    elif cmd == "check" and len(sys.argv) >= 3:
        ok = cmd_check(sys.argv[2])
        sys.exit(0 if ok else 1)
    else:
        print(f"未知命令: {cmd}")
        sys.exit(1)
