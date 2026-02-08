"""Conversation history management with summarization for long sessions.

Maintains an active window of recent messages plus a rolling summary
of older messages. This prevents unbounded context growth during
multi-hour sessions.
"""
import logging
from dataclasses import dataclass, field

logger = logging.getLogger("manny_driver.conversation")


@dataclass
class ConversationStats:
    """Track token usage and costs across a session."""
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_tool_calls: int = 0
    total_llm_calls: int = 0
    estimated_cost: float = 0.0

    def record(self, input_tokens: int, output_tokens: int, tool_calls: int = 0):
        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens
        self.total_tool_calls += tool_calls
        self.total_llm_calls += 1

    @property
    def summary(self) -> str:
        return (
            f"LLM calls: {self.total_llm_calls}, "
            f"Tool calls: {self.total_tool_calls}, "
            f"Tokens: {self.total_input_tokens:,} in / {self.total_output_tokens:,} out | "
            f"Cost: ${self.estimated_cost:.4f}"
        )


class ConversationManager:
    """Manages conversation history with a sliding window and summarization.

    Keeps the last `window_size` messages in full, and summarizes older
    messages into a running summary that's prepended to the conversation.
    """

    def __init__(self, window_size: int = 40):
        self.window_size = window_size
        self.messages: list[dict] = []
        self.summary: str = ""
        self.stats = ConversationStats()

    def add_message(self, message: dict):
        """Add a message to the conversation history."""
        self.messages.append(message)
        self._maybe_summarize()

    def add_messages(self, messages: list[dict]):
        """Add multiple messages."""
        self.messages.extend(messages)
        self._maybe_summarize()

    def get_messages(self) -> list[dict]:
        """Get the messages to send to the LLM.

        Returns the active window, with summary prepended as a user message
        if there is overflow.
        """
        if self.summary:
            summary_msg = {
                "role": "user",
                "content": f"[Session summary so far: {self.summary}]",
            }
            return [summary_msg] + self.messages[-self.window_size:]
        return self.messages[-self.window_size:]

    def clear(self):
        """Reset conversation state."""
        self.messages.clear()
        self.summary = ""

    def _maybe_summarize(self):
        """If messages exceed window, summarize the overflow."""
        if len(self.messages) <= self.window_size:
            return

        # Messages that will be summarized (those falling out of the window)
        overflow = self.messages[: len(self.messages) - self.window_size]
        self.messages = self.messages[-self.window_size:]

        # Build a text summary from overflow messages
        summary_parts = []
        if self.summary:
            summary_parts.append(self.summary)

        for msg in overflow:
            role = msg.get("role", "?")
            content = msg.get("content", "")

            # Handle complex content (tool results, etc.)
            if isinstance(content, list):
                # Summarize tool calls/results compactly
                items = []
                for item in content:
                    if isinstance(item, dict):
                        if item.get("type") == "tool_use":
                            items.append(f"Called {item.get('name', '?')}")
                        elif item.get("type") == "tool_result":
                            text = item.get("content", "")
                            items.append(f"Result: {text[:100]}...")
                        elif item.get("type") == "text":
                            items.append(item.get("text", "")[:100])
                content = "; ".join(items) if items else str(content)[:200]
            elif isinstance(content, str) and len(content) > 200:
                content = content[:200] + "..."

            if role == "assistant":
                summary_parts.append(f"Agent: {content}")
            elif role == "user":
                summary_parts.append(f"User/System: {content}")

        self.summary = " | ".join(summary_parts[-20:])  # Keep last 20 summary items
        logger.debug(f"Summarized {len(overflow)} messages, summary length: {len(self.summary)}")
