#!/usr/bin/env python3
"""AutoLoop Bootstrap 初始化工具 — 创建4个工作文件"""

import sys
import os
import datetime

TSV_HEADER = "iteration\tphase\tstatus\tdimension\tmetric_value\tdelta\tstrategy_id\taction_summary\tside_effect\tevidence_ref\tunit_id\tprotocol_version\tscore_variance\tconfidence\tdetails"


def create_plan(work_dir, task_id, template, goal):
    path = os.path.join(work_dir, "autoloop-plan.md")
    now = datetime.datetime.now().isoformat()
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

| 维度 | 目标分数 | 当前分数 | 目标阈值 | 状态 |
|------|---------|---------|---------|------|
| — | — | 0 | — | 准备开始 |

---

## 迭代预算

| 字段 | 值 |
|------|-----|
| 最大轮次 | 见 protocols/parameters.md |
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
    path = os.path.join(work_dir, "autoloop-findings.md")
    now = datetime.datetime.now().isoformat()
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

---

## 策略评估（REFLECT — 累积追踪）

| 轮次 | strategy_id | 策略 | 效果评分(1-5) | 分数变化 | 保持/避免/待验证 | 原因 |
|------|-------------|------|--------------|---------|-----------------|------|
| — | — | — | — | — | — | — |
"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return path


def create_progress(work_dir, task_id, template):
    path = os.path.join(work_dir, "autoloop-progress.md")
    content = f"""# AutoLoop Progress — 进度追踪

**任务 ID**：{task_id}
**模板**：{template}

## 质量门禁总览

| 维度 | 基线 | 第1轮 | 第2轮 | 第3轮 | 目标 |
|------|------|-------|-------|-------|------|
| — | 0 | — | — | — | — |
"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return path


def create_tsv(work_dir):
    path = os.path.join(work_dir, "autoloop-results.tsv")
    with open(path, "w", encoding="utf-8") as f:
        f.write(TSV_HEADER + "\n")
    return path


def bootstrap(work_dir, task_id=None, template="T1: Research", goal="待填写"):
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

    print(f"OK: Bootstrap完成，已创建{len(files)}个文件:")
    for f in files:
        print(f"  - {os.path.basename(f)}")
    print(f"\n任务ID: {task_id}")
    print(f"模板: {template}")
    print(f"工作目录: {work_dir}")
    return True


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法:")
        print("  autoloop-init.py <工作目录> [模板] [目标]")
        print("  autoloop-init.py /path/to/project 'T1: Research' '调研AI自主迭代工具'")
        sys.exit(1)

    work_dir = sys.argv[1]
    template = sys.argv[2] if len(sys.argv) > 2 else "T1: Research"
    goal = sys.argv[3] if len(sys.argv) > 3 else "待填写"

    ok = bootstrap(work_dir, template=template, goal=goal)
    sys.exit(0 if ok else 1)
