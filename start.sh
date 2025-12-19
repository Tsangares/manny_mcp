#!/bin/bash
# Manny MCP - Master startup script
# Orchestrates: Weston display + Dashboard

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "======================================"
echo "Manny MCP - Starting all services"
echo "======================================"
echo ""

# Start virtual display (Weston with XWayland)
echo "[1/2] Starting Weston virtual display..."
"$SCRIPT_DIR/start_screen.sh"
echo ""

# Wait for display to be ready
echo "Waiting for display to initialize..."
sleep 3

# Start dashboard
echo "[2/2] Starting Manny MCP Dashboard..."
"$SCRIPT_DIR/start_dashboard.sh"
echo ""

echo "======================================"
echo "✓ All services started successfully!"
echo "======================================"
echo ""
echo "Services:"
echo "  • Weston/XWayland: DISPLAY=:2"
echo "  • Dashboard: http://localhost:8080"
echo ""
echo "Next steps:"
echo "  1. Update Claude Code MCP config to use:"
echo "     /home/wil/manny-mcp/server_with_dashboard.py"
echo "  2. Start RuneLite in Claude Code (it will appear on :2)"
echo "  3. Monitor at http://localhost:8080"
echo ""
echo "To stop services:"
echo "  pkill -f 'weston --socket=wayland-1'"
echo "  pkill -f 'python.*dashboard.py'"
echo ""
