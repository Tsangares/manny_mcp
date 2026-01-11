#!/bin/bash
# Dashboard Development Mode - Hot Reload
# Automatically reloads when dashboard.py changes

echo "🔥 Starting Dashboard in HOT-RELOAD mode..."
echo ""
echo "Access at:"
echo "  Local:   http://localhost:8080"
echo "  Network: http://10.0.0.185:8080"
echo ""
echo "📱 On your phone (same WiFi): http://10.0.0.185:8080"
echo ""
echo "🔧 Edit dashboard.py and save - changes reload automatically!"
echo ""

# Kill any existing dashboard
pkill -f "python.*dashboard.py" 2>/dev/null

# Run with uvicorn's --reload flag for hot-reload
cd "$(dirname "$0")"
./venv/bin/uvicorn dashboard:app \
    --host 0.0.0.0 \
    --port 8080 \
    --reload \
    --reload-dir . \
    --reload-include "*.py" \
    --log-level info
