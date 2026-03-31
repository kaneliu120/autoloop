#!/usr/bin/env python3
"""AutoLoop MCP Bridge — 跨平台 MCP 工具发现与调用

在非 Claude Code 环境中（Gemini CLI、Codex CLI 等），
subagent 不能直接使用宿主的 MCP 工具。此桥接脚本提供：
1. MCP 工具发现：列出可用的 MCP 工具
2. MCP 工具调用：通过 stdin/stdout JSON-RPC 协议调用 MCP 工具
3. 平台检测：自动检测当前 IDE 环境，决定是否需要桥接

用法:
  autoloop-mcp-bridge.py discover          # 列出可用 MCP 工具
  autoloop-mcp-bridge.py call <tool> <args> # 调用 MCP 工具
  autoloop-mcp-bridge.py detect-platform    # 检测当前平台
"""
import os
import sys
import json


def detect_platform():
    """检测当前 IDE 平台"""
    if os.environ.get("CLAUDE_CODE"):
        return "claude-code"  # 原生支持，无需桥接
    elif os.environ.get("GEMINI_CLI"):
        return "gemini-cli"
    elif os.environ.get("CODEX_CLI"):
        return "codex-cli"
    else:
        return "unknown"


def discover_mcp_tools():
    """发现可用的 MCP 工具"""
    platform = detect_platform()
    if platform == "claude-code":
        print(json.dumps({"status": "native", "message": "Claude Code 原生支持 MCP，无需桥接"}))
        return

    # 非 Claude Code 环境：读取 MCP 配置
    mcp_config_paths = [
        os.path.expanduser("~/.config/claude-code/mcp.json"),
        ".mcp.json",
        "mcp.json",
    ]
    tools = []
    for path in mcp_config_paths:
        if os.path.exists(path):
            with open(path) as f:
                config = json.load(f)
                tools.extend(config.get("tools", []))

    print(json.dumps({"platform": platform, "tools": tools, "bridge_required": True}))


def call_mcp_tool(tool_name, args_json):
    """调用 MCP 工具（预留接口）"""
    print(json.dumps({
        "status": "not_implemented",
        "message": "MCP call bridge 将在需要时实现",
        "tool": tool_name,
        "args": args_json,
    }))


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd == "discover":
        discover_mcp_tools()
    elif cmd == "detect-platform":
        print(json.dumps({"platform": detect_platform()}))
    elif cmd == "call":
        tool_name = sys.argv[2] if len(sys.argv) > 2 else None
        args_json = sys.argv[3] if len(sys.argv) > 3 else "{}"
        if not tool_name:
            print("Usage: autoloop-mcp-bridge.py call <tool_name> [args_json]", file=sys.stderr)
            sys.exit(1)
        call_mcp_tool(tool_name, args_json)
    else:
        print(f"Unknown command: {cmd}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
