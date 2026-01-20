"""
Unified Training Schema - Combine all data sources into training format.

This module:
1. Defines the unified training example schema
2. Converts journal examples, Claude sessions, and Discord logs to unified format
3. Exports to fine-tuning formats (ChatML, JSONL for Axolotl/Unsloth)

The key insight: We have THREE types of training data:
1. Direct execution: "kill frogs" → send_command(KILL_LOOP Frog)
2. Reasoning chains: Problem → Observation → Root cause → Fix
3. Negative examples: What NOT to do (describe tool instead of execute)
"""

import json
from pathlib import Path
from dataclasses import dataclass, asdict, field
from typing import List, Dict, Optional, Generator, Union
from enum import Enum
from datetime import datetime


class ExampleType(Enum):
    """Types of training examples."""
    DIRECT_EXECUTION = "direct_execution"  # User intent → tool call
    REASONING_CHAIN = "reasoning_chain"    # Problem → analysis → solution
    CODE_CORRECTION = "code_correction"    # Bad code → good code
    NEGATIVE = "negative"                   # What NOT to do
    MULTI_STEP = "multi_step"              # Complex task with multiple steps


@dataclass
class ToolAction:
    """A tool call with optional result."""
    tool: str
    arguments: Dict
    result: Optional[Dict] = None


@dataclass
class UnifiedTrainingExample:
    """Unified training example format."""
    id: str
    source: str  # "journal", "claude_session", "discord"
    source_file: Optional[str] = None

    example_type: str = "direct_execution"

    # Input context
    user_message: str = ""
    game_state: Optional[Dict] = None
    context: Optional[str] = None  # Additional context

    # Expected output
    tool_calls: List[ToolAction] = field(default_factory=list)
    response_text: str = ""

    # For reasoning examples
    reasoning: Optional[str] = None
    problem: Optional[str] = None
    root_cause: Optional[str] = None

    # For code correction
    bad_code: Optional[str] = None
    good_code: Optional[str] = None

    # Metadata
    task_type: str = "simple_command"  # loop_command, multi_step, status_query, etc.
    tags: List[str] = field(default_factory=list)
    quality_score: float = 1.0  # 0.0 to 1.0


class TrainingDataCombiner:
    """Combine all data sources into unified format."""

    def __init__(self, data_dir: str = "fine_tuning/data/extracted"):
        self.data_dir = Path(data_dir)

    def _generate_id(self, source: str, index: int) -> str:
        """Generate unique example ID."""
        return f"{source}_{index:06d}"

    def load_journal_examples(self) -> Generator[UnifiedTrainingExample, None, None]:
        """Load and convert journal training examples."""
        journal_path = self.data_dir / "journal_training.jsonl"
        if not journal_path.exists():
            return

        index = 0
        with open(journal_path) as f:
            for line in f:
                data = json.loads(line)
                example_type = data.get("type", "unknown")

                if example_type == "reasoning":
                    yield UnifiedTrainingExample(
                        id=self._generate_id("journal", index),
                        source="journal",
                        source_file=data.get("source"),
                        example_type=ExampleType.REASONING_CHAIN.value,
                        problem=data.get("input", "").replace("Problem: ", ""),
                        reasoning=data.get("reasoning", "").replace("Root cause: ", ""),
                        tags=data.get("tags", []),
                    )

                elif example_type == "code_correction":
                    yield UnifiedTrainingExample(
                        id=self._generate_id("journal", index),
                        source="journal",
                        source_file=data.get("source"),
                        example_type=ExampleType.CODE_CORRECTION.value,
                        bad_code=data.get("bad_code"),
                        good_code=data.get("good_code"),
                        context=data.get("bad_explanation"),
                        tags=data.get("tags", []),
                    )

                elif example_type == "anti_pattern":
                    yield UnifiedTrainingExample(
                        id=self._generate_id("journal", index),
                        source="journal",
                        source_file=data.get("source"),
                        example_type=ExampleType.NEGATIVE.value,
                        user_message=data.get("pattern", ""),
                        context=data.get("reason"),
                        tags=data.get("tags", []),
                    )

                elif example_type == "command_usage":
                    # Convert to direct execution example
                    cmd = data.get("command", "")
                    example = data.get("example", "")
                    purpose = data.get("purpose", "")

                    yield UnifiedTrainingExample(
                        id=self._generate_id("journal", index),
                        source="journal",
                        source_file=data.get("source"),
                        example_type=ExampleType.DIRECT_EXECUTION.value,
                        user_message=purpose,
                        tool_calls=[ToolAction(tool=cmd, arguments={"example": example})],
                        response_text=f"Executed {cmd}",
                        tags=data.get("tags", []),
                    )

                elif example_type == "lesson":
                    yield UnifiedTrainingExample(
                        id=self._generate_id("journal", index),
                        source="journal",
                        source_file=data.get("source"),
                        example_type=ExampleType.REASONING_CHAIN.value,
                        problem=data.get("problem"),
                        reasoning=data.get("why"),
                        response_text=data.get("solution", ""),
                        context=data.get("title"),
                        tags=data.get("tags", []),
                    )

                index += 1

    def load_claude_session_examples(self) -> Generator[UnifiedTrainingExample, None, None]:
        """Load and convert Claude session examples."""
        session_path = self.data_dir / "claude_sessions.jsonl"
        if not session_path.exists():
            return

        index = 0
        with open(session_path) as f:
            for line in f:
                data = json.loads(line)

                # Convert actions to ToolAction objects
                tool_calls = []
                for action in data.get("actions", []):
                    tool_calls.append(ToolAction(
                        tool=action.get("tool", ""),
                        arguments=action.get("args", {}),
                    ))

                # Determine example type
                if len(tool_calls) > 2:
                    example_type = ExampleType.MULTI_STEP.value
                else:
                    example_type = ExampleType.DIRECT_EXECUTION.value

                yield UnifiedTrainingExample(
                    id=self._generate_id("claude", index),
                    source="claude_session",
                    source_file=data.get("session_id"),
                    example_type=example_type,
                    user_message=data.get("user_intent", ""),
                    tool_calls=tool_calls,
                    response_text=data.get("response", ""),
                    task_type=data.get("task_type", "simple_command"),
                )

                index += 1

    def load_discord_examples(self) -> Generator[UnifiedTrainingExample, None, None]:
        """Load and convert Discord conversation examples."""
        # Discord logs are in logs/conversations/
        discord_dir = Path("logs/conversations")
        if not discord_dir.exists():
            return

        index = 0
        for log_file in sorted(discord_dir.glob("*.jsonl")):
            # Group by request_id
            requests = {}
            with open(log_file) as f:
                for line in f:
                    try:
                        data = json.loads(line)
                        req_id = data.get("request_id")
                        if req_id:
                            if req_id not in requests:
                                requests[req_id] = {"tools": [], "response": "", "request": ""}
                            if data.get("type") == "request":
                                requests[req_id]["request"] = data.get("message", "")
                                requests[req_id]["task_type"] = data.get("task_type", "")
                            elif data.get("type") == "tool_call":
                                requests[req_id]["tools"].append({
                                    "tool": data.get("tool", ""),
                                    "args": data.get("arguments", {}),
                                })
                            elif data.get("type") == "response":
                                requests[req_id]["response"] = data.get("response", "")
                    except json.JSONDecodeError:
                        continue

            # Convert to training examples
            for req_id, req_data in requests.items():
                if not req_data["tools"]:
                    continue

                tool_calls = [
                    ToolAction(tool=t["tool"], arguments=t["args"])
                    for t in req_data["tools"]
                ]

                yield UnifiedTrainingExample(
                    id=self._generate_id("discord", index),
                    source="discord",
                    source_file=str(log_file),
                    example_type=ExampleType.DIRECT_EXECUTION.value,
                    user_message=req_data["request"],
                    tool_calls=tool_calls,
                    response_text=req_data["response"],
                    task_type=req_data.get("task_type", "simple_command"),
                )
                index += 1

    def load_all(self) -> Generator[UnifiedTrainingExample, None, None]:
        """Load all examples from all sources."""
        yield from self.load_journal_examples()
        yield from self.load_claude_session_examples()
        yield from self.load_discord_examples()

    def export_unified(self, output_path: str) -> int:
        """Export all examples in unified JSONL format."""
        count = 0
        with open(output_path, "w") as f:
            for example in self.load_all():
                # Convert ToolAction objects to dicts for serialization
                example_dict = asdict(example)
                example_dict["tool_calls"] = [
                    {"tool": tc.tool, "arguments": tc.arguments, "result": tc.result}
                    for tc in example.tool_calls
                ]
                f.write(json.dumps(example_dict) + "\n")
                count += 1
        return count


class ChatMLExporter:
    """Export training examples to ChatML format for fine-tuning."""

    SYSTEM_PROMPT = """You control an OSRS automation system via MCP tools.

CRITICAL RULES:
1. Execute tools directly - NEVER describe them as JSON text
2. Observe game state before acting when needed
3. Use appropriate tool for the task (send_command for game actions, get_game_state for queries)
4. Keep responses brief and action-focused

Available tools: send_command, send_and_await, get_game_state, get_logs, check_health, click_text, query_nearby, start_runelite, stop_runelite"""

    def __init__(self, include_reasoning: bool = False):
        self.include_reasoning = include_reasoning

    def format_example(self, example: UnifiedTrainingExample) -> str:
        """Format a single example as ChatML."""
        # Build tool call representation
        tool_calls_str = ""
        for tc in example.tool_calls:
            if tc.tool:
                args_str = json.dumps(tc.arguments) if tc.arguments else "{}"
                tool_calls_str += f"<tool_call>{tc.tool}({args_str})</tool_call>\n"

        # Build state context if available
        state_context = ""
        if example.game_state:
            loc = example.game_state.get("location", {})
            health = example.game_state.get("health", {})
            if loc:
                state_context = f"[State: loc=({loc.get('x')},{loc.get('y')},{loc.get('plane')}) "
            if health:
                state_context += f"hp={health.get('current')}/{health.get('max')}]"
            if state_context:
                state_context = state_context.strip() + "\n"

        # Format based on example type
        if example.example_type == ExampleType.DIRECT_EXECUTION.value:
            return f"""<|im_start|>system
{self.SYSTEM_PROMPT}
<|im_end|>
<|im_start|>user
{state_context}{example.user_message}
<|im_end|>
<|im_start|>assistant
{tool_calls_str.strip()}
{example.response_text}
<|im_end|>"""

        elif example.example_type == ExampleType.REASONING_CHAIN.value:
            reasoning_section = ""
            if self.include_reasoning and example.reasoning:
                reasoning_section = f"\n<thinking>{example.reasoning}</thinking>\n"

            return f"""<|im_start|>system
{self.SYSTEM_PROMPT}
<|im_end|>
<|im_start|>user
Problem: {example.problem}
<|im_end|>
<|im_start|>assistant{reasoning_section}
{example.response_text}
<|im_end|>"""

        elif example.example_type == ExampleType.NEGATIVE.value:
            return f"""<|im_start|>system
{self.SYSTEM_PROMPT}
TRAINING NOTE: The following shows what NOT to do.
<|im_end|>
<|im_start|>user
{example.user_message}
<|im_end|>
<|im_start|>assistant
[BAD - DO NOT DO THIS]
Reason: {example.context}
<|im_end|>"""

        else:
            return ""

    def export(self, examples: List[UnifiedTrainingExample], output_path: str) -> int:
        """Export examples to ChatML format."""
        count = 0
        with open(output_path, "w") as f:
            for example in examples:
                formatted = self.format_example(example)
                if formatted:
                    f.write(formatted + "\n\n")
                    count += 1
        return count


class AxolotlExporter:
    """Export to Axolotl JSONL format for fine-tuning."""

    def format_example(self, example: UnifiedTrainingExample) -> Optional[Dict]:
        """Format for Axolotl training."""
        if example.example_type != ExampleType.DIRECT_EXECUTION.value:
            return None

        # Build tool call representation
        tool_calls_str = ""
        for tc in example.tool_calls:
            if tc.tool:
                args_str = json.dumps(tc.arguments) if tc.arguments else "{}"
                tool_calls_str += f"<tool_call>{tc.tool}({args_str})</tool_call>\n"

        return {
            "instruction": example.user_message,
            "input": "",
            "output": f"{tool_calls_str.strip()}\n{example.response_text}".strip(),
        }

    def export(self, examples: List[UnifiedTrainingExample], output_path: str) -> int:
        """Export to Axolotl format."""
        count = 0
        with open(output_path, "w") as f:
            for example in examples:
                formatted = self.format_example(example)
                if formatted:
                    f.write(json.dumps(formatted) + "\n")
                    count += 1
        return count


def main():
    """CLI for training data combination and export."""
    import argparse

    parser = argparse.ArgumentParser(description="Combine and export training data")
    parser.add_argument("--data-dir", "-d", default="fine_tuning/data/extracted",
                        help="Extracted data directory")
    parser.add_argument("--output-dir", "-o", default="fine_tuning/data/training",
                        help="Output directory for training data")
    parser.add_argument("--format", "-f", choices=["unified", "chatml", "axolotl", "all"],
                        default="all", help="Output format")
    parser.add_argument("--stats", action="store_true",
                        help="Show statistics only")

    args = parser.parse_args()

    combiner = TrainingDataCombiner(args.data_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.stats:
        examples = list(combiner.load_all())
        print(f"Total examples: {len(examples)}")

        by_source = {}
        by_type = {}
        by_task = {}

        for ex in examples:
            by_source[ex.source] = by_source.get(ex.source, 0) + 1
            by_type[ex.example_type] = by_type.get(ex.example_type, 0) + 1
            by_task[ex.task_type] = by_task.get(ex.task_type, 0) + 1

        print("\nBy source:")
        for s, c in sorted(by_source.items(), key=lambda x: -x[1]):
            print(f"  {s}: {c}")

        print("\nBy example type:")
        for t, c in sorted(by_type.items(), key=lambda x: -x[1]):
            print(f"  {t}: {c}")

        print("\nBy task type:")
        for t, c in sorted(by_task.items(), key=lambda x: -x[1]):
            print(f"  {t}: {c}")

    else:
        examples = list(combiner.load_all())

        if args.format in ("unified", "all"):
            count = combiner.export_unified(str(output_dir / "unified.jsonl"))
            print(f"Exported {count} examples to unified.jsonl")

        if args.format in ("chatml", "all"):
            exporter = ChatMLExporter()
            count = exporter.export(examples, str(output_dir / "chatml.txt"))
            print(f"Exported {count} examples to chatml.txt")

        if args.format in ("axolotl", "all"):
            exporter = AxolotlExporter()
            count = exporter.export(examples, str(output_dir / "axolotl.jsonl"))
            print(f"Exported {count} examples to axolotl.jsonl")


if __name__ == "__main__":
    main()
