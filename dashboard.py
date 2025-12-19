#!/usr/bin/env python3
"""
Manny MCP Dashboard - Read-only monitoring interface

Provides:
- MJPEG video stream (view-only, no interaction)
- Real-time game state
- MCP activity log (what Claude Code is doing)
- Player stats extracted from game state
"""

import asyncio
import base64
import io
import json
import os
import subprocess
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Any

from fastapi import FastAPI, Response
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn


@dataclass
class MCPCall:
    """Record of an MCP tool invocation."""
    timestamp: str
    tool: str
    arguments: dict
    result_summary: str
    duration_ms: float


@dataclass
class ServerState:
    """Central observable state for the entire system."""

    # MCP activity tracking
    mcp_calls: deque = field(default_factory=lambda: deque(maxlen=100))
    current_tool: Optional[str] = None
    current_tool_started: Optional[float] = None

    # Game state (from manny_state.json)
    game_state: dict = field(default_factory=dict)
    game_state_updated: Optional[str] = None

    # Extracted player stats for easy access
    player_location: dict = field(default_factory=dict)
    player_stats: dict = field(default_factory=dict)
    inventory: list = field(default_factory=list)
    current_action: str = ""

    # Current command being executed
    pending_command: Optional[str] = None
    command_sent_at: Optional[str] = None

    # Recent logs
    logs: deque = field(default_factory=lambda: deque(maxlen=200))

    # Screenshot buffer for MJPEG stream
    latest_screenshot: Optional[bytes] = None
    screenshot_updated: Optional[float] = None

    # Health status
    health: dict = field(default_factory=dict)

    # Lock for thread safety
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def record_mcp_call(self, tool: str, arguments: dict, result: Any, duration_ms: float):
        """Record an MCP tool call."""
        if isinstance(result, dict):
            summary = json.dumps(result)[:200]
        else:
            summary = str(result)[:200]

        call = MCPCall(
            timestamp=datetime.now().isoformat(),
            tool=tool,
            arguments=arguments,
            result_summary=summary,
            duration_ms=round(duration_ms, 2)
        )

        with self._lock:
            self.mcp_calls.append(call)
            self.current_tool = None
            self.current_tool_started = None

    def start_mcp_call(self, tool: str):
        """Mark that an MCP call is starting."""
        with self._lock:
            self.current_tool = tool
            self.current_tool_started = time.time()

    def update_game_state(self, state: dict):
        """Update game state from manny_state.json."""
        with self._lock:
            self.game_state = state
            self.game_state_updated = datetime.now().isoformat()

            player = state.get("player", {})
            self.player_location = player.get("location", {})
            self.player_stats = {
                "hp": player.get("health", 0),
                "hp_max": player.get("maxHealth", 0),
                "prayer": player.get("prayer", 0),
                "prayer_max": player.get("maxPrayer", 0),
                "run_energy": player.get("runEnergy", 0),
                "combat_level": player.get("combatLevel", 0),
                "is_moving": player.get("isMoving", False),
                "is_animating": player.get("isAnimating", False),
            }
            self.inventory = state.get("inventory", [])
            self.current_action = state.get("currentAction", "")

    def update_screenshot(self, png_bytes: bytes):
        """Update the latest screenshot."""
        with self._lock:
            self.latest_screenshot = png_bytes
            self.screenshot_updated = time.time()

    def add_log(self, line: str):
        """Add a log line."""
        with self._lock:
            self.logs.append({
                "timestamp": datetime.now().isoformat(),
                "line": line
            })

    def set_command(self, command: str):
        """Record that a command was sent."""
        with self._lock:
            self.pending_command = command
            self.command_sent_at = datetime.now().isoformat()

    def update_health(self, health: dict):
        """Update health check results."""
        with self._lock:
            self.health = health

    def to_dict(self) -> dict:
        """Export state as JSON-serializable dict."""
        with self._lock:
            return {
                "mcp_calls": [
                    {
                        "timestamp": c.timestamp,
                        "tool": c.tool,
                        "arguments": c.arguments,
                        "result_summary": c.result_summary,
                        "duration_ms": c.duration_ms
                    }
                    for c in list(self.mcp_calls)[-20:]
                ],
                "current_tool": self.current_tool,
                "current_tool_duration_ms": (
                    round((time.time() - self.current_tool_started) * 1000)
                    if self.current_tool_started else None
                ),
                "game_state_updated": self.game_state_updated,
                "player_location": self.player_location,
                "player_stats": self.player_stats,
                "inventory_count": len(self.inventory),
                "inventory": self.inventory[:28],
                "current_action": self.current_action,
                "pending_command": self.pending_command,
                "command_sent_at": self.command_sent_at,
                "logs": list(self.logs)[-50:],
                "health": self.health,
                "screenshot_age_ms": (
                    round((time.time() - self.screenshot_updated) * 1000)
                    if self.screenshot_updated else None
                ),
            }


# Global state instance
STATE = ServerState()

# FastAPI app
app = FastAPI(title="Manny MCP Dashboard")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.get("/", response_class=HTMLResponse)
async def dashboard():
    """Serve the main dashboard HTML."""
    return DASHBOARD_HTML


@app.get("/api/state")
async def get_state():
    """Get current server state as JSON."""
    return STATE.to_dict()


@app.get("/api/game")
async def get_game_state():
    """Get full game state from manny_state.json."""
    return STATE.game_state


@app.get("/api/screenshot")
async def get_screenshot():
    """Get latest screenshot as PNG."""
    if STATE.latest_screenshot:
        return Response(content=STATE.latest_screenshot, media_type="image/png")
    return Response(status_code=404)


@app.get("/stream.mjpeg")
async def mjpeg_stream():
    """MJPEG video stream of screenshots."""

    async def generate():
        last_screenshot = None
        while True:
            if STATE.latest_screenshot and STATE.latest_screenshot != last_screenshot:
                last_screenshot = STATE.latest_screenshot
                try:
                    from PIL import Image
                    img = Image.open(io.BytesIO(last_screenshot))
                    jpeg_buffer = io.BytesIO()
                    img.convert("RGB").save(jpeg_buffer, format="JPEG", quality=70)
                    jpeg_bytes = jpeg_buffer.getvalue()
                except ImportError:
                    jpeg_bytes = last_screenshot

                yield (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n\r\n" +
                    jpeg_bytes +
                    b"\r\n"
                )
            await asyncio.sleep(0.1)

    return StreamingResponse(
        generate(),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )


DASHBOARD_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Manny MCP Dashboard</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, monospace;
            background: #1a1a2e;
            color: #eee;
            min-height: 100vh;
        }
        .container {
            display: grid;
            grid-template-columns: 1fr 400px;
            grid-template-rows: auto 1fr;
            gap: 10px;
            padding: 10px;
            height: 100vh;
        }
        @media (max-width: 900px) {
            .container { grid-template-columns: 1fr; }
        }

        .video-panel {
            grid-row: 1 / 3;
            background: #000;
            border-radius: 8px;
            overflow: hidden;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .video-panel img {
            max-width: 100%;
            max-height: 100%;
            object-fit: contain;
        }

        .stats-panel, .mcp-panel {
            background: #16213e;
            border-radius: 8px;
            padding: 15px;
            overflow-y: auto;
        }

        h2 {
            font-size: 14px;
            color: #0f9;
            margin-bottom: 10px;
            text-transform: uppercase;
            letter-spacing: 1px;
        }

        .stat-row {
            display: flex;
            justify-content: space-between;
            padding: 4px 0;
            border-bottom: 1px solid #ffffff10;
        }
        .stat-label { color: #888; }
        .stat-value { color: #fff; font-weight: 600; }

        .hp-bar, .prayer-bar, .run-bar {
            height: 8px;
            border-radius: 4px;
            margin: 2px 0 8px 0;
            background: #333;
        }
        .hp-bar .fill { background: #e74c3c; height: 100%; border-radius: 4px; }
        .prayer-bar .fill { background: #3498db; height: 100%; border-radius: 4px; }
        .run-bar .fill { background: #f39c12; height: 100%; border-radius: 4px; }

        .mcp-call {
            background: #0d1b2a;
            border-radius: 4px;
            padding: 8px;
            margin-bottom: 6px;
            font-size: 12px;
        }
        .mcp-call.active {
            border-left: 3px solid #0f9;
            animation: pulse 1s infinite;
        }
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.7; }
        }
        .mcp-tool { color: #0f9; font-weight: bold; }
        .mcp-time { color: #666; font-size: 10px; }
        .mcp-args { color: #888; font-size: 11px; word-break: break-all; }

        .inventory-grid {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 2px;
            margin-top: 10px;
        }
        .inv-slot {
            background: #0d1b2a;
            padding: 4px;
            font-size: 10px;
            text-align: center;
            border-radius: 2px;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }
        .inv-slot.empty { color: #444; }

        .current-action {
            background: #2d4a22;
            padding: 8px;
            border-radius: 4px;
            margin-bottom: 10px;
            font-size: 13px;
        }
        .current-action.idle { background: #333; }

        .health-indicator {
            width: 10px;
            height: 10px;
            border-radius: 50%;
            display: inline-block;
            margin-right: 8px;
        }
        .health-indicator.healthy { background: #0f9; }
        .health-indicator.unhealthy { background: #e74c3c; }

        .location { font-family: monospace; color: #0ff; }
    </style>
</head>
<body>
    <div class="container">
        <div class="video-panel">
            <img id="stream" src="/stream.mjpeg" alt="Game Stream">
        </div>

        <div class="stats-panel">
            <h2><span class="health-indicator" id="health-dot"></span>Player Stats</h2>
            <div class="current-action" id="current-action">Idle</div>

            <div class="stat-row">
                <span class="stat-label">Location</span>
                <span class="stat-value location" id="location">--</span>
            </div>

            <div class="stat-row">
                <span class="stat-label">HP</span>
                <span class="stat-value" id="hp">--</span>
            </div>
            <div class="hp-bar"><div class="fill" id="hp-fill"></div></div>

            <div class="stat-row">
                <span class="stat-label">Prayer</span>
                <span class="stat-value" id="prayer">--</span>
            </div>
            <div class="prayer-bar"><div class="fill" id="prayer-fill"></div></div>

            <div class="stat-row">
                <span class="stat-label">Run Energy</span>
                <span class="stat-value" id="run">--</span>
            </div>
            <div class="run-bar"><div class="fill" id="run-fill"></div></div>

            <div class="stat-row">
                <span class="stat-label">Combat Level</span>
                <span class="stat-value" id="combat">--</span>
            </div>

            <div class="stat-row">
                <span class="stat-label">Moving/Animating</span>
                <span class="stat-value" id="movement">--</span>
            </div>

            <h2 style="margin-top: 15px;">Inventory (<span id="inv-count">0</span>/28)</h2>
            <div class="inventory-grid" id="inventory"></div>
        </div>

        <div class="mcp-panel">
            <h2>MCP Activity</h2>
            <div id="pending-command"></div>
            <div id="mcp-calls"></div>
        </div>
    </div>

    <script>
        function updateDashboard() {
            fetch('/api/state')
                .then(r => r.json())
                .then(state => {
                    const dot = document.getElementById('health-dot');
                    dot.className = 'health-indicator ' + (state.health.healthy ? 'healthy' : 'unhealthy');

                    const actionEl = document.getElementById('current-action');
                    if (state.current_action) {
                        actionEl.textContent = state.current_action;
                        actionEl.className = 'current-action';
                    } else {
                        actionEl.textContent = 'Idle';
                        actionEl.className = 'current-action idle';
                    }

                    const loc = state.player_location;
                    document.getElementById('location').textContent =
                        loc.x ? `${loc.x}, ${loc.y}, ${loc.plane || 0}` : '--';

                    const stats = state.player_stats;
                    document.getElementById('hp').textContent = `${stats.hp || 0}/${stats.hp_max || 0}`;
                    document.getElementById('hp-fill').style.width =
                        stats.hp_max ? (stats.hp / stats.hp_max * 100) + '%' : '0%';

                    document.getElementById('prayer').textContent = `${stats.prayer || 0}/${stats.prayer_max || 0}`;
                    document.getElementById('prayer-fill').style.width =
                        stats.prayer_max ? (stats.prayer / stats.prayer_max * 100) + '%' : '0%';

                    document.getElementById('run').textContent = (stats.run_energy || 0) + '%';
                    document.getElementById('run-fill').style.width = (stats.run_energy || 0) + '%';

                    document.getElementById('combat').textContent = stats.combat_level || '--';

                    const moving = [];
                    if (stats.is_moving) moving.push('Moving');
                    if (stats.is_animating) moving.push('Animating');
                    document.getElementById('movement').textContent = moving.length ? moving.join(', ') : 'Idle';

                    document.getElementById('inv-count').textContent = state.inventory_count;
                    const invEl = document.getElementById('inventory');
                    invEl.innerHTML = '';
                    for (let i = 0; i < 28; i++) {
                        const item = state.inventory[i];
                        const slot = document.createElement('div');
                        slot.className = 'inv-slot' + (item ? '' : ' empty');
                        slot.textContent = item ? item.name || item : '·';
                        slot.title = item ? JSON.stringify(item) : 'Empty';
                        invEl.appendChild(slot);
                    }

                    const cmdEl = document.getElementById('pending-command');
                    if (state.pending_command) {
                        cmdEl.innerHTML = `<div class="mcp-call active">
                            <span class="mcp-tool">COMMAND:</span> ${state.pending_command}
                            <div class="mcp-time">${state.command_sent_at}</div>
                        </div>`;
                    } else {
                        cmdEl.innerHTML = '';
                    }

                    const callsEl = document.getElementById('mcp-calls');
                    let html = '';

                    if (state.current_tool) {
                        html += `<div class="mcp-call active">
                            <span class="mcp-tool">${state.current_tool}</span>
                            <span class="mcp-time">${state.current_tool_duration_ms}ms...</span>
                        </div>`;
                    }

                    const calls = [...state.mcp_calls].reverse();
                    for (const call of calls.slice(0, 15)) {
                        html += `<div class="mcp-call">
                            <span class="mcp-tool">${call.tool}</span>
                            <span class="mcp-time">${call.duration_ms}ms</span>
                            <div class="mcp-args">${JSON.stringify(call.arguments)}</div>
                        </div>`;
                    }
                    callsEl.innerHTML = html;
                })
                .catch(console.error);
        }

        setInterval(updateDashboard, 500);
        updateDashboard();
    </script>
</body>
</html>
"""


class DashboardBackgroundTasks:
    """Background tasks for updating state."""

    def __init__(self, config: dict):
        self.config = config
        self.running = False
        self.threads = []

    def start(self):
        """Start background update threads."""
        self.running = True

        t1 = threading.Thread(target=self._poll_game_state, daemon=True)
        t1.start()
        self.threads.append(t1)

        t2 = threading.Thread(target=self._capture_screenshots, daemon=True)
        t2.start()
        self.threads.append(t2)

        t3 = threading.Thread(target=self._check_health, daemon=True)
        t3.start()
        self.threads.append(t3)

    def stop(self):
        self.running = False

    def _poll_game_state(self):
        """Poll manny_state.json every 600ms."""
        state_file = self.config.get("state_file", "/tmp/manny_state.json")
        while self.running:
            try:
                if os.path.exists(state_file):
                    with open(state_file) as f:
                        state = json.load(f)
                    STATE.update_game_state(state)
            except Exception as e:
                STATE.add_log(f"State poll error: {e}")
            time.sleep(0.6)

    def _capture_screenshots(self):
        """Capture screenshots every 500ms for the video stream."""
        display = self.config.get("display", ":2")
        while self.running:
            try:
                env = os.environ.copy()
                env["DISPLAY"] = display

                result = subprocess.run(
                    ["scrot", "-o", "/tmp/dashboard_frame.png"],
                    env=env,
                    capture_output=True,
                    timeout=2
                )

                if result.returncode == 0:
                    with open("/tmp/dashboard_frame.png", "rb") as f:
                        STATE.update_screenshot(f.read())
            except Exception:
                pass
            time.sleep(0.5)

    def _check_health(self):
        """Run health checks every 5 seconds."""
        while self.running:
            try:
                state_file = self.config.get("state_file", "/tmp/manny_state.json")
                health = {"healthy": True, "issues": []}

                if os.path.exists(state_file):
                    age = time.time() - os.path.getmtime(state_file)
                    if age > 5:
                        health["healthy"] = False
                        health["issues"].append(f"State stale ({age:.1f}s)")
                else:
                    health["healthy"] = False
                    health["issues"].append("State file missing")

                result = subprocess.run(
                    ["pgrep", "-f", "runelite"],
                    capture_output=True,
                    timeout=2
                )
                if result.returncode != 0:
                    health["healthy"] = False
                    health["issues"].append("RuneLite not running")

                STATE.update_health(health)
            except Exception as e:
                STATE.update_health({"healthy": False, "issues": [str(e)]})
            time.sleep(5)


def run_dashboard(config: dict, host: str = "0.0.0.0", port: int = 8080):
    """Run the dashboard server standalone."""
    tasks = DashboardBackgroundTasks(config)
    tasks.start()

    try:
        uvicorn.run(app, host=host, port=port, log_level="warning")
    finally:
        tasks.stop()


if __name__ == "__main__":
    import yaml
    config_path = os.environ.get("RUNELITE_MCP_CONFIG", "config.yaml")
    with open(config_path) as f:
        config = yaml.safe_load(f)

    print("Starting Manny MCP Dashboard on http://0.0.0.0:8080")
    run_dashboard(config)
