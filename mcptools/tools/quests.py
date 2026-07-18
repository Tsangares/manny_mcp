"""
Quest Tracking Tools for MCP Server

Reads quest status directly from the game client via GET_QUEST_STATUS command.
Supports F2P filtering and various status filters.
"""

import json
from typing import Any, Dict

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
    "description": "[Quests] Canonical quest tool. List quests with filters, or check a specific quest by (partial) name via quest_name. Reads directly from the game client.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "filter": {
                "type": "string",
                "enum": ["all", "f2p", "p2p", "completed", "in_progress", "not_started"],
                "description": "Filter quests (default: all)",
                "default": "all"
            },
            "quest_name": {
                "type": "string",
                "description": "Check a specific quest by name or partial name (e.g., 'restless', 'cook'). Overrides filter."
            },
            "account_id": {
                "type": "string",
                "description": "Account ID for multi-client support. Omit for default account."
            }
        }
    }
})
async def handle_list_quests(arguments: dict) -> dict:
    """Canonical quest tool: list with filters or check one quest (merges quest_summary/check_quest)."""
    quest_name = arguments.get("quest_name")
    account_id = arguments.get("account_id")

    # Specific-quest mode (absorbs check_quest)
    if quest_name:
        result = await _send_quest_command(quest_name.lower(), account_id)
        if "error" in result:
            return result
        quests = result.get("quests", [])
        if not quests:
            return {
                "found": False,
                "error": f"No quests found matching '{quest_name}'"
            }
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

    # List mode (absorbs quest_summary - summary counts are always included)
    filter_arg = arguments.get("filter", "all")
    result = await _send_quest_command(filter_arg, account_id)
    if "error" in result:
        return result

    quests = result.get("quests", [])
    summary = result.get("summary", {})

    completed = [q["name"] for q in quests if q["status"] == "finished"]
    in_progress = [q["name"] for q in quests if q["status"] == "in_progress"]
    not_started = [q["name"] for q in quests if q["status"] == "not_started"]

    return {
        "filter": filter_arg,
        "summary": summary,
        "progress": f"{summary.get('completed', 0)}/{summary.get('total', 0)} completed",
        "completed": completed,
        "in_progress": in_progress,
        "not_started": not_started,
        "total_quests": len(quests)
    }
