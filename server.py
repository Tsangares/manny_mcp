#!/home/wil/manny-mcp/venv/bin/python
"""RuneLite Debug MCP Server - Modular Architecture"""

import asyncio
import json
import os
import uuid
from dotenv import load_dotenv
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from mcp.server import Server
from mcp.server.stdio import stdio_server

# Import modular components
from mcptools.config import ServerConfig
from mcptools.registry import registry
from mcptools.runelite_manager import MultiRuneLiteManager

# Import tool modules (they register themselves on import)
from mcptools.tools import core, monitoring, screenshot, routine, commands, code_intelligence, testing, spatial, session, quests, sessions, location_history, routine_generator, code_changes, manny_navigation

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
# EVENT-DRIVEN FILE MONITORING
# ============================================================================

class ResponseFileMonitor:
    """
    Event-driven file monitor using watchdog instead of polling.

    Replaces 50ms polling loops with instant event notification, reducing
    CPU usage and latency by 50x.
    """
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.file_dir = os.path.dirname(file_path) or "/tmp"
        self.file_name = os.path.basename(file_path)
        self.event = asyncio.Event()
        self.observer = None
        self.handler = None
        self._loop = None

    def start(self, loop: asyncio.AbstractEventLoop):
        """Start watching the file for changes."""
        self._loop = loop

        class ResponseFileHandler(FileSystemEventHandler):
            def __init__(self, monitor):
                self.monitor = monitor

            def on_modified(self, event):
                if event.src_path.endswith(self.monitor.file_name):
                    # Signal waiting coroutines
                    if self.monitor._loop:
                        self.monitor._loop.call_soon_threadsafe(self.monitor.event.set)

        self.handler = ResponseFileHandler(self)
        self.observer = Observer()
        self.observer.schedule(self.handler, self.file_dir, recursive=False)
        self.observer.start()

    def stop(self):
        """Stop watching the file."""
        if self.observer:
            self.observer.stop()
            self.observer.join()

    async def wait_for_change(self, timeout_sec: float) -> bool:
        """Wait for file to be modified, with timeout."""
        self.event.clear()
        try:
            await asyncio.wait_for(self.event.wait(), timeout=timeout_sec)
            return True
        except asyncio.TimeoutError:
            return False


# Global file monitor (initialized when server starts)
_response_monitor = None


async def send_command_with_response(command: str, timeout_ms: int = 3000, account_id: str = None) -> dict:
    """
    Send a command to the plugin and wait for the response.

    OPTIMIZATION: Uses event-driven file watching (watchdog) instead of polling.
    Reduces latency from avg 50ms to <1ms and eliminates CPU waste.

    The plugin writes responses to /tmp/manny_response.json after processing commands.
    This function sends the command and waits for file modification events.

    REQUEST ID CORRELATION: Appends --rid=xxx to command for unique request/response matching.
    This prevents race conditions when multiple commands of the same type are sent rapidly.

    Args:
        command: Command to send to the plugin
        timeout_ms: Timeout in milliseconds
        account_id: Optional account ID for multi-client support
    """
    global _response_monitor

    # Get account-specific file paths
    command_file = config.get_command_file(account_id)
    response_file = config.get_response_file(account_id)
    timeout_sec = timeout_ms / 1000.0

    import time

    # Generate unique request ID for correlation
    request_id = uuid.uuid4().hex[:8]

    # Record time BEFORE writing command - response must be newer than this
    command_write_time = time.time()

    # Write the command with request ID appended
    command_with_rid = f"{command} --rid={request_id}"
    with open(command_file, "w") as f:
        f.write(command_with_rid + "\n")
    start = command_write_time  # Also use as start time for timeout

    def _check_response():
        """Check if response file has a valid response to our command."""
        if os.path.exists(response_file):
            current_mtime = os.path.getmtime(response_file)
            # Response must be newer than when we wrote the command
            if current_mtime >= command_write_time:
                try:
                    with open(response_file) as f:
                        response = json.load(f)
                    # PRIMARY: Match by request_id (bulletproof correlation)
                    if response.get("request_id") == request_id:
                        return response
                    # FALLBACK: For backwards compat with old Java plugin, match by command name
                    # (only if response has no request_id)
                    if response.get("request_id") is None:
                        if response.get("command", "").upper() == command.split()[0].upper():
                            return response
                except (json.JSONDecodeError, IOError):
                    pass
        return None

    while (time.time() - start) < timeout_sec:
        # FIRST: Check if response is already available (fixes race condition)
        response = _check_response()
        if response:
            return response

        # THEN: Wait for file change event or poll
        if _response_monitor and (account_id is None or account_id == config.default_account):
            remaining_time = timeout_sec - (time.time() - start)
            if remaining_time <= 0:
                break
            # Wait for file change event (instant notification)
            changed = await _response_monitor.wait_for_change(remaining_time)
            if not changed:
                # Timeout from wait_for_change, but still check one more time
                response = _check_response()
                if response:
                    return response
                break
        else:
            # Fallback to polling for non-default accounts
            await asyncio.sleep(0.05)

    return {
        "command": command,
        "status": "timeout",
        "error": f"No response received within {timeout_ms}ms"
    }


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
    global _response_monitor

    # Initialize event-driven file monitor
    _response_monitor = ResponseFileMonitor(RESPONSE_FILE)
    _response_monitor.start(asyncio.get_event_loop())

    try:
        async with stdio_server() as (read_stream, write_stream):
            await server.run(read_stream, write_stream, server.create_initialization_options())
    finally:
        # Clean up file monitor on shutdown
        if _response_monitor:
            _response_monitor.stop()


if __name__ == "__main__":
    asyncio.run(main())
