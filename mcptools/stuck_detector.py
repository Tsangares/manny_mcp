"""
Stuck detection for MCP command dispatch.

Tracks recent commands per account and compares game state snapshots.
If the same command is sent repeatedly with no meaningful state change,
warns and eventually blocks to prevent bot-like behavior loops.
"""
import os
import json
import time
import hashlib
from collections import defaultdict
from typing import Dict, Optional, Tuple


class StuckDetector:
    """
    Detects when the same command is being sent repeatedly with no game state change.

    Tracks a rolling window of (command, state_hash) pairs per account.
    If N consecutive identical pairs are seen, returns a warning/block signal.
    """

    # Thresholds
    WARN_THRESHOLD = 3       # Warn after 3 identical command+state pairs
    BLOCK_THRESHOLD = 6      # Block after 6 identical command+state pairs
    RESET_AFTER_SECONDS = 60  # Reset counter if >60s between commands

    def __init__(self):
        # Per-account tracking: {account_id: {"command": str, "state_hash": str, "count": int, "last_time": float}}
        self._trackers: Dict[str, dict] = defaultdict(lambda: {
            "command": None,
            "state_hash": None,
            "count": 0,
            "last_time": 0.0
        })

    def _normalize_command(self, command: str) -> str:
        """Normalize command for comparison (strip request IDs, whitespace)."""
        # Remove --rid=xxxx suffixes
        parts = command.strip().split()
        parts = [p for p in parts if not p.startswith("--rid=")]
        return " ".join(parts)

    def _hash_state(self, state: dict) -> str:
        """Create a hash of relevant game state fields for comparison."""
        if not state:
            return "no_state"

        # Extract the fields that matter for detecting "stuck"
        relevant = {}

        # Player location
        if "location" in state:
            loc = state["location"]
            relevant["loc"] = f"{loc.get('x')},{loc.get('y')},{loc.get('plane')}"

        # Dialogue state
        if "dialogue" in state:
            d = state["dialogue"]
            relevant["dlg_type"] = d.get("type", "none")
            relevant["dlg_opts"] = str(d.get("options", []))

        # Inventory count (not full contents - just slot count)
        if "inventory" in state:
            inv = state["inventory"]
            if isinstance(inv, dict):
                relevant["inv_used"] = inv.get("used", 0)

        # Combat state
        if "combat" in state:
            relevant["combat"] = state["combat"].get("state", "IDLE")

        # Health
        if "health" in state:
            h = state["health"]
            relevant["hp"] = f"{h.get('current')}/{h.get('max')}"

        # Gravestone
        if "gravestone" in state:
            g = state["gravestone"]
            relevant["grave"] = f"active={g.get('active')},death={g.get('inDeathsDomain')}"

        raw = json.dumps(relevant, sort_keys=True)
        return hashlib.md5(raw.encode()).hexdigest()[:12]

    def check_command(self, command: str, account_id: str = "default",
                      state: dict = None) -> Tuple[str, Optional[str]]:
        """
        Check if a command appears stuck (repeated with no state change).

        Args:
            command: The command being sent
            account_id: Account identifier
            state: Current game state dict (from state file)

        Returns:
            Tuple of (status, message):
            - ("ok", None) - command is fine
            - ("warn", "message") - command appears stuck, warning included
            - ("block", "message") - command is definitely stuck, should be blocked
        """
        tracker = self._trackers[account_id]
        now = time.time()
        normalized = self._normalize_command(command)
        state_hash = self._hash_state(state)

        # Reset if too much time has passed
        if now - tracker["last_time"] > self.RESET_AFTER_SECONDS:
            tracker["count"] = 0

        tracker["last_time"] = now

        # Check if same command + same state
        if tracker["command"] == normalized and tracker["state_hash"] == state_hash:
            tracker["count"] += 1
        else:
            # Different command or state changed - reset
            tracker["command"] = normalized
            tracker["state_hash"] = state_hash
            tracker["count"] = 1

        count = tracker["count"]

        if count >= self.BLOCK_THRESHOLD:
            return ("block",
                    f"STUCK DETECTED: '{normalized}' sent {count} times with identical game state. "
                    f"Command blocked. Change approach or wait {self.RESET_AFTER_SECONDS}s for auto-reset.")
        elif count >= self.WARN_THRESHOLD:
            return ("warn",
                    f"Possible stuck loop: '{normalized}' sent {count} times with no state change. "
                    f"Will block at {self.BLOCK_THRESHOLD} repeats.")
        else:
            return ("ok", None)

    def reset(self, account_id: str = None):
        """Reset stuck detection for an account (or all accounts)."""
        if account_id:
            if account_id in self._trackers:
                self._trackers[account_id] = {
                    "command": None, "state_hash": None,
                    "count": 0, "last_time": 0.0
                }
        else:
            self._trackers.clear()

    def get_status(self, account_id: str = "default") -> dict:
        """Get current stuck detection status for an account."""
        tracker = self._trackers.get(account_id, {})
        return {
            "command": tracker.get("command"),
            "repeat_count": tracker.get("count", 0),
            "warn_threshold": self.WARN_THRESHOLD,
            "block_threshold": self.BLOCK_THRESHOLD
        }


# Global singleton
stuck_detector = StuckDetector()
