"""Multi-signal stuck/error detection for the agent.

Detects when the agent is stuck (repeating commands, position unchanged,
state stale) and provides recovery suggestions.
"""
import logging
import time
from collections import deque
from dataclasses import dataclass, field

logger = logging.getLogger("manny_driver.stuck")


@dataclass
class StuckSignals:
    """Accumulated signals that indicate the agent might be stuck."""
    repeated_commands: int = 0
    position_unchanged_checks: int = 0
    consecutive_errors: int = 0
    consecutive_observations: int = 0  # get_game_state called without actions
    last_position: tuple = (0, 0, 0)
    state_stale_seconds: float = 0.0

    @property
    def is_stuck(self) -> bool:
        return (
            self.repeated_commands >= 3
            or self.position_unchanged_checks >= 5
            or self.consecutive_errors >= 3
            or self.consecutive_observations >= 6
            or self.state_stale_seconds > 30
        )

    @property
    def reason(self) -> str:
        reasons = []
        if self.repeated_commands >= 3:
            reasons.append(f"same command repeated {self.repeated_commands}x")
        if self.position_unchanged_checks >= 5:
            reasons.append(f"position unchanged for {self.position_unchanged_checks} checks")
        if self.consecutive_errors >= 3:
            reasons.append(f"{self.consecutive_errors} consecutive errors")
        if self.consecutive_observations >= 4:
            reasons.append(f"observation loop ({self.consecutive_observations}x without action)")
        if self.state_stale_seconds > 30:
            reasons.append(f"state stale for {self.state_stale_seconds:.0f}s")
        return "; ".join(reasons) if reasons else "unknown"


class StuckDetector:
    """Detects when the agent is stuck and suggests recovery actions."""

    def __init__(self):
        self.recent_commands: deque[str] = deque(maxlen=10)
        self.recent_positions: deque[tuple] = deque(maxlen=10)
        self.recent_errors: deque[str] = deque(maxlen=10)
        self.signals = StuckSignals()
        self._last_check = time.time()

    # Observation-only tools (no game side-effects)
    OBSERVATION_TOOLS = {
        "get_game_state", "get_logs", "query_nearby", "check_health",
        "is_alive", "get_command_response", "get_dialogue", "find_widget",
        "scan_widgets", "scan_tile_objects", "get_transitions",
        "get_location_info", "get_screenshot",
    }

    def record_tool_call(self, tool_name: str):
        """Track tool calls for observation-loop detection."""
        if tool_name in self.OBSERVATION_TOOLS:
            self.signals.consecutive_observations += 1
        else:
            self.signals.consecutive_observations = 0

    def record_command(self, command: str):
        """Record a command that was sent."""
        self.recent_commands.append(command)
        self._update_repeated_commands()

    def record_position(self, x: int, y: int, plane: int):
        """Record the player's position."""
        pos = (x, y, plane)
        self.recent_positions.append(pos)
        self._update_position_unchanged()

    def record_error(self, error: str):
        """Record an error."""
        self.recent_errors.append(error)
        self.signals.consecutive_errors += 1

    def record_success(self):
        """Record a successful action (resets error counter)."""
        self.signals.consecutive_errors = 0

    def record_state_age(self, age_seconds: float):
        """Record how old the game state is."""
        self.signals.state_stale_seconds = age_seconds

    def check(self) -> StuckSignals:
        """Check all signals and return current stuck status."""
        return self.signals

    def reset(self):
        """Reset all signals (after recovery or new directive)."""
        self.recent_commands.clear()
        self.recent_positions.clear()
        self.recent_errors.clear()
        self.signals = StuckSignals()

    def get_recovery_hint(self) -> str:
        """Get a recovery suggestion based on current signals."""
        if self.signals.state_stale_seconds > 30:
            return (
                "The game state file hasn't updated in over 30 seconds. "
                "The plugin may be frozen. Try check_health() and if unhealthy, "
                "use restart_if_frozen() to recover."
            )
        if self.signals.repeated_commands >= 3:
            last_cmd = self.recent_commands[-1] if self.recent_commands else "unknown"
            return (
                f"You've sent '{last_cmd}' multiple times without progress. "
                "Try a different approach: check logs with get_logs(level='ALL', since_seconds=30), "
                "verify your position with get_game_state(), or try an alternative command."
            )
        if self.signals.position_unchanged_checks >= 5:
            return (
                "Your position hasn't changed despite movement commands. "
                "You might be stuck on an obstacle. Try: "
                "1) get_transitions() to find doors/paths, "
                "2) GOTO to a nearby known-reachable tile, "
                "3) TELEPORT_HOME as a last resort."
            )
        if self.signals.consecutive_errors >= 3:
            return (
                "Multiple consecutive errors. Check get_logs(level='ERROR', since_seconds=60) "
                "for details. The client may need a restart via restart_if_frozen()."
            )
        if self.signals.consecutive_observations >= 6:
            return (
                "You've been calling observation tools repeatedly without taking action. "
                "STOP observing and ACT. Use send_command or send_and_await to do something. "
                "If waiting for movement, use send_and_await('GOTO x y 0', 'location:x,y') "
                "instead of polling get_game_state in a loop."
            )
        return "Try observing the current state with get_game_state() to reassess."

    def _update_repeated_commands(self):
        """Count how many times the last command was repeated consecutively."""
        if len(self.recent_commands) < 2:
            self.signals.repeated_commands = 0
            return
        last = self.recent_commands[-1]
        count = 0
        for cmd in reversed(self.recent_commands):
            if cmd == last:
                count += 1
            else:
                break
        self.signals.repeated_commands = count

    def _update_position_unchanged(self):
        """Count consecutive position checks with no change."""
        if len(self.recent_positions) < 2:
            self.signals.position_unchanged_checks = 0
            return
        last = self.recent_positions[-1]
        count = 0
        for pos in reversed(self.recent_positions):
            if pos == last:
                count += 1
            else:
                break
        self.signals.position_unchanged_checks = count
