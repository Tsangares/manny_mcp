#!/bin/bash
# Manny MCP - Master startup script
# Orchestrates: Weston display + Dashboard + RuneLite

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUNELITE_ROOT="/home/wil/Desktop/runelite"

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
# echo "[2/3] Starting Manny MCP Dashboard..."
# "$SCRIPT_DIR/start_dashboard.sh"
# echo ""

# Start RuneLite
echo "[2/2] Starting RuneLite client..."

# Load .env for Jagex launcher credentials
if [ -f "$SCRIPT_DIR/.env" ]; then
    set -a
    source "$SCRIPT_DIR/.env"
    set +a
    echo "Loaded credentials from .env"
fi

cd "$RUNELITE_ROOT"
DISPLAY=:2 JX_CHARACTER_ID="$JX_CHARACTER_ID" JX_DISPLAY_NAME="$JX_DISPLAY_NAME" JX_SESSION_ID="$JX_SESSION_ID" \
    nohup mvn exec:java -pl runelite-client \
    -Dexec.mainClass=net.runelite.client.RuneLite \
    -Dsun.java2d.uiScale=2.0 \
    > /tmp/runelite.log 2>&1 &
RUNELITE_PID=$!
echo "RuneLite started with PID: $RUNELITE_PID"
echo ""

echo "======================================"
echo "All services started successfully!"
echo "======================================"
echo ""
echo "Services:"
echo "  Weston/XWayland: DISPLAY=:2"
echo "  Dashboard: http://localhost:8080"
echo "  RuneLite: PID $RUNELITE_PID (log: /tmp/runelite.log)"
echo ""
echo "To stop services:"
echo "  pkill -f 'weston --socket=wayland-1'"
echo "  pkill -f 'python.*dashboard.py'"
echo "  pkill -f 'runelite'"
echo ""
