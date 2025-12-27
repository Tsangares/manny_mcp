"""
Routine building tools for widget/dialogue interaction.
Used for building multi-step game automations.
"""
import os
import json
from ..registry import registry


# Dependencies (send_command_with_response function)
send_command_with_response = None
RESPONSE_FILE = "/tmp/manny_response.json"


def set_dependencies(send_command_func):
    """Inject dependencies (called from server.py startup)"""
    global send_command_with_response
    send_command_with_response = send_command_func


@registry.register({
    "name": "scan_widgets",
    "description": """[Routine Building] Scan all visible widgets in the game UI. Returns widget IDs, text content, and bounds.

Use this to discover clickable elements, dialogue options, interface buttons, etc.
Filter by text to find specific widgets.""",
    "inputSchema": {
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
})
async def handle_scan_widgets(arguments: dict) -> dict:
    """Scan all visible widgets."""
    timeout_ms = arguments.get("timeout_ms", 3000)
    filter_text = arguments.get("filter_text")

    response = await send_command_with_response("SCAN_WIDGETS", timeout_ms)

    if response.get("status") == "success":
        widgets = response.get("result", {}).get("widgets", [])
        # Apply text filter if provided
        if filter_text:
            filter_lower = filter_text.lower()
            widgets = [w for w in widgets if filter_lower in (w.get("text") or "").lower()]
        return {
            "success": True,
            "widgets": widgets,
            "count": len(widgets),
            "filtered_by": filter_text
        }
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
            }
        }
    }
})
async def handle_get_dialogue(arguments: dict) -> dict:
    """Get current dialogue state."""
    timeout_ms = arguments.get("timeout_ms", 3000)

    # Scan widgets to find dialogue elements
    response = await send_command_with_response("SCAN_WIDGETS", timeout_ms)

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

    for widget in widgets:
        text = widget.get("text", "") or ""
        widget_id = widget.get("id", 0)

        # Check for "Click here to continue"
        if "click here to continue" in text.lower():
            dialogue_info["dialogue_open"] = True
            dialogue_info["has_continue"] = True
            dialogue_info["type"] = "continue"

        # Check for dialogue options
        if text and len(text) < 200 and "click here" not in text.lower():
            if widget_id:
                dialogue_info["options"].append({
                    "text": text,
                    "widget_id": widget_id
                })

    if dialogue_info["options"]:
        dialogue_info["dialogue_open"] = True
        if not dialogue_info["type"]:
            dialogue_info["type"] = "options"

    return dialogue_info


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
            }
        },
        "required": ["text"]
    }
})
async def handle_click_text(arguments: dict) -> dict:
    """Click widget by text."""
    text = arguments.get("text", "")
    timeout_ms = arguments.get("timeout_ms", 3000)

    if not text:
        return {"success": False, "error": "No text provided"}

    # Use plugin's CLICK_DIALOGUE command
    response = await send_command_with_response(f'CLICK_DIALOGUE {text}', timeout_ms)

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
            }
        }
    }
})
async def handle_click_continue(arguments: dict) -> dict:
    """Click continue button."""
    timeout_ms = arguments.get("timeout_ms", 3000)

    response = await send_command_with_response("CLICK_CONTINUE", timeout_ms)

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
    "description": """[Routine Building] Query nearby NPCs and objects with their available actions.

Returns lists of NPCs and objects within range, including their names,
distances, and available right-click actions. Useful for discovering
what can be interacted with.""",
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
})
async def handle_query_nearby(arguments: dict) -> dict:
    """Query nearby NPCs and objects."""
    include_npcs = arguments.get("include_npcs", True)
    include_objects = arguments.get("include_objects", True)
    name_filter = arguments.get("name_filter")
    timeout_ms = arguments.get("timeout_ms", 3000)

    result = {
        "success": True,
        "npcs": [],
        "objects": []
    }

    # Query NPCs
    if include_npcs:
        response = await send_command_with_response("QUERY_NPCS", timeout_ms)
        if response.get("status") == "success":
            npcs = response.get("result", {}).get("npcs", [])
            if name_filter:
                filter_lower = name_filter.lower()
                npcs = [n for n in npcs if filter_lower in (n.get("name") or "").lower()]
            result["npcs"] = npcs

    # Query objects
    if include_objects:
        response = await send_command_with_response("SCAN_OBJECTS", timeout_ms)
        if response.get("status") == "success":
            objects = response.get("result", {}).get("objects", [])
            if name_filter:
                filter_lower = name_filter.lower()
                objects = [o for o in objects if filter_lower in (o.get("name") or "").lower()]
            result["objects"] = objects

    return result


@registry.register({
    "name": "get_command_response",
    "description": """[Routine Building] Read the last command response from the plugin.

Returns the most recent response from /tmp/manny_response.json.
Useful for checking results of commands sent via send_command.""",
    "inputSchema": {
        "type": "object",
        "properties": {}
    }
})
async def handle_get_command_response(arguments: dict) -> dict:
    """Read last command response."""
    try:
        if os.path.exists(RESPONSE_FILE):
            with open(RESPONSE_FILE) as f:
                response = json.load(f)
            return {
                "success": True,
                "response": response
            }
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
            }
        }
    }
})
async def handle_list_plugin_commands(arguments: dict) -> dict:
    """List all plugin commands with metadata."""
    timeout_ms = arguments.get("timeout_ms", 3000)
    category_filter = arguments.get("category")

    # Send LIST_COMMANDS to plugin
    response = await send_command_with_response("LIST_COMMANDS", timeout_ms)

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
