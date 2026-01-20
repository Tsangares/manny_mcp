# Claude Code Session Parser - Implementation Plan

**Purpose**: Extract training data from Claude Code sessions for fine-tuning the LLM controller.

---

## Why Claude Code Sessions are Valuable

Claude Code sessions contain the **gold standard** of training data because they show:

1. **Complex multi-step reasoning** - Not just "kill frogs" but "go to bank, withdraw food, go to swamp, start killing"
2. **State-based decisions** - "Health is low, eat food before continuing"
3. **Error recovery** - "Command failed, check logs, fix and retry"
4. **Task transitions** - "Fishing done, now switch to combat routine"
5. **Tool orchestration** - Multiple MCP tools used in sequence

---

## Session File Format

Claude Code sessions are stored at:
```
~/.claude/projects/-home-wil-manny-mcp/*.jsonl
```

### Message Types

```jsonl
{"type": "user", "message": {"role": "user", "content": "..."}, ...}
{"type": "assistant", "message": {"role": "assistant", "content": [...]}, ...}
```

### Assistant Content Blocks

```json
{
  "content": [
    {"type": "thinking", "thinking": "..."},
    {"type": "text", "text": "..."},
    {"type": "tool_use", "id": "...", "name": "mcp__manny__send_command", "input": {...}}
  ]
}
```

### Tool Results

```json
{"type": "tool_result", "tool_use_id": "...", "content": "..."}
```

---

## Relevant MCP Tools to Extract

Only extract examples involving these tools (game control):

| MCP Tool Name | Purpose |
|---------------|---------|
| `mcp__manny__send_command` | Send raw commands to plugin |
| `mcp__manny__get_game_state` | Get player state |
| `mcp__manny__check_health` | Health check |
| `mcp__manny__get_screenshot` | Visual state |
| `mcp__manny__get_logs` | Debug logs |
| `mcp__manny__run_routine` | Run YAML routines |
| `mcp__manny__start_runelite` | Start client |
| `mcp__manny__stop_runelite` | Stop client |
| `mcp__manny__query_nearby` | Nearby entities |
| `mcp__manny__get_transitions` | Doors/stairs |

**Ignore** tools like:
- `Read`, `Write`, `Edit` (code editing, not game control)
- `Bash`, `Glob`, `Grep` (file operations)
- `Task` (subagent spawning)

---

## Parser Implementation

### File: `discord_bot/claude_session_parser.py`

```python
"""
Parser for Claude Code sessions to extract training examples.

Extracts game control interactions from Claude Code JSONL files
and converts them to the training data format.
"""
import json
import re
from pathlib import Path
from typing import List, Dict, Optional, Generator
from datetime import datetime

# MCP tools related to game control
GAME_CONTROL_TOOLS = {
    "mcp__manny__send_command",
    "mcp__manny__get_game_state",
    "mcp__manny__check_health",
    "mcp__manny__get_screenshot",
    "mcp__manny__get_logs",
    "mcp__manny__run_routine",
    "mcp__manny__start_runelite",
    "mcp__manny__stop_runelite",
    "mcp__manny__restart_runelite",
    "mcp__manny__query_nearby",
    "mcp__manny__get_transitions",
    "mcp__manny__send_and_await",
    "mcp__manny__click_text",
    "mcp__manny__find_widget",
}

# Simplified tool names for training
TOOL_NAME_MAP = {
    "mcp__manny__send_command": "send_command",
    "mcp__manny__get_game_state": "get_game_state",
    "mcp__manny__check_health": "check_health",
    "mcp__manny__get_screenshot": "get_screenshot",
    "mcp__manny__get_logs": "get_logs",
    "mcp__manny__run_routine": "run_routine",
    "mcp__manny__start_runelite": "start_runelite",
    "mcp__manny__stop_runelite": "stop_runelite",
    "mcp__manny__restart_runelite": "restart_runelite",
    "mcp__manny__query_nearby": "query_nearby",
    "mcp__manny__get_transitions": "get_transitions",
    "mcp__manny__send_and_await": "send_and_await",
    "mcp__manny__click_text": "click_text",
    "mcp__manny__find_widget": "find_widget",
}


class ClaudeSessionParser:
    """Parse Claude Code sessions for training data extraction."""

    def __init__(self, session_dir: str = None):
        self.session_dir = Path(session_dir or
            "~/.claude/projects/-home-wil-manny-mcp").expanduser()

    def list_sessions(self) -> List[Path]:
        """List all session files."""
        return sorted(self.session_dir.glob("*.jsonl"))

    def parse_session(self, session_path: Path) -> Generator[Dict, None, None]:
        """Parse a single session file and yield training examples."""
        messages = list(self._read_messages(session_path))

        i = 0
        while i < len(messages):
            msg = messages[i]

            # Look for user messages
            if msg.get("type") == "user":
                user_content = self._extract_user_content(msg)

                # Find the corresponding assistant response
                if i + 1 < len(messages) and messages[i + 1].get("type") == "assistant":
                    assistant_msg = messages[i + 1]
                    tool_calls = self._extract_tool_calls(assistant_msg)
                    text_response = self._extract_text_response(assistant_msg)

                    # Only yield if there were game control tool calls
                    game_tools = [tc for tc in tool_calls
                                  if tc["tool"] in TOOL_NAME_MAP.values()]

                    if game_tools:
                        yield {
                            "source": "claude_code",
                            "session_id": session_path.stem,
                            "timestamp": msg.get("timestamp"),
                            "input": {
                                "user_message": user_content,
                                "task_type": self._infer_task_type(user_content, game_tools)
                            },
                            "expected_actions": [
                                {"tool": tc["tool"], "args": tc["args"]}
                                for tc in game_tools
                            ],
                            "execution_trace": {
                                "tool_calls": tool_calls,
                                "response": text_response
                            },
                            "quality": {
                                "success": True,  # Assume success if tools were called
                                "had_errors": "error" in text_response.lower(),
                                "described_instead_of_executed": False
                            }
                        }
            i += 1

    def _read_messages(self, path: Path) -> Generator[Dict, None, None]:
        """Read and parse JSONL file."""
        with open(path) as f:
            for line in f:
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    continue

    def _extract_user_content(self, msg: Dict) -> str:
        """Extract user message content."""
        message = msg.get("message", {})
        content = message.get("content", "")
        if isinstance(content, str):
            return content
        elif isinstance(content, list):
            # Handle content blocks
            texts = [c.get("text", "") for c in content if c.get("type") == "text"]
            return " ".join(texts)
        return str(content)

    def _extract_tool_calls(self, msg: Dict) -> List[Dict]:
        """Extract tool calls from assistant message."""
        tool_calls = []
        message = msg.get("message", {})
        content = message.get("content", [])

        if not isinstance(content, list):
            return tool_calls

        for block in content:
            if block.get("type") == "tool_use":
                tool_name = block.get("name", "")
                # Map to simplified name
                simple_name = TOOL_NAME_MAP.get(tool_name)
                if simple_name:
                    tool_calls.append({
                        "tool": simple_name,
                        "args": block.get("input", {}),
                        "id": block.get("id")
                    })

        return tool_calls

    def _extract_text_response(self, msg: Dict) -> str:
        """Extract text response from assistant message."""
        message = msg.get("message", {})
        content = message.get("content", [])

        if not isinstance(content, list):
            return ""

        texts = []
        for block in content:
            if block.get("type") == "text":
                texts.append(block.get("text", ""))

        return " ".join(texts)

    def _infer_task_type(self, user_message: str, tool_calls: List[Dict]) -> str:
        """Infer task type from message and tools used."""
        msg_lower = user_message.lower()
        tools_used = {tc["tool"] for tc in tool_calls}

        # Check for status queries
        if tools_used <= {"get_game_state", "check_health", "get_screenshot"}:
            if any(w in msg_lower for w in ["status", "level", "health", "where", "check"]):
                return "status_query"

        # Check for loop commands
        for tc in tool_calls:
            if tc["tool"] == "send_command":
                cmd = tc["args"].get("command", "")
                if "LOOP" in cmd:
                    return "loop_command"

        # Check for multi-step (multiple send_commands)
        send_commands = [tc for tc in tool_calls if tc["tool"] == "send_command"]
        if len(send_commands) > 1:
            return "multi_step"

        # Check for simple commands
        if send_commands:
            return "simple_command"

        return "conversation"

    def export_all(self, output_path: str, min_tool_calls: int = 1) -> int:
        """Export all sessions to training format."""
        examples = []

        for session_path in self.list_sessions():
            for example in self.parse_session(session_path):
                if len(example["expected_actions"]) >= min_tool_calls:
                    examples.append(example)

        with open(output_path, "w") as f:
            for ex in examples:
                f.write(json.dumps(ex) + "\n")

        return len(examples)


def main():
    """CLI for parsing Claude sessions."""
    import argparse

    parser = argparse.ArgumentParser(description="Parse Claude Code sessions for training data")
    parser.add_argument("--output", "-o", default="claude_training_data.jsonl",
                        help="Output file path")
    parser.add_argument("--session-dir", "-d",
                        help="Claude sessions directory")
    parser.add_argument("--min-tools", type=int, default=1,
                        help="Minimum tool calls per example")
    parser.add_argument("--stats", action="store_true",
                        help="Show statistics only")

    args = parser.parse_args()

    parser = ClaudeSessionParser(args.session_dir)

    if args.stats:
        total = 0
        by_type = {}
        for session in parser.list_sessions():
            for ex in parser.parse_session(session):
                total += 1
                task_type = ex["input"]["task_type"]
                by_type[task_type] = by_type.get(task_type, 0) + 1

        print(f"Total examples: {total}")
        print("By task type:")
        for t, c in sorted(by_type.items(), key=lambda x: -x[1]):
            print(f"  {t}: {c}")
    else:
        count = parser.export_all(args.output, args.min_tools)
        print(f"Exported {count} training examples to {args.output}")


if __name__ == "__main__":
    main()
```

---

## Usage

### Extract Statistics
```bash
python discord_bot/claude_session_parser.py --stats
```

### Export Training Data
```bash
python discord_bot/claude_session_parser.py -o claude_training.jsonl
```

### Combine with Discord Data
```bash
cat ~/.manny/training_data/training_*.jsonl claude_training.jsonl > combined_training.jsonl
```

---

## Filtering and Quality

### Examples to Include

- Tool calls actually executed (not described)
- Game state observations followed by actions
- Multi-step task completions
- Error recovery sequences

### Examples to Exclude

- Code editing interactions (Read/Write/Edit tools)
- Pure conversation without tool calls
- Failed/errored interactions
- Very long reasoning chains (>10 tool calls)

### Quality Scoring

Add human annotation for:
- **Relevance**: Is this about game control? (1-5)
- **Correctness**: Was the action appropriate? (1-5)
- **Efficiency**: Was this the best approach? (1-5)

---

## Integration with Training Pipeline

```python
from discord_bot.claude_session_parser import ClaudeSessionParser
from discord_bot.training_logger import export_for_finetuning

# Parse Claude sessions
parser = ClaudeSessionParser()
parser.export_all("claude_examples.jsonl")

# Combine with Discord data and export for fine-tuning
# (merge files, then run export_for_finetuning)
```

---

## Expected Output

From a session like:
```
User: "Go kill some giant frogs at the swamp"
Claude: [thinking] User wants to start combat...
        [tool_use] get_game_state(location)
        [tool_use] send_command(GOTO 3197 3169 0)
        [tool_use] send_command(KILL_LOOP Giant_frog none)
        [text] "Walking to swamp and starting to kill frogs."
```

Extracted training example:
```json
{
  "input": {
    "user_message": "Go kill some giant frogs at the swamp",
    "task_type": "multi_step"
  },
  "expected_actions": [
    {"tool": "get_game_state", "args": {"fields": ["location"]}},
    {"tool": "send_command", "args": {"command": "GOTO 3197 3169 0"}},
    {"tool": "send_command", "args": {"command": "KILL_LOOP Giant_frog none"}}
  ],
  "execution_trace": {
    "response": "Walking to swamp and starting to kill frogs."
  }
}
```
