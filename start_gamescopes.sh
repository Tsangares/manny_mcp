#!/bin/bash
set -euo pipefail
# Start multiple gamescope instances for RuneLite multi-boxing
# Each instance is GPU-accelerated and visible as a window on your desktop
#
# Usage: ./start_gamescopes.sh [start|stop|status|N]
#   ./start_gamescopes.sh         - Start 3 gamescope displays
#   ./start_gamescopes.sh 4       - Start 4 gamescope displays
#   ./start_gamescopes.sh stop    - Stop all gamescope displays
#   ./start_gamescopes.sh status  - Check which displays are running

PIDFILE_DIR="/tmp/gamescope_pids"
DISPLAY_MAP="/tmp/gamescope_displays.txt"
DEFAULT_COUNT=3

# Verify gamescope is installed
if ! command -v gamescope &>/dev/null; then
    echo "ERROR: gamescope not found. Install it first."
    echo "  Arch: sudo pacman -S gamescope"
    exit 1
fi

mkdir -p "$PIDFILE_DIR"

get_next_display() {
    # Find highest X display number currently in use
    local max=1
    for f in /tmp/.X11-unix/X*; do
        if [ -e "$f" ]; then
            local num=$(basename "$f" | sed 's/X//')
            if [ "$num" -gt "$max" ] 2>/dev/null; then
                max=$num
            fi
        fi
    done
    echo $((max + 1))
}

start_one_gamescope() {
    local index=$1
    local expected_display=$(get_next_display)

    echo "Starting gamescope #$index (expecting :$expected_display)..."

    # Start gamescope as nested compositor under existing Wayland session
    # --backend wayland: run under GNOME/mutter instead of grabbing seat
    WAYLAND_DISPLAY="${WAYLAND_DISPLAY:-wayland-0}" \
    _JAVA_AWT_WM_NONREPARENTING=1 gamescope \
        --backend wayland \
        -W 1920 -H 1080 \
        -w 1920 -h 1080 \
        --force-windows-fullscreen \
        --xwayland-count 1 \
        -- sleep infinity &

    local pid=$!

    # Wait for it to create a display and become responsive
    for i in {1..20}; do
        sleep 0.5
        # Check if socket exists
        if [ -S "/tmp/.X11-unix/X$expected_display" ]; then
            # Verify the display is actually responsive (not just socket created)
            if xdpyinfo -display ":$expected_display" &>/dev/null; then
                echo "$expected_display" >> "$DISPLAY_MAP"
                echo "$pid" > "$PIDFILE_DIR/gamescope_$expected_display.pid"
                echo "  Started :$expected_display (PID: $pid)"
                return 0
            fi
        fi
    done

    echo "  Failed to start gamescope #$index"
    kill $pid 2>/dev/null || true
    return 1
}

start_gamescopes() {
    local count=${1:-$DEFAULT_COUNT}

    echo "Starting $count gamescope displays..."
    echo ""

    # Clear old display map
    > "$DISPLAY_MAP"

    local started=0
    for i in $(seq 1 $count); do
        if start_one_gamescope $i; then
            ((started++))
        fi
        sleep 1  # Give each one time to fully initialize
    done

    echo ""
    echo "Started $started gamescope displays"
    echo "Available displays: $(cat "$DISPLAY_MAP" | tr '\n' ' ' | sed 's/ $//')"
    echo ""
    echo "Use: start_runelite(account_id='main', display=':N')"
}

stop_gamescopes() {
    echo "Stopping all gamescope instances..."

    # Kill tracked instances
    for pidfile in "$PIDFILE_DIR"/gamescope_*.pid; do
        if [ -f "$pidfile" ]; then
            local pid=$(cat "$pidfile")
            local display=$(basename "$pidfile" | sed 's/gamescope_//' | sed 's/.pid//')
            if kill -0 "$pid" 2>/dev/null; then
                echo "  Stopping :$display (PID: $pid)"
                kill "$pid" 2>/dev/null || true
            fi
            rm -f "$pidfile"
        fi
    done

    # Kill any untracked gamescope processes
    pkill -f "gamescope.*sleep infinity" 2>/dev/null || true

    sleep 1
    rm -f "$DISPLAY_MAP"
    echo "Done"
}

status() {
    echo "Gamescope Display Status"
    echo "========================"

    local found=0
    for pidfile in "$PIDFILE_DIR"/gamescope_*.pid; do
        if [ -f "$pidfile" ]; then
            local pid=$(cat "$pidfile")
            local display=$(basename "$pidfile" | sed 's/gamescope_//' | sed 's/.pid//')
            if [ -S "/tmp/.X11-unix/X$display" ] && kill -0 "$pid" 2>/dev/null; then
                echo "  :$display  RUNNING (PID: $pid)"
                ((found++))
            else
                echo "  :$display  DEAD"
                rm -f "$pidfile"
            fi
        fi
    done

    if [ $found -eq 0 ]; then
        echo "  No gamescope displays running"
        echo ""
        echo "Start with: ./start_gamescopes.sh"
    else
        echo ""
        echo "Total: $found display(s) available"
    fi
}

cleanup() {
    echo "Cleaning up stale files..."
    local cleaned=0

    # Clean orphaned PID files
    for pidfile in "$PIDFILE_DIR"/gamescope_*.pid; do
        if [ -f "$pidfile" ]; then
            local pid
            pid=$(cat "$pidfile")
            if ! kill -0 "$pid" 2>/dev/null; then
                echo "  Removing stale PID file: $pidfile (PID $pid dead)"
                rm -f "$pidfile"
                ((cleaned++)) || true
            fi
        fi
    done

    # Clean stale proxychains configs
    if [ -d "$HOME/.manny" ]; then
        for conf in "$HOME/.manny"/proxychains_*.conf; do
            if [ -f "$conf" ]; then
                echo "  Removing stale proxychains config: $conf"
                rm -f "$conf"
                ((cleaned++)) || true
            fi
        done
    fi

    # Clean backup files with ~ suffix in routines
    local script_dir
    script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    if [ -d "$script_dir/routines" ]; then
        while IFS= read -r -d '' backup; do
            echo "  Removing backup file: $backup"
            rm -f "$backup"
            ((cleaned++)) || true
        done < <(find "$script_dir/routines" -name '*~' -print0 2>/dev/null)
    fi

    if [ "$cleaned" -eq 0 ]; then
        echo "  Nothing to clean up"
    else
        echo "  Cleaned $cleaned stale file(s)"
    fi
}

# Main
case "${1:-start}" in
    stop)
        stop_gamescopes
        ;;
    status)
        status
        ;;
    cleanup)
        cleanup
        ;;
    [0-9]*)
        start_gamescopes "$1"
        ;;
    start|"")
        start_gamescopes $DEFAULT_COUNT
        ;;
    *)
        echo "Usage: $0 [start|stop|status|cleanup|N]"
        echo ""
        echo "Examples:"
        echo "  $0           # Start 3 gamescope displays"
        echo "  $0 4         # Start 4 gamescope displays"
        echo "  $0 stop      # Stop all displays"
        echo "  $0 status    # Show running displays"
        echo "  $0 cleanup   # Remove stale PID/config files"
        exit 1
        ;;
esac
