#!/bin/bash
# Start a nested Wayland compositor (weston) for RuneLite with GPU support
#
# CPU Usage comparison:
#   Xvfb/Xephyr (software): ~362% CPU (multiple cores maxed)
#   Weston + XWayland (GPU): ~37% CPU
#
# Usage: ./start_screen.sh
# Then run RuneLite with: DISPLAY=:2 <command>

# Kill any existing virtual displays
pkill -f "weston --socket=wayland-1" 2>/dev/null
pkill -f "Xvfb :2" 2>/dev/null
pkill -f "Xephyr :2" 2>/dev/null
sleep 1

# Start weston in nested mode with XWayland
# - Runs as a window inside your main Wayland compositor
# - XWayland provides GPU-accelerated X11 on display :2
# - Note: weston shows a desktop shell (minimal overhead)
WAYLAND_DISPLAY=wayland-0 weston --socket=wayland-1 --width=1920 --height=1080 --xwayland &

sleep 3

# Verify XWayland started
if [ -S /tmp/.X11-unix/X2 ]; then
    echo "Weston started successfully!"
    echo "XWayland available on DISPLAY=:2 (GPU accelerated)"
    echo ""
    echo "To run apps: DISPLAY=:2 <command>"
    echo ""
    echo "Note: Screenshots via scrot may not work - use manual methods"
else
    echo "Warning: XWayland socket not found at /tmp/.X11-unix/X2"
    echo "Available sockets:"
    ls /tmp/.X11-unix/
fi
