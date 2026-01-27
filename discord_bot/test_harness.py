#!/usr/bin/env python3
"""
Test harness for the Discord bot's LLM reasoning.

Run the agentic loop with mock MCP tools to see what the LLM decides to do
without needing RuneLite running.

Usage:
    # Interactive mode
    ./venv/bin/python discord_bot/test_harness.py

    # Single test
    ./venv/bin/python discord_bot/test_harness.py "Kill 100 giant frogs"

    # With custom mock state
    ./venv/bin/python discord_bot/test_harness.py --state-file mock_state.json "What's my status?"

    # Record mode - save mock data from live game
    ./venv/bin/python discord_bot/test_harness.py --record

    # Verbose mode - show full tool results
    ./venv/bin/python discord_bot/test_harness.py -v "Go fish at draynor"
"""
import asyncio
import argparse
import json
import sys
import os
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load .env file if it exists
def load_dotenv():
    """Load environment variables from .env file."""
    env_file = Path(__file__).parent.parent / ".env"
    if env_file.exists():
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    # Don't override existing env vars
                    if key not in os.environ:
                        os.environ[key] = value

load_dotenv()

from discord_bot.llm_client import LLMClient
from discord_bot.agentic_loop import AgenticLoopWithRecovery
from discord_bot.models import ActionDecision


# ============================================================================
# Mock Game State - Default values for testing
# ============================================================================

DEFAULT_MOCK_STATE = {
    "location": {"x": 3222, "y": 3218, "plane": 0},  # Lumbridge castle
    "health": {"current": 25, "max": 30},
    "inventory": {
        "used": 5,
        "capacity": 28,
        "items": ["Bronze sword", "Wooden shield", "Coins x150", "Bread", "Logs"]
    },
    "skills": {
        "attack": {"level": 10, "xp": 1154},
        "strength": {"level": 8, "xp": 737},
        "defence": {"level": 7, "xp": 593},
        "hitpoints": {"level": 12, "xp": 1358},
        "fishing": {"level": 5, "xp": 388},
    },
    "equipment": {
        "head": None,
        "body": None,
        "legs": None,
        "weapon": "Bronze sword",
        "shield": "Wooden shield",
    },
    "nearby": {
        "npcs": ["Man", "Woman", "Guard"],
        "objects": ["Door", "Ladder", "Bank booth"],
    },
    "combat": {
        "style": "Accurate",
        "in_combat": False,
    }
}

# Location database for lookup_location mock
MOCK_LOCATIONS = {
    "lumbridge": {"x": 3222, "y": 3218, "plane": 0, "name": "Lumbridge Castle"},
    "lumbridge castle": {"x": 3222, "y": 3218, "plane": 0, "name": "Lumbridge Castle"},
    "draynor": {"x": 3093, "y": 3244, "plane": 0, "name": "Draynor Village"},
    "draynor fishing": {"x": 3087, "y": 3227, "plane": 0, "name": "Draynor Fishing Spot"},
    "draynor bank": {"x": 3093, "y": 3244, "plane": 0, "name": "Draynor Bank"},
    "varrock": {"x": 3213, "y": 3428, "plane": 0, "name": "Varrock Square"},
    "varrock bank": {"x": 3253, "y": 3420, "plane": 0, "name": "Varrock West Bank"},
    "ge": {"x": 3165, "y": 3487, "plane": 0, "name": "Grand Exchange"},
    "grand exchange": {"x": 3165, "y": 3487, "plane": 0, "name": "Grand Exchange"},
    "giant frogs": {"x": 3197, "y": 3169, "plane": 0, "name": "Lumbridge Swamp Frogs"},
    "frogs": {"x": 3197, "y": 3169, "plane": 0, "name": "Lumbridge Swamp Frogs"},
    "cows": {"x": 3253, "y": 3270, "plane": 0, "name": "Lumbridge Cow Field"},
    "chickens": {"x": 3180, "y": 3288, "plane": 0, "name": "Lumbridge Chicken Coop"},
    "goblins": {"x": 3244, "y": 3245, "plane": 0, "name": "Lumbridge Goblins"},
    "al kharid": {"x": 3293, "y": 3174, "plane": 0, "name": "Al Kharid"},
    "falador": {"x": 2964, "y": 3378, "plane": 0, "name": "Falador"},
}


class MockToolExecutor:
    """
    Mock MCP tool executor for testing.

    Records all tool calls and returns predefined responses.
    """

    def __init__(self, mock_state: Dict[str, Any] = None, verbose: bool = False):
        self.mock_state = mock_state or DEFAULT_MOCK_STATE.copy()
        self.verbose = verbose
        self.call_log: List[Dict[str, Any]] = []
        self.command_count = 0

    async def execute(self, tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a mock tool call."""
        call_record = {
            "tool": tool_name,
            "args": args,
            "timestamp": datetime.now().isoformat(),
        }

        result = await self._dispatch(tool_name, args)
        call_record["result"] = result
        self.call_log.append(call_record)

        if self.verbose:
            print(f"  📞 {tool_name}({json.dumps(args, default=str)[:80]})")
            print(f"     → {json.dumps(result, default=str)[:120]}")

        return result

    async def _dispatch(self, tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """Dispatch to appropriate mock handler."""
        handlers = {
            "get_game_state": self._mock_get_game_state,
            "check_health": self._mock_check_health,
            "lookup_location": self._mock_lookup_location,
            "send_command": self._mock_send_command,
            "get_screenshot": self._mock_get_screenshot,
            "get_logs": self._mock_get_logs,
            "start_runelite": self._mock_start_runelite,
            "stop_runelite": self._mock_stop_runelite,
            "restart_runelite": self._mock_restart_runelite,
            "list_routines": self._mock_list_routines,
            "list_accounts": self._mock_list_accounts,
            "list_plugin_commands": self._mock_list_plugin_commands,
            "get_command_help": self._mock_get_command_help,
            "query_nearby": self._mock_query_nearby,
            "scan_tile_objects": self._mock_scan_tile_objects,
        }

        handler = handlers.get(tool_name)
        if handler:
            return await handler(args)

        return {"error": f"Unknown tool: {tool_name}"}

    async def _mock_get_game_state(self, args: Dict) -> Dict:
        """Mock game state response."""
        fields = args.get("fields", [])

        if not fields:
            return {"state": self.mock_state}

        filtered = {}
        for field in fields:
            if field in self.mock_state:
                filtered[field] = self.mock_state[field]

        return {"state": filtered}

    async def _mock_check_health(self, args: Dict) -> Dict:
        """Mock health check."""
        return {
            "alive": True,
            "process": {"running": True, "pid": 12345},
            "state_file": {"exists": True, "age_seconds": 0.5},
            "window": {"exists": True}
        }

    async def _mock_lookup_location(self, args: Dict) -> Dict:
        """Mock location lookup."""
        location = args.get("location", "").lower()

        # Try exact match first
        if location in MOCK_LOCATIONS:
            loc = MOCK_LOCATIONS[location]
            return {
                "found": True,
                "name": loc["name"],
                "x": loc["x"],
                "y": loc["y"],
                "plane": loc["plane"],
                "goto_command": f"GOTO {loc['x']} {loc['y']} {loc['plane']}"
            }

        # Try partial match
        for key, loc in MOCK_LOCATIONS.items():
            if location in key or key in location:
                return {
                    "found": True,
                    "name": loc["name"],
                    "x": loc["x"],
                    "y": loc["y"],
                    "plane": loc["plane"],
                    "goto_command": f"GOTO {loc['x']} {loc['y']} {loc['plane']}"
                }

        return {
            "found": False,
            "error": f"Location '{location}' not found",
            "hint": "Try: lumbridge, draynor, varrock, ge, cows, frogs, chickens"
        }

    async def _mock_send_command(self, args: Dict) -> Dict:
        """Mock command dispatch."""
        command = args.get("command", "")
        self.command_count += 1

        # Simulate command effects on state
        if command.startswith("GOTO"):
            # Extract coordinates
            parts = command.split()
            if len(parts) >= 4:
                self.mock_state["location"] = {
                    "x": int(parts[1]),
                    "y": int(parts[2]),
                    "plane": int(parts[3])
                }

        elif command.startswith("SWITCH_COMBAT_STYLE"):
            parts = command.split()
            if len(parts) >= 2:
                self.mock_state["combat"]["style"] = parts[1]

        elif command.startswith("BANK_DEPOSIT_ALL"):
            self.mock_state["inventory"]["items"] = []
            self.mock_state["inventory"]["used"] = 0

        return {
            "dispatched": True,
            "command": command,
            "mock": True
        }

    async def _mock_get_screenshot(self, args: Dict) -> Dict:
        """Mock screenshot."""
        return {
            "success": True,
            "path": "/tmp/mock_screenshot.png",
            "message": "Mock screenshot (not a real image)"
        }

    async def _mock_get_logs(self, args: Dict) -> Dict:
        """Mock log retrieval."""
        return {
            "logs": [
                "[INFO] Mock log entry 1",
                "[INFO] Mock log entry 2",
            ],
            "count": 2,
            "mock": True
        }

    async def _mock_start_runelite(self, args: Dict) -> Dict:
        """Mock client start."""
        return {"success": True, "pid": 12345, "mock": True}

    async def _mock_stop_runelite(self, args: Dict) -> Dict:
        """Mock client stop."""
        return {"success": True, "mock": True}

    async def _mock_restart_runelite(self, args: Dict) -> Dict:
        """Mock client restart."""
        return {"restarted": True, "pid": 12346, "mock": True}

    async def _mock_list_routines(self, args: Dict) -> Dict:
        """Mock routine listing."""
        return {
            "routines": [
                "combat/hill_giants.yaml",
                "skilling/fishing_shrimps.yaml",
                "quests/sheep_shearer.yaml",
            ],
            "count": 3
        }

    async def _mock_list_accounts(self, args: Dict) -> Dict:
        """Mock account listing."""
        return {
            "accounts": {"aux": "LOSTimposter"},
            "current": "aux",
            "count": 1
        }

    async def _mock_list_plugin_commands(self, args: Dict) -> Dict:
        """Mock command listing."""
        return {
            "commands": """COMBAT: KILL_LOOP, ATTACK_NPC, SWITCH_COMBAT_STYLE, STOP
MOVEMENT: GOTO, WAIT
BANKING: BANK_OPEN, BANK_CLOSE, BANK_DEPOSIT_ALL, BANK_WITHDRAW
SKILLING: FISH, FISH_DRAYNOR_LOOP, CHOP_TREE, COOK_ALL
INTERACTION: INTERACT_NPC, INTERACT_OBJECT, PICK_UP_ITEM"""
        }

    async def _mock_query_nearby(self, args: Dict) -> Dict:
        """Mock query nearby - returns NPCs, objects, and optionally ground items.

        NOTE: This only returns DROPPED items (TileItems), not static spawns (GameObjects).
        For static item spawns, use scan_tile_objects instead.
        """
        include_ground_items = args.get("include_ground_items", False)
        nearby = self.mock_state.get("nearby", {})

        result = {
            "npcs": nearby.get("npcs", []),
            "objects": nearby.get("objects", []),
        }

        if include_ground_items:
            # Only return dropped items, not static spawns
            result["ground_items"] = nearby.get("ground_items", [])

        # Add contextual hints (matching bot.py behavior)
        hints = []
        for npc in result.get("npcs", []):
            npc_name = npc.get("name", "") if isinstance(npc, dict) else str(npc)
            if "Fishing" in npc_name:
                hints.append("Fishing spots are NPCs. Use FISH or INTERACT_NPC Fishing_spot Net/Bait")
            if "Banker" in npc_name or "Bank" in npc_name:
                hints.append("Banker nearby. Use BANK_OPEN to access bank.")

        for obj in result.get("objects", []):
            obj_name = obj.get("name", "") if isinstance(obj, dict) else str(obj)
            if "Bank" in obj_name:
                hints.append("Bank booth nearby. Use BANK_OPEN to access bank.")

        if hints:
            result["_hints"] = hints

        return result

    async def _mock_scan_tile_objects(self, args: Dict) -> Dict:
        """Mock scan tile objects - finds GameObjects including static item spawns.

        Use this for permanent item spawns (fishing nets, buckets on tables, etc.)
        that don't appear in query_nearby ground_items.
        """
        object_name = args.get("object_name", "").lower().replace("_", " ")
        nearby = self.mock_state.get("nearby", {})

        # Check for static spawns in the scenario
        static_spawns = nearby.get("static_spawns", [])
        objects = nearby.get("objects", [])

        results = []
        for spawn in static_spawns:
            spawn_name = spawn.get("name", "").lower()
            if object_name in spawn_name or spawn_name in object_name:
                results.append({
                    "name": spawn.get("name"),
                    "distance": spawn.get("distance", 1),
                    "x": spawn.get("x", self.mock_state.get("location", {}).get("x", 0)),
                    "y": spawn.get("y", self.mock_state.get("location", {}).get("y", 0)),
                    "type": "GameObject",
                    "actions": spawn.get("actions", ["Take"])
                })

        # Also check regular objects
        for obj in objects:
            obj_name = obj if isinstance(obj, str) else obj.get("name", "")
            if object_name in obj_name.lower():
                results.append({
                    "name": obj_name,
                    "distance": 2,
                    "type": "GameObject"
                })

        result = {
            "success": True,
            "count": len(results),
            "objects": results
        }

        # Add contextual hints for static spawns (matching bot.py behavior)
        hints = []
        for obj in results:
            obj_name = obj.get("name", "").lower()
            obj_actions = obj.get("actions", [])

            if "fishing net" in obj_name or "net" in obj_name:
                hints.append("Static spawn found. Use INTERACT_OBJECT small_fishing_net Take (NOT PICK_UP_ITEM)")
            if "bucket" in obj_name:
                hints.append("Static spawn found. Use INTERACT_OBJECT Bucket Take (NOT PICK_UP_ITEM)")
            if "Take" in obj_actions:
                hints.append("Use INTERACT_OBJECT <name> Take to pick up static spawns")

        if hints:
            result["_hints"] = list(set(hints))  # Dedupe hints

        return result

    async def _mock_get_command_help(self, args: Dict) -> Dict:
        """Mock command help."""
        command = args.get("command", "").upper()
        help_text = {
            "KILL_LOOP": "KILL_LOOP <npc> <food> [count] - Kill NPCs with food management. Use 'none' for no food.",
            "GOTO": "GOTO <x> <y> <plane> - Walk to coordinates",
            "FISH_DRAYNOR_LOOP": "FISH_DRAYNOR_LOOP - Fish shrimp at Draynor with auto-banking",
        }
        return {
            "command": command,
            "help": help_text.get(command, f"No help available for {command}")
        }

    def get_summary(self) -> str:
        """Get a summary of all tool calls."""
        lines = [f"\n{'='*60}", "TOOL CALL SUMMARY", '='*60]

        observe_calls = []
        action_calls = []

        for call in self.call_log:
            tool = call["tool"]
            args = call["args"]

            if tool in ["get_game_state", "check_health", "lookup_location",
                       "get_screenshot", "get_logs", "list_routines",
                       "list_accounts", "list_plugin_commands", "get_command_help",
                       "query_nearby", "scan_tile_objects"]:
                observe_calls.append((tool, args))
            else:
                action_calls.append((tool, args))

        lines.append(f"\n📊 OBSERVATIONS ({len(observe_calls)}):")
        for tool, args in observe_calls:
            args_str = json.dumps(args, default=str)[:60] if args else ""
            lines.append(f"  • {tool}({args_str})")

        lines.append(f"\n⚡ ACTIONS ({len(action_calls)}):")
        for tool, args in action_calls:
            if tool == "send_command":
                cmd = args.get("command", "")
                lines.append(f"  • send_command: {cmd}")
            else:
                args_str = json.dumps(args, default=str)[:60] if args else ""
                lines.append(f"  • {tool}({args_str})")

        observed_first = len(observe_calls) > 0 and (
            len(action_calls) == 0 or
            self.call_log.index({"tool": observe_calls[0][0], "args": observe_calls[0][1],
                                "timestamp": self.call_log[0]["timestamp"],
                                "result": self.call_log[0]["result"]}) == 0
            if self.call_log else True
        )

        # Check if first call was observation
        observation_tools = ["get_game_state", "check_health", "lookup_location",
                             "get_screenshot", "get_logs", "list_routines",
                             "list_accounts", "list_plugin_commands", "get_command_help",
                             "query_nearby", "scan_tile_objects"]
        if self.call_log:
            first_tool = self.call_log[0]["tool"]
            observed_first = first_tool in observation_tools
        else:
            observed_first = False

        lines.append(f"\n✅ Observed before acting: {'YES' if observed_first else 'NO ⚠️'}")
        lines.append(f"📝 Total tool calls: {len(self.call_log)}")
        lines.append(f"🎮 Commands sent: {self.command_count}")

        return "\n".join(lines)


async def run_test(
    message: str,
    mock_state: Dict[str, Any] = None,
    verbose: bool = False,
    history: List[Dict] = None,
    json_output: bool = False,
    model: str = None,
    provider: str = "ollama",
    gemini_model: str = None
) -> Dict[str, Any]:
    """
    Run a single test of the agentic loop.

    Args:
        message: User message to test
        mock_state: Optional custom mock state
        verbose: Show detailed output
        history: Conversation history
        json_output: Output results as JSON
        model: Ollama model to use (overrides default)
        provider: LLM provider (ollama, gemini, claude)
        gemini_model: Gemini model to use (e.g., gemini-2.0-flash)

    Returns:
        Dict with response, tool calls, and analysis
    """
    # Create mock executor
    executor = MockToolExecutor(mock_state=mock_state, verbose=verbose and not json_output)

    # Create LLM client with provider
    llm = LLMClient(provider=provider)
    if provider == "ollama" and model:
        llm.ollama_model = model
        if not json_output:
            print(f"Using model: {model}")
    elif provider == "gemini":
        if gemini_model:
            llm._gemini_model = gemini_model
        if not json_output:
            print(f"Using Gemini model: {llm._gemini_model}")
    elif provider == "claude-code":
        if not json_output:
            print(f"Using Claude Code CLI with model: {llm._claude_code_model}")

    # Create agentic loop with mock executor
    loop = AgenticLoopWithRecovery(
        llm_client=llm,
        tool_executor=executor.execute,
        max_iterations=10
    )

    if not json_output:
        print(f"\n{'='*60}")
        print(f"USER: {message}")
        print('='*60)

        if verbose:
            print("\n🔄 Processing...")

    # Run the loop
    try:
        result = await loop.process(message, history or [])
    except Exception as e:
        output = {
            "message": message,
            "error": str(e),
            "tool_calls": executor.call_log,
        }
        if json_output:
            print(json.dumps(output, indent=2, default=str))
        return output

    output = {
        "message": message,
        "response": result.response,
        "tool_calls": executor.call_log,
        "iterations": result.iterations,
        "observed": result.observed,
        "actions": result.actions,
        "error": result.error,
        "commands_sent": executor.command_count,
    }

    if json_output:
        print(json.dumps(output, indent=2, default=str))
    else:
        # Print results
        print(f"\n💬 RESPONSE: {result.response}")
        print(executor.get_summary())

        if result.error:
            print(f"\n⚠️ ERROR: {result.error}")

    return output


async def interactive_mode(mock_state: Dict = None, verbose: bool = False, model: str = None,
                          provider: str = "ollama", gemini_model: str = None):
    """Run interactive test session."""
    print("\n" + "="*60)
    print("DISCORD BOT TEST HARNESS - Interactive Mode")
    print("="*60)
    print(f"Provider: {provider}")
    if provider == "ollama" and model:
        print(f"Model: {model}")
    elif provider == "gemini":
        print(f"Gemini model: {gemini_model or 'gemini-2.0-flash-lite'}")
    print("Type messages to test the agentic loop.")
    print("Commands: /quit, /state, /reset, /verbose, /help")
    print("="*60)

    history = []

    while True:
        try:
            message = input("\n> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting.")
            break

        if not message:
            continue

        # Handle special commands
        if message.startswith("/"):
            cmd = message.lower()

            if cmd in ["/quit", "/exit", "/q"]:
                print("Exiting.")
                break

            elif cmd == "/state":
                state = mock_state or DEFAULT_MOCK_STATE
                print(json.dumps(state, indent=2))
                continue

            elif cmd == "/reset":
                history = []
                mock_state = DEFAULT_MOCK_STATE.copy()
                print("Reset history and state.")
                continue

            elif cmd == "/verbose":
                verbose = not verbose
                print(f"Verbose mode: {'ON' if verbose else 'OFF'}")
                continue

            elif cmd == "/history":
                print(json.dumps(history, indent=2))
                continue

            elif cmd == "/help":
                print("""
Commands:
  /quit, /exit, /q  - Exit
  /state            - Show current mock state
  /reset            - Reset history and state
  /verbose          - Toggle verbose mode
  /history          - Show conversation history
  /help             - Show this help
                """)
                continue

            else:
                print(f"Unknown command: {cmd}")
                continue

        # Run test
        result = await run_test(message, mock_state=mock_state, verbose=verbose, history=history, model=model,
                                provider=provider, gemini_model=gemini_model)

        # Update history
        history.append({"role": "user", "content": message})
        if result.get("response"):
            history.append({"role": "assistant", "content": result["response"]})

        # Keep history reasonable
        history = history[-10:]


async def record_live_state():
    """Record live game state for use as mock data."""
    print("\n" + "="*60)
    print("RECORDING LIVE STATE")
    print("="*60)

    try:
        # Import real monitoring tools
        from mcptools.tools import monitoring
        from mcptools.config import ServerConfig
        from mcptools.runelite_manager import MultiRuneLiteManager

        config = ServerConfig.load()
        manager = MultiRuneLiteManager(config)
        monitoring.set_dependencies(manager, config)

        # Get current state
        print("Fetching game state from live client...")
        result = await monitoring.handle_get_game_state({"account_id": "aux"})

        if "state" in result:
            state = result["state"]

            # Save to file
            output_path = Path("discord_bot/mock_states")
            output_path.mkdir(exist_ok=True)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = output_path / f"state_{timestamp}.json"

            with open(filename, "w") as f:
                json.dump(state, f, indent=2, default=str)

            print(f"\n✅ State saved to: {filename}")
            print(f"\nUse with: python discord_bot/test_harness.py --state-file {filename} \"your message\"")
            print(f"\nState preview:")
            print(json.dumps(state, indent=2, default=str)[:500])
        else:
            print(f"Failed to get state: {result}")

    except Exception as e:
        print(f"Error recording state: {e}")
        print("\nMake sure RuneLite is running with the manny plugin.")


def load_scenario(scenario_name: str) -> Optional[Dict]:
    """Load a pre-built scenario from scenarios.json."""
    scenarios_file = Path(__file__).parent / "mock_states" / "scenarios.json"
    if not scenarios_file.exists():
        print(f"Scenarios file not found: {scenarios_file}")
        return None

    with open(scenarios_file) as f:
        scenarios = json.load(f)

    if scenario_name not in scenarios:
        available = [k for k in scenarios.keys() if not k.startswith("_")]
        print(f"Unknown scenario: {scenario_name}")
        print(f"Available scenarios: {', '.join(available)}")
        return None

    scenario = scenarios[scenario_name]
    desc = scenario.pop("_description", "")
    print(f"Loaded scenario '{scenario_name}': {desc}")
    return scenario


def list_scenarios():
    """List all available scenarios."""
    scenarios_file = Path(__file__).parent / "mock_states" / "scenarios.json"
    if not scenarios_file.exists():
        print("No scenarios file found")
        return

    with open(scenarios_file) as f:
        scenarios = json.load(f)

    print("\nAvailable Scenarios:")
    print("=" * 50)
    for name, data in scenarios.items():
        if name.startswith("_"):
            continue
        desc = data.get("_description", "No description")
        print(f"  {name:20} - {desc}")
    print("\nUsage: python discord_bot/test_harness.py --scenario <name> \"message\"")


def main():
    parser = argparse.ArgumentParser(
        description="Test harness for Discord bot LLM reasoning",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Interactive mode
  python discord_bot/test_harness.py

  # Single test
  python discord_bot/test_harness.py "Kill 100 giant frogs"

  # With verbose output
  python discord_bot/test_harness.py -v "Go fish at draynor"

  # With pre-built scenario
  python discord_bot/test_harness.py --scenario low_health "What should I do?"
  python discord_bot/test_harness.py --scenario full_inventory "I'm full"

  # List all scenarios
  python discord_bot/test_harness.py --list-scenarios

  # With custom state file
  python discord_bot/test_harness.py --state-file mock_state.json "What's in my inventory?"

  # Record live state for later testing
  python discord_bot/test_harness.py --record
        """
    )

    parser.add_argument("message", nargs="?", help="Message to test (omit for interactive mode)")
    parser.add_argument("-v", "--verbose", action="store_true", help="Show detailed output")
    parser.add_argument("--scenario", "-s", help="Load pre-built scenario (e.g., low_health, full_inventory)")
    parser.add_argument("--list-scenarios", action="store_true", help="List available scenarios")
    parser.add_argument("--state-file", help="JSON file with mock game state")
    parser.add_argument("--record", action="store_true", help="Record live game state")
    parser.add_argument("--json", action="store_true", help="Output results as JSON for analysis")
    parser.add_argument("--model", "-m", help="Ollama model to use (e.g., qwen2.5:14b, qwen3:14b)")
    parser.add_argument("--provider", "-p", choices=["ollama", "gemini", "claude", "claude-code"], default="ollama",
                        help="LLM provider (default: ollama)")
    parser.add_argument("--gemini-model", help="Gemini model (e.g., gemini-2.0-flash, gemini-2.5-flash)")

    args = parser.parse_args()

    # Handle list scenarios
    if args.list_scenarios:
        list_scenarios()
        return

    # Load custom state if provided
    mock_state = None

    # Load scenario first (can be overridden by state-file)
    if args.scenario:
        mock_state = load_scenario(args.scenario)
        if mock_state is None:
            sys.exit(1)

    # State file overrides scenario
    if args.state_file:
        try:
            with open(args.state_file) as f:
                mock_state = json.load(f)
            print(f"Loaded mock state from: {args.state_file}")
        except Exception as e:
            print(f"Error loading state file: {e}")
            sys.exit(1)

    # Run appropriate mode
    if args.record:
        asyncio.run(record_live_state())
    elif args.message:
        asyncio.run(run_test(
            args.message,
            mock_state=mock_state,
            verbose=args.verbose,
            json_output=args.json,
            model=args.model,
            provider=args.provider,
            gemini_model=args.gemini_model
        ))
    else:
        asyncio.run(interactive_mode(mock_state=mock_state, verbose=args.verbose, model=args.model,
                                     provider=args.provider, gemini_model=args.gemini_model))


if __name__ == "__main__":
    main()
