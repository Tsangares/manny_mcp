#!/bin/bash
# Start Manny MCP Dashboard - kills existing instances and runs detached

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="$SCRIPT_DIR/venv"

# Kill any existing dashboard instances
echo "Stopping any existing dashboard instances..."
pkill -f "python.*dashboard.py" 2>/dev/null || true
pkill -f "uvicorn.*dashboard" 2>/dev/null || true
sleep 1

# Check if venv exists, if not create it
if [ ! -d "$VENV" ]; then
    echo "Creating Python venv..."
    python3 -m venv "$VENV"
fi

# Install/update dashboard dependencies
echo "Checking dashboard dependencies..."
"$VENV/bin/pip" install -q -r "$SCRIPT_DIR/requirements-dashboard.txt"

# Start dashboard in background
echo "Starting Manny MCP Dashboard..."
"$VENV/bin/python3" "$SCRIPT_DIR/dashboard.py" > /tmp/manny_dashboard.log 2>&1 &
DASHBOARD_PID=$!

sleep 2

# Verify it's running
if ps -p $DASHBOARD_PID > /dev/null; then
    echo "✓ Dashboard started successfully (PID: $DASHBOARD_PID)"
    echo "  Access at: http://localhost:8080"
    echo "  Logs: tail -f /tmp/manny_dashboard.log"
else
    echo "✗ Dashboard failed to start. Check logs:"
    tail /tmp/manny_dashboard.log
    exit 1
fi
