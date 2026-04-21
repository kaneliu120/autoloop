#!/usr/bin/env python3
"""AutoLoop Security — cross-platform security pipeline

Provides three layers of protection (enabled only outside Claude Code):
1. Compile-time checks: tool allowlist validation
2. Runtime checks: sensitive path detection + write interception
3. Audit logs: record all security events

Usage:
  autoloop-security.py check-tool <tool_name>     # Check whether a tool is allowlisted
  autoloop-security.py check-path <file_path>     # Check whether a path is sensitive
  autoloop-security.py check-write <file_path>    # Check whether a write needs approval
  autoloop-security.py audit-log [--tail N]       # View the security audit log
"""
import os, sys, json, time

# Tool allowlist (tools subagents may use during ACT)
TOOL_ALLOWLIST = {
    "read_file", "write_file", "edit_file", "glob", "grep", "ls",
    "bash", "web_search", "task",
}

# Sensitive path detection (two classes to avoid substring false positives such as "tokenizer_output" matching "token")
# Exact file-name matching (using os.path.basename)
SENSITIVE_EXACT_FILENAMES = {
    ".env", ".env.production", ".env.local", ".env.staging",
    "id_rsa", "id_ed25519", "id_ecdsa",
    "credentials.json", "secrets.json", "token.json",
    "api_key.txt", "api_keys.json",
    "gate-manifest.json",  # P1-04 config-protection
}
# Path-segment matching (checks whether the path contains these directories)
SENSITIVE_PATH_SEGMENTS = {".ssh", "secrets", ".credentials"}

# Write-path patterns that require pre-approval
APPROVAL_REQUIRED_PATTERNS = [
    "*.py",  # Python script changes require approval
    "*.sh",  # Shell script changes require approval
    "SKILL.md", "CLAUDE.md", "AGENTS.md",  # Config file changes require approval
]


def check_tool(tool_name):
    """Check whether a tool is in the allowlist."""
    allowed = tool_name in TOOL_ALLOWLIST
    result = {"tool": tool_name, "allowed": allowed}
    if not allowed:
        result["message"] = f"Tool '{tool_name}' is not in the ACT allowlist"
        _log_event("tool_blocked", result)
    print(json.dumps(result))
    return allowed


def check_path(file_path):
    """Check whether a path is sensitive (exact filename match + path-segment match)."""
    basename = os.path.basename(file_path).lower()
    # Exact filename match
    for name in SENSITIVE_EXACT_FILENAMES:
        if basename == name.lower():
            result = {"path": file_path, "sensitive": True, "matched_pattern": name, "match_type": "exact_filename"}
            _log_event("sensitive_path_access", result)
            print(json.dumps(result))
            return True
    # Path-segment match (directory names)
    path_parts = set(p.lower() for p in file_path.replace("\\", "/").split("/"))
    for seg in SENSITIVE_PATH_SEGMENTS:
        if seg.lower() in path_parts:
            result = {"path": file_path, "sensitive": True, "matched_pattern": seg, "match_type": "path_segment"}
            _log_event("sensitive_path_access", result)
            print(json.dumps(result))
            return True
    print(json.dumps({"path": file_path, "sensitive": False}))
    return False


def check_write(file_path):
    """Check whether a write operation requires pre-approval."""
    import fnmatch
    for pattern in APPROVAL_REQUIRED_PATTERNS:
        if fnmatch.fnmatch(os.path.basename(file_path), pattern):
            result = {"path": file_path, "approval_required": True, "matched_pattern": pattern}
            _log_event("write_approval_required", result)
            print(json.dumps(result))
            return True
    print(json.dumps({"path": file_path, "approval_required": False}))
    return False


def _log_event(event_type, details):
    """Record a security audit log entry."""
    log_dir = os.path.expanduser("~/.autoloop/security/")
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "audit.jsonl")
    entry = {"timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"), "event": event_type, "details": details}
    with open(log_file, "a") as f:
        f.write(json.dumps(entry) + "\n")


def audit_log(tail=20):
    """View the security audit log."""
    log_file = os.path.expanduser("~/.autoloop/security/audit.jsonl")
    if not os.path.exists(log_file):
        print("No audit log found.")
        return
    with open(log_file) as f:
        lines = f.readlines()
    for line in lines[-tail:]:
        print(line.strip())


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    cmd = sys.argv[1]
    if cmd == "check-tool" and len(sys.argv) >= 3:
        sys.exit(0 if check_tool(sys.argv[2]) else 1)
    elif cmd == "check-path" and len(sys.argv) >= 3:
        sys.exit(1 if check_path(sys.argv[2]) else 0)
    elif cmd == "check-write" and len(sys.argv) >= 3:
        sys.exit(1 if check_write(sys.argv[2]) else 0)
    elif cmd == "audit-log":
        tail = 20
        if "--tail" in sys.argv:
            idx = sys.argv.index("--tail")
            if idx + 1 < len(sys.argv):
                try:
                    tail = int(sys.argv[idx + 1])
                except ValueError:
                    tail = 20
        audit_log(tail)
    else:
        print(f"Unknown command or missing args: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    main()
