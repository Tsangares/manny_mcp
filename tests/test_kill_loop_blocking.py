"""DEFECT-26 tests: run_routine.py must block on a plugin-side KILL_LOOP.

These exercise the Python A/B logic added for DEFECT-26 with mock state files /
mocked ``active_loop`` signals — no live plugin needed:

- ``routine._await_active_loop_finish`` polls the exported ``active_loop`` and
  blocks until the loop finishes / times out / stalls, and falls back cleanly
  when no signal ever appears (old plugin build).
- ``handle_execute_routine`` pre-launch guard refuses to start over a running
  loop unless ``force=True``.
- ``watchdog.read_active_loop`` extracts the signal, and the watchdog flags an
  ``unmanaged_loop`` instead of ``completed`` when the run pid dies mid-grind.
"""
import importlib.util
import json
import os
from unittest.mock import AsyncMock

import pytest

from mcptools.tools import routine


# --------------------------------------------------------------------------
# _active_loop_from_state / _loop_progress_key
# --------------------------------------------------------------------------
class TestStateHelpers:
    def test_active_loop_present(self):
        st = {"active_loop": {"command": "KILL_LOOP", "kills": 3, "iteration": 3}}
        assert routine._active_loop_from_state(st) == st["active_loop"]

    def test_active_loop_absent_or_null(self):
        assert routine._active_loop_from_state({"active_loop": None}) is None
        assert routine._active_loop_from_state({}) is None
        assert routine._active_loop_from_state(None) is None
        # A non-dict active_loop is ignored (defensive).
        assert routine._active_loop_from_state({"active_loop": "nope"}) is None

    def test_progress_key_advances(self):
        a = {"kills": 1, "iteration": 1}
        b = {"kills": 2, "iteration": 2}
        assert routine._loop_progress_key(a) != routine._loop_progress_key(b)
        assert routine._loop_progress_key(a) == routine._loop_progress_key(dict(a))


# --------------------------------------------------------------------------
# _await_active_loop_finish
# --------------------------------------------------------------------------
@pytest.mark.asyncio
class TestAwaitActiveLoopFinish:
    async def _no_sleep(self, monkeypatch):
        monkeypatch.setattr(routine.asyncio, "sleep", AsyncMock(return_value=None))

    async def test_finishes_when_loop_clears(self, monkeypatch):
        await self._no_sleep(monkeypatch)
        seq = [
            {"command": "KILL_LOOP", "kills": 1, "iteration": 1},  # appear
            {"command": "KILL_LOOP", "kills": 2, "iteration": 2},  # still running
            None,                                                    # cleared
        ]
        monkeypatch.setattr(routine, "check_active_loop", AsyncMock(side_effect=seq))
        res = await routine._await_active_loop_finish(
            "acct", timeout_ms=60000, appear_grace_ms=5000,
            poll_interval_ms=1, stall_ms=60000)
        assert res.get("finished") is True
        assert res.get("waited") is True

    async def test_no_signal_falls_back(self, monkeypatch):
        await self._no_sleep(monkeypatch)
        # Loop never appears -> do not block (backward-compatible).
        monkeypatch.setattr(routine, "check_active_loop", AsyncMock(return_value=None))
        res = await routine._await_active_loop_finish(
            "acct", timeout_ms=60000, appear_grace_ms=0,
            poll_interval_ms=1, stall_ms=60000)
        assert res.get("waited") is False
        assert res.get("reason") == "no_active_loop_signal"

    async def test_timeout_while_active(self, monkeypatch):
        await self._no_sleep(monkeypatch)
        monkeypatch.setattr(routine, "check_active_loop",
                            AsyncMock(return_value={"command": "KILL_LOOP", "kills": 1, "iteration": 1}))
        res = await routine._await_active_loop_finish(
            "acct", timeout_ms=0, appear_grace_ms=5000,
            poll_interval_ms=1, stall_ms=60000)
        assert res.get("timeout") is True

    async def test_stall_detected(self, monkeypatch):
        await self._no_sleep(monkeypatch)
        # active_loop present but kills/iteration never advance -> stalled.
        monkeypatch.setattr(routine, "check_active_loop",
                            AsyncMock(return_value={"command": "KILL_LOOP", "kills": 5, "iteration": 5}))
        res = await routine._await_active_loop_finish(
            "acct", timeout_ms=60000, appear_grace_ms=5000,
            poll_interval_ms=1, stall_ms=0)
        assert res.get("stalled") is True


# --------------------------------------------------------------------------
# handle_execute_routine pre-launch guard
# --------------------------------------------------------------------------
@pytest.mark.asyncio
class TestPreLaunchGuard:
    def _write_routine(self, tmp_path):
        p = tmp_path / "r.yaml"
        p.write_text(
            "name: t\nsteps:\n"
            "  - id: 1\n    action: KILL_LOOP\n    args: \"Chicken none 5\"\n"
            "    timeout_ms: 3600000\n")
        return str(p)

    async def test_refuses_when_loop_active(self, monkeypatch, tmp_path):
        monkeypatch.setattr(routine, "check_active_loop",
                            AsyncMock(return_value={"command": "KILL_LOOP", "kills": 9}))
        res = await routine.handle_execute_routine({
            "routine_path": self._write_routine(tmp_path),
            "account_id": "newbakshesh", "force": False})
        assert res["success"] is False
        assert res.get("guard") == "kill_loop_active"

    async def test_force_bypasses_guard(self, monkeypatch, tmp_path):
        monkeypatch.setattr(routine, "check_active_loop",
                            AsyncMock(return_value={"command": "KILL_LOOP", "kills": 9}))
        # Bypassed guard -> proceeds into the run loop; short-circuit it with a
        # crash health verdict + a no-op restart so the call returns promptly.
        monkeypatch.setattr(routine, "check_client_health",
                            AsyncMock(return_value={"alive": False, "category": "crash",
                                                    "error": "stub", "stale_seconds": 1}))
        monkeypatch.setattr(routine, "_auto_restart_client", AsyncMock(return_value=False))
        res = await routine.handle_execute_routine({
            "routine_path": self._write_routine(tmp_path),
            "account_id": "newbakshesh", "force": True})
        # It did NOT return the guard refusal (guard was bypassed).
        assert res.get("guard") != "kill_loop_active"


# --------------------------------------------------------------------------
# watchdog.read_active_loop + unmanaged_loop classification
# --------------------------------------------------------------------------
def _load_watchdog():
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "scripts", "remote", "watchdog.py")
    spec = importlib.util.spec_from_file_location("manny_watchdog", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestWatchdogActiveLoop:
    def test_read_active_loop(self, tmp_path):
        wd = _load_watchdog()
        sf = tmp_path / "state.json"
        sf.write_text(json.dumps({"active_loop": {"command": "KILL_LOOP", "kills": 4}}))
        assert wd.read_active_loop(str(sf)) == {"command": "KILL_LOOP", "kills": 4}

    def test_read_active_loop_null_and_missing(self, tmp_path):
        wd = _load_watchdog()
        sf = tmp_path / "state.json"
        sf.write_text(json.dumps({"active_loop": None}))
        assert wd.read_active_loop(str(sf)) is None
        assert wd.read_active_loop(str(tmp_path / "nope.json")) is None

    def test_run_pid_gone_with_active_loop_is_unmanaged(self, tmp_path, monkeypatch):
        """run pid gone + active_loop present => status 'unmanaged_loop', not 'completed'."""
        wd = _load_watchdog()
        sf = tmp_path / "state.json"
        sf.write_text(json.dumps({"active_loop": {"command": "KILL_LOOP", "kills": 7}}))
        rec_path = tmp_path / "run.json"

        # No temp reading, run pid dead, no crash sigs.
        monkeypatch.setattr(wd, "pkg_temp_c", lambda: None)
        monkeypatch.setattr(wd, "pid_alive", lambda pid: False)
        monkeypatch.setattr(wd, "tail_crash_matches", lambda log, seen: [])
        monkeypatch.setattr(wd, "RUNS_DIR", str(tmp_path))

        argv = ["--run-id", "T1", "--account", "newbakshesh", "--routine", "r.yaml",
                "--run-pid", "999999", "--state-file", str(sf),
                "--log-file", str(tmp_path / "client.log"), "--interval", "1"]
        rc = wd.main(argv)
        assert rc == 0
        rec = json.loads((tmp_path / "T1.json").read_text())
        assert rec["status"] == "unmanaged_loop"
        assert rec["active_loop"] == {"command": "KILL_LOOP", "kills": 7}

    def test_run_pid_gone_no_loop_is_completed(self, tmp_path, monkeypatch):
        wd = _load_watchdog()
        sf = tmp_path / "state.json"
        sf.write_text(json.dumps({"active_loop": None, "player": {}}))
        monkeypatch.setattr(wd, "pkg_temp_c", lambda: None)
        monkeypatch.setattr(wd, "pid_alive", lambda pid: False)
        monkeypatch.setattr(wd, "tail_crash_matches", lambda log, seen: [])
        monkeypatch.setattr(wd, "RUNS_DIR", str(tmp_path))
        argv = ["--run-id", "T2", "--account", "newbakshesh", "--routine", "r.yaml",
                "--run-pid", "999999", "--state-file", str(sf),
                "--log-file", str(tmp_path / "client.log"), "--interval", "1"]
        assert wd.main(argv) == 0
        rec = json.loads((tmp_path / "T2.json").read_text())
        assert rec["status"] == "completed"
