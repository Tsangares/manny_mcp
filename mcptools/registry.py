"""
Tool registry pattern for MCP server.
Eliminates dual definition of tool schemas + handlers.
"""
from typing import Callable, Dict, Any, List
from mcp.types import Tool, TextContent, ImageContent
import json


class ToolRegistry:
    """
    Central registry for MCP tools.

    Tools register themselves using the @register decorator, which co-locates
    the tool schema and handler function. This eliminates the need to maintain
    tool definitions in two separate places (list_tools() and call_tool()).

    Example:
        @registry.register({
            "name": "build_plugin",
            "description": "[RuneLite] Compile the manny plugin",
            "inputSchema": {...}
        })
        async def handle_build_plugin(arguments: dict) -> dict:
            return {"success": True}
    """

    def __init__(self):
        self._tools: Dict[str, Dict[str, Any]] = {}

    def register(self, schema: dict):
        """
        Decorator to register a tool.

        Args:
            schema: Tool schema dict with name, description, inputSchema

        Returns:
            Decorator function that registers the handler
        """
        def decorator(handler: Callable):
            name = schema["name"]
            self._tools[name] = {
                "schema": Tool(**schema),
                "handler": handler
            }
            return handler
        return decorator

    def list_tools(self) -> List[Tool]:
        """Return all tool schemas for MCP list_tools() endpoint"""
        return [tool["schema"] for tool in self._tools.values()]

    async def call_tool(self, name: str, arguments: dict) -> List[Any]:
        """
        Execute a tool by name.

        Args:
            name: Tool name
            arguments: Tool arguments dict

        Returns:
            List of MCP content objects (TextContent, ImageContent, etc.)
        """
        if name not in self._tools:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]

        handler = self._tools[name]["handler"]
        try:
            result = await handler(arguments)
            # Normalize response format
            if isinstance(result, list):
                # Already in MCP format
                return result
            elif isinstance(result, dict):
                # Convert dict to JSON TextContent
                return [TextContent(type="text", text=json.dumps(result, indent=2))]
            else:
                # Unexpected format
                return [TextContent(type="text", text=str(result))]
        except Exception as e:
            error_result = {"success": False, "error": str(e), "type": type(e).__name__}
            return [TextContent(type="text", text=json.dumps(error_result, indent=2))]

    def get_tool_names(self) -> List[str]:
        """Get list of all registered tool names"""
        return list(self._tools.keys())

    def get_tool_count(self) -> int:
        """Get count of registered tools"""
        return len(self._tools)

    def has_tool(self, name: str) -> bool:
        """Check if a tool is registered"""
        return name in self._tools


# Global registry instance
registry = ToolRegistry()
