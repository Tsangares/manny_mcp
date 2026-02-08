"""MCP stdio client - connects to server.py as a subprocess."""
import asyncio
import json
import logging
import sys
from contextlib import AsyncExitStack
from pathlib import Path
from typing import Any, Optional

from mcp import ClientSession
from mcp.client.stdio import stdio_client, StdioServerParameters
from mcp.types import TextContent, ImageContent

logger = logging.getLogger("manny_driver.mcp")


class MCPClient:
    """Manages an MCP connection to the server.py subprocess."""

    def __init__(self, server_script: str = "server.py", server_cwd: Optional[str] = None):
        self.server_script = server_script
        self.server_cwd = server_cwd or str(Path(__file__).parent.parent)
        self.session: Optional[ClientSession] = None
        self._tools: list = []
        self._exit_stack: Optional[AsyncExitStack] = None

    async def connect(self):
        """Start the MCP server subprocess and establish a session."""
        server_params = StdioServerParameters(
            command=sys.executable,
            args=[self.server_script],
            cwd=self.server_cwd,
        )

        # Use AsyncExitStack to manage nested context managers
        self._exit_stack = AsyncExitStack()
        await self._exit_stack.__aenter__()

        # Start stdio client
        read_stream, write_stream = await self._exit_stack.enter_async_context(
            stdio_client(server_params)
        )

        # Create and initialize session
        self.session = await self._exit_stack.enter_async_context(
            ClientSession(read_stream, write_stream)
        )
        await self.session.initialize()

        # Cache tool list
        result = await self.session.list_tools()
        self._tools = result.tools
        logger.info(f"MCP connected: {len(self._tools)} tools available")

    async def disconnect(self):
        """Shut down the MCP session and server process."""
        if self._exit_stack:
            try:
                await self._exit_stack.__aexit__(None, None, None)
            except Exception as e:
                logger.debug(f"MCP disconnect: {e}")
            self._exit_stack = None
        self.session = None
        self._tools = []

    def get_tools(self) -> list:
        """Return the raw MCP tool list."""
        return self._tools

    async def call_tool(self, name: str, arguments: dict[str, Any] = None) -> str:
        """Call an MCP tool and return the result as a string.

        Returns text content from the tool result. Images are described
        but not returned (the driver works primarily with text).
        """
        if not self.session:
            raise RuntimeError("MCP client not connected")

        arguments = arguments or {}
        result = await self.session.call_tool(name, arguments)

        # Parse content blocks
        parts = []
        for content in result.content:
            if isinstance(content, TextContent):
                parts.append(content.text)
            elif isinstance(content, ImageContent):
                parts.append(f"[Image: {content.mimeType}, {len(content.data)} bytes]")
            else:
                parts.append(str(content))

        return "\n".join(parts)

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, *args):
        await self.disconnect()
