# Routine Corpus Hardening — 2026-07-18

*Two-part pass over the YAML routine corpus. Task 1: first-time defect audit of
`routines/quests/*.yaml` (5 files) and `routines/utility/*.yaml` (2 files) — these
were NOT covered by the same-day `journals/GRIND_ROUTINE_READINESS_2026-07-18.md`
audit, which only looked at `skilling/` and `combat/`. Task 2: a corpus-WIDE scan
(all of `skilling/combat/quests/utility/tutorial_island`) for GOTO steps that walk
a real distance but have no `await_condition` — the DEFECT-19 lesson learned live:
without one, `run_routine.py`'s 30s step default gives up while navigation is
still walking, misreporting the run as finished while the client keeps moving
completely unsupervised. Vocabulary confirmed against `mcptools/tools/routine.py`
+ `mcptools/tools/monitoring.py` (read, not guessed); command existence confirmed
against `COMMAND_REFERENCE.md`'s 131-command list. No Java or Python touched.*

## Task 1 — quests/ and utility/ audit

5 quest files + 2 utility files parsed and checked against the engine vocab
(`plane:N`, `has_item:X`, `no_item:X`, `inventory_count:<op>N`, `location:X,Y`,
`idle`, `dialogue`, `no_dialogue`; step shapes `action:`/`args:`, `mcp_tool:`
[only `equip_item`/`click_widget`/`find_and_click_widget`/`click_text` dispatch],
`repeat:`, `repeat_until:`) and against `COMMAND_REFERENCE.md`. **Every command
used across all 7 files (`BANK_*`, `GOTO`, `INTERACT_NPC`, `INTERACT_OBJECT`,
`CLICK_DIALOGUE`, `CLICK_CONTINUE`, `PICK_UP_ITEM`, `USE_ITEM_ON_NPC`,
`USE_ITEM_ON_OBJECT`, `CLIMB_LADDER_UP/DOWN`, `KEY_PRESS`, `TELEPORT_HOME`) exists
in the 131-command reference — no typos found.** None of the dead patterns a
prior sweep found elsewhere (`poll_interface_open`, `mcp_tool: click_text`, an
`idle` await on a blocking command) appear in this corpus. `mcp_tool: equip_item`
in `restless_ghost.yaml` step 9 is the one `mcp_tool:` usage and is correct per
the engine's dispatch table.

### Fixes applied

| File | Fix |
|---|---|
| `utility/death_escape.yaml` | Renamed `delay_ms: 1000` → `delay_after_ms: 1000` on 5 `KEY_PRESS` steps (ids 3, 5, 7, 9, 11). `delay_ms` is not a key `_execute_step_once` ever reads (only `delay_before_ms`/`delay_after_ms` are) — same dead-key class as the prior audit's `delay_after:`→`delay_after_ms:` fix. The intended "press Space, wait 1s, press again" pacing between repeated Death's-Domain dialogue presses was silently never applied. |

### Flagged, not fixed

1. **`quests/cooks_assistant.yaml` step 1** — `BANK_OPEN` (with `location:
   lumbridge_bank`) is the very first step, with no preceding `GOTO` to the
   bank. If the quest doesn't reliably start within banking range, this fails
   at step 1. Not fixed: I don't know the account's actual starting position
   when this quest is queued, and guessing wastes a step if it's already
   correct. Needs a live-test data point or explicit starting-location
   assumption from the user.
2. **`quests/sheep_shearer.yaml` step 4** — `skip_if: "has_item:Shears"` on
   `PICK_UP_ITEM Shears`. `skip_if` is not a key the executor reads anywhere
   (only `action`/`args`/`mcp_tool`/`repeat`/`repeat_until`/`await_condition`/
   `delay_before_ms`/`delay_after_ms`/`timeout_ms`/`id`/`phase` are consumed by
   `_execute_step_once`/`_execute_single_step`). Dead key, but harmless —
   `PICK_UP_ITEM` on an item already held just fails gracefully rather than
   corrupting state, so this doesn't change behavior. Left alone per the same
   precedent as the prior audit's cosmetic dead-key findings (`loop.max_iterations`,
   `delay_between_loops_ms`) — not fixed, noted so nobody expects `skip_if` to
   actually skip anything.
3. **`utility/gravestone_retrieval.yaml`** — this file has **no `steps:` key at
   all**, only `manual_steps:` (Claude-Code-session prose). `handle_execute_routine`
   in `routine.py` returns `{"success": False, "error": "Routine has no steps"}`
   immediately for any file missing `steps:` — so this routine **cannot be run
   via `run_routine.py`** in its current form. Exact same "config-only sidecar"
   pattern the prior `GRIND_ROUTINE_READINESS` audit flagged for
   `combat/hill_giants.yaml`/`cow_killer_no_bones.yaml`. The commands it
   documents (`FIND_GRAVE`, `LOOT_GRAVE`) DO exist in `COMMAND_REFERENCE.md`, so
   a real `steps:` block is buildable — but its `manual_steps:` GOTO uses
   templated placeholders (`{grave_x} {grave_y} {grave_plane}`, filled in from a
   `query_nearby` result at runtime), and there's no engine predicate for
   `GET_GRAVE_STATUS`/gravestone-timer state, so writing a faithful `steps:`
   block is a content/design task, not a mechanical fix. Recommend a follow-up
   pass specifically to build the real step list; not attempted here.
4. **General engine caveat (applies corpus-wide, not just these two dirs)** —
   `monitoring._check_condition`'s `location:X,Y` match is `max(|dx|,|dy|) <= 3`
   and does **not** check plane. A handful of routines target the same/nearby
   x,y across two different planes in adjacent steps (e.g.
   `romeo_and_juliet.yaml` steps 4→6, `sheep_shearer.yaml` steps 7→9). This
   didn't misfire in any step I could verify statically, but it's a latent
   false-positive risk (an await could report "arrived" while the player is
   still one plane off, if a stair/ladder step's own `plane:` await hasn't
   actually resolved yet) worth knowing about for anyone debugging a flaky
   plane-transition step.

## Task 2 — corpus-wide long-GOTO await fix

Scanned every `routines/**/*.yaml` for `action: GOTO` (and the `command: "GOTO
..."` alternate shape — found only in two `manual_steps:`/templated blocks that
the engine never executes, see below) lacking `await_condition`. For each
missing case, classified the walking distance using the previous known
coordinate in the same file (previous GOTO target, or a `TELEPORT_HOME` reset to
~Lumbridge spawn) via Chebyshev distance, then applied:

- **Unknown/first-in-file position** → `await_condition: "location:X,Y"` +
  `timeout_ms: 120000` (can't classify as short, so default to the generous
  value).
- **> 20 tiles** (or a same-region underground/basement y+6400 jump, real
  distance unclear) → `timeout_ms: 120000`.
- **≤ 20 tiles** → `timeout_ms: 60000`.
- **≤ 3 tiles** (a "you're basically already there" hop — almost always a
  post-ladder/post-staircase local reposition, or a hop between two files that
  already end/start at the same tile) → **skipped**, not touched. At that
  distance the walk is inherently short (well under the 30s timeout regardless
  of pathfinder fallback), so the DEFECT-19 race this task targets doesn't
  really apply, and the task's own guidance permits leaving "deliberately-short
  adjacent moves" alone.

**60 GOTO steps got an await added**, across 17 files:

| File | Steps (await added) |
|---|---|
| `combat/cow_killer_training.yaml` | 1, 6 |
| `quests/cooks_assistant.yaml` | 6, 9, 11, 13, 15, 22 |
| `quests/imp_catcher.yaml` | 1, 3 |
| `quests/restless_ghost.yaml` | 1, 5, 10, 16, 18, 20, 22 |
| `quests/romeo_and_juliet.yaml` | 1, 4, 10, 13a, 13b, 13c, 13, 15a, 15b, 15c, 15d, 15, 20, 26a, 26b, 26, 27 (17 steps) |
| `quests/sheep_shearer.yaml` | 1, 5, 7, 12 |
| `skilling/fishing_draynor.yaml` | 1 |
| `skilling/mining_falador_iron.yaml` | 1, 3, 5 |
| `skilling/woodcutting_lumbridge.yaml` | 1, 5, 7 |
| `tutorial_island/03_survival_expert.yaml` | 1 |
| `tutorial_island/04_woodcutting_firemaking.yaml` | 12, 15 |
| `tutorial_island/05_cooking.yaml` | 11 |
| `tutorial_island/05_cooking_to_quest_guide.yaml` | 1, 3, 4, 5, 6 |
| `tutorial_island/07_mining_smithing.yaml` | 1 |
| `tutorial_island/08_combat.yaml` | 1, 27 |
| `tutorial_island/10_prayer_magic.yaml` | 8, 17 |
| `utility/death_escape.yaml` | 1 |

`tutorial_island/07/08/10` already had *some* location-based awaits from the
2026-07-18 tutorial transcription pass (DEFECT-7/DEFECT-10: "GOTO's own success
flag is unreliable, verify via location await instead") — I only added awaits to
the GOTO steps in those files that were still missing one; existing awaits
(with or without an explicit `timeout_ms`) were left untouched as out of this
task's scope.

### Deliberately skipped (not touched) — 9 GOTO steps

**Adjacent/negligible-distance moves (≤3 tiles), matching the "deliberately-short
adjacent move" exception in the task brief:**

| File | Step | Reason |
|---|---|---|
| `quests/romeo_and_juliet.yaml` | 6 | 1 tile from step 4's target — post-staircase "walk to Juliet" in the same room. |
| `quests/romeo_and_juliet.yaml` | 22 | Same as above, second visit to Juliet's room. |
| `quests/sheep_shearer.yaml` | 9 | 2 tiles from step 7 — post-ladder walk to the spinning wheel in the same room. |
| `tutorial_island/02_gielinor_guide.yaml` | 11 | ~4 tiles, "stand in front of door" before opening it — same room as the preceding dialogue. |
| `tutorial_island/03_survival_expert.yaml` | 7 | 2 tiles from step 1 — walk to the adjacent fishing spot. |
| `tutorial_island/10_prayer_magic.yaml` | 1 | 0 tiles — `09_banking.yaml`'s own final step (id 9) already ends at this exact tile (3124,3124); this is a continuity no-op across the file boundary. |
| `tutorial_island/10_prayer_magic.yaml` | 11 | 3 tiles from step 10 (which already has its own await). |

**Explicit anti-pattern / likely-superseded file — flagged, not touched:**

| File | Steps | Reason |
|---|---|---|
| `tutorial_island/06_quest_guide.yaml` | 1, 2 | This file's own header comment (line 125) says: *"await_condition and repeat_until cause timeouts - removed"* — a direct, documented prior finding that adding `await_condition` to this file's GOTOs previously broke it. Additionally, `00_master.yaml`'s chain runs `05_cooking_to_quest_guide.yaml` immediately before `06_quest_guide.yaml`, and `05_cooking_to_quest_guide.yaml`'s own header says *"Next section: 06_quest_guide.yaml (now merged into this file)"* — i.e. `05_cooking_to_quest_guide.yaml` already walks to the Quest Guide, talks to them, opens the quest journal, and climbs down the ladder (its steps 1-19), and `06_quest_guide.yaml` appears to redundantly repeat that same sequence. This looks like a stale/superseded file that the master chain still references by accident rather than routine content that needs a mechanical await fix. **Recommend a content decision** (drop `06_quest_guide.yaml` from `00_master.yaml`'s chain, or confirm it's an intentional idempotent double-check) before touching its GOTOs at all — did not add awaits here to avoid re-triggering the exact failure mode its own comment warns about. |

**Not real engine-executed GOTOs, so out of scope entirely** — `death_escape.yaml`
and `gravestone_retrieval.yaml` each have a `command: "GOTO ..."` line, but both
are inside `manual_steps:` (documentation for manual Claude-Code-session
execution, never read by `handle_execute_routine`, which only consumes the
`steps:` key). `gravestone_retrieval.yaml`'s copy additionally uses templated
placeholders (`{grave_x} {grave_y} {grave_plane}`) — ambiguous coordinates by
definition, explicitly excluded by the task brief even if it were a real step.

### Caveat carried forward (per task brief)

`location:X,Y` matching is `max(|dx|,|dy|) <= 3` tiles — generous enough to
absorb GOTO's own ±1-tile arrival slop (DEFECT-7), so the awaits added here
should trigger correctly even on an imprecise landing. The `timeout_ms` values
chosen (60s/120s) are a deliberately generous safety margin, not a tuned
estimate — they should be re-tuned down once navigation (DEFECT-19) is fixed
and each routine is live-gated again.

## Summary

- **Task 1**: 7 files audited (5 quests + 2 utility), 1 file fixed
  (`death_escape.yaml` dead `delay_ms` key), 4 items flagged (missing starting
  GOTO in `cooks_assistant.yaml`, dead `skip_if` in `sheep_shearer.yaml`,
  no-`steps:` in `gravestone_retrieval.yaml`, general plane-blind
  `location:X,Y` caveat).
- **Task 2**: 60 GOTO steps across 17 files got `await_condition` +
  `timeout_ms` added; 9 steps deliberately left alone (7 as genuinely-adjacent
  moves, 2 flagged as a likely-superseded file with its own documented
  anti-pattern warning).
- **Total files edited this session**: 18 (`utility/death_escape.yaml` counted
  once for both its Task 1 and Task 2 fixes; the other 17 files from the Task 2
  table plus `utility/death_escape.yaml` itself = 18 distinct files).
- All 18 edited files re-parsed clean with `yaml.safe_load` after editing
  (verified individually, plus a final full-corpus `yaml.safe_load` pass over
  every `routines/**/*.yaml` file with no parse errors reported). No Java, no
  other Python, and no `routines/skilling/*`/`routines/combat/*` *content*
  beyond the Task 2 GOTO-await mechanical fix were touched (skilling/combat
  were already hardened by `GRIND_ROUTINE_READINESS_2026-07-18.md` and
  intentionally not re-audited here).
