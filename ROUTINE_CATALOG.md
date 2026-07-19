# Routine Catalog

**For the routine YAML schema itself (what keys are live, condition grammars,
loop semantics, blocking-command timeouts, dead keys) see
[`ROUTINE_SCHEMA.md`](ROUTINE_SCHEMA.md) — read that before authoring or
editing any routine.** This file is an inventory: what exists on disk today,
validated status, and what's still just an idea.

Run every existing routine with
`./run_routine.py <path> [--loops N] [--start-step N] [--account ID]`.
Per-file maturity analysis lives in
`journals/ROUTINE_CORPUS_STUDY_2026-07-18.md`.
(`LOAD_SCENARIO`/`LOAD_CMDLOG` were removed in W6-J1 and no longer exist —
routines run exclusively through the YAML executor.)

---

## Existing (validated) — real files under `routines/`

Every entry below has a backing `.yaml` file. "Status" reflects actual
validation/run history, not aspiration.

### Quests (`routines/quests/`)

| Routine | Purpose | Status |
|---|---|---|
| `cooks_assistant.yaml` | Cook's Assistant | ✅ Complete — dialogue-drain fix: monologues use fixed-count repeat + `await:dialogue`, not `repeat_until:no_dialogue` (86ac7b4) |
| `sheep_shearer.yaml` | Sheep Shearer (shear 20 wool, spin, deliver) | ✅ Complete — dialogue-drain fix + `inventory_count` off-by-one corrected (shears occupy a slot → `>=21`) (86ac7b4) |
| `restless_ghost.yaml` | The Restless Ghost | ✅ Complete — dialogue-drain fix (86ac7b4) |
| `imp_catcher.yaml` | Imp Catcher (4 beads → Wizard Mizgog) | ✅ Complete — dialogue-drain fix (86ac7b4) |
| `romeo_and_juliet.yaml` | Romeo & Juliet | ✅ Complete — dialogue-drain fix (86ac7b4) |

### Skilling (`routines/skilling/`)

| Routine | Purpose | Status |
|---|---|---|
| `woodcutting_lumbridge.yaml` | Chop trees near Lumbridge, flat loop until wc lvl 30 (H-2) | ✅ Complete |
| `fishing_draynor.yaml` | Fish shrimp at Draynor, bank Lumbridge | ✅ Validated |
| `fishing_karamja_lobster.yaml` | Lobster cage Musa Point (50-loop) | ✅ Complete — flat `loop:` (note: `start_step`/`max_iterations` keys in this file are dead, see `ROUTINE_SCHEMA.md` §f); deposit-box open delay bumped 2500ms→5000ms, no await atom exists for that interface (a113495) |
| `fishing_karamja_harpoon.yaml` | Harpoon tuna/swordfish Musa Point | ✅ Complete — same dead-key caveat as above; same deposit-box delay fix (a113495) |
| `cooking_lumbridge.yaml` | Cook raw fish at Lumbridge range (loop) | ✅ Complete — removed dead, never-interpolated `cooked_food` key (a113495) |
| `flour_milling.yaml` | Mill grain→flour at Lumbridge windmill | ✅ Complete — replaced always-instant `await:idle` on a stationary Operate with a calibrated `delay_after_ms` (a113495) |
| `mining_falador_iron.yaml` | POWER_MINE iron, Falador Dwarven Mine (loop) | ✅ Complete — replaced always-true `plane:0` staircase await with an await verifying the actual underground landing (86ac7b4) |
| `mine_iron_ore.yaml` | Mine iron in Mining Guild, bank (mining 60) | ✅ Complete |
| `superheat_mining_guild.yaml` | Mine iron + Superheat → iron bars (nested inner/outer loop) | ✅ Complete — reference example for `ROUTINE_SCHEMA.md` §i.3; iron rocks retargeted to the reachable (3029,9739) cluster, `no_item:Iron ore` await added on the superheat cast, landing await added on the guild ladder (86ac7b4) |
| `superheat_steel_bars.yaml` | Mine coal+iron + Superheat → steel bars (loop) | ✅ Complete |

### Combat (`routines/combat/`)

| Routine | Purpose | Status |
|---|---|---|
| `chicken_killer_training.yaml` | GOTO coop → `KILL_LOOP Chicken 200` | ✅ Complete — `KILL_LOOP` timeout raised 1h→2h so the runner doesn't abandon a still-grinding 200-kill batch (a113495) |
| `chicken_killer_loop.yaml` | `KILL_LOOP Chicken`, 50× auto-loop | ✅ Complete — reference example for `ROUTINE_SCHEMA.md` §i.2; `loop.max_iterations`/`delay_between_loops_ms` keys in this file are dead (§f); comment falsely claiming identical coords to the sibling routine corrected (a113495) |
| `cow_killer_training.yaml` | Bank→`EQUIP_BEST_MELEE`→cow pen→kill | ✅ Complete — removed the uncapped/unmanaged `KILL_COW_GET_HIDES` step, made the bounded `KILL_LOOP` terminal, added flat-loop coverage (86ac7b4) |
| `hill_giants_travel.yaml` | Travel GE→Hill Giants (brass-key shortcut) | ✅ Complete |
| `hill_giants_resupply.yaml` | Bank at GE, restock food/runes | ✅ Complete — added `BANK_DEPOSIT_ALL` before restock (a part-full inventory could corrupt the loadout) + `has_item` awaits on key items (a113495) |
| `hill_giants_loot.yaml` | KILL_LOOP_CONFIG + loot-config JSON, flat loop to inventory_full (H-6) | ✅ Complete |
| `hill_giants_restock.yaml` | Bank loot mid-trip, restock, return | ✅ Complete — replaced always-true `plane:0` ladder await with a landing-verify await (86ac7b4); withdraw delays bumped 300ms→4000ms (25/21-qty withdraws can't round-trip in 300ms) + `has_item` awaits on Brass key/Swordfish (a113495) |

> **Removed 2026-07-18:** `cow_killer_no_bones.yaml` and `hill_giants.yaml`
> were `execute_combat_routine`-dialect config sidecars (`npc:`/`kills:`/
> `loot:`/`eating:`, no `steps:` key at all — confirmed non-executable by
> `run_routine.py`/`handle_execute_routine`, which requires `steps:`). Both
> were already fully superseded by the split, actually-runnable files above
> (`hill_giants_travel.yaml` + `hill_giants_loot.yaml` +
> `hill_giants_restock.yaml` + `hill_giants_resupply.yaml`, and
> `cow_killer_training.yaml`). Deleted rather than left as confusing
> no-`steps:` stubs; see `ROUTINE_SCHEMA.md` §f for why their `loot:`/
> `eating:`/`threshold_percent:` keys don't work in this schema anyway.

### Utility (`routines/utility/`)

| Routine | Purpose | Status |
|---|---|---|
| `death_escape.yaml` | Escape Death's Domain after first death | ✅ Complete — previously mislabeled non-executable by a validator bug that exempted any file with a `manual_steps:` block; the validator now only exempts `manual_steps`-only files (no coexisting `steps:`), and this file's 12 real steps are correctly recognized as executable (V-2, 8a8d3e9) |
| `gravestone_retrieval.yaml` | Retrieve items from gravestone (`manual_steps:`) | ⚠️ Stub (runbook, not machine-run) |

### Tutorial Island (`routines/tutorial_island/`)

14 files, stages 01→10 in order: `00_master.yaml` (chain master — running the
whole directory via `./run_routine.py routines/tutorial_island/` skips this
file and `00_*`-prefixed files automatically, `run_routine.py:53`),
`01_character_creation`, `01_experience_selection`, `02_gielinor_guide`,
`03_survival_expert`, `04_woodcutting_firemaking`, `05_cooking`,
`05_cooking_to_quest_guide`, `06_quest_guide`, `07_mining_smithing`,
`08_combat`, `09_banking`, `10_prayer_magic`, plus `widget_reference.yaml`
(reference doc, also skipped by the directory loader). ✅ Best-documented set
in the repo — `08_combat.yaml` is the reference example for `mcp_tool:`
usage in `ROUTINE_SCHEMA.md` §g. Note: `08_combat` and `10_prayer_magic`
pre-adopt an `await_condition: dialogue` atom (Grammar 1, narrow tutorial-only
predicate — see `ROUTINE_SCHEMA.md` §c). `05_cooking_to_quest_guide.yaml` was
a false-positive validator failure on the legal trailing `exact` token on
`GOTO` — `validate_routine_deep` now accepts `x y plane` and
`x y plane exact` (V-1, 8a8d3e9). `10_prayer_magic.yaml` had its STATUS
header corrected to state the actual Brother Brace blocker (steps unchanged,
H-13) and two trailer "WORKING PATTERNS" comments corrected — they had
recommended patterns (`CLICK_DIALOGUE` on empty options, `CAST_SPELL_NPC
Wind_Strike`) the file's own fixes forbid (comments only, M-15) (86ac7b4,
a113495).

### Library / test / generated

| Routine | Purpose | Status |
|---|---|---|
| `common_actions.yaml` | Reusable snippets (stairs/banking) | ✅ Reference (library — nested `steps:` under sub-keys, not directly runnable) |
| `test/basic_test_routine.yaml` | 5-step system smoke test | Scaffold |
| `generated/test_scorpion_attack_*.yaml` | Auto-generated 1-event sample | Scaffold |

---

## Planned (no file yet) — do NOT treat these as real routines

Everything in this section is a proposal. There is **no backing `.yaml`
file** in `routines/` for any row marked ⏳. The commands they'd use are
real and registered in the plugin, but nobody has written the routine YAML.
If you're an LLM and a user asks to "run the flax picker" or similar, check
this table first — if it's listed ⏳ here, say so and offer to write it
(using `ROUTINE_SCHEMA.md`) rather than assuming it exists.

### Questing (`quests/`)

| Routine | Commands needed | Status |
|---|---|---|
| `rune_mysteries.yaml` | GOTO, INTERACT_NPC, CLICK_DIALOGUE, BANK_WITHDRAW | ⏳ PLANNED — not yet implemented |

### Skilling (`skilling/`)

| Routine | Commands needed | Status |
|---|---|---|
| `mining_lumbridge.yaml` | MINE_ORE, GOTO, BANK_DEPOSIT_ALL | ⏳ PLANNED — not yet implemented |
| `firemaking_draynor.yaml` | LIGHT_FIRE, GOTO, DROP_ALL | ⏳ PLANNED — not yet implemented |
| `power_mining_varrock.yaml` | POWER_MINE, GOTO (no banking) | ⏳ PLANNED — `mining_falador_iron.yaml` already covers POWER_MINE iron, but not Varrock |
| `power_chopping.yaml` | POWER_CHOP, GOTO (no banking) | ⏳ PLANNED — not yet implemented |

### Combat (`combat/`)

| Routine | Commands needed | Status |
|---|---|---|
| `cow_killer_hides.yaml` | `KILL_COW_GET_HIDES` (command exists) | ⏳ PLANNED — no backing file (the old `cow_killer_no_bones.yaml` stub that referenced this was deleted 2026-07-18, see above) |
| `goblin_training.yaml` | KILL_LOOP, GOTO, BANK_DEPOSIT | ⏳ PLANNED — not yet implemented |
| `guard_training.yaml` | KILL_LOOP, GOTO, food management | ⏳ PLANNED — not yet implemented |

### Money Making (`routines/money_making/`)

The `routines/money_making/` directory now exists (created 2026-07-18, see
its `README.md` stub) but is **currently empty of routines**. The underlying
*commands* (`TELEGRAB_WINE_LOOP`, `COLLECT_LUMBRIDGE_TIN_COPPER`,
`KILL_COW_GET_HIDES`) are registered and directly usable via `send_command`/
a step's `action:`, but no money-maker `.yaml` has been written yet.

| Routine | Method | Est. GP/hour | Status |
|---|---|---|---|
| `flax_picker.yaml` | Pick flax, bank, repeat | ~50k (unverified estimate) | ⏳ PLANNED |
| `cowhide_collector.yaml` | Kill cows, collect hides | ~30k (unverified estimate) | ⏳ PLANNED |
| `wine_grabber.yaml` | `TELEGRAB_WINE_LOOP` (command exists) | ~150k (unverified estimate) | ⏳ PLANNED |
| `air_rune_crafter.yaml` | Mine essence, craft runes | ~40k (unverified estimate) | ⏳ PLANNED |

GP/hour figures above are carried over from an earlier planning pass and are
**not measured** — treat them as placeholders, not projections.

---

## Command reference

Full list (131 commands) lives in `COMMAND_REFERENCE.md`. Use
`list_commands()` to query the live plugin, or `list_commands(search="...")`
for the static source index (works without a running client). Categories:
banking, combat, skilling, interaction, inventory, movement, query. See
`list_commands(category="...")` for the current set — the category
breakdown previously duplicated here has drifted from the live command list
in the past; the tool itself is now the source of truth.

---

## Authoring a new routine

1. **Read `ROUTINE_SCHEMA.md` first** — the two condition vocabularies, loop
   exclusivity, blocking-command timeouts, and the dead-key list will save
   you from the most common silent-failure mistakes.
2. Discover commands: `list_commands(search="your_task")`,
   `list_commands(category="relevant_category")`.
3. Learn argument format for a specific command:
   `list_commands(command="BANK_WITHDRAW")`.
4. Write the routine YAML, following one of the three worked examples in
   `ROUTINE_SCHEMA.md` §i (linear quest / flat-loop grind / nested
   inner-outer banking loop) as a template.
5. Validate before running:
   ```python
   validate_routine_deep(routine_path="routines/<category>/your_routine.yaml",
                          plugin_dir="manny_src", check_commands=True, suggest_fixes=True)
   ```
   Remember: the validator checks YAML structure and command existence, but
   **not** condition-grammar placement, blocking-command timeouts, or the
   dead-key list — those are `ROUTINE_SCHEMA.md`'s job, not the validator's.
6. Dry-run bounded: `./run_routine.py routines/<category>/your_routine.yaml --loops 1 --account main`.
7. Move this file's entry for the routine from "Planned" to "Existing" once
   it's actually been run successfully — don't pre-promote on the strength
   of validation alone (validation catches syntax, not runtime behavior).
