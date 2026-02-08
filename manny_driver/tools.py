"""Tool filtering and schema conversion for multiple LLM providers."""
import json
from typing import Any

# Gameplay tools allowlist - only these are exposed to the LLM
GAMEPLAY_TOOLS = {
    # Core observation
    "get_game_state",
    "get_logs",
    "check_health",
    "is_alive",
    "get_screenshot",
    "get_command_response",
    # Commands
    "send_command",
    "send_and_await",
    "kill_command",
    # Spatial awareness
    "query_nearby",
    "scan_tile_objects",
    "get_transitions",
    "scan_environment",
    "get_location_info",
    # Widget / UI
    "find_widget",
    "click_text",
    "click_continue",
    "click_widget_by_action",
    "scan_widgets",
    "get_dialogue",
    "get_chat_messages",
    # Inventory / equipment
    "equip_item",
    "deposit_item",
    "teleport_home",
    # Client management (no start/stop - managed externally)
    "auto_reconnect",
    "restart_if_frozen",
    "stabilize_camera",
    # Routines
    "execute_routine",
    # Discovery
    "list_available_commands",
    "get_command_examples",
    # Quests
    "list_quests",
    "quest_summary",
    "check_quest",
}


def is_gameplay_tool(name: str) -> bool:
    """Check if a tool name is in the gameplay allowlist."""
    return name in GAMEPLAY_TOOLS


def filter_tools(mcp_tools: list) -> list:
    """Filter MCP tools to only gameplay-relevant ones."""
    return [t for t in mcp_tools if t.name in GAMEPLAY_TOOLS]


def mcp_to_anthropic(mcp_tools: list) -> list[dict]:
    """Convert MCP tool schemas to Anthropic's tool format.

    Anthropic expects: {name, description, input_schema}
    """
    tools = []
    for tool in mcp_tools:
        if not is_gameplay_tool(tool.name):
            continue
        schema = tool.inputSchema if hasattr(tool, 'inputSchema') else {}
        # Anthropic uses input_schema (not inputSchema)
        tools.append({
            "name": tool.name,
            "description": tool.description or "",
            "input_schema": schema,
        })
    return tools


def mcp_to_openai(mcp_tools: list) -> list[dict]:
    """Convert MCP tool schemas to OpenAI's function calling format.

    OpenAI expects: {type: "function", function: {name, description, parameters}}
    """
    tools = []
    for tool in mcp_tools:
        if not is_gameplay_tool(tool.name):
            continue
        schema = tool.inputSchema if hasattr(tool, 'inputSchema') else {}
        tools.append({
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description or "",
                "parameters": schema,
            },
        })
    return tools


def mcp_to_gemini(mcp_tools: list) -> list[dict]:
    """Convert MCP tool schemas to Gemini function declaration format.

    Returns raw dicts that the Gemini client will convert to FunctionDeclarations.
    """
    tools = []
    for tool in mcp_tools:
        if not is_gameplay_tool(tool.name):
            continue
        schema = tool.inputSchema if hasattr(tool, 'inputSchema') else {}
        # Clean schema for Gemini (remove unsupported fields)
        properties = {}
        for k, v in schema.get("properties", {}).items():
            prop = {"type": v.get("type", "string").upper()}
            if v.get("description"):
                prop["description"] = v["description"]
            if v.get("type") == "array" and "items" in v:
                prop["items"] = {"type": v["items"].get("type", "string").upper()}
            if v.get("enum"):
                prop["enum"] = v["enum"]
            properties[k] = prop

        tools.append({
            "name": tool.name,
            "description": tool.description or "",
            "parameters": {
                "type": "OBJECT",
                "properties": properties,
                "required": schema.get("required", []),
            },
        })
    return tools


def mcp_to_ollama(mcp_tools: list) -> list[dict]:
    """Convert MCP tool schemas to Ollama tool format.

    Same as OpenAI format (Ollama follows OpenAI's convention).
    """
    return mcp_to_openai(mcp_tools)
