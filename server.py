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
    PREPARE_CODE_CHANGE_TOOL,
    VALIDATE_CODE_CHANGE_TOOL,
    DEPLOY_CODE_CHANGE_TOOL
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
                "-Dsun.java2d.uiScale=1.0",  # Use 1.0 to match plugin's menu calculations
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


def take_screenshot(output_path: str = None, crop_game: bool = False) -> dict:
    """Capture screenshot of display :2, optionally cropped to game area."""
    display = CONFIG.get("display", ":2")

    if output_path is None:
        output_path = f"/tmp/runelite_screenshot_{int(time.time())}.png"

    env = os.environ.copy()
    env["DISPLAY"] = display

    try:
        # Use scrot to capture the screen
        result = subprocess.run(
            ["scrot", "-o", output_path],
            env=env,
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode != 0:
            return {"success": False, "error": result.stderr or "scrot failed"}

        # Crop to game area if requested
        if crop_game:
            try:
                from PIL import Image
                img = Image.open(output_path)
                # Crop to RuneLite client area (game viewport + sidebar)
                # These coordinates work for 3000x1080 display with RuneLite on left
                cropped = img.crop((360, 0, 1170, 560))
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
            "cropped": crop_game
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


def analyze_screenshot_with_gemini(prompt: str = None, screenshot_path: str = None, crop: bool = True) -> dict:
    """Use Gemini to visually analyze a screenshot."""
    if not GEMINI_AVAILABLE:
        return {"success": False, "error": "Gemini API not available - install google-generativeai"}

    if not os.environ.get("GEMINI_API_KEY"):
        return {"success": False, "error": "GEMINI_API_KEY not set in environment"}

    # Take screenshot if not provided (cropped by default to save API costs)
    if screenshot_path is None:
        screenshot_result = take_screenshot(crop_game=crop)
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
            manny_src=CONFIG.get("manny_src")
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

    else:
        return [TextContent(type="text", text=f"Unknown tool: {name}")]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
