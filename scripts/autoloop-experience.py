#!/usr/bin/env python3
"""AutoLoop 经验库读写工具

用法:
  autoloop-experience.py <work_dir> query --template T{N} [--tags tag1,tag2] [--include-global]
  autoloop-experience.py <work_dir> write --strategy-id S01-xxx --effect 保持|避免|待验证 --score DELTA [--mechanism "适用机制简述"] [--failure-lesson "what:...|why:...|instead:..."] [--status 推荐|候选默认|观察|已废弃] [--template T{N}] [--dimension dim] [--context "..."] [--tags python,backend,security] [--templates "T1,T2" | "*"]
  注: --score 为单轮分数变化量（delta），非绝对分。主表 avg_delta = 各次 write 的 score 之算术平均（与 experience-registry 一致）。
  可选环境变量 AUTOLOOP_EXPERIENCE_REQUIRE_MECHANISM=1：当 use_count≥2 时强制要求本次带 --mechanism（收紧 D-03）。
  autoloop-experience.py <work_dir> list
  autoloop-experience.py <work_dir> list --json
  autoloop-experience.py <work_dir> audit [--dry-run]          # P2-05：审计策略状态，建议晋升/淘汰
  autoloop-experience.py <work_dir> consolidate [--dry-run]   # P3-01：合并主表中重复 strategy_id 为单行
  autoloop-experience.py <work_dir> evolve-profile --role ROLE --field FIELD --value VALUE --reason REASON  # P2-08：更新 agent profile 进化区域
  主表：每个 strategy_id 仅保留一行（write 为 upsert）。审计：references/experience-audit.md 追加每次写入。
  strategy_id 以 multi: 开头时仅写审计、不更新主表；须满足 P3-06 multi:{SNN+SNN} 约束（见 experience-registry.md）。
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
# 路径解析
# ---------------------------------------------------------------------------

def _find_registry(work_dir):
    """查找 experience-registry.md。

    优先级:
    1. 脚本所在目录的 ../references/experience-registry.md
    2. work_dir 的上级 references/experience-registry.md
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
# 表格解析
# ---------------------------------------------------------------------------

_TABLE_HEADER_RE = re.compile(
    r'^\|\s*strategy_id\s*\|.*status\s*\|',
    re.IGNORECASE | re.MULTILINE,
)


def _parse_strategy_table(content):
    """解析全局策略效果库表格，返回 list[dict]。"""
    match = _TABLE_HEADER_RE.search(content)
    if not match:
        return []

    # 提取表头
    header_line = content[match.start():content.index('\n', match.start())]
    headers = [h.strip() for h in header_line.strip().strip('|').split('|')]

    # 跳过分隔行
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

        # 跳过占位行
        sid = row.get('strategy_id', '')
        if not sid or sid.startswith('（') or sid.startswith('('):
            continue

        strategies.append(row)

    return strategies


def _parse_context_scoped_table(content):
    """解析 context-scoped 状态补充表（如果存在）。"""
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
# P3-01 主表 + 审计（聚合单行 / experience-audit.md）
# ---------------------------------------------------------------------------

_AUDIT_BASENAME = "experience-audit.md"


def _audit_path(registry_path):
    return os.path.join(os.path.dirname(os.path.abspath(registry_path)), _AUDIT_BASENAME)


def _audit_write_scores_chronological(audit_path, strategy_id):
    """本次 write 追加前，按时间顺序收集该 strategy_id 的各次 `write` 审计 score。"""
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
    """由若干单轮 delta（--score）得到 use_count、avg_delta、success_rate（与 registry 字段语义一致）。"""
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
    """主表 avg_delta 列展示格式（与 cmd_write 一致）。"""
    ad = avg_delta
    if isinstance(ad, float) and ad == int(ad):
        return str(int(ad))
    if isinstance(ad, float):
        return "{:.4g}".format(ad)
    return str(ad)


def _append_audit(registry_path, strategy_id, action, payload_lines):
    """追加审计块（Markdown）。payload_lines: list of \"- key: value\" 字符串。"""
    ap = _audit_path(registry_path)
    now = datetime.datetime.now().isoformat(timespec="seconds")
    block = "\n### {} | {} | {}\n\n".format(now, action, strategy_id)
    block += "\n".join(payload_lines) + "\n"
    if not os.path.isfile(ap):
        head = (
            "# Experience audit log\n\n"
            "> 每次 write / consolidate 追加一条；主表 `experience-registry.md` 仅存当前有效行（每 strategy_id 一行）。\n\n"
        )
        with open(ap, "w", encoding="utf-8") as f:
            f.write(head)
    with open(ap, "a", encoding="utf-8") as f:
        f.write(block)


def _split_main_strategy_table(content):
    """拆出主策略表：prefix, header_line, sep_line, row_line_strs, suffix。"""
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
    """同一 strategy_id 多行时保留文件中最后一行（与 upsert 后主表一致）。"""
    seen = {}
    for s in strategies:
        sid = s.get("strategy_id", "")
        if not sid or sid.startswith("（") or sid.startswith("("):
            continue
        seen[sid] = s
    return list(seen.values())


def _row_positive_signal(row):
    """从历史行推断该次写入是否算正向（用于 success_rate）。"""
    desc = str(row.get("description", ""))
    if "[保持]" in desc:
        return True
    if "[避免]" in desc:
        return False
    try:
        return float(str(row.get("avg_delta", "—")).replace("—", "0")) > 0
    except (ValueError, TypeError):
        return False


def _merge_history_rows(
    historical, effect, score, context, dim_str, tags, now_str, prior_scores=None,
    mechanism=None, failure_lesson=None, applicable_templates=None,
):
    """由审计中已有 score + 本次 score 计算 use_count、avg_delta、success_rate、description。

    prior_scores: 本次写入前从 audit 解析的按时间顺序的 delta 列表；主表仅一行 upsert 时必须提供，
    否则 use_count 会恒为 2。
    applicable_templates: 适用模板列表（如 ['T1','T2'] 或 ['*']），写入 [templates: ...] 片段。
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

    last_st = "观察"
    if historical:
        st = historical[-1].get("status", "观察")
        if st in ("推荐", "候选默认", "观察", "已废弃"):
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
    """将主表中重复 strategy_id 合并为单行。优先用审计中该 sid 全部 write 的 score 重算
    use_count / avg_delta / success_rate（与 registry：历次 delta 的算术平均 一致）；无审计时回退为各行 avg_delta 算术平均。
    """
    with open(registry_path, "r", encoding="utf-8") as f:
        content = f.read()
    split = _split_main_strategy_table(content)
    if not split:
        print("ERROR: 未找到策略效果库表格", file=sys.stderr)
        return False
    prefix, header_line, sep_line, row_lines, suffix = split
    headers = _headers_from_line(header_line)
    rows = []
    for rl in row_lines:
        d = _row_dict_from_line(headers, rl)
        sid = d.get("strategy_id", "")
        if sid and not sid.startswith("（") and not sid.startswith("("):
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
        print("OK: 主表无重复 strategy_id，跳过")
        return True

    new_content = _rebuild_table_content(
        prefix, header_line, sep_line, new_rows, headers, suffix
    )
    if dry_run:
        print("DRY-RUN: 将把 {} 个 strategy_id 合并为 {} 行".format(len(rows), len(new_rows)))
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
    print("OK: 已合并重复 strategy_id → {} 行，审计已记录".format(len(new_rows)))
    return True


# ---------------------------------------------------------------------------
# query 命令 — context_tags 与 loop-protocol / experience-registry 对齐（P3-02）
# ---------------------------------------------------------------------------

_EFFECT_BRACKETS = frozenset({'保持', '避免', '待验证'})


def _normalize_tag_set(tags):
    """小写、去空白，用于重叠与集合比较。"""
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
    """从 description 取出 write 时 --tags 写入的片段（[保持] @YYYY-MM-DD [tag1,tag2]）。"""
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
    """context-scoped 补充表：精确匹配 > 任务为行标签超集（取行标签最多）> 全局。"""
    global_status = global_status or '待验证'
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
    """从 description 提取 [templates: ...] 片段，返回模板集合（大写）。
    [templates: *] 返回 frozenset({'*'})；[templates: T1,T3] 返回 frozenset({'T1','T3'})。
    无片段返回 None（表示未设置，默认使用行的 template 字段）。
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
    """查询推荐策略：按模板过滤；若提供任务 context_tags，仅保留与策略
    description 内 context_tags 交集≥2 的条目（loop-protocol）；无 tags 时不做重叠过滤（冷启动）。

    include_global=True 时，除了同模板条目，还返回 applicable_templates 包含当前模板或 [*] 的条目。

    默认仅返回 effective_status 为「推荐」「候选默认」；「观察」需 --include-observation。
    """
    with open(registry_path, 'r', encoding='utf-8') as f:
        content = f.read()

    strategies = _dedupe_strategies_latest(_parse_strategy_table(content))
    scoped = _parse_context_scoped_table(content)
    task_tag_set = _normalize_tag_set(tags)

    # 标准化模板匹配（T1, t1, T1: Research 均匹配 T1）
    tpl_key = template.upper().split(':')[0].split(' ')[0].strip() if template else None

    results = []
    for s in strategies:
        # 模板过滤（含 applicable_templates 跨模板匹配）
        s_tpl = s.get('template', '').upper().split(':')[0].split(' ')[0].strip()
        tpl_match = (not tpl_key) or s_tpl == tpl_key or s_tpl == '通用'
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
            s.get('strategy_id', ''), s.get('status', '待验证'), scoped, task_tag_set,
        )

        allowed = ('推荐', '候选默认', '观察') if include_observation else ('推荐', '候选默认')
        if effective_status in allowed:
            entry = dict(s)
            entry['effective_status'] = effective_status
            results.append(entry)

    # 时间衰减 + success_rate 排序（experience-registry.md §时间衰减机制）
    today = datetime.datetime.now().date()

    def sort_key(item):
        try:
            base_rate = float(item.get('success_rate', '0').rstrip('%'))
        except (ValueError, AttributeError):
            base_rate = 0.0

        # 从 description 中提取 @YYYY-MM-DD 日期
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
                    decay = 0.2  # >90d 严重衰减
                    # 自动降级提示
                    if item.get('effective_status') == '推荐':
                        item['effective_status'] = '观察'
                        item['_decay_note'] = f'>90d未验证，自动降为观察'
            except ValueError:
                pass

        return base_rate * decay

    results.sort(key=sort_key, reverse=True)

    # 持久化 >90d 自动降级（写回 registry 文件）
    downgraded = [r for r in results if r.get('_decay_note')]
    if downgraded:
        with open(registry_path, 'r', encoding='utf-8') as f:
            file_content = f.read()
        modified = False
        for r in downgraded:
            sid = r.get('strategy_id', '')
            # 在文件中找到该策略行，将 推荐 替换为 观察
            old_pattern = f"| {sid} |"
            if old_pattern in file_content:
                lines = file_content.split('\n')
                for idx, line in enumerate(lines):
                    if old_pattern in line and '| 推荐 |' in line:
                        lines[idx] = line.replace('| 推荐 |', '| 观察 |', 1)
                        modified = True
                        print(f"DECAY_DOWNGRADE: {sid} 推荐→观察（{r['_decay_note']}）")
                file_content = '\n'.join(lines)
        if modified:
            with open(registry_path, 'w', encoding='utf-8') as f:
                f.write(file_content)

    # 衰减在排序阶段可能把「推荐」改为「观察」；默认 query 不得返回观察（与 loop-protocol / P0-03）
    if not include_observation:
        results = [r for r in results if r.get("effective_status") != "观察"]

    return results


def _parse_tags(raw):
    """解析 tags 字符串为列表。支持 [a, b] 和 a,b 格式。"""
    if not raw:
        return []
    raw = raw.strip().strip('[]')
    return [t.strip() for t in raw.split(',') if t.strip()]


# ---------------------------------------------------------------------------
# write 命令
# ---------------------------------------------------------------------------

# 合法模板前缀
_VALID_TEMPLATES = {'T1', 'T2', 'T3', 'T4', 'T5', 'T6', 'T7', 'T8'}


def _infer_template(strategy_id):
    """从 strategy_id 推断适用模板。

    规则：
    1. strategy_id 中包含 T{N} 片段（如 S15-T5-xxx）→ 提取该模板
    2. C{NN} 前缀（组合策略）→ '通用'
    3. 无法推断 → '通用'
    """
    parts = strategy_id.upper().replace('_', '-').split('-')
    for part in parts:
        if part in _VALID_TEMPLATES:
            return part
    # 组合策略或无法推断
    return '通用'


def cmd_write(registry_path, strategy_id, effect, score, context,
              status=None, template=None, dimension=None, tags=None, mechanism=None,
              failure_lesson=None, applicable_templates=None):
    """主表 upsert（每个 strategy_id 仅一行）并追加 `experience-audit.md`。

    multi: 前缀见 experience-registry.md — 只记审计，不更新主表聚合。
    applicable_templates: 适用模板列表（如 ['T1','T2'] 或 ['*']），写入 description 的 [templates: ...] 片段。
    """
    valid_statuses = ('推荐', '候选默认', '观察', '已废弃')
    if status is not None and status not in valid_statuses:
        print("ERROR: --status 必须是 {}".format("|".join(valid_statuses)), file=sys.stderr)
        return False

    user_status = status
    if is_multi_strategy_id(strategy_id) and user_status is not None:
        print(
            "ERROR: multi: 混合归因策略不得使用 --status（不入主表生命周期）",
            file=sys.stderr,
        )
        return False

    if user_status is not None and user_status in ('推荐', '候选默认'):
        print(
            "WARN: 显式设置 status={}，绕过自动晋升门槛验证".format(user_status),
            file=sys.stderr,
        )

    try:
        score_val = float(score)
        if abs(score_val) > 10:
            print(
                "WARN: --score={} 看起来是绝对分数而非 delta 变化量。".format(score),
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
                "- note: 不更新主表（混合归因）",
            ],
        )
        print("OK: multi: 已写入审计日志，主表聚合未修改")
        return True

    with open(registry_path, "r", encoding="utf-8") as f:
        content = f.read()

    split = _split_main_strategy_table(content)
    if not split:
        print("ERROR: 未找到策略效果库表格", file=sys.stderr)
        return False
    prefix, header_line, sep_line, row_lines, suffix = split
    headers = _headers_from_line(header_line)
    rows = []
    for rl in row_lines:
        d = _row_dict_from_line(headers, rl)
        sid = d.get("strategy_id", "")
        if sid and not sid.startswith("（") and not sid.startswith("("):
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
        ls = historical[-1].get("status", "观察")
        existing_status = ls if ls in valid_statuses else "观察"
    else:
        existing_status = "观察"

    try:
        d_curr = float(score)
    except (ValueError, TypeError):
        d_curr = 0.0

    prev_score = prior_scores[-1] if prior_scores else None

    confidence = "低" if use_count == 1 else ("中" if use_count <= 3 else "高")
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

            if last_two_nonpos and existing_status != "已废弃":
                status = "已废弃"
                promoted = True
                print(
                    "AUTO_DEPRECATION: 策略 {} 从「{}」降级为「已废弃」"
                    "（连续2次 delta≤0, use_count={}）".format(
                        strategy_id, existing_status, use_count
                    )
                )
            elif existing_status == "已废弃" and d_curr > 0:
                status = "观察"
                promoted = True
                print(
                    "AUTO_RECOVERY: 策略 {} 从「已废弃」恢复为「观察」"
                    "（delta>0, use_count={}）".format(strategy_id, use_count)
                )
            elif existing_status == "观察" and last_two_pos and confidence in ("中", "高"):
                status = "推荐"
                promoted = True
                print(
                    "AUTO_PROMOTION: 策略 {} 从「观察」晋升为「推荐」"
                    "（use_count={}, 连续2次 delta>0, confidence={}）".format(
                        strategy_id, use_count, confidence
                    )
                )
            elif existing_status == "推荐" and use_count >= 4 and confidence == "高":
                if total_positive_count / use_count >= 0.8:
                    status = "候选默认"
                    promoted = True
                    print(
                        "AUTO_PROMOTION: 策略 {} 从「推荐」晋升为「候选默认」"
                        "（use_count={}, success_rate={}）".format(
                            strategy_id, use_count, success_rate
                        )
                    )
            elif existing_status in ("推荐", "候选默认") and not promoted:
                status = existing_status

    require_mech = os.environ.get("AUTOLOOP_EXPERIENCE_REQUIRE_MECHANISM", "").strip().lower() in (
        "1", "true", "yes",
    )
    if require_mech and use_count >= 2:
        if not (mechanism and str(mechanism).strip()):
            print(
                "ERROR: AUTOLOOP_EXPERIENCE_REQUIRE_MECHANISM=1 且 use_count≥2 时必须提供非空 --mechanism",
                file=sys.stderr,
            )
            return False

    # 仅在首次达到 use_count==2 时提示一次，避免多轮 write 刷屏（技术债务 D-03）
    if use_count == 2:
        print(
            "WARN: 策略 {} use_count=2 — 建议按 experience-registry.md 在 description 中补充 "
            "适用机制/前置条件/禁忌等（registry 要求 use_count≥2 后完善）".format(
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

    if not promoted and use_count >= 3 and status == "观察":
        print(
            "PROMOTION_HINT: 策略 {} 已累计 {} 次使用（confidence={}），"
            "尚未满足自动晋升条件（需连续2次 delta>0 且 confidence>=中）".format(
                strategy_id, use_count, confidence
            )
        )

    return True


# ---------------------------------------------------------------------------
# list 命令
# ---------------------------------------------------------------------------

def cmd_list(registry_path):
    """列出所有策略及其状态（主表每 strategy_id 一行）。"""
    with open(registry_path, "r", encoding="utf-8") as f:
        content = f.read()
    return _dedupe_strategies_latest(_parse_strategy_table(content))


# ---------------------------------------------------------------------------
# audit 命令 — P2-05 持续学习闭环
# ---------------------------------------------------------------------------

def _extract_last_date(desc):
    """从 description 中提取最新 @YYYY-MM-DD 日期，返回 datetime.date 或 None。"""
    matches = re.findall(r'@(\d{4}-\d{2}-\d{2})', str(desc))
    if not matches:
        return None
    try:
        return datetime.datetime.strptime(matches[-1], '%Y-%m-%d').date()
    except ValueError:
        return None


def cmd_audit(registry_path, dry_run=True):
    """扫描所有经验条目，基于 use_count/success_rate/avg_delta 自动建议晋升或淘汰。

    返回审计建议列表 list[dict]，每项含 strategy_id / current_status / action / reason。
    dry_run=True 时仅输出报告；False 时执行变更并记录到 experience-audit.md。
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

        # 规则 1：推荐 → 候选默认
        if status == "推荐" and uc >= 4 and sr > 80:
            suggestions.append({
                "strategy_id": sid,
                "current_status": status,
                "action": "晋升为「候选默认」",
                "reason": f"use_count={uc} ≥4, success_rate={sr}% >80%",
            })
            continue

        # 规则 2：任意非废弃 → 已废弃
        if status != "已废弃" and uc >= 3 and sr < 30:
            suggestions.append({
                "strategy_id": sid,
                "current_status": status,
                "action": "标记为「已废弃」",
                "reason": f"use_count={uc} ≥3, success_rate={sr}% <30%",
            })
            continue

        # 规则 3：超过 90 天未验证且推荐 → 降为观察
        if status == "推荐":
            last_date = _extract_last_date(desc)
            if last_date and (today - last_date).days > 90:
                days_ago = (today - last_date).days
                suggestions.append({
                    "strategy_id": sid,
                    "current_status": status,
                    "action": "降为「观察」",
                    "reason": f"最后验证 {last_date} ({days_ago}天前), 超过90天未验证",
                })

    if not dry_run and suggestions:
        # 执行变更
        split = _split_main_strategy_table(content)
        if split:
            prefix, header_line, sep_line, row_lines, suffix = split
            headers = _headers_from_line(header_line)
            rows = []
            for rl in row_lines:
                d = _row_dict_from_line(headers, rl)
                sid_r = d.get("strategy_id", "")
                if sid_r and not sid_r.startswith("（") and not sid_r.startswith("("):
                    rows.append(d)

            action_map = {}
            for sg in suggestions:
                act = sg["action"]
                if "候选默认" in act:
                    action_map[sg["strategy_id"]] = "候选默认"
                elif "已废弃" in act:
                    action_map[sg["strategy_id"]] = "已废弃"
                elif "观察" in act:
                    action_map[sg["strategy_id"]] = "观察"

            for r in rows:
                new_st = action_map.get(r.get("strategy_id"))
                if new_st:
                    r["status"] = new_st

            new_content = _rebuild_table_content(
                prefix, header_line, sep_line, rows, headers, suffix
            )
            with open(registry_path, "w", encoding="utf-8") as f:
                f.write(new_content)

        # 记录审计
        audit_lines = ["- mode: execute", f"- suggestions_count: {len(suggestions)}"]
        for sg in suggestions:
            audit_lines.append(
                f"- {sg['strategy_id']}: {sg['current_status']} → {sg['action']} ({sg['reason']})"
            )
        _append_audit(registry_path, "(audit)", "audit", audit_lines)

    return suggestions


# ---------------------------------------------------------------------------
# CLI 入口
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# evolve-profile 命令 — P2-08 Identity Evolution
# ---------------------------------------------------------------------------

_EVOLUTION_FIELDS = ("擅长领域", "常用策略", "已知局限", "能力自评")


def cmd_evolve_profile(role, field, value, reason):
    """更新 agent profile 的进化区域字段并记录进化历史。"""
    if field not in _EVOLUTION_FIELDS:
        print(f"ERROR: --field 必须是 {'/'.join(_EVOLUTION_FIELDS)} 之一", file=sys.stderr)
        return False

    profiles_dir = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "assets", "agent-profiles"
    )
    profile_path = os.path.normpath(os.path.join(profiles_dir, f"{role}.md"))
    if not os.path.isfile(profile_path):
        print(f"ERROR: profile 文件不存在: {profile_path}", file=sys.stderr)
        return False

    with open(profile_path, "r", encoding="utf-8") as f:
        content = f.read()

    # 在进化区域的指定字段追加新值
    pattern = rf"(- {re.escape(field)}：)(.*)"
    match = re.search(pattern, content)
    if not match:
        print(f"ERROR: 未在 profile 中找到字段「{field}」", file=sys.stderr)
        return False

    existing = match.group(2).strip()
    if existing in ("（随使用积累）", "（随经验库积累）", "（随失败教训积累）", "（随任务完成积累）"):
        new_val = value
    else:
        new_val = f"{existing}; {value}"
    content = content[:match.start()] + f"- {field}：{new_val}" + content[match.end():]

    # 在进化历史表末尾追加新行
    today = datetime.date.today().isoformat()
    history_row = f"| {today} | {field}: {value} | {reason} |"
    # 找到最后一个表格行并在其后追加
    table_rows = list(re.finditer(r"^\|.*\|$", content, re.MULTILINE))
    if table_rows:
        last_row = table_rows[-1]
        insert_pos = last_row.end()
        content = content[:insert_pos] + "\n" + history_row + content[insert_pos:]
    else:
        content = content.rstrip() + "\n" + history_row + "\n"

    with open(profile_path, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"OK: 已更新 {role} profile「{field}」← {value}")
    return True


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)

    work_dir = sys.argv[1]
    command = sys.argv[2]
    json_output = '--json' in sys.argv

    if not os.path.isdir(work_dir):
        print(f"ERROR: 工作目录不存在: {work_dir}", file=sys.stderr)
        sys.exit(1)

    registry_path = _find_registry(work_dir)
    if not registry_path:
        print("ERROR: 未找到 experience-registry.md", file=sys.stderr)
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
            print("ERROR: query 命令需要 --template 参数", file=sys.stderr)
            sys.exit(1)

        results = cmd_query(
            registry_path, template, tags, include_observation=include_observation,
            include_global=include_global)

        if json_output:
            print(json.dumps(results, ensure_ascii=False, indent=2))
        else:
            if not results:
                print("无匹配策略（模板={}, tags={}）".format(template, tags or '无'))
            else:
                print("推荐策略（模板={}, tags={}）:".format(template, tags or '无'))
                print()
                for r in results:
                    sid = r.get('strategy_id', '?')
                    desc = r.get('description', '—')
                    status = r.get('effective_status', r.get('status', '?'))
                    rate = r.get('success_rate', '—')
                    print(f"  {sid}  [{status}]  成功率={rate}  {desc}")

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
            print("ERROR: write 命令需要 --strategy-id 参数", file=sys.stderr)
            sys.exit(1)
        if effect not in ('保持', '避免', '待验证'):
            print("ERROR: --effect 必须是 保持|避免|待验证", file=sys.stderr)
            sys.exit(1)
        if score is None:
            print("ERROR: write 命令需要 --score 参数", file=sys.stderr)
            sys.exit(1)

        ok = cmd_write(registry_path, strategy_id, effect, score, context,
                       status, template, dimension, write_tags, mechanism=mechanism,
                       failure_lesson=failure_lesson,
                       applicable_templates=applicable_templates)
        if ok:
            print(
                "OK: 已 upsert 策略 {} (效果={}, 分数={})".format(
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
        # 默认 dry-run（安全）；需 --execute 显式执行变更
        dry_run = "--execute" not in sys.argv
        suggestions = cmd_audit(registry_path, dry_run=dry_run)
        if not suggestions:
            print("AUDIT: 无需调整，所有策略状态正常")
        else:
            mode = "DRY-RUN" if dry_run else "EXECUTED"
            print(f"AUDIT [{mode}]: {len(suggestions)} 条建议\n")
            print("{:<20} {:<12} {:<20} {}".format(
                "strategy_id", "当前状态", "建议操作", "理由"))
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
            print("ERROR: evolve-profile 需要 --role, --field, --value, --reason 参数",
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
                print("经验库为空（尚无策略记录）")
            else:
                print("全局策略效果库（共{}条）:".format(len(strategies)))
                print()
                print("{:<20} {:<8} {:<12} {:<10} {:<8} {}".format(
                    "strategy_id", "模板", "状态", "成功率", "使用次数", "描述"))
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
        print(f"ERROR: 未知命令: {command}", file=sys.stderr)
        print(__doc__)
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()
