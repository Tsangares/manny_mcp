"""Tests for the `repeat: N` step field in mcptools.tools.routine._execute_single_step.

Steps with `repeat: N` must run their action up to N times sequentially. When
an `await_condition` is present, a satisfied condition short-circuits the
remaining repeats (see routines/quests/restless_ghost.yaml step 8 and
routines/quests/sheep_shearer.yaml step 6 for the real-world usage this
mirrors). Without an await_condition it's a fixed-count blind repeat (see
routines/quests/imp_catcher.yaml step 8: CLICK_CONTINUE repeat=5).

These tests mock `_execute_step_once` (the single-iteration executor) so they
exercise only the repeat/short-circuit orchestration in `_execute_single_step`,
without needing a live plugin connection.
"""
from unittest.mock import AsyncMock

import pytest

from mcptools.tools import routine


@pytest.mark.asyncio
class TestRepeatField:
    async def test_no_repeat_field_executes_once(self, monkeypatch):
        """A step with no `repeat` field (the pre-fix behavior) still runs exactly once."""
        mock_once = AsyncMock(return_value={"step_id": 1, "success": True})
        monkeypatch.setattr(routine, "_execute_step_once", mock_once)

        step = {"id": 1, "action": "CLICK_CONTINUE"}
        result = await routine._execute_single_step(step, 0, {}, None)

        assert mock_once.await_count == 1
        assert result["attempts"] == 1
        assert "repeat" not in result

    async def test_repeat_without_await_condition_runs_n_times(self, monkeypatch):
        """No await_condition: repeat is a fixed-count blind repeat, all N executions run."""
        mock_once = AsyncMock(return_value={"step_id": 1, "success": True})
        monkeypatch.setattr(routine, "_execute_step_once", mock_once)

        step = {"id": 1, "action": "CLICK_CONTINUE", "repeat": 5}
        result = await routine._execute_single_step(step, 0, {}, None)

        assert mock_once.await_count == 5
        assert result["attempts"] == 5
        assert result["repeat"] == 5

    async def test_repeat_short_circuits_when_await_condition_satisfied(self, monkeypatch):
        """An await_condition satisfied on the first try stops remaining repeats."""
        mock_once = AsyncMock(return_value={"step_id": 8, "success": True})
        monkeypatch.setattr(routine, "_execute_step_once", mock_once)

        step = {
            "id": 8,
            "action": "CLICK_CONTINUE",
            "repeat": 5,
            "await_condition": "has_item:Ghostspeak amulet",
        }
        result = await routine._execute_single_step(step, 0, {}, None)

        # Condition satisfied on the very first attempt -- no need to retry.
        assert mock_once.await_count == 1
        assert result["attempts"] == 1
        assert result["success"] is True

    async def test_repeat_continues_until_await_condition_satisfied(self, monkeypatch):
        """Keeps retrying (up to N) while the await_condition is unmet, then stops once met."""
        mock_once = AsyncMock(side_effect=[
            {"step_id": 6, "success": False},
            {"step_id": 6, "success": False},
            {"step_id": 6, "success": True},
        ])
        monkeypatch.setattr(routine, "_execute_step_once", mock_once)

        step = {
            "id": 6,
            "action": "INTERACT_NPC",
            "repeat": 20,
            "await_condition": "inventory_count:>=20",
        }
        result = await routine._execute_single_step(step, 0, {}, None)

        assert mock_once.await_count == 3
        assert result["attempts"] == 3
        assert result["success"] is True

    async def test_repeat_gives_up_after_n_attempts_if_never_satisfied(self, monkeypatch):
        """If the await_condition is never satisfied, it still stops at N attempts (no infinite loop)."""
        mock_once = AsyncMock(return_value={"step_id": 6, "success": False})
        monkeypatch.setattr(routine, "_execute_step_once", mock_once)

        step = {
            "id": 6,
            "action": "INTERACT_NPC",
            "repeat": 4,
            "await_condition": "inventory_count:>=20",
        }
        result = await routine._execute_single_step(step, 0, {}, None)

        assert mock_once.await_count == 4
        assert result["attempts"] == 4
        assert result["success"] is False

    async def test_repeat_zero_or_negative_treated_as_one(self, monkeypatch):
        """Nonsensical repeat values (0, negative) fall back to a single execution."""
        mock_once = AsyncMock(return_value={"step_id": 1, "success": True})
        monkeypatch.setattr(routine, "_execute_step_once", mock_once)

        step = {"id": 1, "action": "CLICK_CONTINUE", "repeat": 0}
        result = await routine._execute_single_step(step, 0, {}, None)

        assert mock_once.await_count == 1
        assert result["attempts"] == 1
