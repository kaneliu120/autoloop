#!/usr/bin/env python3
"""P3-06：multi: 并行策略 strategy_id 约束（experience write 与 validate 共用）。"""

import re

# 与 autoloop-validate STRATEGY_RE 一致：S{NN}-描述
STRATEGY_ID_BASE_RE = re.compile(r"^S\d{2}-.+$")

# multi:{...}，捕获花括号内子策略列表（loop-protocol 推荐 + 或 , 分隔）
_MULTI_BODY_RE = re.compile(r"^multi:\{(.+)\}\s*$", re.IGNORECASE)


def is_multi_strategy_id(strategy_id):
    if not strategy_id or not isinstance(strategy_id, str):
        return False
    return strategy_id.strip().lower().startswith("multi:")


def parse_multi_strategy_components(strategy_id):
    """解析 multi:{A,B} / multi:{A+B} → 子 strategy_id 列表；格式非法返回 None。"""
    if not strategy_id:
        return None
    s = strategy_id.strip()
    m = _MULTI_BODY_RE.match(s)
    if not m:
        return None
    inner = m.group(1).strip()
    if not inner:
        return None
    parts = re.split(r"[+,]", inner)
    out = [p.strip() for p in parts if p.strip()]
    return out if out else None


def validate_multi_strategy_id(strategy_id):
    """返回 (True, None) 或 (False, 错误说明)。"""
    parts = parse_multi_strategy_components(strategy_id)
    if parts is None:
        return (
            False,
            "multi: 须为 multi:{SNN-描述,SNN-描述} 或 multi:{SNN-描述+SNN-描述}（至少 2 个子策略）",
        )
    if len(parts) < 2:
        return False, "multi: 至少包含 2 个子策略（SNN-描述）"
    for p in parts:
        if not STRATEGY_ID_BASE_RE.match(p):
            return (
                False,
                "multi: 子策略 '{}' 须匹配 SNN-描述（如 S01-parallel-scan）".format(p),
            )
    if len(set(parts)) != len(parts):
        return False, "multi: 子策略不得重复"
    return True, None
