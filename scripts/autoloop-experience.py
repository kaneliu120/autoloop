#!/usr/bin/env python3
"""AutoLoop 经验库读写工具

用法:
  autoloop-experience.py <work_dir> query --template T{N} [--tags tag1,tag2]
  autoloop-experience.py <work_dir> write --strategy-id S01-xxx --effect 保持|避免|待验证 --score N [--status 推荐|候选默认|观察|已废弃] [--context "..."]
  autoloop-experience.py <work_dir> list
  autoloop-experience.py <work_dir> list --json
"""

import json
import os
import re
import sys
import datetime

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
# query 命令
# ---------------------------------------------------------------------------

def cmd_query(registry_path, template, tags):
    """查询推荐策略：按模板过滤，可选 context_tags 过滤。"""
    with open(registry_path, 'r', encoding='utf-8') as f:
        content = f.read()

    strategies = _parse_strategy_table(content)
    scoped = _parse_context_scoped_table(content)

    # 标准化模板匹配（T1, t1, T1: Research 均匹配 T1）
    tpl_key = template.upper().split(':')[0].split(' ')[0].strip() if template else None

    results = []
    for s in strategies:
        # 模板过滤
        s_tpl = s.get('template', '').upper().split(':')[0].split(' ')[0].strip()
        if tpl_key and s_tpl != tpl_key and s_tpl != '通用':
            continue

        # 确定有效 status（优先 context-scoped）
        effective_status = s.get('status', '待验证')
        if tags:
            for sc in scoped:
                if sc.get('strategy_id') != s.get('strategy_id'):
                    continue
                sc_tags_raw = sc.get('context_tags', '')
                sc_tags = _parse_tags(sc_tags_raw)
                overlap = len(set(tags) & set(sc_tags))
                if overlap >= 2:
                    effective_status = sc.get('status', effective_status)
                    break

        # 只返回 推荐 或 候选默认 或 观察（lifecycle status 枚举）
        if effective_status in ('推荐', '候选默认', '观察'):
            entry = dict(s)
            entry['effective_status'] = effective_status
            results.append(entry)

    # 按 success_rate 降序排序
    def sort_key(item):
        try:
            return float(item.get('success_rate', '0').rstrip('%'))
        except (ValueError, AttributeError):
            return 0.0

    results.sort(key=sort_key, reverse=True)
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

def cmd_write(registry_path, strategy_id, effect, score, context, status=None):
    """向策略效果库追加一行。

    effect: 本轮策略评价（保持/避免/待验证） — per-round evaluation
    status: 生命周期状态（推荐/候选默认/观察/已废弃） — lifecycle status
           如果未指定，根据 effect 自动推断：新策略默认"观察"
    """
    # 验证 status（lifecycle enum）
    valid_statuses = ('推荐', '候选默认', '观察', '已废弃')
    if status is not None and status not in valid_statuses:
        print(f"ERROR: --status 必须是 {'|'.join(valid_statuses)}", file=sys.stderr)
        return False

    # 如果未指定 status，新策略默认为"观察"
    if status is None:
        status = '观察'

    with open(registry_path, 'r', encoding='utf-8') as f:
        content = f.read()

    match = _TABLE_HEADER_RE.search(content)
    if not match:
        print("ERROR: 未找到策略效果库表格", file=sys.stderr)
        return False

    # 提取模板前缀
    template = ''
    parts = strategy_id.split('-')
    if len(parts) >= 1:
        first = parts[0].upper()
        if first.startswith('S') or first.startswith('C'):
            template = '通用'

    now = datetime.datetime.now().strftime('%Y-%m-%d')
    # 构建新行
    new_row = (
        f"| {strategy_id} | {template} | — | {context or '—'} "
        f"| {score} | — | 1 | — | {status} |"
    )

    # 找到表格的最后一行（最后一个以 | 开头的行）
    lines = content.split('\n')
    table_start = content[:match.start()].count('\n')
    insert_idx = table_start + 1  # header 行之后

    # 跳过分隔行
    for i in range(table_start + 1, len(lines)):
        line = lines[i].strip()
        if re.match(r'^\|[\s\-:|]+\|$', line):
            insert_idx = i + 1
            continue
        if line.startswith('|'):
            insert_idx = i + 1
        else:
            break

    lines.insert(insert_idx, new_row)

    with open(registry_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))

    # 自动晋升建议：检查同 strategy_id 的历史记录
    all_strategies = _parse_strategy_table('\n'.join(lines))
    same_id = [s for s in all_strategies if s.get('strategy_id') == strategy_id]
    if len(same_id) >= 3:
        keep_count = sum(1 for s in same_id if s.get('effect', '') == '保持')
        if keep_count >= 2 and status == '观察':
            print("PROMOTION_HINT: 策略 {} 已累计 {} 次使用（{} 次保持），建议从「观察」晋升为「推荐」".format(
                strategy_id, len(same_id), keep_count))

    return True


# ---------------------------------------------------------------------------
# list 命令
# ---------------------------------------------------------------------------

def cmd_list(registry_path):
    """列出所有策略及其状态。"""
    with open(registry_path, 'r', encoding='utf-8') as f:
        content = f.read()
    return _parse_strategy_table(content)


# ---------------------------------------------------------------------------
# CLI 入口
# ---------------------------------------------------------------------------

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
        args = sys.argv[3:]
        i = 0
        while i < len(args):
            if args[i] == '--template' and i + 1 < len(args):
                template = args[i + 1]
                i += 2
            elif args[i] == '--tags' and i + 1 < len(args):
                tags = _parse_tags(args[i + 1])
                i += 2
            else:
                i += 1

        if not template:
            print("ERROR: query 命令需要 --template 参数", file=sys.stderr)
            sys.exit(1)

        results = cmd_query(registry_path, template, tags)

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
            elif args[i] == '--context' and i + 1 < len(args):
                context = args[i + 1]
                i += 2
            elif args[i] == '--status' and i + 1 < len(args):
                status = args[i + 1]
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

        ok = cmd_write(registry_path, strategy_id, effect, score, context, status)
        if ok:
            print(f"OK: 已写入策略 {strategy_id} (效果={effect}, 状态={status or '观察'}, 分数={score})")
        else:
            sys.exit(1)

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
