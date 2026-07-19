"""
Routine building tools for widget/dialogue interaction.
Used for building multi-step game automations.
"""
import asyncio
import json
import logging
import os
import re
import time

import yaml

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
    Execute a command and wait for response confirmation.

    Unlike send_and_await, this doesn't check game state conditions - it just
    verifies the plugin processed the command by watching for a matching
    response. Delegates to ``transport.send_command`` (the ONE canonical,
    rid-correlated, atomic-write transport); this adapts its return to the
    ``{success, response, elapsed_ms, error}`` shape callers expect.

    Args:
        command: The command to send
        timeout_ms: Maximum time to wait for response
        account_id: Optional account ID for multi-client support

    Returns:
        dict with success, response, elapsed_ms, error
    """
    from .. import transport

    start_time = time.time()
    response = await transport.send_command(
        command,
        account_id=account_id,
        await_response=True,
        timeout=timeout_ms / 1000.0,
    )
    elapsed_ms = int((time.time() - start_time) * 1000)

    # Transport signals non-delivery / timeout via explicit flags.
    if response.get("timeout") or response.get("delivered") is False:
        return {
            "success": False,
            "error": response.get("error", "No response received"),
            "elapsed_ms": elapsed_ms,
        }

    success = response.get("status") == "success"
    return {
        "success": success,
        "response": response,
        "elapsed_ms": elapsed_ms,
        "error": response.get("error") if not success else None,
    }


@registry.register({
    "name": "find_widget",
    "description": """[Widgets] Canonical widget inspection tool. Scans visible widgets and returns compact, filtered results.

Modes (combine freely):
- find_widget(text="Raw lobster")      - search by widget text / name / item name (compact results for clicking)
- find_widget(group=593)               - scan a specific widget group (593 Combat, 149 Inventory, 162 Chatbox)
- find_widget(container_id=30474266)   - list all clickable children sharing a container ID (GE/shop/deposit interfaces)
- find_widget()                        - full-scan summary (count + groups + sample; full data in /tmp/manny_widgets.json)
- find_widget(full=true)               - raw widget data instead of compact results

Returns widget_id, text, bounds, actions (plus itemId/itemQuantity for items) - everything click_widget() needs.""",
    "inputSchema": {
        "type": "object",
        "properties": {
            "text": {
                "type": "string",
                "description": "Text to search for - matches widget text, name, and item names (case-insensitive)"
            },
            "group": {
                "type": "integer",
                "description": "Scan only a specific widget group (e.g., 593 for Combat Interface, 149 for Inventory)"
            },
            "container_id": {
                "type": "integer",
                "description": "List all clickable children of this container widget ID (deduplicated, with click_center)"
            },
            "max_results": {
                "type": "integer",
                "description": "Maximum number of results (default: 5 for text search, 50 otherwise)"
            },
            "full": {
                "type": "boolean",
                "description": "Return raw widget data instead of compact results (default: false)",
                "default": False
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
async def handle_find_widget(arguments: dict) -> dict:
    """Canonical widget inspection: search, group scan, container children, or summary."""
    text = arguments.get("text")
    specific_group = arguments.get("group")
    container_id = arguments.get("container_id")
    full = arguments.get("full", False)
    timeout_ms = arguments.get("timeout_ms", 3000)
    account_id = arguments.get("account_id")

    # Validate inputs
    if not isinstance(timeout_ms, (int, float)) or timeout_ms < 100 or timeout_ms > 30000:
        timeout_ms = 3000
    if specific_group is not None:
        if not isinstance(specific_group, int) or specific_group < 0 or specific_group > 65535:
            return {"success": False, "error": f"Invalid group: must be 0-65535, got {specific_group}"}

    # Build command with optional --group flag and text filter (server-side filtering)
    parts = ["SCAN_WIDGETS"]
    if specific_group is not None:
        parts.append(f"--group {specific_group}")
    if text:
        parts.append(text)
    command = " ".join(parts)

    response = await send_command_with_response(command, timeout_ms, account_id)

    if response.get("status") != "success":
        return {
            "success": False,
            "error": response.get("error", "Failed to scan widgets"),
            "raw_response": response
        }

    widgets = response.get("result", {}).get("widgets", [])

    # Container-children mode (absorbs debug_widget_children)
    if container_id is not None:
        children = []
        for w in widgets:
            if w.get("id") == container_id:
                bounds = w.get("bounds", {})
                actions = w.get("actions", [])
                w_text = w.get("text") or w.get("name") or w.get("itemName") or ""
                if bounds and (actions or w_text):
                    children.append({
                        "text": w_text[:30] if w_text else None,
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
        children.sort(key=lambda c: (c["bounds"]["y"] or 0, c["bounds"]["x"] or 0))
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
            "total_widgets_scanned": len(widgets),
            "children": unique_children
        }

    groups_found = sorted({w["group"] for w in widgets if "group" in w})

    # Raw mode (absorbs scan_widgets)
    if full:
        max_results = arguments.get("max_results", 50)
        result = {
            "success": True,
            "widgets": widgets[:max_results],
            "count": len(widgets),
            "truncated": len(widgets) > max_results,
            "filtered_by": text,
            "groups_found": groups_found,
        }
        if specific_group is not None:
            result["scanned_group"] = specific_group
        return result

    # Unfiltered summary mode (absorbs no-arg scan_widgets)
    MAX_INLINE_WIDGETS = 50
    if not text and specific_group is None and len(widgets) > MAX_INLINE_WIDGETS:
        return {
            "success": True,
            "count": len(widgets),
            "groups_found": groups_found,
            "truncated": True,
            "widgets": widgets[:20],  # Sample
            "hint": f"Large result ({len(widgets)} widgets). Full data in /tmp/manny_widgets.json. Use find_widget(text='...') for filtered searches.",
            "file": "/tmp/manny_widgets.json"
        }

    # Compact results (canonical find_widget behavior)
    max_results = arguments.get("max_results", 5 if text else 50)
    matches = []
    for w in widgets:
        widget_text = w.get("itemName") or w.get("text") or w.get("name") or ""
        bounds_obj = w.get("bounds", {})
        entry = {
            "widget_id": w.get("id"),
            "text": widget_text[:50] + "..." if len(widget_text) > 50 else widget_text,
            "bounds": {
                "x": bounds_obj.get("x"),
                "y": bounds_obj.get("y"),
                "width": bounds_obj.get("width"),
                "height": bounds_obj.get("height")
            },
            "actions": w.get("actions", [])[:3]
        }
        if w.get("itemId"):
            entry["itemId"] = w.get("itemId")
            entry["itemQuantity"] = w.get("itemQuantity")
        matches.append(entry)
        if len(matches) >= max_results:
            break

    result = {
        "success": True,
        "query": text,
        "found": len(matches),
        "total_widgets_scanned": len(widgets),
        "groups_found": groups_found,
        "widgets": matches
    }
    if specific_group is not None:
        result["scanned_group"] = specific_group
    return result


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


@registry.register({
    "name": "click_widget",
    "description": """[Widgets] Canonical widget click tool. ONE tool for all UI clicking - finds the target and clicks it atomically via the plugin (CLICK_AT / CLICK_WIDGET / CLICK_DIALOGUE / CLICK_CONTINUE).

Usage modes:
- click_widget(text="Raw lobster")                       - find widget by text/name/item and click it (fresh bounds, atomic CLICK_AT)
- click_widget(text="Raw lobster", action="Drop")        - use a specific action when the ID-based fallback is needed
- click_widget(action="+10%")                            - find widget BY action text and click it (GE/shop buttons)
- click_widget(widget_id=17694735)                       - click a widget by packed ID
- click_widget(widget_id=..., bounds={x,y,width,height}) - click virtual widgets (deposit box/shop items) at given bounds
- click_widget(dialogue_option="Yes.")                   - click a dialogue option (plugin-side CLICK_DIALOGUE matching)
- click_widget(continue_dialogue=true)                   - click 'Click here to continue'

container_id restricts text/action search to children of that container.
Use find_widget() first when you need to inspect what is clickable.""",
    "inputSchema": {
        "type": "object",
        "properties": {
            "text": {
                "type": "string",
                "description": "Find widget by text/name/item name and click it (fresh bounds at click time)"
            },
            "action": {
                "type": "string",
                "description": "Action text to match (e.g., '+10%', 'Buy 1', 'Drop'). Alone: finds widget by action. With text: used for the CLICK_WIDGET fallback."
            },
            "widget_id": {
                "type": "integer",
                "description": "The packed widget ID to click directly (e.g., 17694735)"
            },
            "bounds": {
                "type": "object",
                "description": "Optional bounds for virtual widgets sharing a container ID: {x, y, width, height}. Clicks center of bounds.",
                "properties": {
                    "x": {"type": "integer"},
                    "y": {"type": "integer"},
                    "width": {"type": "integer"},
                    "height": {"type": "integer"}
                }
            },
            "container_id": {
                "type": "integer",
                "description": "Only match widgets with this container/parent ID during text/action search"
            },
            "dialogue_option": {
                "type": "string",
                "description": "Click a dialogue option by text using the plugin's CLICK_DIALOGUE matching"
            },
            "continue_dialogue": {
                "type": "boolean",
                "description": "Click the 'Click here to continue' button (default: false)",
                "default": False
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
        }
    }
})
async def handle_click_widget(arguments: dict) -> dict:
    """Canonical widget click: by text, action, widget ID, bounds, or dialogue."""
    text = arguments.get("text")
    action = arguments.get("action")
    widget_id = arguments.get("widget_id")
    bounds = arguments.get("bounds")
    container_id = arguments.get("container_id")
    dialogue_option = arguments.get("dialogue_option")
    continue_dialogue = arguments.get("continue_dialogue", False)
    timeout_ms = arguments.get("timeout_ms", 5000)
    account_id = arguments.get("account_id")

    # Mode 1: continue button (absorbs click_continue)
    if continue_dialogue:
        response = await send_command_with_response("CLICK_CONTINUE", timeout_ms, account_id)
        if response.get("status") == "success":
            return {"success": True,
                    "message": response.get("result", {}).get("message", "Clicked continue")}
        return {"success": False,
                "error": response.get("error", "No continue button found")}

    # Mode 2: dialogue option (absorbs click_text / CLICK_DIALOGUE path)
    if dialogue_option:
        response = await send_command_with_response(f'CLICK_DIALOGUE {dialogue_option}', timeout_ms, account_id)
        if response.get("status") == "success":
            return {"success": True, "clicked": dialogue_option,
                    "message": response.get("result", {}).get("message", "Clicked")}
        return {"success": False,
                "error": response.get("error", "Failed to click dialogue option"),
                "searched_for": dialogue_option}

    # Mode 3: direct widget ID (action, if given, is used in CLICK_WIDGET)
    if widget_id and not text:
        # Bounds provided: atomic CLICK_AT at center (virtual widgets)
        if bounds and all(k in bounds for k in ("x", "y", "width", "height")):
            click_x = bounds["x"] + bounds["width"] // 2
            click_y = bounds["y"] + bounds["height"] // 2
            click_response = await send_command_with_response(
                f"CLICK_AT {click_x} {click_y}", timeout_ms, account_id)
            if click_response.get("status") == "success":
                return {"success": True, "widget_id": widget_id,
                        "click_position": {"x": click_x, "y": click_y},
                        "bounds": bounds,
                        "message": f"Clicked virtual widget at ({click_x}, {click_y})"}
            return {"success": False, "widget_id": widget_id,
                    "error": click_response.get("error", "Failed to click widget")}

        # Plain CLICK_WIDGET (optionally with action)
        cmd = f'CLICK_WIDGET {widget_id} "{action}"' if action else f"CLICK_WIDGET {widget_id}"
        response = await send_command_with_response(cmd, timeout_ms, account_id)
        if response.get("status") == "success":
            return {"success": True, "widget_id": widget_id,
                    "message": response.get("result", {}).get("message", "Widget clicked")}
        return {"success": False, "widget_id": widget_id,
                "error": response.get("error", "Failed to click widget")}

    # Mode 4: search + click (absorbs find_and_click_widget / click_widget_by_action)
    if not text and not action:
        return {"success": False,
                "error": "Provide one of: text, action, widget_id, dialogue_option, continue_dialogue"}

    scan_term = text or action
    response = await send_command_with_response(f"SCAN_WIDGETS {scan_term}", timeout_ms, account_id)
    if response.get("status") != "success":
        return {"success": False,
                "error": response.get("error", "Failed to scan widgets")}

    widgets = response.get("result", {}).get("widgets", [])

    match = None
    if text:
        # Text search: first match (server-side filtering already applied)
        for w in widgets:
            if container_id is not None and w.get("id") != container_id:
                continue
            match = w
            break
    else:
        # Action search: match on widget actions
        for w in widgets:
            for widget_action in w.get("actions", []) or []:
                if widget_action and (action in widget_action or action == widget_action):
                    if container_id is not None and w.get("id") != container_id:
                        continue
                    match = w
                    break
            if match:
                break

    if not match:
        return {"success": False,
                "error": f"No widget found matching '{scan_term}'",
                "searched_for": scan_term,
                "widgets_scanned": len(widgets)}

    matched_id = match.get("id")
    matched_text = match.get("itemName") or match.get("text") or match.get("name") or ""
    matched_actions = match.get("actions", [])
    matched_bounds = match.get("bounds", {})

    has_valid_bounds = (matched_bounds
                        and all(k in matched_bounds for k in ("x", "y", "width", "height"))
                        and matched_bounds.get("x", -1) >= 0)

    if has_valid_bounds:
        # Atomic CLICK_AT at fresh bounds center - the canonical, race-free path.
        # Required for widgets that share a container ID (inventory, GE, shops).
        click_x = matched_bounds["x"] + matched_bounds["width"] // 2
        click_y = matched_bounds["y"] + matched_bounds["height"] // 2
        click_response = await send_command_with_response(
            f"CLICK_AT {click_x} {click_y}", timeout_ms, account_id)
    else:
        # Fallback: CLICK_WIDGET by ID with an action if available
        if action:
            cmd = f'CLICK_WIDGET {matched_id} "{action}"'
        elif matched_actions:
            cmd = f'CLICK_WIDGET {matched_id} "{matched_actions[0]}"'
        else:
            cmd = f'CLICK_WIDGET {matched_id}'
        click_response = await send_command_with_response(cmd, timeout_ms, account_id)

    if click_response.get("status") == "success":
        result = {"success": True, "clicked": True,
                  "widget_id": matched_id,
                  "text": matched_text[:50] if matched_text else None,
                  "action_used": action or (matched_actions[0] if matched_actions and not has_valid_bounds else None),
                  "bounds": matched_bounds}
        if has_valid_bounds:
            result["clicked_at"] = {"x": matched_bounds["x"] + matched_bounds["width"] // 2,
                                    "y": matched_bounds["y"] + matched_bounds["height"] // 2}
        return result
    return {"success": False,
            "error": click_response.get("error", "Failed to click widget"),
            "widget_id": matched_id,
            "widget_found": True}


async def handle_click_text(arguments: dict) -> dict:
    """Back-compat shim (old click_text tool): dialogue-option click via canonical click_widget."""
    return await handle_click_widget({
        "dialogue_option": arguments.get("text", ""),
        "timeout_ms": arguments.get("timeout_ms", 3000),
        "account_id": arguments.get("account_id"),
    })


@registry.register({
    "name": "query_nearby",
    "description": """[Routine Building] Query nearby NPCs, objects, and ground items with their available actions.

Returns lists of NPCs, objects, and ground items within range, including their names,
distances, and available right-click actions. Useful for discovering what can be interacted with.

Ground items include:
- Dropped items on the ground
- Items displayed on tables/shelves (scenery items)
- Spawned items (like wine of zamorak)

NAMED TILE-OBJECT SEARCH: pass object_name to search ALL TileObject types by name
(GameObject, WallObject for doors/gates/fences, DecorativeObject, GroundObject, GroundItem).
Essential for finding doors and items on tables. Results appear under "tile_objects".""",
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
            "object_name": {
                "type": "string",
                "description": "Search ALL TileObject types (incl. WallObjects like doors/gates) for this name. Skips the NPC/object/ground-item scans unless include_* is set explicitly."
            },
            "max_distance": {
                "type": "integer",
                "description": "Max search distance in tiles for object_name search (default: 15)",
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
        }
    }
})
async def handle_query_nearby(arguments: dict) -> dict:
    """Query nearby NPCs, objects, and ground items (plus named tile-object search)."""
    object_name = arguments.get("object_name")
    # When doing a named tile-object search, skip the broad scans unless explicitly requested
    default_include = object_name is None
    include_npcs = arguments.get("include_npcs", default_include)
    include_objects = arguments.get("include_objects", default_include)
    include_ground_items = arguments.get("include_ground_items", default_include)
    name_filter = arguments.get("name_filter")
    timeout_ms = arguments.get("timeout_ms", 3000)
    account_id = arguments.get("account_id")

    result = {
        "success": True,
        "npcs": [],
        "objects": [],
        "ground_items": []
    }

    # Named tile-object search (absorbs scan_tile_objects): all TileObject types incl. WallObjects
    if object_name:
        tile_result = await handle_scan_tile_objects({
            "object_name": object_name,
            "max_distance": arguments.get("max_distance", 15),
            "timeout_ms": timeout_ms,
            "account_id": account_id,
        })
        if tile_result.get("success"):
            result["tile_objects"] = tile_result.get("objects", [])
        else:
            result["tile_objects"] = []
            result["tile_objects_error"] = tile_result.get("error")

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
    "name": "list_commands",
    "description": """[Discovery] Canonical command-discovery tool for manny plugin commands.

- list_commands()                        - live command list from the running plugin (LIST_COMMANDS), grouped by category
- list_commands(category="banking")      - filter by category
- list_commands(search="FISH")           - search the static source-derived command index (works without a running client)
- list_commands(command="BANK_WITHDRAW") - usage examples and notes for a single command

The live query automatically falls back to the static source index when no client is running.""",
    "inputSchema": {
        "type": "object",
        "properties": {
            "category": {
                "type": "string",
                "description": "Optional: filter by category (fishing, mining, banking, navigation, dialogue, query, etc.)"
            },
            "search": {
                "type": "string",
                "description": "Search term - uses the static source-derived command index (no client needed)"
            },
            "command": {
                "type": "string",
                "description": "Get usage examples for one specific command (e.g., 'BANK_WITHDRAW')"
            },
            "timeout_ms": {
                "type": "integer",
                "description": "Timeout in milliseconds for the live query (default: 3000)",
                "default": 3000
            },
            "account_id": {
                "type": "string",
                "description": "Account ID for multi-client (optional, defaults to 'default')"
            }
        }
    }
})
async def handle_list_commands(arguments: dict) -> dict:
    """Canonical command discovery: live plugin list, static index search, or per-command examples."""
    timeout_ms = arguments.get("timeout_ms", 3000)
    category_filter = arguments.get("category")
    search = arguments.get("search")
    command = arguments.get("command")
    account_id = arguments.get("account_id")

    # Per-command examples (absorbs get_command_examples)
    if command:
        from manny_tools import get_command_examples
        return get_command_examples(command=command)

    # Static source index (absorbs list_available_commands)
    def _static_list():
        from manny_tools import list_available_commands
        return list_available_commands(
            plugin_dir=str(config.plugin_directory),
            category=category_filter or "all",
            search=search,
        )

    if search:
        return _static_list()

    # Live plugin query (absorbs list_plugin_commands), static fallback when client is down
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
                    "source": "plugin",
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
            return {
                "success": True,
                "source": "plugin",
                "total_commands": commands_data.get("total_commands", 0),
                "categories": commands_data.get("categories", []),
                "commands": commands_data.get("commands", {})
            }
    else:
        # Client down or timed out - fall back to the static source index
        static = _static_list()
        if isinstance(static, dict):
            static.setdefault("source", "static_fallback")
            static["live_error"] = response.get("error", "Live LIST_COMMANDS failed")
        return static


# Back-compat alias for callers that used the old name (not a registered tool)
handle_list_plugin_commands = handle_list_commands


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


# ============================================================================
# DEFECT-26: plugin-side kill-loop blocking + guard
# ----------------------------------------------------------------------------
# KILL_LOOP / KILL_LOOP_CONFIG route through the Java KillLoopCommand, which
# runs a detached, long-lived loop on a background thread. Its IPC response
# returns EARLY — sub-operations inside the loop (equip, drop, cook, bury) emit
# rid-correlated responses, so ``transport.send_command`` matches the FIRST one
# and reports "success" ~seconds in while the loop grinds on for hours. That is
# exactly why run_routine.py used to report "1 loop SUCCESS" and exit, leaving
# the grind UNMANAGED (the watchdog, attached to the run pid, then exits too).
#
# The plugin now exports ``active_loop`` into the state JSON
# (GameEngine.StateExporter <- KillLoopCommand.getActiveLoopStatus). We poll it
# to block until the loop actually finishes, so run_routine (and the watchdog
# attached to it) stay alive for the loop's real duration.
# ============================================================================
KILL_LOOP_COMMANDS = {"KILL_LOOP", "KILL_LOOP_CONFIG"}


def _active_loop_from_state(state: dict):
    """Return the active_loop dict from a state snapshot, or None if absent."""
    if not isinstance(state, dict):
        return None
    al = state.get("active_loop")
    return al if isinstance(al, dict) else None


def _loop_progress_key(active_loop: dict):
    """A tuple that advances while the loop makes progress (kills/iteration)."""
    if not isinstance(active_loop, dict):
        return None
    return (active_loop.get("kills"), active_loop.get("iteration"))


async def check_active_loop(account_id: str = None):
    """Return the account's active_loop status dict, or None if no loop is active.

    Used as the pre-launch guard (refuse to start a routine over a running kill
    loop) and by callers that need to know whether a grind is already in flight.
    """
    state = await get_game_state(account_id)
    return _active_loop_from_state(state)


async def _await_active_loop_finish(account_id: str, timeout_ms: int,
                                    appear_grace_ms: int = 45000,
                                    poll_interval_ms: int = 3000,
                                    stall_ms: int = 300000) -> dict:
    """Block until the plugin-side kill loop (state.active_loop) finishes.

    Poll semantics:
    - Wait up to ``appear_grace_ms`` for active_loop to APPEAR (loop spins up).
      If it never appears, assume the plugin doesn't export the signal (old
      build) or the loop already ended, and return without blocking further
      (backward-compatible — the caller falls back to the command response).
    - Once seen, block WHILE active_loop is present until one of:
        * it clears            -> {"finished": True}
        * ``timeout_ms`` elapse -> {"timeout": True}
        * kills/iteration stop advancing for ``stall_ms`` -> {"stalled": True}
    """
    interval = max(0.5, poll_interval_ms / 1000.0)
    overall_deadline = time.time() + max(0, timeout_ms) / 1000.0
    appear_deadline = time.time() + max(0, appear_grace_ms) / 1000.0

    # Phase 1: wait for the loop to appear (it may take a few seconds to spin up).
    active = await check_active_loop(account_id)
    while active is None:
        if time.time() >= appear_deadline or time.time() >= overall_deadline:
            _routine_logger.info(
                "[KILL-LOOP-WAIT] No active_loop signal appeared within %dms — "
                "not blocking (old plugin build or loop already finished).",
                appear_grace_ms)
            return {"waited": False, "reason": "no_active_loop_signal"}
        await asyncio.sleep(interval)
        active = await check_active_loop(account_id)

    _routine_logger.info("[KILL-LOOP-WAIT] active_loop detected (%s) — blocking until it finishes.",
                         active)

    # Phase 2: block while the loop is present.
    last_progress = _loop_progress_key(active)
    last_progress_ts = time.time()
    while True:
        if time.time() >= overall_deadline:
            _routine_logger.warning(
                "[KILL-LOOP-WAIT] step timeout_ms (%dms) elapsed while loop still active.",
                timeout_ms)
            return {"waited": True, "timeout": True, "last_active_loop": active}

        await asyncio.sleep(interval)
        active = await check_active_loop(account_id)
        if active is None:
            _routine_logger.info("[KILL-LOOP-WAIT] active_loop cleared — loop finished.")
            return {"waited": True, "finished": True}

        progress = _loop_progress_key(active)
        if progress != last_progress:
            last_progress = progress
            last_progress_ts = time.time()
        elif (time.time() - last_progress_ts) * 1000.0 >= stall_ms:
            _routine_logger.warning(
                "[KILL-LOOP-WAIT] loop stalled (no kill progress for %dms): %s",
                stall_ms, active)
            return {"waited": True, "stalled": True, "last_active_loop": active}


# NOTE: intentionally NOT a registered MCP tool. Routines are executed via
# ./run_routine.py (the canonical path), which calls this handler directly.
async def handle_execute_routine(arguments: dict) -> dict:
    """Execute a YAML routine step by step with inner/outer loop support."""
    routine_path = arguments.get("routine_path")
    start_step = arguments.get("start_step", 1)
    max_loops = arguments.get("max_loops", 10000)
    account_id = arguments.get("account_id")
    force = arguments.get("force", False)

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

    # DEFECT-26 pre-launch guard: refuse to start over a running kill loop.
    # Launching a routine (esp. one containing KILL_LOOP) while the client is
    # already grinding a loop used to spawn a SECOND concurrent loop thread
    # (dual-loop collision). Bail loudly unless --force was passed.
    already_active = await check_active_loop(account_id)
    if already_active is not None:
        msg = (f"A kill loop is already active on account "
               f"'{account_id or 'default'}' (active_loop={already_active}). "
               f"Refusing to start a routine over it (would risk a concurrent "
               f"dual-loop). Stop the loop first, or re-run with --force.")
        if not force:
            _routine_logger.error("[ROUTINE] %s", msg)
            return {"success": False, "error": msg,
                    "active_loop": already_active, "guard": "kill_loop_active"}
        _routine_logger.warning("[ROUTINE] --force set: starting despite active kill loop (%s)",
                                already_active)

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
            if health.get("category") == "disconnect":
                # Legitimate disconnect/login gap, NOT a crash -- relogin
                # instead, and don't burn a restart-budget attempt on it.
                _routine_logger.warning(
                    "[ROUTINE] Client disconnected (status=%s), attempting relogin...",
                    health.get("connection_status"))
                recovered = await _attempt_relogin(account_id)
                if recovered:
                    results["errors"].append(
                        f"Recovered from disconnect (status={health.get('connection_status')})")
                    continue  # Retry this outer loop iteration; current_step_idx untouched
                results["success"] = False
                results["disconnect_detected"] = True
                results["crash_error"] = health["error"]
                results["stale_seconds"] = health.get("stale_seconds")
                return results

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
                    if health.get("category") == "disconnect":
                        # Legitimate disconnect/login gap, NOT a crash --
                        # relogin instead of burning a restart-budget attempt.
                        _routine_logger.warning(
                            "[ROUTINE] Client disconnected at step %s (status=%s), attempting relogin...",
                            step_id, health.get("connection_status"))
                        recovered = await _attempt_relogin(account_id)
                        if recovered:
                            results["errors"].append(
                                f"Recovered from disconnect at step {step_id} "
                                f"(status={health.get('connection_status')})")
                            break  # Break inner step loop, re-enter outer loop; current_step_idx untouched
                        results["success"] = False
                        results["disconnect_detected"] = True
                        results["crash_error"] = health["error"]
                        results["crashed_at_step"] = step_id
                        return results

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
    """Execute a routine step, honoring `repeat: N` (default 1).

    `repeat: N` runs the step's action up to N times sequentially. When the
    step also has an `await_condition`, a satisfied condition short-circuits
    the remaining repeats -- this is the evident intent behind every real
    usage (e.g. routines/quests/restless_ghost.yaml step 8: `CLICK_CONTINUE`
    repeat=5 with await_condition="has_item:Ghostspeak amulet" -- "keep
    clicking continue up to 5 times until the item is obtained/dialogue
    ends"; routines/quests/sheep_shearer.yaml step 6: `INTERACT_NPC` repeat=20
    with await_condition="inventory_count:>=20" -- "keep shearing until the
    inventory is full, or give up after 20 tries"). Without an
    await_condition (the more common case -- imp_catcher.yaml,
    death_escape.yaml) it's a fixed-count blind repeat, e.g. "click continue
    5 times" through a known dialogue chain.
    """
    # repeat_until: run the step's action until a predicate holds (or a safety
    # cap is hit). Distinct from the numeric `repeat` below. Used by the tutorial
    # routines as `repeat_until: "no_dialogue"` to press through multi-screen
    # dialogues. Handled by its own loop so the two forms never interleave.
    if step.get('repeat_until'):
        return await _execute_repeat_until(step, step_idx, routine_config, account_id)

    try:
        repeat = max(1, int(step.get('repeat', 1)))
    except (TypeError, ValueError):
        repeat = 1

    await_condition = step.get('await_condition')

    step_result = await _execute_step_once(step, step_idx, routine_config, account_id)
    attempts = 1

    while attempts < repeat:
        if await_condition and step_result.get("success"):
            break  # Condition already satisfied -- short-circuit remaining repeats.
        attempts += 1
        step_result = await _execute_step_once(step, step_idx, routine_config, account_id)

    step_result["attempts"] = attempts
    if repeat > 1:
        step_result["repeat"] = repeat
    return step_result


# repeat_until safety defaults. Overridable per-step (`max_iterations`,
# `repeat_until_timeout_ms`) or via the routine `config:` block
# (`repeat_until_max_iterations`, `repeat_until_timeout_ms`).
DEFAULT_REPEAT_UNTIL_MAX_ITERATIONS = 25   # tutorial dialogues run 3-12 screens; headroom
DEFAULT_REPEAT_UNTIL_TIMEOUT_MS = 2000     # per-iteration wait for state to reflect the predicate
DEFAULT_REPEAT_UNTIL_POLL_INTERVAL_MS = 250


async def _predicate_satisfied(condition: tuple, account_id: str) -> bool:
    """Evaluate a parsed condition tuple against current game state (read-only)."""
    from . import monitoring
    state = await get_game_state(account_id)
    if not state:
        return False
    return monitoring._check_condition(state, condition)


async def _poll_predicate(condition: tuple, account_id: str,
                          timeout_ms: int, poll_interval_ms: int) -> bool:
    """Poll game state until `condition` holds or the timeout elapses.

    Checks at least once (so a zero timeout is a single immediate check).
    Returns True as soon as the predicate holds, else False at timeout.
    """
    deadline = time.time() + max(0, timeout_ms) / 1000.0
    interval = max(0.05, poll_interval_ms / 1000.0)
    while True:
        if await _predicate_satisfied(condition, account_id):
            return True
        if time.time() >= deadline:
            return False
        await asyncio.sleep(interval)


async def _execute_repeat_until(step: dict, step_idx: int,
                                routine_config: dict, account_id: str) -> dict:
    """Execute a step repeatedly until a predicate holds (or a safety cap is hit).

    Tutorial routines use `repeat_until: "no_dialogue"` (press space/continue
    through a multi-screen dialogue: keep advancing WHILE a dialogue is open,
    stop the instant it closes). Semantics are check-FIRST -- a
    `while not satisfied` loop -- so if the predicate already holds we run the
    action ZERO times and never fire a stray space press after a dialogue has
    already closed.

    Safety: capped at `max_iterations` iterations, and each iteration waits at
    most `repeat_until_timeout_ms` for the state to reflect the predicate before
    pressing again (if the dialogue merely advanced to the next screen the wait
    expires and we loop). Hitting the cap is logged and returns success=False.
    """
    from . import monitoring

    step_id = step.get('id', step_idx + 1)
    predicate = str(step.get('repeat_until'))
    if routine_config:
        predicate = interpolate_variables(predicate, routine_config)

    cfg = routine_config or {}

    def _int(value, default):
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    max_iterations = max(1, _int(
        step.get('max_iterations',
                 cfg.get('repeat_until_max_iterations', DEFAULT_REPEAT_UNTIL_MAX_ITERATIONS)),
        DEFAULT_REPEAT_UNTIL_MAX_ITERATIONS))
    iter_timeout_ms = _int(
        step.get('repeat_until_timeout_ms',
                 cfg.get('repeat_until_timeout_ms', DEFAULT_REPEAT_UNTIL_TIMEOUT_MS)),
        DEFAULT_REPEAT_UNTIL_TIMEOUT_MS)
    poll_interval_ms = _int(
        step.get('poll_interval_ms', cfg.get('poll_interval_ms', DEFAULT_REPEAT_UNTIL_POLL_INTERVAL_MS)),
        DEFAULT_REPEAT_UNTIL_POLL_INTERVAL_MS)

    base_result = {
        "step_id": step_id,
        "phase": step.get('phase'),
        "action": step.get('action'),
        "mcp_tool": step.get('mcp_tool'),
        "repeat_until": predicate,
        "max_iterations": max_iterations,
    }

    # Parse the predicate once (fail fast on a bad/unsupported condition).
    try:
        condition = monitoring._parse_condition(predicate)
    except ValueError as e:
        base_result["success"] = False
        base_result["error"] = f"Invalid repeat_until condition: {e}"
        base_result["iterations"] = 0
        return base_result

    iterations = 0
    satisfied = await _predicate_satisfied(condition, account_id)
    last_action_result = None

    while not satisfied and iterations < max_iterations:
        iterations += 1
        last_action_result = await _execute_step_once(step, step_idx, routine_config, account_id)
        satisfied = await _poll_predicate(condition, account_id, iter_timeout_ms, poll_interval_ms)

    if not satisfied and iterations >= max_iterations:
        _routine_logger.warning(
            "[ROUTINE] repeat_until '%s' hit max-iteration cap (%d) at step %s "
            "without becoming satisfied.", predicate, max_iterations, step_id)

    base_result["iterations"] = iterations
    base_result["satisfied"] = satisfied
    base_result["success"] = satisfied
    if not satisfied:
        base_result["error"] = (
            f"repeat_until '{predicate}' not satisfied after {iterations} "
            f"iteration(s) (cap {max_iterations})")
    if last_action_result is not None:
        base_result["last_action_result"] = last_action_result
    return base_result


async def _execute_step_once(step: dict, step_idx: int, routine_config: dict, account_id: str) -> dict:
    """Execute a single iteration of a routine step's action and return the result."""
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

        # DEFECT-26: KILL_LOOP/KILL_LOOP_CONFIG responses return EARLY (see the
        # KILL_LOOP_COMMANDS note above). Block on the plugin's exported
        # active_loop signal until the loop truly finishes, so run_routine — and
        # the watchdog attached to its pid — stay alive for the whole grind.
        action_word = (action or "").strip().upper()
        if action_word in KILL_LOOP_COMMANDS:
            loop_wait = await _await_active_loop_finish(account_id, timeout_ms)
            step_result["loop_wait"] = loop_wait
            if loop_wait.get("finished"):
                step_result["success"] = True
            elif loop_wait.get("timeout") or loop_wait.get("stalled"):
                # Loop outlived the step timeout or stopped advancing: surface it
                # as a step failure so the runner/ledger don't call it clean.
                step_result["success"] = False
                step_result["error"] = (
                    "kill loop did not finish within timeout_ms"
                    if loop_wait.get("timeout") else
                    "kill loop stalled (no kill progress)")
            # else: no active_loop signal ever appeared -> keep the early
            # response's success verdict (backward-compatible fallback).

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
        elif mcp_tool in ("click_widget", "find_and_click_widget"):
            # find_and_click_widget is the legacy name; click_widget is canonical
            result = await handle_click_widget(mcp_args)
        elif mcp_tool == "click_text":
            # Backed by handle_click_text -> handle_click_widget(dialogue_option=...)
            # -> the plugin's CLICK_DIALOGUE. Section 10 uses this to advance/answer
            # dialogue (click_text: {text: "continue" | "Yes" | "No"}).
            result = await handle_click_text(mcp_args)
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

    # no_item_in_bank:ItemName - No more of item in bank (can't withdraw).
    #
    # The game state snapshot (get_game_state / the state file) carries
    # inventory, equipment, skills, location, dialogue, etc. but NEVER bank
    # contents -- a bank snapshot would require sending a QUERY_BANK command
    # through the plugin transport, which this pure state-file reader
    # deliberately does not do. Silently returning False was actively
    # dangerous: a loop gating on `no_item_in_bank:X` would behave as if the
    # bank still held the item forever and never stop. Until bank-snapshot
    # infrastructure exists, fail LOUDLY rather than guess.
    if condition.startswith("no_item_in_bank:"):
        item_name = condition[len("no_item_in_bank:"):].strip()
        msg = (
            f"Unimplemented stop condition 'no_item_in_bank:{item_name}': bank "
            "contents are not present in the game state snapshot, so this "
            "condition cannot be evaluated without new QUERY_BANK infrastructure. "
            "Refusing to silently return False. Use an inventory-based condition "
            "(e.g. 'no_item:<name>' after a withdraw) or add bank-snapshot support."
        )
        _routine_logger.error("[ROUTINE] %s", msg)
        raise NotImplementedError(msg)

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


async def _get_connection_status(account_id: str = None, timeout_ms: int = 5000) -> dict:
    """
    Query GET_GAME_STATE over the existing command IPC channel -- the
    discriminator between "disconnected/logging-in" and "genuinely stuck".

    The plugin's GET_GAME_STATE command (manny_src/utility/commands/
    GetGameStateCommand.java) reads client.getGameState() via a ClientThread
    round-trip that is NOT gated by the GameTick stream, so it keeps
    responding even when the state-file writer (which IS GameTick-driven)
    has legitimately frozen during CONNECTION_LOST/LOGIN_SCREEN/character
    creation. See journals/ENGINE_DISCONNECT_RECOVERY_SPEC.md section (b).

    Returns:
        dict with:
        - responded: bool - False if the command channel itself didn't
          answer (timeout / no send_command_with_response wired up) --
          the one case state-file staleness is still a valid signal.
        - status: "LOGGED_IN" | "LOGGING_IN" | "DISCONNECTED" | "UNKNOWN" | None
        - is_connected: bool | None
        - can_send_commands: bool | None
        - has_local_player: bool | None
    """
    not_responded = {
        "responded": False, "status": None,
        "is_connected": None, "can_send_commands": None, "has_local_player": None,
    }

    if send_command_with_response is None:
        return not_responded

    try:
        response = await send_command_with_response("GET_GAME_STATE", timeout_ms, account_id)
    except Exception:
        return not_responded

    if not isinstance(response, dict) or response.get("timeout") or response.get("status") != "success":
        return not_responded

    result = response.get("result") or {}
    return {
        "responded": True,
        "status": result.get("status"),
        "is_connected": result.get("isConnected"),
        "can_send_commands": result.get("canSendCommands"),
        "has_local_player": result.get("hasLocalPlayer"),
    }


async def check_client_health(account_id: str = None, max_stale_seconds: float = 60) -> dict:
    """
    Check if the client is alive, discriminating a genuine crash/freeze from
    a legitimate disconnect/login/loading gap.

    State-file mtime staleness ALONE is never sufficient to declare a crash:
    the state writer (StateExporter.onGameTick) legitimately stops updating
    during CONNECTION_LOST/LOGIN_SCREEN/character creation because GameTick
    itself stops firing then -- that is expected behavior, not a hang. This
    queries GET_GAME_STATE (see _get_connection_status) as the authoritative
    signal and only falls back to mtime staleness when that command itself
    doesn't respond (the one case staleness alone is still valid: the whole
    command channel being dead does mean the client crashed).
    See journals/ENGINE_DISCONNECT_RECOVERY_SPEC.md sections (a)/(b).

    Returns:
        dict with:
        - alive: bool - True if client appears healthy
        - category: "healthy" | "disconnect" | "crash"
        - stale_seconds: float | None - How old the state file is
        - connection_status: str | None - raw GET_GAME_STATE status field
        - error: str - Error message if not alive
    """
    state_file = config.get_state_file(account_id) if config else "/tmp/manny_state.json"

    state_file_exists = True
    age_seconds = None
    try:
        stat = os.stat(state_file)
        age_seconds = time.time() - stat.st_mtime
    except FileNotFoundError:
        state_file_exists = False
    except Exception as e:
        return {
            "alive": False,
            "category": "crash",
            "stale_seconds": None,
            "connection_status": None,
            "error": f"Error checking state file: {e}",
        }

    conn = await _get_connection_status(account_id)

    if not conn["responded"]:
        # Command channel itself didn't answer -- this is the one case plain
        # mtime staleness is still a valid enough signal that the client is
        # actually dead (not merely disconnected from the game world).
        if not state_file_exists:
            return {
                "alive": False,
                "category": "crash",
                "stale_seconds": None,
                "connection_status": None,
                "error": "State file not found and command channel unresponsive - client not running",
            }
        return {
            "alive": False,
            "category": "crash",
            "stale_seconds": age_seconds,
            "connection_status": None,
            "error": (f"Command channel unresponsive and state file stale for "
                      f"{age_seconds:.0f}s - client likely crashed"),
        }

    status = conn["status"]

    if status == "LOGGED_IN" and conn["can_send_commands"]:
        if age_seconds is not None and age_seconds > max_stale_seconds:
            # Fully connected per GET_GAME_STATE, yet the state-file writer
            # is stuck -- a genuine freeze, not a disconnect.
            return {
                "alive": False,
                "category": "crash",
                "stale_seconds": age_seconds,
                "connection_status": status,
                "error": (f"State file stale for {age_seconds:.0f}s (>{max_stale_seconds}s) "
                          f"while LOGGED_IN - plugin likely frozen"),
            }
        return {
            "alive": True,
            "category": "healthy",
            "stale_seconds": age_seconds,
            "connection_status": status,
        }

    if status in ("LOGGING_IN", "DISCONNECTED", "UNKNOWN"):
        # Legitimate disconnect/login/character-creation gap -- NOT a crash.
        # The state file freezing here is expected; recover via relogin and
        # do not count it against the crash-restart budget.
        return {
            "alive": False,
            "category": "disconnect",
            "stale_seconds": age_seconds,
            "connection_status": status,
            "error": f"Client disconnected (GET_GAME_STATE status={status})",
        }

    # status == "LOGGED_IN" but canSendCommands is False (e.g. mid-LOADING,
    # no local player yet) -- treat conservatively as disconnect-first.
    return {
        "alive": False,
        "category": "disconnect",
        "stale_seconds": age_seconds,
        "connection_status": status,
        "error": f"Client not ready (GET_GAME_STATE status={status}, canSendCommands=False)",
    }


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
        await asyncio.to_thread(runelite_manager.stop_instance, account_id)
    except Exception as e:
        _routine_logger.warning("[AUTO-RESTART] Stop failed (may already be dead): %s", e)

    await asyncio.sleep(3)  # Brief cooldown before restart

    _routine_logger.info("[AUTO-RESTART] Starting client for account '%s'...", account_id or "default")
    try:
        # start_instance returns {"pid": ..., "status": ...} on success (no
        # "success" key) and {"success": False, ...} on failure -- checking
        # "success" here would always default-False on the success path and
        # report every restart as failed. Same fix already applied in
        # monitoring.py's auto_reconnect/restart_if_frozen (Wave 5 P4).
        start_result = await asyncio.to_thread(runelite_manager.start_instance, account_id)
        if not start_result.get("pid"):
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


async def _attempt_relogin(account_id: str = None, max_wait_seconds: float = 60) -> bool:
    """
    Recover from a detected disconnect (check_client_health category
    "disconnect") WITHOUT a full client relaunch.

    Reuses the existing primitives rather than reinventing them:
    1. monitoring.py's ``_xdotool_click`` to dismiss the "You were
       disconnected" Ok dialog -- works even when the command channel is
       unresponsive, since xdotool talks to X directly, not IPC.
    2. The plugin's existing ``LOGIN`` command (PlayerHelpers.java, "LOGIN"
       case) to trigger the login-button click routine.
    3. Polls ``_get_connection_status`` (GET_GAME_STATE) until
       status == "LOGGED_IN" and canSendCommands, bounded by
       ``max_wait_seconds`` (mirrors monitoring.auto_reconnect's default 60s).
    4. Escalates to ``_auto_restart_client`` (full relaunch via
       runelite_manager) only if the bounded wait expires -- this is the
       same escalation target the freeze/crash path already uses, so restart
       accounting stays in one place.

    Deliberately does NOT touch current_step_idx -- a mere relogin doesn't
    change in-world position/inventory, so the routine should resume at the
    step it was on (same as the existing restart path already does).
    See journals/ENGINE_DISCONNECT_RECOVERY_SPEC.md section (c).

    Returns True if the client is confirmed reachable again (either via
    relogin or the restart escalation), False otherwise.
    """
    from . import monitoring as monitoring_mod

    display = None
    try:
        from ..session_manager import session_manager
        default_account = config.default_account if config else None
        display = session_manager.get_display_for_account(account_id or default_account)
    except Exception:
        pass
    if not display:
        display = config.display if config else ":2"

    # Step 1: best-effort dismiss of the disconnect dialog's Ok button.
    try:
        await asyncio.to_thread(monitoring_mod._xdotool_click, 770, 604, display)
    except Exception as e:
        _routine_logger.debug("[RELOGIN] xdotool click failed (non-fatal): %s", e)

    await asyncio.sleep(1.0)

    # Step 2: trigger the plugin's own LOGIN command (clicks Play button).
    # Best-effort -- if the command channel is still unresponsive this is a
    # no-op and the poll loop below will simply keep waiting.
    if send_command_with_response is not None:
        try:
            await send_command_with_response("LOGIN", 5000, account_id)
        except Exception as e:
            _routine_logger.debug("[RELOGIN] LOGIN command failed (non-fatal): %s", e)

    # Step 3: poll GET_GAME_STATE until reconnected, bounded wait.
    _routine_logger.info("[RELOGIN] Waiting up to %ds for reconnect...", max_wait_seconds)
    start = time.time()
    while (time.time() - start) < max_wait_seconds:
        await asyncio.sleep(3)
        conn = await _get_connection_status(account_id)
        if conn["responded"] and conn["status"] == "LOGGED_IN" and conn["can_send_commands"]:
            _routine_logger.info("[RELOGIN] Reconnected after %.0fs", time.time() - start)
            return True

    # Step 4: relogin didn't resolve it within the bounded wait -- escalate
    # to the same full-restart path the freeze/crash branch uses.
    _routine_logger.warning(
        "[RELOGIN] Did not recover within %ds, escalating to full restart", max_wait_seconds)
    return await _auto_restart_client(account_id)

