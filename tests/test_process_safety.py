"""
Wave 5 safety tests:

- pid_is_runelite / scan_runelite_pids: exact-command process identification
  (no pgrep/pkill pattern matching, no false positives on processes whose
  command line merely mentions "runelite").
- MultiRuneLiteManager._kill_all_runelite: kills ONLY managed PIDs (tracked
  instances + session-recorded PIDs verified via /proc); never shells out to
  pkill; skips dead/recycled PIDs gracefully.
- SessionManager: flock-guarded, reentrant read-modify-write of sessions.yaml
  with atomic saves.

All process interactions are mocked - nothing here signals a real process.
"""
import fcntl
import os
from unittest.mock import MagicMock

import pytest
import yaml

from mcptools.runelite_manager import (
    MultiRuneLiteManager,
    pid_is_runelite,
    scan_runelite_pids,
)
from mcptools.session_manager import SessionManager

# ---------------------------------------------------------------------------
# Fake /proc helpers
# ---------------------------------------------------------------------------

def make_proc_entry(proc_root, pid, comm, args):
    pid_dir = proc_root / str(pid)
    pid_dir.mkdir(parents=True)
    (pid_dir / "comm").write_text(comm + "\n")
    (pid_dir / "cmdline").write_bytes("\x00".join(args).encode() + b"\x00")


class TestPidIsRunelite:
    def test_java_shaded_jar_matches(self, tmp_path):
        make_proc_entry(tmp_path, 100, "java",
                        ["/usr/lib/jvm/java-21-openjdk/bin/java", "-jar",
                         "/home/x/runelite/client-1.12.34-SNAPSHOT-shaded.jar"])
        assert pid_is_runelite(100, proc_root=str(tmp_path)) is True

    def test_java_main_class_matches(self, tmp_path):
        make_proc_entry(tmp_path, 101, "java",
                        ["java", "-cp", "x.jar", "net.runelite.client.RuneLite"])
        assert pid_is_runelite(101, proc_root=str(tmp_path)) is True

    def test_java_unrelated_does_not_match(self, tmp_path):
        make_proc_entry(tmp_path, 102, "java", ["java", "-jar", "/opt/other/app.jar"])
        assert pid_is_runelite(102, proc_root=str(tmp_path)) is False

    def test_pgrep_false_positive_case_bash_mentioning_runelite(self, tmp_path):
        # The old `pgrep -f runelite` matched this; the exact-comm check must not.
        make_proc_entry(tmp_path, 103, "bash",
                        ["bash", "-c", "tail -f /tmp/runelite.log"])
        assert pid_is_runelite(103, proc_root=str(tmp_path)) is False

    def test_editor_with_runelite_jar_path_does_not_match(self, tmp_path):
        make_proc_entry(tmp_path, 104, "vim", ["vim", "/home/x/runelite/shaded.jar"])
        assert pid_is_runelite(104, proc_root=str(tmp_path)) is False

    def test_dead_pid_is_false(self, tmp_path):
        assert pid_is_runelite(99999, proc_root=str(tmp_path)) is False

    def test_scan_returns_only_exact_matches(self, tmp_path):
        make_proc_entry(tmp_path, 200, "java",
                        ["java", "-jar", "/x/client-shaded.jar", "net.runelite.client.RuneLite"])
        make_proc_entry(tmp_path, 201, "bash", ["bash", "-c", "echo runelite .jar"])
        make_proc_entry(tmp_path, 202, "java", ["java", "-jar", "/opt/other.jar"])
        (tmp_path / "not_a_pid").mkdir()
        assert scan_runelite_pids(proc_root=str(tmp_path)) == [200]


# ---------------------------------------------------------------------------
# _kill_all_runelite: managed PIDs only
# ---------------------------------------------------------------------------

@pytest.fixture
def manager():
    return MultiRuneLiteManager(MagicMock())


def test_kill_all_stops_tracked_instances_only(manager, monkeypatch):
    import mcptools.runelite_manager as rm

    running = MagicMock()
    running.is_running.return_value = True
    dead = MagicMock()
    dead.is_running.return_value = False
    manager.instances = {"acct_a": running, "acct_b": dead}

    # No session-recorded PIDs.
    fake_sm = MagicMock()
    fake_sm.get_active_sessions.return_value = []
    monkeypatch.setattr(rm, "session_manager", fake_sm)

    # Any pkill/pgrep shell-out is a regression.
    def no_subprocess(*a, **k):
        raise AssertionError(f"_kill_all_runelite must not shell out: {a}")
    monkeypatch.setattr(rm.subprocess, "run", no_subprocess)

    result = manager._kill_all_runelite()

    running.stop.assert_called_once()
    dead.stop.assert_not_called()  # dead tracked instance skipped gracefully
    assert manager.instances == {}
    assert result["killed_tracked"] == ["acct_a"]
    assert result["killed_external"] is False


def test_kill_all_signals_verified_session_pids_and_skips_dead(manager, monkeypatch):
    import mcptools.runelite_manager as rm

    manager.instances = {}

    fake_sm = MagicMock()
    fake_sm.get_active_sessions.return_value = [
        {"account": "live", "pid": 1111, "display": ":3"},
        {"account": "stale", "pid": 2222, "display": ":4"},   # dead/recycled
        {"account": "nopid", "pid": None, "display": ":5"},
    ]
    monkeypatch.setattr(rm, "session_manager", fake_sm)

    # Only 1111 verifies as a live RuneLite java process.
    monkeypatch.setattr(rm, "pid_is_runelite", lambda pid, proc_root="/proc": pid == 1111)

    signals = []

    def fake_kill(pid, sig):
        signals.append((pid, sig))
        if sig == 0:
            raise ProcessLookupError  # after SIGTERM, process is gone
    monkeypatch.setattr(rm.os, "kill", fake_kill)

    def no_subprocess(*a, **k):
        raise AssertionError("_kill_all_runelite must not shell out")
    monkeypatch.setattr(rm.subprocess, "run", no_subprocess)

    result = manager._kill_all_runelite()

    # Only the verified PID was signalled; the dead one was never touched.
    signalled_pids = {pid for pid, sig in signals if sig != 0}
    assert signalled_pids == {1111}
    assert result["killed_session_pids"] == [{"account": "live", "pid": 1111}]
    assert any(s["pid"] == 2222 for s in result["skipped"])
    # The killed session was released in session tracking.
    fake_sm.end_session.assert_called_once_with(display=":3")


# ---------------------------------------------------------------------------
# SessionManager flock + atomic save
# ---------------------------------------------------------------------------

@pytest.fixture
def sm(tmp_path, monkeypatch):
    monkeypatch.setattr(SessionManager, "SESSIONS_FILE", tmp_path / "sessions.yaml")
    monkeypatch.setattr(SessionManager, "LOCK_FILE", tmp_path / "sessions.lock")
    # Startup cleanup touches real /tmp and ~/.manny - keep tests hermetic.
    monkeypatch.setattr(SessionManager, "_cleanup_stale_on_startup", lambda self: None)
    return SessionManager()


def test_save_is_atomic_and_persists(sm):
    sm.start_session("acct", ":3", pid=4321)

    assert sm.SESSIONS_FILE.exists()
    assert not sm.SESSIONS_FILE.with_suffix(".yaml.tmp").exists()
    data = yaml.safe_load(sm.SESSIONS_FILE.read_text())
    assert data["displays"][":3"]["account"] == "acct"
    assert data["displays"][":3"]["pid"] == 4321


def test_flock_held_during_mutation(sm):
    with sm._locked():
        fd = os.open(str(sm.LOCK_FILE), os.O_RDWR)
        try:
            with pytest.raises(BlockingIOError):
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        finally:
            os.close(fd)
    # Released after the with-block.
    fd = os.open(str(sm.LOCK_FILE), os.O_RDWR)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)


def test_locked_is_reentrant(sm):
    # end_session inside cleanup_stale_sessions nests _locked; must not deadlock.
    with sm._locked():
        with sm._locked():
            assert sm._file_lock_depth == 2
        assert sm._file_lock_depth == 1
    assert sm._file_lock_depth == 0
    assert sm._file_lock_fd is None


def test_end_session_nested_in_cleanup(sm):
    # A session whose PID cannot exist -> cleanup must end it via the nested,
    # reentrant end_session path without deadlocking. cleanup_displays=False so
    # no display/pkill logic runs.
    sm.start_session("ghost", ":4", pid=2 ** 22 - 3)  # below kernel pid_max, surely dead
    result = sm.cleanup_stale_sessions(cleanup_displays=False)

    assert result["session_count"] == 1
    assert result["cleaned_sessions"][0]["account"] == "ghost"
    data = yaml.safe_load(sm.SESSIONS_FILE.read_text())
    assert data["displays"][":4"] is None


def test_outermost_lock_reloads_from_disk(sm, tmp_path):
    # Simulate another process writing while we were idle.
    other = SessionManager()
    other.start_session("other_acct", ":5", pid=1234)

    # A fresh mutation on `sm` must see the other process's write.
    sm.start_session("mine", ":2", pid=5678)
    assert sm.displays[":5"] is not None
    assert sm.displays[":5"]["account"] == "other_acct"
    data = yaml.safe_load(sm.SESSIONS_FILE.read_text())
    assert data["displays"][":5"]["account"] == "other_acct"
    assert data["displays"][":2"]["account"] == "mine"
