#!/bin/bash
# Start gamescope displays for RuneLite
#
# Usage: ./start_screen.sh [start|stop|status|N]
#   ./start_screen.sh         - Start 3 gamescope displays
#   ./start_screen.sh 4       - Start 4 gamescope displays
#   ./start_screen.sh stop    - Stop all gamescope displays
#   ./start_screen.sh status  - Check which displays are running
#
# This is a convenience wrapper around start_gamescopes.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

exec "$SCRIPT_DIR/start_gamescopes.sh" "$@"
