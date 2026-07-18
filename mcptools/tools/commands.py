"""
Command execution tools for sending commands and input to the plugin.
"""
import asyncio
import json
import os
import time

from ..registry import registry

# Dependencies
send_command_with_response = None
config = None

# Import state checking functions from monitoring module
_parse_condition = None
_check_condition = None
_extract_relevant_state = None

# Session recorder (lazy import to avoid circular deps)
_session_recorder = None
_command_log = None

# Stuck detector
from ..stuck_detector import stuck_detector as _stuck_detector


def _get_recorder():
    """Lazy import session recorder."""
    global _session_recorder
    if _session_recorder is None:
        from .session import recorder
        _session_recorder = recorder
    return _session_recorder


def _get_command_log():
    """Lazy import always-on command log."""
    global _command_log
    if _command_log is None:
        from .session import command_log
        _command_log = command_log
    return _command_log


def set_dependencies(send_command_func, server_config):
    """Inject dependencies (called from server.py startup)"""
    global send_command_with_response, config
    global _parse_condition, _check_condition, _extract_relevant_state
    send_command_with_response = send_command_func
    config = server_config

    # Late import to avoid circular dependency
    from . import monitoring
    _parse_condition = monitoring._parse_condition
    _check_condition = monitoring._check_condition
    _extract_relevant_state = monitoring._extract_relevant_state


@registry.register({
    "name": "send_command",
    "description": """[Commands] Send a command to the manny plugin via /tmp/manny_command.txt

IMPORTANT: This is async - returns immediately after queuing. The plugin executes on next game tick.
To verify execution: use get_logs(grep="COMMAND_NAME") or get_command_response().
For commands with expected state changes, prefer send_and_await() instead.""",
    "inputSchema": {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "The command to send (e.g., 'GOTO 3200 3200 0', 'BANK_OPEN')"
            },
            "account_id": {
                "type": "string",
                "description": "Account ID for multi-client (optional, defaults to 'default')"
            }
        },
        "required": ["command"]
    }
})
async def handle_send_command(arguments: dict) -> dict:
    """Send command to plugin."""
    command = arguments.get("command", "")
    account_id = arguments.get("account_id")
    command_file = config.get_command_file(account_id)
    state_file = config.get_state_file(account_id)

    # Stuck detection: read current state and check for repeated commands
    current_state = None
    try:
        if os.path.exists(state_file):
            with open(state_file) as f:
                raw_state = json.load(f)
            # Extract the nested state dict if present
            current_state = raw_state.get("state", raw_state) if isinstance(raw_state, dict) else raw_state
    except (json.JSONDecodeError, IOError):
        pass

    acct = account_id or "default"
    stuck_status, stuck_msg = _stuck_detector.check_command(command, acct, current_state)

    if stuck_status == "block":
        return {
            "dispatched": False,
            "command": command,
            "error": stuck_msg,
            "stuck_detection": _stuck_detector.get_status(acct)
        }

    # Always log to daily command history (lightweight, always-on)
    _get_command_log().log_command(command)

    # Also record to explicit session if active (with state tracking)
    recorder = _get_recorder()
    cmd_id = recorder.record_command(command) if recorder.is_active() else None

    try:
        with open(command_file, "w") as f:
            f.write(command + "\n")

        # Verify delivery: the plugin polls the command file every ~500ms and
        # DELETES it upon receipt. Poll for that deletion for a short window
        # so we don't silently report success when the client is down, the
        # account namespace is wrong, or the file was lost to the single-slot
        # overwrite.
        DELIVERY_TIMEOUT_SEC = 1.5
        DELIVERY_POLL_INTERVAL_SEC = 0.5
        delivered = False
        waited = 0.0
        while waited < DELIVERY_TIMEOUT_SEC:
            await asyncio.sleep(DELIVERY_POLL_INTERVAL_SEC)
            waited += DELIVERY_POLL_INTERVAL_SEC
            if not os.path.exists(command_file):
                delivered = True
                break

        if not delivered:
            error_msg = ("command not consumed within 1.5s — client may be down, "
                         "logged-out-processor-idle, or wrong account_id")
            if recorder.is_active():
                recorder.record_error(command, error_msg)
            result = {
                "dispatched": False,
                "delivered": False,
                "command": command,
                "error": error_msg,
                "command_file": command_file
            }
            if account_id:
                result["account_id"] = account_id
            return result

        result = {
            "dispatched": True,
            "delivered": True,
            "command": command,
            "note": "Command queued. Use get_logs() or get_command_response() to verify execution.",
            "command_file": command_file
        }
        if account_id:
            result["account_id"] = account_id
        # Include stuck warning if approaching threshold
        if stuck_status == "warn":
            result["warning"] = stuck_msg
            result["stuck_detection"] = _stuck_detector.get_status(acct)
        return result
    except Exception as e:
        # Record error if session active
        if recorder.is_active():
            recorder.record_error(command, str(e))
        return {"dispatched": False, "error": str(e)}


@registry.register({
    "name": "send_input",
    "description": """[Commands] Send input directly to RuneLite canvas via Java AWT events.

Works regardless of Wayland/X11 setup because it uses the plugin's internal Mouse/Keyboard classes.

Input types:
- click: Click at x,y coordinates (button 1=left, 2=middle, 3=right)
- key: Press a key (e.g., "Return", "Escape", "Space", "a", "1")
- move: Move mouse to x,y without clicking

Use this to:
- Dismiss login/disconnect dialogs
- Click UI elements when game commands don't work
- Send keyboard input to the game""",
    "inputSchema": {
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
            },
            "account_id": {
                "type": "string",
                "description": "Account ID for multi-client (optional, defaults to 'default')"
            }
        },
        "required": ["input_type"]
    }
})
async def handle_send_input(arguments: dict) -> dict:
    """Send input to RuneLite canvas."""
    input_type = arguments.get("input_type")
    account_id = arguments.get("account_id")
    command_file = config.get_command_file(account_id)
    state_file = config.get_state_file(account_id)

    # Stuck detection for key presses and clicks
    acct = account_id or "default"
    current_state = None
    try:
        if os.path.exists(state_file):
            with open(state_file) as f:
                raw_state = json.load(f)
            current_state = raw_state.get("state", raw_state) if isinstance(raw_state, dict) else raw_state
    except (json.JSONDecodeError, IOError):
        pass

    try:
        if input_type == "click":
            x = arguments.get("x")
            y = arguments.get("y")
            button = arguments.get("button", 1)
            if x is None or y is None:
                return {"sent": False, "error": "click requires x and y coordinates"}

            button_name = {1: "left", 2: "middle", 3: "right"}.get(button, "left")
            command = f"MOUSE_MOVE {x} {y}\nMOUSE_CLICK {button_name}"

            # Check stuck detection
            stuck_status, stuck_msg = _stuck_detector.check_command(
                f"click:{x},{y}", acct, current_state)
            if stuck_status == "block":
                return {"sent": False, "error": stuck_msg,
                        "stuck_detection": _stuck_detector.get_status(acct)}

            with open(command_file, "w") as f:
                f.write(command + "\n")
            result = {"sent": True, "input_type": "click", "x": x, "y": y, "button": button_name}
            if stuck_status == "warn":
                result["warning"] = stuck_msg
            return result

        elif input_type == "key":
            key = arguments.get("key")
            if not key:
                return {"sent": False, "error": "key type requires 'key' parameter"}

            command = f"KEY_PRESS {key}"

            # Check stuck detection
            stuck_status, stuck_msg = _stuck_detector.check_command(
                f"key:{key}", acct, current_state)
            if stuck_status == "block":
                return {"sent": False, "error": stuck_msg,
                        "stuck_detection": _stuck_detector.get_status(acct)}

            with open(command_file, "w") as f:
                f.write(command + "\n")
            result = {"sent": True, "input_type": "key", "key": key}
            if stuck_status == "warn":
                result["warning"] = stuck_msg
            return result

        elif input_type == "move":
            x = arguments.get("x")
            y = arguments.get("y")
            if x is None or y is None:
                return {"sent": False, "error": "move requires x and y coordinates"}

            command = f"MOUSE_MOVE {x} {y}"
            with open(command_file, "w") as f:
                f.write(command + "\n")
            return {"sent": True, "input_type": "move", "x": x, "y": y}

        else:
            return {"sent": False, "error": f"Unknown input_type: {input_type}"}

    except Exception as e:
        return {"sent": False, "error": str(e)}


@registry.register({
    "name": "send_and_await",
    "description": """[Commands] Send a command and wait for a state condition to be met.

Combines send_command + await_state_change into a single call for efficiency.
Sends the command, then polls game state until the condition is met or timeout.

Examples:
- send_and_await(command="INTERACT_OBJECT Ladder Climb-up", await_condition="plane:1")
- send_and_await(command="USE_ITEM_ON_OBJECT Grain Hopper", await_condition="no_item:Grain")
- send_and_await(command="BANK_WITHDRAW 1 Pot", await_condition="has_item:Pot")

Supported conditions (same as await_state_change):
- plane:N - Player on plane N (0, 1, or 2)
- has_item:ItemName - Inventory contains item
- no_item:ItemName - Inventory doesn't have item
- inventory_count:<=N or >=N - Slot count comparison
- location:X,Y - Player within 3 tiles of coordinates
- idle - Player not moving""",
    "inputSchema": {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "Command to send to the plugin"
            },
            "await_condition": {
                "type": "string",
                "description": "Condition to wait for after command (e.g., 'plane:2', 'has_item:Flour')"
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
            "account_id": {
                "type": "string",
                "description": "Account ID for multi-client (optional)"
            }
        },
        "required": ["command", "await_condition"]
    }
})
async def handle_send_and_await(arguments: dict) -> dict:
    """Send command and wait for state condition."""
    command = arguments.get("command", "")
    condition_str = arguments.get("await_condition", "")
    timeout_ms = arguments.get("timeout_ms", 10000)
    poll_interval_ms = arguments.get("poll_interval_ms", 500)
    account_id = arguments.get("account_id")

    state_file = config.get_state_file(account_id)

    # Parse condition first to fail fast on invalid conditions
    try:
        condition = _parse_condition(condition_str)
    except ValueError as e:
        return {
            "success": False,
            "error": f"Invalid condition: {e}",
            "command": command,
            "condition": condition_str
        }

    # Pre-flight check: Detect stale state file (plugin may be frozen)
    # If state file is >30s stale, warn caller before wasting time on a frozen plugin
    STALE_THRESHOLD = 30  # seconds
    try:
        if os.path.exists(state_file):
            state_age = time.time() - os.path.getmtime(state_file)
            if state_age > STALE_THRESHOLD:
                return {
                    "success": False,
                    "error": f"Plugin appears frozen - state file is {state_age:.0f}s stale. Use restart_if_frozen() or auto_reconnect() first.",
                    "command": command,
                    "condition": condition_str,
                    "state_age_seconds": round(state_age, 1),
                    "diagnosis": "PLUGIN_FROZEN"
                }
        else:
            return {
                "success": False,
                "error": "State file does not exist - is RuneLite running with manny plugin?",
                "command": command,
                "condition": condition_str,
                "diagnosis": "NO_STATE_FILE"
            }
    except Exception:
        # Don't block on pre-flight check failures, just proceed
        pass

    # Send the command through the rid-correlated transport -- the SAME path the
    # rest of the command layer uses (see handle_equip_item / handle_click_widget,
    # which both call send_command_with_response). Under the hood this writes
    # "<command> --rid=<id>" atomically and correlates the plugin's response by
    # top-level request_id (payload under `result`), polling
    # /tmp/manny_new_response.json for the matching id. Previously this handler
    # wrote the raw command straight to the command file with no --rid, bypassing
    # correlation entirely -- responses could be mismatched or dropped.
    #
    # The dispatch also counts toward the total timeout budget, so a fast command
    # response simply leaves the remainder of the budget for state polling.
    start_time = time.time()
    try:
        command_response = await send_command_with_response(command, timeout_ms, account_id)
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to send command: {e}",
            "command": command,
            "condition": condition_str,
        }

    # If the transport reports the command was never delivered to the plugin,
    # fail fast rather than polling for a condition that can never be met.
    if isinstance(command_response, dict) and command_response.get("delivered") is False:
        return {
            "success": False,
            "error": command_response.get("error", "Command was not delivered to plugin"),
            "command": command,
            "condition": condition_str,
            "command_response": command_response,
        }

    # Wait for condition. Use a do-while shape so at least one state check always
    # runs, even if the dispatch above already consumed the whole timeout budget.
    timeout_sec = timeout_ms / 1000.0
    poll_interval_sec = poll_interval_ms / 1000.0

    last_state = None
    checks = 0

    while True:
        checks += 1

        # Read current state
        try:
            with open(state_file) as f:
                state = json.load(f)
            last_state = state
        except (FileNotFoundError, json.JSONDecodeError):
            state = None

        # Check condition
        if state is not None and _check_condition(state, condition):
            elapsed_ms = int((time.time() - start_time) * 1000)
            return {
                "success": True,
                "condition_met": True,
                "command": command,
                "condition": condition_str,
                "elapsed_ms": elapsed_ms,
                "checks": checks,
                "command_response": command_response,
                "final_state": _extract_relevant_state(state)
            }

        if (time.time() - start_time) >= timeout_sec:
            break
        await asyncio.sleep(poll_interval_sec)

    # Timeout
    elapsed_ms = int((time.time() - start_time) * 1000)
    return {
        "success": False,
        "condition_met": False,
        "command": command,
        "condition": condition_str,
        "elapsed_ms": elapsed_ms,
        "checks": checks,
        "command_response": command_response,
        "error": f"Timeout after {elapsed_ms}ms waiting for condition",
        "final_state": _extract_relevant_state(last_state) if last_state else None
    }


# NOTE: equip_item is no longer a registered MCP tool (use the canonical
# click_widget(text=..., action="Wear"/"Wield") path). The handler is kept
# because routine YAML steps (mcp_tool: equip_item) still call it directly.
async def handle_equip_item(arguments: dict) -> dict:
    """Equip an item from inventory by name."""
    item_name = arguments.get("item_name", "")
    action_override = arguments.get("action")
    timeout_ms = arguments.get("timeout_ms", 3000)
    account_id = arguments.get("account_id")

    if not item_name:
        return {"success": False, "error": "item_name is required"}

    command_file = config.get_command_file(account_id)

    # Step 1: Find the item widget in inventory
    # Use SCAN_WIDGETS with item name filter
    scan_command = f"SCAN_WIDGETS {item_name}"
    response = await send_command_with_response(scan_command, timeout_ms, account_id)

    if response.get("status") != "success":
        return {
            "success": False,
            "error": f"Failed to scan widgets: {response.get('error', 'Unknown error')}",
            "item_name": item_name
        }

    widgets = response.get("result", {}).get("widgets", [])

    # Find the inventory item widget (look for item with matching name and equip actions)
    inventory_widget = None
    equip_action = action_override

    for widget in widgets:
        widget_item_name = widget.get("itemName", "")
        actions = widget.get("actions", [])

        # Check if this is our item (case-insensitive match)
        if widget_item_name.lower() == item_name.lower():
            # Check if it has equip actions
            available_actions = [a for a in actions if a and a in ("Wear", "Wield", "Equip")]
            if available_actions:
                inventory_widget = widget
                # Auto-detect action if not specified
                if not equip_action:
                    equip_action = available_actions[0]  # Use first available equip action
                break

    if not inventory_widget:
        return {
            "success": False,
            "error": f"Item '{item_name}' not found in inventory or has no equip action",
            "item_name": item_name,
            "widgets_scanned": len(widgets)
        }

    widget_id = inventory_widget.get("id")
    if not widget_id:
        return {
            "success": False,
            "error": f"Item '{item_name}' found but has no widget ID",
            "item_name": item_name
        }

    # Step 2: Click at the item's bounds using CLICK_AT command (Java-side atomic click)
    # (CLICK_WIDGET with action re-searches and finds wrong item)
    bounds = inventory_widget.get("bounds", {})
    if not bounds or bounds.get("x", -1) < 0:
        return {
            "success": False,
            "error": f"Item '{item_name}' found but has invalid bounds",
            "item_name": item_name,
            "bounds": bounds
        }

    click_x = bounds["x"] + bounds["width"] // 2
    click_y = bounds["y"] + bounds["height"] // 2

    # Use CLICK_AT command - atomic move+click handled by the Java plugin
    # This avoids xdotool display connection issues with gamescope
    click_command = f"CLICK_AT {click_x} {click_y}"
    click_response = await send_command_with_response(click_command, timeout_ms, account_id)

    if click_response.get("status") != "success":
        return {
            "success": False,
            "error": f"Click failed: {click_response.get('error', 'Unknown error')}",
            "item_name": item_name
        }

    # Give the game a moment to process
    await asyncio.sleep(0.3)

    return {
        "success": True,
        "item_name": item_name,
        "widget_id": widget_id,
        "action": equip_action,
        "clicked_at": {"x": click_x, "y": click_y}
    }


@registry.register({
    "name": "execute_combat_routine",
    "description": """[Combat] Execute a combat routine from a YAML config file.

Reads combat configuration from YAML and runs the combat loop with specified settings.
The config file specifies NPC, kill count, loot items, eating thresholds, etc.

Example YAML:
```yaml
name: "Hill Giants"
npc: "Hill Giant"
kills: 500
loot:
  items: ["Law rune", "Fire rune"]
  bones: ["Big bones"]
eating:
  threshold_percent: 50
  escape_food_count: 3
```

The routine writes config to /tmp/manny_combat_config.json and sends KILL_LOOP_CONFIG command.""",
    "inputSchema": {
        "type": "object",
        "properties": {
            "routine_path": {
                "type": "string",
                "description": "Path to the combat routine YAML file"
            },
            "kills": {
                "type": "integer",
                "description": "Override kill count from YAML (optional)"
            },
            "account_id": {
                "type": "string",
                "description": "Account ID for multi-client (optional)"
            }
        },
        "required": ["routine_path"]
    }
})
async def handle_execute_combat_routine(arguments: dict) -> dict:
    """Execute a combat routine from YAML config."""
    from pathlib import Path

    import yaml

    routine_path = arguments.get("routine_path", "")
    kills_override = arguments.get("kills")
    account_id = arguments.get("account_id")

    # Resolve path
    path = Path(routine_path)
    if not path.is_absolute():
        # Try relative to manny-mcp directory
        mcp_root = Path(__file__).parent.parent.parent
        path = mcp_root / routine_path

    if not path.exists():
        return {
            "success": False,
            "error": f"Routine file not found: {path}"
        }

    # Load YAML config
    try:
        with open(path) as f:
            routine = yaml.safe_load(f)
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to parse YAML: {e}"
        }

    # Extract config
    npc = routine.get("npc", "")
    kills = kills_override or routine.get("kills", 10000)
    loot_config = routine.get("loot", {})
    eating_config = routine.get("eating", {})

    # Build loot list
    loot_items = loot_config.get("items", [])
    bones = loot_config.get("bones", [])

    # Write config to JSON for Java to read
    combat_config = {
        "npc": npc,
        "kills": kills,
        "loot_items": loot_items,
        "bones": bones,
        "ignore_items": loot_config.get("ignore", []),
        "eat_threshold_percent": eating_config.get("threshold_percent", 50),
        "escape_food_count": eating_config.get("escape_food_count", 3)
    }

    config_file = "/tmp/manny_combat_config.json"
    try:
        with open(config_file, "w") as f:
            json.dump(combat_config, f, indent=2)
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to write config: {e}"
        }

    # Send command to Java
    command_file = config.get_command_file(account_id)
    command = f"KILL_LOOP_CONFIG {config_file}"

    try:
        with open(command_file, "w") as f:
            f.write(command + "\n")
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to send command: {e}"
        }

    # Log the command
    _get_command_log().log_command(command)

    return {
        "success": True,
        "dispatched": True,
        "routine": routine.get("name", path.stem),
        "npc": npc,
        "kills": kills,
        "loot_items": loot_items,
        "bones": bones,
        "config_file": config_file,
        "note": "Combat routine started. Use get_logs() to monitor progress."
    }


@registry.register({
    "name": "kill_command",
    "description": """[Commands] EMERGENCY STOP - Immediately kill any running command or routine.

Sends the KILL command which:
1. Sets the interrupt flag to stop all loops (MINE_ORE, FISH, CHOP_TREE, etc.)
2. Cancels any running background command task
3. Stops scenario/routine playback
4. Cancels navigation/pathfinding
5. Resets state managers

Use this when:
- A command is stuck in a loop
- You need to immediately stop all automation
- send_and_await is timing out but the command keeps running

This is a nuclear option - it stops EVERYTHING.""",
    "inputSchema": {
        "type": "object",
        "properties": {
            "account_id": {
                "type": "string",
                "description": "Account ID for multi-client (optional, defaults to 'default')"
            }
        },
        "required": []
    }
})
async def handle_kill_command(arguments: dict) -> dict:
    """Send KILL command to immediately stop all running commands/routines."""
    account_id = arguments.get("account_id")
    command_file = config.get_command_file(account_id)

    command = "KILL"

    # Log the command
    _get_command_log().log_command(command)

    try:
        with open(command_file, "w") as f:
            f.write(command + "\n")
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to send KILL command: {e}"
        }

    # Wait a moment for the kill to take effect
    await asyncio.sleep(0.5)

    return {
        "success": True,
        "command": "KILL",
        "message": "Kill signal sent. All running commands and routines should stop within ~500ms.",
        "account_id": account_id or "default"
    }
