"""Unit tests for mcptools/stuck_detector.py :: StuckDetector.check_command.

The anti-bot-loop safety gate invoked on every dispatched command. It tracks a
rolling (normalized_command, state_hash) pair per account and escalates:
  * WARN at WARN_THRESHOLD (3) identical repeats,
  * BLOCK at BLOCK_THRESHOLD (6) identical repeats,
  * resets the streak when >RESET_AFTER_SECONDS (60s) elapse between commands.

Everything here is pure/offline: no game client, no network, no real sleeps.
The module reads wall-clock via ``time.time()`` (module-level ``import time``),
so we inject a controllable clock by swapping the module's ``time`` attribute
for a fake exposing ``.time()`` — no real sleeping, fully deterministic.
"""
import pytest

from mcptools import stuck_detector as sd
from mcptools.stuck_detector import StuckDetector, stuck_detector


class _FakeClock:
    """Minimal stand-in for the ``time`` module: only ``time()`` is used."""

    def __init__(self, now=1000.0):
        self.now = now

    def time(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


@pytest.fixture
def clock(monkeypatch):
    """Replace stuck_detector's module-level ``time`` with a fake clock."""
    fake = _FakeClock()
    monkeypatch.setattr(sd, "time", fake)
    return fake


@pytest.fixture
def detector(clock):
    """A fresh detector wired to the injected clock."""
    return StuckDetector()


# ---------------------------------------------------------------------------
# Normalization / state-hash primitives (the "sameness" rules)
# ---------------------------------------------------------------------------
class TestNormalization:
    def test_rid_suffix_stripped(self, detector):
        # --rid=xxxx request-id tokens are removed so retries of the same
        # logical command still count as identical.
        assert detector._normalize_command("MINE_ORE Iron --rid=abc123") == "MINE_ORE Iron"

    def test_whitespace_collapsed(self, detector):
        assert detector._normalize_command("  MINE_ORE   Iron  ") == "MINE_ORE Iron"

    def test_case_is_significant(self, detector):
        # No lowercasing is done -> case differences make distinct commands.
        assert detector._normalize_command("mine_ore") != detector._normalize_command("MINE_ORE")

    def test_args_are_significant(self, detector):
        assert detector._normalize_command("MINE_ORE Iron") != detector._normalize_command("MINE_ORE Coal")

    def test_no_state_hashes_equal(self, detector):
        # None and empty dict both collapse to the sentinel "no_state".
        assert detector._hash_state(None) == "no_state"
        assert detector._hash_state({}) == "no_state"

    def test_inventory_only_slot_count_matters(self, detector):
        # Different contents, same used-slot count => same hash (only "used").
        a = detector._hash_state({"inventory": {"used": 3, "items": ["a"]}})
        b = detector._hash_state({"inventory": {"used": 3, "items": ["b", "c"]}})
        assert a == b

    def test_location_change_changes_hash(self, detector):
        a = detector._hash_state({"location": {"x": 1, "y": 2, "plane": 0}})
        b = detector._hash_state({"location": {"x": 9, "y": 2, "plane": 0}})
        assert a != b


# ---------------------------------------------------------------------------
# Distinct commands do not accumulate toward the threshold
# ---------------------------------------------------------------------------
class TestDistinctCommands:
    def test_alternating_commands_stay_ok(self, detector):
        for _ in range(10):
            assert detector.check_command("CMD_A")[0] == "ok"
            assert detector.check_command("CMD_B")[0] == "ok"

    def test_different_command_resets_streak(self, detector):
        # Build up to a warn on CMD_A...
        assert detector.check_command("CMD_A")[0] == "ok"
        assert detector.check_command("CMD_A")[0] == "ok"
        assert detector.check_command("CMD_A")[0] == "warn"
        # ...then a different command drops the streak back to count=1 -> ok.
        assert detector.check_command("CMD_B")[0] == "ok"
        assert detector.get_status()["repeat_count"] == 1

    def test_state_change_resets_streak(self, detector):
        st1 = {"location": {"x": 1, "y": 1, "plane": 0}}
        st2 = {"location": {"x": 2, "y": 2, "plane": 0}}
        assert detector.check_command("WALK", state=st1)[0] == "ok"
        assert detector.check_command("WALK", state=st1)[0] == "ok"
        assert detector.check_command("WALK", state=st1)[0] == "warn"
        # Same command, but the game state moved -> not stuck, streak resets.
        assert detector.check_command("WALK", state=st2)[0] == "ok"
        assert detector.get_status()["repeat_count"] == 1


# ---------------------------------------------------------------------------
# Identical repeats escalate WARN -> BLOCK at the real thresholds
# ---------------------------------------------------------------------------
class TestEscalation:
    def test_thresholds_are_3_and_6(self, detector):
        # Documented thresholds the assertions below hinge on.
        assert detector.WARN_THRESHOLD == 3
        assert detector.BLOCK_THRESHOLD == 6

    def test_warn_then_block_progression(self, detector):
        expected = ["ok", "ok", "warn", "warn", "warn", "block"]
        for i, want in enumerate(expected, start=1):
            status, msg = detector.check_command("MINE_ORE Iron")
            assert status == want, f"call {i} -> {status}, expected {want}"
        # After BLOCK the message is populated and count keeps climbing.
        status, msg = detector.check_command("MINE_ORE Iron")
        assert status == "block"
        assert msg is not None and "STUCK DETECTED" in msg

    def test_warn_message_is_none_at_ok_and_present_at_warn(self, detector):
        assert detector.check_command("X")[1] is None
        assert detector.check_command("X")[1] is None
        status, msg = detector.check_command("X")
        assert status == "warn"
        assert msg is not None and "Possible stuck loop" in msg

    def test_rid_variation_still_escalates(self, detector):
        # Same logical command with rotating request IDs must still stack.
        for want in ["ok", "ok", "warn", "warn", "warn", "block"]:
            status, _ = detector.check_command(f"MINE_ORE Iron --rid={want}{id(want)}")
            assert status == want


# ---------------------------------------------------------------------------
# The reset window clears the streak (injected clock, no real sleep)
# ---------------------------------------------------------------------------
class TestResetWindow:
    def test_gap_over_window_clears_streak(self, detector, clock):
        assert detector.check_command("SPIN")[0] == "ok"
        assert detector.check_command("SPIN")[0] == "ok"
        assert detector.check_command("SPIN")[0] == "warn"
        # Jump past the 60s reset window -> streak clears, back to count=1/ok.
        clock.advance(detector.RESET_AFTER_SECONDS + 1)
        assert detector.check_command("SPIN")[0] == "ok"
        assert detector.get_status()["repeat_count"] == 1

    def test_gap_at_or_under_window_does_not_clear(self, detector, clock):
        # Reset only triggers when the gap STRICTLY exceeds the window.
        assert detector.check_command("SPIN")[0] == "ok"
        assert detector.check_command("SPIN")[0] == "ok"
        clock.advance(detector.RESET_AFTER_SECONDS)  # exactly 60s -> no reset
        assert detector.check_command("SPIN")[0] == "warn"

    def test_repeated_within_window_reaches_block(self, detector, clock):
        # Small sub-window gaps between every call still accumulate to a block.
        results = []
        for _ in range(6):
            results.append(detector.check_command("SPIN")[0])
            clock.advance(5)  # well under 60s
        assert results == ["ok", "ok", "warn", "warn", "warn", "block"]


# ---------------------------------------------------------------------------
# Per-account isolation + reset() + get_status
# ---------------------------------------------------------------------------
class TestAccountsAndReset:
    def test_accounts_are_independent(self, detector):
        for _ in range(6):
            detector.check_command("CMD", account_id="acctA")
        # acctA is now blocked, acctB has never been touched.
        assert detector.check_command("CMD", account_id="acctA")[0] == "block"
        assert detector.check_command("CMD", account_id="acctB")[0] == "ok"

    def test_reset_single_account_clears_streak(self, detector):
        for _ in range(3):
            detector.check_command("CMD", account_id="acctA")
        assert detector.get_status("acctA")["repeat_count"] == 3
        detector.reset("acctA")
        assert detector.get_status("acctA")["repeat_count"] == 0
        assert detector.check_command("CMD", account_id="acctA")[0] == "ok"

    def test_reset_all_accounts(self, detector):
        detector.check_command("CMD", account_id="a")
        detector.check_command("CMD", account_id="b")
        detector.reset()  # no account_id -> clears everything
        assert detector.get_status("a")["repeat_count"] == 0
        assert detector.get_status("b")["repeat_count"] == 0

    def test_get_status_reports_thresholds(self, detector):
        status = detector.get_status("fresh")
        assert status["warn_threshold"] == 3
        assert status["block_threshold"] == 6
        assert status["repeat_count"] == 0
        assert status["command"] is None


# ---------------------------------------------------------------------------
# The module-level singleton behaves consistently
# ---------------------------------------------------------------------------
class TestSingleton:
    def test_singleton_is_a_stuck_detector(self, clock):
        assert isinstance(stuck_detector, StuckDetector)

    def test_singleton_escalates_and_resets(self, clock):
        # Use a unique account so we don't collide with any other test/user;
        # reset afterward to leave the shared instance clean.
        acct = "singleton-test"
        stuck_detector.reset(acct)
        try:
            seq = [stuck_detector.check_command("PING", account_id=acct)[0]
                   for _ in range(6)]
            assert seq == ["ok", "ok", "warn", "warn", "warn", "block"]
        finally:
            stuck_detector.reset(acct)
        assert stuck_detector.get_status(acct)["repeat_count"] == 0
