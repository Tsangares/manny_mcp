"""Tests for `repeat_until: <predicate>` in mcptools.tools.routine.

A step with `repeat_until` runs its action repeatedly until a predicate holds,
with a safety cap on iterations and a per-iteration timeout. The tutorial
routines use `repeat_until: "no_dialogue"` to press space/continue through a
multi-screen dialogue: keep advancing WHILE a dialogue is open, stop the instant
it closes.

Semantics are check-FIRST: if the predicate already holds the action runs zero
times (no stray space press after a dialogue closed).

These tests mock `_predicate_satisfied` (state evaluation) and `_execute_step_once`
(the single-iteration action executor) so they exercise only the repeat_until
orchestration, with `repeat_until_timeout_ms: 0` to keep polling instantaneous.
"""
from unittest.mock import AsyncMock

import pytest

from mcptools.tools import routine


@pytest.mark.asyncio
class TestRepeatUntil:
    async def test_already_satisfied_runs_action_zero_times(self, monkeypatch):
        """Check-first: predicate already true -> action never fires."""
        mock_once = AsyncMock(return_value={"success": True})
        monkeypatch.setattr(routine, "_execute_step_once", mock_once)
        monkeypatch.setattr(routine, "_predicate_satisfied", AsyncMock(return_value=True))

        step = {"id": 1, "action": "KEY_PRESS", "args": "space",
                "repeat_until": "no_dialogue", "repeat_until_timeout_ms": 0}
        result = await routine._execute_single_step(step, 0, {}, None)

        assert mock_once.await_count == 0
        assert result["iterations"] == 0
        assert result["satisfied"] is True
        assert result["success"] is True

    async def test_loops_until_predicate_satisfied(self, monkeypatch):
        """Presses through 3 dialogue screens, stopping when it finally closes."""
        mock_once = AsyncMock(return_value={"success": True})
        monkeypatch.setattr(routine, "_execute_step_once", mock_once)
        # check-first False, then poll False, False, True after 3rd press.
        monkeypatch.setattr(routine, "_predicate_satisfied",
                            AsyncMock(side_effect=[False, False, False, True]))

        step = {"id": 4, "action": "KEY_PRESS", "args": "space",
                "repeat_until": "no_dialogue", "repeat_until_timeout_ms": 0}
        result = await routine._execute_single_step(step, 0, {}, None)

        assert mock_once.await_count == 3
        assert result["iterations"] == 3
        assert result["satisfied"] is True
        assert result["success"] is True

    async def test_hits_iteration_cap_and_logs(self, monkeypatch, caplog):
        """Never-satisfied predicate stops at the cap (no infinite loop) and logs."""
        mock_once = AsyncMock(return_value={"success": True})
        monkeypatch.setattr(routine, "_execute_step_once", mock_once)
        monkeypatch.setattr(routine, "_predicate_satisfied", AsyncMock(return_value=False))

        step = {"id": 7, "action": "KEY_PRESS", "args": "space",
                "repeat_until": "no_dialogue", "max_iterations": 5,
                "repeat_until_timeout_ms": 0}
        with caplog.at_level("WARNING"):
            result = await routine._execute_single_step(step, 0, {}, None)

        assert mock_once.await_count == 5
        assert result["iterations"] == 5
        assert result["satisfied"] is False
        assert result["success"] is False
        assert "cap" in result["error"].lower()
        assert any("max-iteration cap" in r.message for r in caplog.records)

    async def test_config_can_override_cap(self, monkeypatch):
        """The routine `config:` block supplies the default cap when the step omits one."""
        mock_once = AsyncMock(return_value={"success": True})
        monkeypatch.setattr(routine, "_execute_step_once", mock_once)
        monkeypatch.setattr(routine, "_predicate_satisfied", AsyncMock(return_value=False))

        step = {"id": 1, "action": "KEY_PRESS", "args": "space",
                "repeat_until": "no_dialogue", "repeat_until_timeout_ms": 0}
        config = {"repeat_until_max_iterations": 3, "repeat_until_timeout_ms": 0}
        result = await routine._execute_single_step(step, 0, config, None)

        assert mock_once.await_count == 3
        assert result["iterations"] == 3
        assert result["max_iterations"] == 3

    async def test_invalid_predicate_fails_without_running_action(self, monkeypatch):
        """An unparseable predicate fails fast and never fires the action."""
        mock_once = AsyncMock(return_value={"success": True})
        monkeypatch.setattr(routine, "_execute_step_once", mock_once)

        step = {"id": 1, "action": "KEY_PRESS", "args": "space",
                "repeat_until": "totally_bogus", "repeat_until_timeout_ms": 0}
        result = await routine._execute_single_step(step, 0, {}, None)

        assert mock_once.await_count == 0
        assert result["success"] is False
        assert "Invalid repeat_until condition" in result["error"]
        assert result["iterations"] == 0

    async def test_predicate_satisfied_reads_dialogue_state(self, monkeypatch):
        """_predicate_satisfied wires through monitoring._check_condition on real state."""
        from mcptools.tools import monitoring

        # Dialogue closed -> no_dialogue predicate holds.
        monkeypatch.setattr(routine, "get_game_state",
                            AsyncMock(return_value={"dialogue": {"open": False}}))
        condition = monitoring._parse_condition("no_dialogue")
        assert await routine._predicate_satisfied(condition, None) is True

        # Dialogue open -> no_dialogue predicate does NOT hold.
        monkeypatch.setattr(routine, "get_game_state",
                            AsyncMock(return_value={"dialogue": {"open": True}}))
        assert await routine._predicate_satisfied(condition, None) is False
