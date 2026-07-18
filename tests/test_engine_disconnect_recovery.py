"""Offline regression tests for the engine disconnect-recovery fix (2026-07-18).

Companion to journals/ENGINE_DISCONNECT_RECOVERY_SPEC.md. Covers the three
MUST-fix items:

1. `run_routine.py` now threads the shared `MultiRuneLiteManager` into both
   `routine.set_dependencies()` and `monitoring.set_dependencies()` (it
   previously called `routine.set_dependencies(send_cmd, config)` -- only 2
   args -- leaving `routine.runelite_manager` permanently `None` for every
   CLI run, so `_auto_restart_client()` always short-circuited with
   "No runelite_manager available, cannot restart").

2. `check_client_health()` no longer treats state-file mtime staleness ALONE
   as "crashed". It queries GET_GAME_STATE (via the new
   `_get_connection_status()` helper) as the authoritative discriminator and
   only falls back to staleness when that command itself doesn't respond.

3. On a detected disconnect (category == "disconnect"), the routine executor
   calls the new `_attempt_relogin()` instead of burning a crash-restart
   attempt: dismiss the disconnect dialog, send the plugin's LOGIN command,
   poll GET_GAME_STATE for a bounded wait, and escalate to
   `_auto_restart_client()` (the same runelite_manager-backed path used for
   genuine freezes) only on timeout.

All tests are pure/offline: every IPC response and subprocess/xdotool call is
mocked. Nothing here launches, restarts, or touches a real client, and no
`/tmp/manny_*` files are written (state-file reads point at tmp_path).
"""
import time
from unittest.mock import AsyncMock, MagicMock

import pytest

import run_routine
from mcptools.tools import monitoring as monitoring_mod
from mcptools.tools import routine as routine_mod


def _connection_status(status, is_connected=None, can_send_commands=None, has_local_player=None):
    """Build a canned GET_GAME_STATE-shaped IPC response (the transport-level
    shape send_command_with_response returns: {"status": "success", "result": {...}})."""
    return {
        "status": "success",
        "result": {
            "gameState": status,
            "status": status,
            "isConnected": is_connected,
            "canSendCommands": can_send_commands,
            "hasLocalPlayer": has_local_player,
        },
    }


# ---------------------------------------------------------------------------
# 1. runelite_manager wiring (run_routine.py CLI entrypoint)
# ---------------------------------------------------------------------------
class TestRuneliteManagerWiring:
    @pytest.mark.asyncio
    async def test_run_routine_threads_manager_into_routine_and_monitoring(self, tmp_path, monkeypatch):
        """The exact bug from the spec: routine.set_dependencies() must be
        called with the 3rd (manager) argument, mirroring server.py:95, so
        routine.runelite_manager (and monitoring.runelite_manager) are never
        left None for a CLI run."""
        sentinel_manager = MagicMock(name="MultiRuneLiteManagerInstance")

        manager_ctor = MagicMock(return_value=sentinel_manager)
        monkeypatch.setattr("mcptools.runelite_manager.MultiRuneLiteManager", manager_ctor)

        dummy_config = MagicMock(name="ServerConfig")
        dummy_config.get_state_file.return_value = str(tmp_path / "does_not_exist.json")
        monkeypatch.setattr("mcptools.config.ServerConfig.load", classmethod(lambda cls: dummy_config))
        monkeypatch.setattr("mcptools.transport.set_config", MagicMock())

        # Avoid actually executing a routine -- that's covered by other
        # tests/handled elsewhere; this test is only about the wiring.
        fake_result = {"success": True, "routine_name": "noop", "errors": []}
        monkeypatch.setattr(routine_mod, "handle_execute_routine", AsyncMock(return_value=fake_result))

        await run_routine.run_routine(str(tmp_path / "unused.yaml"), max_loops=1,
                                       start_step="1", account_id="test")

        manager_ctor.assert_called_once_with(dummy_config)
        assert routine_mod.runelite_manager is sentinel_manager
        assert monitoring_mod.runelite_manager is sentinel_manager

    def test_call_site_passes_three_positional_args(self):
        """Static guard: re-grep the exact call-site regression this bug was.
        If someone reverts to the 2-arg form this fails immediately, even
        before any behavioral test runs."""
        import inspect
        src = inspect.getsource(run_routine.run_routine)
        assert "routine.set_dependencies(send_cmd, config, manager)" in src
        assert "monitoring.set_dependencies(manager, config)" in src


# ---------------------------------------------------------------------------
# 2. Discriminator: _get_connection_status / check_client_health
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
class TestGetConnectionStatus:
    async def test_parses_successful_response(self, monkeypatch):
        send = AsyncMock(return_value=_connection_status(
            "LOGGED_IN", is_connected=True, can_send_commands=True, has_local_player=True))
        monkeypatch.setattr(routine_mod, "send_command_with_response", send)

        result = await routine_mod._get_connection_status("acct")

        assert result == {
            "responded": True,
            "status": "LOGGED_IN",
            "is_connected": True,
            "can_send_commands": True,
            "has_local_player": True,
        }
        send.assert_awaited_once()
        assert send.await_args.args[0] == "GET_GAME_STATE"

    async def test_timeout_response_means_not_responded(self, monkeypatch):
        # Shape transport.send_command returns on timeout (transport.py:315-318).
        send = AsyncMock(return_value={"timeout": True, "status": "timeout", "error": "no response"})
        monkeypatch.setattr(routine_mod, "send_command_with_response", send)

        result = await routine_mod._get_connection_status("acct")
        assert result["responded"] is False

    async def test_exception_means_not_responded(self, monkeypatch):
        send = AsyncMock(side_effect=RuntimeError("channel dead"))
        monkeypatch.setattr(routine_mod, "send_command_with_response", send)

        result = await routine_mod._get_connection_status("acct")
        assert result["responded"] is False

    async def test_no_send_function_wired_means_not_responded(self, monkeypatch):
        monkeypatch.setattr(routine_mod, "send_command_with_response", None)
        result = await routine_mod._get_connection_status("acct")
        assert result["responded"] is False


@pytest.mark.asyncio
class TestCheckClientHealthDiscriminator:
    """The core regression guard: a stale state file during a legitimate
    disconnect must NOT be classified as a crash."""

    def _wire_config(self, monkeypatch, state_file):
        cfg = MagicMock()
        cfg.get_state_file.return_value = str(state_file)
        monkeypatch.setattr(routine_mod, "config", cfg)

    async def test_fresh_state_and_logged_in_is_healthy(self, tmp_path, monkeypatch):
        state_file = tmp_path / "manny_state.json"
        state_file.write_text("{}")
        self._wire_config(monkeypatch, state_file)
        monkeypatch.setattr(routine_mod, "send_command_with_response", AsyncMock(
            return_value=_connection_status("LOGGED_IN", is_connected=True,
                                             can_send_commands=True, has_local_player=True)))

        health = await routine_mod.check_client_health("acct", max_stale_seconds=60)
        assert health["alive"] is True
        assert health["category"] == "healthy"

    async def test_stale_state_but_disconnected_is_not_a_crash(self, tmp_path, monkeypatch):
        """The exact false positive from the live test: state file frozen on
        the char-creation/disconnect screen, GET_GAME_STATE reports
        DISCONNECTED -- must be classified "disconnect", never "crash"."""
        state_file = tmp_path / "manny_state.json"
        state_file.write_text("{}")
        _make_stale(state_file, 300)
        self._wire_config(monkeypatch, state_file)
        monkeypatch.setattr(routine_mod, "send_command_with_response", AsyncMock(
            return_value=_connection_status("DISCONNECTED", is_connected=False,
                                             can_send_commands=False, has_local_player=False)))

        health = await routine_mod.check_client_health("acct", max_stale_seconds=60)
        assert health["alive"] is False
        assert health["category"] == "disconnect"
        assert health["connection_status"] == "DISCONNECTED"

    async def test_stale_state_but_logging_in_is_not_a_crash(self, tmp_path, monkeypatch):
        state_file = tmp_path / "manny_state.json"
        state_file.write_text("{}")
        _make_stale(state_file, 300)
        self._wire_config(monkeypatch, state_file)
        monkeypatch.setattr(routine_mod, "send_command_with_response", AsyncMock(
            return_value=_connection_status("LOGGING_IN", is_connected=False,
                                             can_send_commands=False, has_local_player=False)))

        health = await routine_mod.check_client_health("acct", max_stale_seconds=60)
        assert health["alive"] is False
        assert health["category"] == "disconnect"

    async def test_stale_state_but_unknown_status_is_conservatively_disconnect(self, tmp_path, monkeypatch):
        state_file = tmp_path / "manny_state.json"
        state_file.write_text("{}")
        _make_stale(state_file, 300)
        self._wire_config(monkeypatch, state_file)
        monkeypatch.setattr(routine_mod, "send_command_with_response", AsyncMock(
            return_value=_connection_status("UNKNOWN")))

        health = await routine_mod.check_client_health("acct", max_stale_seconds=60)
        assert health["alive"] is False
        assert health["category"] == "disconnect"

    async def test_stale_state_and_logged_in_is_genuine_freeze(self, tmp_path, monkeypatch):
        """The other half of the discriminator: fully connected per
        GET_GAME_STATE, yet the state file writer is stuck -- THIS is the
        genuine-stuck case that must still trigger the crash/restart path."""
        state_file = tmp_path / "manny_state.json"
        state_file.write_text("{}")
        _make_stale(state_file, 300)
        self._wire_config(monkeypatch, state_file)
        monkeypatch.setattr(routine_mod, "send_command_with_response", AsyncMock(
            return_value=_connection_status("LOGGED_IN", is_connected=True,
                                             can_send_commands=True, has_local_player=True)))

        health = await routine_mod.check_client_health("acct", max_stale_seconds=60)
        assert health["alive"] is False
        assert health["category"] == "crash"

    async def test_logged_in_but_cannot_send_commands_is_conservative_disconnect(self, tmp_path, monkeypatch):
        """Mid-LOADING: gameState maps to LOGGED_IN but no local player yet."""
        state_file = tmp_path / "manny_state.json"
        state_file.write_text("{}")
        self._wire_config(monkeypatch, state_file)
        monkeypatch.setattr(routine_mod, "send_command_with_response", AsyncMock(
            return_value=_connection_status("LOGGED_IN", is_connected=True,
                                             can_send_commands=False, has_local_player=False)))

        health = await routine_mod.check_client_health("acct", max_stale_seconds=60)
        assert health["alive"] is False
        assert health["category"] == "disconnect"

    async def test_command_channel_unresponsive_falls_back_to_staleness_as_crash(self, tmp_path, monkeypatch):
        """The one case mtime staleness alone remains a valid signal: the
        command channel itself doesn't answer at all."""
        state_file = tmp_path / "manny_state.json"
        state_file.write_text("{}")
        _make_stale(state_file, 300)
        self._wire_config(monkeypatch, state_file)
        monkeypatch.setattr(routine_mod, "send_command_with_response",
                             AsyncMock(side_effect=RuntimeError("dead")))

        health = await routine_mod.check_client_health("acct", max_stale_seconds=60)
        assert health["alive"] is False
        assert health["category"] == "crash"

    async def test_missing_state_file_and_dead_channel_is_crash(self, tmp_path, monkeypatch):
        state_file = tmp_path / "does_not_exist.json"
        self._wire_config(monkeypatch, state_file)
        monkeypatch.setattr(routine_mod, "send_command_with_response",
                             AsyncMock(side_effect=RuntimeError("dead")))

        health = await routine_mod.check_client_health("acct", max_stale_seconds=60)
        assert health["alive"] is False
        assert health["category"] == "crash"
        assert "not found" in health["error"].lower()

    async def test_fresh_state_file_alone_does_not_short_circuit_the_discriminator(self, tmp_path, monkeypatch):
        """Regression guard for the inverse mistake: a FRESH state file must
        not be trusted either if GET_GAME_STATE says disconnected (e.g. a
        stale write followed by a crash right at the disconnect boundary)."""
        state_file = tmp_path / "manny_state.json"
        state_file.write_text("{}")  # fresh mtime
        self._wire_config(monkeypatch, state_file)
        monkeypatch.setattr(routine_mod, "send_command_with_response", AsyncMock(
            return_value=_connection_status("DISCONNECTED", is_connected=False,
                                             can_send_commands=False, has_local_player=False)))

        health = await routine_mod.check_client_health("acct", max_stale_seconds=60)
        assert health["alive"] is False
        assert health["category"] == "disconnect"


def _make_stale(path, age_seconds):
    import os
    old = time.time() - age_seconds
    os.utime(str(path), (old, old))


# ---------------------------------------------------------------------------
# 3. Recovery escalation ladder: _attempt_relogin
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
class TestAttemptRelogin:
    def _fake_clock(self, monkeypatch):
        """Deterministic virtual clock so the bounded-wait poll loop doesn't
        actually sleep in real time. Every mocked asyncio.sleep(n) advances
        the clock by n; time.time() reads the clock."""
        clock = {"t": 0.0}

        def fake_time():
            return clock["t"]

        async def fake_sleep(seconds):
            clock["t"] += seconds

        monkeypatch.setattr(routine_mod.time, "time", fake_time)
        monkeypatch.setattr(routine_mod.asyncio, "sleep", fake_sleep)
        return clock

    def _wire_common(self, monkeypatch):
        monkeypatch.setattr(routine_mod, "send_command_with_response",
                             AsyncMock(return_value={"status": "success", "result": {}}))
        cfg = MagicMock()
        cfg.default_account = "default"
        cfg.display = ":2"
        monkeypatch.setattr(routine_mod, "config", cfg)
        monkeypatch.setattr(monitoring_mod, "_xdotool_click", MagicMock(return_value=True))
        # Avoid real ~/.manny/sessions.yaml reads for a deterministic display.
        from mcptools.session_manager import session_manager
        monkeypatch.setattr(session_manager, "get_display_for_account", MagicMock(return_value=":2"))

    async def test_escalates_to_restart_only_after_bounded_wait(self, monkeypatch):
        """Core ladder assertion: never escalate immediately -- only after the
        bounded poll wait expires without recovery."""
        self._fake_clock(monkeypatch)
        self._wire_common(monkeypatch)

        conn_status = AsyncMock(return_value={
            "responded": True, "status": "DISCONNECTED",
            "is_connected": False, "can_send_commands": False, "has_local_player": False,
        })
        monkeypatch.setattr(routine_mod, "_get_connection_status", conn_status)

        restart = AsyncMock(return_value=True)
        monkeypatch.setattr(routine_mod, "_auto_restart_client", restart)

        result = await routine_mod._attempt_relogin("acct", max_wait_seconds=10)

        assert result is True
        restart.assert_awaited_once_with("acct")
        # Must have polled more than once before giving up -- proves the
        # escalation happened only after the bounded wait, not immediately.
        assert conn_status.await_count >= 2

    async def test_recovers_within_wait_without_escalating(self, monkeypatch):
        self._fake_clock(monkeypatch)
        self._wire_common(monkeypatch)

        responses = [
            {"responded": True, "status": "DISCONNECTED", "is_connected": False,
             "can_send_commands": False, "has_local_player": False},
            {"responded": True, "status": "LOGGING_IN", "is_connected": False,
             "can_send_commands": False, "has_local_player": False},
            {"responded": True, "status": "LOGGED_IN", "is_connected": True,
             "can_send_commands": True, "has_local_player": True},
        ]
        conn_status = AsyncMock(side_effect=responses)
        monkeypatch.setattr(routine_mod, "_get_connection_status", conn_status)

        restart = AsyncMock(return_value=True)
        monkeypatch.setattr(routine_mod, "_auto_restart_client", restart)

        result = await routine_mod._attempt_relogin("acct", max_wait_seconds=60)

        assert result is True
        restart.assert_not_awaited()
        assert conn_status.await_count == 3

    async def test_dismisses_disconnect_dialog_and_sends_login_command(self, monkeypatch):
        """Verifies the actual recovery primitives from the spec are used:
        the disconnect-dialog OK click (monitoring._xdotool_click) and the
        plugin's LOGIN command -- not a reinvented mechanism."""
        self._fake_clock(monkeypatch)
        self._wire_common(monkeypatch)

        conn_status = AsyncMock(return_value={
            "responded": True, "status": "LOGGED_IN",
            "is_connected": True, "can_send_commands": True, "has_local_player": True,
        })
        monkeypatch.setattr(routine_mod, "_get_connection_status", conn_status)
        restart = AsyncMock(return_value=True)
        monkeypatch.setattr(routine_mod, "_auto_restart_client", restart)

        result = await routine_mod._attempt_relogin("acct", max_wait_seconds=60)

        assert result is True
        restart.assert_not_awaited()
        monitoring_mod._xdotool_click.assert_called_once_with(770, 604, ":2")
        routine_mod.send_command_with_response.assert_awaited_once()
        assert routine_mod.send_command_with_response.await_args.args[0] == "LOGIN"

    async def test_restart_escalation_failure_propagates(self, monkeypatch):
        self._fake_clock(monkeypatch)
        self._wire_common(monkeypatch)
        monkeypatch.setattr(routine_mod, "_get_connection_status", AsyncMock(return_value={
            "responded": True, "status": "DISCONNECTED", "is_connected": False,
            "can_send_commands": False, "has_local_player": False,
        }))
        monkeypatch.setattr(routine_mod, "_auto_restart_client", AsyncMock(return_value=False))

        result = await routine_mod._attempt_relogin("acct", max_wait_seconds=5)
        assert result is False


# ---------------------------------------------------------------------------
# 4. current_step_idx preservation across a disconnect-recovery cycle
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
class TestCurrentStepIdxPreservation:
    """Distinct from the (unchanged) restart branch: the relogin branch must
    not reset current_step_idx -- a mere relogin doesn't change in-world
    position/inventory, so the routine should resume the step it was on."""

    def _routine_yaml(self, tmp_path, n_steps):
        import yaml as _yaml
        steps = [{"id": i, "action": "PING"} for i in range(1, n_steps + 1)]
        path = tmp_path / "test_routine.yaml"
        path.write_text(_yaml.safe_dump({"name": "test", "steps": steps}))
        return str(path)

    async def test_outer_loop_start_disconnect_does_not_reset_start_step(self, tmp_path, monkeypatch):
        """start_step is step id '2' (idx 1). A disconnect at the very first
        outer-loop health check, followed by a successful relogin, must still
        begin step execution at idx 1 -- not idx 0."""
        routine_path = self._routine_yaml(tmp_path, 3)

        health_calls = {"n": 0}

        async def fake_health(account_id=None, max_stale_seconds=60):
            health_calls["n"] += 1
            if health_calls["n"] == 1:
                return {"alive": False, "category": "disconnect", "stale_seconds": 5,
                         "connection_status": "DISCONNECTED", "error": "disconnected"}
            return {"alive": True, "category": "healthy", "stale_seconds": 1,
                    "connection_status": "LOGGED_IN"}

        monkeypatch.setattr(routine_mod, "check_client_health", fake_health)
        monkeypatch.setattr(routine_mod, "_attempt_relogin", AsyncMock(return_value=True))
        auto_restart = AsyncMock(return_value=True)
        monkeypatch.setattr(routine_mod, "_auto_restart_client", auto_restart)

        executed_idxs = []

        async def fake_execute_single_step(step, step_idx, routine_config, account_id):
            executed_idxs.append(step_idx)
            return {"success": True, "step": step.get("id")}

        monkeypatch.setattr(routine_mod, "_execute_single_step", fake_execute_single_step)

        result = await routine_mod.handle_execute_routine({
            "routine_path": routine_path, "max_loops": 1, "start_step": "2", "account_id": "acct",
        })

        assert result["success"] is True
        # First executed step must be idx 1 (step id 2), proving the relogin
        # branch never reset current_step_idx back to 0.
        assert executed_idxs[0] == 1
        assert executed_idxs == [1, 2]
        auto_restart.assert_not_awaited()
        assert any("Recovered from disconnect" in e for e in result["errors"])

    async def test_periodic_disconnect_never_rewinds_to_step_zero(self, tmp_path, monkeypatch):
        """6-step routine; health_check_interval=5 means the periodic check
        fires mid-routine. Simulate a disconnect there -- the retried/resumed
        step index must never drop back to 0."""
        routine_path = self._routine_yaml(tmp_path, 6)

        health_calls = {"n": 0}

        async def fake_health(account_id=None, max_stale_seconds=60):
            health_calls["n"] += 1
            if health_calls["n"] == 2:
                # Second call is the periodic mid-routine check.
                return {"alive": False, "category": "disconnect", "stale_seconds": 5,
                         "connection_status": "DISCONNECTED", "error": "disconnected"}
            return {"alive": True, "category": "healthy", "stale_seconds": 1,
                    "connection_status": "LOGGED_IN"}

        monkeypatch.setattr(routine_mod, "check_client_health", fake_health)
        monkeypatch.setattr(routine_mod, "_attempt_relogin", AsyncMock(return_value=True))
        monkeypatch.setattr(routine_mod, "_auto_restart_client", AsyncMock(return_value=True))

        executed_idxs = []

        async def fake_execute_single_step(step, step_idx, routine_config, account_id):
            executed_idxs.append(step_idx)
            return {"success": True, "step": step.get("id")}

        monkeypatch.setattr(routine_mod, "_execute_single_step", fake_execute_single_step)

        result = await routine_mod.handle_execute_routine({
            "routine_path": routine_path, "max_loops": 1, "start_step": "1", "account_id": "acct",
        })

        assert result["success"] is True
        # Once we've progressed past idx 0, a genuine "reset to start" bug
        # would show up as a later 0 in the sequence.
        first_zero_positions = [i for i, v in enumerate(executed_idxs) if v == 0]
        assert first_zero_positions == [0], (
            f"current_step_idx was reset to 0 after the disconnect: {executed_idxs}")
        assert result.get("disconnect_detected") is not True
