#!/usr/bin/env python3
"""AutoLoop Security — 跨平台安全管线

提供三层安全保护（仅在非 Claude Code 环境中激活）：
1. 编译时检查：工具白名单验证
2. 运行时检查：敏感路径检测 + 写操作拦截
3. 审计日志：所有安全事件记录

用法:
  autoloop-security.py check-tool <tool_name>     # 检查工具是否在白名单中
  autoloop-security.py check-path <file_path>     # 检查路径是否敏感
  autoloop-security.py check-write <file_path>    # 检查写操作是否需要审批
  autoloop-security.py audit-log [--tail N]       # 查看安全审计日志
"""
import os, sys, json, time

# 工具白名单（ACT 阶段允许 subagent 使用的工具）
TOOL_ALLOWLIST = {
    "read_file", "write_file", "edit_file", "glob", "grep", "ls",
    "bash", "web_search", "task",
}

# 敏感路径模式（不允许 subagent 读写）
SENSITIVE_PATTERNS = [
    ".env", ".env.production", "credentials", "secrets",
    "id_rsa", "id_ed25519", ".ssh/", "token", "api_key",
    "gate-manifest.json",  # P1-04 config-protection
]

# 需要预审批的写操作路径模式
APPROVAL_REQUIRED_PATTERNS = [
    "*.py",  # Python 脚本修改需要审批
    "*.sh",  # Shell 脚本修改需要审批
    "SKILL.md", "CLAUDE.md", "AGENTS.md",  # 配置文件修改需要审批
]


def check_tool(tool_name):
    """检查工具是否在白名单中"""
    allowed = tool_name in TOOL_ALLOWLIST
    result = {"tool": tool_name, "allowed": allowed}
    if not allowed:
        result["message"] = f"工具 '{tool_name}' 不在 ACT 阶段白名单中"
        _log_event("tool_blocked", result)
    print(json.dumps(result))
    return allowed


def check_path(file_path):
    """检查路径是否敏感"""
    path_lower = file_path.lower()
    for pattern in SENSITIVE_PATTERNS:
        if pattern.lower() in path_lower:
            result = {"path": file_path, "sensitive": True, "matched_pattern": pattern}
            _log_event("sensitive_path_access", result)
            print(json.dumps(result))
            return True
    print(json.dumps({"path": file_path, "sensitive": False}))
    return False


def check_write(file_path):
    """检查写操作是否需要预审批"""
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
    """记录安全审计日志"""
    log_dir = os.path.expanduser("~/.autoloop/security/")
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "audit.jsonl")
    entry = {"timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"), "event": event_type, "details": details}
    with open(log_file, "a") as f:
        f.write(json.dumps(entry) + "\n")


def audit_log(tail=20):
    """查看安全审计日志"""
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
                tail = int(sys.argv[idx + 1])
        audit_log(tail)
    else:
        print(f"Unknown command or missing args: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    main()
