#!/bin/bash
# AutoLoop MCP Server installation script

set -e

echo "=== AutoLoop MCP Server Installation ==="
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "ERROR: python3 is not installed"
    exit 1
fi

# Install the mcp package
echo "1. Installing the mcp package..."
python3 -m pip install "mcp>=1.0.0,<2.0.0"
echo "   ✓ mcp installed"

# Verify the server can start
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
echo "2. Verifying the server..."
python3 -c "import mcp; print(f'   ✓ mcp {mcp.__version__}')" 2>/dev/null || echo "   ⚠ Could not import mcp"

# Print configuration guidance
SKILL_DIR="$(dirname "$SCRIPT_DIR")"
echo ""
echo "3. Add the following configuration to your Claude Code MCP settings:"
echo ""
echo "   File: ~/.claude/settings.json or .claude/settings.json"
echo ""
echo '   "mcpServers": {'
echo '     "autoloop": {'
echo '       "command": "python3",'
echo "       \"args\": [\"$SCRIPT_DIR/server.py\"]"
echo '     }'
echo '   }'
echo ""
echo "   Or run: claude mcp add autoloop python3 $SCRIPT_DIR/server.py"
echo ""
echo "=== Installation Complete ==="
