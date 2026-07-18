# Grind Routine Readiness Audit — 2026-07-18

*Audit of all 10 `routines/skilling/*.yaml` and 9 `routines/combat/*.yaml` files for
unattended-run readiness. Vocabulary confirmed against `mcptools/tools/routine.py` and
`mcptools/tools/monitoring.py` (not guessed), command existence confirmed against
`COMMAND_REFERENCE.md` (131 commands), and several findings additionally verified against
the actual Java command handlers in `/home/wil/Desktop/manny/utility/commands/` (read-only —
no Java edited). Builds on `journals/ROUTINE_CORPUS_STUDY_2026-07-18.md` and
`journals/ROUTINE_VALIDATION_SWEEP_2026-07-17.md`; this pass found a new, more serious class
of defect those didn't cover (see §1 below) and fixed 7 files.*

## 0. Engine vocabulary confirmed from source

- **Step shapes**: `action:`/`args:` (game command), `mcp_tool:` (dispatches only
  `equip_item`, `click_widget`/`find_and_click_widget`, `click_text` — anything else fails
  with "Unknown mcp_tool"), `repeat: N` (implemented — repeats the step, short-circuits on a
  satisfied `await_condition`), `repeat_until: "<predicate>"` (implemented, capped
  iterations). **None of these three (`mcp_tool:`, `repeat:`, `repeat_until:`) are used
  anywhere in `routines/skilling/` or `routines/combat/`** — confirmed by grep, so the
  specific dead patterns a prior audit flagged elsewhere (`click_text`, `repeat: N`) don't
  apply to this corpus. `poll_interface_open` doesn't appear anywhere either.
- **`await_condition` / `repeat_until` predicates** (`monitoring._parse_condition`):
  `plane:N`, `has_item:X`, `no_item:X`, `inventory_count:<op>N`, `location:X,Y`, `idle`,
  `dialogue`, `no_dialogue`. Confirmed live in current source (this is a superset of what an
  earlier same-day journal reported — `dialogue`/`no_dialogue` are now implemented, not
  stubs).
- **Loop `stop_conditions` / `exit_conditions`** (`routine.check_stop_condition`, a
  *different* vocabulary than the above): `inventory_full`, `has_item:X`, `no_item:X`,
  `<skill>_level:N`, and `no_item_in_bank:X` — but `no_item_in_bank:X` now **raises
  `NotImplementedError`** (routine.py:1709-1719) instead of the old silent-`False` stub. This
  bit `cooking_lumbridge.yaml` — see §1.
- **Loop schema**: flat (`loop.enabled` + `loop.repeat_from_step` + `loop.stop_conditions`)
  vs. nested (`loop.inner.{enabled,start_step,end_step,exit_conditions,on_exit}` +
  `loop.outer.{...}`). These are mutually exclusive key sets read by *different* code paths —
  putting `start_step`/`end_step`/`exit_conditions` at the flat top level does nothing (see
  §1, `superheat_mining_guild.yaml`).
- **Dead-but-harmless keys observed**: `loop.max_iterations` (flat mode) and
  `loop.delay_between_loops_ms` are never read anywhere in `routine.py` — the actual loop
  bound is `run_routine.py`'s `--loops` CLI flag (default 10000). `delay_after:` (missing
  `_ms`) is silently ignored — only `delay_after_ms:` is read.

## 1. Headline finding: blocking commands with the 30s step default

`_execute_step_once` defaults `timeout_ms` to **30000** when a step doesn't set it
(routine.py:1519). For commands with an `await_condition`, that's fine — but for blocking
commands run **without** one, that 30s is the full budget for
`transport.send_command(..., timeout=timeout_ms/1000)` to wait for the plugin's response.

I verified directly against the Java handlers that `KILL_LOOP`, `CHOP_TREE`, and
`FISH_DRAYNOR_LOOP` are **fully synchronous** — `executeCommand` runs its own `while` loop
and only calls `responseWriter.writeSuccess(...)` once the whole task finishes (max_kills
reached, inventory full, or target level reached):

- `KillLoopCommand.java` — single `while` loop, `writeSuccess` only at interrupt or after
  all kills.
- `ChopTreeCommand.java` — `while (gameHelpers.getEmptySlots() > 0)`, responds once full.
- `FishDraynorLoopCommand.java` — `while (true)`, responds once the target fishing level is
  reached or interrupted (doc comment: "fish until level 45", **not** an inventory count).

With no `timeout_ms` override, a step like `KILL_LOOP Chicken 200` (real duration: many
minutes) would make `run_routine.py` give up waiting after 30s, log a spurious step timeout,
and — since none of these routines wrap the step in an inner loop — **exit the whole process
shortly after**, reporting the run as "finished" (`results['success']` stays `True`; a plain
step failure outside an inner-loop range doesn't flip it). Meanwhile the plugin keeps running
the real kill/chop/fish loop in the background for its actual duration, **completely
unsupervised** — no health checks, no crash/disconnect recovery, and any LLM driver watching
`run_routine.py`'s exit would wrongly conclude the session ended.

This directly undermined **both routines the handoff named as first live tests**
(`chicken_killer_training.yaml`, `woodcutting_lumbridge.yaml`) plus three more. The fix
pattern (explicit large `timeout_ms`) was already established elsewhere in this exact corpus
— `fishing_karamja_harpoon.yaml`/`fishing_karamja_lobster.yaml` already set 900000/600000ms
for their blocking `FISH` step — so the affected files had simply missed applying their own
sibling's fix. Fixed in 5 files (see §2).

## 2. Fixes applied

| File | Fix |
|---|---|
| `combat/hill_giants_resupply.yaml` | Renamed `delay_after:` → `delay_after_ms:` on 8 steps — the bare key is never read by the executor (dead key, no delay was ever actually applied). |
| `combat/hill_giants_travel.yaml` | Same `delay_after:` → `delay_after_ms:` fix, 2 steps. |
| `skilling/cooking_lumbridge.yaml` | Removed `no_item_in_bank:${raw_food}` from `loop.stop_conditions` — now raises `NotImplementedError` (routine.py:1709-1719) with no try/except around the call site, crashing the whole unattended run on the very first loop-completion check. `cooking_level:99` remains as the only stop condition (effectively never true in practice — loop now runs until `--loops` is exhausted, same net behavior minus the crash). |
| `skilling/superheat_mining_guild.yaml` | Three fixes to step 9 (`MINE_ORE`): (a) removed the redundant `await_condition:"has_item:Iron ore"` on a blocking command and raised `timeout_ms` 15000→45000 (too short for contested Mining Guild iron, risked failing the dispatch itself); (b) **added the missing `1` count arg** (`"iron"` → `"iron 1"`) — per `MineOreCommand.java`'s own doc comment, omitting `[count]` means "mine until inventory full," not "mine one ore," which silently broke the mine-then-superheat inner-loop design; (c) **restructured `loop:` from a broken flat block to the proper `inner:`/`outer:` schema** (the flat block set `start_step`/`end_step`/`exit_conditions` at the top level, which the executor's flat-loop path never reads — the routine was actually re-running the *entire* bank→travel→mine sequence after every single ore+superheat instead of looping steps 9-10 until full) and **added the missing exit-the-mine steps (12: GOTO ladder, 13: climb up)** that the outer loop needs before it can safely jump back to step 1's bank GOTO (mirrors `superheat_steel_bars.yaml`'s already-working steps 11-12, reusing this file's own pre-recorded ladder coordinates). |
| `combat/chicken_killer_loop.yaml` | Added the missing GOTO-to-coop as step 1 (the `lumbridge_chicken_coop` location was defined in the file but never referenced by any step) — reuses the identical coordinates already used by `chicken_killer_training.yaml` step 1. Renumbered `KILL_LOOP` to step 2 and gave it `timeout_ms: 3600000` (see §1). |
| `combat/chicken_killer_training.yaml` | Added `timeout_ms: 3600000` to the `KILL_LOOP Chicken 200` step (see §1). |
| `skilling/woodcutting_lumbridge.yaml` | Added `timeout_ms: 1800000` to the `CHOP_TREE` step (see §1). |
| `combat/cow_killer_training.yaml` | Added `timeout_ms: 3600000` to both `KILL_LOOP Cow 100` (step 7) and `KILL_COW_GET_HIDES 200` (step 8) (see §1). |
| `combat/hill_giants_travel.yaml` | Added `timeout_ms: 14400000` (4hr, 500-kill batch) to the `KILL_LOOP Hill_Giant 500` step (see §1). |
| `skilling/fishing_draynor.yaml` | Added `timeout_ms: 14400000` to the `FISH_DRAYNOR_LOOP 45` step, and corrected the step description/notes — `45` is a **target fishing level** (`FishDraynorLoopCommand.java`: "fish until level 45"), not "inventory nearly full (45/28 slots)" as the original description claimed. This command is a full self-contained grind loop (bank+travel+fish, entirely internal), comparable to `POWER_MINE`, not a single-trip action. |

9 files edited, all re-parsed clean with `yaml.safe_load`. No Java, no other routine
directories touched.

## 3. Flagged, not fixed (needs a decision or live-test data I don't have)

1. **`skilling/flour_milling.yaml` step 4** — `INTERACT_OBJECT Hopper controls Operate` uses
   `await_condition: "idle"`. CLAUDE.md classifies `INTERACT_OBJECT` as an "instant" command
   that should use a state check, not `idle` — but there's no obvious replacement predicate
   here (the flour goes into a bin, not inventory, so no `has_item:`/`location:` check
   applies). Needs a live test to determine whether `idle` actually races here.
2. **`skilling/woodcutting_lumbridge.yaml`** — requirements say "Any axe (bronze or better)"
   but don't say it must be **equipped**. Step 3 is `BANK_DEPOSIT_ALL` — if the axe is sitting
   in inventory rather than equipped, this deposits it away and step 6's `CHOP_TREE` will fail
   with no axe, on the very first pass. Not fixed: I don't know the cached account's actual
   axe state, and guessing an item name to insert an `equip_item` step risks being wrong.
   **Verify axe is equipped before the live test.**
3. **`combat/cow_killer_training.yaml` steps 7-8** — the file's own notes describe `KILL_LOOP`
   (step 7) and `KILL_COW_GET_HIDES` (step 8) as two *alternative* modes, but the flat
   `steps:` list runs both unconditionally back-to-back (100 no-loot kills, then 200 more with
   hide collection). Content/design decision, not a mechanical defect — left as-is.
4. **`combat/hill_giants_loot.yaml`** — `EAT` (step 7) has no HP-threshold arg and fires every
   loop iteration unconditionally (documented in the file's own notes). No `hp:`/`hp_pct:`
   predicate exists in the engine to gate it. Pre-existing, known, requires a new engine
   feature — out of scope here.
5. **`combat/hill_giants_loot.yaml`** — step ids skip `2` (`1,3,4,5,6,7`). Cosmetic only (no
   `goto_step:` targets it), not fixed.
6. **`combat/cow_killer_no_bones.yaml`, `combat/hill_giants.yaml`** — no `steps:` key at all;
   these are config-only sidecars for a never-built "configurable loot" feature, superseded by
   the split `hill_giants_loot/restock/resupply/travel.yaml` chain. Matches the prior sweep's
   suspicion — **recommend archiving/deleting**, but that's a content decision I won't make
   unilaterally.
7. **Dead-but-harmless loop metadata** — `loop.max_iterations` (flat mode) and
   `loop.delay_between_loops_ms` appear in `chicken_killer_loop.yaml`,
   `fishing_karamja_harpoon.yaml`, `fishing_karamja_lobster.yaml`, and `hill_giants_loot.yaml`
   but are never read by the executor (the real cap is `run_routine.py --loops`). Cosmetic
   only — didn't touch since they don't change behavior, but a driver reading these files
   should not expect them to be enforced.
8. **`skilling/mining_falador_iron.yaml`** — `POWER_MINE` has no `timeout_ms` (defaults 30s)
   and no `await_condition`, unlike the fixes in §1/§2 above. Deliberately **not** fixed:
   `PowerMineCommand.java` runs `while (!isInterruptRequested())` — genuinely infinite by
   design (matches the file's own notes, "repeat indefinitely... Stop with KILL command", and
   `loop: enabled: false`). No `timeout_ms` value would make it "complete" normally; the short
   default is consistent with fire-and-forget semantics the author already documented. This is
   the one blocking-command case where the 30s default is actually correct behavior, not a bug.
9. **Item-name underscore convention** — CLAUDE.md's Object Naming table says items use
   spaces ("Raw shrimps"), but every `BANK_WITHDRAW`/`BANK_DEPOSIT_ITEM`/`PICK_UP_ITEM` call
   across this entire corpus (including files already marked `VALIDATED`) underscores
   multi-word item names (`Iron_ore`, `Law_rune`, `Swordfish`). This is self-consistent and
   clearly the actual working convention for space-delimited command args (`cooking_lumbridge.yaml`
   even has a `${var|underscore}` filter specifically for this). Noting this so nobody "fixes"
   it against CLAUDE.md's table by mistake — CLAUDE.md's rule likely describes a different
   context (e.g. `find_widget` text matching), not command args.

## 4. Readiness table

| Routine | Parses? | Vocab-clean? | Structure-ok? | Verdict |
|---|---|---|---|---|
| `combat/chicken_killer_training.yaml` | Yes | Yes | Fixed (timeout) | **READY** |
| `combat/chicken_killer_loop.yaml` | Yes | Yes | Fixed (GOTO + timeout) | **READY** |
| `skilling/woodcutting_lumbridge.yaml` | Yes | Yes | Fixed (timeout) | **READY** (verify axe equipped — flag #2) |
| `skilling/mining_falador_iron.yaml` | Yes | Yes | OK (fire-and-forget by design) | **READY** |
| `skilling/mine_iron_ore.yaml` | Yes | Yes | OK (proper inner/outer, correct MINE_ORE usage) | NEEDS-LIVE-TEST (mining 60 gate) |
| `skilling/superheat_steel_bars.yaml` | Yes | Yes | OK (already "v2 optimized") | NEEDS-LIVE-TEST (mining 60/magic 43/smith 30 gate, staff+runes) |
| `skilling/superheat_mining_guild.yaml` | Yes | Yes | Fixed (3 defects — was structurally broken, see §2) | NEEDS-LIVE-TEST (same skill gates; fixes unverified live) |
| `skilling/cooking_lumbridge.yaml` | Yes | Yes | Fixed (crash removed) | NEEDS-LIVE-TEST (needs 28 raw fish banked) |
| `skilling/fishing_draynor.yaml` | Yes | Yes | Fixed (timeout + doc) | NEEDS-LIVE-TEST (self-contained grind, but long — verify target level) |
| `combat/cow_killer_training.yaml` | Yes | Yes | Fixed (timeout); flag #3 | NEEDS-LIVE-TEST (needs banked melee gear) |
| `combat/hill_giants_loot.yaml` | Yes | Yes | OK structurally; flag #4 (food waste) | NEEDS-LIVE-TEST (dungeon start, gear+food) |
| `combat/hill_giants_restock.yaml` | Yes | Yes | Fixed (delay key) | NEEDS-LIVE-TEST (mid-trip only) |
| `combat/hill_giants_resupply.yaml` | Yes | Yes | Fixed (delay key) | NEEDS-LIVE-TEST (GE start) |
| `combat/hill_giants_travel.yaml` | Yes | Yes | Fixed (delay key + timeout) | NEEDS-LIVE-TEST (GE start, brass key) |
| `skilling/fishing_karamja_harpoon.yaml` | Yes | Yes | OK (already has generous timeouts) | NEEDS-LIVE-TEST (level 35, ferry hops, many failure points) |
| `skilling/fishing_karamja_lobster.yaml` | Yes | Yes | OK | NEEDS-LIVE-TEST (level 40, ferry hops) |
| `skilling/flour_milling.yaml` | Yes | Yes | Flag #1 (`idle` await) | NEEDS-LIVE-TEST |
| `combat/cow_killer_no_bones.yaml` | Yes | n/a (no steps) | n/a | **STALE** (flag #6) |
| `combat/hill_giants.yaml` | Yes | n/a (no steps) | n/a | **STALE** (flag #6) |

## 5. Ranked shortlist — first unattended live grind test

1. **`combat/chicken_killer_training.yaml`** — the handoff's own pick, and now the strongest
   candidate: level-1 NPCs (no death risk), no food/banking needed, self-travels to the coop,
   and the fatal 30s-timeout-vs-many-minute-runtime mismatch is fixed. Only needs any weapon
   equipped. Single run by design (`loop.enabled: false`) — good first smoke test of the fix.
2. **`combat/chicken_killer_loop.yaml`** — same safety profile as #1, now with the missing
   GOTO added, wired for a real multi-hour session (50×100 kills via the flat loop, restarts
   at the coop GOTO each pass). Best pick if #1's smoke test succeeds and a longer unattended
   run is wanted next.
3. **`skilling/woodcutting_lumbridge.yaml`** — the handoff's other named pick. Structurally
   fixed (timeout), but rank it third rather than second because of flag #2 (unconfirmed
   whether the axe is equipped vs. banked) — worth a quick `get_game_state(fields=["equipment","inventory"])`
   check on the target account before queuing it, to avoid step 3 silently banking the only
   axe.

`skilling/mining_falador_iron.yaml` is a strong fourth option if mining 15 + a pickaxe is
confirmed on the account — it was already correctly designed as fire-and-forget and needed no
fix.
