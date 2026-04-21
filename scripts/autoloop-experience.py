#!/usr/bin/env python3
"""AutoLoop experience registry read/write tool

Usage:
  autoloop-experience.py <work_dir> query --template T{N} [--tags tag1,tag2] [--include-global]
  autoloop-experience.py <work_dir> write --strategy-id S01-xxx --effect Keep|Avoid|To Validate --score DELTA [--mechanism "brief mechanism description"] [--failure-lesson "what:...|why:...|instead:..."] [--status Recommended|Candidate Default|Observation|Deprecated] [--template T{N}] [--dimension dim] [--context "..."] [--tags python,backend,security] [--templates "T1,T2" | "*"]
  : --score single-round score delta(delta), . avg_delta =  write  score (and experience-registry ).
  Optional env var AUTOLOOP_EXPERIENCE_REQUIRE_MECHANISM=1: when use_count≥2, require --mechanism on this write (tightens D-03).
  autoloop-experience.py <work_dir> list
  autoloop-experience.py <work_dir> list --json
  autoloop-experience.py <work_dir> audit [--dry-run]          # P2-05: audit strategy statuses and suggest promotion/deprecation
  autoloop-experience.py <work_dir> consolidate [--dry-run]   # P3-01: merge duplicate strategy_id rows in the main table into one row
  autoloop-experience.py <work_dir> evolve-profile --role ROLE --field FIELD --value VALUE --reason REASON  # P2-08: update the evolution section of an agent profile
  Main table: only one row is kept per strategy_id (write is an upsert). Audit entries are appended to references/experience-audit.md.
  strategy_id  multi: , update;  P3-06 multi:{SNN+SNN} (see experience-registry.md).
"""

import json
import os
import re
import sys
import datetime

_scripts_dir = os.path.dirname(os.path.abspath(__file__))
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)
from autoloop_strategy_multi import (  # noqa: E402
    is_multi_strategy_id,
    validate_multi_strategy_id,
)

# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------

def _find_registry(work_dir):
    """Find experience-registry.md.

    priority:
    1. ../references/experience-registry.md next to the script
    2. references/experience-registry.md in work_dir's parent directory
    """
    script_dir = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(script_dir, "..", "references", "experience-registry.md"),
        os.path.join(work_dir, "..", "references", "experience-registry.md"),
        os.path.join(work_dir, "references", "experience-registry.md"),
    ]
    for c in candidates:
        path = os.path.normpath(c)
        if os.path.isfile(path):
            return path
    return None


# ---------------------------------------------------------------------------
# Table Parsing
# ---------------------------------------------------------------------------

_TABLE_HEADER_RE = re.compile(
    r'^\|\s*strategy_id\s*\|.*status\s*\|',
    re.IGNORECASE | re.MULTILINE,
)


def _parse_strategy_table(content):
    """Parse the global strategy-effect library table and return list[dict]."""
    match = _TABLE_HEADER_RE.search(content)
    if not match:
        return []

    # Extract the header
    header_line = content[match.start():content.index('\n', match.start())]
    headers = [h.strip() for h in header_line.strip().strip('|').split('|')]

    # Skip the separator row
    rest = content[content.index('\n', match.start()) + 1:]
    lines = rest.split('\n')
    if lines and re.match(r'^\|[\s\-:|]+\|$', lines[0].strip()):
        lines = lines[1:]

    strategies = []
    for line in lines:
        line = line.strip()
        if not line.startswith('|'):
            break
        cells = [c.strip() for c in line.strip().strip('|').split('|')]
        if len(cells) < len(headers):
            cells.extend([''] * (len(headers) - len(cells)))

        row = {}
        for i, h in enumerate(headers):
            row[h] = cells[i] if i < len(cells) else ''

        # Skip placeholder rows
        sid = row.get('strategy_id', '')
        if not sid or sid.startswith('(') or sid.startswith('('):
            continue

        strategies.append(row)

    return strategies


def _parse_context_scoped_table(content):
    """Parse the context-scoped status supplement table if it exists."""
    marker = re.search(
        r'^\|\s*strategy_id\s*\|\s*context_tags\s*\|\s*status\s*\|',
        content, re.IGNORECASE | re.MULTILINE,
    )
    if not marker:
        return []

    header_line = content[marker.start():content.index('\n', marker.start())]
    headers = [h.strip() for h in header_line.strip().strip('|').split('|')]

    rest = content[content.index('\n', marker.start()) + 1:]
    lines = rest.split('\n')
    if lines and re.match(r'^\|[\s\-:|]+\|$', lines[0].strip()):
        lines = lines[1:]

    rows = []
    for line in lines:
        line = line.strip()
        if not line.startswith('|'):
            break
        cells = [c.strip() for c in line.strip().strip('|').split('|')]
        row = {}
        for i, h in enumerate(headers):
            row[h] = cells[i] if i < len(cells) else ''
        if row.get('strategy_id'):
            rows.append(row)
    return rows


# ---------------------------------------------------------------------------
# P3-01 Main table + audit (aggregate single row / experience-audit.md)
# ---------------------------------------------------------------------------

_AUDIT_BASENAME = "experience-audit.md"


def _audit_path(registry_path):
    return os.path.join(os.path.dirname(os.path.abspath(registry_path)), _AUDIT_BASENAME)


def _audit_write_scores_chronological(audit_path, strategy_id):
    """Before appending this write, collect prior `write` audit scores for this strategy_id in chronological order."""
    if not audit_path or not os.path.isfile(audit_path):
        return []
    with open(audit_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    out = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.strip().startswith("###"):
            rest = line.strip()[3:].strip()
            segs = [s.strip() for s in rest.split("|")]
            if len(segs) >= 3 and segs[1] == "write" and segs[2] == strategy_id:
                j = i + 1
                while j < len(lines) and not lines[j].strip().startswith("###"):
                    mm = re.match(r"-\s*score:\s*(\S+)", lines[j].strip())
                    if mm:
                        try:
                            out.append(float(mm.group(1)))
                        except ValueError:
                            out.append(0.0)
                        break
                    j += 1
        i += 1
    return out


def _stats_from_round_scores(scores):
    """Compute use_count, avg_delta, and success_rate from single-round deltas (--score), matching registry field semantics."""
    if not scores:
        return None
    uc = len(scores)
    pos_n = sum(1 for s in scores if s > 0)
    ad = sum(scores) / uc
    return {
        "use_count": uc,
        "avg_delta": ad,
        "success_rate": "{:.0f}%".format(pos_n / uc * 100),
        "total_positive_count": pos_n,
        "positives": [s > 0 for s in scores],
    }


def _format_avg_delta_for_cell(avg_delta):
    """Display format for the main-table avg_delta column (consistent with cmd_write)."""
    ad = avg_delta
    if isinstance(ad, float) and ad == int(ad):
        return str(int(ad))
    if isinstance(ad, float):
        return "{:.4g}".format(ad)
    return str(ad)


def _append_audit(registry_path, strategy_id, action, payload_lines):
    """Append an audit block(Markdown).payload_lines: list of \"- key: value\" ."""
    ap = _audit_path(registry_path)
    now = datetime.datetime.now().isoformat(timespec="seconds")
    block = "\n### {} | {} | {}\n\n".format(now, action, strategy_id)
    block += "\n".join(payload_lines) + "\n"
    if not os.path.isfile(ap):
        head = (
            "# Experience audit log\n\n"
            "> Append one entry for each write/consolidate; the main table in experience-registry.md keeps only the current effective row (one row per strategy_id).\n\n"
        )
        with open(ap, "w", encoding="utf-8") as f:
            f.write(head)
    with open(ap, "a", encoding="utf-8") as f:
        f.write(block)


def _split_main_strategy_table(content):
    """Split out the main strategy table: prefix, header_line, sep_line, row_line_strs, suffix."""
    match = _TABLE_HEADER_RE.search(content)
    if not match:
        return None
    start = match.start()
    prefix = content[:start]
    rest = content[start:]
    lines = rest.split("\n")
    if not lines:
        return None
    header_line = lines[0]
    i = 1
    sep_line = ""
    if i < len(lines) and re.match(r"^\|[\s\-:|]+\|$", lines[i].strip()):
        sep_line = lines[i]
        i += 1
    row_lines = []
    while i < len(lines):
        line = lines[i]
        if not line.strip().startswith("|"):
            break
        row_lines.append(line)
        i += 1
    suffix = "\n".join(lines[i:])
    return prefix, header_line, sep_line, row_lines, suffix


def _headers_from_line(header_line):
    return [h.strip() for h in header_line.strip().strip("|").split("|")]


def _row_dict_from_line(headers, line):
    cells = [c.strip() for c in line.strip().strip("|").split("|")]
    row = {}
    for hi, h in enumerate(headers):
        row[h] = cells[hi] if hi < len(cells) else ""
    return row


def _format_row_line(headers, row):
    parts = [str(row.get(h, "")) for h in headers]
    return "| " + " | ".join(parts) + " |"


def _rebuild_table_content(prefix, header_line, sep_line, row_dicts, headers, suffix):
    lines = [prefix.rstrip("\n"), header_line]
    if sep_line:
        lines.append(sep_line)
    for r in row_dicts:
        lines.append(_format_row_line(headers, r))
    body = "\n".join(lines)
    if suffix:
        if not suffix.startswith("\n"):
            body += "\n"
        body += suffix
    return body


def _dedupe_strategies_latest(strategies):
    """When the same strategy_id has multiple rows, keep the last row in the file(and upsert )."""
    seen = {}
    for s in strategies:
        sid = s.get("strategy_id", "")
        if not sid or sid.startswith("(") or sid.startswith("("):
            continue
        seen[sid] = s
    return list(seen.values())


def _row_positive_signal(row):
    """write( success_rate)."""
    desc = str(row.get("description", ""))
    if "[Keep]" in desc:
        return True
    if "[Avoid]" in desc:
        return False
    try:
        return float(str(row.get("avg_delta", "—")).replace("—", "0")) > 0
    except (ValueError, TypeError):
        return False


def _merge_history_rows(
    historical, effect, score, context, dim_str, tags, now_str, prior_scores=None,
    mechanism=None, failure_lesson=None, applicable_templates=None,
):
    """Use existing audit scores plus the current score to compute use_count, avg_delta, success_rate, and description.

    prior_scores: write audit Time delta ;  upsert must, 
     use_count  2.
    applicable_templates: applicable template list( ['T1','T2'] or ['*']), write [templates: ...] .
    """
    parts = ["[{}]".format(effect), "@{}".format(now_str)]
    if tags:
        parts.append("[{}]".format(",".join(tags)))
    if applicable_templates:
        parts.append("[templates: {}]".format(",".join(applicable_templates)))
    if mechanism:
        parts.append("[mechanism: {}]".format(str(mechanism).strip()))
    if failure_lesson:
        parts.append("[failure_lesson: {}]".format(str(failure_lesson).strip()))
    if context:
        parts.append(context)
    desc = " ".join(parts)

    try:
        score_val = float(score)
    except (ValueError, TypeError):
        score_val = 0.0

    if prior_scores is not None:
        deltas = list(prior_scores) + [score_val]
    else:
        deltas = []
        for s in historical:
            try:
                deltas.append(float(str(s.get("avg_delta", "0")).replace("—", "0")))
            except (ValueError, TypeError):
                pass
        deltas.append(score_val)

    st = _stats_from_round_scores(deltas)
    if st is None:
        st = _stats_from_round_scores([score_val])
    use_count = st["use_count"]
    positives = st["positives"]
    total_positive_count = st["total_positive_count"]
    success_rate = st["success_rate"]
    avg_delta = st["avg_delta"]
    current_positive = score_val > 0

    last_st = "Observation"
    if historical:
        st = historical[-1].get("status", "Observation")
        if st in ("Recommended", "Candidate Default", "Observation", "Deprecated"):
            last_st = st

    return {
        "positives": positives,
        "deltas": deltas,
        "use_count": use_count,
        "success_rate": success_rate,
        "avg_delta": avg_delta,
        "description": desc,
        "last_status": last_st,
        "total_positive_count": total_positive_count,
        "current_positive": current_positive,
    }


def cmd_consolidate(registry_path, dry_run=False):
    """Merge duplicate strategy_id rows into one row.

    Prefer recomputing use_count / avg_delta / success_rate from audit write scores.
    If audit history is unavailable, fall back to averaging row avg_delta values.
    """
    with open(registry_path, "r", encoding="utf-8") as f:
        content = f.read()
    split = _split_main_strategy_table(content)
    if not split:
        print("ERROR: Strategy-effect library table not found", file=sys.stderr)
        return False
    prefix, header_line, sep_line, row_lines, suffix = split
    headers = _headers_from_line(header_line)
    rows = []
    for rl in row_lines:
        d = _row_dict_from_line(headers, rl)
        sid = d.get("strategy_id", "")
        if sid and not sid.startswith("(") and not sid.startswith("("):
            rows.append(d)

    by_sid = {}
    order = []
    for r in rows:
        sid = r["strategy_id"]
        if sid not in by_sid:
            order.append(sid)
            by_sid[sid] = []
        by_sid[sid].append(r)

    new_rows = []
    merged_any = False
    for sid in order:
        group = by_sid[sid]
        if len(group) == 1:
            new_rows.append(group[0])
            continue
        merged_any = True
        last = group[-1]
        merged = dict(last)
        ap = _audit_path(registry_path)
        audit_scores = _audit_write_scores_chronological(ap, sid)
        stat = _stats_from_round_scores(audit_scores)
        if stat:
            merged["use_count"] = str(stat["use_count"])
            merged["success_rate"] = stat["success_rate"]
            merged["avg_delta"] = _format_avg_delta_for_cell(stat["avg_delta"])
        else:
            positives = [_row_positive_signal(x) for x in group]
            row_avgs = []
            for x in group:
                try:
                    row_avgs.append(float(str(x.get("avg_delta", "0")).replace("—", "0")))
                except (ValueError, TypeError):
                    pass
            use_count = len(group)
            tp = sum(1 for p in positives if p)
            success_rate = "{:.0f}%".format(tp / use_count * 100) if use_count else "0%"
            avg_delta = sum(row_avgs) / len(row_avgs) if row_avgs else 0.0
            merged["use_count"] = str(use_count)
            merged["success_rate"] = success_rate
            merged["avg_delta"] = _format_avg_delta_for_cell(avg_delta)
        new_rows.append(merged)

    if not merged_any:
        print("OK: No duplicate strategy_id values in the main table; skipping")
        return True

    new_content = _rebuild_table_content(
        prefix, header_line, sep_line, new_rows, headers, suffix
    )
    if dry_run:
        print("DRY-RUN: Would merge {} strategy_id values into {} rows".format(len(rows), len(new_rows)))
        return True

    with open(registry_path, "w", encoding="utf-8") as f:
        f.write(new_content)
    _append_audit(
        registry_path,
        "(batch)",
        "consolidate",
        [
            "- merged_duplicate_rows: true",
            "- before_row_count: {}".format(len(rows)),
            "- after_row_count: {}".format(len(new_rows)),
        ],
    )
    print("OK: Merged duplicate strategy_id values into {} rows; audit recorded".format(len(new_rows)))
    return True


# ---------------------------------------------------------------------------
# query  — context_tags and loop-protocol / experience-registry (P3-02)
# ---------------------------------------------------------------------------

_EFFECT_BRACKETS = frozenset({'Keep', 'Avoid', 'To Validate'})


def _normalize_tag_set(tags):
    """Lowercase and strip whitespace for overlap and set comparisons."""
    if not tags:
        return frozenset()
    out = set()
    for t in tags:
        if t is None:
            continue
        s = str(t).strip().lower()
        if s:
            out.add(s)
    return frozenset(out)


def _extract_context_tags_from_description(desc):
    """Extract the fragment written by --tags from description during write([Keep] @YYYY-MM-DD [tag1,tag2])."""
    if not desc:
        return []
    desc = str(desc)
    m = re.search(r'@\d{4}-\d{2}-\d{2}\s+\[([^\]]+)\]', desc)
    if m:
        inner = m.group(1).strip()
        if inner and inner not in _EFFECT_BRACKETS:
            return _parse_tags(inner)
    for m in re.finditer(r'\[([^\]]+)\]', desc):
        inner = m.group(1).strip()
        if inner in _EFFECT_BRACKETS:
            continue
        if ',' in inner:
            return _parse_tags(inner)
    return []


def _resolve_scoped_status(strategy_id, global_status, scoped_rows, task_tag_set):
    """Context-scoped supplement table: Exact match > task tags are a superset of row tags (choose the row with the most tags) > global."""
    global_status = global_status or 'To Validate'
    if not task_tag_set:
        return global_status
    rows = [r for r in scoped_rows if r.get('strategy_id') == strategy_id]
    if not rows:
        return global_status
    best_pri = -1
    best_len = -1
    chosen = global_status
    for r in rows:
        rt = _normalize_tag_set(_parse_tags(r.get('context_tags', '')))
        if not rt:
            continue
        if task_tag_set == rt:
            pri, ln = 2, len(rt)
        elif task_tag_set >= rt:
            pri, ln = 1, len(rt)
        else:
            continue
        if pri > best_pri or (pri == best_pri and ln > best_len):
            best_pri, best_len = pri, ln
            st = r.get('status', '')
            if st:
                chosen = st
    return chosen


def _extract_applicable_templates(desc):
    """ description extract [templates: ...] , return the template set (uppercase).
    [templates: *] Returns frozenset({'*'}); [templates: T1,T3] Returns frozenset({'T1','T3'}).
    If no fragment exists, return None (meaning unset, so the row template field is used by default).
    """
    if not desc:
        return None
    m = re.search(r'\[templates:\s*([^\]]+)\]', str(desc))
    if not m:
        return None
    raw = m.group(1).strip()
    if raw == '*':
        return frozenset({'*'})
    return frozenset(t.strip().upper() for t in raw.split(',') if t.strip())


def cmd_query(registry_path, template, tags, include_observation=False,
              include_global=False):
    """Query recommended strategies: filter by template; if task context_tags are provided, keep only strategies whose
    description has context_tags overlap >=2 (loop-protocol); when tags are absent, do not filter by overlap (cold start).

    include_global=True , Besides same-template rows, also return rows whose applicable_templates include the current template or [*].

    By default only return effective_status values Recommended or Candidate Default; Observation requires --include-observation.
    """
    with open(registry_path, 'r', encoding='utf-8') as f:
        content = f.read()

    strategies = _dedupe_strategies_latest(_parse_strategy_table(content))
    scoped = _parse_context_scoped_table(content)
    task_tag_set = _normalize_tag_set(tags)

    # Normalize template matching(T1, t1, T1: Research  T1)
    tpl_key = template.upper().split(':')[0].split(' ')[0].strip() if template else None

    results = []
    for s in strategies:
        # Template filtering (including cross-template applicable_templates matching)
        s_tpl = s.get('template', '').upper().split(':')[0].split(' ')[0].strip()
        tpl_match = (not tpl_key) or s_tpl == tpl_key or s_tpl == 'General'
        if not tpl_match and include_global:
            at = _extract_applicable_templates(s.get('description', ''))
            if at is not None and ('*' in at or (tpl_key and tpl_key in at)):
                tpl_match = True
        if not tpl_match:
            continue

        strategy_tags = _extract_context_tags_from_description(s.get('description', ''))
        strategy_tag_set = _normalize_tag_set(strategy_tags)
        if task_tag_set:
            if len(task_tag_set & strategy_tag_set) < 2:
                continue

        effective_status = _resolve_scoped_status(
            s.get('strategy_id', ''), s.get('status', 'To Validate'), scoped, task_tag_set,
        )

        allowed = ('Recommended', 'Candidate Default', 'Observation') if include_observation else ('Recommended', 'Candidate Default')
        if effective_status in allowed:
            entry = dict(s)
            entry['effective_status'] = effective_status
            results.append(entry)

    # Time + success_rate (experience-registry.md §time-decay mechanism)
    today = datetime.datetime.now().date()

    def sort_key(item):
        try:
            base_rate = float(item.get('success_rate', '0').rstrip('%'))
        except (ValueError, AttributeError):
            base_rate = 0.0

        # Extract the @YYYY-MM-DD date from description
        desc = item.get('description', '')
        decay = 1.0
        date_match = re.search(r'@(\d{4}-\d{2}-\d{2})', desc)
        if date_match:
            try:
                last_date = datetime.datetime.strptime(
                    date_match.group(1), '%Y-%m-%d').date()
                days_ago = (today - last_date).days
                if days_ago <= 30:
                    decay = 1.0
                elif days_ago <= 60:
                    decay = 0.8
                elif days_ago <= 90:
                    decay = 0.5
                else:
                    decay = 0.2  # >90d severely decayed
                    # automatic downgrade note
                    if item.get('effective_status') == 'Recommended':
                        item['effective_status'] = 'Observation'
                        item['_decay_note'] = f'>90d without validation; automatically downgraded to Observation'
            except ValueError:
                pass

        return base_rate * decay

    results.sort(key=sort_key, reverse=True)

    # Persist >90d automatic downgrades (write back to the registry file)
    downgraded = [r for r in results if r.get('_decay_note')]
    if downgraded:
        with open(registry_path, 'r', encoding='utf-8') as f:
            file_content = f.read()
        modified = False
        for r in downgraded:
            sid = r.get('strategy_id', '')
            # Find the strategy row in the file and replace Recommended with Observation
            old_pattern = f"| {sid} |"
            if old_pattern in file_content:
                lines = file_content.split('\n')
                for idx, line in enumerate(lines):
                    if old_pattern in line and '| Recommended |' in line:
                        lines[idx] = line.replace('| Recommended |', '| Observation |', 1)
                        modified = True
                        print(f"DECAY_DOWNGRADE: {sid} Recommended→Observation ({r['_decay_note']})")
                file_content = '\n'.join(lines)
        if modified:
            with open(registry_path, 'w', encoding='utf-8') as f:
                f.write(file_content)

    # Decay may change Recommended to Observation during sorting; query should not return Observation by default(and loop-protocol / P0-03)
    if not include_observation:
        results = [r for r in results if r.get("effective_status") != "Observation"]

    return results


def _parse_tags(raw):
    """Parse a tags string into a list. Supports [a, b] and a,b formats."""
    if not raw:
        return []
    raw = raw.strip().strip('[]')
    return [t.strip() for t in raw.split(',') if t.strip()]


# ---------------------------------------------------------------------------
# write 
# ---------------------------------------------------------------------------

# Valid template prefixes
_VALID_TEMPLATES = {'T1', 'T2', 'T3', 'T4', 'T5', 'T6', 'T7', 'T8'}


def _infer_template(strategy_id):
    """Infer applicable templates from strategy_id.

    Rules:
    1. 1. If strategy_id contains a T{N} fragment (for example S15-T5-xxx), extract that template
    2. 2. A C{NN} prefix (combined strategy) -> 'General'
    3. 3. If inference is impossible -> 'General'
    """
    parts = strategy_id.upper().replace('_', '-').split('-')
    for part in parts:
        if part in _VALID_TEMPLATES:
            return part
    # Combined strategy or cannot infer
    return 'General'


def cmd_write(registry_path, strategy_id, effect, score, context,
              status=None, template=None, dimension=None, tags=None, mechanism=None,
              failure_lesson=None, applicable_templates=None):
    """Main-table upsert (one row per strategy_id) and append to experience-audit.md.

    For multi strategy IDs, write to experience-audit.md only; do not update the
    main table aggregate.
    applicable_templates: optional template list (['T1','T2'] or ['*']); appended
    to the description as [templates: ...].
    """
    valid_statuses = ('Recommended', 'Candidate Default', 'Observation', 'Deprecated')
    if status is not None and status not in valid_statuses:
        print("ERROR: --status must be {}".format("|".join(valid_statuses)), file=sys.stderr)
        return False

    user_status = status
    if is_multi_strategy_id(strategy_id) and user_status is not None:
        print(
            "ERROR: multi strategy IDs cannot use --status",
            file=sys.stderr,
        )
        return False

    if user_status is not None and user_status in ('Recommended', 'Candidate Default'):
        print(
            "WARN: explicit status={} overrides automatic promotion and validation".format(user_status),
            file=sys.stderr,
        )

    try:
        score_val = float(score)
        if abs(score_val) > 10:
            print(
                "WARN: --score={} looks like an absolute score rather than a delta.".format(score),
                file=sys.stderr,
            )
    except (ValueError, TypeError):
        pass

    now = datetime.datetime.now().strftime('%Y-%m-%d')
    if is_multi_strategy_id(strategy_id):
        ok_m, err_m = validate_multi_strategy_id(strategy_id)
        if not ok_m:
            print("ERROR: {}".format(err_m), file=sys.stderr)
            return False
        parts = ["[{}]".format(effect), "@{}".format(now)]
        if tags:
            parts.append("[{}]".format(",".join(tags)))
        if context:
            parts.append(context)
        desc = " ".join(parts)
        _append_audit(
            registry_path,
            strategy_id,
            "write_multi_reference",
            [
                "- effect: {}".format(effect),
                "- score: {}".format(score),
                "- description: {}".format(desc),
                "- note: Do not update the main table (mixed attribution)",
            ],
        )
        print("OK: wrote multi-strategy entry")
        return True

    with open(registry_path, "r", encoding="utf-8") as f:
        content = f.read()

    split = _split_main_strategy_table(content)
    if not split:
        print("ERROR: Strategy-effect library table not found", file=sys.stderr)
        return False
    prefix, header_line, sep_line, row_lines, suffix = split
    headers = _headers_from_line(header_line)
    rows = []
    for rl in row_lines:
        d = _row_dict_from_line(headers, rl)
        sid = d.get("strategy_id", "")
        if sid and not sid.startswith("(") and not sid.startswith("("):
            rows.append(d)

    historical = [r for r in rows if r.get("strategy_id") == strategy_id]
    other_rows = [r for r in rows if r.get("strategy_id") != strategy_id]

    if not template:
        template = _infer_template(strategy_id)
    dim_str = dimension or "—"

    ap = _audit_path(registry_path)
    prior_scores = _audit_write_scores_chronological(ap, strategy_id)
    m = _merge_history_rows(
        historical, effect, score, context, dim_str, tags, now, prior_scores=prior_scores,
        mechanism=mechanism, failure_lesson=failure_lesson,
        applicable_templates=applicable_templates,
    )
    use_count = m["use_count"]
    positives = m["positives"]
    total_positive_count = m["total_positive_count"]
    success_rate = m["success_rate"]
    desc = m["description"]
    avg_delta = m["avg_delta"]

    if historical:
        ls = historical[-1].get("status", "Observation")
        existing_status = ls if ls in valid_statuses else "Observation"
    else:
        existing_status = "Observation"

    try:
        d_curr = float(score)
    except (ValueError, TypeError):
        d_curr = 0.0

    prev_score = prior_scores[-1] if prior_scores else None

    confidence = "Low" if use_count == 1 else ("Medium" if use_count <= 3 else "High")
    promoted = False

    if user_status is not None:
        status = user_status
    else:
        status = existing_status
        if use_count >= 2:
            if prev_score is not None:
                last_two_pos = prev_score > 0 and d_curr > 0
                last_two_nonpos = prev_score <= 0 and d_curr <= 0
            else:
                last_two_pos = (
                    len(positives) >= 2 and positives[-2] and positives[-1]
                )
                last_two_nonpos = (
                    len(positives) >= 2
                    and (not positives[-2])
                    and (not positives[-1])
                )

            if last_two_nonpos and existing_status != "Deprecated":
                status = "Deprecated"
                promoted = True
                print(
                    "AUTO_DEPRECATION: Strategy {} {}→Deprecated "
                    "(2 deltas<=0, use_count={})".format(
                        strategy_id, existing_status, use_count
                    )
                )
            elif existing_status == "Deprecated" and d_curr > 0:
                status = "Observation"
                promoted = True
                print(
                    "AUTO_RECOVERY: Strategy {} Deprecated→Observation "
                    "(delta>0, use_count={})".format(strategy_id, use_count)
                )
            elif existing_status == "Observation" and last_two_pos and confidence in ("Medium", "High"):
                status = "Recommended"
                promoted = True
                print(
                    "AUTO_PROMOTION: Strategy {} Observation→Recommended "
                    "(use_count={}, last 2 deltas>0, confidence={})".format(
                        strategy_id, use_count, confidence
                    )
                )
            elif existing_status == "Recommended" and use_count >= 4 and confidence == "High":
                if total_positive_count / use_count >= 0.8:
                    status = "Candidate Default"
                    promoted = True
                    print(
                        "AUTO_PROMOTION: Strategy {} Recommended→Candidate Default "
                        "(use_count={}, success_rate={})".format(
                            strategy_id, use_count, success_rate
                        )
                    )
            elif existing_status in ("Recommended", "Candidate Default") and not promoted:
                status = existing_status

    require_mech = os.environ.get("AUTOLOOP_EXPERIENCE_REQUIRE_MECHANISM", "").strip().lower() in (
        "1", "true", "yes",
    )
    if require_mech and use_count >= 2:
        if not (mechanism and str(mechanism).strip()):
            print(
                "ERROR: AUTOLOOP_EXPERIENCE_REQUIRE_MECHANISM=1 and use_count≥2 requires a non-empty --mechanism",
                file=sys.stderr,
            )
            return False

    # Only warn once when use_count first reaches 2, to avoid repeated write spam( D-03)
    if use_count == 2:
        print(
            "WARN: Strategy {} reached use_count=2 — review experience-registry.md description quality and "
            "add medium-confidence supplemental details under /items/ (registry use_count>=2)".format(
                strategy_id,
            ),
            file=sys.stderr,
        )

    row_out = {h: "" for h in headers}
    ad_str = _format_avg_delta_for_cell(avg_delta)
    row_out.update({
        "strategy_id": strategy_id,
        "template": template,
        "dimension": dim_str,
        "description": desc,
        "avg_delta": ad_str,
        "side_effects": "—",
        "use_count": str(use_count),
        "success_rate": success_rate,
        "status": status,
    })

    order = []
    seen = set()
    for r in rows:
        s = r.get("strategy_id")
        if s and s not in seen:
            seen.add(s)
            order.append(s)
    if strategy_id not in seen:
        order.append(strategy_id)

    by_sid = {r["strategy_id"]: r for r in other_rows}
    by_sid[strategy_id] = row_out
    new_rows = [by_sid[s] for s in order if s in by_sid]

    new_content = _rebuild_table_content(
        prefix, header_line, sep_line, new_rows, headers, suffix
    )

    with open(registry_path, "w", encoding="utf-8") as f:
        f.write(new_content)

    _append_audit(
        registry_path,
        strategy_id,
        "write",
        [
            "- effect: {}".format(effect),
            "- score: {}".format(score),
            "- use_count_after: {}".format(use_count),
            "- success_rate: {}".format(success_rate),
            "- status_after: {}".format(status),
            "- avg_delta: {}".format(ad_str),
            "- description: {}".format(desc),
        ],
    )

    if not promoted and use_count >= 3 and status == "Observation":
        print(
            "PROMOTION_HINT: Strategy {} has accumulated {} uses(confidence={}), "
            "automatic promotion requires the last two deltas > 0 with confidence >= Medium".format(
                strategy_id, use_count, confidence
            )
        )

    return True


# ---------------------------------------------------------------------------
# list 
# ---------------------------------------------------------------------------

def cmd_list(registry_path):
    """StrategyStatus( strategy_id )."""
    with open(registry_path, "r", encoding="utf-8") as f:
        content = f.read()
    return _dedupe_strategies_latest(_parse_strategy_table(content))


# ---------------------------------------------------------------------------
# audit  — P2-05 continuous learning loop
# ---------------------------------------------------------------------------

def _extract_last_date(desc):
    """Extract the last @YYYY-MM-DD token from a description and return datetime.date or None."""
    matches = re.findall(r'@(\d{4}-\d{2}-\d{2})', str(desc))
    if not matches:
        return None
    try:
        return datetime.datetime.strptime(matches[-1], '%Y-%m-%d').date()
    except ValueError:
        return None


def cmd_audit(registry_path, dry_run=True):
    """items,  use_count/success_rate/avg_delta Recommendationor.

    ReturnsRecommendation list[dict],  strategy_id / current_status / action / reason.
    dry_run=True ; False record experience-audit.md.
    """
    with open(registry_path, "r", encoding="utf-8") as f:
        content = f.read()

    strategies = _dedupe_strategies_latest(_parse_strategy_table(content))
    today = datetime.datetime.now().date()
    suggestions = []

    for s in strategies:
        sid = s.get("strategy_id", "")
        status = s.get("status", "")
        desc = s.get("description", "")
        try:
            uc = int(s.get("use_count", "0"))
        except (ValueError, TypeError):
            uc = 0
        try:
            sr = float(str(s.get("success_rate", "0")).rstrip("%"))
        except (ValueError, TypeError):
            sr = 0.0

        # rules 1: Recommended → Candidate Default
        if status == "Recommended" and uc >= 4 and sr > 80:
            suggestions.append({
                "strategy_id": sid,
                "current_status": status,
                "action": "Promote to Candidate Default",
                "reason": f"use_count={uc} ≥4, success_rate={sr}% >80%",
            })
            continue

        # rules 2: Any non-deprecated status → Deprecated
        if status != "Deprecated" and uc >= 3 and sr < 30:
            suggestions.append({
                "strategy_id": sid,
                "current_status": status,
                "action": "Mark as Deprecated",
                "reason": f"use_count={uc} ≥3, success_rate={sr}% <30%",
            })
            continue

        # rules 3: Recommended and not validated for more than 90 days → downgrade to Observation
        if status == "Recommended":
            last_date = _extract_last_date(desc)
            if last_date and (today - last_date).days > 90:
                days_ago = (today - last_date).days
                suggestions.append({
                    "strategy_id": sid,
                    "current_status": status,
                    "action": "Downgrade to Observation",
                    "reason": f"Last validated {last_date} ({days_ago}days ago), 90validation",
                })

    if not dry_run and suggestions:
        # 
        split = _split_main_strategy_table(content)
        if split:
            prefix, header_line, sep_line, row_lines, suffix = split
            headers = _headers_from_line(header_line)
            rows = []
            for rl in row_lines:
                d = _row_dict_from_line(headers, rl)
                sid_r = d.get("strategy_id", "")
                if sid_r and not sid_r.startswith("(") and not sid_r.startswith("("):
                    rows.append(d)

            action_map = {}
            for sg in suggestions:
                act = sg["action"]
                if "Candidate Default" in act:
                    action_map[sg["strategy_id"]] = "Candidate Default"
                elif "Deprecated" in act:
                    action_map[sg["strategy_id"]] = "Deprecated"
                elif "Observation" in act:
                    action_map[sg["strategy_id"]] = "Observation"

            for r in rows:
                new_st = action_map.get(r.get("strategy_id"))
                if new_st:
                    r["status"] = new_st

            new_content = _rebuild_table_content(
                prefix, header_line, sep_line, rows, headers, suffix
            )
            with open(registry_path, "w", encoding="utf-8") as f:
                f.write(new_content)

        # Record audit
        audit_lines = ["- mode: execute", f"- suggestions_count: {len(suggestions)}"]
        for sg in suggestions:
            audit_lines.append(
                f"- {sg['strategy_id']}: {sg['current_status']} → {sg['action']} ({sg['reason']})"
            )
        _append_audit(registry_path, "(audit)", "audit", audit_lines)

    return suggestions


# ---------------------------------------------------------------------------
# CLI Entry
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# evolve-profile  — P2-08 Identity Evolution
# ---------------------------------------------------------------------------

_EVOLUTION_FIELDS = ("Strength Areas", "Strategy", "Known Limitations", "Capability Self-assessment")


def cmd_evolve_profile(role, field, value, reason):
    """Update an evolution-section field in an agent profile and record the evolution history."""
    if field not in _EVOLUTION_FIELDS:
        print(f"ERROR: --field must be {'/'.join(_EVOLUTION_FIELDS)} ", file=sys.stderr)
        return False

    profiles_dir = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "assets", "agent-profiles"
    )
    profile_path = os.path.normpath(os.path.join(profiles_dir, f"{role}.md"))
    if not os.path.isfile(profile_path):
        print(f"ERROR: profile file does not exist: {profile_path}", file=sys.stderr)
        return False

    with open(profile_path, "r", encoding="utf-8") as f:
        content = f.read()

    # FieldNew Value
    pattern = rf"(- {re.escape(field)}: )(.*)"
    match = re.search(pattern, content)
    if not match:
        print(f"ERROR: field '{field}' not found in profile", file=sys.stderr)
        return False

    existing = match.group(2).strip()
    if existing in ("(accumulates with use)", "(accumulates with the experience registry)", "(accumulates with failure lessons)", "(taskCompleted)"):
        new_val = value
    else:
        new_val = f"{existing}; {value}"
    content = content[:match.start()] + f"- {field}: {new_val}" + content[match.end():]

    # Append a new row to the end of the evolution-history table
    today = datetime.date.today().isoformat()
    history_row = f"| {today} | {field}: {value} | {reason} |"
    # Find the last table row and append after it
    table_rows = list(re.finditer(r"^\|.*\|$", content, re.MULTILINE))
    if table_rows:
        last_row = table_rows[-1]
        insert_pos = last_row.end()
        content = content[:insert_pos] + "\n" + history_row + content[insert_pos:]
    else:
        content = content.rstrip() + "\n" + history_row + "\n"

    with open(profile_path, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"OK: Updated {role} profile field '{field}' <- {value}")
    return True


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)

    work_dir = sys.argv[1]
    command = sys.argv[2]
    json_output = '--json' in sys.argv

    if not os.path.isdir(work_dir):
        print(f"ERROR: work directory does not exist: {work_dir}", file=sys.stderr)
        sys.exit(1)

    registry_path = _find_registry(work_dir)
    if not registry_path:
        print("ERROR: experience-registry.md not found", file=sys.stderr)
        sys.exit(1)

    if command == 'query':
        template = None
        tags = []
        include_observation = '--include-observation' in sys.argv
        include_global = '--include-global' in sys.argv
        args = sys.argv[3:]
        i = 0
        while i < len(args):
            if args[i] == '--template' and i + 1 < len(args):
                template = args[i + 1]
                i += 2
            elif args[i] == '--tags' and i + 1 < len(args):
                tags = _parse_tags(args[i + 1])
                i += 2
            elif args[i] in ('--include-observation', '--include-global'):
                i += 1
            else:
                i += 1

        if not template:
            print("ERROR: query command requires the --template argument", file=sys.stderr)
            sys.exit(1)

        results = cmd_query(
            registry_path, template, tags, include_observation=include_observation,
            include_global=include_global)

        if json_output:
            print(json.dumps(results, ensure_ascii=False, indent=2))
        else:
            if not results:
                print("No matching strategies for template {} and tags {}.".format(template, tags or 'None'))
            else:
                print("Recommended strategies for template {} and tags {}:".format(template, tags or 'None'))
                print()
                for r in results:
                    sid = r.get('strategy_id', '?')
                    desc = r.get('description', '—')
                    status = r.get('effective_status', r.get('status', '?'))
                    rate = r.get('success_rate', '—')
                    print(f"  {sid}  [{status}]  ={rate}  {desc}")

    elif command == 'write':
        strategy_id = None
        effect = None
        score = None
        context = None
        status = None
        template = None
        dimension = None
        write_tags = None
        mechanism = None
        failure_lesson = None
        applicable_templates = None
        args = sys.argv[3:]
        i = 0
        while i < len(args):
            if args[i] == '--strategy-id' and i + 1 < len(args):
                strategy_id = args[i + 1]
                i += 2
            elif args[i] == '--effect' and i + 1 < len(args):
                effect = args[i + 1]
                i += 2
            elif args[i] == '--score' and i + 1 < len(args):
                score = args[i + 1]
                i += 2
            elif args[i] == '--mechanism' and i + 1 < len(args):
                mechanism = args[i + 1]
                i += 2
            elif args[i] == '--failure-lesson' and i + 1 < len(args):
                failure_lesson = args[i + 1]
                i += 2
            elif args[i] == '--context' and i + 1 < len(args):
                context = args[i + 1]
                i += 2
            elif args[i] == '--status' and i + 1 < len(args):
                status = args[i + 1]
                i += 2
            elif args[i] == '--template' and i + 1 < len(args):
                template = args[i + 1]
                i += 2
            elif args[i] == '--dimension' and i + 1 < len(args):
                dimension = args[i + 1]
                i += 2
            elif args[i] == '--tags' and i + 1 < len(args):
                write_tags = _parse_tags(args[i + 1])
                i += 2
            elif args[i] == '--templates' and i + 1 < len(args):
                raw_tpl = args[i + 1].strip()
                if raw_tpl == '*':
                    applicable_templates = ['*']
                else:
                    applicable_templates = [t.strip().upper() for t in raw_tpl.split(',') if t.strip()]
                i += 2
            else:
                i += 1

        if not strategy_id:
            print("ERROR: write command requires the --strategy-id argument", file=sys.stderr)
            sys.exit(1)
        if effect not in ('Keep', 'Avoid', 'To Validate'):
            print("ERROR: --effect must be Keep|Avoid|To Validate", file=sys.stderr)
            sys.exit(1)
        if score is None:
            print("ERROR: write command requires the --score argument", file=sys.stderr)
            sys.exit(1)

        ok = cmd_write(registry_path, strategy_id, effect, score, context,
                       status, template, dimension, write_tags, mechanism=mechanism,
                       failure_lesson=failure_lesson,
                       applicable_templates=applicable_templates)
        if ok:
            print(
                "OK:  upsert Strategy {} (={}, score={})".format(
                    strategy_id, effect, score
                )
            )
        else:
            sys.exit(1)

    elif command == "consolidate":
        dry_run = "--dry-run" in sys.argv
        ok = cmd_consolidate(registry_path, dry_run=dry_run)
        sys.exit(0 if ok else 1)

    elif command == "audit":
        # dry-run by default for safety; use --execute to apply changes
        dry_run = "--execute" not in sys.argv
        suggestions = cmd_audit(registry_path, dry_run=dry_run)
        if not suggestions:
            print("Audit: no suggestions found.")
        else:
            mode = "DRY-RUN" if dry_run else "EXECUTED"
            print(f"Audit [{mode}]: {len(suggestions)} recommendations\n")
            print("{:<20} {:<12} {:<20} {}".format(
                "strategy_id", "CurrentStatus", "Recommendation", "Rationale"))
            print("-" * 80)
            for sg in suggestions:
                print("{:<20} {:<12} {:<20} {}".format(
                    sg["strategy_id"],
                    sg["current_status"],
                    sg["action"],
                    sg["reason"],
                ))
        sys.exit(0)

    elif command == 'evolve-profile':
        role = None
        field = None
        value = None
        reason = None
        args = sys.argv[3:]
        i = 0
        while i < len(args):
            if args[i] == '--role' and i + 1 < len(args):
                role = args[i + 1]
                i += 2
            elif args[i] == '--field' and i + 1 < len(args):
                field = args[i + 1]
                i += 2
            elif args[i] == '--value' and i + 1 < len(args):
                value = args[i + 1]
                i += 2
            elif args[i] == '--reason' and i + 1 < len(args):
                reason = args[i + 1]
                i += 2
            else:
                i += 1

        if not all([role, field, value, reason]):
            print("ERROR: evolve-profile requires --role, --field, --value, and --reason",
                  file=sys.stderr)
            sys.exit(1)

        ok = cmd_evolve_profile(role, field, value, reason)
        sys.exit(0 if ok else 1)

    elif command == 'list':
        strategies = cmd_list(registry_path)

        if json_output:
            print(json.dumps(strategies, ensure_ascii=False, indent=2))
        else:
            if not strategies:
                print("Experience registry: no strategy records found.")
            else:
                print("Strategy({}items):".format(len(strategies)))
                print()
                print("{:<20} {:<8} {:<12} {:<10} {:<8} {}".format(
                    "strategy_id", "Template", "Status", "", "Use Count", "Description"))
                print("-" * 80)
                for s in strategies:
                    print("{:<20} {:<8} {:<12} {:<10} {:<8} {}".format(
                        s.get('strategy_id', '?'),
                        s.get('template', '—'),
                        s.get('status', '?'),
                        s.get('success_rate', '—'),
                        s.get('use_count', '—'),
                        s.get('description', '—')[:40],
                    ))
    else:
        print(f"ERROR: unknown command: {command}", file=sys.stderr)
        print(__doc__)
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()
