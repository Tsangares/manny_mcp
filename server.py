#!/home/wil/manny-mcp/venv/bin/python
"""RuneLite Debug MCP Server - Phase 1: Core Loop"""

import asyncio
import json
import os
import re
import signal
import subprocess
import threading
import time
from collections import deque
from datetime import datetime
from pathlib import Path

import yaml
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent, ImageContent
import base64
from dotenv import load_dotenv

# Import code change tools (staging workflow)
from request_code_change import (
    prepare_code_change,
    validate_code_change,
    deploy_code_change,
    find_relevant_files,
    backup_files,
    rollback_code_change,
    diagnose_issues,
    PREPARE_CODE_CHANGE_TOOL,
    VALIDATE_CODE_CHANGE_TOOL,
    DEPLOY_CODE_CHANGE_TOOL,
    FIND_RELEVANT_FILES_TOOL,
    BACKUP_FILES_TOOL,
    ROLLBACK_CODE_CHANGE_TOOL,
    DIAGNOSE_ISSUES_TOOL
)

# Import manny-specific tools
from manny_tools import (
    get_manny_guidelines,
    get_plugin_context,
    get_section,
    find_command,
    find_pattern_in_plugin,
    generate_command_template,
    check_anti_patterns,
    get_class_summary,
    find_similar_fix,
    get_threading_patterns,
    find_blocking_patterns,
    generate_debug_instrumentation,
    get_blocking_trace,
    GET_PLUGIN_CONTEXT_TOOL,
    GET_SECTION_TOOL,
    FIND_COMMAND_TOOL,
    FIND_PATTERN_TOOL,
    GENERATE_COMMAND_TEMPLATE_TOOL,
    CHECK_ANTI_PATTERNS_TOOL,
    GET_CLASS_SUMMARY_TOOL,
    FIND_SIMILAR_FIX_TOOL,
    GET_THREADING_PATTERNS_TOOL,
    FIND_BLOCKING_PATTERNS_TOOL,
    GENERATE_DEBUG_INSTRUMENTATION_TOOL,
    GET_BLOCKING_TRACE_TOOL
)

# Load environment variables (for GEMINI_API_KEY)
load_dotenv()

# Try to import Gemini API
try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
    genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))
except ImportError:
    GEMINI_AVAILABLE = False

# Try to import Anthropic API for Haiku-powered tools
try:
    from anthropic import Anthropic
    ANTHROPIC_AVAILABLE = True
    anthropic_client = Anthropic()  # Uses ANTHROPIC_API_KEY from env
except ImportError:
    ANTHROPIC_AVAILABLE = False
    anthropic_client = None


async def call_haiku(prompt: str, max_tokens: int = 1000) -> str:
    """
    Fast Haiku call for preprocessing tasks.
    Returns the text response or raises an exception.
    """
    if not ANTHROPIC_AVAILABLE:
        raise RuntimeError("Anthropic SDK not installed - pip install anthropic")

    response = anthropic_client.messages.create(
        model="claude-3-5-haiku-20241022",
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.content[0].text

# Load config
CONFIG_PATH = os.environ.get("RUNELITE_MCP_CONFIG",
                             Path(__file__).parent / "config.yaml")

def load_config():
    with open(CONFIG_PATH) as f:
        config = yaml.safe_load(f)
    # Expand ~ in paths
    for key in ["log_file", "session_file", "runelite_jar"]:
        if key in config and isinstance(config[key], str):
            config[key] = os.path.expanduser(config[key])
    return config

CONFIG = load_config()

# Response file for plugin command responses
RESPONSE_FILE = "/tmp/manny_response.json"


async def send_command_with_response(command: str, timeout_ms: int = 3000) -> dict:
    """
    Send a command to the plugin and wait for the response.

    The plugin writes responses to /tmp/manny_response.json after processing commands.
    This function clears the old response, sends the command, and waits for a new response.
    """
    command_file = CONFIG.get("command_file", "/tmp/manny_command.txt")

    # Record the old response timestamp (if exists) to detect new response
    old_mtime = None
    if os.path.exists(RESPONSE_FILE):
        old_mtime = os.path.getmtime(RESPONSE_FILE)

    # Write the command
    with open(command_file, "w") as f:
        f.write(command + "\n")

    # Wait for a new response
    start = time.time()
    timeout_sec = timeout_ms / 1000.0

    while (time.time() - start) < timeout_sec:
        if os.path.exists(RESPONSE_FILE):
            current_mtime = os.path.getmtime(RESPONSE_FILE)
            # Check if file was modified after we sent the command
            if old_mtime is None or current_mtime > old_mtime:
                try:
                    with open(RESPONSE_FILE) as f:
                        response = json.load(f)
                    # Verify it's a response to our command
                    if response.get("command", "").upper() == command.split()[0].upper():
                        return response
                except (json.JSONDecodeError, IOError):
                    pass  # File still being written, wait
        await asyncio.sleep(0.05)

    return {
        "command": command,
        "status": "timeout",
        "error": f"No response received within {timeout_ms}ms"
    }


class RuneLiteManager:
    """Manages RuneLite process and log capture."""

    def __init__(self):
        self.process = None
        self.log_buffer = deque(maxlen=CONFIG.get("log_buffer_size", 10000))
        self.log_lock = threading.Lock()
        self.log_thread = None

    def _capture_logs(self):
        """Background thread to capture process output."""
        if not self.process:
            return
        try:
            for line in iter(self.process.stdout.readline, ''):
                if not line:
                    break
                timestamp = datetime.now().isoformat()
                with self.log_lock:
                    self.log_buffer.append((timestamp, line.rstrip()))
        except Exception:
            pass

    def start(self, developer_mode: bool = True) -> dict:
        """Start RuneLite process."""
        if self.process and self.process.poll() is None:
            # Already running, restart
            self.stop()
            status = "restarted"
        else:
            status = "started"

        # Build the command based on config
        use_vgl = CONFIG.get("use_virtualgl", False)
        vgl_display = CONFIG.get("vgl_display", ":0")

        if CONFIG.get("use_exec_java", False):
            # Use mvn exec:java
            args = " ".join(CONFIG.get("runelite_args", []))
            base_cmd = [
                "mvn", "exec:java",
                "-pl", "runelite-client",
                "-Dexec.mainClass=net.runelite.client.RuneLite",
                "-Dsun.java2d.uiScale=2.0",  # HiDPI scaling - plugin now auto-detects
            ]
            if args:
                base_cmd.append(f"-Dexec.args={args}")
            cwd = CONFIG["runelite_root"]
        else:
            # Use JAR directly
            base_cmd = [CONFIG["java_path"], "-jar", CONFIG["runelite_jar"]]
            base_cmd.extend(CONFIG.get("runelite_args", []))
            cwd = None

        # Wrap with vglrun if VirtualGL is enabled
        if use_vgl:
            cmd = ["vglrun", "-d", vgl_display] + base_cmd
        else:
            cmd = base_cmd

        env = os.environ.copy()
        env["DISPLAY"] = CONFIG.get("display", ":2")
        # Jagex launcher session credentials for auto-login (from .env)
        env["JX_CHARACTER_ID"] = os.environ.get("JX_CHARACTER_ID", "")
        env["JX_DISPLAY_NAME"] = os.environ.get("JX_DISPLAY_NAME", "")
        env["JX_SESSION_ID"] = os.environ.get("JX_SESSION_ID", "")

        self.log_buffer.clear()

        self.process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            env=env,
            cwd=cwd,
            bufsize=1
        )

        # Start log capture thread
        self.log_thread = threading.Thread(target=self._capture_logs, daemon=True)
        self.log_thread.start()

        # Wait briefly for startup
        time.sleep(3)

        with self.log_lock:
            startup_logs = [line for _, line in list(self.log_buffer)[:50]]

        return {
            "pid": self.process.pid,
            "status": status,
            "startup_logs": startup_logs,
            "command": " ".join(cmd)
        }

    def stop(self) -> dict:
        """Stop RuneLite process."""
        if not self.process:
            return {"stopped": False, "exit_code": None, "message": "No process running"}

        pid = self.process.pid

        # Try graceful termination first
        self.process.terminate()
        try:
            exit_code = self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.process.kill()
            exit_code = self.process.wait()

        self.process = None
        return {"stopped": True, "exit_code": exit_code, "pid": pid}

    def is_running(self) -> bool:
        return self.process is not None and self.process.poll() is None

    def get_logs(
        self,
        level: str = "WARN",
        since_seconds: float = 30,
        grep: str = None,
        max_lines: int = 100,
        plugin_only: bool = True
    ) -> dict:
        """Get filtered logs from the buffer."""

        level_priority = {"DEBUG": 0, "INFO": 1, "WARN": 2, "ERROR": 3, "ALL": -1}
        min_level = level_priority.get(level.upper(), 2)

        cutoff_time = datetime.now().timestamp() - since_seconds
        plugin_prefix = CONFIG.get("plugin_logger_prefix", "manny")

        matching_lines = []
        total_matching = 0

        with self.log_lock:
            for timestamp_str, line in self.log_buffer:
                try:
                    ts = datetime.fromisoformat(timestamp_str).timestamp()
                except:
                    ts = 0

                # Time filter
                if ts < cutoff_time:
                    continue

                # Level filter
                if min_level >= 0:
                    line_level = -1
                    if "[DEBUG]" in line or " DEBUG " in line:
                        line_level = 0
                    elif "[INFO]" in line or " INFO " in line:
                        line_level = 1
                    elif "[WARN]" in line or " WARN " in line:
                        line_level = 2
                    elif "[ERROR]" in line or " ERROR " in line:
                        line_level = 3

                    if line_level < min_level:
                        continue

                # Plugin filter
                if plugin_only and plugin_prefix.lower() not in line.lower():
                    continue

                # Grep filter
                if grep and grep.lower() not in line.lower():
                    continue

                total_matching += 1
                if len(matching_lines) < max_lines:
                    matching_lines.append(line)

        return {
            "lines": matching_lines,
            "truncated": total_matching > max_lines,
            "total_matching": total_matching
        }


def parse_maven_errors(output: str) -> list:
    """Parse Maven output for compilation errors."""
    errors = []
    # Match patterns like: [ERROR] /path/to/File.java:[42,15] error message
    error_pattern = re.compile(
        r'\[ERROR\]\s+([^:]+):?\[?(\d+)?[,\]]?\s*(.+)'
    )

    for line in output.split('\n'):
        if '[ERROR]' in line:
            match = error_pattern.match(line.strip())
            if match:
                file_path = match.group(1).strip()
                line_num = match.group(2)
                message = match.group(3).strip() if match.group(3) else line
                errors.append({
                    "file": file_path,
                    "line": int(line_num) if line_num else None,
                    "message": message
                })
            else:
                # Generic error line
                errors.append({
                    "file": None,
                    "line": None,
                    "message": line.replace('[ERROR]', '').strip()
                })
    return errors


def parse_maven_warnings(output: str) -> list:
    """Parse Maven output for warnings."""
    warnings = []
    for line in output.split('\n'):
        if '[WARNING]' in line:
            warnings.append(line.replace('[WARNING]', '').strip())
    return warnings


def build_plugin(clean: bool = True) -> dict:
    """Run Maven to compile the plugin."""
    start_time = time.time()

    cmd = ["mvn"]
    if clean:
        cmd.append("clean")
    cmd.extend(["compile", "-pl", "runelite-client", "-T", "1C", "-DskipTests"])

    result = subprocess.run(
        cmd,
        cwd=CONFIG["runelite_root"],
        capture_output=True,
        text=True,
        timeout=300  # 5 minute timeout
    )

    build_time = time.time() - start_time
    output = result.stdout + result.stderr

    errors = parse_maven_errors(output)
    warnings = parse_maven_warnings(output)

    return {
        "success": result.returncode == 0,
        "build_time_seconds": round(build_time, 2),
        "errors": errors,
        "warnings": warnings[:10],  # Truncate warnings
        "return_code": result.returncode
    }


def take_screenshot(output_path: str = None, mode: str = "fullscreen") -> dict:
    """
    Capture screenshot of display :2, optionally cropped to game viewport.

    Args:
        output_path: Where to save (default: /tmp/runelite_screenshot_<timestamp>.png)
        mode: "fullscreen" (entire window) or "viewport" (game area only: 1020x666+200+8)

    Returns:
        dict with success, path, base64, display, mode
    """
    display = CONFIG.get("display", ":2")

    if output_path is None:
        output_path = f"/tmp/runelite_screenshot_{int(time.time())}.png"

    env = os.environ.copy()
    env["DISPLAY"] = display

    try:
        # First, find the RuneLite window ID
        window_result = subprocess.run(
            ["xdotool", "search", "--name", "RuneLite"],
            env=env,
            capture_output=True,
            text=True,
            timeout=5
        )

        window_id = None
        if window_result.returncode == 0 and window_result.stdout.strip():
            # Take the first window ID found
            window_id = window_result.stdout.strip().split('\n')[0]

        if window_id:
            # Use ImageMagick import to capture the specific window (works with XWayland)
            result = subprocess.run(
                ["import", "-window", window_id, output_path],
                env=env,
                capture_output=True,
                text=True,
                timeout=10
            )
        else:
            # Fallback to scrot for root window if no RuneLite window found
            result = subprocess.run(
                ["scrot", "-o", output_path],
                env=env,
                capture_output=True,
                text=True,
                timeout=10
            )

        if result.returncode != 0:
            return {"success": False, "error": result.stderr or "Screenshot capture failed"}

        # Crop to game viewport if requested
        if mode == "viewport":
            try:
                from PIL import Image
                img = Image.open(output_path)
                # Official viewport coordinates from CLAUDE.md: 1020x666 at offset 200,8
                # PIL crop format: (left, top, right, bottom) = (200, 8, 1220, 674)
                cropped = img.crop((200, 8, 1220, 674))
                cropped.save(output_path)
            except ImportError:
                pass  # PIL not available, use uncropped
            except Exception:
                pass  # Cropping failed, use uncropped

        # Read and encode the image
        with open(output_path, "rb") as f:
            image_data = base64.b64encode(f.read()).decode("utf-8")

        return {
            "success": True,
            "path": output_path,
            "base64": image_data,
            "display": display,
            "mode": mode
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "Screenshot timed out"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def check_client_health() -> dict:
    """Check if RuneLite client is healthy - process running, state updating, window exists."""
    health = {
        "healthy": True,
        "issues": [],
        "process": {"running": False, "pid": None},
        "state_file": {"exists": False, "fresh": False, "age_seconds": None},
        "window": {"exists": False, "position": None}
    }

    # Check process - first check managed process, then look for any RuneLite
    if runelite_manager.is_running():
        health["process"]["running"] = True
        health["process"]["pid"] = runelite_manager.process.pid
        health["process"]["managed"] = True
    else:
        # Check for externally-started RuneLite via pgrep
        try:
            result = subprocess.run(
                ["pgrep", "-f", "runelite"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0 and result.stdout.strip():
                pids = result.stdout.strip().split('\n')
                health["process"]["running"] = True
                health["process"]["pid"] = int(pids[0])
                health["process"]["managed"] = False
            else:
                health["healthy"] = False
                health["issues"].append("RuneLite process not running")
        except Exception as e:
            health["healthy"] = False
            health["issues"].append(f"Could not check for RuneLite process: {e}")

    # Check state file freshness
    state_file = CONFIG.get("state_file", "/tmp/manny_state.json")
    try:
        if os.path.exists(state_file):
            health["state_file"]["exists"] = True
            mtime = os.path.getmtime(state_file)
            age = time.time() - mtime
            health["state_file"]["age_seconds"] = round(age, 1)

            # State should update every ~600ms (game tick), stale after 5 seconds
            if age < 5:
                health["state_file"]["fresh"] = True
            else:
                health["healthy"] = False
                health["issues"].append(f"State file stale ({age:.1f}s old)")

            # Also check the timestamp inside the file and verify meaningful player data
            try:
                with open(state_file) as f:
                    state = json.load(f)
                    if "timestamp" in state:
                        internal_age = (time.time() * 1000 - state["timestamp"]) / 1000
                        health["state_file"]["internal_age_seconds"] = round(internal_age, 1)

                    # Check for meaningful player data (location exists = game is running)
                    player = state.get("player", {})
                    location = player.get("location", {})
                    if location.get("x") and location.get("y"):
                        health["state_file"]["has_player_data"] = True
                    else:
                        health["state_file"]["has_player_data"] = False
                        health["healthy"] = False
                        health["issues"].append("State file missing player location - game may have crashed")
            except:
                pass
        else:
            health["healthy"] = False
            health["issues"].append("State file does not exist")
    except Exception as e:
        health["issues"].append(f"Error checking state file: {e}")

    # Check if window exists using xdotool
    display = CONFIG.get("display", ":2")
    try:
        env = os.environ.copy()
        env["DISPLAY"] = display
        result = subprocess.run(
            ["xdotool", "search", "--name", "RuneLite"],
            env=env,
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0 and result.stdout.strip():
            health["window"]["exists"] = True
            window_id = result.stdout.strip().split('\n')[0]
            # Get window geometry
            geom_result = subprocess.run(
                ["xdotool", "getwindowgeometry", window_id],
                env=env,
                capture_output=True,
                text=True,
                timeout=5
            )
            if geom_result.returncode == 0:
                health["window"]["geometry"] = geom_result.stdout.strip()
        else:
            health["healthy"] = False
            health["issues"].append("RuneLite window not found")
    except FileNotFoundError:
        health["issues"].append("xdotool not installed - cannot check window")
    except subprocess.TimeoutExpired:
        health["issues"].append("Window check timed out")
    except Exception as e:
        health["issues"].append(f"Error checking window: {e}")

    return health


def analyze_screenshot_with_gemini(prompt: str = None, screenshot_path: str = None) -> dict:
    """Use Gemini to visually analyze a screenshot."""
    if not GEMINI_AVAILABLE:
        return {"success": False, "error": "Gemini API not available - install google-generativeai"}

    if not os.environ.get("GEMINI_API_KEY"):
        return {"success": False, "error": "GEMINI_API_KEY not set in environment"}

    # Take screenshot if not provided (always fullscreen for better context)
    if screenshot_path is None:
        screenshot_result = take_screenshot(mode="fullscreen")
        if not screenshot_result["success"]:
            return {"success": False, "error": f"Failed to take screenshot: {screenshot_result.get('error')}"}
        screenshot_path = screenshot_result["path"]

    # Default prompt for OSRS analysis
    if prompt is None:
        prompt = """Analyze this Old School RuneScape screenshot. Please tell me:
1. Player location (be specific - town name, area)
2. What is the player currently doing or hovering over?
3. Inventory contents - list all visible items
4. Equipment visible (if any panel is open)
5. Health/Prayer/Run energy status
6. Any important observations for automation (NPCs, objects, obstacles)

Be concise and accurate - this is used for game automation."""

    try:
        with open(screenshot_path, "rb") as f:
            image_data = f.read()

        model = genai.GenerativeModel('gemini-2.5-flash-lite')  # Cheapest option
        image_part = {"mime_type": "image/png", "data": image_data}

        response = model.generate_content([prompt, image_part])

        return {
            "success": True,
            "analysis": response.text,
            "screenshot_path": screenshot_path,
            "model": "gemini-2.5-flash"
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


# Global manager instance
runelite_manager = RuneLiteManager()

# Global state for Haiku delta tracking
_last_game_state = {}

# Create MCP server
server = Server("runelite-debug")


@server.list_tools()
async def list_tools():
    return [
        Tool(
            name="build_plugin",
            description="Compile the manny RuneLite plugin using Maven. Returns structured build results with any errors.",
            inputSchema={
                "type": "object",
                "properties": {
                    "clean": {
                        "type": "boolean",
                        "description": "Whether to run 'mvn clean' first (default: true)",
                        "default": True
                    }
                }
            }
        ),
        Tool(
            name="start_runelite",
            description="Start or restart the RuneLite client with the manny plugin loaded. Runs on display :2.",
            inputSchema={
                "type": "object",
                "properties": {
                    "developer_mode": {
                        "type": "boolean",
                        "description": "Enable RuneLite developer mode (default: true)",
                        "default": True
                    }
                }
            }
        ),
        Tool(
            name="stop_runelite",
            description="Stop the managed RuneLite process.",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        Tool(
            name="get_logs",
            description="Get filtered logs from the running RuneLite process.",
            inputSchema={
                "type": "object",
                "properties": {
                    "level": {
                        "type": "string",
                        "enum": ["DEBUG", "INFO", "WARN", "ERROR", "ALL"],
                        "description": "Minimum log level to include (default: WARN)",
                        "default": "WARN"
                    },
                    "since_seconds": {
                        "type": "number",
                        "description": "Only logs from last N seconds (default: 30)",
                        "default": 30
                    },
                    "grep": {
                        "type": "string",
                        "description": "Filter to lines containing this substring"
                    },
                    "max_lines": {
                        "type": "integer",
                        "description": "Maximum number of lines to return (default: 100)",
                        "default": 100
                    },
                    "plugin_only": {
                        "type": "boolean",
                        "description": "Only show logs from the manny plugin (default: true)",
                        "default": True
                    }
                }
            }
        ),
        Tool(
            name="runelite_status",
            description="Check if RuneLite is currently running.",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        Tool(
            name="send_command",
            description="Send a command to the manny plugin via /tmp/manny_command.txt",
            inputSchema={
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "The command to send (e.g., 'GOTO 3200 3200 0', 'BANK_OPEN')"
                    }
                },
                "required": ["command"]
            }
        ),
        Tool(
            name="send_input",
            description="""Send input directly to RuneLite canvas via Java AWT events.

Works regardless of Wayland/X11 setup because it uses the plugin's internal Mouse/Keyboard classes.

Input types:
- click: Click at x,y coordinates (button 1=left, 2=middle, 3=right)
- key: Press a key (e.g., "Return", "Escape", "Space", "a", "1")
- move: Move mouse to x,y without clicking

Use this to:
- Dismiss login/disconnect dialogs
- Click UI elements when game commands don't work
- Send keyboard input to the game""",
            inputSchema={
                "type": "object",
                "properties": {
                    "input_type": {
                        "type": "string",
                        "enum": ["click", "key", "move"],
                        "description": "Type of input to send"
                    },
                    "x": {
                        "type": "integer",
                        "description": "X coordinate (for click/move)"
                    },
                    "y": {
                        "type": "integer",
                        "description": "Y coordinate (for click/move)"
                    },
                    "button": {
                        "type": "integer",
                        "description": "Mouse button: 1=left, 2=middle, 3=right (default: 1)",
                        "default": 1
                    },
                    "key": {
                        "type": "string",
                        "description": "Key to press (for key type). E.g., 'Return', 'Escape', 'Space', 'a'"
                    }
                },
                "required": ["input_type"]
            }
        ),
        Tool(
            name="get_game_state",
            description="Read the current game state from /tmp/manny_state.json",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        Tool(
            name="get_screenshot",
            description="Capture a screenshot of the RuneLite window on display :2. Returns the image as base64 and saves to a file.",
            inputSchema={
                "type": "object",
                "properties": {
                    "output_path": {
                        "type": "string",
                        "description": "Optional path to save the screenshot (default: /tmp/runelite_screenshot_<timestamp>.png)"
                    }
                }
            }
        ),
        Tool(
            name="analyze_screenshot",
            description="Use Gemini AI to visually analyze a screenshot of the game. Can answer questions about what's on screen.",
            inputSchema={
                "type": "object",
                "properties": {
                    "prompt": {
                        "type": "string",
                        "description": "Custom prompt for analysis (default: general OSRS state analysis)"
                    },
                    "screenshot_path": {
                        "type": "string",
                        "description": "Path to existing screenshot (default: takes new screenshot)"
                    }
                }
            }
        ),
        Tool(
            name="check_health",
            description="Check if RuneLite client is healthy - verifies process is running, state file is updating, and window exists. Use this to detect crashes.",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        # Code change tools (staging workflow)
        Tool(
            name=PREPARE_CODE_CHANGE_TOOL["name"],
            description=PREPARE_CODE_CHANGE_TOOL["description"],
            inputSchema=PREPARE_CODE_CHANGE_TOOL["inputSchema"]
        ),
        Tool(
            name=VALIDATE_CODE_CHANGE_TOOL["name"],
            description=VALIDATE_CODE_CHANGE_TOOL["description"],
            inputSchema=VALIDATE_CODE_CHANGE_TOOL["inputSchema"]
        ),
        Tool(
            name=DEPLOY_CODE_CHANGE_TOOL["name"],
            description=DEPLOY_CODE_CHANGE_TOOL["description"],
            inputSchema=DEPLOY_CODE_CHANGE_TOOL["inputSchema"]
        ),
        # Helper tools
        Tool(
            name=FIND_RELEVANT_FILES_TOOL["name"],
            description=FIND_RELEVANT_FILES_TOOL["description"],
            inputSchema=FIND_RELEVANT_FILES_TOOL["inputSchema"]
        ),
        Tool(
            name=BACKUP_FILES_TOOL["name"],
            description=BACKUP_FILES_TOOL["description"],
            inputSchema=BACKUP_FILES_TOOL["inputSchema"]
        ),
        Tool(
            name=ROLLBACK_CODE_CHANGE_TOOL["name"],
            description=ROLLBACK_CODE_CHANGE_TOOL["description"],
            inputSchema=ROLLBACK_CODE_CHANGE_TOOL["inputSchema"]
        ),
        Tool(
            name=DIAGNOSE_ISSUES_TOOL["name"],
            description=DIAGNOSE_ISSUES_TOOL["description"],
            inputSchema=DIAGNOSE_ISSUES_TOOL["inputSchema"]
        ),
        # Manny-specific tools
        Tool(
            name=GET_PLUGIN_CONTEXT_TOOL["name"],
            description=GET_PLUGIN_CONTEXT_TOOL["description"],
            inputSchema=GET_PLUGIN_CONTEXT_TOOL["inputSchema"]
        ),
        Tool(
            name=GET_SECTION_TOOL["name"],
            description=GET_SECTION_TOOL["description"],
            inputSchema=GET_SECTION_TOOL["inputSchema"]
        ),
        Tool(
            name=FIND_COMMAND_TOOL["name"],
            description=FIND_COMMAND_TOOL["description"],
            inputSchema=FIND_COMMAND_TOOL["inputSchema"]
        ),
        Tool(
            name=FIND_PATTERN_TOOL["name"],
            description=FIND_PATTERN_TOOL["description"],
            inputSchema=FIND_PATTERN_TOOL["inputSchema"]
        ),
        Tool(
            name=GENERATE_COMMAND_TEMPLATE_TOOL["name"],
            description=GENERATE_COMMAND_TEMPLATE_TOOL["description"],
            inputSchema=GENERATE_COMMAND_TEMPLATE_TOOL["inputSchema"]
        ),
        Tool(
            name=CHECK_ANTI_PATTERNS_TOOL["name"],
            description=CHECK_ANTI_PATTERNS_TOOL["description"],
            inputSchema=CHECK_ANTI_PATTERNS_TOOL["inputSchema"]
        ),
        Tool(
            name=GET_CLASS_SUMMARY_TOOL["name"],
            description=GET_CLASS_SUMMARY_TOOL["description"],
            inputSchema=GET_CLASS_SUMMARY_TOOL["inputSchema"]
        ),
        Tool(
            name=FIND_SIMILAR_FIX_TOOL["name"],
            description=FIND_SIMILAR_FIX_TOOL["description"],
            inputSchema=FIND_SIMILAR_FIX_TOOL["inputSchema"]
        ),
        Tool(
            name=GET_THREADING_PATTERNS_TOOL["name"],
            description=GET_THREADING_PATTERNS_TOOL["description"],
            inputSchema=GET_THREADING_PATTERNS_TOOL["inputSchema"]
        ),
        # Runtime debugging tools
        Tool(
            name=FIND_BLOCKING_PATTERNS_TOOL["name"],
            description=FIND_BLOCKING_PATTERNS_TOOL["description"],
            inputSchema=FIND_BLOCKING_PATTERNS_TOOL["inputSchema"]
        ),
        Tool(
            name=GENERATE_DEBUG_INSTRUMENTATION_TOOL["name"],
            description=GENERATE_DEBUG_INSTRUMENTATION_TOOL["description"],
            inputSchema=GENERATE_DEBUG_INSTRUMENTATION_TOOL["inputSchema"]
        ),
        Tool(
            name=GET_BLOCKING_TRACE_TOOL["name"],
            description=GET_BLOCKING_TRACE_TOOL["description"],
            inputSchema=GET_BLOCKING_TRACE_TOOL["inputSchema"]
        ),
        # Widget and dialogue tools for routine building
        Tool(
            name="scan_widgets",
            description="""Scan all visible widgets in the game UI. Returns widget IDs, text content, and bounds.

Use this to discover clickable elements, dialogue options, interface buttons, etc.
Filter by text to find specific widgets.""",
            inputSchema={
                "type": "object",
                "properties": {
                    "filter_text": {
                        "type": "string",
                        "description": "Optional text to filter widgets by (case-insensitive)"
                    },
                    "timeout_ms": {
                        "type": "integer",
                        "description": "Timeout in milliseconds (default: 3000)",
                        "default": 3000
                    }
                }
            }
        ),
        Tool(
            name="get_dialogue",
            description="""Get the current dialogue state including available options.

Returns whether a dialogue is open, the type (continue button, options, player input),
the speaker name, text, and clickable options with their widget IDs.""",
            inputSchema={
                "type": "object",
                "properties": {
                    "timeout_ms": {
                        "type": "integer",
                        "description": "Timeout in milliseconds (default: 3000)",
                        "default": 3000
                    }
                }
            }
        ),
        Tool(
            name="click_text",
            description="""Find a widget containing the specified text and click it.

Useful for clicking dialogue options, buttons, or any UI element by its text content.
Returns success/failure and the widget ID that was clicked.""",
            inputSchema={
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "The text to search for and click"
                    },
                    "timeout_ms": {
                        "type": "integer",
                        "description": "Timeout in milliseconds (default: 3000)",
                        "default": 3000
                    }
                },
                "required": ["text"]
            }
        ),
        Tool(
            name="click_continue",
            description="""Click the 'Click here to continue' button in dialogues.

Automatically finds and clicks continue buttons in NPC dialogues.
Returns success/failure.""",
            inputSchema={
                "type": "object",
                "properties": {
                    "timeout_ms": {
                        "type": "integer",
                        "description": "Timeout in milliseconds (default: 3000)",
                        "default": 3000
                    }
                }
            }
        ),
        Tool(
            name="query_nearby",
            description="""Query nearby NPCs and objects with their available actions.

Returns lists of NPCs and objects within range, including their names,
distances, and available right-click actions. Useful for discovering
what can be interacted with.""",
            inputSchema={
                "type": "object",
                "properties": {
                    "include_npcs": {
                        "type": "boolean",
                        "description": "Include NPCs in results (default: true)",
                        "default": True
                    },
                    "include_objects": {
                        "type": "boolean",
                        "description": "Include objects in results (default: true)",
                        "default": True
                    },
                    "name_filter": {
                        "type": "string",
                        "description": "Optional name filter (case-insensitive)"
                    },
                    "timeout_ms": {
                        "type": "integer",
                        "description": "Timeout in milliseconds (default: 3000)",
                        "default": 3000
                    }
                }
            }
        ),
        Tool(
            name="get_command_response",
            description="""Read the last command response from the plugin.

Returns the most recent response from /tmp/manny_response.json.
Useful for checking results of commands sent via send_command.""",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        # Haiku-powered tools for fast preprocessing
        Tool(
            name="validate_routine",
            description="""Validate a YAML routine file for syntax and semantic errors.

Uses Haiku AI for fast validation. Checks:
- YAML syntax
- Required fields (action, description for each step)
- Valid actions (GOTO, INTERACT_NPC, BANK_OPEN, etc.)
- Coordinate ranges (x/y: 0-15000, plane: 0-3)
- GOTO args format

Returns validation results with errors and warnings.""",
            inputSchema={
                "type": "object",
                "properties": {
                    "routine_path": {
                        "type": "string",
                        "description": "Path to the YAML routine file to validate"
                    }
                },
                "required": ["routine_path"]
            }
        ),
        Tool(
            name="get_log_alerts",
            description="""Get summarized alerts from logs using Haiku AI.

Filters noise and extracts only actionable issues:
- Errors and exceptions
- Stuck/failed patterns
- Unexpected states

Returns a concise summary instead of raw log lines. Token-efficient for monitoring.""",
            inputSchema={
                "type": "object",
                "properties": {
                    "since_seconds": {
                        "type": "integer",
                        "description": "Only analyze logs from last N seconds (default: 60)",
                        "default": 60
                    },
                    "max_log_lines": {
                        "type": "integer",
                        "description": "Max log lines to analyze (default: 100)",
                        "default": 100
                    }
                }
            }
        ),
        Tool(
            name="get_state_delta",
            description="""Get summarized state changes using Haiku AI.

Compares current game state to previous state and returns a one-line delta:
"Moved 47 tiles | +12 fish | Inventory 24→28/28 | +1,200 Fishing XP"

Token-efficient alternative to repeatedly fetching full game state.""",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        )
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict):
    if name == "build_plugin":
        clean = arguments.get("clean", True)
        result = build_plugin(clean=clean)
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "start_runelite":
        developer_mode = arguments.get("developer_mode", True)
        result = runelite_manager.start(developer_mode=developer_mode)
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "stop_runelite":
        result = runelite_manager.stop()
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "get_logs":
        result = runelite_manager.get_logs(
            level=arguments.get("level", "WARN"),
            since_seconds=arguments.get("since_seconds", 30),
            grep=arguments.get("grep"),
            max_lines=arguments.get("max_lines", 100),
            plugin_only=arguments.get("plugin_only", True)
        )
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "runelite_status":
        result = {
            "running": runelite_manager.is_running(),
            "pid": runelite_manager.process.pid if runelite_manager.process else None
        }
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "send_command":
        command = arguments.get("command", "")
        command_file = CONFIG.get("command_file", "/tmp/manny_command.txt")
        try:
            with open(command_file, "w") as f:
                f.write(command + "\n")
            result = {"sent": True, "command": command}
        except Exception as e:
            result = {"sent": False, "error": str(e)}
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "send_input":
        input_type = arguments.get("input_type")
        command_file = CONFIG.get("command_file", "/tmp/manny_command.txt")

        try:
            if input_type == "click":
                x = arguments.get("x")
                y = arguments.get("y")
                button = arguments.get("button", 1)
                if x is None or y is None:
                    result = {"sent": False, "error": "click requires x and y coordinates"}
                else:
                    # Use existing MOUSE_MOVE + MOUSE_CLICK commands
                    # First move to position, then click
                    button_name = {1: "left", 2: "middle", 3: "right"}.get(button, "left")
                    command = f"MOUSE_MOVE {x},{y}\nMOUSE_CLICK {button_name}"
                    with open(command_file, "w") as f:
                        f.write(command + "\n")
                    result = {"sent": True, "input_type": "click", "x": x, "y": y, "button": button_name}

            elif input_type == "key":
                key = arguments.get("key")
                if not key:
                    result = {"sent": False, "error": "key type requires 'key' parameter"}
                else:
                    # KEY_PRESS command - plugin needs to handle this
                    command = f"KEY_PRESS {key}"
                    with open(command_file, "w") as f:
                        f.write(command + "\n")
                    result = {"sent": True, "input_type": "key", "key": key,
                              "note": "KEY_PRESS command may need to be added to plugin"}

            elif input_type == "move":
                x = arguments.get("x")
                y = arguments.get("y")
                if x is None or y is None:
                    result = {"sent": False, "error": "move requires x and y coordinates"}
                else:
                    # Use existing MOUSE_MOVE command
                    command = f"MOUSE_MOVE {x},{y}"
                    with open(command_file, "w") as f:
                        f.write(command + "\n")
                    result = {"sent": True, "input_type": "move", "x": x, "y": y}

            else:
                result = {"sent": False, "error": f"Unknown input_type: {input_type}"}

        except Exception as e:
            result = {"sent": False, "error": str(e)}

        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "get_game_state":
        state_file = CONFIG.get("state_file", "/tmp/manny_state.json")
        try:
            with open(state_file) as f:
                state = json.load(f)
            result = {"success": True, "state": state}
        except FileNotFoundError:
            result = {"success": False, "error": "State file not found - is manny plugin running?"}
        except json.JSONDecodeError as e:
            result = {"success": False, "error": f"Invalid JSON: {e}"}
        except Exception as e:
            result = {"success": False, "error": str(e)}
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "get_screenshot":
        output_path = arguments.get("output_path")
        result = take_screenshot(output_path)
        if result["success"]:
            # Return both the image and metadata
            return [
                ImageContent(type="image", data=result["base64"], mimeType="image/png"),
                TextContent(type="text", text=json.dumps({
                    "success": True,
                    "path": result["path"],
                    "display": result["display"]
                }, indent=2))
            ]
        else:
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "analyze_screenshot":
        prompt = arguments.get("prompt")
        screenshot_path = arguments.get("screenshot_path")
        result = analyze_screenshot_with_gemini(prompt=prompt, screenshot_path=screenshot_path)
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "check_health":
        result = check_client_health()
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "prepare_code_change":
        result = prepare_code_change(
            problem_description=arguments["problem_description"],
            relevant_files=arguments["relevant_files"],
            logs=arguments.get("logs", ""),
            game_state=arguments.get("game_state"),
            manny_src=CONFIG.get("plugin_directory"),
            auto_include_guidelines=arguments.get("auto_include_guidelines", True),
            compact=arguments.get("compact", False),
            max_file_lines=arguments.get("max_file_lines", 0)
        )
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "validate_code_change":
        result = validate_code_change(
            runelite_root=CONFIG.get("runelite_root"),
            modified_files=arguments.get("modified_files")
        )
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "deploy_code_change":
        result = deploy_code_change(
            runelite_root=CONFIG.get("runelite_root"),
            restart_after=arguments.get("restart_after", True)
        )
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "find_relevant_files":
        result = find_relevant_files(
            manny_src=CONFIG.get("plugin_directory"),
            search_term=arguments.get("search_term"),
            class_name=arguments.get("class_name"),
            error_message=arguments.get("error_message")
        )
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "backup_files":
        result = backup_files(
            file_paths=arguments["file_paths"]
        )
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "rollback_code_change":
        result = rollback_code_change(
            file_paths=arguments.get("file_paths")
        )
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "diagnose_issues":
        result = diagnose_issues(
            log_lines=arguments["log_lines"],
            game_state=arguments.get("game_state"),
            manny_src=CONFIG.get("plugin_directory")
        )
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    # Manny-specific tools
    elif name == "get_plugin_context":
        result = get_plugin_context(
            plugin_dir=CONFIG.get("plugin_directory"),
            context_type=arguments.get("context_type", "full")
        )
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "get_section":
        result = get_section(
            plugin_dir=CONFIG.get("plugin_directory"),
            file=arguments.get("file", "PlayerHelpers.java"),
            section=arguments.get("section", "list"),
            max_lines=arguments.get("max_lines", 0),
            summary_only=arguments.get("summary_only", False)
        )
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "find_command":
        result = find_command(
            plugin_dir=CONFIG.get("plugin_directory"),
            command=arguments["command"],
            include_handler=arguments.get("include_handler", True),
            max_handler_lines=arguments.get("max_handler_lines", 50),
            summary_only=arguments.get("summary_only", False)
        )
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "find_pattern":
        result = find_pattern_in_plugin(
            plugin_dir=CONFIG.get("plugin_directory"),
            pattern_type=arguments["pattern_type"],
            search_term=arguments.get("search_term")
        )
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "generate_command_template":
        result = generate_command_template(
            command_name=arguments["command_name"],
            description=arguments.get("description", "TODO: Add description"),
            has_args=arguments.get("has_args", False),
            args_format=arguments.get("args_format", "<arg>"),
            has_loop=arguments.get("has_loop", False)
        )
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "check_anti_patterns":
        result = check_anti_patterns(
            code=arguments.get("code"),
            file_path=arguments.get("file_path")
        )
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "get_class_summary":
        result = get_class_summary(
            plugin_dir=CONFIG.get("plugin_directory"),
            class_name=arguments["class_name"]
        )
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "find_similar_fix":
        result = find_similar_fix(
            plugin_dir=CONFIG.get("plugin_directory"),
            problem=arguments["problem"]
        )
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "get_threading_patterns":
        result = get_threading_patterns()
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    # Runtime debugging tools
    elif name == "find_blocking_patterns":
        result = find_blocking_patterns(
            plugin_dir=CONFIG.get("plugin_directory"),
            file_path=arguments.get("file_path")
        )
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "generate_debug_instrumentation":
        result = generate_debug_instrumentation(
            instrumentation_type=arguments["type"],
            threshold_ms=arguments.get("threshold_ms", 100)
        )
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "get_blocking_trace":
        result = get_blocking_trace(
            since_seconds=arguments.get("since_seconds", 60),
            min_duration_ms=arguments.get("min_duration_ms", 100)
        )
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    # Widget and dialogue tools for routine building
    elif name == "scan_widgets":
        timeout_ms = arguments.get("timeout_ms", 3000)
        filter_text = arguments.get("filter_text")

        response = await send_command_with_response("SCAN_WIDGETS", timeout_ms)

        if response.get("status") == "success":
            widgets = response.get("result", {}).get("widgets", [])
            # Apply text filter if provided
            if filter_text:
                filter_lower = filter_text.lower()
                widgets = [w for w in widgets if filter_lower in (w.get("text") or "").lower()]
            result = {
                "success": True,
                "widgets": widgets,
                "count": len(widgets),
                "filtered_by": filter_text
            }
        else:
            result = {
                "success": False,
                "error": response.get("error", "Failed to scan widgets"),
                "raw_response": response
            }
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "get_dialogue":
        timeout_ms = arguments.get("timeout_ms", 3000)

        # Scan widgets first to find dialogue elements
        response = await send_command_with_response("SCAN_WIDGETS", timeout_ms)

        if response.get("status") != "success":
            result = {
                "success": False,
                "dialogue_open": False,
                "error": response.get("error", "Failed to scan widgets")
            }
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        widgets = response.get("result", {}).get("widgets", [])

        # Look for dialogue-related widgets
        # Widget groups: 217 (NPC dialogue), 219 (Player dialogue), 229/231 (options)
        dialogue_info = {
            "success": True,
            "dialogue_open": False,
            "type": None,
            "speaker": None,
            "text": None,
            "options": [],
            "has_continue": False
        }

        for widget in widgets:
            text = widget.get("text", "") or ""
            widget_id = widget.get("id", 0)

            # Check for "Click here to continue"
            if "click here to continue" in text.lower():
                dialogue_info["dialogue_open"] = True
                dialogue_info["has_continue"] = True
                dialogue_info["type"] = "continue"

            # Check for numbered options (dialogue choices often have numbers or specific patterns)
            # Options typically have short text and are clickable
            if text and len(text) < 200 and not "click here" in text.lower():
                # Could be a dialogue option or speaker text
                if widget_id:
                    dialogue_info["options"].append({
                        "text": text,
                        "widget_id": widget_id
                    })

        if dialogue_info["options"]:
            dialogue_info["dialogue_open"] = True
            if not dialogue_info["type"]:
                dialogue_info["type"] = "options"

        return [TextContent(type="text", text=json.dumps(dialogue_info, indent=2))]

    elif name == "click_text":
        text = arguments.get("text", "")
        timeout_ms = arguments.get("timeout_ms", 3000)

        if not text:
            result = {"success": False, "error": "No text provided"}
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        # Use the plugin's CLICK_DIALOGUE command which searches by text
        response = await send_command_with_response(f'CLICK_DIALOGUE {text}', timeout_ms)

        if response.get("status") == "success":
            result = {
                "success": True,
                "clicked": text,
                "message": response.get("result", {}).get("message", "Clicked")
            }
        else:
            result = {
                "success": False,
                "error": response.get("error", "Failed to click text"),
                "searched_for": text
            }
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "click_continue":
        timeout_ms = arguments.get("timeout_ms", 3000)

        # Use the plugin's CLICK_CONTINUE command
        response = await send_command_with_response("CLICK_CONTINUE", timeout_ms)

        if response.get("status") == "success":
            result = {
                "success": True,
                "message": response.get("result", {}).get("message", "Clicked continue")
            }
        else:
            result = {
                "success": False,
                "error": response.get("error", "No continue button found")
            }
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "query_nearby":
        include_npcs = arguments.get("include_npcs", True)
        include_objects = arguments.get("include_objects", True)
        name_filter = arguments.get("name_filter")
        timeout_ms = arguments.get("timeout_ms", 3000)

        result = {
            "success": True,
            "npcs": [],
            "objects": []
        }

        # Query NPCs if requested
        if include_npcs:
            response = await send_command_with_response("QUERY_NPCS", timeout_ms)
            if response.get("status") == "success":
                npcs = response.get("result", {}).get("npcs", [])
                if name_filter:
                    filter_lower = name_filter.lower()
                    npcs = [n for n in npcs if filter_lower in (n.get("name") or "").lower()]
                result["npcs"] = npcs

        # Query objects if requested
        if include_objects:
            response = await send_command_with_response("SCAN_OBJECTS", timeout_ms)
            if response.get("status") == "success":
                objects = response.get("result", {}).get("objects", [])
                if name_filter:
                    filter_lower = name_filter.lower()
                    objects = [o for o in objects if filter_lower in (o.get("name") or "").lower()]
                result["objects"] = objects

        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "get_command_response":
        try:
            if os.path.exists(RESPONSE_FILE):
                with open(RESPONSE_FILE) as f:
                    response = json.load(f)
                result = {
                    "success": True,
                    "response": response
                }
            else:
                result = {
                    "success": False,
                    "error": "No response file found"
                }
        except Exception as e:
            result = {
                "success": False,
                "error": str(e)
            }
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    # Haiku-powered tools
    elif name == "validate_routine":
        routine_path = arguments.get("routine_path", "")

        if not ANTHROPIC_AVAILABLE:
            result = {"valid": False, "errors": ["Anthropic SDK not installed - pip install anthropic"]}
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        try:
            # Read the YAML file
            with open(routine_path) as f:
                content = f.read()

            # Parse YAML to catch syntax errors
            try:
                routine = yaml.safe_load(content)
            except yaml.YAMLError as e:
                result = {"valid": False, "errors": [f"YAML syntax error: {e}"], "warnings": []}
                return [TextContent(type="text", text=json.dumps(result, indent=2))]

            # Use Haiku for semantic validation
            prompt = f"""Validate this OSRS routine YAML. Check for:
- Required fields: each step should have 'action' and 'description'
- Valid actions: GOTO, INTERACT_NPC, INTERACT_OBJECT, BANK_OPEN, BANK_DEPOSIT_ALL, BANK_WITHDRAW, BANK_CLOSE, PICKUP_ITEM, USE_ITEM_ON_NPC, USE_ITEM_ON_OBJECT, DIALOGUE, CLIMB_LADDER_UP, CLIMB_LADDER_DOWN
- Coordinates: x and y should be 0-15000, plane should be 0-3
- GOTO args format should be "x y plane" (three space-separated integers)
- Location references should have x, y, plane fields

Return ONLY valid JSON (no markdown, no explanation):
{{"valid": true/false, "errors": ["error1", "error2"], "warnings": ["warning1"]}}

Routine content:
```yaml
{content}
```"""

            haiku_response = await call_haiku(prompt, max_tokens=500)

            # Parse Haiku's JSON response
            try:
                # Clean up response in case Haiku added markdown
                cleaned = haiku_response.strip()
                if cleaned.startswith("```"):
                    cleaned = cleaned.split("\n", 1)[1]
                if cleaned.endswith("```"):
                    cleaned = cleaned.rsplit("```", 1)[0]
                result = json.loads(cleaned.strip())
            except json.JSONDecodeError:
                result = {
                    "valid": False,
                    "errors": ["Failed to parse Haiku validation response"],
                    "warnings": [],
                    "raw_response": haiku_response
                }

        except FileNotFoundError:
            result = {"valid": False, "errors": [f"File not found: {routine_path}"], "warnings": []}
        except Exception as e:
            result = {"valid": False, "errors": [str(e)], "warnings": []}

        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "get_log_alerts":
        since_seconds = arguments.get("since_seconds", 60)
        max_log_lines = arguments.get("max_log_lines", 100)

        if not ANTHROPIC_AVAILABLE:
            result = {"alerts": [], "summary": "Anthropic SDK not installed", "error": True}
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        # Get raw logs
        logs = runelite_manager.get_logs(
            level="ALL",
            since_seconds=since_seconds,
            max_lines=max_log_lines,
            plugin_only=True
        )

        if not logs["lines"]:
            result = {"alerts": [], "summary": "No recent logs", "log_count": 0}
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        try:
            # Use Haiku to filter and summarize
            log_text = "\n".join(logs["lines"][-max_log_lines:])
            prompt = f"""Analyze these OSRS bot logs. Extract ONLY actionable issues:
- Errors and exceptions (ERROR level or stack traces)
- Stuck/failed patterns ("stuck", "failed", "timeout", "not found")
- Unexpected states or crashes

Ignore: INFO messages, routine progress logs, expected retries (2/3, 3/3), normal operation

Return ONLY valid JSON (no markdown):
{{"alerts": [{{"severity": "error" or "warn", "summary": "brief description"}}], "summary": "one line overall status"}}

If no issues found, return:
{{"alerts": [], "summary": "Operating normally"}}

Logs:
{log_text}"""

            haiku_response = await call_haiku(prompt, max_tokens=500)

            # Parse response
            try:
                cleaned = haiku_response.strip()
                if cleaned.startswith("```"):
                    cleaned = cleaned.split("\n", 1)[1]
                if cleaned.endswith("```"):
                    cleaned = cleaned.rsplit("```", 1)[0]
                result = json.loads(cleaned.strip())
                result["log_count"] = len(logs["lines"])
            except json.JSONDecodeError:
                result = {
                    "alerts": [],
                    "summary": "Failed to parse Haiku response",
                    "raw_response": haiku_response,
                    "log_count": len(logs["lines"])
                }

        except Exception as e:
            result = {"alerts": [], "summary": f"Error: {e}", "error": True}

        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "get_state_delta":
        global _last_game_state

        if not ANTHROPIC_AVAILABLE:
            result = {"delta": "Anthropic SDK not installed", "error": True}
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        # Get current game state
        state_file = CONFIG.get("state_file", "/tmp/manny_state.json")
        try:
            with open(state_file) as f:
                current_state = json.load(f)
        except FileNotFoundError:
            result = {"delta": "State file not found", "error": True}
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
        except json.JSONDecodeError as e:
            result = {"delta": f"Invalid JSON: {e}", "error": True}
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        # First call - no previous state to compare
        if not _last_game_state:
            _last_game_state = current_state
            # Extract key info for first capture
            player = current_state.get("player", {})
            location = player.get("location", {})
            pos_str = f"({location.get('x', '?')}, {location.get('y', '?')})"
            result = {
                "delta": f"First capture at {pos_str}",
                "position": location,
                "first_capture": True
            }
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        try:
            # Use Haiku to compare and summarize
            prompt = f"""Compare these two OSRS game states and summarize MEANINGFUL changes only.

Format: "Moved X tiles | +Y items | -Z items | +N XP in Skill | HP: X→Y"
If no meaningful changes: "No changes"

Only report:
- Position changes (calculate tile distance if moved)
- Inventory changes (items added/removed)
- XP gains (only if changed)
- HP/Prayer changes (only if changed)

Ignore: timestamp differences, unchanged values

Return ONLY the summary string, no JSON, no explanation.

Previous state:
{json.dumps(_last_game_state, indent=2)[:2000]}

Current state:
{json.dumps(current_state, indent=2)[:2000]}"""

            delta = await call_haiku(prompt, max_tokens=150)

            # Update tracked state
            _last_game_state = current_state

            # Extract position for convenience
            player = current_state.get("player", {})
            location = player.get("location", {})

            result = {
                "delta": delta.strip(),
                "position": location
            }

        except Exception as e:
            result = {"delta": f"Error: {e}", "error": True}

        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    else:
        return [TextContent(type="text", text=f"Unknown tool: {name}")]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
