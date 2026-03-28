#!/bin/bash
# AutoLoop MCP Server 安装脚本

set -e

echo "=== AutoLoop MCP Server 安装 ==="
echo ""

# 检查 Python
if ! command -v python3 &> /dev/null; then
    echo "ERROR: python3 未安装"
    exit 1
fi

# 安装 mcp 包
echo "1. 安装 mcp 包..."
pip install mcp 2>/dev/null || pip3 install mcp
echo "   ✓ mcp 已安装"

# 验证 server 可启动
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
echo "2. 验证 server..."
python3 -c "import mcp; print(f'   ✓ mcp {mcp.__version__}')" 2>/dev/null || echo "   ⚠ 无法导入 mcp"

# 输出配置指引
SKILL_DIR="$(dirname "$SCRIPT_DIR")"
echo ""
echo "3. 将以下配置添加到 Claude Code MCP 设置："
echo ""
echo "   文件: ~/.claude/settings.json 或 .claude/settings.json"
echo ""
echo '   "mcpServers": {'
echo '     "autoloop": {'
echo '       "command": "python3",'
echo "       \"args\": [\"$SCRIPT_DIR/server.py\"]"
echo '     }'
echo '   }'
echo ""
echo "   或运行: claude mcp add autoloop python3 $SCRIPT_DIR/server.py"
echo ""
echo "=== 安装完成 ==="
