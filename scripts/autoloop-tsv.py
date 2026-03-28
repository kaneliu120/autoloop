#!/usr/bin/env python3
"""AutoLoop TSV 读写校验工具（15列格式）"""

import csv
import sys
import os
from io import StringIO

COLUMNS = [
    "iteration", "phase", "status", "dimension", "metric_value",
    "delta", "strategy_id", "action_summary", "side_effect",
    "evidence_ref", "unit_id", "protocol_version", "score_variance",
    "confidence", "details"
]

STATUS_ENUM = ["通过", "未通过", "待检查", "待审查"]

PHASES = [
    "OBSERVE", "ORIENT", "DECIDE", "ACT", "VERIFY",
    "SYNTHESIZE", "EVOLVE", "REFLECT",
    "scan", "generate", "compare", "baseline"
]


def validate_file(path):
    """校验TSV文件格式"""
    if not os.path.exists(path):
        print(f"ERROR: 文件不存在: {path}")
        return False

    errors = []
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.reader(f, delimiter="\t")
        header = next(reader, None)

        if header is None:
            print("ERROR: 文件为空")
            return False

        # 校验列数
        if len(header) != len(COLUMNS):
            errors.append(f"表头列数错误: 期望{len(COLUMNS)}列, 实际{len(header)}列")
        else:
            for i, (expected, actual) in enumerate(zip(COLUMNS, header)):
                if expected != actual.strip():
                    errors.append(f"列{i+1}名称错误: 期望'{expected}', 实际'{actual.strip()}'")

        # 校验数据行
        for line_num, row in enumerate(reader, start=2):
            if len(row) != len(COLUMNS):
                errors.append(f"行{line_num}: 列数错误({len(row)}列, 期望{len(COLUMNS)})")
                continue

            # iteration 必须是数字
            if row[0].strip() and not row[0].strip().isdigit():
                errors.append(f"行{line_num}: iteration不是数字: '{row[0].strip()}'")

            # status 必须是枚举值
            status = row[2].strip()
            if status and status not in STATUS_ENUM:
                errors.append(f"行{line_num}: status非法: '{status}', 允许值: {STATUS_ENUM}")

    if errors:
        print(f"FAIL: {len(errors)}个错误")
        for e in errors:
            print(f"  - {e}")
        return False
    else:
        print("PASS: TSV格式校验通过")
        return True


def write_header(path):
    """创建TSV文件并写入表头"""
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, delimiter="\t")
        writer.writerow(COLUMNS)
    print(f"OK: 已创建TSV文件 ({len(COLUMNS)}列): {path}")


def append_row(path, row_dict):
    """追加一行数据（校验后写入）"""
    if not os.path.exists(path):
        print(f"ERROR: 文件不存在: {path}")
        return False

    # 校验必填字段
    missing = [c for c in ["iteration", "phase", "status", "dimension"] if not row_dict.get(c)]
    if missing:
        print(f"ERROR: 缺少必填字段: {missing}")
        return False

    # 校验status枚举
    if row_dict.get("status") not in STATUS_ENUM:
        print(f"ERROR: status非法: '{row_dict.get('status')}', 允许值: {STATUS_ENUM}")
        return False

    row = [row_dict.get(c, "—") for c in COLUMNS]
    with open(path, "a", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, delimiter="\t")
        writer.writerow(row)
    print(f"OK: 已追加1行 (iteration={row_dict.get('iteration')}, dimension={row_dict.get('dimension')})")
    return True


def read_summary(path):
    """读取TSV并输出摘要"""
    if not os.path.exists(path):
        print(f"ERROR: 文件不存在: {path}")
        return

    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        rows = list(reader)

    if not rows:
        print("TSV为空（只有表头）")
        return

    iterations = set(r.get("iteration", "") for r in rows)
    dimensions = set(r.get("dimension", "") for r in rows)
    strategies = set(r.get("strategy_id", "") for r in rows if r.get("strategy_id") != "—")

    print(f"总行数: {len(rows)}")
    print(f"轮次: {sorted(iterations)}")
    print(f"维度: {sorted(dimensions)}")
    print(f"策略: {sorted(strategies)}")

    # 最新一轮的各维度得分
    max_iter = max(iterations)
    latest = [r for r in rows if r.get("iteration") == max_iter]
    print(f"\n最新轮次 (iteration={max_iter}):")
    for r in latest:
        print(f"  {r.get('dimension')}: {r.get('metric_value')} (delta={r.get('delta')}, strategy={r.get('strategy_id')})")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法:")
        print("  autoloop-tsv.py validate <file>     校验TSV格式")
        print("  autoloop-tsv.py create <file>        创建TSV（写入表头）")
        print("  autoloop-tsv.py summary <file>       读取摘要")
        print("  autoloop-tsv.py append <file> <json>  追加一行（JSON格式）")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "validate" and len(sys.argv) >= 3:
        ok = validate_file(sys.argv[2])
        sys.exit(0 if ok else 1)
    elif cmd == "create" and len(sys.argv) >= 3:
        write_header(sys.argv[2])
    elif cmd == "summary" and len(sys.argv) >= 3:
        read_summary(sys.argv[2])
    elif cmd == "append" and len(sys.argv) >= 4:
        import json
        row = json.loads(sys.argv[3])
        ok = append_row(sys.argv[2], row)
        sys.exit(0 if ok else 1)
    else:
        print(f"未知命令: {cmd}")
        sys.exit(1)
