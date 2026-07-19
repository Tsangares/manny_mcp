"""Offline dry-run interpreter for ``steps:``/``loop:`` routines.

WHY THIS EXISTS
---------------
Every routine bug class found the hard way this week was discovered on a LIVE
account: silent step-failure march-on, await-condition vocabulary mixing
(Grammar 1 vs Grammar 2 -- see ROUTINE_SCHEMA.md (c)), blocking-command timeout
traps, flat-vs-nested loop-schema mixing, and guaranteed-timeout dialogue
steps. This module steps a routine through its control flow against a scripted,
dict-based ``StateModel`` fixture -- sending NO command to any client -- so
those sequencing/await bugs surface PRE-LOGIN instead of live at account risk.

It COMPLEMENTS ``validate_routine_deep`` (static schema linting); this is a
*dynamic* sequencing simulation: it walks the same loop/step/on_failure logic
``handle_execute_routine`` uses (reusing that engine's own helpers by import --
``_resolve_step_idx``, ``_parse_on_failure``, ``check_stop_condition``,
``interpolate_variables``, and monitoring's condition parser/checker) and
applies a small per-command *effect table* to a StateModel. Await conditions
are then evaluated against the mutated model:

- If a step's ``await_condition`` (Grammar 1) is NOT satisfied after the
  command's modeled effect, the real engine would poll to ``timeout_ms`` and
  fail -- so the dry-run reports a DRY-RUN FAILURE naming the step + reason.
  This is the key detection: guaranteed-timeout steps.
- A condition string in the wrong grammar slot is caught at parse time
  (Grammar 1) or flagged as an unrecognized no-op atom (Grammar 2).
- A blocking command whose modeled batch duration exceeds its ``timeout_ms``
  is flagged (the timeout trap that abandons a still-grinding loop).
- ``on_failure: continue`` is honored for control flow but the failure is
  still surfaced -- exactly the "silently marches on" class made visible.

HONEST LIMITS (dry-run CANNOT verify)
-------------------------------------
- Coordinate reachability / NAV collision / corner-cutting -- a GOTO's modeled
  effect ALWAYS lands the player on the target tile; a separate Java route-lint
  covers real pathing.
- NPC/object availability, ambiguous-name resolution, widget existence.
- Timing realism -- simulated durations are coarse per-command ESTIMATES, not
  measured; the simulated wall-clock is an order-of-magnitude sanity figure,
  not a prediction.
- Anything requiring live plugin/bank/world state (e.g. ``no_item_in_bank:``,
  which the engine itself refuses to evaluate offline).

A PASS here means "the step sequence, awaits and loop transitions are
self-consistent against the fixture"; it is a necessary, not sufficient,
gate before a live run.
"""
import json
import os

from .tools import monitoring, routine

# ---------------------------------------------------------------------------
# Command classification (mirrors ROUTINE_SCHEMA.md (e)).
# ---------------------------------------------------------------------------
BLOCKING_COMMANDS = {
    "KILL_LOOP", "KILL_LOOP_CONFIG", "MINE_ORE", "CHOP_TREE", "FISH",
    "FISH_DROP", "FISH_DRAYNOR_LOOP", "COOK_ALL", "SMELT_BAR",
    "SMELT_BRONZE_BARS", "POWER_MINE", "POWER_CHOP", "KILL_COW_GET_HIDES",
}
KILL_LOOP_COMMANDS = {"KILL_LOOP", "KILL_LOOP_CONFIG"}

# Blocking gather commands that ACCUMULATE their yield into the inventory (as
# opposed to POWER_*/FISH_DROP which drop, or COOK_ALL/SMELT_* which transform).
# Modeled as filling the 28-slot inventory so an ``inventory_full`` inner-loop
# exit (the documented "mine/chop/fish until full then bank" pattern, e.g.
# skilling/mine_iron_ore.yaml) actually TERMINATES in the simulation instead of
# spinning to the step-execution safety cap. Justified by these commands'
# documented "until inventory full" semantics (COMMAND_REFERENCE.md Skilling /
# the routines' own inner-loop design).
GATHER_FILL_COMMANDS = {"MINE_ORE", "CHOP_TREE", "FISH", "KILL_COW_GET_HIDES"}

# Every command the Manny plugin actually exposes (COMMAND_REFERENCE.md, 131
# commands). A verb in this set but WITHOUT a specific modeled effect below is
# a legitimate command we simply don't simulate -- treated as generic success
# at its declared await (the honest unmodeled default), NOT flagged as unknown.
# The "unknown command" warning is reserved for verbs absent here (typos / not
# in the plugin), which is the signal actually worth surfacing.
KNOWN_COMMANDS = frozenset({
    "ATTACK_NPC", "BANK_CHECK", "BANK_CLOSE", "BANK_DEPOSIT_ALL",
    "BANK_DEPOSIT_EQUIPMENT", "BANK_DEPOSIT_ITEM", "BANK_OPEN", "BANK_WITHDRAW",
    "BURY_ALL", "BURY_ITEM", "BUY_GE", "CAMERA_PITCH", "CAMERA_POINT_AT",
    "CAMERA_RESET", "CAMERA_STABILIZE", "CAMERA_YAW", "CAST_SPELL",
    "CAST_SPELL_NPC", "CAST_SPELL_ON_GROUND_ITEM",
    "CAST_SPELL_ON_INVENTORY_ITEM", "CHECK_HP_THRESHOLD", "CHOP_TREE",
    "CLICK_AT", "CLICK_CHILD_WIDGET", "CLICK_CONTINUE", "CLICK_DIALOGUE",
    "CLICK_NPC", "CLICK_WIDGET", "CLIMB_LADDER_DOWN", "CLIMB_LADDER_UP",
    "CLOSE_INTERFACE", "COLLECT_LUMBRIDGE_TIN_COPPER", "COOK_ALL", "DESELECT",
    "DROP_ALL", "DROP_ITEM", "DUMP_COLLISION", "EAT", "EMERGENCY_STOP",
    "EQUIP_BEST_MELEE", "EQUIPMENT_LOG", "F2P_MODE", "FIND_GRAVE", "FIND_NPC",
    "FIND_OBJECT", "FISH", "FISH_DRAYNOR_LOOP", "FISH_DROP", "GE_ABORT",
    "GE_ADJUST_PRICE", "GE_BUY", "GE_CANCEL", "GE_CLICK_BUY", "GE_CLICK_SELL",
    "GE_COLLECT", "GE_CONFIRM", "GE_INPUT_PRICE", "GE_INPUT_QUANTITY",
    "GE_OPEN", "GE_SEARCH", "GE_SELECT_ITEM", "GE_SELL", "GE_SELL_ITEM",
    "GE_SET_QUANTITY", "GE_SLOW_BUY", "GET_GAME_STATE", "GET_LOCATIONS",
    "GET_QUEST_STATUS", "GOTO", "IMP_HUNT", "INTERACT_NPC", "INTERACT_OBJECT",
    "KEY_PRESS", "KILL", "KILL_COW", "KILL_COW_GET_HIDES", "KILL_LOOP",
    "KILL_LOOP_CONFIG", "LIGHT_FIRE", "LIST_COMMANDS", "LIST_OBJECTS", "LOGIN",
    "LOOT_GRAVE", "MINE_ORE", "MOUSE_CLICK", "MOUSE_MOVE", "PAUSE",
    "PICK_UP_ITEM", "PING", "POWER_CHOP", "POWER_MINE", "QUERY_EQUIPMENT",
    "QUERY_GROUND_ITEMS", "QUERY_INVENTORY", "QUERY_NPCS", "QUERY_PLAYERS",
    "QUERY_TRANSITIONS", "RANDOMIZE_CHARACTER", "RESUME", "SAVE_LOCATION",
    "SCAN_BANK", "SCAN_OBJECTS", "SCAN_TILEOBJECTS", "SCAN_WIDGETS",
    "SET_CONFIG", "SHOP_BUY", "SMELT_BAR", "SMELT_BRONZE", "SMELT_BRONZE_BARS",
    "START_PROCESSOR", "STOP", "STOP_PROCESSOR", "SWITCH_COMBAT_STYLE",
    "TAB_OPEN", "TALK_NPC", "TELEGRAB_WINE_LOOP", "TELEPORT", "TELEPORT_HOME",
    "TILE", "TILE_CLEAR", "TILE_CLEAR_ALL", "TILE_EXPORT", "TILE_LIST",
    "USE_ITEM_ON_ITEM", "USE_ITEM_ON_NPC", "USE_ITEM_ON_OBJECT", "VIZ_PATH",
    "VIZ_REGION", "WAIT", "WIKI_QUERY", "ZOOM",
})

# Grammar-2 atoms recognized by routine.check_stop_condition (ROUTINE_SCHEMA.md
# (c)). Used only to WARN when a loop condition is NOT one of these (it would
# silently never trigger). We do not re-implement evaluation -- that stays in
# routine.check_stop_condition, which we call for the actual truth value.
def _is_known_grammar2(cond: str) -> bool:
    cond = cond.strip()
    if cond == "inventory_full":
        return True
    for prefix in ("has_item:", "no_item:", "no_item_in_bank:"):
        if cond.startswith(prefix):
            return True
    return "_level:" in cond


# Loot items that stack (a full inventory is NOT the fill trigger for these).
# Anything else looted by a kill loop is treated as non-stackable and fills the
# 28-slot inventory -- which is what drives an ``inventory_full`` inner-loop
# exit for e.g. cowhides.
_STACKABLE_LOOT = {
    "feather", "coins", "law rune", "nature rune", "fire rune", "water rune",
    "air rune", "mind rune", "chaos rune", "death rune", "blood rune",
    "cosmic rune", "astral rune", "ashes",
}

# Coarse per-command duration estimates (ms). NOT timing-accurate -- see the
# module docstring's HONEST LIMITS. Used only for the simulated wall-clock and
# the blocking-timeout-trap check.
_MIN_STEP_MS = 800
_GOTO_MS_PER_TILE = 600
_GOTO_DEFAULT_MS = 3000
_STAIRCASE_MS = 3000
_BANK_MS = 1500
_KILL_MS_PER_ATTEMPT = 10000  # conservative worst-case seconds/kill


class StateModel:
    """Scripted, dict-based fixture the dry-run mutates and queries.

    ``as_state()`` renders a snapshot in the SAME shape the real state file
    uses, so BOTH condition grammars read it unchanged: Grammar 1 via
    ``monitoring._check_condition`` (reads ``player.*``, top-level
    ``dialogue``), Grammar 2 via ``routine.check_stop_condition`` (reads
    top-level ``inventory`` + ``player.skills``).
    """

    def __init__(self, location=(3222, 3218, 0), inventory=None, skills=None,
                 dialogue_open=False, is_moving=False):
        self.x, self.y, self.plane = location
        # inventory: list of {"name": str, "qty": int}
        self.items = [dict(i) for i in (inventory or [])]
        self.skills = {k.lower(): dict(v) for k, v in (skills or {}).items()}
        self.dialogue_open = dialogue_open
        self.is_moving = is_moving
        self.bank_open = False

    def add_item(self, name, qty=1, stackable=False):
        if stackable:
            for it in self.items:
                if it["name"].lower() == name.lower():
                    it["qty"] = it.get("qty", 1) + qty
                    return
            if len(self.items) < 28:
                self.items.append({"name": name, "qty": qty})
        else:
            for _ in range(qty):
                if len(self.items) >= 28:
                    break
                self.items.append({"name": name, "qty": 1})

    def fill_inventory(self, name):
        while len(self.items) < 28:
            self.items.append({"name": name, "qty": 1})

    def clear_inventory(self):
        self.items = []

    def as_state(self):
        items = [{"name": it["name"]} for it in self.items]
        used = len(self.items)
        return {
            "player": {
                "location": {"x": self.x, "y": self.y, "plane": self.plane},
                "inventory": {"used": used, "items": items},
                "skills": self.skills,
                "isMoving": self.is_moving,
            },
            # Grammar-2 (check_stop_condition) prefers this top-level shape.
            "inventory": {
                "used": used,
                "items": [f"{it['name']} x{it.get('qty', 1)}" for it in self.items],
            },
            "dialogue": {"open": self.dialogue_open},
        }


class DryRunInterpreter:
    """Walk a routine's control flow offline, mutating a StateModel.

    Mirrors ``handle_execute_routine``'s inner/outer + flat loop handling,
    ``on_failure`` policy, and ``repeat_until``/``repeat`` semantics, reusing
    the engine's own helpers so the two cannot drift on the parts that matter.
    """

    def __init__(self, routine_doc, model=None, max_loops=1, max_step_execs=100000):
        self.doc = routine_doc
        self.model = model or StateModel()
        self.max_loops = max_loops
        self.max_step_execs = max_step_execs
        self.trace = []
        self.failures = []
        self.warnings = []
        self.sim_ms = 0
        self.step_execs = 0
        # check_stop_condition reads the module-global get_game_state; point it
        # at our model for the duration of the run (restored in run()).
        self._saved_get_state = None

    # -- condition evaluation (reuse engine helpers) ------------------------

    def _eval_grammar1(self, cond):
        """(satisfied, error) using monitoring's pure parser+checker."""
        try:
            parsed = monitoring._parse_condition(cond)
        except ValueError as e:
            return None, str(e)
        return monitoring._check_condition(self.model.as_state(), parsed), None

    async def _eval_grammar2(self, cond):
        """Truth value via routine.check_stop_condition (the real impl)."""
        try:
            return await routine.check_stop_condition(cond, None), None
        except NotImplementedError as e:
            return None, str(e)

    # -- effect table -------------------------------------------------------

    def _estimate_duration(self, action, args, timeout_ms):
        a = (action or "").upper()
        if a == "GOTO":
            parts = args.split()
            if len(parts) >= 2:
                try:
                    tx, ty = int(parts[0]), int(parts[1])
                    dist = max(abs(self.model.x - tx), abs(self.model.y - ty))
                    return max(_MIN_STEP_MS, dist * _GOTO_MS_PER_TILE)
                except ValueError:
                    return _GOTO_DEFAULT_MS
            return _GOTO_DEFAULT_MS
        if a == "INTERACT_OBJECT" and ("Climb" in args or "climb" in args):
            return _STAIRCASE_MS
        if a.startswith("BANK_"):
            return _BANK_MS
        if a in KILL_LOOP_COMMANDS:
            return self._kill_batch_ms(a, args)
        return _MIN_STEP_MS

    def _kill_batch_ms(self, action, args):
        kills, _npc, _loot = self._kill_config(action, args)
        return max(_MIN_STEP_MS, kills * _KILL_MS_PER_ATTEMPT)

    def _kill_config(self, action, args):
        """Return (kills, npc, loot_items) for a KILL_LOOP[_CONFIG] step."""
        if action.upper() == "KILL_LOOP_CONFIG":
            path = args.strip()
            try:
                with open(path) as fh:
                    cfg = json.load(fh)
                return (int(cfg.get("kills", 100)), cfg.get("npc", "?"),
                        cfg.get("loot_items", []))
            except (OSError, json.JSONDecodeError, ValueError):
                self.warnings.append(
                    f"KILL_LOOP_CONFIG: could not read config '{path}'; "
                    f"assuming 100 kills, rune-only loot")
                return 100, "?", []
        # Bare KILL_LOOP <npc> <food|none> [max_kills]: default loot is runes.
        parts = args.split()
        kills = 100
        if len(parts) >= 3:
            try:
                kills = int(parts[2])
            except ValueError:
                kills = 100
        npc = parts[0] if parts else "?"
        return kills, npc, ["Law rune", "Nature rune", "Fire rune", "Water rune"]

    def _apply_effect(self, action, args):
        """Mutate the model for ``action``; return ``(note, modeled)``.

        ``modeled`` is True for commands whose concrete effect we simulate
        (GOTO, BANK_*, KILL_LOOP*, gather-fill). Their awaits are then checked
        STRICTLY against that effect -- the source of the real detections (a
        GOTO whose await can't be reached, etc.).

        ``modeled`` is False for commands whose effect we do NOT simulate
        (INTERACT_NPC/OBJECT gathering, dialogue-advance content, ladder
        climbs, CAST_SPELL, EQUIP, TAB_OPEN, unknown verbs...). These are
        assumed to SUCCEED at their own declared
        ``await_condition`` postcondition (see ``_apply_await_postcondition``),
        because dry-run cannot know that e.g. "milk a cow" yields a bucket --
        the honest default is to trust the author's stated postcondition rather
        than false-positive on every gathering step."""
        a = (action or "").upper()
        if a == "GOTO":
            parts = args.split()
            if len(parts) >= 3:
                try:
                    self.model.x, self.model.y, self.model.plane = (
                        int(parts[0]), int(parts[1]), int(parts[2]))
                except ValueError:
                    pass
            elif len(parts) >= 2:
                try:
                    self.model.x, self.model.y = int(parts[0]), int(parts[1])
                except ValueError:
                    pass
            self.model.is_moving = False
            return f"moved to ({self.model.x},{self.model.y},p{self.model.plane})", True
        # Climbs are SOFT-modeled: a +/-1 plane guess, but marked unmodeled so a
        # declared ``plane:N`` await corrects it. OSRS undergrounds are often
        # plane-0-with-a-Y-offset (Tutorial Island combat, Dwarven Mine), so a
        # rigid +/-1 would false-positive on legitimate same-plane climb awaits.
        if a == "INTERACT_OBJECT" and ("Climb-up" in args or "Climb up" in args):
            self.model.plane += 1
            return f"climbed up (~plane {self.model.plane}, await-corrected)", False
        if a == "INTERACT_OBJECT" and ("Climb-down" in args or "Climb down" in args):
            self.model.plane = max(0, self.model.plane - 1)
            return f"climbed down (~plane {self.model.plane}, await-corrected)", False
        # Dedicated ladder verbs behave like the Climb INTERACT_OBJECT: a soft
        # +/-1 plane guess, marked unmodeled so a declared ``plane:N`` await
        # corrects it (undergrounds are often plane-0-with-a-Y-offset).
        if a == "CLIMB_LADDER_UP":
            self.model.plane += 1
            return f"climbed ladder up (~plane {self.model.plane}, await-corrected)", False
        if a == "CLIMB_LADDER_DOWN":
            self.model.plane = max(0, self.model.plane - 1)
            return f"climbed ladder down (~plane {self.model.plane}, await-corrected)", False
        if a in GATHER_FILL_COMMANDS:
            res = args.split()[0].capitalize() if args.split() else "Resource"
            self.model.fill_inventory(res)
            return f"gathered {res} until inventory full (blocking)", True
        if a == "BANK_OPEN":
            self.model.bank_open = True
            return "bank opened", True
        if a in ("BANK_DEPOSIT_ALL", "BANK_DEPOSIT_ITEM"):
            self.model.clear_inventory()
            return "inventory deposited (emptied)", True
        if a == "BANK_CLOSE":
            self.model.bank_open = False
            return "bank closed", True
        if a in KILL_LOOP_COMMANDS:
            return self._apply_kill_loop(a, args), True
        if a in ("CLICK_CONTINUE", "CLICK_DIALOGUE", "CLICK_TEXT", "KEY_PRESS"):
            # We model the ONE effect we can know -- closing/advancing the
            # dialogue -- but mark the step UNMODELED (False): the CONTENT a
            # dialogue delivers (a quest reward item, a skill grant) is exactly
            # as unknowable as what an NPC gather yields, so an item/skill await
            # falls back to the honest assume-declared-postcondition default
            # (e.g. Father Urhney handing over the Ghostspeak amulet across a
            # CLICK_CONTINUE). A ``dialogue``/``no_dialogue`` await is still
            # satisfied strictly by the modeled close.
            self.model.dialogue_open = False
            return "dialogue advanced/closed", False
        if a in ("SWITCH_COMBAT_STYLE", "TAB_OPEN", "WAIT", "INTERACT_NPC",
                 "INTERACT_OBJECT", "EQUIP_ITEM", "CAST_SPELL_NPC",
                 "CAST_SPELL_ON_INVENTORY_ITEM", "PICK_UP_ITEM"):
            return "ok (assumed success at declared await, if any)", False
        # A real plugin command we simply don't simulate: generic success at its
        # declared await (honest unmodeled default), no false "unknown" alarm.
        if action and a in KNOWN_COMMANDS:
            return "ok (assumed success at declared await, if any)", False
        # No ``action:`` at all -> an mcp_tool/no-op step reaching here via the
        # repeat_until path; not an "unknown command", just nothing to model.
        if not action:
            return "ok (no action; mcp_tool/no-op step)", False
        # Default effect for genuinely unknown commands (typo / not in plugin).
        self.warnings.append(
            f"Unknown command '{action}' -- modeled as generic success after "
            f"min duration (assumed success at its declared await). Verify it "
            f"exists in the plugin.")
        return "ok (unknown command, default effect)", False

    def _apply_await_postcondition(self, cond):
        """Optimistically mutate the model to satisfy a Grammar-1 ``cond``.

        Used only for unmodeled commands (see ``_apply_effect``): the await
        encodes the author's intended postcondition, so a command we don't
        simulate is assumed to have achieved it. Returns True if a mutation was
        applied. Never raises (bad conditions are caught by the strict path)."""
        try:
            ctype, value, op = monitoring._parse_condition(cond)
        except ValueError:
            return False
        m = self.model
        if ctype == "has_item":
            m.add_item(value, qty=1, stackable=True)
        elif ctype == "no_item":
            m.items = [it for it in m.items if it["name"].lower() != value.lower()]
        elif ctype == "location":
            m.x, m.y = value
        elif ctype == "plane":
            m.plane = value
        elif ctype == "idle":
            m.is_moving = False
        elif ctype == "dialogue":
            m.dialogue_open = bool(value)
        elif ctype == "inventory_count":
            target = value
            if op in ("<=", "<", "=="):
                cap = target if op != "<" else max(0, target - 1)
                m.items = m.items[:cap]
            elif op in (">=", ">"):
                need = target if op != ">" else target + 1
                while len(m.items) < min(28, need):
                    m.items.append({"name": "Filler", "qty": 1})
        else:
            return False
        return True

    def _apply_kill_loop(self, action, args):
        kills, npc, loot = self._kill_config(action, args)
        looted = []
        filled = False
        for item in (loot or []):
            if item.lower() in _STACKABLE_LOOT:
                self.model.add_item(item, qty=kills, stackable=True)
            else:
                self.model.fill_inventory(item)
                filled = True
            looted.append(item)
        note = f"killed up to {kills} {npc}; looted {looted or 'runes'}"
        if filled:
            note += " (inventory filled -> inventory_full)"
        return note

    # -- step execution -----------------------------------------------------

    def _config(self):
        return self.doc.get("config", {}) or {}

    def _interp(self, text):
        cfg = self._config()
        if text and cfg:
            return routine.interpolate_variables(str(text), cfg)
        return text

    async def _exec_step(self, step, loop_pass):
        """Simulate one step; append a trace entry; return (success, action)."""
        self.step_execs += 1
        step_id = step.get("id", "?")
        action = step.get("action")
        mcp_tool = step.get("mcp_tool")
        args = self._interp(step.get("args", "") if isinstance(step.get("args"), str) else "")
        timeout_ms = step.get("timeout_ms", 30000)
        await_cond = self._interp(step.get("await_condition"))
        repeat_until = self._interp(step.get("repeat_until"))

        status = "OK"
        details = []

        label = action or (f"mcp_tool:{mcp_tool}" if mcp_tool else "?")
        command = f"{action} {args}".strip() if action else label

        # repeat_until (Grammar 1 vocabulary) ------------------------------
        if repeat_until:
            _note, modeled = self._apply_effect(action, args)
            sat, err = self._eval_grammar1(repeat_until)
            if not sat and err is None and not modeled:
                # Unmodeled command: assume the loop achieves its predicate.
                self._apply_await_postcondition(repeat_until)
                sat, err = self._eval_grammar1(repeat_until)
            dur = self._estimate_duration(action, args, timeout_ms)
            self.sim_ms += dur
            if err is not None:
                status = "FAIL"
                details.append(
                    f"invalid repeat_until '{repeat_until}': {err} "
                    f"(wrong grammar? repeat_until uses step-level Grammar 1)")
            elif not sat:
                status = "FAIL"
                details.append(
                    f"repeat_until '{repeat_until}' NOT satisfied after the "
                    f"modeled effect -- would hit its max_iterations cap "
                    f"without becoming true (guaranteed-timeout drain step)")
            else:
                details.append(f"repeat_until '{repeat_until}' satisfied")
            return self._finish_step(step_id, label, command, dur, status, details, loop_pass, action)

        # mcp_tool steps: modeled as generic success (no live widget scan).
        if mcp_tool:
            self._apply_effect("EQUIP_ITEM" if mcp_tool == "equip_item" else "CLICK_TEXT", args)
            dur = _MIN_STEP_MS
            self.sim_ms += dur
            if isinstance(step.get("args"), str):
                self.warnings.append(
                    f"Step {step_id}: mcp_tool '{mcp_tool}' args is a bare "
                    f"string -> silently becomes {{}} at runtime (ROUTINE_SCHEMA.md (g))")
            details.append(f"mcp_tool '{mcp_tool}' (modeled success)")
            return self._finish_step(step_id, label, command, dur, status, details, loop_pass, action)

        # Blocking command sanity (ROUTINE_SCHEMA.md (e)) ------------------
        a = (action or "").upper()
        is_blocking = a in BLOCKING_COMMANDS
        if is_blocking and await_cond:
            status = "FAIL"
            details.append(
                f"blocking command {a} carries await_condition '{await_cond}' "
                f"-- fires instantly/wrongly; remove it (ROUTINE_SCHEMA.md (e))")

        # Apply the command effect, then evaluate the await.
        effect_note, modeled = self._apply_effect(action, args)
        details.append(effect_note)
        dur = self._estimate_duration(action, args, timeout_ms)

        if is_blocking:
            if dur > timeout_ms:
                status = "FAIL"
                details.append(
                    f"estimated batch ~{_fmt_ms(dur)} exceeds timeout_ms "
                    f"{_fmt_ms(timeout_ms)} -- runner would give up while the "
                    f"loop grinds on unmanaged (blocking-timeout trap)")
                self.sim_ms += timeout_ms
            else:
                self.sim_ms += dur
            if a in KILL_LOOP_COMMANDS:
                details.append(f"est. batch {_fmt_ms(dur)} (<= timeout {_fmt_ms(timeout_ms)})"
                               if dur <= timeout_ms else "batch exceeds timeout")
        elif await_cond:
            self.sim_ms += dur
            sat, err = self._eval_grammar1(await_cond)
            assumed = False
            if not sat and err is None and not modeled:
                # Unmodeled command (e.g. INTERACT_NPC gather): assume it
                # succeeds at its own declared postcondition rather than
                # false-positive. Modeled commands stay strict (real detection).
                assumed = self._apply_await_postcondition(await_cond)
                sat, err = self._eval_grammar1(await_cond)
            if err is not None:
                status = "FAIL"
                details.append(
                    f"invalid await_condition '{await_cond}': {err} "
                    f"(wrong grammar? await uses step-level Grammar 1 -- "
                    f"loop atoms like 'inventory_full' belong in stop/exit_conditions)")
            elif not sat:
                status = "FAIL"
                details.append(
                    f"await_condition '{await_cond}' NOT satisfied after the "
                    f"modeled effect -- real engine would poll to timeout_ms "
                    f"({_fmt_ms(timeout_ms)}) then fail (guaranteed-timeout step)")
            elif assumed:
                details.append(f"await '{await_cond}' satisfied (assumed postcondition)")
            else:
                details.append(f"await '{await_cond}' satisfied")
        else:
            self.sim_ms += dur

        return self._finish_step(step_id, label, command, dur, status, details, loop_pass, action)

    def _finish_step(self, step_id, label, command, dur, status, details, loop_pass, action):
        entry = {
            "pass": loop_pass,
            "step_id": step_id,
            "action": label,
            "command": command,
            "duration_ms": dur,
            "cumulative_ms": self.sim_ms,
            "status": status,
            "detail": "; ".join(details),
        }
        self.trace.append(entry)
        if status == "FAIL":
            self.failures.append(
                f"pass {loop_pass} step {step_id} ({label}): {'; '.join(details)}")
        return status != "FAIL", action

    # -- loop-condition vetting (Grammar 2) --------------------------------

    def _vet_loop_conditions(self):
        loop = self.doc.get("loop", {}) or {}
        blocks = []
        if "stop_conditions" in loop:
            blocks.append(("stop_conditions", loop.get("stop_conditions") or []))
        for name in ("inner", "outer"):
            b = loop.get(name, {}) or {}
            if "exit_conditions" in b:
                blocks.append((f"{name}.exit_conditions", b.get("exit_conditions") or []))
        for where, conds in blocks:
            for c in conds:
                c = self._interp(c)
                if not _is_known_grammar2(c):
                    self.warnings.append(
                        f"loop {where}: '{c}' is NOT a recognized Grammar-2 atom "
                        f"-- it will SILENTLY never trigger (ROUTINE_SCHEMA.md (c); "
                        f"step-level Grammar-1 atoms like plane:/location:/idle "
                        f"do not work in loop conditions)")

    async def _loop_should_stop(self, conditions):
        """ANY Grammar-2 condition true -> stop. Reuses check_stop_condition."""
        for c in conditions or []:
            c = self._interp(c)
            if not _is_known_grammar2(c):
                continue  # already warned; treated as never-true
            val, err = await self._eval_grammar2(c)
            if err is not None:
                self.warnings.append(f"loop condition '{c}': {err}")
                continue
            if val:
                return c
        return None

    # -- main drive ---------------------------------------------------------

    async def run(self):
        result = {
            "routine_name": self.doc.get("name", "Unknown"),
            "success": True,
            "aborted": False,
            "loops_completed": 0,
            "stop_reason": None,
        }
        steps = self.doc.get("steps")
        if not steps:
            result["success"] = False
            result["error"] = "Routine has no steps"
            return self._summarize(result)

        # Point the engine's state reader at our model for Grammar-2 checks.
        self._saved_get_state = routine.get_game_state

        async def _model_state(account_id=None):
            return self.model.as_state()

        routine.get_game_state = _model_state
        try:
            await self._drive(steps, result)
        finally:
            routine.get_game_state = self._saved_get_state
        return self._summarize(result)

    async def _drive(self, steps, result):
        self._vet_loop_conditions()

        step_id_to_idx = {}
        for idx, step in enumerate(steps):
            step_id_to_idx[str(step.get("id", idx + 1))] = idx

        loop = self.doc.get("loop", {}) or {}
        inner = loop.get("inner", {}) or {}
        outer = loop.get("outer", {}) or {}
        flat_enabled = loop.get("enabled", False)
        flat_repeat_from = loop.get("repeat_from_step", 1)
        has_inner_outer = inner.get("enabled", False) or outer.get("enabled", False)
        inner_start_idx = (routine._resolve_step_idx(inner.get("start_step", 1), step_id_to_idx, None)
                           if inner.get("enabled") else None)
        inner_end_idx = (routine._resolve_step_idx(inner.get("end_step", ""), step_id_to_idx, None)
                         if inner.get("enabled") else None)
        # Mirrors execute_routine's inner-loop failure bookkeeping (routine.py):
        # a failing step *inside* the inner loop bounds restarts the inner loop
        # rather than marching on; after this many consecutive restarts in a row
        # it exits via on_exit instead. Keep both constants in lockstep with
        # routine.py's inner_consecutive_failures / max_inner_consecutive_failures.
        inner_consecutive_failures = 0
        max_inner_consecutive_failures = 3

        outer_count = 0
        loop_pass = 1
        idx = routine._resolve_step_idx(1, step_id_to_idx, 0)

        while outer_count < self.max_loops:
            while idx < len(steps):
                if self.step_execs >= self.max_step_execs:
                    self.warnings.append("safety cap: max step executions reached")
                    result["stop_reason"] = "max_step_execs"
                    return
                step = steps[idx]
                step_id = step.get("id", idx + 1)
                ok, action = await self._exec_step(step, loop_pass)

                if not ok:
                    on_failure = routine._parse_on_failure(step.get("on_failure"))
                    if on_failure["mode"] == "abort":
                        result["success"] = False
                        result["aborted"] = True
                        result["aborted_at_step"] = step_id
                        result["abort_reason"] = f"step {step_id} failed (on_failure: abort)"
                        return
                    if on_failure["mode"] == "retry":
                        # Deterministic model: a retry reproduces the same
                        # failure, so the engine would exhaust retries -> abort.
                        result["success"] = False
                        result["aborted"] = True
                        result["aborted_at_step"] = step_id
                        result["abort_reason"] = (
                            f"step {step_id} failed; on_failure retry:{on_failure['retries']} "
                            f"would re-run identically against the fixture and then abort")
                        self.warnings.append(
                            f"step {step_id}: retry:{on_failure['retries']} is deterministic "
                            f"in dry-run (same inputs -> same failure)")
                        return
                    # continue (default): mark the run failed but keep going --
                    # this is the "silently marches on" class made visible.
                    result["success"] = False

                    # A failure on a step *inside* the inner loop's [start_step,
                    # end_step] bounds is NOT a march-on in the live engine: it
                    # increments inner_consecutive_failures and RESTARTS the inner
                    # loop from start_step, and after max_inner_consecutive_failures
                    # (3) in a row it resets the counter and exits via on_exit
                    # (falling through to the next step if on_exit is absent/invalid
                    # -- exactly like routine.py's execute_routine).
                    in_inner_bounds = (
                        has_inner_outer and inner.get("enabled", False)
                        and inner_start_idx is not None and inner_end_idx is not None
                        and inner_start_idx <= idx <= inner_end_idx)
                    if in_inner_bounds:
                        inner_consecutive_failures += 1
                        self.trace[-1]["detail"] += (
                            f" | on_failure=continue (inner loop): LIVE runner RESTARTS the "
                            f"inner loop from step {inner.get('start_step', 1)} "
                            f"({inner_consecutive_failures}/{max_inner_consecutive_failures} "
                            f"consecutive failures)")
                        if inner_consecutive_failures >= max_inner_consecutive_failures:
                            self.trace[-1]["detail"] += (
                                " -- threshold reached, LIVE runner exits the inner loop via on_exit")
                            inner_consecutive_failures = 0
                            on_exit = inner.get("on_exit", "")
                            if on_exit.startswith("goto_step:"):
                                j = routine._resolve_step_idx(on_exit.split(":", 1)[1], step_id_to_idx, None)
                                if j is not None:
                                    idx = j
                                    continue
                            # No/invalid on_exit target: fall through to the next
                            # step, same as live (see the end-step check below).
                        else:
                            idx = inner_start_idx
                            continue
                    else:
                        self.trace[-1]["detail"] += (
                            " | on_failure=continue: LIVE runner would MARCH ON past this failure")

                # Inner loop: reached inner.end_step?
                if has_inner_outer and inner.get("enabled", False):
                    if str(step_id) == str(inner.get("end_step", "")):
                        # Live resets the consecutive-failure counter on reaching
                        # end_step regardless of whether the loop exits or repeats.
                        inner_consecutive_failures = 0
                        exit_c = await self._loop_should_stop(inner.get("exit_conditions", []))
                        if exit_c:
                            on_exit = inner.get("on_exit", "")
                            if on_exit.startswith("goto_step:"):
                                j = routine._resolve_step_idx(on_exit.split(":", 1)[1], step_id_to_idx, None)
                                if j is not None:
                                    idx = j
                                    continue
                        else:
                            if inner_start_idx is not None:
                                idx = inner_start_idx
                                continue
                idx += 1

            # End of a full pass.
            if has_inner_outer and outer.get("enabled", False):
                outer_count += 1
                result["loops_completed"] = outer_count
                exit_c = await self._loop_should_stop(outer.get("exit_conditions", []))
                if exit_c:
                    result["stop_reason"] = f"outer exit_condition: {exit_c}"
                    break
                idx = routine._resolve_step_idx(outer.get("start_step", 1), step_id_to_idx, 0)
                loop_pass += 1
            elif flat_enabled:
                outer_count += 1
                result["loops_completed"] = outer_count
                stop = await self._loop_should_stop(loop.get("stop_conditions", []))
                if stop:
                    result["stop_reason"] = f"stop_condition: {stop}"
                    break
                idx = routine._resolve_step_idx(flat_repeat_from, step_id_to_idx, 0)
                loop_pass += 1
            else:
                result["loops_completed"] = 1
                break

        if result["stop_reason"] is None and outer_count >= self.max_loops:
            result["stop_reason"] = f"reached max_loops ({self.max_loops})"

    def _summarize(self, result):
        result.update({
            "steps_simulated": len(self.trace),
            "simulated_wall_clock_ms": self.sim_ms,
            "simulated_wall_clock": _fmt_ms(self.sim_ms),
            "failures": self.failures,
            "warnings": self.warnings,
            "trace": self.trace,
        })
        if self.failures and result["success"]:
            result["success"] = False
        return result


def _fmt_ms(ms):
    ms = int(ms)
    s = ms / 1000.0
    if s < 60:
        return f"{s:.1f}s"
    m = s / 60.0
    if m < 60:
        return f"{m:.1f}m"
    return f"{m / 60.0:.2f}h"


# ---------------------------------------------------------------------------
# Public entrypoints
# ---------------------------------------------------------------------------
async def dry_run_routine(routine_path, max_loops=1, model=None):
    """Load a routine YAML and simulate it offline. Returns a result dict."""
    import yaml
    try:
        with open(routine_path) as fh:
            doc = yaml.safe_load(fh)
    except FileNotFoundError:
        return {"success": False, "error": f"Routine file not found: {routine_path}",
                "failures": [], "warnings": [], "trace": []}
    except yaml.YAMLError as e:
        return {"success": False, "error": f"Invalid YAML: {e}",
                "failures": [], "warnings": [], "trace": []}
    if not isinstance(doc, dict) or "steps" not in doc:
        return {"success": False, "error": "Routine has no steps",
                "routine_name": (doc or {}).get("name") if isinstance(doc, dict) else None,
                "failures": [], "warnings": [], "trace": []}
    interp = DryRunInterpreter(doc, model=model, max_loops=max_loops)
    result = await interp.run()
    result["routine_path"] = routine_path
    return result


_FOOTER = (
    "DRY-RUN LIMITS: simulates step sequencing/awaits/loops against a fixture "
    "only. Does NOT verify coordinate reachability/collision (use the Java "
    "route-lint), NPC/widget availability, or timing realism (durations are "
    "coarse estimates). A PASS is necessary, not sufficient, before a live run."
)


def format_report(result):
    """Human-readable trace + summary for a single dry-run result."""
    lines = []
    name = result.get("routine_name", "Unknown")
    lines.append("=" * 70)
    lines.append(f"DRY-RUN: {name}")
    if result.get("routine_path"):
        lines.append(f"  {result['routine_path']}")
    lines.append("=" * 70)

    if result.get("error"):
        lines.append(f"ERROR: {result['error']}")
        lines.append("=" * 70)
        return "\n".join(lines)

    for e in result.get("trace", []):
        marker = {"OK": "  ", "FAIL": "!!", "WARN": " ~"}.get(e["status"], "  ")
        lines.append(
            f"{marker} [p{e['pass']} step {e['step_id']}] {e['action']:<20} "
            f"{_fmt_ms(e['duration_ms']):>7} (t+{_fmt_ms(e['cumulative_ms'])})")
        if e["detail"]:
            lines.append(f"       {e['detail']}")

    lines.append("-" * 70)
    status = "PASS" if result.get("success") else "FAIL"
    lines.append(f"RESULT: {status}")
    lines.append(f"  steps simulated:      {result.get('steps_simulated', 0)}")
    lines.append(f"  simulated wall-clock: {result.get('simulated_wall_clock', '0s')}")
    lines.append(f"  loops completed:      {result.get('loops_completed', 0)}")
    if result.get("stop_reason"):
        lines.append(f"  stop reason:          {result['stop_reason']}")
    if result.get("aborted"):
        lines.append(f"  ABORTED at step {result.get('aborted_at_step')}: {result.get('abort_reason')}")

    failures = result.get("failures", [])
    if failures:
        lines.append(f"\n  FAILURES ({len(failures)}):")
        for f in failures:
            lines.append(f"    - {f}")
    warnings = result.get("warnings", [])
    if warnings:
        lines.append(f"\n  WARNINGS ({len(warnings)}):")
        for w in warnings:
            lines.append(f"    - {w}")

    lines.append("-" * 70)
    lines.append(_FOOTER)
    lines.append("=" * 70)
    return "\n".join(lines)
