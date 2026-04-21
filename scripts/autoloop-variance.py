#!/usr/bin/env python3
"""AutoLoop scoring variance and confidence calculator."""

import sys
import os
import csv
import math


def compute_variance(scores):
    """Compute score variance."""
    n = len(scores)
    if n < 2:
        return 0.0
    mean = sum(scores) / n
    variance = sum((s - mean) ** 2 for s in scores) / (n - 1)
    return variance


def compute_confidence(variance, evidence_count):
    """Compute confidence from variance and evidence count."""
    if evidence_count == 0 or variance >= 2.0:
        return 30, "low", True  # fail-closed
    elif evidence_count >= 3 and variance < 1.0:
        return 85, "high", False
    elif evidence_count >= 1 and variance < 2.0:
        return 65, "medium", False
    else:
        return 30, "low", True


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
        print("ERROR: At least one score is required")
        return False

    mean = sum(scores) / len(scores)
    variance = compute_variance(scores)
    pct, level, fail_closed = compute_confidence(variance, evidence)

    status = "FAIL (fail-closed)" if fail_closed else "PASS"
    print(f"{status}: confidence={pct}% ({level})")
    print(f"  Mean: {mean:.2f}")
    print(f"  Variance: {variance:.4f}")
    print(f"  Evidence count: {evidence}")
    print(f"  Recommended score_variance: {variance:.2f}")
    print(f"  Recommended confidence: {pct}%")
    return not fail_closed


def cmd_check(tsv_path):
    """check <tsv file> - check variance and confidence for every row."""
    if not os.path.exists(tsv_path):
        print(f"ERROR: File does not exist: {tsv_path}")
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
                issues.append(f"Row {line_num}: score_variance is not numeric: '{sv}'")
                continue

            try:
                confidence = float(conf.replace("%", "")) if conf and conf != "—" else 0.0
            except ValueError:
                issues.append(f"Row {line_num}: confidence is not numeric: '{conf}'")
                continue

            if variance >= 2.0:
                issues.append(f"Row {line_num} [iter={it}, dim={dim}]: variance={variance} ≥ 2.0 → fail-closed")
            if confidence < 50 and confidence != 0:
                issues.append(f"Row {line_num} [iter={it}, dim={dim}]: confidence={confidence}% < 50% → fail-closed")
            if variance >= 2.0 and confidence >= 50:
                issues.append(f"Row {line_num} [iter={it}, dim={dim}]: variance≥2.0 but confidence≥50%, inconsistent data")

    if issues:
        print(f"FAIL: {len(issues)} issues")
        for issue in issues:
            print(f"  - {issue}")
        return False
    else:
        print("PASS: All rows satisfy variance and confidence requirements")
        return True


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:")
        print("  autoloop-variance.py compute <score1> <score2> [--evidence N]")
        print("  autoloop-variance.py check <tsv file>")
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd == "compute" and len(sys.argv) >= 3:
        ok = cmd_compute(sys.argv[2:])
        sys.exit(0 if ok else 1)
    elif cmd == "check" and len(sys.argv) >= 3:
        ok = cmd_check(sys.argv[2])
        sys.exit(0 if ok else 1)
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)
