#!/bin/bash
# Start a virtual display for RuneLite with GPU support
#
# Usage: ./start_screen.sh [options] [display_num]
#   ./start_screen.sh              - GPU headless mode (Gamescope, default)
#   ./start_screen.sh --xvfb       - Software rendering (Xvfb, fallback)
#   ./start_screen.sh --gamescope  - Interactive mode (Gamescope windowed, needs display)
#   ./start_screen.sh 3            - Start additional display :3 (Xvfb)
#
# Then run RuneLite with: DISPLAY=:2 <command>

set -e

# Parse arguments
MODE="gpu-headless"  # Default to GPU headless
TARGET_DISPLAY=""

for arg in "$@"; do
    case "$arg" in
        --gamescope)
            MODE="gamescope-windowed"
            ;;
        --xvfb|--headless)
            MODE="xvfb"
            ;;
        --gpu|--gpu-headless)
            MODE="gpu-headless"
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

    # Use Xvfb for additional displays (simple, reliable)
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

# Kill any existing virtual displays (but not :0/:1 which may be system displays)
pkill -f "gamescope.*headless" 2>/dev/null || true
pkill -f "gamescope.*sleep infinity" 2>/dev/null || true
pkill -f "Xvfb :2" 2>/dev/null || true
sleep 1

# Remove stale X socket if present
rm -f /tmp/.X11-unix/X2 2>/dev/null || true

# GPU Headless mode (default) - Gamescope with headless backend
start_gpu_headless() {
    echo "Starting GPU-accelerated headless display (Gamescope)..."

    export _JAVA_AWT_WM_NONREPARENTING=1

    gamescope \
        --backend headless \
        -W 1920 -H 1080 \
        -w 1920 -h 1080 \
        -- sleep infinity &

    GAMESCOPE_PID=$!

    # Wait for Xwayland to be ready
    for i in {1..15}; do
        sleep 0.5
        # Gamescope headless creates its own display number
        if [ -S /tmp/.X11-unix/X2 ]; then
            if kill -0 $GAMESCOPE_PID 2>/dev/null; then
                echo "Gamescope headless started successfully!"
                echo "Display: :2"
                echo "PID: $GAMESCOPE_PID"
                echo ":2" > /tmp/manny_display

                # Show GPU info
                GPU_INFO=$(gamescope --help 2>&1 | head -1 || true)
                nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | head -1 | xargs -I{} echo "GPU: {}"

                return 0
            fi
        fi

        # Check higher display numbers too
        for d in 2 3 4 5; do
            if [ -S "/tmp/.X11-unix/X$d" ]; then
                if kill -0 $GAMESCOPE_PID 2>/dev/null; then
                    echo "Gamescope headless started successfully!"
                    echo "Display: :$d"
                    echo "PID: $GAMESCOPE_PID"
                    echo ":$d" > /tmp/manny_display
                    nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | head -1 | xargs -I{} echo "GPU: {}"
                    return 0
                fi
            fi
        done
    done

    echo "Gamescope headless failed to start"
    kill $GAMESCOPE_PID 2>/dev/null || true
    return 1
}

# Xvfb fallback - software rendering
start_xvfb() {
    echo "Starting software-rendered display (Xvfb)..."

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

# Interactive Gamescope - runs as window on existing display (needs DISPLAY set)
start_gamescope_windowed() {
    echo "Starting interactive Gamescope (windowed)..."

    if [ -z "$DISPLAY" ]; then
        echo "ERROR: --gamescope requires DISPLAY to be set (run from desktop session)"
        return 1
    fi

    export _JAVA_AWT_WM_NONREPARENTING=1

    gamescope \
        -W 1920 -H 1080 \
        -w 1920 -h 1080 \
        --force-windows-fullscreen \
        --xwayland-count 1 \
        -- sleep infinity &

    GAMESCOPE_PID=$!

    for i in {1..10}; do
        sleep 1
        DISPLAY_NUM=$(ls /tmp/.X11-unix/ 2>/dev/null | grep -oE '[0-9]+' | sort -n | tail -1)
        if [ -n "$DISPLAY_NUM" ] && [ "$DISPLAY_NUM" != "0" ] && [ "$DISPLAY_NUM" != "1" ]; then
            if kill -0 $GAMESCOPE_PID 2>/dev/null; then
                echo "Gamescope windowed started!"
                echo "Display: :$DISPLAY_NUM"
                echo "PID: $GAMESCOPE_PID"
                echo ":$DISPLAY_NUM" > /tmp/manny_display
                return 0
            fi
        fi
    done

    echo "Gamescope windowed failed to start"
    kill $GAMESCOPE_PID 2>/dev/null || true
    return 1
}

# Main logic
case "$MODE" in
    gpu-headless)
        echo "Mode: GPU Headless (Gamescope + Vulkan)"
        if start_gpu_headless; then
            echo ""
            echo "Display ready! GPU-accelerated rendering enabled."
            echo "Use get_screenshot() to view."
            exit 0
        else
            echo "GPU headless failed, falling back to Xvfb..."
            if start_xvfb; then
                echo ""
                echo "Display ready (software rendering fallback)."
                exit 0
            fi
            echo "ERROR: Could not start any display"
            exit 1
        fi
        ;;
    xvfb)
        echo "Mode: Software Rendering (Xvfb)"
        if start_xvfb; then
            echo ""
            echo "Display ready! Use get_screenshot() to view."
            exit 0
        else
            echo "ERROR: Could not start Xvfb"
            exit 1
        fi
        ;;
    gamescope-windowed)
        echo "Mode: Interactive Windowed (Gamescope)"
        if start_gamescope_windowed; then
            echo ""
            echo "Display ready! GPU-accelerated window visible."
            exit 0
        else
            echo "ERROR: Could not start Gamescope windowed"
            exit 1
        fi
        ;;
esac
