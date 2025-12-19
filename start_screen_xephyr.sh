#!/bin/bash
# Start Xephyr - simple nested X server
# Lightweight, resizable window, GPU accelerated
#
# Usage: ./start_screen_xephyr.sh [width] [height]
# Default: 1920x1080

WIDTH=${1:-1920}
HEIGHT=${2:-1080}

# Kill any existing displays
pkill -f "Xephyr :2" 2>/dev/null || true
pkill -f "weston.*wayland-1" 2>/dev/null || true
pkill -f "cage" 2>/dev/null || true
pkill -f "Xvfb :2" 2>/dev/null || true
sleep 1

echo "Starting Xephyr on DISPLAY=:2 (${WIDTH}x${HEIGHT}) with GPU acceleration..."

# Start Xephyr with GPU support
# -br: black background
# -ac: disable access control
# -noreset: don't reset after last client exits
# -resizeable: allow window resizing
# -glamor: enable GPU acceleration via glamor (CRITICAL for performance)
# +extension GLX: enable OpenGL extension
# +extension RENDER: enable render extension
# -dpi 96: set DPI
Xephyr :2 -screen ${WIDTH}x${HEIGHT} -br -ac -noreset -resizeable -glamor +extension GLX +extension RENDER -dpi 96 &

sleep 2

if [ -S /tmp/.X11-unix/X2 ]; then
    echo "✓ Xephyr started successfully!"
    echo "  DISPLAY=:2 (GPU accelerated, resizable)"
    echo ""
    echo "To run RuneLite: DISPLAY=:2 <command>"
    echo ""
    echo "To remove window border:"
    echo "  wmctrl -r Xephyr -b add,undecorated"
else
    echo "✗ Failed to start Xephyr"
    exit 1
fi
