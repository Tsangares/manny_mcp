"""
Training data logger for fine-tuning LLM controllers.

Captures the full context needed to train a model on:
1. Tool execution (not description)
2. State-based decision making
3. Multi-step task decomposition
4. Error recovery

Data format designed for instruction fine-tuning.
"""
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
import logging

logger = logging.getLogger("training_logger")

# Training data directory
TRAINING_DIR = Path(os.environ.get("TRAINING_DATA_DIR",
                                    os.path.expanduser("~/.manny/training_data")))


class TrainingExample:
    """A single training example capturing the full interaction loop."""

    def __init__(self, request_id: str, source: str = "discord"):
        self.request_id = request_id
        self.source = source  # discord, mcp, claude_code
        self.timestamp = datetime.now().isoformat()

        # Input context
        self.user_message: str = ""
        self.task_type: str = ""
        self.game_state_before: Optional[Dict] = None
        self.conversation_history: List[Dict] = []

        # Execution trace
        self.tool_calls: List[Dict] = []  # [{tool, args, result, latency_ms}]
        self.reasoning: Optional[str] = None  # If model explained its thinking

        # Output
        self.response: str = ""
        self.game_state_after: Optional[Dict] = None

        # Quality signals
        self.success: Optional[bool] = None  # Did the user's intent get fulfilled?
        self.had_errors: bool = False
        self.user_feedback: Optional[str] = None  # Corrective feedback if any
        self.human_rating: Optional[int] = None  # 1-5 rating for quality

    def add_tool_call(self, tool: str, args: Dict, result: Any, latency_ms: int = 0):
        """Record a tool call in the execution trace."""
        self.tool_calls.append({
            "tool": tool,
            "args": args,
            "result": self._safe_serialize(result),
            "latency_ms": latency_ms
        })

    def _safe_serialize(self, obj: Any) -> Any:
        """Safely serialize objects for JSON."""
        if obj is None:
            return None
        if isinstance(obj, (str, int, float, bool)):
            return obj
        if isinstance(obj, dict):
            return {k: self._safe_serialize(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return [self._safe_serialize(item) for item in obj]
        return str(obj)

    def to_training_format(self) -> Dict:
        """Export in format suitable for fine-tuning."""
        return {
            "id": self.request_id,
            "timestamp": self.timestamp,
            "source": self.source,

            # Input (what the model sees)
            "input": {
                "user_message": self.user_message,
                "task_type": self.task_type,
                "game_state": self._compact_state(self.game_state_before),
                "history_summary": self._summarize_history()
            },

            # Expected output (what we want the model to do)
            "expected_actions": [
                {"tool": tc["tool"], "args": tc["args"]}
                for tc in self.tool_calls
            ],

            # Full trace for analysis
            "execution_trace": {
                "tool_calls": self.tool_calls,
                "response": self.response,
                "state_after": self._compact_state(self.game_state_after)
            },

            # Quality signals for filtering training data
            "quality": {
                "success": self.success,
                "had_errors": self.had_errors,
                "user_feedback": self.user_feedback,
                "human_rating": self.human_rating,
                "tool_call_count": len(self.tool_calls),
                "described_instead_of_executed": self._check_description_pattern()
            }
        }

    def _compact_state(self, state: Optional[Dict]) -> Optional[Dict]:
        """Create compact state representation for training."""
        if not state:
            return None

        compact = {}
        if "player" in state:
            p = state["player"]
            if "location" in p:
                loc = p["location"]
                compact["location"] = [loc.get("x"), loc.get("y"), loc.get("plane")]
            if "health" in p:
                h = p["health"]
                compact["health"] = [h.get("current"), h.get("max")]
            if "inventory" in p:
                inv = p["inventory"]
                compact["inventory_used"] = inv.get("used", 0)
        return compact

    def _summarize_history(self) -> str:
        """Summarize conversation history."""
        if not self.conversation_history:
            return "none"
        return f"{len(self.conversation_history)} prior messages"

    def _check_description_pattern(self) -> bool:
        """Check if response describes tool calls instead of executing them."""
        bad_patterns = [
            '{"name":',
            '"tool":',
            'send_command',
            'I would use',
            'you would need to',
            'the command is'
        ]
        response_lower = self.response.lower()
        return any(p.lower() in response_lower for p in bad_patterns) and len(self.tool_calls) == 0


class TrainingLogger:
    """Manages training data collection and export."""

    def __init__(self):
        TRAINING_DIR.mkdir(parents=True, exist_ok=True)
        self._current_examples: Dict[str, TrainingExample] = {}
        self._today_file = TRAINING_DIR / f"training_{datetime.now().strftime('%Y-%m-%d')}.jsonl"

    def start_example(self, request_id: str, user_message: str,
                      task_type: str = "", source: str = "discord") -> TrainingExample:
        """Start tracking a new training example."""
        example = TrainingExample(request_id, source)
        example.user_message = user_message
        example.task_type = task_type
        self._current_examples[request_id] = example
        return example

    def get_example(self, request_id: str) -> Optional[TrainingExample]:
        """Get an in-progress example."""
        return self._current_examples.get(request_id)

    def complete_example(self, request_id: str, response: str,
                         success: Optional[bool] = None):
        """Complete and save a training example."""
        example = self._current_examples.pop(request_id, None)
        if not example:
            logger.warning(f"No example found for request_id: {request_id}")
            return

        example.response = response
        example.success = success

        # Auto-detect failure patterns
        if "error" in response.lower() or "failed" in response.lower():
            example.had_errors = True

        # Save to file
        self._save_example(example)

    def _save_example(self, example: TrainingExample):
        """Append example to today's training file."""
        try:
            with open(self._today_file, "a") as f:
                f.write(json.dumps(example.to_training_format()) + "\n")
            logger.debug(f"Saved training example: {example.request_id}")
        except Exception as e:
            logger.error(f"Failed to save training example: {e}")

    def add_user_feedback(self, request_id: str, feedback: str):
        """Record user's corrective feedback (useful for RLHF)."""
        # For completed examples, we'd need to update the file
        # For now, log it separately
        feedback_file = TRAINING_DIR / "user_feedback.jsonl"
        with open(feedback_file, "a") as f:
            f.write(json.dumps({
                "request_id": request_id,
                "timestamp": datetime.now().isoformat(),
                "feedback": feedback
            }) + "\n")


# Export functions for easy stats

def get_training_stats() -> Dict:
    """Get statistics about collected training data."""
    stats = {
        "total_examples": 0,
        "by_source": {},
        "by_task_type": {},
        "success_rate": 0,
        "described_instead_of_executed": 0
    }

    for file in TRAINING_DIR.glob("training_*.jsonl"):
        with open(file) as f:
            for line in f:
                try:
                    ex = json.loads(line)
                    stats["total_examples"] += 1

                    source = ex.get("source", "unknown")
                    stats["by_source"][source] = stats["by_source"].get(source, 0) + 1

                    task_type = ex.get("input", {}).get("task_type", "unknown")
                    stats["by_task_type"][task_type] = stats["by_task_type"].get(task_type, 0) + 1

                    if ex.get("quality", {}).get("success"):
                        stats["success_rate"] += 1
                    if ex.get("quality", {}).get("described_instead_of_executed"):
                        stats["described_instead_of_executed"] += 1
                except:
                    pass

    if stats["total_examples"] > 0:
        stats["success_rate"] = stats["success_rate"] / stats["total_examples"]

    return stats


def export_for_finetuning(output_path: str, min_quality: int = 3,
                          exclude_failures: bool = True) -> int:
    """Export training data in ChatML format for fine-tuning.

    Returns number of examples exported.
    """
    examples = []

    for file in TRAINING_DIR.glob("training_*.jsonl"):
        with open(file) as f:
            for line in f:
                try:
                    ex = json.loads(line)

                    # Filter by quality
                    quality = ex.get("quality", {})
                    if exclude_failures and quality.get("had_errors"):
                        continue
                    if quality.get("described_instead_of_executed"):
                        continue  # Never train on description pattern
                    rating = quality.get("human_rating")
                    if rating is not None and rating < min_quality:
                        continue

                    # Convert to ChatML format
                    chatml = _to_chatml(ex)
                    if chatml:
                        examples.append(chatml)
                except:
                    pass

    # Write output
    with open(output_path, "w") as f:
        for ex in examples:
            f.write(json.dumps(ex) + "\n")

    return len(examples)


def _to_chatml(example: Dict) -> Optional[Dict]:
    """Convert training example to ChatML format."""
    input_data = example.get("input", {})
    actions = example.get("expected_actions", [])
    trace = example.get("execution_trace", {})

    if not actions:
        return None  # Skip examples with no tool calls

    # Build user message with context
    user_content = input_data.get("user_message", "")
    state = input_data.get("game_state")
    if state:
        user_content = f"[Game State: {json.dumps(state)}]\n\n{user_content}"

    # Build assistant response with tool calls
    tool_calls_str = ""
    for action in actions:
        tool_calls_str += f"<tool_call>{action['tool']}({json.dumps(action['args'])})</tool_call>\n"

    response = trace.get("response", "Done.")
    assistant_content = f"{tool_calls_str}{response}"

    return {
        "messages": [
            {"role": "user", "content": user_content},
            {"role": "assistant", "content": assistant_content}
        ]
    }


# Global instance
training_logger = TrainingLogger()
