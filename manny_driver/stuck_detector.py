"""Multi-signal stuck/error detection for the agent.

Detects when the agent is stuck (repeating commands, position unchanged,
state stale) and provides recovery suggestions.
"""
import logging
import re
import time
from collections import deque
from dataclasses import dataclass, field, replace
from typing import Optional, Tuple

logger = logging.getLogger("manny_driver.stuck")


# ---------------------------------------------------------------------------
# Login / ban detection (DEFECT-22b, driver side)
#
# Consumes the `login` state section exported by the plugin
# (GameEngine.buildLoginState / manny commit 93dae33):
#   { game_state, login_index, terminal_login_failure, login_failure_message }
#
# The plugin's persistence heuristic latches `terminal_login_failure=true` when a
# non-{2,4} login-screen index persists across >=2 world-hop attempts without ever
# reaching LOGGED_IN. This module mirrors the SECONDARY heuristic driver-side (so an
# older plugin that only exports raw fields, or a missed latch, is still caught) and
# feeds the PRIMARY vision confirmation (analyze_screenshot). Everything here is pure
# and offline: no game client, no network, no vision dependency required.
# ---------------------------------------------------------------------------

# The two DOCUMENTED, stable login-screen form indices (username/password, OTP).
# Everything else is an undocumented error/transition screen whose number drifts.
LOGIN_FORM_INDICES = frozenset({2, 4})

# GameState enum name for a completed login. Reaching it clears every login latch.
LOGGED_IN_STATE = "LOGGED_IN"

# Seconds a non-form login-error screen must persist on the SAME login_index
# before the driver-side heuristic itself flags terminal-suspect (backstop for
# a missed plugin latch). Raised well past any legitimate connect/transition
# screen duration: a real ban screen parks on one stable index, transitions
# churn through several within seconds. The plugin-latch path (terminal_login_failure)
# is NOT gated by this window and still fires immediately.
LOGIN_STUCK_SECONDS = 120.0

# ---------------------------------------------------------------------------
# DEFECT-32 — oscillation-robust terminal-login detection.
#
# The live 2026-07-19 banned-account gate showed the client world-hopping FOREVER:
# login_index oscillated 10 <-> 14 every cycle with errorScreen=true, so the SAME-index
# streak backstop above (LOGIN_STUCK_SECONDS / _login_error_index) never accumulated —
# its window resets on every index change — and the run never stopped. The client's own
# WorldSelector defeated the streak detector it was supposed to feed.
#
# These two triggers are index-oscillation-robust: they measure how long the client has
# sat in ANY non-form login-error state (index may flip freely between samples), and how
# many times the error index has flipped (a world-hop proxy). Either firing is terminal.
# ---------------------------------------------------------------------------

# Continuous seconds on non-{2,4} login-error screens — index may CHANGE between samples,
# the epoch only resets when a non-error state (LOGGED_IN / a {2,4} form / non-LOGIN_SCREEN
# / unreadable -1) is seen. Chosen at 90s: comfortably past the 31s legitimate-transition
# regression guard (a real connect/transition reaches LOGGED_IN within seconds), and below
# the 120s stable-index backstop so an oscillating ban is caught at least as fast as a
# parked one. Independent of index stability, so world-hopping cannot defeat it.
LOGIN_ERROR_MAX_SECONDS = 90.0

# Number of login-index CHANGES observed within one continuous error epoch (each flip ~=
# a world-hop that repainted the login screen). 6 flips is far more than any healthy login
# (which passes through a handful of transition frames then reaches LOGGED_IN) but is
# reached quickly by a stuck hop-storm. A parked ban screen (0 flips) is caught by the
# duration trigger instead; an oscillating ban (this defect) is caught by whichever fires
# first.
LOGIN_ERROR_MAX_HOPS = 6

# PRIMARY signal prompt — strict, tokenised vision classification of the rasterised
# login screen. Kept here so the driver and tests share one source of truth.
BAN_CLASSIFICATION_PROMPT = (
    "This is an OSRS login screen. Does it show an account ban, disable, lock, "
    "appeal, or 'serious rule breaking' message? Answer strictly with ONE of these "
    "tokens first: BANNED, LOCKED, MEMBERS_REQUIRED, WORLD_FULL, RATE_LIMITED, "
    "NORMAL, or OTHER — then a one-line reason."
)

# Vision verdict tokens and how each maps to run policy.
_VISION_TOKENS = (
    "BANNED", "LOCKED", "MEMBERS_REQUIRED", "WORLD_FULL", "RATE_LIMITED",
    "NORMAL", "OTHER",
)
# TERMINAL: stop the run, never relaunch/hop/retry.
VISION_TERMINAL_CATEGORIES = frozenset({"BANNED", "LOCKED"})
# TRANSIENT: bounded retry / world-hop is legitimate.
VISION_TRANSIENT_CATEGORIES = frozenset({"WORLD_FULL", "RATE_LIMITED"})


@dataclass
class LoginClassification:
    """Heuristic verdict for one polled `login` state section."""
    present: bool                 # login section existed in the state file
    terminal: bool                # stop-the-run: plugin latch or vision-confirmed ban
    on_error_screen: bool         # LOGIN_SCREEN on a non-{2,4} error index
    logged_in: bool
    game_state: str = ""
    login_index: int = -1
    message: str = ""
    category: str = "UNKNOWN"     # NORMAL | ERROR_SCREEN | TERMINAL_LOGIN_FAILURE | vision token
    reason: str = ""
    vision_used: bool = False


def classify_login_state(login) -> LoginClassification:
    """Pure, offline classification of the exported `login` section.

    Accepts the dict from state["login"], or None/{}/garbage from a pre-DEFECT-22b
    plugin that never exported the section. Backward compatibility is mandatory:
    a missing/empty section must classify as NORMAL (present=False), never terminal.
    """
    if not isinstance(login, dict) or not login:
        return LoginClassification(
            present=False, terminal=False, on_error_screen=False, logged_in=False,
            category="NORMAL", reason="no login section (pre-DEFECT-22b plugin)")

    gs = login.get("game_state")
    gs = gs if isinstance(gs, str) else ""

    try:
        idx = int(login.get("login_index", -1))
    except (TypeError, ValueError):
        idx = -1

    terminal = bool(login.get("terminal_login_failure"))
    msg = login.get("login_failure_message") or ""
    if not isinstance(msg, str):
        msg = str(msg)

    logged_in = (gs == LOGGED_IN_STATE)
    # login_index -1 means unreadable (client threw) — do NOT treat as an error screen.
    on_error = (gs == "LOGIN_SCREEN" and idx >= 0 and idx not in LOGIN_FORM_INDICES)

    if terminal:
        category = "TERMINAL_LOGIN_FAILURE"
        reason = msg or "plugin latched terminal_login_failure"
    elif logged_in:
        category, reason = "NORMAL", "logged in"
    elif on_error:
        category = "ERROR_SCREEN"
        reason = "non-form login index %d on login screen" % idx
    else:
        category, reason = "NORMAL", "normal login form / login in progress"

    return LoginClassification(
        present=True, terminal=terminal, on_error_screen=on_error,
        logged_in=logged_in, game_state=gs, login_index=idx, message=msg,
        category=category, reason=reason)


def parse_vision_verdict(text) -> Tuple[str, str]:
    """Parse an analyze_screenshot response into (token, one-line-reason).

    Returns ("UNKNOWN", "") when vision is unavailable / empty — the caller treats
    UNKNOWN as "no vision signal" and keeps the heuristic verdict (graceful degrade).
    """
    if not text or not isinstance(text, str):
        return ("UNKNOWN", "")
    first_line = next((ln.strip() for ln in text.splitlines() if ln.strip()), "")
    # PRIMARY: the prompt asks for the token FIRST. Require an exact match on the
    # leading word, not merely "appears anywhere" -- avoids whole-text substring
    # matching mislabeling e.g. "not BANNED, it's NORMAL" as BANNED.
    lead = re.match(r"[A-Za-z_]+", first_line)
    lead = lead.group(0).upper() if lead else ""
    if lead in _VISION_TOKENS:
        return (lead, first_line[:200])
    # FALLBACK: response didn't lead with the bare token (e.g. wrapped in prose or
    # markdown). Priority-ordered substring scan of the whole text, most severe
    # (terminal) categories first, so a malformed reply still fails toward caution.
    upper = text.upper()
    for tok in _VISION_TOKENS:
        if tok in upper:
            return (tok, first_line[:200])
    return ("OTHER", first_line[:200])


def apply_vision_verdict(classification: LoginClassification,
                         verdict_token: str,
                         verdict_reason: str = "") -> LoginClassification:
    """Fold a vision verdict into a heuristic classification (PRIMARY over SECONDARY).

    Vision is authoritative when it produces a real token: it sets the category and can
    ESCALATE to terminal (BANNED/LOCKED). It never DOWNGRADES a plugin-latched terminal
    (a confirmed in-plugin latch outranks a vision "NORMAL"). An UNKNOWN/empty verdict
    (vision unavailable) leaves the heuristic untouched — graceful degradation.
    """
    if not verdict_token or verdict_token == "UNKNOWN":
        return classification
    out = replace(classification, vision_used=True)
    out.category = verdict_token
    if verdict_reason:
        out.reason = verdict_reason
    # Escalate to terminal on a confirmed ban; keep an existing plugin latch.
    out.terminal = classification.terminal or (verdict_token in VISION_TERMINAL_CATEGORIES)
    return out


@dataclass
class StuckSignals:
    """Accumulated signals that indicate the agent might be stuck."""
    repeated_commands: int = 0
    position_unchanged_checks: int = 0
    consecutive_errors: int = 0
    consecutive_observations: int = 0  # get_game_state called without actions
    last_position: tuple = (0, 0, 0)
    state_stale_seconds: float = 0.0
    # DEFECT-22b login/ban signals (see classify_login_state above).
    login_terminal: bool = False          # plugin-latched terminal login failure
    login_stuck_seconds: float = 0.0      # time held on a non-form login-error screen (SAME index)
    login_failure_message: str = ""
    # DEFECT-32 oscillation-robust signals (index may flip freely; see LOGIN_ERROR_* above).
    login_error_seconds: float = 0.0      # continuous time in ANY non-form login-error state
    login_error_hops: int = 0             # login-index changes within the current error epoch

    @property
    def is_stuck(self) -> bool:
        return (
            self.repeated_commands >= 3
            or self.position_unchanged_checks >= 5
            or self.consecutive_errors >= 3
            or self.consecutive_observations >= 6
            or self.state_stale_seconds > 30
            or self.login_terminal
            or self.login_stuck_seconds >= LOGIN_STUCK_SECONDS
            or self.login_error_seconds >= LOGIN_ERROR_MAX_SECONDS
            or self.login_error_hops >= LOGIN_ERROR_MAX_HOPS
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
        if self.login_terminal:
            reasons.append("terminal login failure (suspected ban)")
        elif self.login_stuck_seconds >= LOGIN_STUCK_SECONDS:
            reasons.append(f"stuck on login-error screen for {self.login_stuck_seconds:.0f}s")
        elif self.login_error_seconds >= LOGIN_ERROR_MAX_SECONDS:
            reasons.append(
                f"login-error state (world-hopping) for {self.login_error_seconds:.0f}s")
        elif self.login_error_hops >= LOGIN_ERROR_MAX_HOPS:
            reasons.append(
                f"login-error index oscillated across {self.login_error_hops} world-hops")
        return "; ".join(reasons) if reasons else "unknown"


class StuckDetector:
    """Detects when the agent is stuck and suggests recovery actions."""

    def __init__(self):
        self.recent_commands: deque[str] = deque(maxlen=10)
        self.recent_positions: deque[tuple] = deque(maxlen=10)
        self.recent_errors: deque[str] = deque(maxlen=10)
        self.signals = StuckSignals()
        self._last_check = time.time()
        # DEFECT-22b login/ban tracking (SAME-index streak backstop)
        self._login_error_since: Optional[float] = None
        self._login_error_index: Optional[int] = None
        self._last_login: Optional[LoginClassification] = None
        # DEFECT-32 oscillation-robust tracking (epoch spans index changes)
        self._login_error_epoch_since: Optional[float] = None
        self._login_error_prev_index: Optional[int] = None

    # Observation-only tools (no game side-effects)
    OBSERVATION_TOOLS = {
        "get_game_state", "get_logs", "query_nearby", "check_health",
        "is_alive", "get_dialogue", "find_widget",
        "scan_environment", "get_location_info", "get_screenshot",
        "get_chat_messages", "list_commands", "list_quests",
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

    def record_login_state(self, login, now: float = None) -> LoginClassification:
        """Consume the exported `login` state section and update login/ban signals.

        `login` is state["login"] (dict), or None/{} on a pre-DEFECT-22b plugin — in
        which case this is a no-op that clears any prior login signal (never a false
        terminal). Returns the LoginClassification for callers that want the verdict.
        """
        now = now if now is not None else time.time()
        cls = classify_login_state(login)
        self._last_login = cls

        if not cls.present:
            # Old plugin / no signal — do not misclassify, clear state.
            self._reset_login_error_windows()
            self.signals.login_terminal = False
            return cls

        if cls.logged_in:
            # Success clears every login latch.
            self._reset_login_error_windows()
            self.signals.login_terminal = False
            self.signals.login_failure_message = ""
            return cls

        if cls.terminal:
            self.signals.login_terminal = True
            self.signals.login_failure_message = cls.message

        if cls.on_error_screen:
            # ---- SAME-index streak backstop (DEFECT-22b; stable-index ban) ----------
            # The persistence timer only accrues while the SAME login_index persists.
            # A parked ban screen rests on one stable index; an index change restarts
            # this particular window. This path is DEAD against an oscillating ban —
            # DEFECT-32's epoch/hop triggers below cover that case.
            if self._login_error_since is None or self._login_error_index != cls.login_index:
                self._login_error_since = now
                self._login_error_index = cls.login_index
            self.signals.login_stuck_seconds = max(0.0, now - self._login_error_since)

            # ---- DEFECT-32 oscillation-robust epoch + hop counter ------------------
            # The epoch spans ANY run of consecutive non-form login-error screens; index
            # changes do NOT reset it (that is exactly how the client's world-hopping
            # defeated the streak backstop). Each index flip within the epoch is counted
            # as a world-hop.
            if self._login_error_epoch_since is None:
                self._login_error_epoch_since = now
                self.signals.login_error_hops = 0
            elif (self._login_error_prev_index is not None
                  and cls.login_index != self._login_error_prev_index):
                self.signals.login_error_hops += 1
            self._login_error_prev_index = cls.login_index
            self.signals.login_error_seconds = max(0.0, now - self._login_error_epoch_since)
        else:
            # Normal form / transient in-progress state — reset BOTH windows.
            self._reset_login_error_windows()
        return cls

    def _reset_login_error_windows(self):
        """Clear both the SAME-index streak and the DEFECT-32 oscillation epoch/hop state."""
        self._login_error_since = None
        self._login_error_index = None
        self._login_error_epoch_since = None
        self._login_error_prev_index = None
        self.signals.login_stuck_seconds = 0.0
        self.signals.login_error_seconds = 0.0
        self.signals.login_error_hops = 0

    @property
    def last_login_classification(self) -> Optional[LoginClassification]:
        """The most recent login classification, or None if never polled."""
        return self._last_login

    @property
    def login_terminal_suspected(self) -> bool:
        """True when the run must STOP for a login failure (no relaunch/hop/retry).

        Fires on EITHER:
          (a) the confident plugin latch (terminal_login_failure=true) — the
              authoritative signal, gated by nothing but itself, fires immediately; or
          (b) the driver-side SAME-index persistence backstop: the SAME non-{2,4}
              login_index held unchanged for the whole LOGIN_STUCK_SECONDS window, for a
              plugin that exports raw fields but missed its own latch; or
          (c) DEFECT-32 oscillation-robust triggers: continuous non-form login-error
              state past LOGIN_ERROR_MAX_SECONDS, OR the error index flipping more than
              LOGIN_ERROR_MAX_HOPS times within one error epoch. Unlike (b), these do NOT
              require a stable index — they catch the world-hopping ban (index oscillating
              10<->14) that defeats the streak backstop. A genuinely healthy transition
              reaches LOGGED_IN within seconds and never crosses either threshold.
        """
        return bool(
            self.signals.login_terminal
            or self.signals.login_stuck_seconds >= LOGIN_STUCK_SECONDS
            or self.signals.login_error_seconds >= LOGIN_ERROR_MAX_SECONDS
            or self.signals.login_error_hops >= LOGIN_ERROR_MAX_HOPS
        )

    def check(self) -> StuckSignals:
        """Check all signals and return current stuck status."""
        return self.signals

    def reset(self):
        """Reset all signals (after recovery or new directive)."""
        self.recent_commands.clear()
        self.recent_positions.clear()
        self.recent_errors.clear()
        self.signals = StuckSignals()
        self._login_error_since = None
        self._login_error_index = None
        self._login_error_epoch_since = None
        self._login_error_prev_index = None
        self._last_login = None

    def get_recovery_hint(self) -> str:
        """Get a recovery suggestion based on current signals."""
        # Login/ban is terminal: STOP, never relaunch/hop/retry. Checked FIRST so it
        # is never masked by a co-occurring generic stuck signal.
        if (self.signals.login_terminal
                or self.signals.login_stuck_seconds >= LOGIN_STUCK_SECONDS
                or self.signals.login_error_seconds >= LOGIN_ERROR_MAX_SECONDS
                or self.signals.login_error_hops >= LOGIN_ERROR_MAX_HOPS):
            msg = self.signals.login_failure_message or "terminal login failure"
            if not self.signals.login_terminal and (
                    self.signals.login_error_seconds >= LOGIN_ERROR_MAX_SECONDS
                    or self.signals.login_error_hops >= LOGIN_ERROR_MAX_HOPS):
                msg = ("login-error stall: %ds in a login-error state across %d world-hops"
                       % (self.signals.login_error_seconds, self.signals.login_error_hops))
            return (
                f"Terminal login failure detected ({msg}). STOP the run now — do NOT "
                "relaunch, world-hop, or retry. Confirm the reason with "
                "analyze_screenshot (BANNED/LOCKED = stop; WORLD_FULL/RATE_LIMITED = "
                "bounded retry only), then mark the account. A banned/disabled/locked "
                "account cannot log in; retrying only hammers it."
            )
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
                "1) scan_environment(transitions_only=True) to find doors/paths, "
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
