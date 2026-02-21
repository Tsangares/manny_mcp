"""
Routine building tools for widget/dialogue interaction.
Used for building multi-step game automations.
"""
import os
import json
import time
import asyncio
import uuid
import re
from ..registry import registry
from ..utils import maybe_truncate_response


# Dependencies (send_command_with_response function and config)
send_command_with_response = None
config = None
runelite_manager = None

# Late-imported handlers
_handle_send_and_await = None
_handle_await_state_change = None
_handle_equip_item = None


def set_dependencies(send_command_func, server_config, manager=None):
    """Inject dependencies (called from server.py startup)"""
    global send_command_with_response, config, runelite_manager
    global _handle_send_and_await, _handle_await_state_change, _handle_equip_item
    send_command_with_response = send_command_func
    config = server_config
    runelite_manager = manager

    # Late import handlers from other modules to avoid circular deps
    from . import commands, monitoring
    _handle_send_and_await = commands.handle_send_and_await
    _handle_await_state_change = monitoring.handle_await_state_change
    _handle_equip_item = commands.handle_equip_item


async def execute_simple_command(command: str, timeout_ms: int = 10000, account_id: str = None) -> dict:
    """
    Execute a command and poll for response confirmation.

    Unlike send_and_await, this doesn't check game state conditions - it just
    verifies the plugin processed the command by watching for a new response.

    REQUEST ID CORRELATION: Appends --rid=xxx to command for unique request/response matching.
    This prevents race conditions when multiple commands of the same type are sent rapidly.

    Args:
        command: The command to send
        timeout_ms: Maximum time to wait for response
        account_id: Optional account ID for multi-client support

    Returns:
        dict with success, response, elapsed_ms, error
    """
    command_file = config.get_command_file(account_id)
    response_file = config.get_response_file(account_id)

    # Generate unique request ID for correlation
    request_id = uuid.uuid4().hex[:8]

    # Get current response timestamp before sending
    old_ts = 0
    try:
        with open(response_file) as f:
            old_response = json.load(f)
            old_ts = old_response.get("timestamp", 0)
    except (FileNotFoundError, json.JSONDecodeError):
        pass

    # Send command with request ID appended
    command_with_rid = f"{command} --rid={request_id}"
    try:
        with open(command_file, "w") as f:
            f.write(command_with_rid + "\n")
    except Exception as e:
        return {"success": False, "error": f"Failed to write command: {e}"}

    # Poll for NEW response (different timestamp)
    start_time = time.time()
    timeout_sec = timeout_ms / 1000.0
    poll_interval = 0.3  # 300ms between checks

    while (time.time() - start_time) < timeout_sec:
        try:
            with open(response_file) as f:
                response = json.load(f)

            new_ts = response.get("timestamp", 0)
            if new_ts > old_ts:
                # PRIMARY: Match by request_id (bulletproof correlation)
                if response.get("request_id") == request_id:
                    elapsed_ms = int((time.time() - start_time) * 1000)
                    return {
                        "success": response.get("status") == "success",
                        "response": response,
                        "elapsed_ms": elapsed_ms,
                        "error": response.get("error") if response.get("status") != "success" else None
                    }
                # FALLBACK: For backwards compat with old Java plugin, match by command name
                # (only if response has no request_id)
                if response.get("request_id") is None:
                    resp_cmd = response.get("command", "").upper()
                    our_cmd = command.split()[0].upper()
                    if resp_cmd == our_cmd:
                        elapsed_ms = int((time.time() - start_time) * 1000)
                        return {
                            "success": response.get("status") == "success",
                            "response": response,
                            "elapsed_ms": elapsed_ms,
                            "error": response.get("error") if response.get("status") != "success" else None
                        }
        except (FileNotFoundError, json.JSONDecodeError):
            pass

        await asyncio.sleep(poll_interval)

    # Timeout
    elapsed_ms = int((time.time() - start_time) * 1000)
    return {
        "success": False,
        "error": f"Timeout after {elapsed_ms}ms waiting for response",
        "elapsed_ms": elapsed_ms
    }


@registry.register({
    "name": "scan_widgets",
    "description": """[Routine Building] Scan all visible widgets in the game UI. Returns widget IDs, text content, and bounds.

Use this to discover clickable elements, dialogue options, interface buttons, etc.
Filter by text to find specific widgets.

Supports filtering by:
- Widget text content
- Widget name
- Item name (for inventory/bank/deposit box item widgets)

For item widgets (inventory, bank, deposit box), returns itemId, itemQuantity, and itemName.

SPECIFIC GROUP: Use group=593 to scan only a specific widget group (e.g., 593 for Combat Interface).
This is useful when you know which interface you're looking for.

Also scans widget roots and their children to catch active interfaces not in the default list.""",
    "inputSchema": {
        "type": "object",
        "properties": {
            "filter_text": {
                "type": "string",
                "description": "Optional text to filter widgets by - matches text, name, and item names (case-insensitive)"
            },
            "group": {
                "type": "integer",
                "description": "Scan only a specific widget group (e.g., 593 for Combat Interface, 149 for Inventory)"
            },
            "timeout_ms": {
                "type": "integer",
                "description": "Timeout in milliseconds (default: 3000)",
                "default": 3000
            },
            "account_id": {
                "type": "string",
                "description": "Account ID for multi-client (optional, defaults to 'default')"
            }
        }
    }
})
async def handle_scan_widgets(arguments: dict) -> dict:
    """Scan all visible widgets."""
    timeout_ms = arguments.get("timeout_ms", 3000)
    filter_text = arguments.get("filter_text")
    specific_group = arguments.get("group")
    account_id = arguments.get("account_id")

    # Validate inputs
    if not isinstance(timeout_ms, (int, float)) or timeout_ms < 100 or timeout_ms > 30000:
        timeout_ms = 3000
    if specific_group is not None:
        if not isinstance(specific_group, int) or specific_group < 0 or specific_group > 65535:
            return {"success": False, "error": f"Invalid group: must be 0-65535, got {specific_group}"}

    # Build command with optional --group flag and filter
    parts = ["SCAN_WIDGETS"]
    if specific_group is not None:
        parts.append(f"--group {specific_group}")
    if filter_text:
        parts.append(filter_text)
    command = " ".join(parts)

    response = await send_command_with_response(command, timeout_ms, account_id)

    if response.get("status") == "success":
        widgets = response.get("result", {}).get("widgets", [])

        # Calculate which widget groups were found
        groups_found = set()
        for w in widgets:
            if "group" in w:
                groups_found.add(w["group"])

        # When unfiltered and large result set, return summary only to avoid overwhelming Claude
        # Full data is always available in /tmp/manny_widgets.json
        MAX_INLINE_WIDGETS = 50
        if not filter_text and not specific_group and len(widgets) > MAX_INLINE_WIDGETS:
            result = {
                "success": True,
                "count": len(widgets),
                "groups_found": sorted(groups_found),
                "truncated": True,
                "widgets": widgets[:20],  # Return first 20 as sample
                "hint": f"Large result ({len(widgets)} widgets). Full data in /tmp/manny_widgets.json. Use find_widget(text='...') for filtered searches.",
                "file": "/tmp/manny_widgets.json"
            }
        else:
            result = {
                "success": True,
                "widgets": widgets,
                "count": len(widgets),
                "filtered_by": filter_text,
                "groups_found": sorted(groups_found),
            }
            if specific_group is not None:
                result["scanned_group"] = specific_group

        return result
    else:
        return {
            "success": False,
            "error": response.get("error", "Failed to scan widgets"),
            "raw_response": response
        }


@registry.register({
    "name": "get_dialogue",
    "description": """[Routine Building] Get the current dialogue state including available options.

Returns whether a dialogue is open, the type (continue button, options, player input),
the speaker name, text, and clickable options with their widget IDs.""",
    "inputSchema": {
        "type": "object",
        "properties": {
            "timeout_ms": {
                "type": "integer",
                "description": "Timeout in milliseconds (default: 3000)",
                "default": 3000
            },
            "account_id": {
                "type": "string",
                "description": "Account ID for multi-client (optional, defaults to 'default')"
            }
        }
    }
})
async def handle_get_dialogue(arguments: dict) -> dict:
    """Get current dialogue state.

    Only returns dialogue-specific widgets, filtering out chat interface elements.

    Widget groups for OSRS dialogues:
    - 217: Player dialogue (chatbox player head)
    - 219: Options dialogue (multi-choice)
    - 231: NPC dialogue (chatbox NPC head)
    - 229: Continue button dialogue
    - 193: Item received notification
    """
    timeout_ms = arguments.get("timeout_ms", 3000)
    account_id = arguments.get("account_id")

    # Scan widgets to find dialogue elements
    response = await send_command_with_response("SCAN_WIDGETS", timeout_ms, account_id)

    if response.get("status") != "success":
        return {
            "success": False,
            "dialogue_open": False,
            "error": response.get("error", "Failed to scan widgets")
        }

    widgets = response.get("result", {}).get("widgets", [])

    # Parse dialogue widgets
    dialogue_info = {
        "success": True,
        "dialogue_open": False,
        "type": None,
        "speaker": None,
        "text": None,
        "options": [],
        "has_continue": False
    }

    # Known dialogue widget groups (all others are filtered out)
    # 217 = Player dialogue, 219 = Options, 231 = NPC dialogue,
    # 229 = Continue button, 193 = Item received
    DIALOGUE_GROUPS = {217, 219, 231, 229, 193}

    # Specific widget IDs for dialogue components
    PLAYER_NAME_ID = 14221316   # Group 217, child 4
    PLAYER_TEXT_ID = 14221318   # Group 217, child 6
    NPC_NAME_ID = 15138820      # Group 231, child 4
    NPC_TEXT_ID = 15138822      # Group 231, child 6
    OPTIONS_CONTAINER = 219     # Group 219 contains option children

    seen_options = set()  # Deduplicate options

    for widget in widgets:
        text = widget.get("text", "") or ""
        widget_id = widget.get("id", 0)

        if not widget_id or not text.strip():
            continue

        # Extract widget group from packed ID: group = id >> 16
        widget_group = widget_id >> 16

        # ONLY process dialogue-related widget groups
        if widget_group not in DIALOGUE_GROUPS:
            continue

        text_lower = text.lower().strip()
        text_clean = text.strip()

        # Check for "Click here to continue" button
        if "click here to continue" in text_lower:
            dialogue_info["dialogue_open"] = True
            dialogue_info["has_continue"] = True
            if not dialogue_info["type"]:
                dialogue_info["type"] = "continue"
            continue

        # Extract speaker name from player or NPC dialogue
        if widget_id == PLAYER_NAME_ID or widget_id == NPC_NAME_ID:
            dialogue_info["speaker"] = text_clean
            dialogue_info["dialogue_open"] = True
            if not dialogue_info["type"]:
                dialogue_info["type"] = "npc" if widget_id == NPC_NAME_ID else "player"
            continue

        # Extract dialogue text from player or NPC dialogue
        if widget_id == PLAYER_TEXT_ID or widget_id == NPC_TEXT_ID:
            dialogue_info["text"] = text_clean
            dialogue_info["dialogue_open"] = True
            continue

        # Options dialogue (group 219)
        if widget_group == OPTIONS_CONTAINER:
            # Skip the "Select an option" header
            if text_lower == "select an option":
                dialogue_info["dialogue_open"] = True
                dialogue_info["type"] = "options"
                continue

            # Deduplicate (widgets sometimes appear twice)
            option_key = (widget_id, text_clean)
            if option_key in seen_options:
                continue
            seen_options.add(option_key)

            # Add actual dialogue options
            if text_clean and len(text_clean) < 200:
                dialogue_info["options"].append({
                    "text": text_clean,
                    "widget_id": widget_id
                })

    # Set type to options if we found options but didn't set type yet
    if dialogue_info["options"] and not dialogue_info["type"]:
        dialogue_info["dialogue_open"] = True
        dialogue_info["type"] = "options"

    return dialogue_info


@registry.register({
    "name": "get_chat_messages",
    "description": """[Routine Building] Get recent game chat messages from the chatbox.

Returns the last N game messages from the chatbox widget. Useful for detecting:
- Action feedback ("The grain slides down the chute", "You need a pot")
- Combat messages ("You hit a 5", "The goblin is dead")
- Quest progress hints
- Error messages ("You can't reach that")

Filters out player chat and focuses on game/server messages.""",
    "inputSchema": {
        "type": "object",
        "properties": {
            "max_messages": {
                "type": "integer",
                "description": "Maximum number of messages to return (default: 10)",
                "default": 10
            },
            "filter": {
                "type": "string",
                "description": "Optional substring filter (case-insensitive)"
            },
            "timeout_ms": {
                "type": "integer",
                "description": "Timeout in milliseconds (default: 3000)",
                "default": 3000
            },
            "account_id": {
                "type": "string",
                "description": "Account ID for multi-client (optional, defaults to 'default')"
            }
        }
    }
})
async def handle_get_chat_messages(arguments: dict) -> dict:
    """Get recent chat messages from the game chatbox.

    Widget groups for OSRS chat:
    - 162: Main chatbox container
    - Chat messages are children with text content
    """
    timeout_ms = arguments.get("timeout_ms", 3000)
    max_messages = arguments.get("max_messages", 10)
    filter_text = arguments.get("filter", "").lower()
    account_id = arguments.get("account_id")

    # Scan widgets to find chat messages
    response = await send_command_with_response("SCAN_WIDGETS --group 162", timeout_ms, account_id)

    if response.get("status") != "success":
        return {
            "success": False,
            "messages": [],
            "error": response.get("error", "Failed to scan chat widgets")
        }

    widgets = response.get("result", {}).get("widgets", [])

    messages = []
    seen_texts = set()  # Deduplicate messages

    # Chat message widget IDs in group 162
    # The chatbox has multiple children - we want text content
    CHATBOX_GROUP = 162

    for widget in widgets:
        text = widget.get("text", "") or ""
        widget_id = widget.get("id", 0)

        if not widget_id or not text.strip():
            continue

        # Extract widget group
        widget_group = widget_id >> 16

        # Only process chatbox widgets
        if widget_group != CHATBOX_GROUP:
            continue

        text_clean = text.strip()

        # Skip empty or very short texts
        if len(text_clean) < 3:
            continue

        # Skip UI labels (common chatbox labels)
        skip_labels = ["public", "private", "channel", "clan", "trade", "report",
                      "game", "all", "on", "off", "filter", "friends", "hide"]
        if text_clean.lower() in skip_labels:
            continue

        # Skip duplicates
        if text_clean in seen_texts:
            continue
        seen_texts.add(text_clean)

        # Apply filter if specified
        if filter_text and filter_text not in text_clean.lower():
            continue

        messages.append({
            "text": text_clean,
            "widget_id": widget_id
        })

        if len(messages) >= max_messages:
            break

    return {
        "success": True,
        "count": len(messages),
        "messages": messages
    }


WIDGET_SELECTION_FILE = "/tmp/manny_widget_select.txt"


@registry.register({
    "name": "clear_widget_overlay",
    "description": """[Widget Inspector] Clear the widget highlight overlay from the game screen.

Use this when the green bounding box overlay stays visible after closing the External Widget Inspector.
Simply clears the selection file so the overlay has nothing to highlight.""",
    "inputSchema": {
        "type": "object",
        "properties": {},
        "required": []
    }
})
async def handle_clear_widget_overlay(arguments: dict) -> dict:
    """Clear the widget selection overlay."""
    try:
        with open(WIDGET_SELECTION_FILE, 'w') as f:
            f.write("")
        return {
            "success": True,
            "message": "Widget overlay cleared"
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


@registry.register({
    "name": "click_text",
    "description": """[Routine Building] Find a widget containing the specified text and click it.

Useful for clicking dialogue options, buttons, or any UI element by its text content.
Returns success/failure and the widget ID that was clicked.""",
    "inputSchema": {
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
            },
            "account_id": {
                "type": "string",
                "description": "Account ID for multi-client (optional, defaults to 'default')"
            }
        },
        "required": ["text"]
    }
})
async def handle_click_text(arguments: dict) -> dict:
    """Click widget by text."""
    text = arguments.get("text", "")
    timeout_ms = arguments.get("timeout_ms", 3000)
    account_id = arguments.get("account_id")

    if not text:
        return {"success": False, "error": "No text provided"}

    # Use plugin's CLICK_DIALOGUE command
    response = await send_command_with_response(f'CLICK_DIALOGUE {text}', timeout_ms, account_id)

    if response.get("status") == "success":
        return {
            "success": True,
            "clicked": text,
            "message": response.get("result", {}).get("message", "Clicked")
        }
    else:
        return {
            "success": False,
            "error": response.get("error", "Failed to click text"),
            "searched_for": text
        }


@registry.register({
    "name": "click_continue",
    "description": """[Routine Building] Click the 'Click here to continue' button in dialogues.

Automatically finds and clicks continue buttons in NPC dialogues.
Returns success/failure.""",
    "inputSchema": {
        "type": "object",
        "properties": {
            "timeout_ms": {
                "type": "integer",
                "description": "Timeout in milliseconds (default: 3000)",
                "default": 3000
            },
            "account_id": {
                "type": "string",
                "description": "Account ID for multi-client (optional, defaults to 'default')"
            }
        }
    }
})
async def handle_click_continue(arguments: dict) -> dict:
    """Click continue button."""
    timeout_ms = arguments.get("timeout_ms", 3000)
    account_id = arguments.get("account_id")

    response = await send_command_with_response("CLICK_CONTINUE", timeout_ms, account_id)

    if response.get("status") == "success":
        return {
            "success": True,
            "message": response.get("result", {}).get("message", "Clicked continue")
        }
    else:
        return {
            "success": False,
            "error": response.get("error", "No continue button found")
        }


@registry.register({
    "name": "query_nearby",
    "description": """[Routine Building] Query nearby NPCs, objects, and ground items with their available actions.

Returns lists of NPCs, objects, and ground items within range, including their names,
distances, and available right-click actions. Useful for discovering what can be interacted with.

Ground items include:
- Dropped items on the ground
- Items displayed on tables/shelves (scenery items)
- Spawned items (like wine of zamorak)""",
    "inputSchema": {
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
            "include_ground_items": {
                "type": "boolean",
                "description": "Include ground items (items on ground/tables) in results (default: true)",
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
            },
            "account_id": {
                "type": "string",
                "description": "Account ID for multi-client (optional, defaults to 'default')"
            }
        }
    }
})
async def handle_query_nearby(arguments: dict) -> dict:
    """Query nearby NPCs, objects, and ground items."""
    include_npcs = arguments.get("include_npcs", True)
    include_objects = arguments.get("include_objects", True)
    include_ground_items = arguments.get("include_ground_items", True)
    name_filter = arguments.get("name_filter")
    timeout_ms = arguments.get("timeout_ms", 3000)
    account_id = arguments.get("account_id")

    result = {
        "success": True,
        "npcs": [],
        "objects": [],
        "ground_items": []
    }

    # Query NPCs
    if include_npcs:
        response = await send_command_with_response("QUERY_NPCS", timeout_ms, account_id)
        if response.get("status") == "success":
            npcs = response.get("result", {}).get("npcs", [])
            if name_filter:
                filter_lower = name_filter.lower()
                npcs = [n for n in npcs if filter_lower in (n.get("name") or "").lower()]
            result["npcs"] = npcs

    # Query objects
    if include_objects:
        response = await send_command_with_response("SCAN_OBJECTS", timeout_ms, account_id)
        if response.get("status") == "success":
            objects = response.get("result", {}).get("objects", [])
            if name_filter:
                filter_lower = name_filter.lower()
                objects = [o for o in objects if filter_lower in (o.get("name") or "").lower()]
            result["objects"] = objects

    # Query ground items (items on ground/tables)
    if include_ground_items:
        response = await send_command_with_response("QUERY_GROUND_ITEMS", timeout_ms, account_id)
        if response.get("status") == "success":
            ground_items = response.get("result", {}).get("ground_items", [])
            if name_filter:
                filter_lower = name_filter.lower()
                ground_items = [i for i in ground_items if filter_lower in (i.get("name") or "").lower()]
            result["ground_items"] = ground_items

    # Truncate large responses to avoid filling context
    return maybe_truncate_response(result, prefix="nearby_output")


@registry.register({
    "name": "get_command_response",
    "description": """[Routine Building] Read the last command response from the plugin.

Returns the most recent response from /tmp/manny_response.json.
Useful for checking results of commands sent via send_command.""",
    "inputSchema": {
        "type": "object",
        "properties": {
            "account_id": {
                "type": "string",
                "description": "Account ID for multi-client (optional, defaults to 'default')"
            }
        }
    }
})
async def handle_get_command_response(arguments: dict) -> dict:
    """Read last command response."""
    account_id = arguments.get("account_id")
    response_file = config.get_response_file(account_id)

    try:
        if os.path.exists(response_file):
            with open(response_file) as f:
                response = json.load(f)
            result = {
                "success": True,
                "response": response
            }
            if account_id:
                result["account_id"] = account_id
            return result
        else:
            return {
                "success": False,
                "error": "No response file found"
            }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


@registry.register({
    "name": "scan_tile_objects",
    "description": """[Routine Building] Scan for ANY type of TileObject near the player.

Unlike query_nearby (which only finds GameObjects), this searches ALL TileObject types:
- GameObject (normal scenery)
- WallObject (doors, gates, fences, walls)
- DecorativeObject (decorations)
- GroundObject (ground-layer objects)
- GroundItem (items on ground/tables - TileItems)

Essential for finding doors, gates, fences (WallObjects) AND items on tables (GroundItems).
Returns object type, ID, location, distance, and available actions.""",
    "inputSchema": {
        "type": "object",
        "properties": {
            "object_name": {
                "type": "string",
                "description": "Name of object to search for (underscores replaced with spaces)"
            },
            "max_distance": {
                "type": "integer",
                "description": "Maximum search distance in tiles (default: 15)",
                "default": 15
            },
            "timeout_ms": {
                "type": "integer",
                "description": "Timeout in milliseconds (default: 3000)",
                "default": 3000
            },
            "account_id": {
                "type": "string",
                "description": "Account ID for multi-client (optional, defaults to 'default')"
            }
        },
        "required": ["object_name"]
    }
})
async def handle_scan_tile_objects(arguments: dict) -> dict:
    """Scan for TileObjects by name (includes WallObjects for doors/gates)."""
    object_name = arguments.get("object_name", "")
    max_distance = arguments.get("max_distance", 15)
    timeout_ms = arguments.get("timeout_ms", 3000)
    account_id = arguments.get("account_id")

    if not object_name:
        return {"success": False, "error": "object_name is required"}

    # Build command with optional distance
    command = f"SCAN_TILEOBJECTS {object_name} {max_distance}"
    response = await send_command_with_response(command, timeout_ms, account_id)

    if response.get("status") == "success":
        result = response.get("result", {})
        # Handle single vs multiple objects
        if "objects" in result:
            output = {
                "success": True,
                "count": result.get("count", len(result["objects"])),
                "objects": result["objects"],
                "searched_for": object_name
            }
        else:
            # Single object returned directly
            output = {
                "success": True,
                "count": 1,
                "objects": [result],
                "searched_for": object_name
            }
        # Truncate large responses to avoid filling context
        return maybe_truncate_response(output, prefix="tile_objects_output")
    else:
        return {
            "success": False,
            "error": response.get("error", f"'{object_name}' not found"),
            "searched_for": object_name,
            "note": "Searched: GameObject, WallObject, DecorativeObject, GroundObject, GroundItem"
        }


@registry.register({
    "name": "list_plugin_commands",
    "description": """[Discovery] List all available manny plugin commands with metadata.

Returns commands organized by category (fishing, mining, banking, navigation, etc.)
with argument format and description for each command. Use this to discover what
commands the plugin supports without reading source code.""",
    "inputSchema": {
        "type": "object",
        "properties": {
            "category": {
                "type": "string",
                "description": "Optional: filter by category (fishing, mining, banking, navigation, dialogue, query, etc.)"
            },
            "timeout_ms": {
                "type": "integer",
                "description": "Timeout in milliseconds (default: 3000)",
                "default": 3000
            },
            "account_id": {
                "type": "string",
                "description": "Account ID for multi-client (optional, defaults to 'default')"
            }
        }
    }
})
async def handle_list_plugin_commands(arguments: dict) -> dict:
    """List all plugin commands with metadata."""
    timeout_ms = arguments.get("timeout_ms", 3000)
    category_filter = arguments.get("category")
    account_id = arguments.get("account_id")

    # Send LIST_COMMANDS to plugin
    response = await send_command_with_response("LIST_COMMANDS", timeout_ms, account_id)

    if response.get("status") == "success":
        commands_data = response.get("result", {})

        # Apply category filter if provided
        if category_filter:
            all_commands = commands_data.get("commands", {})
            if category_filter in all_commands:
                filtered_commands = {category_filter: all_commands[category_filter]}
                return {
                    "success": True,
                    "total_commands": len(all_commands[category_filter]),
                    "categories": [category_filter],
                    "commands": filtered_commands,
                    "filtered_by": category_filter
                }
            else:
                return {
                    "success": False,
                    "error": f"Category '{category_filter}' not found",
                    "available_categories": commands_data.get("categories", [])
                }
        else:
            # Return all commands
            return {
                "success": True,
                "total_commands": commands_data.get("total_commands", 0),
                "categories": commands_data.get("categories", []),
                "commands": commands_data.get("commands", {})
            }
    else:
        return {
            "success": False,
            "error": response.get("error", "Failed to list commands"),
            "raw_response": response
        }


import yaml
import asyncio
import time

# Late-import handlers from other modules (set in set_dependencies)
_handle_send_and_await = None
_handle_await_state_change = None


def interpolate_variables(text: str, config: dict) -> str:
    """
    Interpolate ${variable} references in text using config values.

    Supports:
    - ${variable} - Direct substitution
    - ${variable|underscore} - Replace spaces with underscores (for command args)

    Examples:
        config = {"raw_food": "Raw swordfish", "quantity": 28}
        interpolate_variables("${raw_food}", config) -> "Raw swordfish"
        interpolate_variables("${raw_food|underscore}", config) -> "Raw_swordfish"
        interpolate_variables("${raw_food|underscore} ${quantity}", config) -> "Raw_swordfish 28"
    """
    if not text or not config:
        return text

    # Pattern matches ${variable} or ${variable|filter}
    pattern = r'\$\{([a-zA-Z_][a-zA-Z0-9_]*)(?:\|([a-zA-Z_]+))?\}'

    def replacer(match):
        var_name = match.group(1)
        filter_name = match.group(2)

        if var_name not in config:
            # Leave unresolved variables as-is (or could raise error)
            return match.group(0)

        value = config[var_name]
        # Convert to string if needed
        value = str(value) if not isinstance(value, str) else value

        # Apply filter if specified
        if filter_name == "underscore":
            value = value.replace(" ", "_")
        # Add more filters here as needed (e.g., lowercase, uppercase)

        return value

    return re.sub(pattern, replacer, text)


@registry.register({
    "name": "execute_routine",
    "description": """[Routine Execution] Execute a YAML routine file step by step.

Loads a routine YAML file and executes each step in order:
- Sends commands to the game
- Waits for await_conditions (plane changes, inventory changes, etc.)
- Handles delays between steps
- Reports progress after each step
- Loops if loop.enabled is true

Returns progress updates and final results.""",
    "inputSchema": {
        "type": "object",
        "properties": {
            "routine_path": {
                "type": "string",
                "description": "Path to the routine YAML file"
            },
            "start_step": {
                "type": "integer",
                "description": "Step ID to start from (default: 1)",
                "default": 1
            },
            "max_loops": {
                "type": "integer",
                "description": "Maximum number of loop iterations (default: 10000)",
                "default": 10000
            },
            "account_id": {
                "type": "string",
                "description": "Account ID for multi-client (optional)"
            }
        },
        "required": ["routine_path"]
    }
})
async def handle_execute_routine(arguments: dict) -> dict:
    """Execute a YAML routine step by step with inner/outer loop support."""
    routine_path = arguments.get("routine_path")
    start_step = arguments.get("start_step", 1)
    max_loops = arguments.get("max_loops", 10000)
    account_id = arguments.get("account_id")

    # Load routine YAML
    try:
        with open(routine_path, 'r') as f:
            routine = yaml.safe_load(f)
    except FileNotFoundError:
        return {"success": False, "error": f"Routine file not found: {routine_path}"}
    except yaml.YAMLError as e:
        return {"success": False, "error": f"Invalid YAML: {e}"}

    if not routine or 'steps' not in routine:
        return {"success": False, "error": "Routine has no steps"}

    steps = routine['steps']
    loop_config = routine.get('loop', {})
    routine_config = routine.get('config', {})

    # Build step index: map step ID -> list index (supports string IDs like "6b")
    step_id_to_idx = {}
    for idx, step in enumerate(steps):
        sid = step.get('id', idx + 1)
        step_id_to_idx[str(sid)] = idx

    # Parse loop configuration (supports both flat and inner/outer formats)
    inner_loop = loop_config.get('inner', {})
    outer_loop = loop_config.get('outer', {})

    # Flat loop format (backwards compatible)
    flat_loop_enabled = loop_config.get('enabled', False)
    flat_repeat_from = loop_config.get('repeat_from_step', 1)

    # Determine loop mode
    has_inner_outer = inner_loop.get('enabled', False) or outer_loop.get('enabled', False)

    inner_start_idx = None
    inner_end_idx = None
    if inner_loop.get('enabled', False):
        inner_start_idx = _resolve_step_idx(inner_loop.get('start_step', 1), step_id_to_idx, None)
        inner_end_idx = _resolve_step_idx(inner_loop.get('end_step', ''), step_id_to_idx, None)

    results = {
        "success": True,
        "routine_name": routine.get('name', 'Unknown'),
        "total_steps": len(steps),
        "completed_steps": [],
        "inner_loops_completed": 0,
        "outer_loops_completed": 0,
        "loops_completed": 0,
        "errors": []
    }

    health_check_interval = 5
    steps_since_health_check = 0
    outer_count = 0
    inner_count = 0
    restart_attempts = 0
    max_restart_attempts = 3
    inner_consecutive_failures = 0
    max_inner_consecutive_failures = 3
    current_step_idx = _resolve_step_idx(start_step, step_id_to_idx, 0)

    while outer_count < max_loops:
        # Health check at start of each outer loop
        health = await check_client_health(account_id, max_stale_seconds=60)
        if not health["alive"]:
            if restart_attempts < max_restart_attempts:
                restart_attempts += 1
                _routine_logger.warning("[ROUTINE] Client crash detected (attempt %d/%d), auto-restarting...",
                                        restart_attempts, max_restart_attempts)
                restarted = await _auto_restart_client(account_id)
                if restarted:
                    results["errors"].append(f"Auto-restarted client (attempt {restart_attempts})")
                    continue  # Retry this outer loop iteration
            results["success"] = False
            results["crash_detected"] = True
            results["crash_error"] = health["error"]
            results["stale_seconds"] = health.get("stale_seconds")
            results["restart_attempts"] = restart_attempts
            return results

        # Execute steps
        while current_step_idx < len(steps):
            step = steps[current_step_idx]
            step_id = step.get('id', current_step_idx + 1)

            # Execute this step
            step_result = await _execute_single_step(step, current_step_idx, routine_config, account_id)
            results["completed_steps"].append(step_result)

            # Track failures
            if not step_result.get("success", True):
                action = step.get('action', step.get('mcp_tool', '?'))
                results["errors"].append(f"Step {step_id} ({action}): {step_result.get('error', 'failed')}")

                # Inner loop failure: restart iteration instead of continuing
                if (inner_start_idx is not None and inner_end_idx is not None
                        and inner_start_idx <= current_step_idx <= inner_end_idx):
                    inner_consecutive_failures += 1
                    _routine_logger.warning(
                        "[ROUTINE] Inner loop step %s failed (%d/%d). Restarting from step %s.",
                        step_id, inner_consecutive_failures, max_inner_consecutive_failures,
                        inner_loop.get('start_step', 1))

                    if inner_consecutive_failures >= max_inner_consecutive_failures:
                        _routine_logger.warning(
                            "[ROUTINE] %d consecutive inner loop failures. Exiting via on_exit.",
                            inner_consecutive_failures)
                        inner_consecutive_failures = 0
                        on_exit = inner_loop.get('on_exit', '')
                        if on_exit.startswith('goto_step:'):
                            target_step = on_exit.split(':', 1)[1]
                            jump_idx = _resolve_step_idx(target_step, step_id_to_idx, None)
                            if jump_idx is not None:
                                current_step_idx = jump_idx
                                continue
                    else:
                        current_step_idx = inner_start_idx
                        continue

            # Periodic health check
            steps_since_health_check += 1
            if steps_since_health_check >= health_check_interval:
                steps_since_health_check = 0
                health = await check_client_health(account_id, max_stale_seconds=60)
                if not health["alive"]:
                    if restart_attempts < max_restart_attempts:
                        restart_attempts += 1
                        _routine_logger.warning("[ROUTINE] Client crash at step %s (attempt %d/%d), auto-restarting...",
                                                step_id, restart_attempts, max_restart_attempts)
                        restarted = await _auto_restart_client(account_id)
                        if restarted:
                            results["errors"].append(f"Auto-restarted at step {step_id} (attempt {restart_attempts})")
                            break  # Break inner step loop, re-enter outer loop (re-checks health)
                    results["success"] = False
                    results["crash_detected"] = True
                    results["crash_error"] = health["error"]
                    results["crashed_at_step"] = step_id
                    results["restart_attempts"] = restart_attempts
                    return results

            # Check inner loop: did we just finish the inner loop's end_step?
            if has_inner_outer and inner_loop.get('enabled', False):
                inner_end = str(inner_loop.get('end_step', ''))
                if str(step_id) == inner_end:
                    # Check inner exit conditions
                    inner_exit = await _check_conditions(
                        inner_loop.get('exit_conditions', []), routine_config, account_id)

                    if inner_exit:
                        # Inner loop exits - jump to on_exit target
                        inner_count += 1
                        inner_consecutive_failures = 0
                        results["inner_loops_completed"] = inner_count
                        on_exit = inner_loop.get('on_exit', '')
                        if on_exit.startswith('goto_step:'):
                            target_step = on_exit.split(':', 1)[1]
                            jump_idx = _resolve_step_idx(target_step, step_id_to_idx, None)
                            if jump_idx is not None:
                                current_step_idx = jump_idx
                                continue
                        # If no on_exit or invalid target, fall through to next step
                    else:
                        # Inner loop continues - jump back to start_step
                        inner_consecutive_failures = 0
                        if inner_start_idx is not None:
                            current_step_idx = inner_start_idx
                            continue

            current_step_idx += 1

        # All steps completed - check if we should loop
        if has_inner_outer and outer_loop.get('enabled', False):
            outer_count += 1
            results["outer_loops_completed"] = outer_count
            results["loops_completed"] = outer_count

            # Check outer exit conditions
            outer_exit = await _check_conditions(
                outer_loop.get('exit_conditions', []), routine_config, account_id)

            if outer_exit:
                results["stop_reason"] = "outer_exit_condition_met"
                break

            # Outer loop continues - restart from outer start_step
            outer_start = outer_loop.get('start_step', 1)
            current_step_idx = _resolve_step_idx(outer_start, step_id_to_idx, 0)

        elif flat_loop_enabled:
            # Flat loop (backwards compatible)
            outer_count += 1
            results["loops_completed"] = outer_count
            current_step_idx = _resolve_step_idx(flat_repeat_from, step_id_to_idx, 0)

            # Check flat stop conditions
            stop_conditions = loop_config.get('stop_conditions', [])
            should_stop = False
            for condition in stop_conditions:
                interpolated = condition
                if routine_config:
                    interpolated = interpolate_variables(condition, routine_config)
                if await check_stop_condition(interpolated, account_id):
                    should_stop = True
                    results["stop_reason"] = interpolated
                    break
            if should_stop:
                break
        else:
            break

    return results


def _resolve_step_idx(step_id, step_id_to_idx: dict, default):
    """Resolve a step ID (int or string like '6b') to a list index."""
    key = str(step_id)
    if key in step_id_to_idx:
        return step_id_to_idx[key]
    # Try as integer index (1-based)
    try:
        return int(step_id) - 1
    except (ValueError, TypeError):
        return default


async def _check_conditions(conditions: list, routine_config: dict, account_id: str) -> bool:
    """Check if ANY exit condition is met. Returns True if should exit."""
    for condition in conditions:
        interpolated = condition
        if routine_config:
            interpolated = interpolate_variables(condition, routine_config)
        if await check_stop_condition(interpolated, account_id):
            return True
    return False


async def _execute_single_step(step: dict, step_idx: int, routine_config: dict, account_id: str) -> dict:
    """Execute a single routine step and return the result."""
    step_id = step.get('id', step_idx + 1)
    action = step.get('action')
    delay_before = step.get('delay_before_ms', 0)
    timeout_ms = step.get('timeout_ms', 30000)

    # Interpolate variables in step fields
    args = step.get('args', '')
    if args and routine_config:
        args = interpolate_variables(str(args), routine_config)

    await_condition = step.get('await_condition')
    if await_condition and routine_config:
        await_condition = interpolate_variables(await_condition, routine_config)

    # Apply delay before action
    if delay_before > 0:
        await asyncio.sleep(delay_before / 1000)

    # Check for mcp_tool field (MCP tool invocation instead of game command)
    mcp_tool = step.get('mcp_tool')
    if mcp_tool:
        return await _execute_mcp_tool_step(step, mcp_tool, account_id)

    # Build and send command
    command = f"{action} {args}".strip() if args else action

    step_result = {
        "step_id": step_id,
        "phase": step.get('phase'),
        "action": action,
        "command": command
    }

    # Handle step execution using existing tested handlers
    if action == "WAIT":
        if await_condition:
            result = await _handle_await_state_change({
                "condition": await_condition,
                "timeout_ms": timeout_ms,
                "poll_interval_ms": 200,
                "account_id": account_id
            })
            step_result["success"] = result.get("success", False)
            step_result["elapsed_ms"] = result.get("elapsed_ms")
            step_result["await_result"] = "success" if result.get("success") else "timeout"
        else:
            await asyncio.sleep(timeout_ms / 1000)
            step_result["success"] = True
            step_result["await_result"] = "waited"

    elif await_condition:
        result = await _handle_send_and_await({
            "command": command,
            "await_condition": await_condition,
            "timeout_ms": timeout_ms,
            "poll_interval_ms": 200,
            "account_id": account_id
        })
        step_result["success"] = result.get("success", False)
        step_result["elapsed_ms"] = result.get("elapsed_ms")
        step_result["checks"] = result.get("checks")
        step_result["await_result"] = "success" if result.get("success") else "timeout"

        # Retry once if condition not met
        if not result.get("success"):
            result = await _handle_send_and_await({
                "command": command,
                "await_condition": await_condition,
                "timeout_ms": timeout_ms * 2,
                "poll_interval_ms": 200,
                "account_id": account_id
            })
            if result.get("success"):
                step_result["success"] = True
                step_result["await_result"] = "success"
                step_result["retried"] = True

    else:
        result = await execute_simple_command(command, timeout_ms, account_id)
        step_result["success"] = result.get("success", False)
        step_result["response"] = result.get("response", {}).get("status")
        step_result["elapsed_ms"] = result.get("elapsed_ms")
        if result.get("error"):
            step_result["error"] = result["error"]

    # Apply delay after action
    delay_after = step.get('delay_after_ms', 0)
    if delay_after > 0:
        await asyncio.sleep(delay_after / 1000.0)

    return step_result


async def _execute_mcp_tool_step(step: dict, mcp_tool: str, account_id: str) -> dict:
    """Execute a step that invokes an MCP tool."""
    step_id = step.get('id', '?')
    mcp_args = step.get('args', {})
    if isinstance(mcp_args, str):
        mcp_args = {}
    if account_id and 'account_id' not in mcp_args:
        mcp_args['account_id'] = account_id

    step_result = {
        "step_id": step_id,
        "phase": step.get('phase'),
        "mcp_tool": mcp_tool,
        "mcp_args": mcp_args
    }

    try:
        if mcp_tool == "equip_item":
            result = await _handle_equip_item(mcp_args)
        elif mcp_tool == "find_and_click_widget":
            result = await handle_find_and_click_widget(mcp_args)
        else:
            step_result["success"] = False
            step_result["error"] = f"Unknown mcp_tool: {mcp_tool}"
            return step_result

        step_result["success"] = result.get("success", False)
        step_result["result"] = result
        if not result.get("success"):
            step_result["error"] = result.get("error", "MCP tool failed")

    except Exception as e:
        step_result["success"] = False
        step_result["error"] = str(e)

    return step_result


async def check_stop_condition(condition: str, account_id: str = None) -> bool:
    """Check if a loop stop condition is met."""
    state = await get_game_state(account_id)
    if not state:
        return False

    # inventory_full - All 28 slots used
    if condition == "inventory_full":
        inventory = state.get("inventory", state.get("player", {}).get("inventory", {}))
        # Handle both compact format {"used": N} and list format
        if isinstance(inventory, dict):
            used = inventory.get("used", 0)
            return used >= 28
        elif isinstance(inventory, list):
            return len([i for i in inventory if i]) >= 28
        return False

    # no_item:ItemName - Item not in inventory
    if condition.startswith("no_item:"):
        item_name = condition[len("no_item:"):].strip()
        inventory = state.get("inventory", state.get("player", {}).get("inventory", {}))
        # Check compact format: {"items": ["Coal x2", "Iron ore x1", ...]}
        if isinstance(inventory, dict):
            items = inventory.get("items", [])
            for item in items:
                # Items may be "Name xN" or just "Name"
                if isinstance(item, str) and item.split(" x")[0] == item_name:
                    return False
                elif isinstance(item, dict) and item.get("name") == item_name:
                    return False
            return True  # Item not found
        elif isinstance(inventory, list):
            for item in inventory:
                if isinstance(item, dict) and item.get("name") == item_name:
                    return False
                elif isinstance(item, str) and item.split(" x")[0] == item_name:
                    return False
            return True
        return False

    # has_item:ItemName - Item IS in inventory
    if condition.startswith("has_item:"):
        item_name = condition[len("has_item:"):].strip()
        # Invert no_item check
        return not await check_stop_condition(f"no_item:{item_name}", account_id)

    # no_item_in_bank:ItemName - No more of item in bank (can't withdraw)
    if condition.startswith("no_item_in_bank:"):
        # Bank contents not available in state file - return False
        return False

    # skill_level:N - Skill reached level N
    if "_level:" in condition:
        parts = condition.split("_level:")
        skill_name = parts[0].lower()
        target_level = int(parts[1])
        skills = state.get("player", {}).get("skills", {})
        current_level = skills.get(skill_name, {}).get("level", 0)
        return current_level >= target_level

    return False


async def get_game_state(account_id: str = None) -> dict:
    """Read current game state from file."""
    state_file = config.get_state_file(account_id) if config else "/tmp/manny_state.json"
    try:
        with open(state_file, 'r') as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


async def check_client_health(account_id: str = None, max_stale_seconds: float = 60) -> dict:
    """
    Check if the client is alive by checking state file freshness.

    Returns:
        dict with:
        - alive: bool - True if client appears healthy
        - stale_seconds: float - How old the state file is
        - error: str - Error message if not alive
    """
    state_file = config.get_state_file(account_id) if config else "/tmp/manny_state.json"

    try:
        stat = os.stat(state_file)
        age_seconds = time.time() - stat.st_mtime

        if age_seconds > max_stale_seconds:
            return {
                "alive": False,
                "stale_seconds": age_seconds,
                "error": f"State file stale for {age_seconds:.0f}s (>{max_stale_seconds}s) - client likely crashed"
            }

        return {
            "alive": True,
            "stale_seconds": age_seconds
        }
    except FileNotFoundError:
        return {
            "alive": False,
            "stale_seconds": None,
            "error": "State file not found - client not running"
        }
    except Exception as e:
        return {
            "alive": False,
            "stale_seconds": None,
            "error": f"Error checking state file: {e}"
        }


import logging
_routine_logger = logging.getLogger("routine.auto_restart")


async def _auto_restart_client(account_id: str = None) -> bool:
    """
    Stop and restart the RuneLite client, then wait for the state file to refresh.

    Returns True if the client is healthy again, False otherwise.
    """
    if runelite_manager is None:
        _routine_logger.warning("[AUTO-RESTART] No runelite_manager available, cannot restart")
        return False

    _routine_logger.info("[AUTO-RESTART] Stopping client for account '%s'...", account_id or "default")
    try:
        runelite_manager.stop_instance(account_id)
    except Exception as e:
        _routine_logger.warning("[AUTO-RESTART] Stop failed (may already be dead): %s", e)

    await asyncio.sleep(3)  # Brief cooldown before restart

    _routine_logger.info("[AUTO-RESTART] Starting client for account '%s'...", account_id or "default")
    try:
        start_result = runelite_manager.start_instance(account_id)
        if not start_result.get("success", False):
            _routine_logger.error("[AUTO-RESTART] Start failed: %s", start_result)
            return False
    except Exception as e:
        _routine_logger.error("[AUTO-RESTART] Start exception: %s", e)
        return False

    # Wait for state file to become fresh (max 120s for login + plugin load)
    _routine_logger.info("[AUTO-RESTART] Waiting for state file to refresh...")
    for i in range(60):  # 60 * 2s = 120s
        await asyncio.sleep(2)
        health = await check_client_health(account_id, max_stale_seconds=10)
        if health["alive"]:
            _routine_logger.info("[AUTO-RESTART] Client healthy after %ds", (i + 1) * 2)
            return True

    _routine_logger.error("[AUTO-RESTART] Client did not become healthy within 120s")
    return False


@registry.register({
    "name": "click_widget",
    "description": """[Routine Building] Click a widget by its ID.

Uses the plugin's CLICK_WIDGET command with proper coordinate handling.
The widget is clicked at its center using absolute screen coordinates.

Example: click_widget(widget_id=17694735) to click the cooking interface shrimp button.

For virtual widgets (deposit box items, shop items, etc.) that share a container ID,
pass the bounds from find_widget() to click at the correct position:
  click_widget(widget_id=12582914, bounds={"x": 269, "y": 106, "width": 36, "height": 32})

To find widget IDs:
1. Use scan_widgets() to see all visible widgets
2. Or use find_widget() to search for specific text""",
    "inputSchema": {
        "type": "object",
        "properties": {
            "widget_id": {
                "type": "integer",
                "description": "The packed widget ID (e.g., 17694735)"
            },
            "bounds": {
                "type": "object",
                "description": "Optional bounds for virtual widgets: {x, y, width, height}. When provided, clicks at center of bounds instead of using Java's widget lookup.",
                "properties": {
                    "x": {"type": "integer"},
                    "y": {"type": "integer"},
                    "width": {"type": "integer"},
                    "height": {"type": "integer"}
                }
            },
            "timeout_ms": {
                "type": "integer",
                "description": "Timeout in milliseconds (default: 5000)",
                "default": 5000
            },
            "account_id": {
                "type": "string",
                "description": "Account ID for multi-client (optional, defaults to 'default')"
            }
        },
        "required": ["widget_id"]
    }
})
async def handle_click_widget(arguments: dict) -> dict:
    """Click a widget by ID, or by bounds for virtual widgets."""
    widget_id = arguments.get("widget_id")
    bounds = arguments.get("bounds")
    timeout_ms = arguments.get("timeout_ms", 5000)
    account_id = arguments.get("account_id")

    if not widget_id:
        return {"success": False, "error": "widget_id is required"}

    # If bounds provided, use direct mouse click (for virtual widgets like deposit box items)
    if bounds and all(k in bounds for k in ("x", "y", "width", "height")):
        # Calculate center of widget
        click_x = bounds["x"] + bounds["width"] // 2
        click_y = bounds["y"] + bounds["height"] // 2

        # Use direct mouse commands - send MOUSE_MOVE first, then MOUSE_CLICK
        # Must be sent as separate commands since plugin only processes one command per file
        command_file = config.get_command_file(account_id)

        try:
            # Step 1: Move mouse to position
            with open(command_file, "w") as f:
                f.write(f"MOUSE_MOVE {click_x} {click_y}\n")

            # Wait for move to be processed (plugin polls every 200ms)
            await asyncio.sleep(0.3)

            # Step 2: Click at current position
            with open(command_file, "w") as f:
                f.write("MOUSE_CLICK left\n")

            return {
                "success": True,
                "widget_id": widget_id,
                "click_position": {"x": click_x, "y": click_y},
                "bounds": bounds,
                "message": f"Clicked virtual widget at ({click_x}, {click_y})"
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to send click: {e}"}

    # Otherwise use Java's CLICK_WIDGET command (for real widgets)
    response = await send_command_with_response(f"CLICK_WIDGET {widget_id}", timeout_ms, account_id)

    if response.get("status") == "success":
        result = response.get("result", {})
        return {
            "success": True,
            "widget_id": widget_id,
            "message": result.get("message", "Widget clicked")
        }
    else:
        return {
            "success": False,
            "widget_id": widget_id,
            "error": response.get("error", "Failed to click widget")
        }


@registry.register({
    "name": "find_widget",
    "description": """[Routine Building] Find widgets by text and return compact results.

Scans visible widgets and filters by text, name, OR item name. Returns only essential info for clicking:
- widget_id: The ID to pass to click_widget()
- text: The widget's text/item name
- bounds: {x, y, width, height} for reference
- actions: Available actions
- itemId/itemQuantity: For item widgets (inventory, bank, deposit box)

Much lighter than scan_widgets() - designed for finding clickable elements.

Examples:
- find_widget(text="Cook") - find cooking options in a menu
- find_widget(text="Raw lobster") - find lobster items in inventory/bank/deposit box
- find_widget(text="Deposit") - find deposit buttons""",
    "inputSchema": {
        "type": "object",
        "properties": {
            "text": {
                "type": "string",
                "description": "Text to search for - matches widget text, name, and item names (case-insensitive)"
            },
            "max_results": {
                "type": "integer",
                "description": "Maximum number of results (default: 5)",
                "default": 5
            },
            "timeout_ms": {
                "type": "integer",
                "description": "Timeout in milliseconds (default: 3000)",
                "default": 3000
            },
            "account_id": {
                "type": "string",
                "description": "Account ID for multi-client (optional, defaults to 'default')"
            }
        },
        "required": ["text"]
    }
})
async def handle_find_widget(arguments: dict) -> dict:
    """Find widgets by text with compact output."""
    text = arguments.get("text", "")
    max_results = arguments.get("max_results", 5)
    timeout_ms = arguments.get("timeout_ms", 3000)
    account_id = arguments.get("account_id")

    if not text:
        return {"success": False, "error": "text is required"}

    # Use server-side filtering for efficiency (Java command now supports itemName filtering)
    command = f"SCAN_WIDGETS {text}"
    response = await send_command_with_response(command, timeout_ms, account_id)

    if response.get("status") != "success":
        return {
            "success": False,
            "error": response.get("error", "Failed to scan widgets")
        }

    widgets = response.get("result", {}).get("widgets", [])

    # Compact results for output
    matches = []
    for w in widgets:
        # Get display text: prefer itemName for item widgets, then text, then name
        widget_text = w.get("itemName") or w.get("text") or w.get("name") or ""

        # Get bounds from the nested bounds object
        bounds_obj = w.get("bounds", {})

        result = {
            "widget_id": w.get("id"),
            "text": widget_text[:50] + "..." if len(widget_text) > 50 else widget_text,
            "bounds": {
                "x": bounds_obj.get("x"),
                "y": bounds_obj.get("y"),
                "width": bounds_obj.get("width"),
                "height": bounds_obj.get("height")
            },
            "actions": w.get("actions", [])[:3]  # Max 3 actions
        }

        # Include item info if present
        if w.get("itemId"):
            result["itemId"] = w.get("itemId")
            result["itemQuantity"] = w.get("itemQuantity")

        matches.append(result)
        if len(matches) >= max_results:
            break

    return {
        "success": True,
        "query": text,
        "found": len(matches),
        "total_widgets_scanned": len(widgets),
        "widgets": matches
    }


@registry.register({
    "name": "find_and_click_widget",
    "description": """[Routine Building] Find a widget by text/name/item and click it in one call.

Combines find_widget + click_widget into a single operation. Searches widget text,
name, item names, AND actions (like find_widget does), then clicks the first match.

This is the PREFERRED way to click UI elements when you know what text to search for.

Examples:
- find_and_click_widget(text="Inventory") - Click the Inventory tab
- find_and_click_widget(text="Quest") - Click the Quest tab
- find_and_click_widget(text="Continue") - Click continue button
- find_and_click_widget(text="Raw lobster", action="Drop") - Find lobster, use Drop action""",
    "inputSchema": {
        "type": "object",
        "properties": {
            "text": {
                "type": "string",
                "description": "Text to search for in widget text, name, item name, or actions"
            },
            "action": {
                "type": "string",
                "description": "Optional: Specific action to use when clicking (e.g., 'Drop', 'Use'). If not specified, uses default click."
            },
            "timeout_ms": {
                "type": "integer",
                "description": "Timeout in milliseconds (default: 3000)",
                "default": 3000
            },
            "account_id": {
                "type": "string",
                "description": "Account ID for multi-client (optional)"
            }
        },
        "required": ["text"]
    }
})
async def handle_find_and_click_widget(arguments: dict) -> dict:
    """Find a widget by text and click it in one operation."""
    text = arguments.get("text", "")
    action = arguments.get("action")
    timeout_ms = arguments.get("timeout_ms", 3000)
    account_id = arguments.get("account_id")

    if not text:
        return {"success": False, "error": "text is required"}

    # Step 1: Find widgets matching the text (uses server-side filtering)
    command = f"SCAN_WIDGETS {text}"
    response = await send_command_with_response(command, timeout_ms, account_id)

    if response.get("status") != "success":
        return {
            "success": False,
            "error": response.get("error", "Failed to scan widgets")
        }

    widgets = response.get("result", {}).get("widgets", [])

    if not widgets:
        return {
            "success": False,
            "error": f"No widget found matching '{text}'",
            "searched_for": text
        }

    # Step 2: Get the first match
    widget = widgets[0]
    widget_id = widget.get("id")
    widget_text = widget.get("itemName") or widget.get("text") or widget.get("name") or ""
    widget_actions = widget.get("actions", [])
    bounds = widget.get("bounds", {})

    # Step 3: Click the widget
    # IMPORTANT: For inventory items that share widget IDs (like container 9764864),
    # we must use the BOUNDS from find_widget, not search by action (which finds wrong item).
    # Use direct coordinate clicking when we have valid bounds.

    has_valid_bounds = bounds and all(k in bounds for k in ("x", "y", "width", "height")) and bounds.get("x", -1) >= 0

    if has_valid_bounds:
        # Click at center of the found widget's bounds (reliable for inventory items)
        click_x = bounds["x"] + bounds["width"] // 2
        click_y = bounds["y"] + bounds["height"] // 2

        # Use CLICK_AT command - atomic move+click handled by the Java plugin
        # This avoids xdotool display connection issues with gamescope
        click_command = f"CLICK_AT {click_x} {click_y}"
        click_response = await send_command_with_response(click_command, timeout_ms, account_id)
    else:
        # Fallback: Use CLICK_WIDGET with action (for widgets with proper individual IDs)
        if action:
            click_command = f'CLICK_WIDGET {widget_id} "{action}"'
        elif widget_actions:
            click_command = f'CLICK_WIDGET {widget_id} "{widget_actions[0]}"'
        else:
            click_command = f'CLICK_WIDGET {widget_id}'

        click_response = await send_command_with_response(click_command, timeout_ms, account_id)

    if click_response.get("status") == "success":
        return {
            "success": True,
            "clicked": True,
            "widget_id": widget_id,
            "text": widget_text[:50] if widget_text else None,
            "action_used": action or (widget_actions[0] if widget_actions else None),
            "bounds": bounds
        }
    else:
        return {
            "success": False,
            "error": click_response.get("error", "Failed to click widget"),
            "widget_id": widget_id,
            "widget_found": True
        }


@registry.register({
    "name": "click_widget_by_action",
    "description": """[Routine Building] Find a widget by action text and click it atomically.

Combines find_widget + click_widget into one operation with fresh bounds at click time.
Ideal for GE buttons, shop items, and other interfaces where widgets share container IDs.

The tool:
1. Scans all visible widgets for matching action
2. Gets fresh bounds at click time (avoids stale coordinate issues)
3. Clicks center of the matched widget

Examples:
- click_widget_by_action(action="+10%") - Click GE price +10% button
- click_widget_by_action(action="+10") - Click GE quantity +10 button
- click_widget_by_action(action="Buy 1") - Click shop Buy 1 option
- click_widget_by_action(action="-5%", container_id=30474266) - Limit search to GE container""",
    "inputSchema": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "description": "Action text to match (e.g., '+10%', 'Buy 1', '-5%')"
            },
            "container_id": {
                "type": "integer",
                "description": "Optional: Only match widgets with this container/parent ID"
            },
            "timeout_ms": {
                "type": "integer",
                "description": "Timeout in milliseconds (default: 3000)",
                "default": 3000
            },
            "account_id": {
                "type": "string",
                "description": "Account ID for multi-client (optional)"
            }
        },
        "required": ["action"]
    }
})
async def handle_click_widget_by_action(arguments: dict) -> dict:
    """Find a widget by action and click it in one atomic operation."""
    action = arguments.get("action", "")
    container_id = arguments.get("container_id")
    timeout_ms = arguments.get("timeout_ms", 3000)
    account_id = arguments.get("account_id")

    if not action:
        return {"success": False, "error": "action is required"}

    # Step 1: Scan for widgets matching the action
    command = f"SCAN_WIDGETS {action}"
    response = await send_command_with_response(command, timeout_ms, account_id)

    if response.get("status") != "success":
        return {
            "success": False,
            "error": response.get("error", "Failed to scan widgets")
        }

    widgets = response.get("result", {}).get("widgets", [])

    # Step 2: Find widget with matching action
    match = None
    for w in widgets:
        actions = w.get("actions", [])
        if not actions:
            continue

        # Check if any action matches (exact or contains)
        for widget_action in actions:
            if widget_action and (action in widget_action or action == widget_action):
                # If container_id specified, verify it matches
                if container_id is not None and w.get("id") != container_id:
                    continue
                match = w
                break
        if match:
            break

    if not match:
        return {
            "success": False,
            "error": f"No widget with action '{action}' found",
            "widgets_scanned": len(widgets)
        }

    # Step 3: Get bounds and click
    bounds = match.get("bounds", {})
    if not bounds or not all(k in bounds for k in ("x", "y", "width", "height")):
        return {
            "success": False,
            "error": f"Widget found but has invalid bounds: {bounds}"
        }

    click_x = bounds["x"] + bounds["width"] // 2
    click_y = bounds["y"] + bounds["height"] // 2

    # Send mouse commands
    command_file = config.get_command_file(account_id)

    try:
        # Use CLICK_AT for atomic move+click (avoids MOUSE_MOVE + MOUSE_CLICK race)
        click_command = f"CLICK_AT {click_x} {click_y}"
        click_response = await send_command_with_response(click_command, timeout_ms, account_id)

        if click_response.get("status") != "success":
            return {
                "success": False,
                "error": f"Click failed: {click_response.get('error', 'Unknown error')}",
                "action": action
            }

        return {
            "success": True,
            "action": action,
            "widget_id": match.get("id"),
            "clicked_at": {"x": click_x, "y": click_y},
            "bounds": bounds,
            "message": f"Clicked widget with action '{action}' at ({click_x}, {click_y})"
        }
    except Exception as e:
        return {"success": False, "error": f"Failed to send click: {e}"}


@registry.register({
    "name": "debug_widget_children",
    "description": """[Routine Building] List all clickable children of a widget container.

Returns all widgets that share a container ID, showing their bounds and actions.
Useful for debugging GE, shop, and other interfaces with virtual/child widgets.

Use this to visualize what Claude sees when interacting with complex interfaces.

Example:
- debug_widget_children(container_id=30474266) - List all GE offer screen buttons""",
    "inputSchema": {
        "type": "object",
        "properties": {
            "container_id": {
                "type": "integer",
                "description": "The container widget ID to inspect"
            },
            "timeout_ms": {
                "type": "integer",
                "description": "Timeout in milliseconds (default: 3000)",
                "default": 3000
            },
            "account_id": {
                "type": "string",
                "description": "Account ID for multi-client (optional)"
            }
        },
        "required": ["container_id"]
    }
})
async def handle_debug_widget_children(arguments: dict) -> dict:
    """List all clickable children of a container widget."""
    container_id = arguments.get("container_id")
    timeout_ms = arguments.get("timeout_ms", 3000)
    account_id = arguments.get("account_id")

    if not container_id:
        return {"success": False, "error": "container_id is required"}

    # Scan all widgets (no filter)
    command = "SCAN_WIDGETS"
    response = await send_command_with_response(command, timeout_ms, account_id)

    if response.get("status") != "success":
        return {
            "success": False,
            "error": response.get("error", "Failed to scan widgets")
        }

    all_widgets = response.get("result", {}).get("widgets", [])

    # Filter to only widgets matching the container ID
    children = []
    for w in all_widgets:
        if w.get("id") == container_id:
            bounds = w.get("bounds", {})
            actions = w.get("actions", [])
            text = w.get("text") or w.get("name") or w.get("itemName") or ""

            # Only include if has bounds and either actions or text
            if bounds and (actions or text):
                children.append({
                    "text": text[:30] if text else None,
                    "actions": actions,
                    "bounds": {
                        "x": bounds.get("x"),
                        "y": bounds.get("y"),
                        "width": bounds.get("width"),
                        "height": bounds.get("height")
                    },
                    "click_center": {
                        "x": bounds.get("x", 0) + bounds.get("width", 0) // 2,
                        "y": bounds.get("y", 0) + bounds.get("height", 0) // 2
                    }
                })

    # Sort by x position then y for visual order
    children.sort(key=lambda c: (c["bounds"]["y"], c["bounds"]["x"]))

    # Group by unique bounds (deduplicate)
    unique_children = []
    seen_bounds = set()
    for child in children:
        bounds_key = (child["bounds"]["x"], child["bounds"]["y"],
                      child["bounds"]["width"], child["bounds"]["height"])
        if bounds_key not in seen_bounds:
            seen_bounds.add(bounds_key)
            unique_children.append(child)

    return {
        "success": True,
        "container_id": container_id,
        "child_count": len(unique_children),
        "total_widgets_scanned": len(all_widgets),
        "children": unique_children
    }
