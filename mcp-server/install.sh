#!/bin/bash
# AutoLoop MCP Server installation script for Codex

set -euo pipefail

echo "=== AutoLoop MCP Server Installation ==="
echo ""

# Check Python and Codex
if ! command -v python3 &> /dev/null; then
    echo "ERROR: python3 is not installed"
    exit 1
fi
if ! command -v codex &> /dev/null; then
    echo "ERROR: Codex CLI is not installed or not on PATH"
    exit 1
fi

ALLOW_WRITE=0
if [ "${1:-}" = "--allow-write" ]; then
    ALLOW_WRITE=1
    shift
fi

if [ "$#" -ne 1 ]; then
    echo "Usage: bash mcp-server/install.sh [--allow-write] /absolute/path/to/trusted-workspaces"
    exit 1
fi

if [ ! -d "$1" ]; then
    echo "ERROR: trusted workspace root does not exist: $1"
    exit 1
fi

WORKDIR_ROOT="$(cd "$1" && pwd -P)"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"

# Install MCP into an isolated environment, not the user's global Python.
echo "1. Creating the isolated MCP environment..."
python3 -m venv "$VENV_DIR"
"$VENV_DIR/bin/python" -m pip install --upgrade pip
"$VENV_DIR/bin/python" -m pip install "mcp>=1.0.0,<2.0.0"
echo "   ✓ mcp installed in $VENV_DIR"

echo "2. Verifying the server..."
"$VENV_DIR/bin/python" -c "import mcp; print(f'   ✓ mcp {mcp.__version__}')"

echo ""
echo "3. Registering the protected server with Codex..."
MCP_ARGS=(mcp add autoloop --env "AUTOLOOP_MCP_WORKDIR_ROOT=$WORKDIR_ROOT")
if [ "$ALLOW_WRITE" -eq 1 ]; then
    MCP_ARGS+=(--env "AUTOLOOP_MCP_ALLOW_WRITE=1")
fi
MCP_ARGS+=(-- "$VENV_DIR/bin/python" "$SCRIPT_DIR/server.py")
codex "${MCP_ARGS[@]}"
echo "   ✓ registered; verify with: codex mcp list"
echo ""
if [ "$ALLOW_WRITE" -eq 1 ]; then
    echo "Write tools are enabled for the reviewed workspace root."
else
    echo "Write tools remain disabled. Reinstall with --allow-write only after review."
fi
echo "Experience-registry writes also require AUTOLOOP_MCP_EXPERIENCE_REGISTRY_PATH"
echo "inside the trusted root."
echo "See mcp-server/CODEX_SETUP.md for that optional step."
echo "=== Installation Complete ==="
