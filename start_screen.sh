#!/bin/bash
# Start a nested display for RuneLite with GPU support
#
# Usage: ./start_screen.sh [options] [display_num]
#   ./start_screen.sh              - Headless mode (Xvfb, no mouse capture)
#   ./start_screen.sh --gamescope  - Interactive mode (Gamescope, GPU accelerated)
#   ./start_screen.sh --headless   - Explicit headless mode (Xvfb)
#   ./start_screen.sh 3            - Start display :3 (adds to existing, uses Xvfb)
#
# Then run RuneLite with: DISPLAY=:2 <command>

set -e

# Parse arguments
MODE="headless"  # Default to headless (no mouse capture)
TARGET_DISPLAY=""

for arg in "$@"; do
    case "$arg" in
        --gamescope)
            MODE="gamescope"
            ;;
        --headless|--xvfb)
            MODE="headless"
            ;;
        [0-9]*)
            TARGET_DISPLAY="$arg"
            ;;
    esac
done

if [ -n "$TARGET_DISPLAY" ]; then
    # Starting additional display - don't kill existing ones
    echo "Starting additional display (requesting :$TARGET_DISPLAY)..."

    # Check if already running
    if [ -S "/tmp/.X11-unix/X$TARGET_DISPLAY" ]; then
        echo "Display :$TARGET_DISPLAY already running"
        exit 0
    fi

    # Use Xvfb for additional displays (simple, reliable, no GPU needed)
    Xvfb :$TARGET_DISPLAY -screen 0 1024x768x24 &
    XVFB_PID=$!

    # Wait for Xvfb to create its display
    for i in {1..10}; do
        sleep 0.5
        if [ -S "/tmp/.X11-unix/X$TARGET_DISPLAY" ]; then
            if kill -0 $XVFB_PID 2>/dev/null; then
                echo "Xvfb started on :$TARGET_DISPLAY (PID: $XVFB_PID)"
                exit 0
            fi
        fi
    done

    echo "Failed to start Xvfb for display :$TARGET_DISPLAY"
    kill $XVFB_PID 2>/dev/null || true
    exit 1
fi

# Primary display startup

# Kill any existing virtual displays
pkill -f "gamescope" 2>/dev/null || true
pkill -f "weston --socket=wayland-1" 2>/dev/null || true
pkill -f "Xwayland.*:2" 2>/dev/null || true
pkill -f "Xvfb :2" 2>/dev/null || true
pkill -f "Xephyr :2" 2>/dev/null || true
sleep 1

# Remove stale X socket if present
rm -f /tmp/.X11-unix/X2 2>/dev/null || true

# Headless mode (default) - no mouse capture, good for server/autonomous use
start_headless() {
    echo "Starting headless display (Xvfb)..."

    Xvfb :2 -screen 0 1920x1080x24 &
    XVFB_PID=$!

    for i in {1..10}; do
        sleep 0.5
        if [ -S /tmp/.X11-unix/X2 ]; then
            if kill -0 $XVFB_PID 2>/dev/null; then
                echo "Xvfb started successfully!"
                echo "Display: :2"
                echo "PID: $XVFB_PID"
                echo ":2" > /tmp/manny_display
                return 0
            fi
        fi
    done

    echo "Xvfb failed to start"
    kill $XVFB_PID 2>/dev/null || true
    return 1
}

if [ "$MODE" = "headless" ]; then
    echo "Mode: Headless (no mouse capture)"
    if start_headless; then
        echo ""
        echo "Display ready! Use get_screenshot() to view."
        exit 0
    else
        echo "ERROR: Could not start headless display"
        exit 1
    fi
fi

echo "Mode: Interactive (Gamescope)"
echo "Starting nested display with GPU acceleration..."

# Try Gamescope first
start_gamescope() {
    echo "Attempting Gamescope..."

    # Gamescope creates its own Xwayland on a display it chooses
    # We run it with a dummy app that keeps it alive
    # _JAVA_AWT_WM_NONREPARENTING=1 is needed for Java/Swing apps like RuneLite

    export _JAVA_AWT_WM_NONREPARENTING=1

    # Start gamescope as a nested window
    # -W/-H: output window size
    # -w/-h: internal resolution (game sees this)
    # --force-windows-fullscreen: makes X11 apps fill the gamescope window
    # --xwayland-count 1: single Xwayland server
    gamescope \
        -W 1920 -H 1080 \
        -w 1920 -h 1080 \
        --force-windows-fullscreen \
        --xwayland-count 1 \
        -- sleep infinity &

    GAMESCOPE_PID=$!

    # Wait for Xwayland to be ready (gamescope picks its own display number)
    for i in {1..10}; do
        sleep 1
        # Find what display gamescope created
        DISPLAY_NUM=$(ls /tmp/.X11-unix/ 2>/dev/null | grep -oE '[0-9]+' | sort -n | tail -1)
        if [ -n "$DISPLAY_NUM" ] && [ "$DISPLAY_NUM" != "0" ] && [ "$DISPLAY_NUM" != "1" ]; then
            # Verify gamescope is still running
            if kill -0 $GAMESCOPE_PID 2>/dev/null; then
                echo "Gamescope started successfully!"
                echo "Display: :$DISPLAY_NUM"
                echo "PID: $GAMESCOPE_PID"

                # Create a symlink/marker so we know which display to use
                echo ":$DISPLAY_NUM" > /tmp/manny_display

                echo ""
                echo "To run apps: DISPLAY=:$DISPLAY_NUM <command>"
                echo "Java apps:   _JAVA_AWT_WM_NONREPARENTING=1 DISPLAY=:$DISPLAY_NUM <command>"
                return 0
            fi
        fi
    done

    echo "Gamescope failed to start properly"
    kill $GAMESCOPE_PID 2>/dev/null || true
    return 1
}

# Fallback: Rootful Xwayland (GPU accelerated, unlike Xephyr)
start_xwayland() {
    echo "Attempting rootful Xwayland fallback..."

    # Rootful Xwayland runs as a Wayland client with its own X server
    # -decorate: window decorations
    Xwayland -geometry 1920x1080 -decorate :2 &

    XWAYLAND_PID=$!

    # Wait for socket
    for i in {1..10}; do
        sleep 1
        if [ -S /tmp/.X11-unix/X2 ]; then
            if kill -0 $XWAYLAND_PID 2>/dev/null; then
                echo "Rootful Xwayland started successfully!"
                echo "Display: :2"
                echo "PID: $XWAYLAND_PID"

                echo ":2" > /tmp/manny_display

                echo ""
                echo "To run apps: DISPLAY=:2 <command>"
                return 0
            fi
        fi
    done

    echo "Xwayland failed to start"
    kill $XWAYLAND_PID 2>/dev/null || true
    return 1
}

# Try gamescope first, fall back to Xwayland
if start_gamescope; then
    echo ""
    echo "Using Gamescope (recommended)"
elif start_xwayland; then
    echo ""
    echo "Using rootful Xwayland (fallback)"
else
    echo ""
    echo "ERROR: Could not start any GPU-accelerated display server"
    echo "Available X sockets:"
    ls -la /tmp/.X11-unix/ 2>/dev/null || echo "  (none)"
    exit 1
fi

echo ""
echo "Display ready for RuneLite!"
