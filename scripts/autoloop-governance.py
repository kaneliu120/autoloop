#!/usr/bin/env python3
"""AutoLoop Governance — 企业级治理

提供企业环境下的治理能力：
1. Secrets 检测：扫描输出中的敏感信息（API key、密码、token）
2. 策略违规检测：检查 agent 行为是否违反组织策略
3. 审批流：记录所有需要审批的操作及其状态
4. 角色权限：定义不同用户角色的操作权限

用法:
  autoloop-governance.py scan-secrets <file>        # 扫描文件中的 secrets
  autoloop-governance.py check-policy <action>      # 检查操作是否违反策略
  autoloop-governance.py approval-log [--pending]   # 查看审批日志
  autoloop-governance.py role-check <user> <action> # 检查用户权限
"""
import os
import sys
import json
import re
import time

# Secrets 检测模式
SECRET_PATTERNS = [
    (r'(?i)(api[_-]?key|apikey)\s*[:=]\s*["\']?[\w\-]{20,}', "API Key"),
    (r'(?i)(secret|password|passwd|pwd)\s*[:=]\s*["\']?[^\s"\']{8,}', "Password/Secret"),
    (r'(?i)(token|bearer)\s*[:=]\s*["\']?[\w\-\.]{20,}', "Token"),
    (r'(?i)(aws_access_key_id)\s*[:=]\s*[A-Z0-9]{20}', "AWS Key"),
    (r'sk-[a-zA-Z0-9]{20,}', "OpenAI API Key"),
    (r'xai-[a-zA-Z0-9]{20,}', "xAI API Key"),
    (r'ghp_[a-zA-Z0-9]{36,}', "GitHub Token"),
]

# 组织策略（可通过配置文件覆盖）
DEFAULT_POLICIES = {
    "max_cost_per_task_usd": 10.0,
    "require_approval_for_deploy": True,
    "require_approval_for_delete": True,
    "allowed_external_apis": ["openai", "anthropic", "google", "xai"],
    "max_concurrent_tasks": 5,
}

# 角色权限矩阵
ROLE_PERMISSIONS = {
    "admin": {"read", "write", "execute", "deploy", "delete", "configure", "approve"},
    "developer": {"read", "write", "execute"},
    "reviewer": {"read", "approve"},
    "viewer": {"read"},
}


def scan_secrets(file_path):
    """扫描文件中的 secrets"""
    if not os.path.exists(file_path):
        print(json.dumps({"error": f"File not found: {file_path}"}))
        return []

    with open(file_path) as f:
        content = f.read()

    findings = []
    for pattern, secret_type in SECRET_PATTERNS:
        matches = re.finditer(pattern, content)
        for m in matches:
            matched_text = m.group()
            if len(matched_text) > 14:
                redacted = matched_text[:10] + "..." + matched_text[-4:]
            else:
                redacted = "***"
            findings.append({
                "type": secret_type,
                "line": content[:m.start()].count("\n") + 1,
                "matched": redacted,
            })

    result = {"file": file_path, "secrets_found": len(findings), "findings": findings}
    if findings:
        _log_governance_event("secrets_detected", result)
    print(json.dumps(result, indent=2))
    return findings


def check_policy(action, context=None):
    """检查操作是否违反组织策略"""
    policies = _load_policies()
    violations = []

    if action == "deploy" and policies.get("require_approval_for_deploy"):
        violations.append("部署操作需要审批（require_approval_for_deploy=true）")
    if action == "delete" and policies.get("require_approval_for_delete"):
        violations.append("删除操作需要审批（require_approval_for_delete=true）")

    result = {"action": action, "violations": violations, "compliant": len(violations) == 0}
    if violations:
        _log_governance_event("policy_violation", result)
    print(json.dumps(result))
    return len(violations) == 0


def role_check(user, action):
    """检查用户角色权限"""
    role = _get_user_role(user)
    permissions = ROLE_PERMISSIONS.get(role, set())
    allowed = action in permissions
    result = {"user": user, "role": role, "action": action, "allowed": allowed}
    if not allowed:
        _log_governance_event("permission_denied", result)
    print(json.dumps(result))
    return allowed


def _load_policies():
    """加载组织策略（配置文件覆盖默认）"""
    config_path = os.path.expanduser("~/.autoloop/governance/policies.json")
    if os.path.exists(config_path):
        with open(config_path) as f:
            return {**DEFAULT_POLICIES, **json.load(f)}
    return DEFAULT_POLICIES


def _get_user_role(user):
    """获取用户角色（配置文件或默认 admin）"""
    roles_path = os.path.expanduser("~/.autoloop/governance/roles.json")
    if os.path.exists(roles_path):
        with open(roles_path) as f:
            roles = json.load(f)
            return roles.get(user, "viewer")
    return "admin"  # 单用户默认 admin


def _log_governance_event(event_type, details):
    """记录治理审计日志"""
    log_dir = os.path.expanduser("~/.autoloop/governance/")
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "governance-audit.jsonl")
    entry = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "event": event_type,
        "details": details,
    }
    with open(log_file, "a") as f:
        f.write(json.dumps(entry) + "\n")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "scan-secrets" and len(sys.argv) >= 3:
        scan_secrets(sys.argv[2])
    elif cmd == "check-policy" and len(sys.argv) >= 3:
        sys.exit(0 if check_policy(sys.argv[2]) else 1)
    elif cmd == "role-check" and len(sys.argv) >= 4:
        sys.exit(0 if role_check(sys.argv[2], sys.argv[3]) else 1)
    elif cmd == "approval-log":
        log_file = os.path.expanduser("~/.autoloop/governance/governance-audit.jsonl")
        if os.path.exists(log_file):
            with open(log_file) as f:
                for line in f.readlines()[-20:]:
                    print(line.strip())
        else:
            print("No governance audit log found.")
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    main()
