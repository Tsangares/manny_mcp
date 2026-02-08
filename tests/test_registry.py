"""Tests for mcptools.registry - ToolRegistry registration and dispatch."""
import json
import pytest
from mcp.types import TextContent

from mcptools.registry import ToolRegistry


@pytest.fixture
def reg():
    """Fresh registry for each test."""
    return ToolRegistry()


class TestToolRegistration:
    def test_register_tool(self, reg):
        @reg.register({
            "name": "test_tool",
            "description": "A test tool",
            "inputSchema": {"type": "object", "properties": {}}
        })
        async def handler(arguments):
            return {"ok": True}

        assert reg.has_tool("test_tool")
        assert reg.get_tool_count() == 1

    def test_register_multiple_tools(self, reg):
        for i in range(3):
            @reg.register({
                "name": f"tool_{i}",
                "description": f"Tool {i}",
                "inputSchema": {"type": "object", "properties": {}}
            })
            async def handler(arguments, _i=i):
                return {"id": _i}

        assert reg.get_tool_count() == 3
        assert set(reg.get_tool_names()) == {"tool_0", "tool_1", "tool_2"}

    def test_tool_keyword_registration(self, reg):
        @reg.tool(
            name="kw_tool",
            description="Keyword tool",
            inputSchema={"type": "object", "properties": {}}
        )
        async def handler(arguments):
            return {"ok": True}

        assert reg.has_tool("kw_tool")

    def test_has_tool_false_for_missing(self, reg):
        assert reg.has_tool("nonexistent") is False


class TestToolListing:
    def test_list_tools_returns_tool_objects(self, reg):
        @reg.register({
            "name": "test_tool",
            "description": "Test",
            "inputSchema": {"type": "object", "properties": {}}
        })
        async def handler(arguments):
            return {}

        tools = reg.list_tools()
        assert len(tools) == 1
        assert tools[0].name == "test_tool"
        assert tools[0].description == "Test"


class TestToolExecution:
    @pytest.mark.asyncio
    async def test_call_tool_dict_response(self, reg):
        @reg.register({
            "name": "echo",
            "description": "Echo input",
            "inputSchema": {"type": "object", "properties": {}}
        })
        async def handler(arguments):
            return {"echoed": arguments.get("msg", "")}

        result = await reg.call_tool("echo", {"msg": "hello"})
        assert len(result) == 1
        assert isinstance(result[0], TextContent)
        data = json.loads(result[0].text)
        assert data["echoed"] == "hello"

    @pytest.mark.asyncio
    async def test_call_tool_list_response(self, reg):
        @reg.register({
            "name": "custom",
            "description": "Custom",
            "inputSchema": {"type": "object", "properties": {}}
        })
        async def handler(arguments):
            return [TextContent(type="text", text="custom output")]

        result = await reg.call_tool("custom", {})
        assert result[0].text == "custom output"

    @pytest.mark.asyncio
    async def test_call_unknown_tool(self, reg):
        result = await reg.call_tool("missing", {})
        assert "Unknown tool" in result[0].text

    @pytest.mark.asyncio
    async def test_call_tool_error_handling(self, reg):
        @reg.register({
            "name": "broken",
            "description": "Broken",
            "inputSchema": {"type": "object", "properties": {}}
        })
        async def handler(arguments):
            raise ValueError("something went wrong")

        result = await reg.call_tool("broken", {})
        data = json.loads(result[0].text)
        assert data["success"] is False
        assert "something went wrong" in data["error"]
        assert data["type"] == "ValueError"
