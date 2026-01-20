"""
Dedicated conversation logger for the Discord bot.
Logs user messages, LLM responses, tool calls, and task classification
to a separate file for easy analysis.
"""
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List

# Create logs directory
LOGS_DIR = Path(__file__).parent.parent / "logs" / "conversations"
LOGS_DIR.mkdir(parents=True, exist_ok=True)


class ConversationLogger:
    """Logs bot conversations to structured files."""

    def __init__(self, log_dir: Path = LOGS_DIR):
        self.log_dir = log_dir
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # Get today's log file
        today = datetime.now().strftime("%Y-%m-%d")
        self.log_file = self.log_dir / f"conversations_{today}.jsonl"

        # Also set up a human-readable log
        self.readable_file = self.log_dir / f"conversations_{today}.log"

        # Configure file logger
        self.logger = logging.getLogger("conversation")
        self.logger.setLevel(logging.DEBUG)
        self.logger.propagate = False  # Don't send to root logger

        # Remove existing handlers to avoid duplicates
        self.logger.handlers.clear()

        # File handler for readable logs
        fh = logging.FileHandler(self.readable_file, encoding="utf-8")
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(logging.Formatter("%(message)s"))
        self.logger.addHandler(fh)

    def _write_json(self, entry: Dict[str, Any]):
        """Append a JSON entry to the log file."""
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, default=str) + "\n")

    def log_request(
        self,
        user_id: int,
        username: str,
        message: str,
        task_type: str,
        account_id: str
    ) -> str:
        """Log an incoming user request. Returns a request_id for correlation."""
        request_id = datetime.now().strftime("%H%M%S%f")[:10]
        timestamp = datetime.now().isoformat()

        entry = {
            "type": "request",
            "request_id": request_id,
            "timestamp": timestamp,
            "user_id": user_id,
            "username": username,
            "message": message,
            "task_type": task_type,
            "account_id": account_id,
        }
        self._write_json(entry)

        # Human readable
        self.logger.info(f"\n{'='*60}")
        self.logger.info(f"[{timestamp}] REQUEST {request_id}")
        self.logger.info(f"User: {username} ({user_id})")
        self.logger.info(f"Account: {account_id}")
        self.logger.info(f"Task Type: {task_type}")
        self.logger.info(f"Message: {message}")

        return request_id

    def log_context(
        self,
        request_id: str,
        enriched_context: Dict[str, Any]
    ):
        """Log the enriched context provided to the LLM."""
        entry = {
            "type": "context",
            "request_id": request_id,
            "timestamp": datetime.now().isoformat(),
            "context": enriched_context,
        }
        self._write_json(entry)

        # Human readable (abbreviated)
        hints = enriched_context.get("hints", [])
        commands = list(enriched_context.get("available_commands", {}).keys())
        self.logger.info(f"Context: commands={commands}, hints={len(hints)}")

    def log_tool_call(
        self,
        request_id: str,
        tool_name: str,
        arguments: Dict[str, Any],
        result: Any
    ):
        """Log a tool call made by the LLM."""
        entry = {
            "type": "tool_call",
            "request_id": request_id,
            "timestamp": datetime.now().isoformat(),
            "tool": tool_name,
            "arguments": arguments,
            "result": result,
        }
        self._write_json(entry)

        # Human readable
        args_str = json.dumps(arguments) if arguments else ""
        result_str = str(result)[:100] + "..." if len(str(result)) > 100 else str(result)
        self.logger.info(f"  TOOL: {tool_name}({args_str}) -> {result_str}")

    def log_response(
        self,
        request_id: str,
        response: str,
        tool_calls_count: int = 0,
        error: Optional[str] = None
    ):
        """Log the final LLM response."""
        entry = {
            "type": "response",
            "request_id": request_id,
            "timestamp": datetime.now().isoformat(),
            "response": response,
            "tool_calls_count": tool_calls_count,
            "error": error,
        }
        self._write_json(entry)

        # Human readable
        if error:
            self.logger.info(f"ERROR: {error}")
        else:
            self.logger.info(f"Tool calls: {tool_calls_count}")
            self.logger.info(f"Response: {response}")
        self.logger.info(f"{'='*60}\n")

    def log_error(
        self,
        request_id: str,
        error: str,
        context: Optional[Dict] = None
    ):
        """Log an error that occurred during processing."""
        entry = {
            "type": "error",
            "request_id": request_id,
            "timestamp": datetime.now().isoformat(),
            "error": error,
            "context": context,
        }
        self._write_json(entry)

        self.logger.error(f"ERROR [{request_id}]: {error}")


# Global instance
_logger: Optional[ConversationLogger] = None


def get_conversation_logger() -> ConversationLogger:
    """Get or create the global conversation logger."""
    global _logger
    if _logger is None:
        _logger = ConversationLogger()
    return _logger
