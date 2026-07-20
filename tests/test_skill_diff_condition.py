"""Tests for the `skill_diff:<a>-<b>:<op>N` loop stop/exit-condition atom.

The atom expresses BALANCED-TRAINING gates in Grammar 2 (loop
`stop_conditions:`/`exit_conditions:`): the signed BASE-level difference
`level(a) - level(b)`. e.g. `skill_diff:attack-strength:>=3` == "stop once
attack is at least 3 levels ABOVE strength". It complements the pre-existing
`<skill>_level:N` gate (which already covers absolute level targets); no
`skill:<name>:<op>N` atom is added -- that would duplicate `<skill>_level:N`.

Ground-truth properties this locks in:
  - SIGN direction: level(a) - level(b) (a ahead of b is POSITIVE).
  - BASE level only: reads `.level` (getRealSkillLevel), NOT `.boostedLevel`,
    so potion/prayer boosts never false-trigger a style switch.
  - HONESTY on missing state: if EITHER skill is absent (stale/partial read)
    the diff is UNKNOWN -> False (never stops) -- stricter than `<skill>_level:N`,
    which defaults a missing skill to 0.
  - It is a Grammar-2 atom ONLY; used as a step await_condition it is flagged.
  - Deep validator rejects unknown skill names and malformed comparisons.
"""
import pytest

import manny_tools
from mcptools import dryrun
from mcptools.tools import routine


# ---------------------------------------------------------------------------
# Pure parser (routine.parse_skill_diff)
# ---------------------------------------------------------------------------
class TestParseSkillDiff:
    def test_ge_parses(self):
        assert routine.parse_skill_diff("skill_diff:attack-strength:>=3") == (
            "attack", "strength", ">=", 3)

    def test_le_parses(self):
        assert routine.parse_skill_diff("skill_diff:attack-defence:<=2") == (
            "attack", "defence", "<=", 2)

    def test_gt_lt_parse(self):
        assert routine.parse_skill_diff("skill_diff:strength-attack:>1") == (
            "strength", "attack", ">", 1)
        assert routine.parse_skill_diff("skill_diff:defence-attack:<5") == (
            "defence", "attack", "<", 5)

    def test_bare_value_is_equals(self):
        assert routine.parse_skill_diff("skill_diff:attack-strength:0") == (
            "attack", "strength", "==", 0)

    def test_negative_target(self):
        assert routine.parse_skill_diff("skill_diff:attack-strength:>=-2") == (
            "attack", "strength", ">=", -2)

    def test_case_insensitive_skill_names(self):
        assert routine.parse_skill_diff("skill_diff:Attack-Strength:>=3") == (
            "attack", "strength", ">=", 3)

    @pytest.mark.parametrize("bad", [
        "skill_diff:attack-strength",       # missing comparison
        "skill_diff:attack:>=3",            # only one skill
        "skill_diff:-strength:>=3",         # empty first skill
        "skill_diff:attack-strength:>=abc",  # non-int target
    ])
    def test_malformed_raises(self, bad):
        with pytest.raises(ValueError):
            routine.parse_skill_diff(bad)


# ---------------------------------------------------------------------------
# Runtime evaluation (routine.check_stop_condition) -- SIGN + operators + honesty
# ---------------------------------------------------------------------------
def _skills(**levels):
    """Build a player.skills export; each value is {'level': base, 'boostedLevel': boosted}."""
    out = {}
    for name, v in levels.items():
        if isinstance(v, tuple):
            base, boosted = v
        else:
            base, boosted = v, v
        out[name] = {"level": base, "boostedLevel": boosted, "xp": 0}
    return out


@pytest.fixture
def patch_state(monkeypatch):
    """Point routine.get_game_state at a supplied fixture dict."""
    def _set(state):
        async def _fake(account_id=None):
            return state
        monkeypatch.setattr(routine, "get_game_state", _fake)
    return _set


@pytest.mark.asyncio
class TestCheckSkillDiff:
    async def _eval(self, patch_state, skills, cond):
        patch_state({"player": {"skills": skills}})
        return await routine.check_stop_condition(cond)

    async def test_sign_a_ahead_is_positive(self, patch_state):
        # attack 13, strength 10 -> diff +3 -> attack-strength:>=3 is TRUE.
        s = _skills(attack=13, strength=10)
        assert await self._eval(patch_state, s, "skill_diff:attack-strength:>=3") is True
        # The SAME state read the other direction (strength-attack) is -3, NOT >=3.
        assert await self._eval(patch_state, s, "skill_diff:strength-attack:>=3") is False

    async def test_ge_boundary(self, patch_state):
        s = _skills(attack=12, strength=10)  # diff +2
        assert await self._eval(patch_state, s, "skill_diff:attack-strength:>=3") is False
        assert await self._eval(patch_state, s, "skill_diff:attack-strength:>=2") is True

    async def test_le_and_equals(self, patch_state):
        s = _skills(attack=10, strength=10)  # diff 0
        assert await self._eval(patch_state, s, "skill_diff:attack-strength:<=0") is True
        assert await self._eval(patch_state, s, "skill_diff:attack-strength:0") is True
        assert await self._eval(patch_state, s, "skill_diff:attack-strength:>0") is False

    async def test_reads_base_not_boosted(self, patch_state):
        # Base attack 10 == base strength 10 (diff 0), but attack is BOOSTED to 15
        # (e.g. a potion). A boosted read would show +5 and wrongly switch styles.
        s = _skills(attack=(10, 15), strength=(10, 10))
        assert await self._eval(patch_state, s, "skill_diff:attack-strength:>=3") is False

    async def test_missing_skill_is_unknown_false(self, patch_state):
        # strength absent from a partial read: diff UNKNOWN -> False (never stop).
        s = _skills(attack=50)
        assert await self._eval(patch_state, s, "skill_diff:attack-strength:>=3") is False

    async def test_empty_skills_is_unknown_false(self, patch_state):
        assert await self._eval(patch_state, {}, "skill_diff:attack-strength:>=3") is False

    async def test_malformed_atom_never_silently_stops(self, patch_state):
        s = _skills(attack=99, strength=1)
        # Even wildly-satisfied-looking but malformed atoms must return False.
        assert await self._eval(patch_state, s, "skill_diff:attack-strength") is False


# ---------------------------------------------------------------------------
# Deep validator (manny_tools) -- both vocabularies + unknown-skill error
# ---------------------------------------------------------------------------
class TestValidatorVocabulary:
    def test_skill_diff_is_valid_stop_condition(self):
        assert manny_tools._stop_condition_error("skill_diff:attack-strength:>=3") is None

    def test_existing_level_atom_still_valid(self):
        assert manny_tools._stop_condition_error("mining_level:60") is None

    def test_unknown_skill_is_error(self):
        err = manny_tools._stop_condition_error("skill_diff:attak-strength:>=3")
        assert err is not None and "unknown skill" in err.lower()

    def test_malformed_comparison_is_error(self):
        err = manny_tools._stop_condition_error("skill_diff:attack-strength:>=x")
        assert err is not None

    def test_only_one_skill_is_error(self):
        err = manny_tools._stop_condition_error("skill_diff:attack:>=3")
        assert err is not None

    def test_skill_diff_in_await_slot_is_flagged(self):
        # Grammar-2 atom used as a Grammar-1 step await_condition -> flagged.
        err = manny_tools._await_condition_error("skill_diff:attack-strength:>=3")
        assert err is not None and "vocabulary" in err.lower()


class TestValidatorEndToEnd:
    def _validate(self, tmp_path, stop_conditions):
        import yaml
        doc = {
            "name": "diff", "type": "combat",
            "steps": [
                {"id": 1, "phase": "combat", "action": "KILL_LOOP",
                 "args": "Chicken none 100", "description": "kill",
                 "timeout_ms": 3600000},
            ],
            "loop": {"enabled": True, "repeat_from_step": 1,
                     "stop_conditions": stop_conditions},
        }
        p = tmp_path / "r.yaml"
        p.write_text(yaml.safe_dump(doc))
        return manny_tools.validate_routine_deep(str(p), plugin_dir="/nonexistent",
                                                 check_commands=False)

    def test_valid_skill_diff_routine_passes(self, tmp_path):
        res = self._validate(tmp_path, ["skill_diff:attack-strength:>=3"])
        assert res["valid"] is True, " || ".join(res["errors"])

    def test_unknown_skill_routine_fails(self, tmp_path):
        res = self._validate(tmp_path, ["skill_diff:atack-strength:>=3"])
        assert res["valid"] is False
        assert any("unknown skill" in e.lower() for e in res["errors"])


# ---------------------------------------------------------------------------
# Dry-run: a small skill-gated flat loop reaches its gate (no infinite loop)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
class TestDryRunSkillGatedLoop:
    def _rotation_doc(self, stop):
        # accurate-style chicken loop: each pass trains attack (coarse model).
        return {
            "name": "accurate chickens",
            "type": "combat",
            "steps": [
                {"id": 1, "action": "SWITCH_COMBAT_STYLE", "args": "accurate",
                 "description": "train attack"},
                {"id": 2, "action": "KILL_LOOP", "args": "Chicken none 100",
                 "description": "kill", "timeout_ms": 3600000},
            ],
            "loop": {"enabled": True, "repeat_from_step": 1,
                     "stop_conditions": [stop]},
        }

    async def test_diff_loop_stops_via_condition(self):
        # attack 5 == strength 5. accurate style trains attack +1/pass; after 3
        # passes attack 8 - strength 5 == 3 -> skill_diff:attack-strength:>=3.
        model = dryrun.StateModel(skills={
            "attack": {"level": 5}, "strength": {"level": 5},
            "defence": {"level": 5}, "hitpoints": {"level": 10}})
        interp = dryrun.DryRunInterpreter(
            self._rotation_doc("skill_diff:attack-strength:>=3"),
            model=model, max_loops=25)
        res = await interp.run()
        assert res["success"] is True, res.get("failures")
        assert "skill_diff:attack-strength:>=3" in (res.get("stop_reason") or "")
        assert res["loops_completed"] == 3
        # Strength never trained (style was accurate) -- the whole point.
        assert model.skills["strength"]["level"] == 5
        assert model.skills["attack"]["level"] == 8

    async def test_below_gate_runs_to_max_loops_not_infinite(self):
        # Only 2 passes allowed: attack reaches 7, diff 2 < 3 -> bounded stop.
        model = dryrun.StateModel(skills={
            "attack": {"level": 5}, "strength": {"level": 5},
            "hitpoints": {"level": 10}})
        interp = dryrun.DryRunInterpreter(
            self._rotation_doc("skill_diff:attack-strength:>=3"),
            model=model, max_loops=2)
        res = await interp.run()
        assert res["loops_completed"] == 2
        assert "max_loops" in (res.get("stop_reason") or "")

    async def test_fixture_already_at_gate_stops_first_pass(self):
        # No training needed: fixture already diff +5. Exercises the pure
        # fixture path (independent of the coarse kill-loop training model).
        model = dryrun.StateModel(skills={
            "attack": {"level": 15}, "strength": {"level": 10}})
        doc = {
            "name": "already ahead", "type": "combat",
            "steps": [{"id": 1, "action": "WAIT", "args": "600",
                       "description": "noop"}],
            "loop": {"enabled": True, "repeat_from_step": 1,
                     "stop_conditions": ["skill_diff:attack-strength:>=3"]},
        }
        interp = dryrun.DryRunInterpreter(doc, model=model, max_loops=10)
        res = await interp.run()
        assert res["loops_completed"] == 1
        assert "skill_diff" in (res.get("stop_reason") or "")

    async def test_dryrun_recognizes_skill_diff_as_grammar2(self):
        # No "not a recognized Grammar-2 atom" warning for skill_diff.
        model = dryrun.StateModel(skills={"attack": {"level": 5},
                                          "strength": {"level": 5}})
        interp = dryrun.DryRunInterpreter(
            self._rotation_doc("skill_diff:attack-strength:>=99"),
            model=model, max_loops=1)
        res = await interp.run()
        assert not any("not a recognized grammar-2" in w.lower()
                       for w in res["warnings"]), res["warnings"]
