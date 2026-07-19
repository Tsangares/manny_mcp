"""Tests for the per-step ``on_failure`` policy in
``mcptools.tools.routine.handle_execute_routine``.

A step failure is handled per its ``on_failure`` key:
  * absent / ``continue`` (default) -- log the error and proceed to the next
    step (exactly the legacy behavior; nothing that omits the key changes).
  * ``abort`` -- stop the run, record ``abort_reason``/``aborted_at_step``.
  * ``retry:N`` / ``{retry: N}`` -- re-send the step up to N times, then abort.

These drive the real ``handle_execute_routine`` outer loop with the client
health / active-loop / single-step executor mocked out, so only the failure
policy orchestration is exercised (no live plugin).
"""
from unittest.mock import AsyncMock

import pytest
import yaml

from mcptools.tools import routine


def _write(tmp_path, steps, loop=None):
    doc = {"name": "on_failure_test", "type": "utility", "steps": steps}
    if loop is not None:
        doc["loop"] = loop
    p = tmp_path / "r.yaml"
    p.write_text(yaml.safe_dump(doc))
    return str(p)


def _patch_env(monkeypatch):
    monkeypatch.setattr(routine, "check_active_loop", AsyncMock(return_value=None))
    monkeypatch.setattr(routine, "check_client_health",
                        AsyncMock(return_value={"alive": True}))


def _unit_parse():
    return routine._parse_on_failure


class TestParseOnFailure:
    def test_default_and_continue(self):
        p = _unit_parse()
        assert p(None) == {"mode": "continue", "retries": 0}
        assert p("") == {"mode": "continue", "retries": 0}
        assert p("continue") == {"mode": "continue", "retries": 0}

    def test_abort(self):
        assert _unit_parse()("abort") == {"mode": "abort", "retries": 0}

    def test_retry_string_and_dict(self):
        p = _unit_parse()
        assert p("retry:3") == {"mode": "retry", "retries": 3}
        assert p({"retry": 2}) == {"mode": "retry", "retries": 2}
        # min clamp to 1
        assert p("retry:0")["retries"] == 1

    def test_garbage_falls_back_to_continue(self):
        p = _unit_parse()
        assert p("nonsense")["mode"] == "continue"
        assert p("retry:abc")["mode"] == "continue"


@pytest.mark.asyncio
class TestOnFailureEngine:
    async def _run(self, monkeypatch, tmp_path, steps, exec_fn, loop=None):
        _patch_env(monkeypatch)
        monkeypatch.setattr(routine, "_execute_single_step", AsyncMock(side_effect=exec_fn))
        path = _write(tmp_path, steps, loop=loop)
        return await routine.handle_execute_routine(
            {"routine_path": path, "max_loops": 1})

    async def test_continue_is_backward_compatible(self, monkeypatch, tmp_path):
        """No on_failure key: a failed middle step is logged and the run marches on."""
        calls = []

        async def exec_fn(step, idx, cfg, acct):
            calls.append(step["id"])
            ok = step["id"] != 2
            return {"step_id": step["id"], "success": ok, "error": "boom"}

        steps = [{"id": 1, "action": "GOTO", "args": "1 2 0"},
                 {"id": 2, "action": "GOTO", "args": "3 4 0"},
                 {"id": 3, "action": "GOTO", "args": "5 6 0"}]
        res = await self._run(monkeypatch, tmp_path, steps, exec_fn)

        assert calls == [1, 2, 3]              # step 3 still ran after 2 failed
        assert not res.get("aborted")
        assert any("Step 2" in e for e in res["errors"])

    async def test_abort_stops_the_run(self, monkeypatch, tmp_path):
        calls = []

        async def exec_fn(step, idx, cfg, acct):
            calls.append(step["id"])
            ok = step["id"] != 2
            return {"step_id": step["id"], "success": ok, "error": "boom"}

        steps = [{"id": 1, "action": "GOTO", "args": "1 2 0"},
                 {"id": 2, "action": "BANK_OPEN", "on_failure": "abort"},
                 {"id": 3, "action": "GOTO", "args": "5 6 0"}]
        res = await self._run(monkeypatch, tmp_path, steps, exec_fn)

        assert calls == [1, 2]                 # step 3 never reached
        assert res["aborted"] is True
        assert res["aborted_at_step"] == 2
        assert res["success"] is False
        assert "abort_reason" in res

    async def test_retry_then_recover(self, monkeypatch, tmp_path):
        attempts = {"n": 0}

        async def exec_fn(step, idx, cfg, acct):
            if step["id"] == 2:
                attempts["n"] += 1
                ok = attempts["n"] >= 2      # fail once, succeed on the retry
                return {"step_id": 2, "success": ok, "error": "boom"}
            return {"step_id": step["id"], "success": True}

        steps = [{"id": 1, "action": "GOTO", "args": "1 2 0"},
                 {"id": 2, "action": "BANK_OPEN", "on_failure": "retry:2"},
                 {"id": 3, "action": "GOTO", "args": "5 6 0"}]
        res = await self._run(monkeypatch, tmp_path, steps, exec_fn)

        assert attempts["n"] == 2              # initial + one retry
        assert not res.get("aborted")          # recovered -> run continues
        assert res["success"] is True

    async def test_retry_exhausted_aborts(self, monkeypatch, tmp_path):
        attempts = {"n": 0}

        async def exec_fn(step, idx, cfg, acct):
            if step["id"] == 2:
                attempts["n"] += 1
                return {"step_id": 2, "success": False, "error": "boom"}
            return {"step_id": step["id"], "success": True}

        steps = [{"id": 1, "action": "GOTO", "args": "1 2 0"},
                 {"id": 2, "action": "BANK_OPEN", "on_failure": "retry:2"},
                 {"id": 3, "action": "GOTO", "args": "5 6 0"}]
        res = await self._run(monkeypatch, tmp_path, steps, exec_fn)

        assert attempts["n"] == 3              # initial + 2 retries
        assert res["aborted"] is True
        assert res["aborted_at_step"] == 2
