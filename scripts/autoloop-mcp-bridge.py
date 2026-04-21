#!/usr/bin/env python3
"""AutoLoop MCP Bridge — cross-platform MCP tool discovery and invocation

In non-Claude Code environments (Gemini CLI, Codex CLI, etc.),
subagents cannot use the host's MCP tools directly. This bridge provides:
1. MCP tool discovery: list available MCP tools
2. MCP tool invocation: call MCP tools via stdin/stdout JSON-RPC
3. Platform detection: detect the current IDE environment and decide whether a bridge is needed

Usage:
  autoloop-mcp-bridge.py discover          # List available MCP tools
  autoloop-mcp-bridge.py call <tool> <args> # Call an MCP tool
  autoloop-mcp-bridge.py detect-platform    # Detect the current platform
"""
import os
import sys
import json


def detect_platform():
    """Detect the current IDE platform."""
    if os.environ.get("CLAUDE_CODE"):
        return "claude-code"  # Native support; no bridge needed
    elif os.environ.get("GEMINI_CLI"):
        return "gemini-cli"
    elif os.environ.get("CODEX_CLI"):
        return "codex-cli"
    else:
        return "unknown"


def discover_mcp_tools():
    """Discover available MCP tools."""
    platform = detect_platform()
    if platform == "claude-code":
        print(json.dumps({"status": "native", "message": "Claude Code supports MCP natively; no bridge needed"}))
        return

    # Non-Claude Code environment: read MCP configuration
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
    """Call an MCP tool (reserved interface)."""
    print(json.dumps({
        "status": "not_implemented",
        "message": "The MCP call bridge will be implemented when needed",
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
