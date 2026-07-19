"""Tests for the KILL-THEN-SPAWN auto-restart guard (finding #5 / double-client).

Attempt #1's restart path spawned a SECOND client without reaping the first
(this run's fresh MultiRuneLiteManager did not track a client launched by a
separate ``mannyctl start`` process), and the disconnect->relogin escalation
re-triggered forever. The fix: reap the predecessor by session PID and confirm it
is dead before spawning, and cap restarts per account per process (fail loud).
"""
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from mcptools.tools import routine


@pytest.fixture(autouse=True)
def _reset(monkeypatch):
    routine._auto_restart_counts.clear()
    monkeypatch.setattr(routine, "config",
                        SimpleNamespace(resolve_account_id=lambda a=None: a or "acct"))
    yield
    routine._auto_restart_counts.clear()


@pytest.mark.asyncio
async def test_cap_refuses_after_max_restarts(monkeypatch):
    start = MagicMock(return_value={"pid": 123})
    monkeypatch.setattr(routine, "runelite_manager", SimpleNamespace(start_instance=start))
    monkeypatch.setattr(routine, "_reap_account_client",
                        AsyncMock(return_value={"reaped": [111], "still_alive": []}))
    monkeypatch.setattr(routine, "check_client_health", AsyncMock(return_value={"alive": True}))
    monkeypatch.setattr(routine.asyncio, "sleep", AsyncMock(return_value=None))

    # Two restarts allowed...
    assert await routine._auto_restart_client("acct") is True
    assert await routine._auto_restart_client("acct") is True
    # ...the third is refused (fail loud) and does NOT spawn a client.
    assert start.call_count == 2
    assert await routine._auto_restart_client("acct") is False
    assert start.call_count == 2


@pytest.mark.asyncio
async def test_refuses_spawn_when_predecessor_wont_die(monkeypatch):
    start = MagicMock(return_value={"pid": 123})
    monkeypatch.setattr(routine, "runelite_manager", SimpleNamespace(start_instance=start))
    # Reap could not confirm the old client dead -> must NOT spawn a second one.
    monkeypatch.setattr(routine, "_reap_account_client",
                        AsyncMock(return_value={"reaped": [], "still_alive": [999]}))
    monkeypatch.setattr(routine.asyncio, "sleep", AsyncMock(return_value=None))

    assert await routine._auto_restart_client("acct") is False
    start.assert_not_called()


@pytest.mark.asyncio
async def test_reap_kills_untracked_session_pid(monkeypatch):
    """The cross-process session PID (a mannyctl-launched client this manager does
    not track) is SIGTERM'd and reaped."""
    stop = MagicMock()
    monkeypatch.setattr(routine, "runelite_manager", SimpleNamespace(stop_instance=stop))
    monkeypatch.setattr(routine, "_live_runelite_pids_for_account",
                        lambda acct: [{"pid": 4242, "display": ":4"}])

    killed = []

    def fake_kill(pid, sig):
        killed.append((pid, sig))
        if sig == 0:
            raise ProcessLookupError()  # dead on the verify poll

    monkeypatch.setattr(routine.os, "kill", fake_kill)
    monkeypatch.setattr(routine.asyncio, "sleep", AsyncMock(return_value=None))

    # session_manager.end_session is imported lazily inside the reaper.
    import mcptools.session_manager as sm
    monkeypatch.setattr(sm.session_manager, "end_session", lambda **k: {"success": True})

    out = await routine._reap_account_client("acct")
    assert 4242 in out["reaped"]
    assert out["still_alive"] == []
    assert any(sig != 0 for _, sig in killed)  # a real terminating signal was sent
