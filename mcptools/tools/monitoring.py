"""
Monitoring tools for RuneLite process.
Handles logs, game state, and health checks.
"""
import os
import json
import subprocess
import time
from pathlib import Path
from ..registry import registry


# Dependencies injected at startup
runelite_manager = None
config = None
RESPONSE_FILE = "/tmp/manny_response.json"


def set_dependencies(manager, server_config):
    """Inject dependencies (called from server.py startup)"""
    global runelite_manager, config
    runelite_manager = manager
    config = server_config


@registry.register({
    "name": "get_logs",
    "description": "[Monitoring] Get filtered logs from the running RuneLite process.",
    "inputSchema": {
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
})
async def handle_get_logs(arguments: dict) -> dict:
    """Get filtered logs from RuneLite."""
    return runelite_manager.get_logs(
        level=arguments.get("level", "WARN"),
        since_seconds=arguments.get("since_seconds", 30),
        grep=arguments.get("grep"),
        max_lines=arguments.get("max_lines", 100),
        plugin_only=arguments.get("plugin_only", True)
    )


@registry.register({
    "name": "get_game_state",
    "description": "[Monitoring] Read the current game state from /tmp/manny_state.json",
    "inputSchema": {
        "type": "object",
        "properties": {}
    }
})
async def handle_get_game_state(arguments: dict) -> dict:
    """Read game state from state file."""
    state_file = config.state_file
    try:
        with open(state_file) as f:
            state = json.load(f)
        return {"success": True, "state": state}
    except FileNotFoundError:
        return {"success": False, "error": "State file not found - is manny plugin running?"}
    except json.JSONDecodeError as e:
        return {"success": False, "error": f"Invalid JSON: {e}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


@registry.register({
    "name": "check_health",
    "description": "[Monitoring] Check if RuneLite client is healthy - verifies process is running, state file is updating, and window exists. Use this to detect crashes.",
    "inputSchema": {
        "type": "object",
        "properties": {}
    }
})
async def handle_check_health(arguments: dict) -> dict:
    """Check if RuneLite client is healthy."""
    health = {
        "healthy": True,
        "issues": [],
        "process": {"running": False, "pid": None},
        "state_file": {"exists": False, "fresh": False, "age_seconds": None},
        "window": {"exists": False, "position": None}
    }

    # Check process
    if runelite_manager.is_running():
        health["process"]["running"] = True
        health["process"]["pid"] = runelite_manager.process.pid
        health["process"]["managed"] = True
    else:
        # Check for externally-started RuneLite
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
    state_file = config.state_file
    try:
        if os.path.exists(state_file):
            health["state_file"]["exists"] = True
            mtime = os.path.getmtime(state_file)
            age = time.time() - mtime
            health["state_file"]["age_seconds"] = round(age, 1)

            # State should update every ~600ms, stale after 5 seconds
            if age < 5:
                health["state_file"]["fresh"] = True
            else:
                health["healthy"] = False
                health["issues"].append(f"State file stale ({age:.1f}s old)")

            # Check internal timestamp and player data
            try:
                with open(state_file) as f:
                    state = json.load(f)
                    if "timestamp" in state:
                        internal_age = (time.time() * 1000 - state["timestamp"]) / 1000
                        health["state_file"]["internal_age_seconds"] = round(internal_age, 1)

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

    # Check if window exists
    display = config.display
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
