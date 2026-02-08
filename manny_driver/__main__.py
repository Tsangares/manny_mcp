"""CLI entry point: python -m manny_driver"""
import argparse
import asyncio
import logging
import signal
import sys
from pathlib import Path

from dotenv import load_dotenv

from .agent import Agent
from .cli import (
    print_banner,
    print_error,
    print_stats,
    print_status,
    print_text,
    print_tool_call,
    read_user_input,
    C,
)
from .config import DriverConfig, detect_provider, load_config
from .llm_client import create_client
from .mcp_client import MCPClient

# Load .env from project root
load_dotenv(Path(__file__).parent.parent / ".env")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="manny-driver",
        description="Autonomous OSRS agent powered by LLMs via MCP",
    )
    parser.add_argument(
        "goal",
        nargs="?",
        default=None,
        help="Goal directive (e.g., 'Mine iron ore until level 60')",
    )
    parser.add_argument(
        "--account", "-a",
        default=None,
        help="OSRS account alias (default: main)",
    )
    parser.add_argument(
        "--provider", "-p",
        choices=["anthropic", "gemini", "ollama", "openai", "auto"],
        default=None,
        help="LLM provider (default: auto-detect)",
    )
    parser.add_argument(
        "--model", "-m",
        default=None,
        help="Model name override (e.g., claude-haiku-4-5-20251001)",
    )
    parser.add_argument(
        "--monitor",
        action="store_true",
        help="Monitor-only mode (no autonomous actions)",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Verbose logging",
    )
    parser.add_argument(
        "--max-tools",
        type=int,
        default=None,
        help="Max tool calls per turn (default: 50)",
    )
    return parser.parse_args()


async def interactive_loop(agent: Agent):
    """REPL-style interactive mode."""
    print(f"\n{C.DIM}Interactive mode. Type a goal or message. Ctrl+C to stop, Ctrl+D to quit.{C.RESET}\n")

    while True:
        try:
            user_input = await read_user_input(f"{C.BOLD}> {C.RESET}")
            if not user_input.strip():
                continue

            # Run the directive
            tool_calls = await agent.run_directive(user_input.strip())
            print_status(f"Turn complete: {tool_calls} tool calls")
            print()

        except EOFError:
            print("\nGoodbye.")
            break
        except KeyboardInterrupt:
            print(f"\n{C.DIM}(Ctrl+C caught - type a new command or Ctrl+D to quit){C.RESET}")
            agent.stop()
            continue


async def goal_mode(agent: Agent, goal: str, monitor_after: bool = True):
    """Execute a goal directive, then optionally monitor."""
    print(f"\n{C.BOLD}Goal:{C.RESET} {goal}\n")

    tool_calls = await agent.run_directive(goal)
    print_status(f"Execution complete: {tool_calls} tool calls")

    if monitor_after:
        print(f"\n{C.DIM}Entering monitoring mode (Ctrl+C to stop)...{C.RESET}\n")
        try:
            await agent.run_monitoring()
        except KeyboardInterrupt:
            print(f"\n{C.DIM}Monitoring stopped.{C.RESET}")


async def main():
    args = parse_args()

    # Setup logging
    level = logging.DEBUG if args.verbose else logging.WARNING
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
    )

    # Load config
    config = load_config(
        provider=args.provider if args.provider != "auto" else None,
        model=args.model,
        account=args.account,
        verbose=args.verbose,
        monitor_only=args.monitor,
    )

    if args.max_tools:
        config.max_tool_calls_per_turn = args.max_tools

    # Print banner
    print_banner(config.provider, config.resolved_model, config.account_id)

    # Create LLM client
    try:
        llm = create_client(config.provider, config.resolved_model)
    except Exception as e:
        print_error(f"Failed to create LLM client: {e}")
        sys.exit(1)

    # Connect to MCP server
    print_status("Connecting to MCP server...")
    mcp = MCPClient(
        server_script=config.server_script,
        server_cwd=config.server_cwd,
    )

    try:
        await mcp.connect()
        tool_count = len(mcp.get_tools())
        from .tools import filter_tools
        gameplay_count = len(filter_tools(mcp.get_tools()))
        print_status(f"Connected: {gameplay_count} gameplay tools (of {tool_count} total)")

    except Exception as e:
        print_error(f"Failed to connect to MCP server: {e}")
        sys.exit(1)

    # Wait for game client to be reachable before handing off to LLM
    print_status("Checking game client...")
    acct_args = {"account_id": config.account_id} if config.account_id else {}
    for attempt in range(10):
        try:
            # Just verify we can get game state with player data
            state_text = await mcp.call_tool("get_game_state", {
                **acct_args,
                "fields": ["location"],
            })
            import json as _json
            state = _json.loads(state_text)
            if state.get("success") and state.get("state", {}).get("location"):
                loc = state["state"]["location"]
                print_status(f"Game client ready at ({loc['x']}, {loc['y']})")
                break
        except Exception:
            pass
        if attempt == 9:
            print_error("Cannot reach game client after 10s. Is RuneLite running?")
            await mcp.disconnect()
            sys.exit(1)
        await asyncio.sleep(1)

    # Create agent
    agent = Agent(
        config=config,
        mcp=mcp,
        llm=llm,
        on_tool_call=print_tool_call,
        on_text=print_text,
        on_status=print_status,
    )

    # Handle Ctrl+C gracefully
    def handle_sigint(sig, frame):
        print(f"\n{C.DIM}(stopping...){C.RESET}")
        agent.stop()

    signal.signal(signal.SIGINT, handle_sigint)

    try:
        if args.goal:
            # Goal-directed mode
            await goal_mode(agent, args.goal, monitor_after=not args.monitor)
        else:
            # Interactive REPL mode
            await interactive_loop(agent)

    except KeyboardInterrupt:
        pass
    finally:
        # Print stats
        print_stats(agent.conversation.stats)

        # Disconnect
        print_status("Disconnecting...")
        await mcp.disconnect()
        print()


def run():
    """Entry point for the CLI."""
    asyncio.run(main())


if __name__ == "__main__":
    run()
