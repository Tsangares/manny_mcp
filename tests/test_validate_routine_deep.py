"""
Track C: deep-schema checks in `validate_routine_deep`.

`validate_routine_deep` is the machine-checkable routine schema. Each test below
seeds one routine that embodies a single bug class that was previously only ever
found live, and asserts the validator mechanically flags it. A golden-valid
routine asserts a clean pass so the checks don't over-fire.

Grammar / schema ground-truthed against:
  - mcptools/tools/monitoring.py  (_parse_condition / _check_condition)
  - mcptools/tools/routine.py     (check_stop_condition, run_routine, dispatch)
  - manny_src/utility/commands/*Command.java (blocking loops, KILL_LOOP args)
"""
import yaml

import manny_tools


def _write_yaml(tmp_path, name, data):
    p = tmp_path / name
    p.write_text(yaml.safe_dump(data))
    return str(p)


def _validate(path):
    # check_commands=False -> no dependency on a live PlayerHelpers.java parse.
    return manny_tools.validate_routine_deep(path, plugin_dir="/nonexistent",
                                             check_commands=False)


def _errs(res):
    return " || ".join(res["errors"])


def _warns(res):
    return " || ".join(res["warnings"])


# ---------------------------------------------------------------------------
# Golden valid routine -- must pass with zero errors AND zero warnings.
# ---------------------------------------------------------------------------
class TestGoldenValid:
    def test_clean_routine_passes(self, tmp_path):
        path = _write_yaml(tmp_path, "golden.yaml", {
            "name": "Golden",
            "type": "combat",
            "skill": "combat",
            "locations": {"coop": {"x": 3180, "y": 3288, "plane": 0}},
            "steps": [
                {"id": 1, "phase": "travel", "action": "GOTO",
                 "args": "3180 3288 0", "description": "walk",
                 "await_condition": "location:3180,3288", "timeout_ms": 20000},
                {"id": 2, "phase": "combat", "action": "KILL_LOOP",
                 "args": "Chicken none 100", "description": "kill",
                 "timeout_ms": 3600000},
            ],
            "loop": {"enabled": True, "repeat_from_step": 1,
                     "stop_conditions": ["inventory_full"]},
        })
        res = _validate(path)
        assert res["valid"] is True, _errs(res)
        assert res["errors"] == []
        assert res["warnings"] == [], _warns(res)


# ---------------------------------------------------------------------------
# Check 1: unknown / dead keys (top-level, step, loop) -> WARNING.
# ---------------------------------------------------------------------------
class TestUnknownKeys:
    def test_dead_top_level_key(self, tmp_path):
        path = _write_yaml(tmp_path, "top.yaml", {
            "name": "x", "threshold_percent": 50, "loot": {"items": ["Bones"]},
            "steps": [{"id": 1, "action": "GOTO", "args": "1 2 0",
                       "description": "d"}],
        })
        res = _validate(path)
        assert any("threshold_percent" in w for w in res["warnings"])
        assert any("loot" in w for w in res["warnings"])

    def test_dead_step_key_skip_if(self, tmp_path):
        path = _write_yaml(tmp_path, "step.yaml", {
            "name": "x",
            "steps": [{"id": 1, "action": "GOTO", "args": "1 2 0",
                       "description": "d", "skip_if": "has_item:Bones"}],
        })
        res = _validate(path)
        assert any("skip_if" in w for w in res["warnings"])

    def test_dead_step_key_location(self, tmp_path):
        # per Track B: the executor never reads a step's `location:`.
        path = _write_yaml(tmp_path, "loc.yaml", {
            "name": "x", "locations": {"a": {"x": 1, "y": 2, "plane": 0}},
            "steps": [{"id": 1, "action": "GOTO", "args": "1 2 0",
                       "description": "d", "location": "a"}],
        })
        res = _validate(path)
        assert any("dead key 'location'" in w for w in res["warnings"])

    def test_dead_loop_max_iterations(self, tmp_path):
        path = _write_yaml(tmp_path, "loopkey.yaml", {
            "name": "x",
            "steps": [{"id": 1, "action": "GOTO", "args": "1 2 0",
                       "description": "d"}],
            "loop": {"enabled": True, "repeat_from_step": 1,
                     "stop_conditions": ["inventory_full"],
                     "max_iterations": 50, "delay_between_loops_ms": 2000},
        })
        res = _validate(path)
        assert any("max_iterations" in w for w in res["warnings"])
        assert any("delay_between_loops_ms" in w for w in res["warnings"])

    def test_dead_flat_loop_start_step(self, tmp_path):
        path = _write_yaml(tmp_path, "flatstart.yaml", {
            "name": "x",
            "steps": [{"id": 1, "action": "GOTO", "args": "1 2 0",
                       "description": "d"}],
            "loop": {"enabled": True, "start_step": 1,
                     "stop_conditions": ["inventory_full"]},
        })
        res = _validate(path)
        assert any("start_step" in w for w in res["warnings"])

    def test_on_failure_is_a_known_step_key(self, tmp_path):
        # `on_failure` is a live per-step key (routine._parse_on_failure) --
        # it must NOT be flagged as an unknown/dead key.
        path = _write_yaml(tmp_path, "onfail.yaml", {
            "name": "x",
            "steps": [{"id": 1, "action": "BANK_OPEN",
                       "description": "d", "on_failure": "abort"},
                      {"id": 2, "action": "BANK_DEPOSIT_ALL",
                       "description": "d", "on_failure": "retry:2"}],
        })
        res = _validate(path)
        assert not any("on_failure" in w for w in res["warnings"]), _warns(res)


# ---------------------------------------------------------------------------
# Check 2: blocking-command timeout + no-await.
# ---------------------------------------------------------------------------
class TestBlockingCommandTimeout:
    def test_missing_timeout_errors(self, tmp_path):
        path = _write_yaml(tmp_path, "notimeout.yaml", {
            "name": "x",
            "steps": [{"id": 1, "action": "POWER_MINE", "args": "iron",
                       "description": "mine"}],
        })
        res = _validate(path)
        assert res["valid"] is False
        assert any("POWER_MINE" in e and "no timeout_ms" in e for e in res["errors"])

    def test_timeout_below_floor_errors(self, tmp_path):
        path = _write_yaml(tmp_path, "shorttimeout.yaml", {
            "name": "x",
            "steps": [{"id": 1, "action": "KILL_LOOP", "args": "Cow none 100",
                       "description": "kill", "timeout_ms": 30000}],
        })
        res = _validate(path)
        assert any("below the" in e and "floor" in e for e in res["errors"])

    def test_blocking_with_await_errors(self, tmp_path):
        path = _write_yaml(tmp_path, "fishawait.yaml", {
            "name": "x",
            "steps": [{"id": 1, "action": "FISH", "args": "lobster",
                       "description": "fish", "timeout_ms": 600000,
                       "await_condition": "inventory_count:>=28"}],
        })
        res = _validate(path)
        assert any("must not have an await_condition" in e for e in res["errors"])

    def test_blocking_with_idle_await_calls_out_idle(self, tmp_path):
        path = _write_yaml(tmp_path, "mineidle.yaml", {
            "name": "x",
            "steps": [{"id": 1, "action": "MINE_ORE", "args": "iron 5",
                       "description": "mine", "timeout_ms": 60000,
                       "await_condition": "idle"}],
        })
        res = _validate(path)
        assert any("`idle`" in e and "instantly" in e for e in res["errors"])

    def test_blocking_with_proper_timeout_no_await_ok(self, tmp_path):
        path = _write_yaml(tmp_path, "goodmine.yaml", {
            "name": "x",
            "steps": [{"id": 1, "action": "MINE_ORE", "args": "iron 5",
                       "description": "mine", "timeout_ms": 45000}],
        })
        res = _validate(path)
        assert not any("MINE_ORE" in e for e in res["errors"]), _errs(res)


# ---------------------------------------------------------------------------
# Check 3: flat vs nested loop schema exclusivity.
# ---------------------------------------------------------------------------
class TestLoopSchemaExclusivity:
    def test_mixed_flat_and_nested_errors(self, tmp_path):
        path = _write_yaml(tmp_path, "mixloop.yaml", {
            "name": "x",
            "steps": [{"id": 1, "action": "GOTO", "args": "1 2 0",
                       "description": "d"}],
            "loop": {"enabled": True, "repeat_from_step": 1,
                     "inner": {"enabled": True, "start_step": 1, "end_step": 1}},
        })
        res = _validate(path)
        assert any("mutually exclusive" in e for e in res["errors"])


# ---------------------------------------------------------------------------
# Check 4: condition vocabulary cross-use / unrecognized.
# ---------------------------------------------------------------------------
class TestConditionVocabulary:
    def test_await_using_stop_vocab_errors(self, tmp_path):
        path = _write_yaml(tmp_path, "awaitstop.yaml", {
            "name": "x",
            "steps": [{"id": 1, "action": "GOTO", "args": "1 2 0",
                       "description": "d",
                       "await_condition": "inventory_full"}],
        })
        res = _validate(path)
        assert any("await_condition" in e and "other vocabulary" in e
                   for e in res["errors"])

    def test_stop_using_await_vocab_errors(self, tmp_path):
        path = _write_yaml(tmp_path, "stopawait.yaml", {
            "name": "x",
            "steps": [{"id": 1, "action": "GOTO", "args": "1 2 0",
                       "description": "d"}],
            "loop": {"enabled": True, "repeat_from_step": 1,
                     "stop_conditions": ["idle"]},
        })
        res = _validate(path)
        assert any("stop/exit condition" in e and "other vocabulary" in e
                   for e in res["errors"])

    def test_unrecognized_stop_condition_errors_silent_false(self, tmp_path):
        path = _write_yaml(tmp_path, "badstop.yaml", {
            "name": "x",
            "steps": [{"id": 1, "action": "GOTO", "args": "1 2 0",
                       "description": "d"}],
            "loop": {"enabled": True, "repeat_from_step": 1,
                     "stop_conditions": ["hp_below:10"]},
        })
        res = _validate(path)
        assert any("SILENTLY returns" in e for e in res["errors"])

    def test_shared_atom_not_flagged(self, tmp_path):
        # has_item / no_item are valid in BOTH vocabularies -> no cross-use error.
        path = _write_yaml(tmp_path, "shared.yaml", {
            "name": "x",
            "steps": [{"id": 1, "action": "GOTO", "args": "1 2 0",
                       "description": "d",
                       "await_condition": "has_item:Bones",
                       "timeout_ms": 5000}],
            "loop": {"enabled": True, "repeat_from_step": 1,
                     "stop_conditions": ["no_item:Bones"]},
        })
        res = _validate(path)
        assert not any("vocabulary" in e for e in res["errors"]), _errs(res)


# ---------------------------------------------------------------------------
# Check 5: mcp_tool whitelist + args-must-be-dict.
# ---------------------------------------------------------------------------
class TestMcpToolChecks:
    def test_unknown_mcp_tool_errors(self, tmp_path):
        path = _write_yaml(tmp_path, "badmcp.yaml", {
            "name": "x",
            "steps": [{"id": 1, "mcp_tool": "teleport_home",
                       "args": {"x": 1}, "description": "d"}],
        })
        res = _validate(path)
        assert any("teleport_home" in e for e in res["errors"])

    def test_mcp_tool_string_args_errors(self, tmp_path):
        path = _write_yaml(tmp_path, "strargs.yaml", {
            "name": "x",
            "steps": [{"id": 1, "mcp_tool": "equip_item",
                       "args": "Bronze sword", "description": "d"}],
        })
        res = _validate(path)
        assert any("args must be a dict" in e for e in res["errors"])

    def test_click_text_is_whitelisted(self, tmp_path):
        # regression: click_text is a real dispatch arm (routine.py:1632).
        path = _write_yaml(tmp_path, "clicktext.yaml", {
            "name": "x",
            "steps": [{"id": 1, "mcp_tool": "click_text",
                       "args": {"text": "Yes"}, "description": "d"}],
        })
        res = _validate(path)
        assert not any("click_text" in e for e in res["errors"]), _errs(res)


# ---------------------------------------------------------------------------
# Check 6: unbounded flat loop -> WARNING.
# ---------------------------------------------------------------------------
class TestUnboundedLoop:
    def test_enabled_without_stop_conditions_warns(self, tmp_path):
        path = _write_yaml(tmp_path, "unbounded.yaml", {
            "name": "x",
            "steps": [{"id": 1, "action": "GOTO", "args": "1 2 0",
                       "description": "d"}],
            "loop": {"enabled": True, "repeat_from_step": 1},
        })
        res = _validate(path)
        assert any("bounded only by" in w for w in res["warnings"])


# ---------------------------------------------------------------------------
# Check 7: KILL_LOOP numeric 2nd arg (food name).
# ---------------------------------------------------------------------------
class TestKillLoopFoodArg:
    def test_numeric_second_arg_errors(self, tmp_path):
        path = _write_yaml(tmp_path, "killnum.yaml", {
            "name": "x",
            "steps": [{"id": 1, "action": "KILL_LOOP", "args": "Chicken 100",
                       "description": "kill", "timeout_ms": 3600000}],
        })
        res = _validate(path)
        assert any("2nd arg" in e and "food name" in e.lower()
                   for e in res["errors"])

    def test_none_food_arg_ok(self, tmp_path):
        path = _write_yaml(tmp_path, "killnone.yaml", {
            "name": "x",
            "steps": [{"id": 1, "action": "KILL_LOOP", "args": "Chicken none 100",
                       "description": "kill", "timeout_ms": 3600000}],
        })
        res = _validate(path)
        assert not any("2nd arg" in e for e in res["errors"]), _errs(res)

    def test_kill_cow_numeric_second_arg_ok(self, tmp_path):
        # KILL_COW args are `<food> [max_kills]` -- numeric 2nd arg is correct.
        path = _write_yaml(tmp_path, "cownum.yaml", {
            "name": "x",
            "steps": [{"id": 1, "action": "KILL_COW", "args": "Trout 100",
                       "description": "kill", "timeout_ms": 3600000}],
        })
        res = _validate(path)
        assert not any("2nd arg" in e for e in res["errors"]), _errs(res)


# ---------------------------------------------------------------------------
# Regression: the pre-fix chicken_killer_loop.yaml shape (numeric-food arg +
# dead loop.max_iterations key). This used to be a corpus-anchored test
# against the live routines/combat/chicken_killer_loop.yaml file, but that
# file was fixed in commit 0d600ee (proper `none` food arg, max_iterations
# dropped in favor of stop_conditions), decoupling the regression coverage
# from mutable corpus state. The buggy shape is now reproduced inline via
# tmp_path so this test stays stable regardless of corpus edits.
# ---------------------------------------------------------------------------
class TestCorpusChickenKiller:
    def test_chicken_killer_loop_flagged(self, tmp_path):
        path = _write_yaml(tmp_path, "chicken_killer_loop_buggy.yaml", {
            "name": "Chicken Killer Auto-Loop",
            "type": "combat",
            "skill": "combat",
            "steps": [
                {"id": 1, "phase": "combat", "action": "KILL_LOOP",
                 "args": "Chicken 100", "description": "Kill 100 chickens",
                 "timeout_ms": 3600000},
            ],
            "loop": {"enabled": True, "max_iterations": 50},
        })
        res = _validate(path)
        assert any("2nd arg" in e and "food name" in e.lower()
                   for e in res["errors"]), _errs(res)
        assert any("max_iterations" in w for w in res["warnings"]), _warns(res)

    def test_nested_inner_loop_kill_body_not_flagged(self, tmp_path):
        # Finding 9: a KILL_LOOP that is the single-step body of a nested inner
        # loop with a proper exit (start_step==end_step, exit_conditions + on_exit)
        # is correctly non-terminal -- the loop jumps away via on_exit. It must
        # NOT trip the "not the last step" warning (cowhide_banking.yaml shape).
        path = _write_yaml(tmp_path, "nested_ok.yaml", {
            "name": "Nested Kill/Bank",
            "type": "money_making",
            "skill": "combat",
            "steps": [
                {"id": 1, "phase": "travel", "action": "GOTO", "args": "1 2 0",
                 "description": "walk", "await_condition": "location:1,2",
                 "timeout_ms": 20000},
                {"id": 2, "phase": "combat", "action": "KILL_LOOP_CONFIG",
                 "args": "cfg.json", "description": "kill batch",
                 "timeout_ms": 3600000},
                {"id": 3, "phase": "banking", "action": "BANK_OPEN",
                 "description": "bank"},
            ],
            "loop": {
                "inner": {"enabled": True, "start_step": 2, "end_step": 2,
                          "exit_conditions": ["inventory_full"],
                          "on_exit": "goto_step:3"},
                "outer": {"enabled": True, "start_step": 1, "end_step": 3,
                          "exit_conditions": []},
            },
        })
        res = _validate(path)
        assert not any("not the last step" in w.lower() or "NOT the" in w
                       for w in res["warnings"]), _warns(res)

    def test_nested_inner_loop_without_exit_still_flagged(self, tmp_path):
        # A nested inner loop MISSING a real exit (no on_exit) is genuinely
        # non-terminal -> the warning must still fire.
        path = _write_yaml(tmp_path, "nested_bad.yaml", {
            "name": "Nested No Exit",
            "type": "money_making",
            "skill": "combat",
            "steps": [
                {"id": 1, "phase": "combat", "action": "KILL_LOOP",
                 "args": "Cow none 100", "description": "kill",
                 "timeout_ms": 3600000},
                {"id": 2, "phase": "banking", "action": "BANK_OPEN",
                 "description": "bank"},
            ],
            "loop": {
                "inner": {"enabled": True, "start_step": 1, "end_step": 1,
                          "exit_conditions": ["inventory_full"]},
                "outer": {"enabled": True, "start_step": 1, "end_step": 2,
                          "exit_conditions": []},
            },
        })
        res = _validate(path)
        assert any("not the last" in w.lower() for w in res["warnings"]), _warns(res)

    def test_live_chicken_killer_loop_now_clean(self):
        # Corpus-health check: the real routine, post-fix (commit 0d600ee),
        # must validate with zero errors.
        import os
        repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        path = os.path.join(repo, "routines/combat/chicken_killer_loop.yaml")
        if not os.path.exists(path):
            import pytest
            pytest.skip("chicken_killer_loop.yaml not present")
        res = _validate(path)
        assert res["errors"] == [], _errs(res)


# ---------------------------------------------------------------------------
# Non-executable stubs stay exempt from the deep schema checks.
# ---------------------------------------------------------------------------
class TestStubExemption:
    def test_config_sidecar_not_deep_checked(self, tmp_path):
        path = _write_yaml(tmp_path, "hill_giants.yaml", {
            "name": "Hill Giants", "type": "combat", "npc": "Hill Giant",
            "loot": {"items": ["Law rune"]}, "eating": {"food": "Tuna"},
        })
        res = _validate(path)
        assert res["non_executable"] is True
        # freeform sidecar keys must NOT be flagged as dead top-level keys
        assert not any("loot" in w for w in res["warnings"]), _warns(res)
