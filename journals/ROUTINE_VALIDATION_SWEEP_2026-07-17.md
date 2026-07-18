# Routine Library QA Sweep — 2026-07-17

*Deep-validator pass over every YAML under `routines/` (all 7 categories, 42 files),
run in-process against `manny_tools.validate_routine_deep` while a live Tutorial
Island test owned the game client. No client start/stop, no writes to
`/tmp/manny_new_command.txt`, no edits under `routines/tutorial_island/`.*

## How it was run

`validate_routine_deep` lives in `manny_tools.py:2492` (the MCP tool
`mcptools/tools/manny_navigation.py:handle_validate_routine_deep` is a thin
registry wrapper around the same function, imported there as
`_validate_routine_deep`). It's a pure function — reads the routine YAML with
`yaml.safe_load`, calls `list_available_commands(plugin_dir)` (parses
`PlayerHelpers.java` text for `register("NAME", ...)` calls plus the legacy
`switch(cmd)` block), and returns errors/warnings/suggestions. No command-file
I/O, no client interaction — safe to run standalone. Bootstrapping the full
MCP registry (`mcptools/bootstrap.py:init_registry()`) would have pulled in
`MultiRuneLiteManager` for no benefit, so the sweep imported
`validate_routine_deep` directly from `manny_tools.py` via
`./venv/bin/python`, driven by a one-off driver script that walked
`routines/**/*.yaml` and called the function per file.

Command index sanity check: `list_available_commands('/home/wil/Desktop/manny')`
returns exactly **131 commands** — confirms the plugin at commit `c01219c`
("Wave 6-J1... Remove LOAD_SCENARIO + LOAD_CMDLOG commands (133 -> 131)") is
what's being validated against. Grepped all 42 routine files for
`LOAD_SCENARIO`/`LOAD_CMDLOG` — zero hits, so no routine still references
either removed command.

## Summary counts

| | Count |
|---|---|
| Total YAML files scanned | 42 |
| Clean (no validator errors or warnings) | 33 |
| Warnings only | 0 |
| Errors reported by validator | 9 |
| ...of which real defects (fixed) | 1 |
| ...of which validator false positives (demonstrated, see §4) | 8 |
| Files edited | 1 (`routines/quests/restless_ghost.yaml`) |

No routine anywhere triggered a warning-only result — every non-clean file had
at least one `errors[]` entry. `repeat: N` appears in 6 files (`imp_catcher`,
`cooks_assistant`, `restless_ghost`, `sheep_shearer`, `death_escape`,
`common_actions`) and, per the hardening journal, the validator doesn't
inspect `repeat` at all — it neither passes nor fails on it, consistent with
"now supported" needing no validator change.

## Per-file findings

Status legend: **CLEAN** = zero errors/warnings. **FIXED** = had a real error,
mechanically corrected below, re-validated clean of that error (residual flag
is a demonstrated validator false positive). **FP** = validator error(s) but,
on inspection, a false positive (validator gap, not a routine bug — see §4).
**REAL** = genuine, unresolved issue, left as-is because it's inside
`tutorial_island/` (owned by another agent) or needs behavioral judgment.

| File | Category | Steps | Status | Notes |
|---|---|---|---|---|
| combat/chicken_killer_loop.yaml | combat | 1 | CLEAN | |
| combat/chicken_killer_training.yaml | combat | 2 | CLEAN | |
| combat/cow_killer_no_bones.yaml | combat | — | FP | No `steps:` — it's a loot/eating config sidecar (metadata-only), not an executable routine. See §4a. |
| combat/cow_killer_training.yaml | combat | 8 | CLEAN | |
| combat/hill_giants.yaml | combat | — | FP | No `steps:` — draft/example doc for the proposed "configurable loot" feature (`tickets/configurable_loot.md`), superseded by the split `hill_giants_loot/restock/resupply/travel.yaml`. See §4a, §5.1. |
| combat/hill_giants_loot.yaml | combat | 6 | CLEAN | |
| combat/hill_giants_restock.yaml | combat | 15 | CLEAN | |
| combat/hill_giants_resupply.yaml | combat | 9 | CLEAN | |
| combat/hill_giants_travel.yaml | combat | 4 | CLEAN | |
| common_actions.yaml | (library) | — | FP | No `steps:` — documented in `ROUTINE_CATALOG.md:19` as `Library / Reference`, a bag of reusable snippets nested under named keys (`stairs.lumbridge_castle.ground_to_first.steps`, etc.), not a flat top-level routine. See §4a. |
| generated/test_scorpion_attack_1769492259.yaml | generated | 1 | CLEAN | |
| quests/cooks_assistant.yaml | quests | 25 | CLEAN | |
| quests/imp_catcher.yaml | quests | 10 | CLEAN | |
| quests/restless_ghost.yaml | quests | 25 | **FIXED** | Step 9 was `action: MCP_TOOL` / `tool: equip_item` — not a real command; only fake-sent the literal string `MCP_TOOL Ghostspeak amulet` to the game. Fixed to the engine's actual `mcp_tool:` step shape. Re-validation now reports only a **false-positive** "missing action" (§4b). |
| quests/romeo_and_juliet.yaml | quests | 38 | CLEAN | |
| quests/sheep_shearer.yaml | quests | 15 | CLEAN | Contains a `skip_if:` guard (line 86) the engine doesn't implement yet — judgment item, §5.1, not a validator error. |
| skilling/cooking_lumbridge.yaml | skilling | 16 | CLEAN | |
| skilling/fishing_draynor.yaml | skilling | 6 | CLEAN | |
| skilling/fishing_karamja_harpoon.yaml | skilling | 15 | CLEAN | |
| skilling/fishing_karamja_lobster.yaml | skilling | 14 | CLEAN | |
| skilling/flour_milling.yaml | skilling | 7 | CLEAN | |
| skilling/mine_iron_ore.yaml | skilling | 18 | CLEAN | |
| skilling/mining_falador_iron.yaml | skilling | 6 | CLEAN | |
| skilling/superheat_mining_guild.yaml | skilling | 11 | CLEAN | |
| skilling/superheat_steel_bars.yaml | skilling | 21 | CLEAN | |
| skilling/woodcutting_lumbridge.yaml | skilling | 10 | CLEAN | |
| test/basic_test_routine.yaml | test | 5 | CLEAN | |
| tutorial_island/01_character_creation.yaml | tutorial_island | 5 | CLEAN | not edited (owned by other agent) |
| tutorial_island/01_experience_selection.yaml | tutorial_island | 1 | CLEAN | not edited |
| tutorial_island/02_gielinor_guide.yaml | tutorial_island | 12 | CLEAN | not edited |
| tutorial_island/03_survival_expert.yaml | tutorial_island | 11 | CLEAN | not edited |
| tutorial_island/04_woodcutting_firemaking.yaml | tutorial_island | 13 | CLEAN | not edited |
| tutorial_island/05_cooking.yaml | tutorial_island | 12 | CLEAN | not edited |
| tutorial_island/05_cooking_to_quest_guide.yaml | tutorial_island | 19 | REAL | 5 locations (`cooking_exit_door`, `cooking_door_approach`, `quest_guide_door`, `quest_guide_npc`, `ladder_down`) are missing `plane`. Looks like a genuine data gap, not a validator bug — **not fixed, out of scope** (tutorial_island). |
| tutorial_island/06_quest_guide.yaml | tutorial_island | 16 | CLEAN | not edited |
| tutorial_island/07_mining_smithing.yaml | tutorial_island | 25 | CLEAN | not edited |
| tutorial_island/08_combat.yaml | tutorial_island | 18 | FP | 6 steps (3,4,7,8,14,15) use `mcp_tool: equip_item`/`find_and_click_widget`, marked `status: VALIDATED` in the file itself. Flagged "missing action" — same validator gap as restless_ghost, §4b. Not edited. |
| tutorial_island/09_banking.yaml | tutorial_island | 10 | CLEAN | not edited |
| tutorial_island/10_prayer_magic.yaml | tutorial_island | 29 | FP | 9 steps (5,13,19,20,22,25,26,27,28) use `mcp_tool: click_widget`/`click_text`, all `status: VALIDATED`. Same validator gap, §4b. Not edited. |
| tutorial_island/widget_reference.yaml | tutorial_island | — | FP | No `steps:` — a widget-ID reference doc (per `journals/tutorial_island_navigation_lessons_2026-01-25.md:106`), not a routine. §4a. Not edited. |
| utility/death_escape.yaml | utility | 12 | CLEAN | |
| utility/gravestone_retrieval.yaml | utility | — | FP | Uses `manual_steps:` (a documented human/LLM runbook format, not `steps:`) — intentionally not machine-executed. §4a. |

## Fixes applied

**`routines/quests/restless_ghost.yaml:154-160`** — before:

```yaml
  - id: 9
    phase: "talk_ghost"
    action: MCP_TOOL
    tool: "equip_item"
    args: "Ghostspeak amulet"
    description: "Equip the Ghostspeak amulet"
    notes: "EQUIP_ITEM command doesn't exist - use MCP equip_item() tool"
```

after:

```yaml
  - id: 9
    phase: "talk_ghost"
    mcp_tool: equip_item
    args:
      item_name: "Ghostspeak amulet"
    description: "Equip the Ghostspeak amulet"
    notes: "action: MCP_TOOL is not a real command (executor only dispatches a top-level mcp_tool: key, routine.py:1371-1374). Uses the same mcp_tool: equip_item / args.item_name shape already VALIDATED in tutorial_island/08_combat.yaml and 10_prayer_magic.yaml."
```

Verification, not guesswork:

- `EQUIP_ITEM` is **not** a game command — confirmed against the full 131-command
  index (`list_available_commands` filtered on `EQUIP` returns only
  `EQUIPMENT_LOG`, `QUERY_EQUIPMENT`, `BANK_DEPOSIT_EQUIPMENT`,
  `EQUIP_BEST_MELEE` — no generic per-item equip command exists). So this
  isn't "replace with the equivalent game command" — the original author's own
  `notes:` already said as much ("EQUIP_ITEM command doesn't exist - use MCP
  equip_item() tool"); the bug was purely in *how* the MCP-tool step was
  spelled.
- The executor (`mcptools/tools/routine.py:1371-1374`) dispatches on a
  top-level `step.get('mcp_tool')` key, not `action`/`tool`. `_execute_mcp_tool_step`
  (routine.py:1446-1477) then calls `handle_equip_item(mcp_args)`
  (`mcptools/tools/commands.py:465`), which reads `arguments.get("item_name", "")`
  — so `args` must be a dict with an `item_name` key, not a bare string (a bare
  string would silently become `{}` at routine.py:1450-1451,
  `if isinstance(mcp_args, str): mcp_args = {}`, dropping the item name
  entirely).
- The exact `mcp_tool: equip_item` / `args: {item_name: ...}` shape is already
  live and marked `status: VALIDATED` in `routines/tutorial_island/08_combat.yaml`
  (steps 4, 7, 8, 14, 15) and `10_prayer_magic.yaml` — this is a proven,
  working pattern, not a new invention.
- Re-ran `validate_routine_deep` on the fixed file: the `Unknown command
  'MCP_TOOL'` error is gone. The only remaining error is
  `Step 9: Missing required field 'action'`, which is the validator's known gap
  (§4b) — confirmed false positive, not a regression.

No other file needed a mechanical fix. Everything else flagged is either a
validator false positive (§4) or a judgment call (§5).

## Judgment items for the orchestrator (not fixed — needs a decision)

1. **`routines/quests/sheep_shearer.yaml:86`** — `skip_if: "has_item:Shears"`.
   The engine (`mcptools/tools/routine.py`) does not implement `skip_if`/
   `only_if`/`on_fail` anywhere (grepped, zero matches) — these are proposed
   in `journals/ROUTINE_ENGINE_HARDENING_2026-07-17.md` §1c but not yet built.
   The key is currently inert: the step still runs unconditionally (it has a
   valid `action: PICK_UP_ITEM`), so this isn't broken, just quietly not doing
   what its author intended. Decide: implement the guard feature, or strip
   the dead key until it's real.
2. **`routines/combat/hill_giants.yaml` and `routines/combat/cow_killer_no_bones.yaml`**
   — both look like superseded/example config docs (no `steps:`, carry stale
   `threshold_percent` keys the engine doesn't read per the hardening
   journal's open question #1). `hill_giants.yaml` is also cited in
   `tickets/configurable_loot.md` as the worked example for a not-yet-built
   "configurable loot" feature. Real, current execution for Hill Giants goes
   through the split `hill_giants_loot/restock/resupply/travel.yaml` (all
   clean). Decide: archive/delete these two, or keep as living design
   references — a content decision, not mechanical.
3. **`routines/tutorial_island/05_cooking_to_quest_guide.yaml`** — 5 location
   entries missing `plane` (table above). This looks like a real, if minor,
   data gap rather than a validator artifact (every other location block in
   the library sets x/y/plane). Left untouched — file is inside
   `tutorial_island/`, owned by the other agent running the live test.
4. **Validator scope gap in general** (root cause of most of §L4a): there's no
   marker distinguishing "this YAML is a runnable routine" from "this YAML is
   a reference/library/design doc that happens to live under `routines/`."
   Cheapest fix: an explicit `type: reference` (or `executable: false`) key
   that `validate_routine_deep` treats as "skip the steps-required check" —
   or move non-executable files out of `routines/` into a `routines/docs/`
   or `references/` sibling. Either is a policy call, not something to guess
   at unilaterally.

## Validator false positives (validator bugs, demonstrated)

**(a) `Missing required field: 'steps'` fires on any YAML under `routines/`
regardless of whether the file was ever meant to be an executable routine.**
`manny_tools.py:2544-2545` unconditionally requires a top-level `steps` key.
Five files trip this despite being intentionally non-executable:

- `routines/common_actions.yaml` — documented as `Library`/`Reference` in
  `ROUTINE_CATALOG.md:19`.
- `routines/tutorial_island/widget_reference.yaml` — a widget-ID reference
  doc (`journals/tutorial_island_navigation_lessons_2026-01-25.md:106`).
- `routines/utility/gravestone_retrieval.yaml` — uses a deliberate
  `manual_steps:` schema for human/LLM-followed recovery instructions, not
  `steps:`.
- `routines/combat/hill_giants.yaml`, `routines/combat/cow_killer_no_bones.yaml`
  — design/config docs (see judgment item 2 above).

Demonstration that this is a scope gap, not a routine defect: none of these
five files are ever passed to `run_routine.py` in any script, doc, or test
harness in the repo (grepped `discord_bot/`, `tickets/`, `journals/`, `*.md`
for each filename — only doc/reference mentions, zero execution call sites).
The validator has no way to know a file isn't meant to run, so it treats
"reference doc that lives in `routines/`" identically to "broken routine."

**(b) `Missing required field 'action'` fires on any step using the fully
supported `mcp_tool:` key instead of `action:`.** `manny_tools.py:2567-2568`
requires `action` in every step unconditionally, but the executor
(`mcptools/tools/routine.py:1371-1374`) explicitly supports an alternate step
shape keyed on `mcp_tool` (dispatched to `_execute_mcp_tool_step`, routine.py:1446).
This is not a hypothetical — it's the *documented, `status: VALIDATED`*
pattern already used live in `tutorial_island/08_combat.yaml` (6 steps) and
`tutorial_island/10_prayer_magic.yaml` (9 steps), and is now also the correct
shape in the just-fixed `restless_ghost.yaml` step 9. Directly demonstrated
by the before/after re-validation in the Fixes section above: fixing the real
`MCP_TOOL` bug in `restless_ghost.yaml` didn't clear the file's error count —
it just swapped a real error for this false one, proving the false-positive
class exists independent of the actual routine defect. This matches audit
finding §0.4 in `journals/ROUTINE_ENGINE_HARDENING_2026-07-17.md`
("`validate_routine_deep` ... does **not** parse ... `mcp_tool` ... steps").

Recommended validator fix (not applied here — out of scope, this is a
validation-only task): in the step-required-fields check, accept
`'action' in step or 'mcp_tool' in step`; and in the top-level structural
check, skip the `steps`-required error when the routine has a `type:
reference` marker (see judgment item 4) or when `manual_steps` is present
instead.

## Files edited

- `routines/quests/restless_ghost.yaml` (step 9, line 154 area) — the only edit made this sweep.

No other file was touched. Nothing under `routines/tutorial_island/` was
edited. `/tmp/manny_new_command.txt` was never referenced and no client
was started or stopped.
