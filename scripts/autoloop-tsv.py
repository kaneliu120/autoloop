#!/usr/bin/env python3
"""AutoLoop TSV read/write validation tool (15-column format)."""

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

STATUS_ENUM = ["Pass", "Fail", "Pending Check", "Pending Review"]

PHASES = [
    "OBSERVE", "ORIENT", "DECIDE", "ACT", "VERIFY",
    "SYNTHESIZE", "EVOLVE", "REFLECT",
    "scan", "generate", "compare", "baseline"
]


def validate_file(path):
    """Validate TSV file format."""
    if not os.path.exists(path):
        print(f"ERROR: File not found: {path}")
        return False

    errors = []
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.reader(f, delimiter="\t")
        header = next(reader, None)

        if header is None:
            print("ERROR: File is empty")
            return False

        # Validate column count.
        if len(header) != len(COLUMNS):
            errors.append(f"Header column count mismatch: expected {len(COLUMNS)}, got {len(header)}")
        else:
            for i, (expected, actual) in enumerate(zip(COLUMNS, header)):
                if expected != actual.strip():
                    errors.append(f"Column {i+1} name mismatch: expected '{expected}', got '{actual.strip()}'")

        # Validate data rows.
        for line_num, row in enumerate(reader, start=2):
            if len(row) != len(COLUMNS):
                errors.append(f"Line {line_num}: wrong column count ({len(row)} vs {len(COLUMNS)})")
                continue

            # `iteration` must be numeric.
            if row[0].strip() and not row[0].strip().isdigit():
                errors.append(f"Line {line_num}: iteration is not numeric: '{row[0].strip()}'")

            # `status` must be a valid enum value.
            status = row[2].strip()
            if status and status not in STATUS_ENUM:
                errors.append(f"Line {line_num}: invalid status '{status}', allowed values: {STATUS_ENUM}")

    if errors:
        print(f"FAIL: {len(errors)} errors")
        for e in errors:
            print(f"  - {e}")
        return False
    else:
        print("PASS: TSV format validation succeeded")
        return True


def write_header(path):
    """Create a TSV file and write the header."""
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, delimiter="\t")
        writer.writerow(COLUMNS)
    print(f"OK: Created TSV file ({len(COLUMNS)} columns): {path}")


def append_row(path, row_dict):
    """Append one validated row."""
    if not os.path.exists(path):
        print(f"ERROR: File not found: {path}")
        return False

    # Validate required fields.
    missing = [c for c in ["iteration", "phase", "status", "dimension"] if not row_dict.get(c)]
    if missing:
        print(f"ERROR: Missing required fields: {missing}")
        return False

    # Validate status enum.
    if row_dict.get("status") not in STATUS_ENUM:
        print(f"ERROR: Invalid status '{row_dict.get('status')}', allowed values: {STATUS_ENUM}")
        return False

    row = [row_dict.get(c, "—") for c in COLUMNS]
    with open(path, "a", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, delimiter="\t")
        writer.writerow(row)
    print(f"OK: Appended 1 row (iteration={row_dict.get('iteration')}, dimension={row_dict.get('dimension')})")
    return True


def read_summary(path):
    """Read the TSV file and print a summary."""
    if not os.path.exists(path):
        print(f"ERROR: File not found: {path}")
        return

    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        rows = list(reader)

    if not rows:
        print("TSV is empty (header only)")
        return

    iterations = set(r.get("iteration", "") for r in rows)
    dimensions = set(r.get("dimension", "") for r in rows)
    strategies = set(r.get("strategy_id", "") for r in rows if r.get("strategy_id") != "—")

    print(f"Total rows: {len(rows)}")
    print(f"Iterations: {sorted(iterations)}")
    print(f"Dimensions: {sorted(dimensions)}")
    print(f"Strategies: {sorted(strategies)}")

    # Scores for the latest iteration.
    max_iter = max(iterations)
    latest = [r for r in rows if r.get("iteration") == max_iter]
    print(f"\nLatest iteration (iteration={max_iter}):")
    for r in latest:
        print(f"  {r.get('dimension')}: {r.get('metric_value')} (delta={r.get('delta')}, strategy={r.get('strategy_id')})")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:")
        print("  autoloop-tsv.py validate <file>      Validate TSV format")
        print("  autoloop-tsv.py create <file>        Create TSV (write header)")
        print("  autoloop-tsv.py summary <file>       Read summary")
        print("  autoloop-tsv.py append <file> <json> Append one row (JSON)")
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
        print(f"Unknown command: {cmd}")
        sys.exit(1)
