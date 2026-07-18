"""Tests for `mcp_tool: "click_text"` dispatch in routine._execute_mcp_tool_step.

Section 10 (10_prayer_magic.yaml) advances/answers dialogue via
`mcp_tool: "click_text"` with `args: {text: "continue" | "Yes" | "No"}`.
This was previously unwired ("Unknown mcp_tool"). It is now backed by
handle_click_text -> handle_click_widget(dialogue_option=...) -> CLICK_DIALOGUE.
"""
from unittest.mock import AsyncMock

import pytest

from mcptools.tools import routine


@pytest.mark.asyncio
class TestClickTextDispatch:
    async def test_click_text_is_wired(self, monkeypatch):
        mock_click = AsyncMock(return_value={"success": True, "clicked": "continue"})
        monkeypatch.setattr(routine, "handle_click_text", mock_click)

        step = {"id": 19, "mcp_tool": "click_text", "args": {"text": "continue"}}
        result = await routine._execute_mcp_tool_step(step, "click_text", None)

        assert mock_click.await_count == 1
        called_args = mock_click.await_args[0][0]
        assert called_args["text"] == "continue"
        assert result["success"] is True

    async def test_click_text_passes_account_id(self, monkeypatch):
        mock_click = AsyncMock(return_value={"success": True})
        monkeypatch.setattr(routine, "handle_click_text", mock_click)

        step = {"id": 26, "mcp_tool": "click_text", "args": {"text": "No"}}
        await routine._execute_mcp_tool_step(step, "click_text", "main")

        called_args = mock_click.await_args[0][0]
        assert called_args["account_id"] == "main"
        assert called_args["text"] == "No"

    async def test_click_text_failure_propagates(self, monkeypatch):
        mock_click = AsyncMock(return_value={"success": False, "error": "no dialogue option"})
        monkeypatch.setattr(routine, "handle_click_text", mock_click)

        step = {"id": 22, "mcp_tool": "click_text", "args": {"text": "continue"}}
        result = await routine._execute_mcp_tool_step(step, "click_text", None)

        assert result["success"] is False
        assert result["error"] == "no dialogue option"

    async def test_unknown_mcp_tool_still_errors(self):
        """Regression: an unrecognized mcp_tool still returns a clear error."""
        step = {"id": 1, "mcp_tool": "does_not_exist", "args": {}}
        result = await routine._execute_mcp_tool_step(step, "does_not_exist", None)

        assert result["success"] is False
        assert "Unknown mcp_tool" in result["error"]

    async def test_routes_through_execute_single_step(self, monkeypatch):
        """A full step with mcp_tool click_text dispatches to the wired handler."""
        mock_click = AsyncMock(return_value={"success": True})
        monkeypatch.setattr(routine, "handle_click_text", mock_click)

        step = {"id": 25, "mcp_tool": "click_text", "args": {"text": "continue"}}
        result = await routine._execute_single_step(step, 0, {}, None)

        assert mock_click.await_count == 1
        assert result["success"] is True
