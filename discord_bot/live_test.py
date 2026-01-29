#!/usr/bin/env python3
"""
Live test harness - tests LLM reasoning with REAL MCP tools.

Unlike test_harness.py which mocks tools, this actually executes commands
against a running RuneLite client.

Usage:
    # Single command
    ./venv/bin/python discord_bot/live_test.py "Kill chickens until level 15 attack"

    # Interactive mode
    ./venv/bin/python discord_bot/live_test.py

    # With specific account
    ./venv/bin/python discord_bot/live_test.py --account superape "What's my status?"
"""
import asyncio
import argparse
import json
import sys
import os
import logging
from pathlib import Path
from typing import Dict, Any, List

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load .env file
def load_dotenv():
    env_file = Path(__file__).parent.parent / ".env"
    if env_file.exists():
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    if key not in os.environ:
                        os.environ[key] = value

load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(name)s] %(levelname)s: %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger("live_test")

# Reduce noise from other loggers
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

from discord_bot.llm_client import LLMClient
from discord_bot.agentic_loop import AgenticLoopWithRecovery

# Import MCP tool modules
from mcptools.tools import monitoring, commands, screenshot, routine, spatial
from mcptools.runelite_manager import RuneLiteManager
from mcptools.config import ServerConfig


def initialize_mcp_tools(config: ServerConfig, manager: RuneLiteManager):
    """Initialize MCP tool dependencies (same as server.py)."""

    def send_command_with_response(cmd: str, account_id: str = None, timeout_ms: int = 5000):
        """Blocking wrapper for send_command used by routine tools."""
        import asyncio
        return asyncio.get_event_loop().run_until_complete(
            commands.handle_send_command({
                "command": cmd,
                "account_id": account_id,
                "timeout_ms": timeout_ms
            })
        )

    monitoring.set_dependencies(manager, config)
    commands.set_dependencies(send_command_with_response, config)
    screenshot.set_dependencies(manager, config, None)
    routine.set_dependencies(send_command_with_response, config)
    spatial.set_dependencies(send_command_with_response, config)


# Tool handler imports (after set_dependencies is defined)
from mcptools.tools.monitoring import (
    handle_get_game_state,
    handle_check_health,
    handle_get_logs,
    handle_auto_reconnect
)
from mcptools.tools.commands import handle_send_command
from mcptools.tools.screenshot import _take_screenshot as take_screenshot
from mcptools.tools.routine import handle_query_nearby, handle_scan_tile_objects


class LiveToolExecutor:
    """Executes real MCP tools."""

    _initialized = False

    def __init__(self, account_id: str = "default"):
        self.account_id = account_id
        self.config = ServerConfig.load()
        self._manager = RuneLiteManager(self.config)
        self.tool_calls: List[Dict] = []

        # Initialize MCP tool dependencies once
        if not LiveToolExecutor._initialized:
            initialize_mcp_tools(self.config, self._manager)
            LiveToolExecutor._initialized = True

    async def execute(self, tool_name: str, arguments: dict) -> dict:
        """Execute a tool and track the call."""
        logger.info(f"🔧 TOOL: {tool_name}({json.dumps(arguments, default=str)[:200]})")

        self.tool_calls.append({
            "tool": tool_name,
            "args": arguments
        })

        try:
            result = await self._execute(tool_name, arguments)
            # Truncate large results for logging
            result_str = json.dumps(result, default=str)
            if len(result_str) > 500:
                logger.info(f"   → {result_str[:500]}...")
            else:
                logger.info(f"   → {result_str}")
            return result
        except Exception as e:
            logger.error(f"   → ERROR: {e}")
            return {"error": str(e)}

    async def _execute(self, tool_name: str, arguments: dict) -> dict:
        """Route tool to appropriate handler."""

        if tool_name == "get_game_state":
            return await handle_get_game_state({
                "account_id": self.account_id,
                "fields": arguments.get("fields")
            })

        elif tool_name == "check_health":
            return await handle_check_health({
                "account_id": self.account_id
            })

        elif tool_name == "send_command":
            return await handle_send_command({
                "command": arguments.get("command", ""),
                "account_id": self.account_id
            })

        elif tool_name == "get_logs":
            return await handle_get_logs({
                "account_id": self.account_id,
                "level": arguments.get("level", "WARN"),
                "since_seconds": arguments.get("since_seconds", 30),
                "grep": arguments.get("grep"),
                "max_lines": 50
            })

        elif tool_name == "query_nearby":
            return await handle_query_nearby({
                "account_id": self.account_id,
                "include_npcs": arguments.get("include_npcs", True),
                "include_objects": arguments.get("include_objects", True),
                "include_ground_items": arguments.get("include_ground_items", True),
                "name_filter": arguments.get("name_filter"),
                "timeout_ms": arguments.get("timeout_ms", 3000)
            })

        elif tool_name == "scan_tile_objects":
            return await handle_scan_tile_objects({
                "account_id": self.account_id,
                "object_name": arguments.get("object_name"),
                "radius": arguments.get("radius", 15),
                "timeout_ms": arguments.get("timeout_ms", 3000)
            })

        elif tool_name == "get_screenshot":
            result = take_screenshot(account_id=self.account_id)
            if result.get("success"):
                return {"success": True, "path": result.get("path")}
            return result

        elif tool_name == "start_runelite":
            result = await asyncio.to_thread(
                self._manager.start_instance,
                self.account_id
            )
            return result

        elif tool_name == "stop_runelite":
            return self._manager.stop_instance(self.account_id)

        elif tool_name == "auto_reconnect":
            return await handle_auto_reconnect({
                "account_id": self.account_id
            })

        elif tool_name == "lookup_location":
            from discord_bot.locations import find_location, get_goto_command
            location_query = arguments.get("location", "")
            loc = find_location(location_query)
            if loc:
                return {
                    "found": True,
                    "name": loc["name"],
                    "x": loc["x"],
                    "y": loc["y"],
                    "plane": loc["plane"],
                    "goto_command": get_goto_command(location_query)
                }
            return {"found": False, "error": f"Location '{location_query}' not found"}

        elif tool_name == "list_plugin_commands":
            # Just return a hint - full list is too large
            return {
                "hint": "Use KILL_LOOP <npc> <food|none> for combat, GOTO <x> <y> <plane> for navigation, FISH for fishing",
                "categories": ["combat", "navigation", "skilling", "banking", "interaction"]
            }

        elif tool_name == "get_command_help":
            cmd = arguments.get("command", "").upper()
            help_text = {
                "KILL_LOOP": "KILL_LOOP <npc_name> <food_name|none> [max_kills] - Kill NPCs continuously",
                "GOTO": "GOTO <x> <y> <plane> - Navigate to coordinates",
                "FISH": "FISH - Fish at nearest spot with equipment in inventory",
                "BANK_OPEN": "BANK_OPEN - Open nearest bank",
                "INTERACT_NPC": "INTERACT_NPC <npc_name> <action> - Interact with NPC"
            }
            return {"command": cmd, "help": help_text.get(cmd, "Unknown command")}

        else:
            return {"error": f"Unknown tool: {tool_name}"}


async def run_single(message: str, account_id: str, provider: str = "ollama"):
    """Run a single message through the LLM with real tools."""

    print(f"\n{'='*60}")
    print(f"USER: {message}")
    print(f"{'='*60}\n")

    # Initialize components
    llm = LLMClient(provider=provider)
    executor = LiveToolExecutor(account_id=account_id)

    loop = AgenticLoopWithRecovery(
        llm_client=llm,
        tool_executor=executor.execute,
        max_iterations=10
    )

    # Run the agentic loop
    result = await loop.process(message=message, history=[])

    # Print results
    print(f"\n{'='*60}")
    print("RESULT")
    print(f"{'='*60}")
    print(f"\n💬 RESPONSE: {result.response}\n")

    if executor.tool_calls:
        print(f"{'='*60}")
        print("TOOL CALLS")
        print(f"{'='*60}\n")

        observations = []
        actions = []

        for tc in executor.tool_calls:
            tool = tc["tool"]
            if tool in ["get_game_state", "check_health", "get_logs", "query_nearby", "scan_tile_objects", "get_screenshot"]:
                observations.append(tc)
            else:
                actions.append(tc)

        if observations:
            print("📊 OBSERVATIONS:")
            for tc in observations:
                args_str = json.dumps(tc["args"], default=str) if tc["args"] else ""
                print(f"  • {tc['tool']}({args_str[:100]})")

        if actions:
            print("\n⚡ ACTIONS:")
            for tc in actions:
                if tc["tool"] == "send_command":
                    print(f"  • send_command: {tc['args'].get('command', '')}")
                else:
                    args_str = json.dumps(tc["args"], default=str) if tc["args"] else ""
                    print(f"  • {tc['tool']}({args_str[:100]})")

        observed_before_acting = len(observations) > 0 or len(actions) == 0
        print(f"\n✅ Observed before acting: {'YES' if observed_before_acting else 'NO'}")
        print(f"📝 Total tool calls: {len(executor.tool_calls)}")

        commands_sent = [tc for tc in actions if tc["tool"] == "send_command"]
        print(f"🎮 Commands sent: {len(commands_sent)}")

    return result


async def interactive_mode(account_id: str, provider: str = "ollama"):
    """Interactive REPL for testing."""

    print(f"""
{'='*60}
LIVE TEST HARNESS - Interactive Mode
{'='*60}
Account: {account_id}
Provider: {provider}

Commands:
  /quit    - Exit
  /account <id> - Switch account
  /help    - Show this help

Enter messages to send to the LLM.
{'='*60}
""")

    history = []

    while True:
        try:
            user_input = input("\n> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting...")
            break

        if not user_input:
            continue

        if user_input == "/quit":
            break
        elif user_input == "/help":
            print("Commands: /quit, /account <id>, /help")
            continue
        elif user_input.startswith("/account "):
            account_id = user_input.split(" ", 1)[1]
            print(f"Switched to account: {account_id}")
            continue

        result = await run_single(user_input, account_id, provider)

        # Add to history
        history.append({"role": "user", "content": user_input})
        history.append({"role": "assistant", "content": result.response})


def main():
    parser = argparse.ArgumentParser(description="Live test harness for LLM + MCP tools")
    parser.add_argument("message", nargs="?", help="Message to send (interactive mode if omitted)")
    parser.add_argument("--account", "-a", default="superape", help="Account ID (default: superape)")
    parser.add_argument("--provider", "-p", default="ollama", help="LLM provider: ollama, gemini, claude")

    args = parser.parse_args()

    if args.message:
        asyncio.run(run_single(args.message, args.account, args.provider))
    else:
        asyncio.run(interactive_mode(args.account, args.provider))


if __name__ == "__main__":
    main()
