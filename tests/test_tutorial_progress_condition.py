"""Tests for the `tutorial_progress:>=N` step-condition atom (varbit 281 gate).

The plugin exports the game's authoritative Tutorial Island progress (varbit
281, 0..1000, 1000 == complete) as a TOP-LEVEL `tutorial` object
({"progress": <int|null>}). This atom lets a step await_condition -- and, via
run_chain, a whole master-chain section -- gate on real game progress instead
of blind step sequencing (attempt #1's false-pass root cause).

Critical compatibility property: against an OLD jar (no `tutorial` section) or a
logged-out client (`progress: null`), the condition must evaluate UNKNOWN
(False), NOT raise -- so old state files keep working.

It is a STEP-vocabulary atom ONLY, mirroring location:/inventory_count: -- NOT
the pending general condition dialect.
"""
import json
from unittest.mock import MagicMock

import pytest

from mcptools import dryrun
from mcptools.tools import monitoring


class TestParseTutorialProgress:
    def test_ge_parses(self):
        assert monitoring._parse_condition("tutorial_progress:>=250") == (
            "tutorial_progress", 250, ">=")

    def test_le_parses(self):
        assert monitoring._parse_condition("tutorial_progress:<=120") == (
            "tutorial_progress", 120, "<=")

    def test_gt_parses(self):
        assert monitoring._parse_condition("tutorial_progress:>370") == (
            "tutorial_progress", 370, ">")

    def test_lt_parses(self):
        assert monitoring._parse_condition("tutorial_progress:<1000") == (
            "tutorial_progress", 1000, "<")

    def test_bare_value_parses_as_equals(self):
        assert monitoring._parse_condition("tutorial_progress:1000") == (
            "tutorial_progress", 1000, "==")


class TestCheckTutorialProgress:
    def _state(self, progress):
        return {"player": {}, "tutorial": {"progress": progress}}

    def test_ge_satisfied_when_at_or_above(self):
        cond = ("tutorial_progress", 250, ">=")
        assert monitoring._check_condition(self._state(250), cond) is True
        assert monitoring._check_condition(self._state(300), cond) is True
        assert monitoring._check_condition(self._state(249), cond) is False

    def test_le_satisfied_when_at_or_below(self):
        cond = ("tutorial_progress", 120, "<=")
        assert monitoring._check_condition(self._state(120), cond) is True
        assert monitoring._check_condition(self._state(90), cond) is True
        assert monitoring._check_condition(self._state(121), cond) is False

    def test_gt_and_lt(self):
        assert monitoring._check_condition(
            self._state(371), ("tutorial_progress", 370, ">")) is True
        assert monitoring._check_condition(
            self._state(370), ("tutorial_progress", 370, ">")) is False
        assert monitoring._check_condition(
            self._state(999), ("tutorial_progress", 1000, "<")) is True

    def test_equals(self):
        assert monitoring._check_condition(
            self._state(1000), ("tutorial_progress", 1000, "==")) is True
        assert monitoring._check_condition(
            self._state(999), ("tutorial_progress", 1000, "==")) is False

    # --- OLD-JAR / LOGGED-OUT COMPATIBILITY: must NOT crash, must evaluate False ---

    def test_missing_tutorial_section_is_unknown_not_crash(self):
        """Old jar: no `tutorial` key at all. Must return False, never raise."""
        state = {"player": {"location": {"x": 1, "y": 2, "plane": 0}}}
        cond = ("tutorial_progress", 250, ">=")
        assert monitoring._check_condition(state, cond) is False

    def test_null_tutorial_section_is_unknown(self):
        state = {"tutorial": None}
        assert monitoring._check_condition(
            state, ("tutorial_progress", 1, ">=")) is False

    def test_null_progress_is_unknown_logged_out(self):
        """Logged out: plugin emits progress: null. Must be unknown, not 0-compare."""
        state = {"tutorial": {"progress": None}}
        # >=0 would be True if null were coerced to 0 -- verify it is NOT.
        assert monitoring._check_condition(
            state, ("tutorial_progress", 0, ">=")) is False
        assert monitoring._check_condition(
            state, ("tutorial_progress", 250, ">=")) is False

    def test_zero_progress_is_a_real_value(self):
        """progress: 0 (freshly on island) is a real value, distinct from null."""
        state = {"tutorial": {"progress": 0}}
        assert monitoring._check_condition(
            state, ("tutorial_progress", 0, ">=")) is True
        assert monitoring._check_condition(
            state, ("tutorial_progress", 1, ">=")) is False


class TestDryRunFixtureCarriesTutorial:
    def test_default_fixture_has_null_progress(self):
        st = dryrun.StateModel().as_state()
        assert st["tutorial"]["progress"] is None
        # Old-jar-style unknown against the default fixture.
        assert monitoring._check_condition(
            st, ("tutorial_progress", 250, ">=")) is False

    def test_fixture_can_set_progress(self):
        st = dryrun.StateModel(tutorial_progress=250).as_state()
        assert st["tutorial"]["progress"] == 250
        assert monitoring._check_condition(
            st, ("tutorial_progress", 250, ">=")) is True


@pytest.mark.asyncio
class TestAwaitTutorialProgress:
    """End-to-end through handle_await_state_change against a temp state file."""

    async def _run(self, monkeypatch, tmp_path, state, condition):
        state_file = tmp_path / "manny_state.json"
        state_file.write_text(json.dumps(state))
        fake_config = MagicMock()
        fake_config.get_state_file.return_value = str(state_file)
        monkeypatch.setattr(monitoring, "config", fake_config)
        return await monitoring.handle_await_state_change({
            "condition": condition,
            "timeout_ms": 400,
            "poll_interval_ms": 50,
        })

    async def test_met_when_progress_reached(self, monkeypatch, tmp_path):
        state = {"player": {}, "tutorial": {"progress": 260}}
        result = await self._run(monkeypatch, tmp_path, state, "tutorial_progress:>=250")
        assert result["success"] is True
        assert result["condition_met"] is True

    async def test_times_out_not_invalid_on_old_jar(self, monkeypatch, tmp_path):
        # No tutorial section (old jar): should TIME OUT, not "Invalid condition".
        state = {"player": {"location": {"x": 1, "y": 2, "plane": 0}}}
        result = await self._run(monkeypatch, tmp_path, state, "tutorial_progress:>=250")
        assert result["success"] is False
        assert "invalid" not in (result.get("error", "").lower())
