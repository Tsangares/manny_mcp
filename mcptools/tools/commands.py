"""
Command execution tools for sending commands and input to the plugin.
"""
import os
import json
import time
import asyncio
from ..registry import registry


# Dependencies
send_command_with_response = None
config = None

# Import state checking functions from monitoring module
_parse_condition = None
_check_condition = None
_extract_relevant_state = None


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

    try:
        with open(command_file, "w") as f:
            f.write(command + "\n")
        result = {
            "dispatched": True,
            "command": command,
            "note": "Command queued. Use get_logs() or get_command_response() to verify execution."
        }
        if account_id:
            result["account_id"] = account_id
        return result
    except Exception as e:
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

    try:
        if input_type == "click":
            x = arguments.get("x")
            y = arguments.get("y")
            button = arguments.get("button", 1)
            if x is None or y is None:
                return {"sent": False, "error": "click requires x and y coordinates"}

            button_name = {1: "left", 2: "middle", 3: "right"}.get(button, "left")
            command = f"MOUSE_MOVE {x} {y}\nMOUSE_CLICK {button_name}"
            with open(command_file, "w") as f:
                f.write(command + "\n")
            return {"sent": True, "input_type": "click", "x": x, "y": y, "button": button_name}

        elif input_type == "key":
            key = arguments.get("key")
            if not key:
                return {"sent": False, "error": "key type requires 'key' parameter"}

            command = f"KEY_PRESS {key}"
            with open(command_file, "w") as f:
                f.write(command + "\n")
            return {"sent": True, "input_type": "key", "key": key,
                    "note": "KEY_PRESS command may need to be added to plugin"}

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

    command_file = config.get_command_file(account_id)
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

    # Send the command
    try:
        with open(command_file, "w") as f:
            f.write(command + "\n")
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to send command: {e}",
            "command": command
        }

    # Wait for condition
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
                "command": command,
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
        "command": command,
        "condition": condition_str,
        "elapsed_ms": elapsed_ms,
        "checks": checks,
        "error": f"Timeout after {elapsed_ms}ms waiting for condition",
        "final_state": _extract_relevant_state(last_state) if last_state else None
    }


@registry.register({
    "name": "deposit_item",
    "description": """[Commands] Deposit a specific item from inventory into the bank or deposit box.

Requires the bank or deposit box interface to be open first.
Handles item name conversion automatically (spaces to underscores).

Examples:
- deposit_item(item_name="Raw lobster")
- deposit_item(item_name="Bronze bar", wait_for_completion=True)""",
    "inputSchema": {
        "type": "object",
        "properties": {
            "item_name": {
                "type": "string",
                "description": "Name of the item to deposit (e.g., 'Raw lobster', 'Bronze bar')"
            },
            "wait_for_completion": {
                "type": "boolean",
                "description": "If true, wait for the item to be removed from inventory (default: true)",
                "default": True
            },
            "timeout_ms": {
                "type": "integer",
                "description": "Maximum time to wait in milliseconds if wait_for_completion is true (default: 5000)",
                "default": 5000
            },
            "account_id": {
                "type": "string",
                "description": "Account ID for multi-client (optional)"
            }
        },
        "required": ["item_name"]
    }
})
async def handle_deposit_item(arguments: dict) -> dict:
    """Deposit an item from inventory to bank/deposit box."""
    item_name = arguments.get("item_name", "")
    wait_for_completion = arguments.get("wait_for_completion", True)
    timeout_ms = arguments.get("timeout_ms", 5000)
    account_id = arguments.get("account_id")

    command_file = config.get_command_file(account_id)
    state_file = config.get_state_file(account_id)

    # Convert spaces to underscores for command format
    item_name_cmd = item_name.replace(" ", "_")
    command = f"BANK_DEPOSIT_ITEM {item_name_cmd}"

    # Send the command
    try:
        with open(command_file, "w") as f:
            f.write(command + "\n")
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to send command: {e}",
            "item_name": item_name
        }

    if not wait_for_completion:
        return {
            "success": True,
            "command_sent": True,
            "item_name": item_name,
            "waited": False
        }

    # Wait for item to be removed from inventory
    condition_str = f"no_item:{item_name}"
    try:
        condition = _parse_condition(condition_str)
    except ValueError as e:
        return {
            "success": False,
            "error": f"Invalid condition: {e}",
            "item_name": item_name
        }

    start_time = time.time()
    timeout_sec = timeout_ms / 1000.0
    poll_interval_sec = 0.3  # 300ms polling

    last_state = None
    checks = 0

    while (time.time() - start_time) < timeout_sec:
        checks += 1

        try:
            with open(state_file) as f:
                state = json.load(f)
            last_state = state
        except (FileNotFoundError, json.JSONDecodeError):
            await asyncio.sleep(poll_interval_sec)
            continue

        if _check_condition(state, condition):
            elapsed_ms = int((time.time() - start_time) * 1000)
            return {
                "success": True,
                "deposited": True,
                "item_name": item_name,
                "elapsed_ms": elapsed_ms,
                "checks": checks
            }

        await asyncio.sleep(poll_interval_sec)

    # Timeout - item might still be in inventory
    elapsed_ms = int((time.time() - start_time) * 1000)
    return {
        "success": False,
        "deposited": False,
        "item_name": item_name,
        "elapsed_ms": elapsed_ms,
        "checks": checks,
        "error": f"Timeout after {elapsed_ms}ms - item may still be in inventory"
    }


@registry.register({
    "name": "teleport_home",
    "description": """[Commands] Cast Home Teleport to return to Lumbridge.

Opens the magic tab, clicks Home Teleport spell, and waits for teleport.
Home Teleport has a 30-minute cooldown and takes ~10 seconds to cast.

Note: The spell will fail if:
- On cooldown (30 min between casts)
- In combat
- Player moves during casting

Returns success/failure and final player location.""",
    "inputSchema": {
        "type": "object",
        "properties": {
            "wait_for_arrival": {
                "type": "boolean",
                "description": "If true, wait for player to arrive in Lumbridge (default: true)",
                "default": True
            },
            "timeout_ms": {
                "type": "integer",
                "description": "Maximum time to wait for teleport in milliseconds (default: 15000)",
                "default": 15000
            },
            "account_id": {
                "type": "string",
                "description": "Account ID for multi-client (optional)"
            }
        },
        "required": []
    }
})
async def handle_teleport_home(arguments: dict) -> dict:
    """Cast Home Teleport to Lumbridge."""
    wait_for_arrival = arguments.get("wait_for_arrival", True)
    timeout_ms = arguments.get("timeout_ms", 15000)
    account_id = arguments.get("account_id")

    command_file = config.get_command_file(account_id)
    state_file = config.get_state_file(account_id)

    # Send the command
    try:
        with open(command_file, "w") as f:
            f.write("TELEPORT_HOME\n")
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to send command: {e}"
        }

    if not wait_for_arrival:
        return {
            "success": True,
            "command_sent": True,
            "waited": False,
            "note": "TELEPORT_HOME sent. Teleport takes ~10 seconds."
        }

    # Wait for arrival near Lumbridge spawn (3222, 3218)
    # Using location:3222,3218 with default 3-tile tolerance
    condition_str = "location:3222,3218"
    try:
        condition = _parse_condition(condition_str)
    except ValueError as e:
        return {
            "success": False,
            "error": f"Invalid condition: {e}"
        }

    start_time = time.time()
    timeout_sec = timeout_ms / 1000.0
    poll_interval_sec = 0.5

    last_state = None
    checks = 0

    while (time.time() - start_time) < timeout_sec:
        checks += 1

        try:
            with open(state_file) as f:
                state = json.load(f)
            last_state = state
        except (FileNotFoundError, json.JSONDecodeError):
            await asyncio.sleep(poll_interval_sec)
            continue

        if _check_condition(state, condition):
            elapsed_ms = int((time.time() - start_time) * 1000)
            location = state.get("player", {}).get("location", {})
            return {
                "success": True,
                "teleported": True,
                "elapsed_ms": elapsed_ms,
                "checks": checks,
                "location": location
            }

        await asyncio.sleep(poll_interval_sec)

    # Timeout
    elapsed_ms = int((time.time() - start_time) * 1000)
    location = None
    if last_state:
        location = last_state.get("player", {}).get("location", {})

    return {
        "success": False,
        "teleported": False,
        "elapsed_ms": elapsed_ms,
        "checks": checks,
        "error": f"Timeout after {elapsed_ms}ms - teleport may have failed (cooldown, interrupted, or combat)",
        "location": location
    }


@registry.register({
    "name": "stabilize_camera",
    "description": """[Commands] Reset camera to a stable medium zoom and pitch.

Counteracts NPC zoom-in behavior by resetting to a comfortable viewing distance.
- Zooms out to maximum (normalizes baseline)
- Zooms back in to medium distance (8 scrolls)
- Sets pitch to 300 (moderate angle, good visibility)

Use after NPC interactions that may have zoomed in too close.""",
    "inputSchema": {
        "type": "object",
        "properties": {
            "account_id": {
                "type": "string",
                "description": "Account ID for multi-client (optional)"
            }
        },
        "required": []
    }
})
async def handle_stabilize_camera(arguments: dict) -> dict:
    """Reset camera to stable medium zoom and pitch."""
    account_id = arguments.get("account_id")
    command_file = config.get_command_file(account_id)

    try:
        with open(command_file, "w") as f:
            f.write("CAMERA_STABILIZE\n")
        result = {"success": True, "command": "CAMERA_STABILIZE"}
        if account_id:
            result["account_id"] = account_id
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}
