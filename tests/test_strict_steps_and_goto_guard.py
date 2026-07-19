"""Tests for the tutorial FIX-LOOP engine-honesty changes:

  * ``config.strict_steps`` (finding #1a) -- a step that fails under the default
    ``continue`` policy still marks the SECTION failed (results["success"]=False)
    at completion, WITHOUT changing per-step control flow. Off by default, so
    legacy routines are unaffected. This kills the false-pass class: a section
    that logged failed steps used to exit runner-status SUCCESS and let the
    master chain march into the next section on a desynced game.

  * The GOTO movement guard (finding #2b) -- a no-await ``GOTO`` that reports
    plugin-success but never moves the player one tile (and wasn't already at the
    target) fails HONESTLY instead of blind-marching on its timeout (the s07
    cross-plane ladder case: 0 tiles in 8.5 min, silent).
"""
from unittest.mock import AsyncMock

import pytest
import yaml

from mcptools.tools import routine


def _write(tmp_path, steps, config=None):
    doc = {"name": "strict_test", "type": "utility", "steps": steps}
    if config is not None:
        doc["config"] = config
    p = tmp_path / "r.yaml"
    p.write_text(yaml.safe_dump(doc))
    return str(p)


def _patch_env(monkeypatch):
    monkeypatch.setattr(routine, "check_active_loop", AsyncMock(return_value=None))
    monkeypatch.setattr(routine, "check_client_health",
                        AsyncMock(return_value={"alive": True}))


@pytest.mark.asyncio
class TestStrictSteps:
    async def _run(self, monkeypatch, tmp_path, steps, exec_fn, config=None):
        _patch_env(monkeypatch)
        monkeypatch.setattr(routine, "_execute_single_step", AsyncMock(side_effect=exec_fn))
        path = _write(tmp_path, steps, config=config)
        return await routine.handle_execute_routine(
            {"routine_path": path, "max_loops": 1})

    @staticmethod
    def _fail_step2(step, idx, cfg, acct):
        return {"step_id": step["id"], "success": step["id"] != 2, "error": "boom"}

    async def test_strict_off_is_backward_compatible(self, monkeypatch, tmp_path):
        """Without strict_steps a failed middle step is logged but the SECTION
        still reports success (the pre-fix / legacy behavior)."""
        calls = []

        async def exec_fn(step, idx, cfg, acct):
            calls.append(step["id"])
            return self._fail_step2(step, idx, cfg, acct)

        steps = [{"id": 1, "action": "GOTO", "args": "1 2 0"},
                 {"id": 2, "action": "GOTO", "args": "3 4 0"},
                 {"id": 3, "action": "GOTO", "args": "5 6 0"}]
        res = await self._run(monkeypatch, tmp_path, steps, exec_fn)

        assert calls == [1, 2, 3]
        assert res["success"] is True          # legacy false-pass preserved when OFF
        assert any("Step 2" in e for e in res["errors"])

    async def test_strict_on_fails_section_but_finishes(self, monkeypatch, tmp_path):
        """With strict_steps a failed step flips the verdict to failed, WITHOUT
        aborting mid-section (control flow unchanged: every step still runs)."""
        calls = []

        async def exec_fn(step, idx, cfg, acct):
            calls.append(step["id"])
            return self._fail_step2(step, idx, cfg, acct)

        steps = [{"id": 1, "action": "GOTO", "args": "1 2 0"},
                 {"id": 2, "action": "GOTO", "args": "3 4 0"},
                 {"id": 3, "action": "GOTO", "args": "5 6 0"}]
        res = await self._run(monkeypatch, tmp_path, steps, exec_fn,
                              config={"strict_steps": True})

        assert calls == [1, 2, 3]              # flow unchanged: not an abort
        assert res["success"] is False         # section HONESTLY fails
        assert res.get("strict_failure") is True
        assert res.get("first_failed_step") == 2
        assert 2 in res.get("failed_steps", [])
        assert not res.get("aborted")          # verdict-only, not a mid-run abort

    async def test_strict_on_all_pass_is_success(self, monkeypatch, tmp_path):
        async def exec_fn(step, idx, cfg, acct):
            return {"step_id": step["id"], "success": True}

        steps = [{"id": 1, "action": "GOTO", "args": "1 2 0"},
                 {"id": 2, "action": "GOTO", "args": "3 4 0"}]
        res = await self._run(monkeypatch, tmp_path, steps, exec_fn,
                              config={"strict_steps": True})
        assert res["success"] is True
        assert not res.get("strict_failure")


@pytest.mark.asyncio
class TestGotoMovementGuard:
    async def test_stuck_goto_fails(self, monkeypatch):
        """No-await GOTO, plugin says success, player never moves -> step fails."""
        monkeypatch.setattr(routine, "execute_simple_command",
                            AsyncMock(return_value={"success": True, "response": {}}))
        # Player is far from the target and never moves.
        state = {"player": {"location": {"x": 3000, "y": 3000, "plane": 0}}}
        monkeypatch.setattr(routine, "get_game_state", AsyncMock(return_value=state))
        # Don't actually sleep out the poll window.
        monkeypatch.setattr(routine.asyncio, "sleep", AsyncMock(return_value=None))

        step = {"id": 1, "action": "GOTO", "args": "3088 3119 0"}
        res = await routine._execute_step_once(step, 0, {}, None)

        assert res["success"] is False
        assert "did not move" in res["error"]
        assert res["movement_check"]["progressed"] is False

    async def test_goto_that_moves_succeeds(self, monkeypatch):
        positions = [
            {"player": {"location": {"x": 3000, "y": 3000, "plane": 0}}},  # pre
            {"player": {"location": {"x": 3001, "y": 3000, "plane": 0}}},  # moved 1 tile
        ]
        gs = AsyncMock(side_effect=lambda *a, **k: positions[min(len(positions) - 1,
                                                                 gs.await_count - 1)])
        monkeypatch.setattr(routine, "get_game_state", gs)
        monkeypatch.setattr(routine, "execute_simple_command",
                            AsyncMock(return_value={"success": True, "response": {}}))
        monkeypatch.setattr(routine.asyncio, "sleep", AsyncMock(return_value=None))

        step = {"id": 1, "action": "GOTO", "args": "3050 3000 0"}
        res = await routine._execute_step_once(step, 0, {}, None)
        assert res["success"] is True
        assert res["movement_check"]["progressed"] is True

    async def test_goto_already_at_target_succeeds(self, monkeypatch):
        state = {"player": {"location": {"x": 3088, "y": 3119, "plane": 0}}}
        monkeypatch.setattr(routine, "get_game_state", AsyncMock(return_value=state))
        monkeypatch.setattr(routine, "execute_simple_command",
                            AsyncMock(return_value={"success": True, "response": {}}))
        monkeypatch.setattr(routine.asyncio, "sleep", AsyncMock(return_value=None))

        step = {"id": 1, "action": "GOTO", "args": "3088 3119 0"}
        res = await routine._execute_step_once(step, 0, {}, None)
        assert res["success"] is True
        assert res["movement_check"]["reason"] == "already_at_target"

    async def test_goto_with_await_condition_bypasses_guard(self, monkeypatch):
        """A GOTO carrying an await_condition goes through the await branch, not the
        movement guard (the await's own timeout handles honesty)."""
        monkeypatch.setattr(routine, "_handle_send_and_await",
                            AsyncMock(return_value={"success": True, "elapsed_ms": 10}))
        # get_game_state must NOT be consulted by the guard on this path.
        monkeypatch.setattr(routine, "get_game_state",
                            AsyncMock(side_effect=AssertionError("guard ran on await path")))
        step = {"id": 1, "action": "GOTO", "args": "3050 3000 0",
                "await_condition": "location:3050,3000"}
        res = await routine._execute_step_once(step, 0, {}, None)
        assert res["success"] is True
        assert "movement_check" not in res
