"""
Quest Tracking Tools for MCP Server

Reads quest status directly from the game client via GET_QUEST_STATUS command.
Supports F2P filtering and various status filters.
"""

import json
from typing import Optional, Dict, Any

from ..registry import registry


# Dependencies injected at startup
runelite_manager = None
config = None


def set_dependencies(manager, server_config):
    """Inject dependencies (called from server.py startup)"""
    global runelite_manager, config
    runelite_manager = manager
    config = server_config


async def _send_quest_command(filter_arg: str = "", account_id: str = None) -> Dict[str, Any]:
    """Send GET_QUEST_STATUS command and get response."""
    instance = runelite_manager.get_instance(account_id)
    if not instance:
        return {"error": "RuneLite not running"}

    # Send command
    cmd = f"GET_QUEST_STATUS {filter_arg}".strip()
    instance.send_command(cmd)

    # Wait a bit for command to execute
    import asyncio
    await asyncio.sleep(0.5)

    # Get response
    response = instance.get_command_response()
    if response and response.get("success"):
        # Parse JSON from the success message
        try:
            return json.loads(response.get("message", "{}"))
        except json.JSONDecodeError:
            return {"error": "Failed to parse quest data"}
    else:
        return {"error": response.get("message", "Command failed")}


@registry.register({
    "name": "list_quests",
    "description": "[Quests] List quests from the game with optional filters. Reads directly from game client.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "filter": {
                "type": "string",
                "enum": ["all", "f2p", "p2p", "completed", "in_progress", "not_started"],
                "description": "Filter quests (default: all)",
                "default": "all"
            },
            "account_id": {
                "type": "string",
                "description": "Account ID for multi-client support. Omit for default account."
            }
        }
    }
})
async def handle_list_quests(arguments: dict) -> dict:
    """List quests with filters from game client."""
    filter_arg = arguments.get("filter", "all")
    account_id = arguments.get("account_id")

    result = await _send_quest_command(filter_arg, account_id)

    if "error" in result:
        return result

    # Format output nicely
    quests = result.get("quests", [])
    summary = result.get("summary", {})

    # Group by status for display
    completed = [q for q in quests if q["status"] == "finished"]
    in_progress = [q for q in quests if q["status"] == "in_progress"]
    not_started = [q for q in quests if q["status"] == "not_started"]

    return {
        "filter": filter_arg,
        "summary": summary,
        "completed": [q["name"] for q in completed],
        "in_progress": [q["name"] for q in in_progress],
        "not_started": [q["name"] for q in not_started],
        "total_quests": len(quests)
    }


@registry.register({
    "name": "quest_summary",
    "description": "[Quests] Quick summary of quest progress, optionally filtered to F2P only.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "f2p_only": {
                "type": "boolean",
                "description": "Only show F2P quests (default: true)",
                "default": True
            },
            "account_id": {
                "type": "string",
                "description": "Account ID for multi-client support. Omit for default account."
            }
        }
    }
})
async def handle_quest_summary(arguments: dict) -> dict:
    """Quick quest progress summary."""
    f2p_only = arguments.get("f2p_only", True)
    account_id = arguments.get("account_id")

    filter_arg = "f2p" if f2p_only else "all"
    result = await _send_quest_command(filter_arg, account_id)

    if "error" in result:
        return result

    quests = result.get("quests", [])
    summary = result.get("summary", {})

    completed = [q["name"] for q in quests if q["status"] == "finished"]
    in_progress = [q["name"] for q in quests if q["status"] == "in_progress"]
    not_started = [q["name"] for q in quests if q["status"] == "not_started"]

    return {
        "membership_filter": "F2P" if f2p_only else "All",
        "progress": f"{summary.get('completed', 0)}/{summary.get('total', 0)} completed",
        "completed": {
            "count": len(completed),
            "quests": completed
        },
        "in_progress": {
            "count": len(in_progress),
            "quests": in_progress
        },
        "not_started": {
            "count": len(not_started),
            "quests": not_started[:10] if len(not_started) > 10 else not_started,  # Limit for readability
            "truncated": len(not_started) > 10
        }
    }


@registry.register({
    "name": "check_quest",
    "description": "[Quests] Check the status of a specific quest by name (partial match supported).",
    "inputSchema": {
        "type": "object",
        "properties": {
            "quest_name": {
                "type": "string",
                "description": "Quest name or partial name (e.g., 'restless', 'cook')"
            },
            "account_id": {
                "type": "string",
                "description": "Account ID for multi-client support. Omit for default account."
            }
        },
        "required": ["quest_name"]
    }
})
async def handle_check_quest(arguments: dict) -> dict:
    """Check status of a specific quest."""
    quest_name = arguments.get("quest_name", "")
    account_id = arguments.get("account_id")

    if not quest_name:
        return {"error": "Quest name required"}

    result = await _send_quest_command(quest_name.lower(), account_id)

    if "error" in result:
        return result

    quests = result.get("quests", [])

    if not quests:
        return {
            "found": False,
            "error": f"No quests found matching '{quest_name}'"
        }

    # Return all matches (could be multiple partial matches)
    return {
        "found": True,
        "matches": len(quests),
        "quests": [
            {
                "name": q["name"],
                "status": q["status"],
                "f2p": q.get("f2p", False)
            }
            for q in quests
        ]
    }
