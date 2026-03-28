#!/usr/bin/env python3
"""AutoLoop 跨文件主键校验工具 — 校验4个输出文件的主键一致性"""

import csv
import os
import re
import sys

STRATEGY_RE = re.compile(r"^S\d{2}-.+$")
PROBLEM_RE = re.compile(r"^[A-Z]\d{3}$")
MULTI_STRATEGY_RE = re.compile(r"^multi:\{.+\}$")

FILES = {
    "results": "autoloop-results.tsv",
    "findings": "autoloop-findings.md",
    "progress": "autoloop-progress.md",
    "plan": "autoloop-plan.md",
}


def parse_tsv(path):
    """解析 results.tsv，返回行列表（dict）"""
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for i, row in enumerate(reader, start=2):
            row["_line"] = i
            rows.append(row)
    return rows


def extract_ids_from_findings(path):
    """从 findings.md 提取 problem_id 集合和 strategy_id 集合"""
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    problem_ids = set(re.findall(r"\b([A-Z]\d{3})\b", text))
    strategy_ids = set(re.findall(r"\b(S\d{2}-[\w-]+)", text))
    return problem_ids, strategy_ids


def extract_iterations_from_progress(path):
    """从 progress.md 标题中提取 iteration 编号集合"""
    iterations = set()
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if line.startswith("#"):
                nums = re.findall(r"(?:iteration|轮次|第)\s*(\d+)", line, re.IGNORECASE)
                iterations.update(nums)
    return iterations


def extract_dimensions_from_gates(work_dir):
    """尝试从 plan.md 或 quality-gates.md 提取维度名"""
    dims = set()
    for name in ("autoloop-plan.md", "quality-gates.md"):
        p = os.path.join(work_dir, name)
        if not os.path.exists(p):
            continue
        with open(p, "r", encoding="utf-8") as f:
            for line in f:
                m = re.match(r"^\|\s*(.+?)\s*\|.*\d+%", line)
                if m:
                    dim = m.group(1).strip()
                    if dim and dim != "维度":
                        dims.add(dim)
    return dims


def validate(work_dir):
    """执行全部跨文件主键校验，返回错误列表"""
    errors = []
    missing = []
    for key, fname in FILES.items():
        if not os.path.exists(os.path.join(work_dir, fname)):
            missing.append(fname)
    if missing:
        return [f"缺少文件: {', '.join(missing)}"]

    tsv_rows = parse_tsv(os.path.join(work_dir, FILES["results"]))
    f_problems, f_strategies = extract_ids_from_findings(
        os.path.join(work_dir, FILES["findings"])
    )
    p_iterations = extract_iterations_from_progress(
        os.path.join(work_dir, FILES["progress"])
    )
    known_dims = extract_dimensions_from_gates(work_dir)

    for row in tsv_rows:
        ln = row["_line"]
        sid = row.get("strategy_id", "").strip()
        evi = row.get("evidence_ref", "").strip()
        it = row.get("iteration", "").strip()
        dim = row.get("dimension", "").strip()

        # strategy_id 格式校验
        if sid and sid not in ("—", "baseline"):
            if not STRATEGY_RE.match(sid) and not MULTI_STRATEGY_RE.match(sid):
                errors.append(
                    f"行{ln}: strategy_id 格式错误: '{sid}' (期望 S{{NN}}-{{描述}})"
                )
            elif STRATEGY_RE.match(sid) and sid not in f_strategies:
                errors.append(f"行{ln}: strategy_id '{sid}' 在 findings.md 中未定义")

        # evidence_ref → problem_id 存在性
        if evi and evi != "—":
            for pid in re.findall(r"[A-Z]\d{3}", evi):
                if pid not in f_problems:
                    errors.append(
                        f"行{ln}: evidence_ref 引用的 '{pid}' 在 findings.md 中未定义"
                    )

        # iteration 存在性
        if it and it.isdigit() and p_iterations and it not in p_iterations:
            errors.append(
                f"行{ln}: iteration {it} 在 progress.md 标题中无对应轮次记录"
            )

        # dimension 一致性
        if dim and dim not in ("—", "score") and known_dims and dim not in known_dims:
            errors.append(
                f"行{ln}: dimension '{dim}' 不在已知维度集合中"
                f" ({', '.join(sorted(known_dims))})"
            )

    return errors


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: autoloop-validate.py <工作目录>")
        print("  校验 autoloop 4个输出文件的跨文件主键一致性")
        sys.exit(1)

    work_dir = sys.argv[1]
    if not os.path.isdir(work_dir):
        print(f"ERROR: 目录不存在: {work_dir}")
        sys.exit(1)

    errs = validate(work_dir)
    if errs:
        print(f"FAIL: {len(errs)} 个跨文件一致性错误")
        for e in errs:
            print(f"  - {e}")
        sys.exit(1)
    else:
        print("PASS: 跨文件主键校验全部通过")
        sys.exit(0)
