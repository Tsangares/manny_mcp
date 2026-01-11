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

from fastapi import FastAPI, Response, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import struct


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

            # Health is nested: player.health.current/max
            health = player.get("health", {})
            if isinstance(health, dict):
                hp = health.get("current", 0)
                hp_max = health.get("max", 0)
            else:
                hp = health
                hp_max = player.get("maxHealth", 0)

            self.player_stats = {
                "hp": hp,
                "hp_max": hp_max,
                "prayer": player.get("prayer", 0),
                "prayer_max": player.get("maxPrayer", 0),
                "run_energy": player.get("runEnergy", 0),
                "combat_level": player.get("combatLevel", 0),
                "is_moving": player.get("isMoving", False),
                "is_animating": player.get("isAnimating", False),
            }

            # Inventory is nested: player.inventory.items
            inventory_data = player.get("inventory", {})
            if isinstance(inventory_data, dict):
                self.inventory = inventory_data.get("items", [])
            else:
                self.inventory = inventory_data if inventory_data else []

            self.current_action = state.get("scenario", {}).get("currentTask", "Idle")

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
            }


# Global state instance
STATE = ServerState()

# WebSocket clients and background tasks
active_ws_clients: set[WebSocket] = set()
background_tasks: Optional['DashboardBackgroundTasks'] = None

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


@app.websocket("/ws/stream")
async def websocket_stream(websocket: WebSocket):
    """WebSocket endpoint for H.264 video streaming."""
    await websocket.accept()
    active_ws_clients.add(websocket)

    try:
        last_sent_index = 0

        while True:
            # Check if there are new frames in the queue
            if background_tasks and len(background_tasks.frame_queue) > last_sent_index:
                # Send ALL new frames in order, not just the latest
                queue_snapshot = list(background_tasks.frame_queue)
                for i in range(last_sent_index, len(queue_snapshot)):
                    try:
                        await websocket.send_bytes(queue_snapshot[i])
                    except Exception:
                        break
                last_sent_index = len(queue_snapshot)

            # Small sleep to avoid busy loop
            await asyncio.sleep(0.01)

    except WebSocketDisconnect:
        pass
    finally:
        active_ws_clients.discard(websocket)


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
            overflow-x: hidden;
        }
        .container {
            display: grid;
            grid-template-columns: 1fr 400px;
            grid-template-rows: auto 1fr;
            gap: 10px;
            padding: 10px;
            height: 100vh;
        }

        /* Mobile-first responsive design */
        @media (max-width: 900px) {
            .container {
                grid-template-columns: 1fr;
                grid-template-rows: auto auto 1fr;
                height: 100vh;
                padding: 8px;
                gap: 8px;
            }
            .video-panel {
                grid-row: 1;
                max-height: 35vh;
                min-height: 200px;
            }
            .stats-panel {
                grid-row: 2;
                max-height: 40vh;
            }
            .mcp-panel {
                grid-row: 3;
                min-height: 150px;
            }
        }

        /* Pixel 6 specific optimizations (portrait: 412x915 CSS pixels) */
        @media (max-width: 480px) {
            body {
                font-size: 14px;
            }
            .container {
                padding: 4px;
                gap: 6px;
            }
            h2 {
                font-size: 12px !important;
                margin-bottom: 8px !important;
            }
            .stat-row {
                padding: 6px 0 !important;
            }
            .mcp-call {
                padding: 10px !important;
                margin-bottom: 8px !important;
                font-size: 11px !important;
            }
            .stats-panel, .mcp-panel {
                padding: 12px !important;
            }
        }

        .video-panel {
            grid-row: 1 / 3;
            background: #0a0a14;
            border-radius: 8px;
            overflow: hidden;
            display: flex;
            align-items: flex-start;
            justify-content: center;
            position: relative;
        }
        .video-panel video {
            max-width: 100%;
            max-height: 100%;
            width: 100%;
            height: auto;
            display: block;
            object-fit: contain;
        }

        .stats-panel, .mcp-panel {
            background: #16213e;
            border-radius: 8px;
            padding: 15px;
            overflow-y: auto;
            -webkit-overflow-scrolling: touch; /* Smooth scrolling on iOS */
        }

        h2 {
            font-size: 14px;
            color: #0f9;
            margin-bottom: 10px;
            text-transform: uppercase;
            letter-spacing: 1px;
            font-weight: 600;
        }

        .stat-row {
            display: flex;
            justify-content: space-between;
            padding: 4px 0;
            border-bottom: 1px solid #ffffff10;
            min-height: 28px; /* Better touch targets on mobile */
            align-items: center;
        }
        .stat-label {
            color: #888;
            font-size: 13px;
        }
        .stat-value {
            color: #fff;
            font-weight: 600;
            font-size: 14px;
        }

        .hp-bar, .prayer-bar, .run-bar {
            height: 10px;
            border-radius: 5px;
            margin: 2px 0 8px 0;
            background: #333;
            overflow: hidden;
        }
        .hp-bar .fill {
            background: linear-gradient(90deg, #e74c3c, #c0392b);
            height: 100%;
            border-radius: 5px;
            transition: width 0.3s ease;
        }
        .prayer-bar .fill {
            background: linear-gradient(90deg, #3498db, #2980b9);
            height: 100%;
            border-radius: 5px;
            transition: width 0.3s ease;
        }
        .run-bar .fill {
            background: linear-gradient(90deg, #f39c12, #e67e22);
            height: 100%;
            border-radius: 5px;
            transition: width 0.3s ease;
        }

        .mcp-call {
            background: #0d1b2a;
            border-radius: 6px;
            padding: 8px;
            margin-bottom: 6px;
            font-size: 12px;
            border-left: 2px solid transparent;
            transition: all 0.2s ease;
        }
        .mcp-call.active {
            border-left: 3px solid #0f9;
            background: #0f1f2f;
            animation: pulse 1s infinite;
        }
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.7; }
        }
        .mcp-tool {
            color: #0f9;
            font-weight: bold;
            font-size: 13px;
        }
        .mcp-time {
            color: #666;
            font-size: 10px;
            margin-left: 8px;
        }
        .mcp-args {
            color: #888;
            font-size: 11px;
            word-break: break-all;
            margin-top: 4px;
            line-height: 1.4;
        }

        .current-action {
            background: #2d4a22;
            padding: 10px 12px;
            border-radius: 6px;
            margin-bottom: 12px;
            font-size: 13px;
            font-weight: 500;
            border-left: 3px solid #4CAF50;
            transition: all 0.3s ease;
        }
        .current-action.idle {
            background: #333;
            border-left: 3px solid #666;
        }

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
            <video id="stream" autoplay muted playsinline></video>
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

        </div>

        <div class="mcp-panel">
            <h2>MCP Activity</h2>
            <div id="pending-command"></div>
            <div id="mcp-calls"></div>
        </div>
    </div>

    <script>
        // H.264 WebSocket Stream Client
        class H264Stream {
            constructor(videoElement, wsUrl) {
                this.video = videoElement;
                this.wsUrl = wsUrl;
                this.mediaSource = new MediaSource();
                this.sourceBuffer = null;
                this.queue = [];
                this.isUpdating = false;
            }

            async start() {
                // Check MSE support
                if (!window.MediaSource || !MediaSource.isTypeSupported('video/mp4; codecs="avc1.42E01E"')) {
                    alert('Your browser does not support H.264 streaming. Please use Chrome, Firefox, Safari, or Edge.');
                    return;
                }

                this.video.src = URL.createObjectURL(this.mediaSource);

                await new Promise(resolve => {
                    this.mediaSource.addEventListener('sourceopen', resolve, { once: true });
                });

                console.log('[Video] MediaSource opened');

                // Set duration to infinity for live streaming
                if (this.mediaSource.readyState === 'open') {
                    try {
                        this.mediaSource.duration = Infinity;
                        console.log('[Video] Duration set to Infinity');
                    } catch (e) {
                        console.warn('[Video] Could not set duration:', e);
                    }
                }

                this.sourceBuffer = this.mediaSource.addSourceBuffer('video/mp4; codecs="avc1.42E01E"');
                this.sourceBuffer.mode = 'sequence';
                console.log('[Video] SourceBuffer created');

                this.sourceBuffer.addEventListener('updateend', () => {
                    this.isUpdating = false;
                    console.log('[Video] Buffer update complete');

                    // Try to play the video once we have data
                    if (this.video.paused && this.sourceBuffer.buffered.length > 0) {
                        console.log('[Video] Starting playback...');
                        this.video.play().then(() => {
                            console.log('[Video] Playback started!');
                        }).catch(e => {
                            console.error('[Video] Play failed:', e);
                        });
                    }

                    this.processQueue();
                });

                this.sourceBuffer.addEventListener('error', (e) => {
                    console.error('[Video] SourceBuffer error:', e);
                });

                this.mediaSource.addEventListener('sourceclose', () => {
                    console.error('[Video] MediaSource closed unexpectedly!');
                });

                this.connect();
            }

            connect() {
                this.ws = new WebSocket(this.wsUrl);
                this.ws.binaryType = 'arraybuffer';

                this.ws.onopen = () => {
                    console.log('[Video] WebSocket connected');
                };

                this.ws.onmessage = (event) => {
                    console.log(`[Video] Received frame: ${event.data.byteLength} bytes, queue length: ${this.queue.length}`);
                    this.queue.push(event.data);
                    this.processQueue();
                };

                this.ws.onclose = () => {
                    console.log('[Video] WebSocket closed, reconnecting in 2s...');
                    setTimeout(() => this.connect(), 2000);
                };

                this.ws.onerror = (error) => {
                    console.error('[Video] WebSocket error:', error);
                };
            }

            processQueue() {
                if (this.isUpdating || this.queue.length === 0) return;

                // Check if SourceBuffer is still valid
                if (!this.sourceBuffer || this.mediaSource.readyState !== 'open') {
                    console.error('[Video] Cannot append: MediaSource not open (state:', this.mediaSource.readyState, ')');
                    return;
                }

                this.isUpdating = true;
                const buffer = this.queue.shift();
                console.log(`[Video] Appending ${buffer.byteLength} bytes to SourceBuffer`);
                try {
                    this.sourceBuffer.appendBuffer(buffer);
                } catch (e) {
                    console.error('[Video] Buffer append failed:', e);
                    this.isUpdating = false;
                }
            }
        }

        // Initialize video stream
        let stream;
        window.addEventListener('DOMContentLoaded', () => {
            const video = document.getElementById('stream');
            const wsUrl = `ws://${window.location.host}/ws/stream`;
            stream = new H264Stream(video, wsUrl);
            stream.start();
        });

        // Update dashboard stats
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

        # FFmpeg process management
        self.ffmpeg_process = None
        self.ffmpeg_encoder = None
        self.ffmpeg_restart_count = 0
        self.mp4_buffer = bytearray()
        self.frame_queue = deque(maxlen=30)  # Buffer for frames to broadcast

    def _detect_h264_encoder(self) -> str:
        """Test encoders in priority order, return first working one."""
        # Prioritize h264_vaapi for Intel GPU (low CPU usage)
        encoders = ['h264_vaapi', 'h264_nvenc', 'h264_amf', 'libx264']
        display = self.config.get('display', ':2')

        for encoder in encoders:
            try:
                STATE.add_log(f"Testing encoder: {encoder}")
                cmd = [
                    'ffmpeg', '-f', 'x11grab',
                    '-video_size', '1020x666',
                    '-framerate', '24',
                    '-t', '1',  # 1 second test
                    '-i', f'{display}+200,8',
                    '-c:v', encoder,
                    '-f', 'null',
                    '-'
                ]

                env = os.environ.copy()
                env['DISPLAY'] = display

                result = subprocess.run(
                    cmd,
                    env=env,
                    capture_output=True,
                    timeout=5
                )

                if result.returncode == 0:
                    STATE.add_log(f"Selected encoder: {encoder}")
                    return encoder

            except (subprocess.TimeoutExpired, Exception) as e:
                STATE.add_log(f"Encoder {encoder} failed: {e}")
                continue

        # Fallback to libx264 if all tests fail
        STATE.add_log("All encoders failed, using libx264 as fallback")
        return 'libx264'

    def _build_ffmpeg_cmd(self, display: str, x: int, y: int) -> list:
        """Build FFmpeg command optimized for the selected encoder."""
        base_cmd = [
            'ffmpeg',
            '-f', 'x11grab',
            '-video_size', '1020x666',
        ]

        # Use lower framerate for hardware encoding (less load)
        if self.ffmpeg_encoder == 'h264_vaapi':
            framerate = '15'  # 15fps for low CPU usage
        else:
            framerate = '20'  # 20fps for software

        base_cmd.extend(['-framerate', framerate])
        base_cmd.extend(['-i', f'{display}+{x},{y}'])

        # Hardware encoding (h264_vaapi) - uses Intel GPU
        if self.ffmpeg_encoder == 'h264_vaapi':
            base_cmd.extend([
                '-vaapi_device', '/dev/dri/renderD128',  # Intel GPU device
                '-vf', 'format=nv12,hwupload',  # Upload to GPU
                '-c:v', 'h264_vaapi',
                '-qp', '24',  # Quality (lower = better, 18-28 is good range)
                '-g', '30',  # Keyframe every 2s at 15fps
                '-b:v', '1.5M',  # Lower bitrate for 15fps
                '-maxrate', '2M',
                '-bufsize', '1M',
            ])
        # Software encoding fallback
        else:
            base_cmd.extend([
                '-c:v', self.ffmpeg_encoder,
                '-preset', 'veryfast',
                '-tune', 'zerolatency',
                '-g', '40',  # Keyframe every 2s at 20fps
                '-b:v', '1.5M',
                '-maxrate', '2M',
                '-bufsize', '1M',
            ])

        # Common final settings
        base_cmd.extend([
            '-pix_fmt', 'yuv420p',
            '-movflags', 'frag_keyframe+empty_moov+default_base_moof',
            '-f', 'mp4',
            'pipe:1'
        ])

        return base_cmd

    def _start_ffmpeg(self):
        """Start FFmpeg process with detected encoder - capture window and crop."""
        if self.ffmpeg_process:
            try:
                self.ffmpeg_process.terminate()
                self.ffmpeg_process.wait(timeout=2)
            except:
                pass

        display = self.config.get('display', ':2')
        env = os.environ.copy()
        env['DISPLAY'] = display

        # Find RuneLite window and calculate absolute viewport position
        try:
            # Get window geometry
            result = subprocess.run(
                ['xdotool', 'search', '--name', 'RuneLite', 'getwindowgeometry'],
                env=env,
                capture_output=True,
                text=True,
                timeout=3
            )
            if result.returncode == 0 and result.stdout:
                # Parse position from output like "Position: 38,59 (screen: 0)"
                for line in result.stdout.split('\n'):
                    if line.strip().startswith('Position:'):
                        pos_str = line.split(':')[1].split('(')[0].strip()
                        win_x, win_y = map(int, pos_str.split(','))

                        # Viewport is at offset 200,8 within the window
                        viewport_x = win_x + 200
                        viewport_y = win_y + 8

                        STATE.add_log(f"RuneLite window at ({win_x},{win_y}), viewport at ({viewport_x},{viewport_y})")
                        cmd = self._build_ffmpeg_cmd(display, viewport_x, viewport_y)
                        break
                else:
                    raise ValueError("Could not parse window position")
            else:
                raise ValueError("xdotool command failed")
        except Exception as e:
            STATE.add_log(f"Error finding window: {e}, using default coordinates")
            # Fallback to default coordinates
            cmd = self._build_ffmpeg_cmd(display, 200, 8)

        STATE.add_log(f"Starting FFmpeg with encoder: {self.ffmpeg_encoder}")
        self.ffmpeg_process = subprocess.Popen(
            cmd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        self.mp4_buffer.clear()

    def _extract_mp4_fragment(self) -> Optional[bytes]:
        """Extract complete MP4 fragment from buffer (init segment or moof+mdat)."""
        if len(self.mp4_buffer) < 8:
            return None

        try:
            # Parse MP4 boxes to extract complete fragments
            i = 0

            # Check for initialization segment (ftyp + moov)
            if self.mp4_buffer[4:8] == b'ftyp':
                # Extract complete initialization segment (ftyp + moov)
                extracted_size = 0
                while i < len(self.mp4_buffer) - 8:
                    box_size = struct.unpack('>I', self.mp4_buffer[i:i+4])[0]
                    box_type = self.mp4_buffer[i+4:i+8]

                    if box_size < 8:
                        break

                    extracted_size = i + box_size

                    # moov is the last box of init segment
                    if box_type == b'moov':
                        if extracted_size <= len(self.mp4_buffer):
                            init_segment = bytes(self.mp4_buffer[0:extracted_size])
                            self.mp4_buffer = self.mp4_buffer[extracted_size:]
                            return init_segment
                        return None

                    i += box_size
                return None

            # Look for media segment (moof + mdat)
            # Must start at position 0 - if buffer has garbage, clear it
            if len(self.mp4_buffer) >= 8:
                box_size = struct.unpack('>I', self.mp4_buffer[0:4])[0]
                box_type = self.mp4_buffer[4:8]

                if box_type == b'moof':
                    # Found moof, look for complete fragment (moof + mdat)
                    if box_size + 8 > len(self.mp4_buffer):
                        return None  # Not enough data yet

                    # Check if next box is mdat
                    next_box_size = struct.unpack('>I', self.mp4_buffer[box_size:box_size+4])[0]
                    next_box_type = self.mp4_buffer[box_size+4:box_size+8]

                    if next_box_type == b'mdat':
                        # Complete fragment found
                        fragment_end = box_size + next_box_size
                        if fragment_end <= len(self.mp4_buffer):
                            fragment = bytes(self.mp4_buffer[0:fragment_end])
                            self.mp4_buffer = self.mp4_buffer[fragment_end:]
                            return fragment
                else:
                    # Buffer doesn't start with ftyp or moof - clear garbage
                    STATE.add_log(f"MP4 buffer has invalid start: {box_type}, clearing buffer")
                    self.mp4_buffer.clear()
                    return None

        except Exception as e:
            STATE.add_log(f"MP4 fragment extraction error: {e}")

        return None

    def _ffmpeg_reader_thread(self):
        """Read MP4 fragments from FFmpeg stdout, broadcast to WebSocket clients."""
        while self.running:
            try:
                if not self.ffmpeg_process or self.ffmpeg_process.poll() is not None:
                    # FFmpeg died, restart
                    STATE.add_log("FFmpeg process died, restarting...")
                    time.sleep(2)
                    self._start_ffmpeg()
                    continue

                chunk = self.ffmpeg_process.stdout.read(4096)
                if not chunk:
                    STATE.add_log("FFmpeg stdout closed")
                    time.sleep(1)
                    continue

                self.mp4_buffer.extend(chunk)

                # Extract and add complete MP4 fragments to queue
                while True:
                    fragment = self._extract_mp4_fragment()
                    if fragment is None:
                        break

                    # Log fragment type for debugging
                    frag_type = fragment[4:8].decode('ascii', errors='ignore') if len(fragment) >= 8 else 'unknown'
                    if frag_type == 'ftyp':
                        STATE.add_log(f"Extracted INIT segment: {len(fragment)} bytes")
                    elif frag_type == 'moof':
                        # Only log first few moof segments to avoid spam
                        if len(self.frame_queue) < 5:
                            STATE.add_log(f"Extracted media segment: {len(fragment)} bytes")

                    # Add to queue for WebSocket clients to consume
                    self.frame_queue.append(fragment)

            except Exception as e:
                STATE.add_log(f"FFmpeg reader error: {e}")
                time.sleep(1)

    def start(self):
        """Start background update threads."""
        self.running = True

        # Detect and start FFmpeg
        self.ffmpeg_encoder = self._detect_h264_encoder()
        self._start_ffmpeg()

        t1 = threading.Thread(target=self._poll_game_state, daemon=True)
        t1.start()
        self.threads.append(t1)

        t2 = threading.Thread(target=self._ffmpeg_reader_thread, daemon=True)
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
    global background_tasks
    background_tasks = DashboardBackgroundTasks(config)
    background_tasks.start()

    try:
        uvicorn.run(app, host=host, port=port, log_level="warning")
    finally:
        background_tasks.stop()


if __name__ == "__main__":
    import yaml
    config_path = os.environ.get("RUNELITE_MCP_CONFIG", "config.yaml")
    with open(config_path) as f:
        config = yaml.safe_load(f)

    print("Starting Manny MCP Dashboard on http://0.0.0.0:8080")
    run_dashboard(config)
