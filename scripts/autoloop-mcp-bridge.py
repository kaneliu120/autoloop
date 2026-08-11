#!/usr/bin/env python3
"""AutoLoop MCP Bridge — Codex MCP configuration helper.

Codex launches configured MCP servers itself. This helper reports the local
Codex configuration command and does not impersonate an MCP client:
1. platform detection
2. the operator command used to list configured MCP servers
3. a clear refusal for direct JSON-RPC invocation, which belongs to Codex

Usage:
  autoloop-mcp-bridge.py discover          # List available MCP tools
  autoloop-mcp-bridge.py call <tool> <args> # Call an MCP tool
  autoloop-mcp-bridge.py detect-platform    # Detect the current platform
"""
import json
import shutil
import sys


def detect_platform():
    """Report whether the Codex CLI is available to manage MCP servers."""
    return "codex" if shutil.which("codex") else "unknown"


def discover_mcp_tools():
    """Report the Codex command that lists configured MCP servers."""
    platform = detect_platform()
    print(json.dumps({
        "platform": platform,
        "discovery_command": "codex mcp list",
        "bridge_required": False,
        "message": "Configure AutoLoop with codex mcp add; Codex owns MCP tool discovery.",
    }))


def call_mcp_tool(tool_name, args_json):
    """Refuse direct invocation; Codex must own the MCP connection."""
    print(json.dumps({
        "status": "unsupported",
        "message": "Use the configured AutoLoop MCP server from Codex; this helper does not proxy JSON-RPC.",
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
