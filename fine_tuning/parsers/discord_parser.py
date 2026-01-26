#!/usr/bin/env python3
"""
Discord Conversation Parser - Stage 1 Automated Extraction

Parses Discord bot conversation logs into training examples.
For Stage 2 enrichment (negative examples, reasoning chains), see CLAUDE.md.

Usage:
    python3 discord_parser.py --date 2026-01-25    # Parse specific day
    python3 discord_parser.py --all                 # Parse all unparsed
    python3 discord_parser.py --status              # Show parse status
    python3 discord_parser.py --reparse 2026-01-25  # Force re-parse
"""

import json
import argparse
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Generator
from dataclasses import dataclass, asdict, field


# Paths
LOGS_DIR = Path(__file__).parent.parent.parent / "logs" / "conversations"
EXTRACTED_DIR = Path(__file__).parent.parent / "data" / "extracted"


# Command categories for tagging
COMMAND_CATEGORIES = {
    "fishing": ["FISH", "FISH_DRAYNOR", "FISH_LOOP", "NET", "HARPOON"],
    "banking": ["BANK_OPEN", "BANK_CLOSE", "BANK_WITHDRAW", "BANK_DEPOSIT", "DEPOSIT"],
    "navigation": ["GOTO", "WALK", "RUN"],
    "combat": ["KILL", "KILL_LOOP", "ATTACK", "FIGHT"],
    "interaction": ["INTERACT_NPC", "INTERACT_OBJECT", "TALK", "USE"],
    "inventory": ["DROP", "EQUIP", "USE_ITEM", "EAT", "DRINK"],
    "query": ["get_game_state", "query_nearby", "scan_widgets", "get_logs"],
}


@dataclass
class ToolCall:
    tool: str
    arguments: Dict
    result: Optional[Dict] = None


@dataclass
class TrainingExample:
    id: str
    source: str = "discord"
    source_file: str = ""
    example_type: str = "direct_execution"
    user_message: str = ""
    game_state: Optional[Dict] = None
    context: Optional[str] = None
    tool_calls: List[Dict] = field(default_factory=list)
    response_text: str = ""
    reasoning: Optional[str] = None
    problem: Optional[str] = None
    root_cause: Optional[str] = None
    bad_code: Optional[str] = None
    good_code: Optional[str] = None
    task_type: str = "simple_command"
    tags: List[str] = field(default_factory=list)
    quality_score: float = 0.7  # Neutral default for automated extraction


def categorize_command(command: str) -> List[str]:
    """Categorize a command into tags based on keywords."""
    tags = []
    command_upper = command.upper()

    for category, keywords in COMMAND_CATEGORIES.items():
        if any(kw in command_upper for kw in keywords):
            tags.append(category)

    return tags if tags else ["other"]


def categorize_tool(tool: str) -> List[str]:
    """Categorize a tool call into tags."""
    tool_lower = tool.lower()

    if "game_state" in tool_lower:
        return ["query", "state_check"]
    elif "nearby" in tool_lower or "scan" in tool_lower:
        return ["query", "discovery"]
    elif "send_command" in tool_lower:
        return ["execution"]
    elif "log" in tool_lower:
        return ["query", "debugging"]

    return ["other"]


def parse_conversation(log_path: Path) -> Generator[TrainingExample, None, None]:
    """Parse a Discord conversation log file into training examples."""

    date_str = log_path.stem.replace("conversations_", "")
    source_file = f"logs/conversations/{log_path.name}"

    # Group entries by request_id
    requests = {}

    with open(log_path) as f:
        for line in f:
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue

            request_id = entry.get("request_id")
            if not request_id:
                continue

            if request_id not in requests:
                requests[request_id] = {
                    "request": None,
                    "tool_calls": [],
                    "response": None
                }

            entry_type = entry.get("type")
            if entry_type == "request":
                requests[request_id]["request"] = entry
            elif entry_type == "tool_call":
                requests[request_id]["tool_calls"].append(entry)
            elif entry_type == "response":
                requests[request_id]["response"] = entry

    # Convert to training examples
    example_idx = 0
    for request_id, data in sorted(requests.items()):
        request = data["request"]
        tool_calls = data["tool_calls"]
        response = data["response"]

        if not request or not response:
            continue

        # Build tool_calls list
        tc_list = []
        tags = set()
        game_state = None

        for tc in tool_calls:
            tool = tc.get("tool", "")
            args = tc.get("arguments", {})
            result = tc.get("result")

            tc_list.append({
                "tool": tool,
                "arguments": args,
                "result": result
            })

            # Extract game state if available
            if tool == "get_game_state" and result and "state" in result:
                game_state = result["state"]

            # Categorize
            if tool == "send_command" and "command" in args:
                tags.update(categorize_command(args["command"]))
            else:
                tags.update(categorize_tool(tool))

        # Determine if this is likely a good or questionable example
        # (Stage 2 enrichment will refine this)
        quality = 0.7  # Neutral default

        # Boost quality if response indicates success
        response_text = response.get("response", "")
        if any(word in response_text.lower() for word in ["started", "completed", "success", "done"]):
            quality = 0.85

        # Lower quality if response indicates uncertainty
        if any(word in response_text.lower() for word in ["couldn't", "failed", "error", "not found"]):
            quality = 0.5

        example = TrainingExample(
            id=f"discord_{date_str.replace('-', '')}_{example_idx:03d}",
            source_file=source_file,
            user_message=request.get("message", ""),
            game_state=game_state,
            tool_calls=tc_list,
            response_text=response_text,
            task_type=request.get("task_type", "simple_command"),
            tags=sorted(list(tags)),
            quality_score=quality
        )

        yield example
        example_idx += 1


def get_log_dates() -> List[str]:
    """Get all available Discord log dates."""
    dates = []
    for path in LOGS_DIR.glob("conversations_*.jsonl"):
        date_str = path.stem.replace("conversations_", "")
        dates.append(date_str)
    return sorted(dates)


def get_parsed_dates() -> List[str]:
    """Get dates that have already been parsed."""
    dates = []
    for path in EXTRACTED_DIR.glob("discord_*.jsonl"):
        date_str = path.stem.replace("discord_", "")
        dates.append(date_str)
    return sorted(dates)


def parse_date(date_str: str, force: bool = False) -> Optional[Path]:
    """Parse a specific date's logs."""
    log_path = LOGS_DIR / f"conversations_{date_str}.jsonl"
    output_path = EXTRACTED_DIR / f"discord_{date_str}.jsonl"

    if not log_path.exists():
        print(f"No log file for {date_str}")
        return None

    if output_path.exists() and not force:
        print(f"Already parsed: {date_str} (use --reparse to force)")
        return output_path

    # Ensure output dir exists
    EXTRACTED_DIR.mkdir(parents=True, exist_ok=True)

    # Parse and write
    examples = list(parse_conversation(log_path))

    with open(output_path, 'w') as f:
        for example in examples:
            f.write(json.dumps(asdict(example)) + "\n")

    print(f"Parsed {date_str}: {len(examples)} examples → {output_path}")
    return output_path


def show_status():
    """Show parsing status for all dates."""
    log_dates = set(get_log_dates())
    parsed_dates = set(get_parsed_dates())

    print("\n=== Discord Log Parsing Status ===\n")

    all_dates = sorted(log_dates | parsed_dates)

    for date in all_dates:
        has_log = date in log_dates
        has_parsed = date in parsed_dates

        if has_log and has_parsed:
            # Count examples
            extracted_path = EXTRACTED_DIR / f"discord_{date}.jsonl"
            count = sum(1 for _ in open(extracted_path))
            print(f"  {date}: ✓ parsed ({count} examples)")
        elif has_log and not has_parsed:
            print(f"  {date}: ○ not yet parsed")
        elif has_parsed and not has_log:
            print(f"  {date}: ? parsed but log missing")

    unparsed = log_dates - parsed_dates
    print(f"\nTotal: {len(log_dates)} logs, {len(parsed_dates)} parsed, {len(unparsed)} pending")


def main():
    parser = argparse.ArgumentParser(description="Parse Discord conversation logs")
    parser.add_argument("--date", help="Parse specific date (YYYY-MM-DD)")
    parser.add_argument("--all", action="store_true", help="Parse all unparsed logs")
    parser.add_argument("--reparse", help="Force re-parse a date")
    parser.add_argument("--status", action="store_true", help="Show parsing status")

    args = parser.parse_args()

    if args.status:
        show_status()
    elif args.date:
        parse_date(args.date)
    elif args.reparse:
        parse_date(args.reparse, force=True)
    elif args.all:
        log_dates = set(get_log_dates())
        parsed_dates = set(get_parsed_dates())
        unparsed = log_dates - parsed_dates

        if not unparsed:
            print("All logs already parsed")
            return

        for date in sorted(unparsed):
            parse_date(date)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
