#!/bin/bash
# Start RuneLite in a nested Cage compositor
# Cage is minimal - just shows the app fullscreen with GPU acceleration
#
# Usage: ./start_screen_cage.sh
# RuneLite will be on DISPLAY=:2

set -e

# Kill any existing displays
pkill -f "cage.*xwayland" 2>/dev/null || true
pkill -f "weston.*wayland-1" 2>/dev/null || true
pkill -f "Xvfb :2" 2>/dev/null || true
pkill -f "Xephyr :2" 2>/dev/null || true
sleep 1

echo "Starting Cage compositor for RuneLite..."

# Cage runs a single app fullscreen
# We'll use a dummy app first, then you can attach RuneLite to :2
# -s means disable screen saver
# -d means enable debug logging
WAYLAND_DISPLAY=wayland-0 cage -s -- bash -c '
    # Wait for XWayland to be ready
    while [ ! -S /tmp/.X11-unix/X2 ]; do sleep 0.1; done
    echo "Cage ready on DISPLAY=:2"
    # Keep cage alive - run your RuneLite here via DISPLAY=:2
    sleep infinity
' &

sleep 2

if [ -S /tmp/.X11-unix/X2 ]; then
    echo "✓ Cage started successfully!"
    echo "  XWayland on DISPLAY=:2 (GPU accelerated)"
    echo ""
    echo "To run RuneLite: DISPLAY=:2 <your maven command>"
else
    echo "✗ Failed to start Cage/XWayland"
    exit 1
fi
