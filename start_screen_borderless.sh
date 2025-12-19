#!/bin/bash
# Start weston and remove window borders

# Start the display
./start_screen.sh

# Wait for weston window to appear
sleep 3

# Try to remove borders (works for X11 window managers)
if command -v wmctrl &> /dev/null; then
    wmctrl -r weston -b add,undecorated 2>/dev/null || true
fi

# For Sway/Wayland compositors, use swaymsg
if command -v swaymsg &> /dev/null; then
    swaymsg '[app_id="weston"] border none' 2>/dev/null || true
fi

echo "Display started. If borders still visible, add window manager rules."
