#!/home/wil/Desktop/manny_mcp/venv/bin/python
"""RuneLite Debug MCP Server - Modular Architecture"""

import asyncio
import os

from dotenv import load_dotenv
from mcp.server import Server
from mcp.server.stdio import stdio_server

# Import modular components
from mcptools import transport
from mcptools.config import ServerConfig
from mcptools.registry import registry
from mcptools.runelite_manager import MultiRuneLiteManager

# Import tool modules (they register themselves on import)
from mcptools.tools import (
    code_changes,
    commands,
    core,
    manny_navigation,
    monitoring,
    quests,
    routine,
    screenshot,
    spatial,
)

# Load environment variables (for GEMINI_API_KEY, session credentials)
load_dotenv()

# Try to import Gemini API
try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
    genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))
except ImportError:
    GEMINI_AVAILABLE = False

# Load config
config = ServerConfig.load()

# Response file for plugin command responses
RESPONSE_FILE = config.state_file.replace("state.json", "response.json")
if not RESPONSE_FILE.endswith("response.json"):
    RESPONSE_FILE = "/tmp/manny_response.json"


# ============================================================================
# COMMAND TRANSPORT (delegated to mcptools.transport — the ONE canonical impl)
# ============================================================================

# Reuse the already-loaded config in the transport layer so both share one
# ServerConfig (and one account resolver).
transport.set_config(config)


async def send_command_with_response(command: str, timeout_ms: int = 3000, account_id: str = None) -> dict:
    """
    Send a command to the plugin and wait for the response.

    Thin MCP-facing wrapper over ``transport.send_command`` (the single
    canonical, rid-correlated, atomic-write, watchdog-driven transport). The
    signature and return shape are preserved for downstream tool modules:
    on success it returns the parsed plugin response dict; on timeout it
    returns a dict with ``status == "timeout"``.

    Args:
        command: Command to send to the plugin
        timeout_ms: Timeout in milliseconds
        account_id: Optional account ID for multi-client support
    """
    return await transport.send_command(
        command,
        account_id=account_id,
        await_response=True,
        timeout=timeout_ms / 1000.0,
    )


# ============================================================================
# INITIALIZE COMPONENTS
# ============================================================================

# Initialize multi-client RuneLite manager
runelite_manager = MultiRuneLiteManager(config)

# Inject dependencies into tool modules
core.set_dependencies(runelite_manager, config)
monitoring.set_dependencies(runelite_manager, config)
screenshot.set_dependencies(runelite_manager, config, genai if GEMINI_AVAILABLE else None)
routine.set_dependencies(send_command_with_response, config, runelite_manager)
commands.set_dependencies(send_command_with_response, config)
spatial.set_dependencies(send_command_with_response, config)
code_changes.set_dependencies(config)
manny_navigation.set_dependencies(config)
quests.set_dependencies(runelite_manager, config)


# ============================================================================
# MCP SERVER
# ============================================================================

server = Server("runelite-debug")


@server.list_tools()
async def list_tools():
    """Return all registered tools."""
    return registry.list_tools()


@server.call_tool()
async def call_tool(name: str, arguments: dict):
    """Route all tool calls through the registry."""
    return await registry.call_tool(name, arguments)


async def main():
    """Start the MCP server."""
    # Initialize the event-driven response-file monitor in the transport layer.
    transport.start_response_monitor(asyncio.get_event_loop(), RESPONSE_FILE)

    try:
        async with stdio_server() as (read_stream, write_stream):
            await server.run(read_stream, write_stream, server.create_initialization_options())
    finally:
        # Clean up file monitor on shutdown
        transport.stop_response_monitor()


if __name__ == "__main__":
    asyncio.run(main())
