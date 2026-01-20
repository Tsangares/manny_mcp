"""
Enhanced Claude Code Session Parser - Extract MCP training data from sessions.

Claude Code sessions contain complex multi-turn interactions. This parser:

1. Filters for MCP-related tool calls (ignores Read/Edit/Bash for file editing)
2. Extracts user intent → observation → action → verification sequences
3. Handles multi-turn context (user says "fix that" referencing earlier turn)
4. Categorizes sessions by primary focus (MCP control vs code editing)
5. Extracts successful execution patterns for training

Output: Structured JSONL suitable for fine-tuning.
"""

import json
import re
from pathlib import Path
from dataclasses import dataclass, asdict, field
from typing import List, Dict, Optional, Generator, Set, Tuple
from datetime import datetime


# MCP tools we care about for game control training
MCP_GAME_CONTROL_TOOLS = {
    # Core control
    "send_command", "send_and_await", "send_input",
    # Observation
    "get_game_state", "get_screenshot", "analyze_screenshot",
    "get_logs", "get_command_response", "check_health", "is_alive",
    # Widget interaction
    "scan_widgets", "find_widget", "click_widget", "click_text",
    "click_continue", "get_dialogue", "find_and_click_widget",
    # Spatial awareness
    "query_nearby", "scan_tile_objects", "get_transitions",
    "scan_environment", "get_location_info",
    # Client management
    "start_runelite", "stop_runelite", "runelite_status",
    "auto_reconnect", "restart_if_frozen",
    # Routine execution
    "execute_routine", "execute_combat_routine",
    # Equipment/inventory
    "deposit_item", "equip_item", "teleport_home", "stabilize_camera",
}

# Tools to ignore (code editing, not game control)
IGNORE_TOOLS = {"Read", "Write", "Edit", "Glob", "Grep", "Bash", "Task", "TodoWrite"}

# MCP prefix patterns
MCP_PREFIXES = ["mcp__runelite-debug__", "mcp__manny__"]


@dataclass
class ToolCall:
    """A single tool call with result."""
    tool: str  # Simplified tool name
    full_name: str  # Original full name
    arguments: Dict
    result: Optional[Dict] = None
    success: bool = True


@dataclass
class ConversationTurn:
    """A user message and assistant response pair."""
    user_message: str
    user_content_blocks: List[Dict] = field(default_factory=list)
    assistant_text: str = ""
    assistant_thinking: str = ""
    tool_calls: List[ToolCall] = field(default_factory=list)
    has_mcp_tools: bool = False
    has_edit_tools: bool = False
    timestamp: Optional[str] = None


@dataclass
class ExtractedSequence:
    """An extracted training sequence."""
    session_id: str
    turn_index: int
    user_intent: str
    observations: List[Dict]  # get_game_state, get_logs results
    actions: List[Dict]  # send_command, click_text calls
    verifications: List[Dict]  # Post-action checks
    response: str
    success: bool
    task_type: str  # "simple_command", "loop_command", "multi_step", "query", etc.


class ClaudeSessionParser:
    """Parse Claude Code sessions for MCP training data."""

    def __init__(self, session_dir: str = None):
        self.session_dir = Path(session_dir or
            "~/.claude/projects/-home-wil-manny-mcp").expanduser()

    def list_sessions(self) -> List[Path]:
        """List all session files."""
        return sorted(self.session_dir.glob("*.jsonl"))

    def _is_mcp_tool(self, tool_name: str) -> bool:
        """Check if this is an MCP game control tool."""
        for prefix in MCP_PREFIXES:
            if tool_name.startswith(prefix):
                # Extract the actual tool name
                short_name = tool_name.split("__")[-1]
                return short_name in MCP_GAME_CONTROL_TOOLS
        return False

    def _simplify_tool_name(self, tool_name: str) -> str:
        """Convert mcp__runelite-debug__send_command -> send_command."""
        for prefix in MCP_PREFIXES:
            if tool_name.startswith(prefix):
                return tool_name.split("__")[-1]
        return tool_name

    def _read_session(self, session_path: Path) -> Generator[Dict, None, None]:
        """Read and yield messages from a session file."""
        with open(session_path) as f:
            for line in f:
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    continue

    def _extract_user_content(self, msg: Dict) -> Tuple[str, List[Dict]]:
        """Extract text content from user message."""
        message = msg.get("message", {})
        content = message.get("content", "")

        if isinstance(content, str):
            return content, []
        elif isinstance(content, list):
            texts = []
            blocks = []
            for block in content:
                if block.get("type") == "text":
                    texts.append(block.get("text", ""))
                elif block.get("type") == "tool_result":
                    blocks.append(block)
            return " ".join(texts), blocks
        return str(content), []

    def _extract_assistant_content(self, messages: List[Dict]) -> Tuple[str, str, List[ToolCall]]:
        """Extract text, thinking, and tool calls from consecutive assistant messages."""
        text_parts = []
        thinking_parts = []
        tool_calls = []

        for msg in messages:
            content = msg.get("message", {}).get("content", [])
            if not isinstance(content, list):
                continue

            for block in content:
                block_type = block.get("type")
                if block_type == "text":
                    text_parts.append(block.get("text", ""))
                elif block_type == "thinking":
                    thinking_parts.append(block.get("thinking", ""))
                elif block_type == "tool_use":
                    tool_name = block.get("name", "")
                    tool_calls.append(ToolCall(
                        tool=self._simplify_tool_name(tool_name),
                        full_name=tool_name,
                        arguments=block.get("input", {}),
                    ))

        return " ".join(text_parts), " ".join(thinking_parts), tool_calls

    def parse_session(self, session_path: Path) -> Generator[ConversationTurn, None, None]:
        """Parse a session into conversation turns."""
        messages = list(self._read_session(session_path))

        i = 0
        while i < len(messages):
            msg = messages[i]

            # Skip non-message types
            if msg.get("type") not in ("user", "assistant"):
                i += 1
                continue

            # Find user message
            if msg.get("type") == "user":
                user_text, user_blocks = self._extract_user_content(msg)

                # Skip tool result messages (these are responses to tool calls)
                if user_blocks and all(b.get("type") == "tool_result" for b in user_blocks):
                    i += 1
                    continue

                # Collect consecutive assistant messages
                assistant_msgs = []
                j = i + 1
                while j < len(messages) and messages[j].get("type") == "assistant":
                    assistant_msgs.append(messages[j])
                    j += 1

                if assistant_msgs:
                    text, thinking, tool_calls = self._extract_assistant_content(assistant_msgs)

                    has_mcp = any(self._is_mcp_tool(tc.full_name) for tc in tool_calls)
                    has_edit = any(tc.tool in IGNORE_TOOLS for tc in tool_calls)

                    # Only yield turns with MCP tools
                    if has_mcp or (user_text and not has_edit):
                        yield ConversationTurn(
                            user_message=user_text,
                            user_content_blocks=user_blocks,
                            assistant_text=text,
                            assistant_thinking=thinking,
                            tool_calls=tool_calls,
                            has_mcp_tools=has_mcp,
                            has_edit_tools=has_edit,
                            timestamp=msg.get("timestamp"),
                        )

                i = j
            else:
                i += 1

    def extract_training_sequences(self, session_path: Path) -> Generator[ExtractedSequence, None, None]:
        """Extract training sequences from a session."""
        session_id = session_path.stem

        for turn_idx, turn in enumerate(self.parse_session(session_path)):
            # Skip turns without MCP tools
            if not turn.has_mcp_tools:
                continue

            # Categorize tool calls
            observations = []
            actions = []
            verifications = []

            for tc in turn.tool_calls:
                if not self._is_mcp_tool(tc.full_name):
                    continue

                call_data = {"tool": tc.tool, "args": tc.arguments}

                # Observation tools
                if tc.tool in ("get_game_state", "get_screenshot", "get_logs",
                               "check_health", "query_nearby", "scan_widgets",
                               "scan_tile_objects", "get_transitions", "scan_environment",
                               "get_dialogue", "find_widget"):
                    observations.append(call_data)

                # Action tools
                elif tc.tool in ("send_command", "send_and_await", "send_input",
                                 "click_text", "click_widget", "click_continue",
                                 "start_runelite", "stop_runelite", "execute_routine",
                                 "deposit_item", "equip_item", "teleport_home",
                                 "stabilize_camera", "find_and_click_widget"):
                    actions.append(call_data)

                # Verification tools (often used after actions)
                elif tc.tool in ("get_command_response", "is_alive", "runelite_status"):
                    verifications.append(call_data)

            # Only yield if there are actions
            if actions:
                task_type = self._infer_task_type(turn.user_message, actions)

                yield ExtractedSequence(
                    session_id=session_id,
                    turn_index=turn_idx,
                    user_intent=turn.user_message[:500],
                    observations=observations,
                    actions=actions,
                    verifications=verifications,
                    response=turn.assistant_text[:500],
                    success=True,  # Assume success if we got here
                    task_type=task_type,
                )

    def _infer_task_type(self, user_message: str, actions: List[Dict]) -> str:
        """Infer the task type from user message and actions."""
        msg_lower = user_message.lower()

        # Check for loop commands
        for action in actions:
            if action["tool"] == "send_command":
                cmd = action["args"].get("command", "")
                if "LOOP" in cmd:
                    return "loop_command"

        # Check for status queries
        if any(w in msg_lower for w in ["status", "where", "what", "level", "health"]):
            if not actions or all(a["tool"] in ("get_game_state", "check_health") for a in actions):
                return "status_query"

        # Check for multi-step
        if len(actions) > 2:
            return "multi_step"

        # Check for client management
        if any(a["tool"] in ("start_runelite", "stop_runelite") for a in actions):
            return "client_management"

        # Default to simple command
        return "simple_command"

    def export_training_data(self, output_path: str, max_sessions: int = None) -> int:
        """Export all training sequences to JSONL."""
        count = 0

        with open(output_path, "w") as f:
            sessions = self.list_sessions()
            if max_sessions:
                sessions = sessions[:max_sessions]

            for session_path in sessions:
                try:
                    for seq in self.extract_training_sequences(session_path):
                        f.write(json.dumps(asdict(seq)) + "\n")
                        count += 1
                except Exception as e:
                    print(f"Error processing {session_path.name}: {e}")

        return count

    def get_stats(self, max_sessions: int = None) -> Dict:
        """Get statistics about extractable training data."""
        stats = {
            "sessions_processed": 0,
            "total_sequences": 0,
            "by_task_type": {},
            "tools_used": {},
            "actions_per_sequence": [],
        }

        sessions = self.list_sessions()
        if max_sessions:
            sessions = sessions[:max_sessions]

        for session_path in sessions:
            try:
                stats["sessions_processed"] += 1
                for seq in self.extract_training_sequences(session_path):
                    stats["total_sequences"] += 1
                    stats["by_task_type"][seq.task_type] = stats["by_task_type"].get(seq.task_type, 0) + 1
                    stats["actions_per_sequence"].append(len(seq.actions))

                    for action in seq.actions:
                        tool = action["tool"]
                        stats["tools_used"][tool] = stats["tools_used"].get(tool, 0) + 1
            except Exception as e:
                print(f"Error: {e}")

        # Calculate averages
        if stats["actions_per_sequence"]:
            stats["avg_actions_per_sequence"] = sum(stats["actions_per_sequence"]) / len(stats["actions_per_sequence"])
        else:
            stats["avg_actions_per_sequence"] = 0

        return stats


def generate_chatml_examples(sequences: List[ExtractedSequence]) -> Generator[str, None, None]:
    """Convert extracted sequences to ChatML format for training."""
    for seq in sequences:
        # Build tool call representation
        tool_calls_str = ""
        for action in seq.actions:
            tool = action["tool"]
            args = json.dumps(action["args"])
            tool_calls_str += f"<tool_call>{tool}({args})</tool_call>\n"

        # Format the example
        example = f"""<|im_start|>system
You control an OSRS automation system via MCP tools. Execute tools directly - never describe them as JSON.
<|im_end|>
<|im_start|>user
{seq.user_intent}
<|im_end|>
<|im_start|>assistant
{tool_calls_str.strip()}
{seq.response}
<|im_end|>"""

        yield example


def main():
    """CLI for Claude session parsing."""
    import argparse

    parser = argparse.ArgumentParser(description="Parse Claude Code sessions for training data")
    parser.add_argument("--session-dir", "-d",
                        help="Claude sessions directory")
    parser.add_argument("--output", "-o", default="fine_tuning/data/extracted/claude_sessions.jsonl",
                        help="Output file path")
    parser.add_argument("--max-sessions", "-n", type=int,
                        help="Maximum sessions to process")
    parser.add_argument("--stats", action="store_true",
                        help="Show statistics only")
    parser.add_argument("--chatml", action="store_true",
                        help="Also export ChatML format")

    args = parser.parse_args()

    csp = ClaudeSessionParser(args.session_dir)

    if args.stats:
        print("Analyzing sessions (this may take a moment)...")
        stats = csp.get_stats(args.max_sessions)

        print(f"\nSessions processed: {stats['sessions_processed']}")
        print(f"Total training sequences: {stats['total_sequences']}")
        print(f"Avg actions per sequence: {stats['avg_actions_per_sequence']:.1f}")

        print("\nBy task type:")
        for t, c in sorted(stats["by_task_type"].items(), key=lambda x: -x[1]):
            print(f"  {t}: {c}")

        print("\nTop tools used:")
        for tool, count in sorted(stats["tools_used"].items(), key=lambda x: -x[1])[:15]:
            print(f"  {tool}: {count}")

    else:
        print(f"Processing sessions from {csp.session_dir}...")
        count = csp.export_training_data(args.output, args.max_sessions)
        print(f"Exported {count} training sequences to {args.output}")

        if args.chatml:
            chatml_path = args.output.replace(".jsonl", "_chatml.txt")
            sequences = []
            with open(args.output) as f:
                for line in f:
                    seq_dict = json.loads(line)
                    sequences.append(ExtractedSequence(**seq_dict))

            with open(chatml_path, "w") as f:
                for example in generate_chatml_examples(sequences):
                    f.write(example + "\n\n---\n\n")

            print(f"Exported ChatML examples to {chatml_path}")


if __name__ == "__main__":
    main()
