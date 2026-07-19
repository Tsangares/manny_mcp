"""DEFECT-22b — driver/watchdog ban-at-login detection.

Covers the Python half of the ban-detection redesign
(journals/BAN_DETECTION_REDESIGN_2026-07-19.md):

  * classify_login_state / parse_vision_verdict / apply_vision_verdict (pure, offline)
  * StuckDetector login-terminal signal + persistence backstop + recovery hint
  * watchdog read_login_state / login_terminal_failure + suspected_ban main-loop path

BACKWARD COMPATIBILITY IS MANDATORY: a state file from a pre-DEFECT-22b plugin has NO
`login` section; it must never crash or be misclassified as a ban. No live client, no
network, no vision dependency — everything here runs fully offline with synthetic state.
"""
import importlib.util
import json
import os

import pytest

from manny_driver.stuck_detector import (
    LOGIN_STUCK_SECONDS,
    StuckDetector,
    apply_vision_verdict,
    classify_login_state,
    parse_vision_verdict,
)


# ---------------------------------------------------------------------------
# classify_login_state — pure heuristic
# ---------------------------------------------------------------------------
class TestClassifyLoginState:
    def test_missing_section_is_backward_compatible(self):
        # Pre-DEFECT-22b plugin: no login section at all.
        for absent in (None, {}, "garbage", 123, []):
            c = classify_login_state(absent)
            assert c.present is False
            assert c.terminal is False
            assert c.category == "NORMAL"

    def test_plugin_latched_terminal(self):
        c = classify_login_state({
            "game_state": "LOGIN_SCREEN",
            "login_index": 14,
            "terminal_login_failure": True,
            "login_failure_message": "persistent non-form login state (idx=14)",
        })
        assert c.present and c.terminal
        assert c.category == "TERMINAL_LOGIN_FAILURE"
        assert "idx=14" in c.message

    def test_logged_in_is_normal(self):
        c = classify_login_state({
            "game_state": "LOGGED_IN", "login_index": -1,
            "terminal_login_failure": False, "login_failure_message": None,
        })
        assert c.logged_in and not c.terminal
        assert c.category == "NORMAL"
        assert c.on_error_screen is False

    @pytest.mark.parametrize("idx", [2, 4])
    def test_documented_form_indices_are_not_error_screens(self, idx):
        c = classify_login_state({
            "game_state": "LOGIN_SCREEN", "login_index": idx,
            "terminal_login_failure": False, "login_failure_message": None,
        })
        assert c.on_error_screen is False
        assert c.category == "NORMAL"

    def test_non_form_index_is_error_screen_not_yet_terminal(self):
        c = classify_login_state({
            "game_state": "LOGIN_SCREEN", "login_index": 14,
            "terminal_login_failure": False, "login_failure_message": None,
        })
        assert c.on_error_screen is True
        assert c.terminal is False
        assert c.category == "ERROR_SCREEN"

    def test_unreadable_index_minus_one_is_not_error_screen(self):
        # client.getLoginIndex() threw -> -1; must NOT be read as a ban screen.
        c = classify_login_state({
            "game_state": "LOGIN_SCREEN", "login_index": -1,
            "terminal_login_failure": False, "login_failure_message": None,
        })
        assert c.on_error_screen is False
        assert c.category == "NORMAL"

    def test_garbage_field_types_do_not_crash(self):
        c = classify_login_state({
            "game_state": 999, "login_index": "not-a-number",
            "terminal_login_failure": "true-ish", "login_failure_message": 42,
        })
        assert c.login_index == -1
        assert isinstance(c.message, str)
        # "true-ish" is truthy -> terminal
        assert c.terminal is True


# ---------------------------------------------------------------------------
# parse_vision_verdict / apply_vision_verdict
# ---------------------------------------------------------------------------
class TestVisionVerdict:
    @pytest.mark.parametrize("text,tok", [
        ("BANNED - your account has been disabled", "BANNED"),
        ("LOCKED for hijack recovery", "LOCKED"),
        ("WORLD_FULL, try another world", "WORLD_FULL"),
        ("RATE_LIMITED: too many attempts", "RATE_LIMITED"),
        ("MEMBERS_REQUIRED on this world", "MEMBERS_REQUIRED"),
        ("NORMAL login form, nothing wrong", "NORMAL"),
    ])
    def test_token_extraction(self, text, tok):
        token, reason = parse_vision_verdict(text)
        assert token == tok
        assert reason  # one-line reason preserved

    def test_unavailable_degrades_to_unknown(self):
        assert parse_vision_verdict(None) == ("UNKNOWN", "")
        assert parse_vision_verdict("") == ("UNKNOWN", "")
        assert parse_vision_verdict(123) == ("UNKNOWN", "")

    def test_unrecognized_is_other(self):
        token, _ = parse_vision_verdict("the model rambled with no keyword")
        assert token == "OTHER"

    def test_vision_escalates_error_screen_to_banned(self):
        base = classify_login_state({
            "game_state": "LOGIN_SCREEN", "login_index": 14,
            "terminal_login_failure": False,
        })
        out = apply_vision_verdict(base, "BANNED", "serious rule breaking")
        assert out.terminal is True
        assert out.category == "BANNED"
        assert out.vision_used is True

    def test_vision_transient_stays_retryable(self):
        base = classify_login_state({
            "game_state": "LOGIN_SCREEN", "login_index": 14,
            "terminal_login_failure": False,
        })
        out = apply_vision_verdict(base, "WORLD_FULL", "world is full")
        assert out.terminal is False
        assert out.category == "WORLD_FULL"

    def test_vision_never_downgrades_plugin_latch(self):
        # Plugin latched terminal; vision says NORMAL -> still terminal (latch wins).
        base = classify_login_state({
            "game_state": "LOGIN_SCREEN", "login_index": 14,
            "terminal_login_failure": True, "login_failure_message": "latched",
        })
        out = apply_vision_verdict(base, "NORMAL", "looks fine")
        assert out.terminal is True

    def test_unknown_verdict_leaves_heuristic_untouched(self):
        base = classify_login_state({
            "game_state": "LOGIN_SCREEN", "login_index": 14,
            "terminal_login_failure": True,
        })
        out = apply_vision_verdict(base, "UNKNOWN", "")
        assert out is base  # graceful degrade: heuristic stands unchanged
        assert out.vision_used is False


# ---------------------------------------------------------------------------
# StuckDetector login integration
# ---------------------------------------------------------------------------
class TestStuckDetectorLogin:
    def test_old_plugin_never_flags(self):
        d = StuckDetector()
        d.record_login_state(None)
        assert d.login_terminal_suspected is False
        assert d.signals.login_terminal is False
        assert d.check().is_stuck is False

    def test_terminal_latch_suspected_and_stuck(self):
        d = StuckDetector()
        d.record_login_state({
            "game_state": "LOGIN_SCREEN", "login_index": 14,
            "terminal_login_failure": True, "login_failure_message": "banned",
        })
        assert d.login_terminal_suspected is True
        assert d.check().is_stuck is True
        hint = d.get_recovery_hint()
        assert "STOP" in hint and "relaunch" in hint

    def test_persistence_backstop_without_plugin_latch(self):
        # Non-form error screen that persists past LOGIN_STUCK_SECONDS latches suspect
        # even if the plugin never set terminal_login_failure (old/missed latch).
        d = StuckDetector()
        err = {"game_state": "LOGIN_SCREEN", "login_index": 14,
               "terminal_login_failure": False}
        d.record_login_state(err, now=1000.0)
        assert d.login_terminal_suspected is False  # just started
        d.record_login_state(err, now=1000.0 + LOGIN_STUCK_SECONDS + 1)
        assert d.login_terminal_suspected is True

    def test_login_success_clears_signals(self):
        d = StuckDetector()
        d.record_login_state({
            "game_state": "LOGIN_SCREEN", "login_index": 14,
            "terminal_login_failure": True, "login_failure_message": "x",
        })
        assert d.login_terminal_suspected is True
        d.record_login_state({"game_state": "LOGGED_IN", "login_index": -1,
                              "terminal_login_failure": False})
        assert d.login_terminal_suspected is False
        assert d.signals.login_terminal is False

    def test_reset_clears_login_state(self):
        d = StuckDetector()
        d.record_login_state({"game_state": "LOGIN_SCREEN", "login_index": 14,
                              "terminal_login_failure": True})
        d.reset()
        assert d.login_terminal_suspected is False
        assert d.last_login_classification is None

    def test_normal_form_does_not_flag(self):
        d = StuckDetector()
        d.record_login_state({"game_state": "LOGIN_SCREEN", "login_index": 2,
                              "terminal_login_failure": False}, now=1.0)
        d.record_login_state({"game_state": "LOGIN_SCREEN", "login_index": 2,
                              "terminal_login_failure": False}, now=1000.0)
        assert d.login_terminal_suspected is False


# ---------------------------------------------------------------------------
# watchdog — read_login_state / login_terminal_failure / suspected_ban path
# ---------------------------------------------------------------------------
def _load_watchdog():
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "scripts", "remote", "watchdog.py")
    spec = importlib.util.spec_from_file_location("manny_watchdog_login", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestWatchdogLogin:
    def test_read_login_state(self, tmp_path):
        wd = _load_watchdog()
        sf = tmp_path / "state.json"
        login = {"game_state": "LOGIN_SCREEN", "login_index": 14,
                 "terminal_login_failure": True, "login_failure_message": "banned"}
        sf.write_text(json.dumps({"login": login, "player": {}}))
        assert wd.read_login_state(str(sf)) == login

    def test_read_login_state_missing_is_none(self, tmp_path):
        wd = _load_watchdog()
        sf = tmp_path / "state.json"
        # Pre-DEFECT-22b plugin: no login section.
        sf.write_text(json.dumps({"player": {}, "active_loop": None}))
        assert wd.read_login_state(str(sf)) is None
        assert wd.read_login_state(str(tmp_path / "nope.json")) is None

    def test_login_terminal_failure_predicate(self):
        wd = _load_watchdog()
        assert wd.login_terminal_failure({"terminal_login_failure": True}) is True
        assert wd.login_terminal_failure({"terminal_login_failure": False}) is False
        assert wd.login_terminal_failure(None) is False
        assert wd.login_terminal_failure({}) is False

    def test_main_records_suspected_ban_dry_run(self, tmp_path, monkeypatch):
        wd = _load_watchdog()
        sf = tmp_path / "state.json"
        sf.write_text(json.dumps({
            "player": {},
            "login": {"game_state": "LOGIN_SCREEN", "login_index": 14,
                      "terminal_login_failure": True,
                      "login_failure_message": "persistent non-form login state (idx=14)"},
        }))
        # run process alive (so we don't hit the run-gone branch), no temp reading.
        monkeypatch.setattr(wd, "pkg_temp_c", lambda: None)
        monkeypatch.setattr(wd, "pid_alive", lambda pid: True)
        monkeypatch.setattr(wd, "RUNS_DIR", str(tmp_path))

        argv = ["--run-id", "BAN1", "--account", "newbakshesh", "--routine", "r.yaml",
                "--run-pid", "123456", "--state-file", str(sf),
                "--log-file", str(tmp_path / "client.log"), "--interval", "1", "--dry-run"]
        assert wd.main(argv) == 0
        rec = json.loads((tmp_path / "BAN1.json").read_text())
        assert rec["status"] == "suspected_ban"
        kinds = [e["kind"] for e in rec["events"]]
        assert "login_failure" in kinds
        assert "suspected_ban" in kinds
        assert "needs_attention" in kinds
        # dry-run: never actually SIGTERM'd
        assert any("DRY-RUN" in e["detail"] for e in rec["events"] if e["kind"] == "suspected_ban")

    def test_main_sigterms_run_on_terminal_login(self, tmp_path, monkeypatch):
        wd = _load_watchdog()
        sf = tmp_path / "state.json"
        sf.write_text(json.dumps({
            "player": {},
            "login": {"game_state": "LOGIN_SCREEN", "login_index": 14,
                      "terminal_login_failure": True, "login_failure_message": "banned"},
        }))
        killed = []
        monkeypatch.setattr(wd, "pkg_temp_c", lambda: None)
        monkeypatch.setattr(wd, "pid_alive", lambda pid: True)
        monkeypatch.setattr(wd, "sigterm", lambda pid: killed.append(int(pid)) or True)
        monkeypatch.setattr(wd, "RUNS_DIR", str(tmp_path))

        argv = ["--run-id", "BAN2", "--account", "new", "--routine", "r.yaml",
                "--run-pid", "424242", "--client-pid", "434343",
                "--state-file", str(sf), "--log-file", str(tmp_path / "c.log"),
                "--interval", "1"]
        assert wd.main(argv) == 0
        rec = json.loads((tmp_path / "BAN2.json").read_text())
        assert rec["status"] == "suspected_ban"
        assert 424242 in killed  # run process torn down
        assert 434343 in killed  # client too

    def test_main_old_plugin_no_login_section_not_ban(self, tmp_path, monkeypatch):
        # Backward compat: no login section + run pid gone => completed, not ban.
        wd = _load_watchdog()
        sf = tmp_path / "state.json"
        sf.write_text(json.dumps({"player": {}, "active_loop": None}))
        monkeypatch.setattr(wd, "pkg_temp_c", lambda: None)
        monkeypatch.setattr(wd, "pid_alive", lambda pid: False)
        monkeypatch.setattr(wd, "tail_crash_matches", lambda log, seen: [])
        monkeypatch.setattr(wd, "RUNS_DIR", str(tmp_path))
        argv = ["--run-id", "OLD1", "--account", "main", "--routine", "r.yaml",
                "--run-pid", "999999", "--state-file", str(sf),
                "--log-file", str(tmp_path / "c.log"), "--interval", "1"]
        assert wd.main(argv) == 0
        rec = json.loads((tmp_path / "OLD1.json").read_text())
        assert rec["status"] == "completed"
