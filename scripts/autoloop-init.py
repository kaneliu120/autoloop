#!/usr/bin/env python3
"""AutoLoop Bootstrap 初始化工具 — 创建4个工作文件（plan/findings/progress/results.tsv）

用法:
  autoloop-init.py <工作目录> [模板] [目标]
  autoloop-init.py <工作目录> 'T1: Research' '调研AI自主迭代工具'
  autoloop-init.py <工作目录> 'T6: Quality' '代码质量审查' --ssot
"""

import subprocess
import sys
import os
import datetime

TSV_HEADER = "iteration\tphase\tstatus\tdimension\tmetric_value\tdelta\tstrategy_id\taction_summary\tside_effect\tevidence_ref\tunit_id\tprotocol_version\tscore_variance\tconfidence\tdetails"

# ---------------------------------------------------------------------------
# T1-T7 质量门禁维度定义 — 从 gate-manifest.json（SSOT）加载
# ---------------------------------------------------------------------------

import json


def _load_gate_manifest():
    """Load gate definitions from canonical manifest (SSOT)."""
    manifest_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "references", "gate-manifest.json")
    with open(manifest_path, "r", encoding="utf-8") as f:
        return json.load(f)


# manifest dimension → 中文标签
_MANIFEST_LABEL_MAP = {
    "coverage": "覆盖率",
    "credibility": "可信度",
    "consistency": "一致性",
    "completeness": "完整性",
    "bias_check": "偏见检查",
    "sensitivity": "敏感性分析",
    "kpi_target": "KPI 达目标值",
    "pass_rate": "通过率",
    "avg_score": "平均分",
    "syntax_errors": "语法验证",
    "p1_p2_issues": "P1/P2 问题",
    "service_health": "服务健康",
    "user_acceptance": "人工验收",
    "security": "安全性",
    "reliability": "可靠性",
    "maintainability": "可维护性",
    "p1_count": "P1 问题",
    "security_p2": "安全 P2 问题",
    "reliability_p2": "可靠性 P2 问题",
    "maintainability_p2": "可维护性 P2 问题",
    "architecture": "架构",
    "performance": "性能",
    "stability": "稳定性",
}


def _format_threshold(gate):
    """Convert manifest gate to human-readable threshold string."""
    threshold = gate["threshold"]
    unit = gate["unit"]
    comparator = gate.get("comparator", ">=")

    if threshold is None:
        return "用户在 plan 中设定"
    if unit == "bool":
        return "True" if threshold else "False"
    if unit == "%":
        if comparator == ">=":
            return f"≥ {threshold}%"
        elif comparator == "==":
            return f"{threshold}%"
        elif comparator == "<=":
            return f"≤ {threshold}%"
        return f"{threshold}%"
    if unit == "/10":
        if comparator == ">=":
            return f"≥ {threshold}/10"
        return f"{threshold}/10"
    if unit == "count":
        if comparator == "==" and threshold == 0:
            return "= 0"
        elif comparator == "<=":
            return f"≤ {threshold}"
        return f"{threshold}"
    return str(threshold)


def _manifest_to_init_gates(manifest):
    """Convert manifest templates to init's internal TEMPLATE_GATES format.

    Returns dict: {"T1": [("覆盖率", "≥ 85%", "Hard"), ...], ...}
    """
    result = {}
    for tkey, tdef in manifest["templates"].items():
        gates = []
        for g in tdef["gates"]:
            dim_raw = g["dimension"]
            label = _MANIFEST_LABEL_MAP.get(dim_raw, dim_raw)
            threshold_str = _format_threshold(g)
            gate_type = g["type"].capitalize()  # hard → Hard
            gates.append((label, threshold_str, gate_type))
        result[tkey] = gates
    return result


_MANIFEST = _load_gate_manifest()
TEMPLATE_GATES = _manifest_to_init_gates(_MANIFEST)

# ---------------------------------------------------------------------------
# 资产模板路径
# ---------------------------------------------------------------------------

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.normpath(os.path.join(SCRIPT_DIR, "..", "assets"))


def _read_asset(filename):
    """读取 assets/ 目录下的模板文件，不存在则返回 None。"""
    path = os.path.join(ASSETS_DIR, filename)
    if os.path.isfile(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    return None


def _parse_template_key(template):
    """从模板字符串中提取 T{N} 键，如 'T6: Quality' -> 'T6'。"""
    t = template.strip().upper().split(":")[0].split(" ")[0]
    if t.startswith("T") and len(t) >= 2 and t[1:].isdigit():
        return t
    return None


def _build_gate_table(template):
    """根据模板生成质量门禁表格内容。"""
    key = _parse_template_key(template)
    gates = TEMPLATE_GATES.get(key, []) if key else []

    if not gates:
        return "| — | — | 0 | — | 准备开始 |"

    rows = []
    for dim, threshold, gate_type in gates:
        rows.append(f"| {dim} | {threshold} | 0 | {gate_type} | 准备开始 |")
    return "\n".join(rows)


def create_plan(work_dir, task_id, template, goal):
    path = os.path.join(work_dir, "autoloop-plan.md")
    now = datetime.datetime.now().isoformat()
    gate_rows = _build_gate_table(template)

    content = f"""# AutoLoop 任务计划

## 元信息

| 字段 | 值 |
|------|-----|
| 任务 ID | {task_id} |
| 模板 | {template} |
| 状态 | 准备开始 |
| 创建时间 | {now} |
| 最后更新 | {now} |
| 工作目录 | {work_dir} |
| 计划版本 | 1.0 |

---

## 目标描述

**一句话目标**：{goal}

---

## 质量门禁

| 维度 | 目标阈值 | 当前分数 | 门禁类型 | 状态 |
|------|---------|---------|---------|------|
{gate_rows}

---

## 迭代预算

| 字段 | 值 |
|------|-----|
| 最大轮次 | 见 references/parameters.md |
| 当前轮次 | 0 |
| 预算耗尽策略 | 输出当前最优 |

---

## 策略历史

| 轮次 | strategy_id | 维度 | 策略 | 结果 | 弃用原因 |
|------|-------------|------|------|------|---------|
| — | — | — | — | — | — |
"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return path


def create_findings(work_dir, task_id, template):
    """创建 findings 文件，使用 assets/findings-template.md 的4层结构骨架。"""
    path = os.path.join(work_dir, "autoloop-findings.md")
    now = datetime.datetime.now().isoformat()

    asset = _read_asset("findings-template.md")
    if asset:
        # 用实际值替换模板占位符
        content = asset
        content = content.replace("autoloop-{YYYYMMDD-HHMMSS}", task_id)
        content = content.replace("T{N}: {名称}", template)
        content = content.replace("{ISO 8601}", now)
        # 清理其余占位符为待填写
        content = content.replace("{主题}", "待填写")
        content = content.replace("{N}", "进行中")
    else:
        # 回退：内联最小骨架
        content = f"""# AutoLoop Findings — 发现记录

**任务 ID**：{task_id}
**模板**：{template}
**创建时间**：{now}
**最后更新**：{now}

---

## 执行摘要

**调研/分析主题**：待填写
**总轮次**：进行中
**最终质量得分**：待评分

**关键结论（TOP 5）**：
1. 待填写
2. 待填写
3. 待填写
4. 待填写
5. 待填写

---

## 问题清单（REFLECT 第 1 层 — 累积追踪）

| 轮次 | 问题描述 | 来源 | 严重度 | 状态 | 根因分析 |
|------|---------|------|--------|------|---------|
| — | — | — | — | — | — |

## 策略评估（REFLECT 第 2 层 — 策略效果知识库）

| 轮次 | strategy_id | 策略 | 效果评分(1-5) | 分数变化 | 保持/避免/待验证 | 原因 |
|------|-------------|------|--------------|---------|-----------------|------|
| — | — | — | — | — | — | — |

## 模式识别（REFLECT 第 3 层 — 跨轮次趋势）

### 反复出现的问题
- 待记录

### 收益递减信号
- 待记录

### 跨维度关联
- 待记录

### 瓶颈
- 待记录

## 经验教训（REFLECT 第 4 层 — 可复用认知）

### 验证的假设
- 待记录

### 可泛化的方法论
- 待记录

### 对 AutoLoop 自身流程的改进建议
- 待记录
"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return path


def create_progress(work_dir, task_id, template):
    """创建 progress 文件，使用 assets/progress-template.md 的8阶段循环骨架。"""
    path = os.path.join(work_dir, "autoloop-progress.md")

    asset = _read_asset("progress-template.md")
    if asset:
        now = datetime.datetime.now().isoformat()
        content = asset
        content = content.replace("autoloop-{YYYYMMDD-HHMMSS}", task_id)
        content = content.replace("T{N}: {名称}", template)
        content = content.replace("{ISO 8601}", now)

        # 填充质量门禁总览行
        key = _parse_template_key(template)
        gates = TEMPLATE_GATES.get(key, []) if key else []
        if gates:
            # 替换模板中的占位维度行
            gate_rows = []
            for dim, threshold, _ in gates:
                gate_rows.append(f"| {dim} | — | — | — | — | ≥{threshold.lstrip('≥').strip()} |")
            gate_block = "\n".join(gate_rows)
            # 替换模板中 {维度 N} 占位行
            import re
            content = re.sub(
                r'\| \{维度 \d+\} \| — \| — \| — \| — \| ≥\{阈值\} \|\n?',
                '',
                content,
            )
            # 在质量门禁总览表头分隔行后插入实际维度
            sep_marker = "|------|------|-------|-------|-------|------|\n"
            if sep_marker in content:
                content = content.replace(sep_marker, sep_marker + gate_block + "\n")
    else:
        # 回退：内联最小骨架
        key = _parse_template_key(template)
        gates = TEMPLATE_GATES.get(key, []) if key else []
        if gates:
            gate_rows = []
            for dim, threshold, _ in gates:
                gate_rows.append(f"| {dim} | 0 | — | — | — | ≥{threshold.lstrip('≥').strip()} |")
            gate_block = "\n".join(gate_rows)
        else:
            gate_block = "| — | 0 | — | — | — | — |"

        content = f"""# AutoLoop Progress — 进度追踪

**任务 ID**：{task_id}
**模板**：{template}

## 质量门禁总览

| 维度 | 基线 | 第1轮 | 第2轮 | 第3轮 | 目标 |
|------|------|-------|-------|-------|------|
{gate_block}
"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return path


def create_tsv(work_dir):
    path = os.path.join(work_dir, "autoloop-results.tsv")
    with open(path, "w", encoding="utf-8") as f:
        f.write(TSV_HEADER + "\n")
    return path


def bootstrap(work_dir, task_id=None, template="T1: Research", goal="待填写",
              ssot=False):
    if not os.path.isdir(work_dir):
        print(f"ERROR: 目录不存在: {work_dir}")
        return False

    if task_id is None:
        task_id = f"autoloop-{datetime.datetime.now().strftime('%Y%m%d-%H%M%S')}"

    files = []
    files.append(create_plan(work_dir, task_id, template, goal))
    files.append(create_findings(work_dir, task_id, template))
    files.append(create_progress(work_dir, task_id, template))
    files.append(create_tsv(work_dir))

    # --ssot: 同时初始化 autoloop-state.json
    if ssot:
        state_script = os.path.join(SCRIPT_DIR, "autoloop-state.py")
        if os.path.isfile(state_script):
            result = subprocess.run(
                [sys.executable, state_script, "init", work_dir, template, goal],
                capture_output=True, text=True,
            )
            if result.returncode == 0:
                files.append(os.path.join(work_dir, "autoloop-state.json"))
                print(f"SSOT: {result.stdout.strip()}")
            else:
                error = result.stderr.strip() or result.stdout.strip()
                print(f"WARNING: SSOT 初始化失败: {error}")
        else:
            print(f"WARNING: autoloop-state.py 不存在: {state_script}")

    print(f"OK: Bootstrap完成，已创建{len(files)}个文件:")
    for f in files:
        print(f"  - {os.path.basename(f)}")
    print(f"\n任务ID: {task_id}")
    print(f"模板: {template}")
    print(f"工作目录: {work_dir}")
    return True


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    work_dir = sys.argv[1]
    # 过滤掉 flags
    positional = [a for a in sys.argv[2:] if not a.startswith("--")]
    template = positional[0] if len(positional) > 0 else "T1: Research"
    goal = positional[1] if len(positional) > 1 else "待填写"
    ssot = "--ssot" in sys.argv

    ok = bootstrap(work_dir, template=template, goal=goal, ssot=ssot)
    sys.exit(0 if ok else 1)
