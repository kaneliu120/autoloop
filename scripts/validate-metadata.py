#!/usr/bin/env python3
"""SKILL.md 元数据校验工具

用法:
  validate-metadata.py --name "autoloop" --description "..."
  validate-metadata.py --file SKILL.md
"""

import re
import sys


def parse_yaml_frontmatter(content):
    """从 Markdown 文件解析 YAML frontmatter（简易解析，无需 PyYAML）。"""
    if not content.startswith("---"):
        return {}
    end = content.find("\n---", 3)
    if end < 0:
        return {}
    block = content[4:end].strip()
    data = {}
    for line in block.split("\n"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" in line:
            key, _, val = line.partition(":")
            data[key.strip()] = val.strip().strip('"').strip("'")
    return data


def validate(name, description, full_content=None):
    """校验元数据，返回 (ok: bool, errors: list[str])。"""
    errors = []

    # --- name 校验 ---
    if not name:
        errors.append("name: 缺失")
    else:
        if len(name) < 1 or len(name) > 64:
            errors.append(f"name: 长度必须 1-64 字符，当前 {len(name)}")
        if not re.match(r'^[a-z0-9]+(-[a-z0-9]+)*$', name):
            errors.append(
                "name: 只允许小写字母+数字+连字符，不允许连续连字符，"
                f"当前值: '{name}'"
            )
        if '--' in name:
            errors.append(f"name: 不允许连续连字符，当前值: '{name}'")

    # --- description 校验 ---
    if not description:
        errors.append("description: 缺失")
    else:
        if len(description) >= 1024:
            errors.append(
                f"description: 必须 < 1024 字符，当前 {len(description)}"
            )
        # 人称代词检查
        person_patterns = [
            (r'\bI\b', "第一人称 'I'"),
            (r'\bme\b', "第一人称 'me'"),
            (r'\bmy\b', "第一人称 'my'"),
            (r'\byou\b', "第二人称 'you'"),
            (r'\byour\b', "第二人称 'your'"),
            (r'我', "第一人称 '我'"),
            (r'你', "第二人称 '你'"),
        ]
        for pattern, label in person_patterns:
            if re.search(pattern, description):
                errors.append(f"description: 包含{label}（禁止第一/第二人称）")

    # --- 触发器检查（仅当有完整内容时）---
    if full_content is not None:
        has_positive = bool(re.search(
            r'[Uu]se\s+when|适用场景|正向触发|positive\s+trigger',
            full_content, re.IGNORECASE,
        ))
        has_negative = bool(re.search(
            r'[Dd]o\s+not\s+use|不适用|负向触发|negative\s+trigger',
            full_content, re.IGNORECASE,
        ))
        if not has_positive:
            errors.append("触发器: 缺少正向触发条件（Use when / 适用场景）")
        if not has_negative:
            errors.append("触发器: 缺少负向触发条件（Do not use / 不适用）")

    return len(errors) == 0, errors


def main():
    name = None
    description = None
    file_path = None
    full_content = None

    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == '--name' and i + 1 < len(args):
            name = args[i + 1]
            i += 2
        elif args[i] == '--description' and i + 1 < len(args):
            description = args[i + 1]
            i += 2
        elif args[i] == '--file' and i + 1 < len(args):
            file_path = args[i + 1]
            i += 2
        else:
            i += 1

    if file_path:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                full_content = f.read()
        except FileNotFoundError:
            print(f"ERROR: 文件不存在: {file_path}", file=sys.stderr)
            sys.exit(1)

        meta = parse_yaml_frontmatter(full_content)
        name = name or meta.get('name', '')
        description = description or meta.get('description', '')

    if not name and not description and not file_path:
        print(__doc__)
        sys.exit(1)

    ok, errors = validate(name, description, full_content)

    if ok:
        print("SUCCESS: Metadata valid")
        sys.exit(0)
    else:
        for e in errors:
            print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
