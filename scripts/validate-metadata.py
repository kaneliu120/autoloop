#!/usr/bin/env python3
"""SKILL.md metadata validation tool

Usage:
  validate-metadata.py --name "autoloop" --description "..."
  validate-metadata.py --file SKILL.md
"""

import re
import sys


def parse_yaml_frontmatter(content):
    """Parse YAML frontmatter from a Markdown file (simple parser, no PyYAML required)."""
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
    """Validate metadata and return (ok: bool, errors: list[str])."""
    errors = []

    # --- name validation ---
    if not name:
        errors.append("name: missing")
    else:
        if len(name) < 1 or len(name) > 64:
            errors.append(f"name: must be 1-64 characters long, got {len(name)}")
        if not re.match(r'^[a-z0-9]+(-[a-z0-9]+)*$', name):
            errors.append(
                "name: only lowercase letters, digits, and hyphens are allowed; "
                f"current value: '{name}'"
            )
        if '--' in name:
            errors.append(f"name: consecutive hyphens are not allowed, current value: '{name}'")

    # --- description validation ---
    if not description:
        errors.append("description: missing")
    else:
        if len(description) >= 1024:
            errors.append(
                f"description: must be < 1024 characters, got {len(description)}"
            )
        # Pronoun checks
        person_patterns = [
            (r'\bI\b', "first person 'I'"),
            (r'\bme\b', "first person 'me'"),
            (r'\bmy\b', "first person 'my'"),
            (r'\byou\b', "second person 'you'"),
            (r'\byour\b', "second person 'your'"),
            ("\u6211", "first person 'I'"),
            ("\u4f60", "second person 'you'"),
        ]
        for pattern, label in person_patterns:
            if re.search(pattern, description):
                errors.append(f"description: contains {label} (first/second person is forbidden)")

    # --- Trigger checks (only when full content is available) ---
    if full_content is not None:
        has_positive = bool(re.search(
            r'[Uu]se\s+when|use case|positive trigger|positive\s+trigger',
            full_content, re.IGNORECASE,
        ))
        has_negative = bool(re.search(
            r'[Dd]o\s+not\s+use|do not use|negative trigger|negative\s+trigger',
            full_content, re.IGNORECASE,
        ))
        if not has_positive:
            errors.append("triggers: missing positive trigger condition (Use when / use case)")
        if not has_negative:
            errors.append("triggers: missing negative trigger condition (Do not use / do not use)")

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
            print(f"ERROR: File does not exist: {file_path}", file=sys.stderr)
            sys.exit(1)

        meta = parse_yaml_frontmatter(full_content)
        name = name or meta.get('name', '')
        description = description or meta.get('description', '')

    if not name and not description and not file_path:
        print(__doc__)
        sys.exit(1)

    ok, errors = validate(name, description, full_content)

    if ok:
        print("SUCCESS: metadata valid")
        sys.exit(0)
    else:
        for e in errors:
            print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
