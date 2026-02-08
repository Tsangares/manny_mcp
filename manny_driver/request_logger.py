"""JSONL request logger for tracking LLM costs per session."""
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .config import get_token_cost

LOG_PATH = Path("/tmp/manny_driver_requests.jsonl")


class RequestLogger:
    """Append one JSONL line per LLM request to a shared log file."""

    def __init__(self):
        self.session_id = uuid.uuid4().hex[:12]

    def log(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
        directive: str = "",
        phase: str = "execution",
    ):
        cost = get_token_cost(model, input_tokens, output_tokens)
        record = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "session_id": self.session_id,
            "model": model,
            "in": input_tokens,
            "out": output_tokens,
            "cost_usd": round(cost, 8),
            "directive": (directive or "")[:100],
            "phase": phase,
        }
        with open(LOG_PATH, "a") as f:
            f.write(json.dumps(record) + "\n")
