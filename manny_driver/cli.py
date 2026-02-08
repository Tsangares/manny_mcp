"""Terminal output and user interaction for manny-driver."""
import asyncio
import json
import sys
import time
from typing import Any


# ANSI colors
class C:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    GRAY = "\033[90m"


def print_banner(provider: str, model: str, account: str):
    """Print startup banner."""
    print(f"\n{C.BOLD}manny-driver{C.RESET} - Autonomous OSRS Agent")
    print(f"{C.DIM}Provider: {C.RESET}{C.CYAN}{provider}{C.RESET} ({C.CYAN}{model}{C.RESET})")
    print(f"{C.DIM}Account:  {C.RESET}{C.CYAN}{account}{C.RESET}")
    print(f"{C.DIM}{'─' * 50}{C.RESET}\n")


def print_tool_call(name: str, args: dict[str, Any]):
    """Display a tool call (like Claude Code shows tool usage)."""
    # Compact args display
    args_str = ""
    if args:
        # Show command string specially
        if "command" in args:
            args_str = f' "{args["command"]}"'
            other = {k: v for k, v in args.items() if k != "command"}
            if other:
                args_str += f" {_compact_args(other)}"
        elif "fields" in args:
            args_str = f" {args['fields']}"
        else:
            args_str = f" {_compact_args(args)}"

    # Color by tool type
    if name in ("send_command", "send_and_await", "kill_command"):
        color = C.YELLOW
    elif name in ("get_game_state", "get_logs", "check_health", "is_alive",
                   "query_nearby", "get_dialogue", "get_transitions"):
        color = C.BLUE
    elif name.startswith("start_") or name.startswith("stop_") or name.startswith("restart_"):
        color = C.RED
    else:
        color = C.MAGENTA

    print(f"  {color}{C.BOLD}{name}{C.RESET}{C.DIM}{args_str}{C.RESET}")


def print_text(text: str):
    """Display LLM text output."""
    if not text.strip():
        return
    # Indent and color
    for line in text.strip().split("\n"):
        print(f"  {C.GREEN}{line}{C.RESET}")


def print_status(status: str):
    """Display a status message."""
    print(f"  {C.GRAY}[{status}]{C.RESET}")


def print_stats(stats):
    """Display session statistics."""
    print(f"\n{C.DIM}{'─' * 50}{C.RESET}")
    print(f"{C.DIM}{stats.summary}{C.RESET}")


def print_error(error: str):
    """Display an error message."""
    print(f"\n  {C.RED}{C.BOLD}Error:{C.RESET} {C.RED}{error}{C.RESET}")


def _compact_args(args: dict) -> str:
    """Format args compactly for display."""
    parts = []
    for k, v in args.items():
        if isinstance(v, str) and len(v) > 60:
            v = v[:60] + "..."
        parts.append(f"{k}={v}")
    return ", ".join(parts)


async def read_user_input(prompt: str = "> ") -> str:
    """Read user input asynchronously (non-blocking)."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, lambda: input(prompt))
