#!/usr/bin/env python3
"""
server_with_dashboard.py - MCP server with integrated dashboard

Wraps the original server.py and adds:
1. Dashboard HTTP server on port 8080
2. MCP call tracking (what Claude Code is doing)
3. Automatic state/screenshot polling
4. MJPEG video stream
"""

import asyncio
import json
import os
import threading
import time

import yaml

from dashboard import STATE, DashboardBackgroundTasks, app as dashboard_app
from server import (
    CONFIG,
    Server,
    Tool,
    TextContent,
    ImageContent,
    runelite_manager,
    build_plugin,
    take_screenshot,
    check_client_health,
    analyze_screenshot_with_gemini,
    stdio_server,
)


# Create new MCP server with hooks
server = Server("runelite-debug")


@server.list_tools()
async def list_tools():
    """List available tools - same as original."""
    return [
        Tool(
            name="build_plugin",
            description="Compile the manny RuneLite plugin using Maven.",
            inputSchema={
                "type": "object",
                "properties": {
                    "clean": {"type": "boolean", "description": "Run 'mvn clean' first", "default": True}
                }
            }
        ),
        Tool(
            name="start_runelite",
            description="Start or restart RuneLite with the manny plugin. Runs on display :2.",
            inputSchema={
                "type": "object",
                "properties": {
                    "developer_mode": {"type": "boolean", "default": True}
                }
            }
        ),
        Tool(
            name="stop_runelite",
            description="Stop the managed RuneLite process.",
            inputSchema={"type": "object", "properties": {}}
        ),
        Tool(
            name="get_logs",
            description="Get filtered logs from RuneLite.",
            inputSchema={
                "type": "object",
                "properties": {
                    "level": {"type": "string", "enum": ["DEBUG", "INFO", "WARN", "ERROR", "ALL"], "default": "WARN"},
                    "since_seconds": {"type": "number", "default": 30},
                    "grep": {"type": "string"},
                    "max_lines": {"type": "integer", "default": 100},
                    "plugin_only": {"type": "boolean", "default": True}
                }
            }
        ),
        Tool(
            name="runelite_status",
            description="Check if RuneLite is running.",
            inputSchema={"type": "object", "properties": {}}
        ),
        Tool(
            name="send_command",
            description="Send a command to the manny plugin via /tmp/manny_command.txt",
            inputSchema={
                "type": "object",
                "properties": {"command": {"type": "string"}},
                "required": ["command"]
            }
        ),
        Tool(
            name="get_game_state",
            description="Read current game state from /tmp/manny_state.json",
            inputSchema={"type": "object", "properties": {}}
        ),
        Tool(
            name="get_screenshot",
            description="Capture a screenshot of the RuneLite window.",
            inputSchema={
                "type": "object",
                "properties": {"output_path": {"type": "string"}}
            }
        ),
        Tool(
            name="analyze_screenshot",
            description="Use Gemini AI to analyze a screenshot.",
            inputSchema={
                "type": "object",
                "properties": {
                    "prompt": {"type": "string"},
                    "screenshot_path": {"type": "string"}
                }
            }
        ),
        Tool(
            name="check_health",
            description="Check if RuneLite client is healthy.",
            inputSchema={"type": "object", "properties": {}}
        )
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict):
    """Handle tool calls with dashboard hooks."""
    STATE.start_mcp_call(name)
    start_time = time.time()

    try:
        result = await _handle_tool(name, arguments)
        duration_ms = (time.time() - start_time) * 1000

        result_summary = "ok"
        if result and len(result) > 0:
            first = result[0]
            if hasattr(first, 'text'):
                try:
                    parsed = json.loads(first.text)
                    if isinstance(parsed, dict):
                        if parsed.get('success') is False:
                            result_summary = f"failed: {parsed.get('error', 'unknown')[:50]}"
                        elif 'error' in parsed:
                            result_summary = f"error: {parsed['error'][:50]}"
                except Exception:
                    pass

        STATE.record_mcp_call(name, arguments, result_summary, duration_ms)
        return result

    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        STATE.record_mcp_call(name, arguments, f"exception: {str(e)[:80]}", duration_ms)
        raise


async def _handle_tool(name: str, arguments: dict):
    """Actual tool handling logic."""

    if name == "build_plugin":
        result = build_plugin(clean=arguments.get("clean", True))
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "start_runelite":
        result = runelite_manager.start(developer_mode=arguments.get("developer_mode", True))
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "stop_runelite":
        result = runelite_manager.stop()
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "get_logs":
        result = runelite_manager.get_logs(
            level=arguments.get("level", "WARN"),
            since_seconds=arguments.get("since_seconds", 30),
            grep=arguments.get("grep"),
            max_lines=arguments.get("max_lines", 100),
            plugin_only=arguments.get("plugin_only", True)
        )
        for line in result.get("lines", [])[:10]:
            STATE.add_log(line)
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "runelite_status":
        result = {
            "running": runelite_manager.is_running(),
            "pid": runelite_manager.process.pid if runelite_manager.process else None
        }
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "send_command":
        command = arguments.get("command", "")
        command_file = CONFIG.get("command_file", "/tmp/manny_command.txt")
        try:
            with open(command_file, "w") as f:
                f.write(command + "\n")
            result = {"sent": True, "command": command}
            STATE.set_command(command)
        except Exception as e:
            result = {"sent": False, "error": str(e)}
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "get_game_state":
        state_file = CONFIG.get("state_file", "/tmp/manny_state.json")
        try:
            with open(state_file) as f:
                state = json.load(f)
            result = {"success": True, "state": state}
            if state.get("currentAction"):
                STATE.pending_command = None
        except FileNotFoundError:
            result = {"success": False, "error": "State file not found"}
        except json.JSONDecodeError as e:
            result = {"success": False, "error": f"Invalid JSON: {e}"}
        except Exception as e:
            result = {"success": False, "error": str(e)}
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "get_screenshot":
        result = take_screenshot(arguments.get("output_path"))
        if result["success"]:
            return [
                ImageContent(type="image", data=result["base64"], mimeType="image/png"),
                TextContent(type="text", text=json.dumps({
                    "success": True, "path": result["path"], "display": result["display"]
                }, indent=2))
            ]
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "analyze_screenshot":
        result = analyze_screenshot_with_gemini(
            prompt=arguments.get("prompt"),
            screenshot_path=arguments.get("screenshot_path")
        )
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    elif name == "check_health":
        result = check_client_health()
        STATE.update_health(result)
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    else:
        return [TextContent(type="text", text=f"Unknown tool: {name}")]


def run_dashboard_thread(config: dict, port: int = 8080):
    """Run dashboard in a background thread."""
    tasks = DashboardBackgroundTasks(config)
    tasks.start()

    import uvicorn
    uvicorn.run(dashboard_app, host="0.0.0.0", port=port, log_level="warning", access_log=False)


async def main():
    """Main entry point - starts both MCP server and dashboard."""

    dashboard_thread = threading.Thread(
        target=run_dashboard_thread,
        args=(CONFIG, 8080),
        daemon=True
    )
    dashboard_thread.start()
    print("Dashboard started on http://0.0.0.0:8080", flush=True)

    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
