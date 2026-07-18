"""In-process MCP tool client.

Talks directly to the shared ``mcptools.registry.ToolRegistry`` (via
``mcptools.bootstrap.init_registry``) instead of spawning a second copy of
``server.py`` as a stdio subprocess.

SINGLE-SERVER RULE: there must be exactly one control plane writing commands
to the plugin's file-IPC (see ``mcptools/transport.py`` and
``mcptools/bootstrap.py``). Before this fix, the driver spawned its own
``server.py`` subprocess purely to get a tool-calling interface -- a second,
fully independent process capable of racing the "real" MCP server (the one
Claude Code talks to) for writes to the same ``/tmp/manny_*_command.txt`` /
``*_response.json`` files. That's exactly the kind of divergent-copy bug
``mcptools/transport.py`` was written to eliminate for command I/O
specifically; spawning a whole second server process reintroduced the same
class of problem one level up. Do NOT reintroduce a subprocess spawn here --
if the driver needs a new tool, register it once in ``mcptools/tools/`` (like
every other tool) and it's automatically available in-process via the
registry, with no second process involved.
"""
import base64
import logging
from typing import Any, Optional

from mcp.types import ImageContent, TextContent

from mcptools import bootstrap
from mcptools.registry import registry

logger = logging.getLogger("manny_driver.mcp")


class MCPClient:
    """In-process facade over the shared ToolRegistry.

    Keeps the same public surface the old stdio-subprocess client had
    (``connect``/``disconnect``/``get_tools``/``call_tool``/async context
    manager) so callers (``manny_driver/agent.py``, ``manny_driver/__main__.py``)
    and the tool-name filtering in ``manny_driver/tools.py`` are unaffected.
    """

    def __init__(self, server_script: str = "server.py", server_cwd: Optional[str] = None):
        # `server_script` is accepted (but unused) purely for backward-compatible
        # construction -- there is no subprocess to launch anymore.
        self.server_script = server_script
        self.server_cwd = server_cwd
        self._tools: list = []
        self._connected = False

    async def connect(self):
        """Wire the shared tool registry in-process (no subprocess spawn)."""
        bootstrap.init_registry(project_root=self.server_cwd)
        self._tools = registry.list_tools()
        self._connected = True
        logger.info(f"MCP (in-process) connected: {len(self._tools)} tools available")

    async def disconnect(self):
        """No-op: there is no subprocess or stream to tear down."""
        self._connected = False
        self._tools = []

    def get_tools(self) -> list:
        """Return the raw MCP tool list."""
        return self._tools

    async def call_tool(self, name: str, arguments: dict[str, Any] = None) -> str:
        """Call a tool via the shared registry and return the result as a string.

        Returns text content from the tool result. Images are described
        but not returned (the driver works primarily with text).
        """
        if not self._connected:
            raise RuntimeError("MCP client not connected")

        arguments = arguments or {}
        content = await registry.call_tool(name, arguments)

        # Parse content blocks (same shapes the old stdio session returned).
        parts = []
        for block in content:
            if isinstance(block, TextContent):
                parts.append(block.text)
            elif isinstance(block, ImageContent):
                try:
                    size = len(base64.b64decode(block.data))
                except Exception:
                    size = len(block.data)
                parts.append(f"[Image: {block.mimeType}, {size} bytes]")
            else:
                parts.append(str(block))

        return "\n".join(parts)

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, *args):
        await self.disconnect()
