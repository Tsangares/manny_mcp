"""Tests for the `varp:<id>:<op>N` / `varbit:<id>:<op>N` step-condition atoms
(task #26 -- generic quest-state gate).

The plugin exports an allowlisted set of VarPlayers/Varbits as a TOP-LEVEL
`vars` object ({"varps": {"<id>": int}, "varbits": {"<id>": int}}), mirroring
how `tutorial.progress` (varbit 281) was added. These atoms let a step
await_condition gate on arbitrary game-truth quest state (e.g. Cook's
Assistant, VarPlayer 29) instead of proxying on inventory contents.

Critical compatibility property (mirrors tutorial_progress exactly): against
an OLD jar (no `vars` section), a state missing the `varps`/`varbits`
sub-section, or an id absent from the export (not allowlisted, or genuinely
unknown), the condition must evaluate UNKNOWN (False), NOT raise -- so old
state files keep working and an un-allowlisted id is a silent no-op rather
than a crash.

It is a STEP-vocabulary (Grammar 1) atom ONLY, like tutorial_progress: -- NOT
the loop stop/exit-condition (Grammar 2) vocabulary.
"""
import json
from unittest.mock import MagicMock

import pytest

import manny_tools
from mcptools import dryrun
from mcptools.tools import monitoring


# ---------------------------------------------------------------------------
# Parser (monitoring._parse_condition)
# ---------------------------------------------------------------------------
class TestParseVarpVarbit:
    def test_varp_ge_parses(self):
        assert monitoring._parse_condition("varp:29:>=1") == (
            "varp", (29, 1), ">=")

    def test_varp_le_parses(self):
        assert monitoring._parse_condition("varp:281:<=500") == (
            "varp", (281, 500), "<=")

    def test_varp_gt_parses(self):
        assert monitoring._parse_condition("varp:29:>1") == (
            "varp", (29, 1), ">")

    def test_varp_lt_parses(self):
        assert monitoring._parse_condition("varp:29:<2") == (
            "varp", (29, 2), "<")

    def test_varp_bare_value_parses_as_equals(self):
        assert monitoring._parse_condition("varp:29:2") == (
            "varp", (29, 2), "==")

    def test_varbit_parses_independently(self):
        assert monitoring._parse_condition("varbit:3550:==1") == (
            "varbit", (3550, 1), "==")

    def test_varbit_ge_parses(self):
        assert monitoring._parse_condition("varbit:3550:>=1") == (
            "varbit", (3550, 1), ">=")


# ---------------------------------------------------------------------------
# Evaluator (monitoring._check_condition)
# ---------------------------------------------------------------------------
class TestCheckVarpVarbit:
    def _state(self, varps=None, varbits=None):
        return {"player": {}, "vars": {"varps": varps or {}, "varbits": varbits or {}}}

    def test_varp_ge_satisfied_when_at_or_above(self):
        cond = ("varp", (29, 1), ">=")
        assert monitoring._check_condition(self._state(varps={"29": 1}), cond) is True
        assert monitoring._check_condition(self._state(varps={"29": 2}), cond) is True
        assert monitoring._check_condition(self._state(varps={"29": 0}), cond) is False

    def test_varp_le(self):
        cond = ("varp", (29, 1), "<=")
        assert monitoring._check_condition(self._state(varps={"29": 1}), cond) is True
        assert monitoring._check_condition(self._state(varps={"29": 0}), cond) is True
        assert monitoring._check_condition(self._state(varps={"29": 2}), cond) is False

    def test_varp_gt_and_lt(self):
        assert monitoring._check_condition(
            self._state(varps={"29": 2}), ("varp", (29, 1), ">")) is True
        assert monitoring._check_condition(
            self._state(varps={"29": 1}), ("varp", (29, 1), ">")) is False
        assert monitoring._check_condition(
            self._state(varps={"29": 0}), ("varp", (29, 1), "<")) is True

    def test_varp_equals(self):
        assert monitoring._check_condition(
            self._state(varps={"29": 2}), ("varp", (29, 2), "==")) is True
        assert monitoring._check_condition(
            self._state(varps={"29": 1}), ("varp", (29, 2), "==")) is False

    def test_varbit_namespace_is_independent_of_varp(self):
        # Same id, different namespace, different value -- must not conflate.
        state = self._state(varps={"3550": 0}, varbits={"3550": 1})
        assert monitoring._check_condition(state, ("varbit", (3550, 1), "==")) is True
        assert monitoring._check_condition(state, ("varp", (3550, 1), "==")) is False

    # --- OLD-JAR / UNKNOWN-ID COMPATIBILITY: must NOT crash, must evaluate False ---

    def test_missing_vars_section_is_unknown_not_crash(self):
        """Old jar: no `vars` key at all. Must return False, never raise."""
        state = {"player": {"location": {"x": 1, "y": 2, "plane": 0}}}
        assert monitoring._check_condition(state, ("varp", (29, 1), ">=")) is False
        assert monitoring._check_condition(state, ("varbit", (3550, 1), "==")) is False

    def test_null_vars_section_is_unknown(self):
        state = {"vars": None}
        assert monitoring._check_condition(state, ("varp", (29, 1), ">=")) is False

    def test_missing_sub_section_is_unknown(self):
        """`vars` present but no `varps`/`varbits` key."""
        state = {"vars": {}}
        assert monitoring._check_condition(state, ("varp", (29, 1), ">=")) is False
        assert monitoring._check_condition(state, ("varbit", (1, 1), "==")) is False

    def test_unallowlisted_id_absent_from_export_is_unknown(self):
        """An id not seeded in Java's VARP_ALLOWLIST is simply absent -- a
        quest gate on it silently never fires, never crashes."""
        state = self._state(varps={"29": 1, "281": 1000})
        assert monitoring._check_condition(state, ("varp", (99999, 1), ">=")) is False

    def test_zero_value_is_a_real_value(self):
        """varp value 0 (not-started) is real, distinct from "absent"."""
        state = self._state(varps={"29": 0})
        assert monitoring._check_condition(state, ("varp", (29, 0), ">=")) is True
        assert monitoring._check_condition(state, ("varp", (29, 1), ">=")) is False


# ---------------------------------------------------------------------------
# Dry-run fixture carries `vars`
# ---------------------------------------------------------------------------
class TestDryRunFixtureCarriesVars:
    def test_default_fixture_has_empty_vars(self):
        st = dryrun.StateModel().as_state()
        assert st["vars"] == {"varps": {}, "varbits": {}}
        assert monitoring._check_condition(st, ("varp", (29, 1), ">=")) is False

    def test_fixture_can_set_varp(self):
        st = dryrun.StateModel(varps={"29": 2}).as_state()
        assert st["vars"]["varps"]["29"] == 2
        assert monitoring._check_condition(st, ("varp", (29, 2), ">=")) is True

    def test_fixture_can_set_varbit(self):
        st = dryrun.StateModel(varbits={"3550": 1}).as_state()
        assert st["vars"]["varbits"]["3550"] == 1
        assert monitoring._check_condition(st, ("varbit", (3550, 1), "==")) is True


# ---------------------------------------------------------------------------
# Dry-run: unmodeled command + declared varp:/varbit: await is armed
# (mirrors the tutorial_progress ladder-gate pattern, c186adf).
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
class TestDryRunVarpAwaitArming:
    def _wait_doc(self, await_cond):
        return {
            "name": "quest gate", "type": "quest",
            "steps": [
                {"id": 1, "action": "WAIT", "args": "600",
                 "description": "wait for quest state",
                 "await_condition": await_cond, "timeout_ms": 5000},
            ],
        }

    async def test_ge_gate_armed_and_step_passes(self):
        model = dryrun.StateModel()
        interp = dryrun.DryRunInterpreter(self._wait_doc("varp:29:>=1"), model=model)
        res = await interp.run()
        assert res["success"] is True, res.get("failures")
        assert model.varps.get("29") == 1

    async def test_gt_gate_arms_n_plus_1(self):
        model = dryrun.StateModel()
        interp = dryrun.DryRunInterpreter(self._wait_doc("varp:29:>1"), model=model)
        res = await interp.run()
        assert res["success"] is True, res.get("failures")
        assert model.varps.get("29") == 2

    async def test_varbit_gate_armed_independently(self):
        model = dryrun.StateModel()
        interp = dryrun.DryRunInterpreter(self._wait_doc("varbit:3550:==1"), model=model)
        res = await interp.run()
        assert res["success"] is True, res.get("failures")
        assert model.varbits.get("3550") == 1
        assert model.varps == {}


# ---------------------------------------------------------------------------
# End-to-end through handle_await_state_change against a temp state file.
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
class TestAwaitVarpVarbit:
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

    async def test_met_when_varp_reached(self, monkeypatch, tmp_path):
        state = {"player": {}, "vars": {"varps": {"29": 2}, "varbits": {}}}
        result = await self._run(monkeypatch, tmp_path, state, "varp:29:>=1")
        assert result["success"] is True
        assert result["condition_met"] is True

    async def test_times_out_not_invalid_on_old_jar(self, monkeypatch, tmp_path):
        # No `vars` section (old jar): should TIME OUT, not "Invalid condition".
        state = {"player": {"location": {"x": 1, "y": 2, "plane": 0}}}
        result = await self._run(monkeypatch, tmp_path, state, "varp:29:>=1")
        assert result["success"] is False
        assert "invalid" not in (result.get("error", "").lower())


# ---------------------------------------------------------------------------
# Deep validator (manny_tools) -- vocabulary membership + format validation.
# ---------------------------------------------------------------------------
class TestValidatorVocabulary:
    def test_varp_is_valid_await_condition(self):
        assert manny_tools._await_condition_error("varp:29:>=1") is None

    def test_varbit_is_valid_await_condition(self):
        assert manny_tools._await_condition_error("varbit:3550:==1") is None

    def test_varp_missing_comparison_is_error(self):
        err = manny_tools._await_condition_error("varp:29")
        assert err is not None and "comparison" in err.lower()

    def test_varp_non_integer_id_is_error(self):
        err = manny_tools._await_condition_error("varp:abc:>=1")
        assert err is not None and "id" in err.lower()

    def test_varp_malformed_comparison_is_error(self):
        err = manny_tools._await_condition_error("varp:29:>=abc")
        assert err is not None

    def test_varp_used_as_stop_condition_is_flagged(self):
        # Grammar-1 atom used in the Grammar-2 slot -> flagged.
        err = manny_tools._stop_condition_error("varp:29:>=1")
        assert err is not None and "vocabulary" in err.lower()

    def test_await_vocab_help_lists_new_atoms(self):
        assert "varp:" in manny_tools._AWAIT_VOCAB_HELP
        assert "varbit:" in manny_tools._AWAIT_VOCAB_HELP


class TestValidatorEndToEnd:
    def _validate(self, tmp_path, await_condition):
        import yaml
        doc = {
            "name": "quest gate", "type": "quest",
            "steps": [
                {"id": 1, "phase": "quest", "action": "WAIT", "args": "600",
                 "description": "wait for quest state",
                 "await_condition": await_condition, "timeout_ms": 5000},
            ],
        }
        p = tmp_path / "r.yaml"
        p.write_text(yaml.safe_dump(doc))
        return manny_tools.validate_routine_deep(str(p), plugin_dir="/nonexistent",
                                                 check_commands=False)

    def test_valid_varp_routine_passes(self, tmp_path):
        res = self._validate(tmp_path, "varp:29:>=1")
        assert res["valid"] is True, " || ".join(res["errors"])

    def test_valid_varbit_routine_passes(self, tmp_path):
        res = self._validate(tmp_path, "varbit:3550:==1")
        assert res["valid"] is True, " || ".join(res["errors"])

    def test_malformed_varp_routine_fails(self, tmp_path):
        res = self._validate(tmp_path, "varp:abc:>=1")
        assert res["valid"] is False
