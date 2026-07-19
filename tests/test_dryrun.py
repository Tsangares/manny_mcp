"""Tests for the offline routine dry-run interpreter (``mcptools.dryrun``).

Covers:
  * both shipped money-makers dry-run PASS end-to-end with sane durations,
  * a deliberately-broken routine (impossible await + mixed loop-condition
    vocabulary + a blocking-command timeout trap) FAILS with the right
    diagnosis,
  * the StateModel effect table and control-flow (inner/outer + flat loops)
    behave as the engine would.

No client, no login -- pure offline simulation.
"""
import os

import pytest
import yaml

from mcptools import dryrun

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COWHIDE = os.path.join(REPO, "routines/money_making/cowhide_banking.yaml")
FEATHERS = os.path.join(REPO, "routines/money_making/chicken_feathers.yaml")


def _write(tmp_path, doc):
    p = tmp_path / "r.yaml"
    p.write_text(yaml.safe_dump(doc))
    return str(p)


@pytest.mark.asyncio
class TestMoneyMakersPass:
    async def test_cowhide_banking_passes(self):
        res = await dryrun.dry_run_routine(COWHIDE, max_loops=1)
        assert res["success"] is True, res["failures"]
        assert res["failures"] == []
        # Inner kill loop fills the inventory -> inventory_full -> banks -> returns.
        assert res["steps_simulated"] >= 24
        assert res["loops_completed"] == 1
        # A full field<->bank cycle is minutes, not seconds or days.
        assert 60_000 < res["simulated_wall_clock_ms"] < 6 * 3600_000

    async def test_chicken_feathers_passes(self):
        res = await dryrun.dry_run_routine(FEATHERS, max_loops=1)
        assert res["success"] is True, res["failures"]
        assert res["failures"] == []
        # Feathers stack, so no inventory_full; flat loop bounded by max_loops.
        assert res["loops_completed"] == 1
        # 1000-kill batch estimate stays under the routine's 6h timeout_ms.
        assert res["simulated_wall_clock_ms"] < 21_600_000

    async def test_two_loops_cowhide_still_passes(self):
        res = await dryrun.dry_run_routine(COWHIDE, max_loops=2)
        assert res["success"] is True, res["failures"]
        assert res["loops_completed"] == 2


@pytest.mark.asyncio
class TestBrokenRoutineFails:
    async def test_impossible_await_and_mixed_loop_vocab(self, tmp_path):
        """One routine exercising three bug classes at once:

        - step 2 await 'has_item:Gold bar' after a GOTO that produces no item
          -> guaranteed-timeout step,
        - step 3 await 'inventory_full' -> Grammar-2 atom in a Grammar-1 slot
          (invalid await / vocabulary mixing),
        - flat loop stop_condition 'location:1,2' -> Grammar-1 atom in a
          Grammar-2 slot (silent never-trigger).
        """
        doc = {
            "name": "broken",
            "steps": [
                {"id": 1, "action": "GOTO", "args": "10 20 0",
                 "await_condition": "location:10,20"},
                {"id": 2, "action": "GOTO", "args": "11 21 0",
                 "await_condition": "has_item:Gold bar"},
                {"id": 3, "action": "GOTO", "args": "12 22 0",
                 "await_condition": "inventory_full"},
            ],
            "loop": {"enabled": True, "repeat_from_step": 1,
                     "stop_conditions": ["location:1,2"]},
        }
        res = await dryrun.dry_run_routine(_write(tmp_path, doc), max_loops=1)
        assert res["success"] is False
        joined = " ".join(res["failures"])
        # Impossible await surfaced with the guaranteed-timeout diagnosis.
        assert "has_item:Gold bar" in joined and "guaranteed-timeout" in joined
        # Vocabulary mixing surfaced for the Grammar-2 atom in an await slot.
        assert "inventory_full" in joined
        # Mixed loop vocabulary surfaced as a warning (silent never-trigger).
        assert any("location:1,2" in w and "Grammar-2" in w for w in res["warnings"])

    async def test_blocking_command_timeout_trap(self, tmp_path):
        """A KILL_LOOP whose modeled batch outruns its timeout_ms is flagged."""
        doc = {
            "name": "timeout-trap",
            "steps": [
                {"id": 1, "action": "KILL_LOOP", "args": "Cow none 1000",
                 "timeout_ms": 60000},  # 1000 kills modeled >> 60s
            ],
        }
        res = await dryrun.dry_run_routine(_write(tmp_path, doc), max_loops=1)
        assert res["success"] is False
        assert any("exceeds timeout_ms" in f for f in res["failures"])

    async def test_blocking_command_with_await_flagged(self, tmp_path):
        """Pairing a blocking command with await_condition (esp. idle) fails."""
        doc = {
            "name": "blocking-await",
            "steps": [
                {"id": 1, "action": "MINE_ORE", "args": "Iron 1",
                 "await_condition": "idle", "timeout_ms": 300000},
            ],
        }
        res = await dryrun.dry_run_routine(_write(tmp_path, doc), max_loops=1)
        assert res["success"] is False
        assert any("await_condition" in f for f in res["failures"])

    async def test_repeat_until_wrong_grammar_fails(self, tmp_path):
        doc = {
            "name": "bad-repeat-until",
            "steps": [
                {"id": 1, "action": "CLICK_CONTINUE",
                 "repeat_until": "inventory_full", "max_iterations": 5},
            ],
        }
        res = await dryrun.dry_run_routine(_write(tmp_path, doc), max_loops=1)
        assert res["success"] is False
        assert any("repeat_until" in f for f in res["failures"])

    async def test_no_steps_fails(self, tmp_path):
        p = tmp_path / "empty.yaml"
        p.write_text(yaml.safe_dump({"name": "empty"}))
        res = await dryrun.dry_run_routine(str(p), max_loops=1)
        assert res["success"] is False
        assert "no steps" in res["error"].lower()


@pytest.mark.asyncio
class TestControlFlow:
    async def test_repeat_until_dialogue_drain_passes(self, tmp_path):
        """CLICK_CONTINUE + repeat_until:no_dialogue is the canonical drain and
        must pass (the effect closes the dialogue)."""
        doc = {
            "name": "drain",
            "steps": [
                {"id": 1, "action": "CLICK_CONTINUE",
                 "repeat_until": "no_dialogue", "max_iterations": 15},
            ],
        }
        res = await dryrun.dry_run_routine(_write(tmp_path, doc), max_loops=1)
        assert res["success"] is True, res["failures"]

    async def test_dialogue_advance_grants_item_via_declared_await(self, tmp_path):
        """A quest item handed over across a CLICK_CONTINUE is unknowable to the
        model, so the declared has_item await/repeat_until is trusted
        (assume-postcondition) rather than false-failed. Mirrors restless_ghost
        step 8 and romeo_and_juliet step 19."""
        doc = {
            "name": "reward-dialogue",
            "steps": [
                {"id": 1, "action": "INTERACT_NPC", "args": "Priest Talk-to",
                 "await_condition": "dialogue"},
                {"id": 2, "action": "CLICK_CONTINUE", "repeat": 5,
                 "await_condition": "has_item:Ghostspeak amulet"},
                {"id": 3, "action": "CLICK_CONTINUE",
                 "repeat_until": "has_item:Cadava potion"},
            ],
        }
        res = await dryrun.dry_run_routine(_write(tmp_path, doc), max_loops=1)
        assert res["success"] is True, res["failures"]

    async def test_mine_inner_loop_terminates_on_inventory_full(self, tmp_path):
        """A MINE_ORE inner loop gating on inventory_full must EXIT (gather-fill
        models the full inventory) rather than spin to the safety cap."""
        doc = {
            "name": "mine-inner",
            "steps": [
                {"id": 1, "action": "MINE_ORE", "args": "iron 1",
                 "timeout_ms": 45000},
                {"id": 2, "action": "BANK_DEPOSIT_ALL"},
            ],
            "loop": {"inner": {"enabled": True, "start_step": 1, "end_step": 1,
                               "exit_conditions": ["inventory_full"],
                               "on_exit": "goto_step:2"},
                     "outer": {"enabled": True, "start_step": 1, "end_step": 2,
                               "exit_conditions": []}},
        }
        res = await dryrun.dry_run_routine(_write(tmp_path, doc), max_loops=1)
        assert res["success"] is True, res["failures"]
        assert not any("safety cap" in w for w in res["warnings"])

    async def test_on_failure_continue_marches_on_but_reports(self, tmp_path):
        """A failed step with on_failure:continue keeps simulating yet the run
        is still reported as failed (the silent-march-on class made visible)."""
        doc = {
            "name": "march-on",
            "steps": [
                {"id": 1, "action": "GOTO", "args": "1 2 0",
                 "await_condition": "has_item:Nope", "on_failure": "continue"},
                {"id": 2, "action": "GOTO", "args": "3 4 0",
                 "await_condition": "location:3,4"},
            ],
        }
        res = await dryrun.dry_run_routine(_write(tmp_path, doc), max_loops=1)
        assert res["success"] is False
        # Step 2 still ran (marched on) even though step 1 failed.
        assert res["steps_simulated"] == 2
        assert any("MARCH ON" in e["detail"] for e in res["trace"])

    async def test_on_failure_abort_stops(self, tmp_path):
        doc = {
            "name": "abort",
            "steps": [
                {"id": 1, "action": "GOTO", "args": "1 2 0",
                 "await_condition": "has_item:Nope", "on_failure": "abort"},
                {"id": 2, "action": "GOTO", "args": "3 4 0"},
            ],
        }
        res = await dryrun.dry_run_routine(_write(tmp_path, doc), max_loops=1)
        assert res["aborted"] is True
        assert res["aborted_at_step"] == 1
        assert res["steps_simulated"] == 1  # step 2 never reached


class TestStateModel:
    def test_deposit_empties_inventory(self):
        m = dryrun.StateModel(inventory=[{"name": "Cowhide", "qty": 1}])
        i = dryrun.DryRunInterpreter({"steps": []}, model=m)
        i._apply_effect("BANK_DEPOSIT_ALL", "")
        assert m.items == []

    def test_goto_sets_location(self):
        m = dryrun.StateModel()
        i = dryrun.DryRunInterpreter({"steps": []}, model=m)
        i._apply_effect("GOTO", "100 200 1")
        assert (m.x, m.y, m.plane) == (100, 200, 1)

    def test_staircase_changes_plane(self):
        m = dryrun.StateModel(location=(0, 0, 0))
        i = dryrun.DryRunInterpreter({"steps": []}, model=m)
        i._apply_effect("INTERACT_OBJECT", "Staircase Climb-up")
        assert m.plane == 1
        i._apply_effect("INTERACT_OBJECT", "Staircase Climb-down")
        assert m.plane == 0

    def test_as_state_serves_both_grammars(self):
        m = dryrun.StateModel(location=(3208, 3220, 2),
                              inventory=[{"name": "Cowhide", "qty": 1}],
                              skills={"defence": {"level": 5}})
        s = m.as_state()
        # Grammar 1 shape
        assert s["player"]["location"]["plane"] == 2
        assert s["player"]["inventory"]["items"][0]["name"] == "Cowhide"
        # Grammar 2 shape
        assert s["inventory"]["used"] == 1
        assert s["player"]["skills"]["defence"]["level"] == 5

    def test_unknown_command_warns(self):
        i = dryrun.DryRunInterpreter({"steps": []}, model=dryrun.StateModel())
        i._apply_effect("TOTALLY_MADE_UP", "")
        assert any("Unknown command" in w for w in i.warnings)

    def test_known_plugin_command_does_not_warn(self):
        """A real plugin command with no modeled effect is a silent generic
        success -- NOT flagged unknown (that alarm is reserved for typos)."""
        i = dryrun.DryRunInterpreter({"steps": []}, model=dryrun.StateModel())
        for cmd in ("BANK_WITHDRAW", "USE_ITEM_ON_OBJECT", "CAMERA_STABILIZE",
                    "TELEPORT_HOME", "CLICK_WIDGET", "CLICK_NPC"):
            note, modeled = i._apply_effect(cmd, "x")
            assert modeled is False
        assert i.warnings == []

    def test_gather_command_fills_inventory(self):
        """MINE_ORE/CHOP_TREE/FISH accumulate -> fill the 28-slot inventory so
        an ``inventory_full`` inner-loop exit can actually trigger."""
        for cmd, args in (("MINE_ORE", "iron 1"), ("CHOP_TREE", "oak"),
                          ("FISH", "lobster")):
            m = dryrun.StateModel()
            i = dryrun.DryRunInterpreter({"steps": []}, model=m)
            i._apply_effect(cmd, args)
            assert len(m.items) == 28
        assert i.warnings == []

    def test_ladder_verbs_change_plane(self):
        m = dryrun.StateModel(location=(0, 0, 0))
        i = dryrun.DryRunInterpreter({"steps": []}, model=m)
        i._apply_effect("CLIMB_LADDER_UP", "")
        assert m.plane == 1
        i._apply_effect("CLIMB_LADDER_DOWN", "")
        assert m.plane == 0


def test_known_grammar2_recognizer():
    assert dryrun._is_known_grammar2("inventory_full")
    assert dryrun._is_known_grammar2("has_item:Coins")
    assert dryrun._is_known_grammar2("defence_level:20")
    assert not dryrun._is_known_grammar2("location:1,2")
    assert not dryrun._is_known_grammar2("plane:2")
    assert not dryrun._is_known_grammar2("idle")
