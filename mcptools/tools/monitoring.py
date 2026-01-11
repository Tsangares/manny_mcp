"""
Monitoring tools for RuneLite process.
Handles logs, game state, and health checks.
Supports multi-client via account_id parameter.
"""
import os
import json
import subprocess
import time
from pathlib import Path
from ..registry import registry


# Dependencies injected at startup (MultiRuneLiteManager)
runelite_manager = None
config = None


def set_dependencies(manager, server_config):
    """Inject dependencies (called from server.py startup)"""
    global runelite_manager, config
    runelite_manager = manager
    config = server_config


# Common account_id schema property used across tools
ACCOUNT_ID_SCHEMA = {
    "type": "string",
    "description": "Account ID for multi-client support. Omit for default account."
}


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
            },
            "account_id": ACCOUNT_ID_SCHEMA
        }
    }
})
async def handle_get_logs(arguments: dict) -> dict:
    """Get filtered logs from RuneLite for specified account."""
    account_id = arguments.get("account_id")
    instance = runelite_manager.get_instance(account_id)

    if not instance:
        return {
            "account_id": account_id or config.default_account,
            "lines": [],
            "truncated": False,
            "total_matching": 0,
            "error": "No instance running for this account"
        }

    return instance.get_logs(
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
        "properties": {
            "account_id": ACCOUNT_ID_SCHEMA
        }
    }
})
async def handle_get_game_state(arguments: dict) -> dict:
    """Read game state from state file for specified account."""
    account_id = arguments.get("account_id")
    state_file = config.get_state_file(account_id)

    try:
        with open(state_file) as f:
            state = json.load(f)
        return {
            "success": True,
            "account_id": account_id or config.default_account,
            "state": state
        }
    except FileNotFoundError:
        return {
            "success": False,
            "account_id": account_id or config.default_account,
            "error": f"State file not found ({state_file}) - is manny plugin running?"
        }
    except json.JSONDecodeError as e:
        return {"success": False, "error": f"Invalid JSON: {e}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


# Known crash patterns in logs
CRASH_PATTERNS = [
    ("Client error: map loading", "Map loading crash - client failed to load region data"),
    ("Client error", "Generic client crash"),
    ("OutOfMemoryError", "Out of memory - client ran out of heap space"),
    ("StackOverflowError", "Stack overflow - infinite recursion detected"),
    ("NullPointerException", "Null pointer exception in client"),
    ("TIMEOUT after", "Client thread timeout - game may be frozen"),
]


def _scan_logs_for_crashes(instance, since_seconds: int = 60) -> list:
    """Scan recent logs for crash indicators."""
    if not instance:
        return []

    crashes = []
    try:
        log_result = instance.get_logs(
            level="ERROR",
            since_seconds=since_seconds,
            max_lines=50,
            plugin_only=False
        )

        log_lines = log_result.get("lines", [])
        for line in log_lines:
            for pattern, description in CRASH_PATTERNS:
                if pattern in line:
                    crashes.append({
                        "pattern": pattern,
                        "description": description,
                        "log_line": line[:200]  # Truncate long lines
                    })
                    break  # Only report first matching pattern per line
    except Exception:
        pass

    return crashes


@registry.register({
    "name": "check_health",
    "description": "[Monitoring] Check if RuneLite client is healthy - verifies process is running, state file is updating, and window exists. Use this to detect crashes.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "account_id": ACCOUNT_ID_SCHEMA
        }
    }
})
async def handle_check_health(arguments: dict) -> dict:
    """Check if RuneLite client is healthy for specified account."""
    account_id = arguments.get("account_id")
    instance = runelite_manager.get_instance(account_id)
    account_config = config.get_account_config(account_id)

    health = {
        "healthy": True,
        "account_id": account_id or config.default_account,
        "issues": [],
        "crashes_detected": [],
        "process": {"running": False, "pid": None},
        "state_file": {"exists": False, "fresh": False, "age_seconds": None},
        "window": {"exists": False, "position": None}
    }

    # Check process for this account
    if instance and instance.is_running():
        health["process"]["running"] = True
        health["process"]["pid"] = instance.process.pid
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

    # Check state file freshness for this account
    state_file = config.get_state_file(account_id)
    try:
        if os.path.exists(state_file):
            health["state_file"]["exists"] = True
            health["state_file"]["path"] = state_file
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
            health["issues"].append(f"State file does not exist: {state_file}")
    except Exception as e:
        health["issues"].append(f"Error checking state file: {e}")

    # Check if window exists on account's display
    display = account_config.display
    health["window"]["display"] = display
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
            health["issues"].append(f"RuneLite window not found on display {display}")
    except FileNotFoundError:
        health["issues"].append("xdotool not installed - cannot check window")
    except subprocess.TimeoutExpired:
        health["issues"].append("Window check timed out")
    except Exception as e:
        health["issues"].append(f"Error checking window: {e}")

    # Scan logs for crash indicators (last 60 seconds)
    crashes = _scan_logs_for_crashes(instance, since_seconds=60)
    if crashes:
        health["crashes_detected"] = crashes
        # Mark as unhealthy if we see critical crashes
        critical_patterns = ["Client error", "OutOfMemoryError", "StackOverflowError"]
        for crash in crashes:
            if any(p in crash["pattern"] for p in critical_patterns):
                health["healthy"] = False
                health["issues"].append(f"Crash detected: {crash['description']}")
                break

    return health


@registry.register({
    "name": "is_alive",
    "description": "[Monitoring] Fast crash check - returns alive/dead status in <1 second. Use this for quick polling instead of check_health.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "account_id": ACCOUNT_ID_SCHEMA,
            "max_stale_seconds": {
                "type": "number",
                "description": "Max seconds state file can be stale before considered dead (default: 30)",
                "default": 30
            }
        }
    }
})
async def handle_is_alive(arguments: dict) -> dict:
    """Fast health check - just process + state freshness."""
    account_id = arguments.get("account_id")
    max_stale = arguments.get("max_stale_seconds", 30)

    instance = runelite_manager.get_instance(account_id)
    state_file = config.get_state_file(account_id)

    # Quick process check
    process_alive = False
    if instance and instance.is_running():
        process_alive = True
    else:
        try:
            result = subprocess.run(
                ["pgrep", "-f", "net.runelite.client.RuneLite"],
                capture_output=True, timeout=2
            )
            process_alive = result.returncode == 0
        except:
            pass

    # Quick state file check
    state_fresh = False
    state_age = None
    try:
        if os.path.exists(state_file):
            state_age = round(time.time() - os.path.getmtime(state_file), 1)
            state_fresh = state_age < max_stale
    except:
        pass

    alive = process_alive and state_fresh
    status = "ALIVE" if alive else ("DEAD" if not process_alive else "STALE")

    return {
        "alive": alive,
        "status": status,
        "process_running": process_alive,
        "state_age_seconds": state_age,
        "state_fresh": state_fresh
    }


# ============================================================================
# STATE-AWARE WAITING
# ============================================================================

def _parse_condition(condition: str) -> tuple:
    """
    Parse a condition string into (type, value, operator).

    Supported formats:
    - plane:N - Player on plane N
    - has_item:ItemName - Inventory contains item
    - no_item:ItemName - Inventory doesn't have item
    - inventory_count:<=N or inventory_count:>=N - Slot count comparison
    - location:X,Y - Player near coordinates (within 3 tiles)
    - idle - Player not animating/moving
    """
    if ":" not in condition:
        if condition == "idle":
            return ("idle", None, None)
        raise ValueError(f"Invalid condition format: {condition}")

    parts = condition.split(":", 1)
    cond_type = parts[0].lower()
    value = parts[1]

    if cond_type == "plane":
        return ("plane", int(value), "==")
    elif cond_type == "has_item":
        return ("has_item", value, None)
    elif cond_type == "no_item":
        return ("no_item", value, None)
    elif cond_type == "inventory_count":
        if value.startswith("<="):
            return ("inventory_count", int(value[2:]), "<=")
        elif value.startswith(">="):
            return ("inventory_count", int(value[2:]), ">=")
        elif value.startswith("<"):
            return ("inventory_count", int(value[1:]), "<")
        elif value.startswith(">"):
            return ("inventory_count", int(value[1:]), ">")
        else:
            return ("inventory_count", int(value), "==")
    elif cond_type == "location":
        coords = value.split(",")
        return ("location", (int(coords[0]), int(coords[1])), None)
    else:
        raise ValueError(f"Unknown condition type: {cond_type}")


def _check_condition(state: dict, condition: tuple) -> bool:
    """Check if game state matches the parsed condition."""
    cond_type, value, operator = condition

    player = state.get("player", {})

    if cond_type == "plane":
        location = player.get("location", {})
        current_plane = location.get("plane", -1)
        return current_plane == value

    elif cond_type == "has_item":
        inventory = player.get("inventory", {})
        items = inventory.get("items", [])
        item_name_lower = value.lower()
        for item in items:
            if item and item.get("name", "").lower() == item_name_lower:
                return True
        return False

    elif cond_type == "no_item":
        inventory = player.get("inventory", {})
        items = inventory.get("items", [])
        item_name_lower = value.lower()
        for item in items:
            if item and item.get("name", "").lower() == item_name_lower:
                return False
        return True

    elif cond_type == "inventory_count":
        inventory = player.get("inventory", {})
        items = inventory.get("items", [])
        count = sum(1 for item in items if item is not None)

        if operator == "<=":
            return count <= value
        elif operator == ">=":
            return count >= value
        elif operator == "<":
            return count < value
        elif operator == ">":
            return count > value
        else:
            return count == value

    elif cond_type == "location":
        location = player.get("location", {})
        current_x = location.get("x", 0)
        current_y = location.get("y", 0)
        target_x, target_y = value
        distance = abs(current_x - target_x) + abs(current_y - target_y)
        return distance <= 3

    elif cond_type == "idle":
        is_moving = player.get("isMoving", False)
        # Could also check animation, but isMoving is most reliable
        return not is_moving

    return False


@registry.register({
    "name": "await_state_change",
    "description": """[Monitoring] Wait for game state to match a condition. Returns when condition met or timeout.

Supported conditions:
- plane:N - Player on plane N (0, 1, or 2)
- has_item:ItemName - Inventory contains item (case-insensitive)
- no_item:ItemName - Inventory doesn't have item
- inventory_count:<=N or >=N or <N or >N - Slot count comparison
- location:X,Y - Player within 3 tiles of coordinates
- idle - Player not moving

Examples: 'plane:2', 'has_item:Pot of flour', 'no_item:Grain', 'inventory_count:<=5'""",
    "inputSchema": {
        "type": "object",
        "properties": {
            "condition": {
                "type": "string",
                "description": "Condition to wait for (e.g., 'plane:2', 'has_item:Flour')"
            },
            "timeout_ms": {
                "type": "integer",
                "description": "Maximum time to wait in milliseconds (default: 10000)",
                "default": 10000
            },
            "poll_interval_ms": {
                "type": "integer",
                "description": "How often to check state in milliseconds (default: 500)",
                "default": 500
            },
            "account_id": ACCOUNT_ID_SCHEMA
        },
        "required": ["condition"]
    }
})
async def handle_await_state_change(arguments: dict) -> dict:
    """Wait for game state to match a condition."""
    import asyncio

    condition_str = arguments.get("condition", "")
    timeout_ms = arguments.get("timeout_ms", 10000)
    poll_interval_ms = arguments.get("poll_interval_ms", 500)
    account_id = arguments.get("account_id")

    state_file = config.get_state_file(account_id)

    # Parse the condition
    try:
        condition = _parse_condition(condition_str)
    except ValueError as e:
        return {
            "success": False,
            "error": str(e),
            "condition": condition_str
        }

    start_time = time.time()
    timeout_sec = timeout_ms / 1000.0
    poll_interval_sec = poll_interval_ms / 1000.0

    last_state = None
    checks = 0

    while (time.time() - start_time) < timeout_sec:
        checks += 1

        # Read current state
        try:
            with open(state_file) as f:
                state = json.load(f)
            last_state = state
        except (FileNotFoundError, json.JSONDecodeError):
            await asyncio.sleep(poll_interval_sec)
            continue

        # Check condition
        if _check_condition(state, condition):
            elapsed_ms = int((time.time() - start_time) * 1000)
            return {
                "success": True,
                "condition_met": True,
                "condition": condition_str,
                "elapsed_ms": elapsed_ms,
                "checks": checks,
                "final_state": _extract_relevant_state(state)
            }

        await asyncio.sleep(poll_interval_sec)

    # Timeout
    elapsed_ms = int((time.time() - start_time) * 1000)
    return {
        "success": False,
        "condition_met": False,
        "condition": condition_str,
        "elapsed_ms": elapsed_ms,
        "checks": checks,
        "error": f"Timeout after {elapsed_ms}ms",
        "final_state": _extract_relevant_state(last_state) if last_state else None
    }


def _extract_relevant_state(state: dict) -> dict:
    """Extract just the relevant parts of state for response."""
    if not state:
        return None

    player = state.get("player", {})
    location = player.get("location", {})
    inventory = player.get("inventory", {})

    # Count non-null items
    items = inventory.get("items", [])
    item_count = sum(1 for item in items if item is not None)
    item_names = [item.get("name") for item in items if item is not None]

    return {
        "plane": location.get("plane"),
        "x": location.get("x"),
        "y": location.get("y"),
        "inventory_count": item_count,
        "inventory_items": item_names[:10],  # First 10 for brevity
        "is_moving": player.get("isMoving", False)
    }


# ============================================================================
# AUTO-RECONNECT
# ============================================================================

def _is_disconnected(account_id: str = None) -> tuple:
    """
    Check if client is disconnected by examining state file freshness.

    Returns (is_disconnected: bool, reason: str, state_age_seconds: float)
    """
    state_file = config.get_state_file(account_id)

    if not os.path.exists(state_file):
        return (True, "State file does not exist", None)

    try:
        mtime = os.path.getmtime(state_file)
        age = time.time() - mtime

        # State should update every ~600ms, stale after 10 seconds indicates disconnect
        if age > 10:
            return (True, f"State file stale ({age:.1f}s old)", age)

        # Also check if player location is missing (another disconnect indicator)
        with open(state_file) as f:
            state = json.load(f)
            player = state.get("player", {})
            location = player.get("location", {})
            if not location.get("x") or not location.get("y"):
                return (True, "Player location missing from state", age)

        return (False, "Connected", age)

    except Exception as e:
        return (True, f"Error checking state: {e}", None)


# =============================================================================
# LOGIN SCREEN COORDINATES (DOCUMENTED 2026-01-04)
# =============================================================================
# These are used by auto_reconnect and must be kept accurate.
#
# 1. DISCONNECT DIALOG "Ok" BUTTON:
#    - Top-left: (640, 575)
#    - Bottom-right: (900, 633)
#    - Center: (770, 604)
#
# 2. FIRST LOGIN SCREEN "Play Now" BUTTON (account selection):
#    - Center: (670, 450)  # Approximate - yellow "Play Now" text
#
# 3. WELCOME TO GIELINOR "CLICK HERE TO PLAY" BUTTON:
#    - Top-left: (560, 596)
#    - Bottom-right: (990, 751)
#    - Center: (775, 674)
#    - NOTE: Using (670, 530) as click target - original center was hitting banner below
# =============================================================================

def _xdotool_click(x: int, y: int, display: str = ":2") -> bool:
    """Click at coordinates using xdotool. Works even when game is disconnected."""
    import subprocess
    try:
        # Get RuneLite window ID
        result = subprocess.run(
            ["xdotool", "search", "--name", "RuneLite"],
            capture_output=True, text=True,
            env={**os.environ, "DISPLAY": display}
        )
        window_ids = result.stdout.strip().split('\n')
        if not window_ids or not window_ids[0]:
            return False
        window_id = window_ids[0]

        # Click at coordinates within window
        subprocess.run(
            ["xdotool", "mousemove", "--window", window_id, str(x), str(y), "click", "1"],
            env={**os.environ, "DISPLAY": display},
            check=True
        )
        return True
    except Exception as e:
        return False


@registry.register({
    "name": "auto_reconnect",
    "description": """[Monitoring] Automatically handle disconnection by clicking OK and waiting for reconnect.

Detects disconnection via state file staleness, clicks the OK button on the
disconnect dialog, and waits for the game to reconnect.

Use this when you detect a disconnect or as a recovery step.""",
    "inputSchema": {
        "type": "object",
        "properties": {
            "account_id": ACCOUNT_ID_SCHEMA,
            "max_wait_seconds": {
                "type": "integer",
                "description": "Maximum seconds to wait for reconnection (default: 60)",
                "default": 60
            },
            "restart_on_timeout": {
                "type": "boolean",
                "description": "If true, restart RuneLite client if reconnection times out (default: true)",
                "default": True
            }
        }
    }
})
async def handle_auto_reconnect(arguments: dict) -> dict:
    """Automatically handle disconnection using xdotool clicks."""
    import asyncio

    account_id = arguments.get("account_id")
    max_wait = arguments.get("max_wait_seconds", 60)
    restart_on_timeout = arguments.get("restart_on_timeout", True)
    display = config.display  # Usually ":2"

    # Step 1: Check if actually disconnected
    is_disconnected, reason, state_age = _is_disconnected(account_id)

    if not is_disconnected:
        return {
            "success": True,
            "action": "none",
            "message": "Client is already connected",
            "state_age_seconds": state_age
        }

    clicks_made = []

    try:
        # Step 2: Click OK button on disconnect dialog
        # Uses xdotool which works even when plugin command processor is inactive
        ok_x, ok_y = 770, 604
        if _xdotool_click(ok_x, ok_y, display):
            clicks_made.append(f"Ok button ({ok_x}, {ok_y})")
        else:
            return {
                "success": False,
                "action": "failed",
                "error": "Failed to click Ok button via xdotool"
            }

        await asyncio.sleep(1.5)

        # Step 3: Click "Play Now" on first login screen
        play_now_x, play_now_y = 670, 450
        if _xdotool_click(play_now_x, play_now_y, display):
            clicks_made.append(f"Play Now ({play_now_x}, {play_now_y})")

        await asyncio.sleep(2.0)

        # Step 4: Click "CLICK HERE TO PLAY" on Welcome to Gielinor screen
        click_to_play_x, click_to_play_y = 670, 530
        if _xdotool_click(click_to_play_x, click_to_play_y, display):
            clicks_made.append(f"Click Here To Play ({click_to_play_x}, {click_to_play_y})")

        await asyncio.sleep(2.0)

    except Exception as e:
        return {
            "success": False,
            "action": "failed",
            "error": f"Error during reconnect sequence: {e}",
            "clicks_made": clicks_made
        }

    # Step 5: Wait for reconnection (state file to become fresh)
    start_time = time.time()

    while (time.time() - start_time) < max_wait:
        await asyncio.sleep(2)

        is_disconnected, reason, state_age = _is_disconnected(account_id)

        if not is_disconnected:
            elapsed = time.time() - start_time
            return {
                "success": True,
                "action": "reconnected",
                "message": f"Successfully reconnected after {elapsed:.1f}s",
                "elapsed_seconds": elapsed,
                "clicks_made": clicks_made
            }

    # Timeout waiting for reconnect - optionally restart client
    if restart_on_timeout:
        try:
            # Stop existing instance
            runelite_manager.stop(account_id)
            await asyncio.sleep(2)

            # Start fresh instance
            result = runelite_manager.start(account_id)
            if result.get("success"):
                # Wait for new instance to connect
                restart_start = time.time()
                while (time.time() - restart_start) < 90:  # 90 second startup timeout
                    await asyncio.sleep(3)
                    is_disconnected, reason, state_age = _is_disconnected(account_id)
                    if not is_disconnected:
                        total_elapsed = time.time() - start_time
                        return {
                            "success": True,
                            "action": "restarted",
                            "message": f"Reconnect failed, but restart succeeded after {total_elapsed:.1f}s",
                            "elapsed_seconds": total_elapsed,
                            "clicks_made": clicks_made
                        }

                return {
                    "success": False,
                    "action": "restart_timeout",
                    "error": "Restart initiated but client failed to connect within 90s",
                    "clicks_made": clicks_made
                }
            else:
                return {
                    "success": False,
                    "action": "restart_failed",
                    "error": f"Failed to restart client: {result.get('error', 'unknown')}",
                    "clicks_made": clicks_made
                }
        except Exception as e:
            return {
                "success": False,
                "action": "restart_error",
                "error": f"Error restarting client: {e}",
                "clicks_made": clicks_made
            }

    return {
        "success": False,
        "action": "timeout",
        "error": f"Timed out waiting for reconnection after {max_wait}s",
        "disconnect_reason": reason,
        "clicks_made": clicks_made
    }
