# Routine Corpus Validation Triage — 2026-07-19

Read-only triage of every routine outside `routines/money_making/` (41 files:
combat, quests, skilling, utility, tutorial_island, test, generated,
common_actions). Method: `validate_routine_deep` run on all files
(baseline), then manual line-by-line schema review against
`ROUTINE_SCHEMA.md` by six parallel review streams, with source spot-checks
in `mcptools/tools/routine.py`, `mcptools/tools/monitoring.py`,
`manny_tools.py`, and `manny_src/utility/commands/*.java`.

No file other than this report was modified. No fixes were applied — every
entry below is a SUGGESTED fix only.

Validator baseline: only one file fails validation outright
(`tutorial_island/05_cooking_to_quest_guide.yaml` — and that is a **validator
false positive**, see V-1). Everything else passes with warnings the
validator already surfaces (dead `location:` step keys, unknown top-level
keys, dead `loop.max_iterations`/`start_step`, missing `stop_conditions`,
non-terminal KILL_LOOP in `cow_killer_training.yaml`). Those pre-flagged
items are not repeated below; this report is the *silent* stuff the
validator misses.

---

## HIGH — will break the routine, run dangerously long/wrong, or fail at the worst moment

### H-1. `routines/utility/gravestone_retrieval.yaml` (whole file) — death-recovery routine is a non-executable stub
No top-level `steps:` key exists — only `manual_steps:` prose and doc blocks.
`run_routine.py` on this file returns `{"success": False, "error": "Routine
has no steps"}` immediately (routine.py:1088-1089). `CLAUDE.md`'s Death
Recovery section names this file as a routine to run, right under the
"ALWAYS use run_routine.py" protocol — an agent following both directives
mid-death-recovery gets an instant failure at exactly the moment automated
gravestone retrieval is needed. The underlying commands are real
(`FindGraveCommand.java`, `LootGraveCommand.java`, registered in
`PlayerHelpers.java:1459-1460`; `LootGraveCommand.java:87` gates on ≤15
tiles), so only the YAML wrapper is missing.
**Fix:** either annotate CLAUDE.md that this file is a manual runbook (use
direct `FIND_GRAVE`/`LOOT_GRAVE` send_commands), or build a real `steps:`
block once a gravestone-state predicate exists to resolve the
`{grave_x}/{grave_y}` placeholders.

### H-2. `routines/skilling/woodcutting_lumbridge.yaml` (no `loop:` anywhere; intent stated at :105) — "continuous" grind runs exactly once
Step 10's comment says "Loop back to step 5 for continuous woodcutting", but
the file has no `loop:` block at all. With neither flat nor nested loop
enabled, the engine hits `else: break` (routine.py:1537-1538) after one pass
— one inventory of logs, one bank trip, done. `--loops N` has zero effect
(it only bounds a loop that never re-enters). Silent: run reports success.
**Fix:** add `loop: {enabled: true, repeat_from_step: 5, stop_conditions:
["woodcutting_level:<target>"]}` (or `repeat_from_step: 1` for full re-runs).

### H-3. `routines/skilling/superheat_mining_guild.yaml:61-66, 128-134` — iron rocks coordinate is members-only/unreachable
`iron_rocks_guild` is `(3030, 9720)` and step 8 GOTOs/awaits it.
`superheat_steel_bars.yaml:353-357` documents this exact coordinate as
broken: "Iron rocks at (3030, 9720) are MEMBERS ONLY — use (3029, 9739)
instead... GOTO fails with UNREACHABLE... y-coords should be ~9735-9745."
`mine_iron_ore.yaml` and `superheat_steel_bars.yaml` both use `(3029,
9739)`. Every outer-loop pass of this routine walks to a dead-end tile and
times out (or mines the wrong, members-only cluster).
**Fix:** change lines 62-63, 131, 133 from `3030,9720` to `3029,9739`.

### H-4. `routines/skilling/superheat_mining_guild.yaml:158-164` — superheat cast unverified before the inner-loop exit check
Step 10 (`CAST_SPELL_ON_INVENTORY_ITEM "Superheat_Item Iron_ore"`) has no
`await_condition`, only `delay_after_ms: 1800` — but the real cast takes
~3.5s (per `superheat_steel_bars.yaml`'s own notes). The inner loop's
`exit_conditions` check runs right after this step and can read stale
inventory (~1.7s early), producing wrong continue/exit decisions each pass.
The schema's own worked example (§j.3), "adapted from" this very file, shows
`await_condition: "no_item:Iron ore"` — the real file lacks it.
**Fix:** add `await_condition: "no_item:Iron ore"`, `timeout_ms: 10000-15000`,
matching `superheat_steel_bars.yaml` step 10.

### H-5. `routines/skilling/mining_falador_iron.yaml:87-94` — staircase await is an always-true predicate
Step 4 (`INTERACT_OBJECT "Staircase Climb-down"`) awaits `plane:0`, but the
player is *already* on plane 0 when the command fires (step 3 GOTOs to
`3019 3450 0`; Dwarven Mine depth is encoded via the ~+6400 Y offset, not
plane). The await passes on the first poll whether or not the click worked —
same silent-instant-pass mechanism as `idle` on blocking commands (§e). A
missed staircase click only surfaces later as a confusing step-5 GOTO
timeout from the surface. The file even defines the correct target,
`locations.inside_building: (3019, 9739)` at :39-43, and never uses it.
**Fix:** change step 4's await to `"location:3019,9739"`.

### H-6. `routines/combat/hill_giants_loot.yaml:26-79` — loots the drops of a giant that is still alive
Step 1 (`ATTACK_NPC "Hill_Giant"`, `delay_after_ms: 1000`) fires one attack
action and returns immediately (not a blocking kill command). One second
later the loop marches into `PICK_UP_ITEM Big_bones / Law_rune /
Limpwurt_root` — but a Hill Giant kill takes far longer than 1s, so on
every pass the loot steps run while the giant is alive and find nothing;
`BURY_ALL` buries nothing; step 7 `EAT` eats unconditionally *every pass*
(the file's own :70-79 note admits this), draining food. Combined with the
validator-flagged unbounded flat loop, the routine spins attack-spam/no-loot
cycles until `--loops` (default 10000) while slowly eating its supplies.
**Fix:** replace the whole manual loop with `KILL_LOOP_CONFIG` + a JSON
config carrying `loot_items: ["Law rune", "Big bones", "Limpwurt root",
"Nature rune"]` (§h) — that is exactly the use-case this file reimplements
incorrectly. (Note: `KILL_LOOP_CONFIG` forces food OFF; if food management
matters here, use `KILL_LOOP Hill_Giant Swordfish N` and accept default
rune-only loot, or alternate CONFIG batches with restock steps.)

### H-7. `routines/combat/cow_killer_training.yaml:92-106` — KILL_COW_GET_HIDES always times out and leaves the client grinding unmanaged
Step 8's command has no kill-count arg (`KillCowGetHidesCommand.java` — runs
until manually stopped, as the step's own notes say), yet the step has
`timeout_ms: 3600000`. After exactly 1h, `run_routine.py` gives up, reports
the step failed, and exits — while the plugin keeps killing cows
unsupervised indefinitely. Unlike `KILL_LOOP`/`KILL_LOOP_CONFIG`, this
command is NOT covered by the DEFECT-26 `active_loop` polling fix (§e.1), so
the watchdog/run-ledger protection dies with the runner. This compounds the
validator-flagged non-terminal KILL_LOOP at step 7: the file runs 100
no-loot kills, then an infinite hide-collection session it can never manage.
**Fix:** short term, delete step 8 (or move it to its own routine and
document the manual-stop requirement); proper fix is plugin-side — give
KILL_COW_GET_HIDES a max-kills arg and/or `active_loop` export parity.

### H-8. `routines/quests/romeo_and_juliet.yaml:262-268, 287-306` — one CLICK_CONTINUE + a passive await = guaranteed step timeout
Step 19 sends a single `CLICK_CONTINUE` and then awaits
`has_item:Cadava potion` (30s default); step 24 does the same awaiting
`no_item:Cadava potion` with `timeout_ms: 60000` and notes "Long cutscene."
One click cannot drain a multi-page exchange/cutscene; nothing advances the
dialogue while the await polls, so the condition can never become true and
both steps hang to timeout.
**Fix:** convert both to `action: CLICK_CONTINUE` with `repeat_until:
"<same atom>"` (Grammar 1 accepts `has_item:`/`no_item:` in `repeat_until`),
plus a `max_iterations` cap.

### H-9. `routines/quests/romeo_and_juliet.yaml:64-84, 93-117, 129-154` — three unexhausted-dialogue sequences
Steps 3, 8, 12 each send exactly one `CLICK_CONTINUE` (no repeat/await)
after `INTERACT_NPC` on Romeo / Juliet / Father Lawrence, then immediately
GOTO / interact-object. Multi-page openings are near-certain; per §(i) the
unexhausted monologue silently blocks or mis-targets whatever comes next.
Related MED: the two `GOTO "3158 3425 1"` steps (:93-98, :287-292) have no
`await_condition` at all, so the Juliet talk-to can fire mid-walk.
**Fix:** `CLICK_CONTINUE` + `repeat_until: "no_dialogue"` after each talk-to;
add `await_condition: "location:3158,3425"` to both GOTOs.

### H-10. `routines/quests/sheep_shearer.yaml:99-109` — off-by-one: shears occupy the 20th slot
Step 6 shears with `repeat: 20`, short-circuited by `await_condition:
"inventory_count:>=20"`. `inventory_count` counts *used slots*, and the
player is carrying Shears (picked up step 4) — so the check goes true at 19
wool + 1 shears and stops a wool short. The quest needs 20 wool; the deficit
surfaces only at turn-in, far downstream.
**Fix:** use `inventory_count:>=21` (wool + shears), or count differently.

### H-11. `routines/quests/sheep_shearer.yaml:69-88` — self-documented unexhausted dialogue
Step 3's own note says "Multiple continue clicks needed through dialogue"
but the step sends exactly one `CLICK_CONTINUE`, then step 4 pivots to
`PICK_UP_ITEM Shears`. Same §(i) trap as H-9, acknowledged in the file's own
prose and never implemented.
**Fix:** `repeat_until: "no_dialogue"` on the continue step.

### H-12. `routines/quests/imp_catcher.yaml:97-104` — quest-start option clicked before it exists
Step 6 sends one unconditional `CLICK_CONTINUE`, then step 7 immediately
`CLICK_DIALOGUE "Give me a quest please"`. The file's own header (:12-15)
says Mizgog's opener needs multiple continues before the option appears; if
it isn't rendered yet the option click silently no-ops and the quest never
starts, while every later step "succeeds" pointlessly.
**Fix:** step 6 → `CLICK_CONTINUE` + `repeat_until: "no_dialogue"`.

### H-13. `routines/tutorial_island/10_prayer_magic.yaml:1-5 vs 153-161, 195-199, 214-218` — VALIDATED header over an admitted open blocker
The STATUS header claims full validation ("ISLAND COMPLETE"), but the inline
comment at :153-161 documents an unresolved blocker: Brother Brace paces a
2-3 tile radius and ~10 live attempts at `INTERACT_NPC`/`CLICK_NPC` from
every adjacent tile all failed ("I can't reach that!"); it states outright
that the prayer section past step 12 is NOT re-validated. Steps 12 and 15
(`INTERACT_NPC "Brother_Brace Talk-to"`) carry no retry/re-resolve
mitigation. Anyone trusting the header schedules an unattended run into a
known wall.
**Fix:** correct the STATUS header now; add a pacing-aware retry
(re-resolve NPC position per attempt) before steps 12/15 to unblock.

### H-14. `routines/tutorial_island/10_prayer_magic.yaml:342-347, 376-388` — DEFECT-6 early-exit risk at the mainland-exit gate
Steps 27/30b drain dialogue with `KEY_PRESS space` + `repeat_until:
"no_dialogue"`, but the file's own notes document DEFECT-6: the state file
can misreport dialogue as closed *between pages*, so the check-first loop
can exit mid-monologue. Step 30b's note literally instructs a human to
"press space a few more times" if that happens — no compensating mechanism
is in the YAML. This gates the final mainland-exit sequence: a silent early
exit strands the run after everything else succeeded.
**Fix:** append 2-3 unconditional `KEY_PRESS space` steps (extra presses on
closed dialogue are inert) and/or raise `repeat_until_timeout_ms` so the
predicate re-check outlives the inter-page gap.

### H-15. `routines/tutorial_island/06_quest_guide.yaml:68-76` — DEFECT-24 no-op widget click, in a file marked VALIDATED
Step 9 clicks widget `15138820` — the dialogue speaker-name *header* (group
231 child 4), not an option; per §(i)/DEFECT-24 this is a no-op and the
routine marches on as if it succeeded. Mitigating context: `00_master.yaml`
deliberately excludes this file from the chain (:59-71) and
`05_cooking_to_quest_guide.yaml:224-226` documents this exact trap — but the
file still says `STATUS: VALIDATED` at :2 and is a copy-paste hazard.
**Fix:** delete the file or mark it SUPERSEDED at the top, pointing at
`05_cooking_to_quest_guide.yaml`; strip step 9 either way.

---

## MED — degrades reliability, wastes time, or misattributes failures

### M-1. `routines/combat/cow_killer_training.yaml:31-38` — plane-blind await can pass underneath the bank
Step 1 GOTOs to the plane-2 Lumbridge bank and awaits `location:3208,3220`.
The `location:` check compares X,Y only (monitoring.py:621-627 — no plane
term), so if pathing stalls on plane 0 under the bank the await still
passes, and steps 2-5 (BANK_OPEN etc.) fail confusingly. Indoor plane-2
navigation via bare GOTO is itself against the indoor-navigation protocol.
**Fix:** split into explicit staircase steps with `plane:2` awaits (Grammar 1
has `plane:N` — this is the case it exists for), then the location await.

### M-2. `routines/combat/chicken_killer_training.yaml:45-62` — 1h ceiling for a 200-kill batch
`KILL_LOOP Chicken none 200` with `timeout_ms: 3600000`. The schema's table
(§e) puts a *100*-kill batch at "many minutes to over an hour"; 200 kills
can plausibly exceed 1h, at which point the runner abandons a
still-grinding loop (the exact DEFECT-26 unmanaged-grind failure the
timeout was added to prevent).
**Fix:** raise to `7200000` (2h) to scale with the kill count.

### M-3. `routines/combat/hill_giants_restock.yaml:150-157` — always-true `plane:0` await on the dungeon ladder
Step 14 (`Ladder Climb-down`) awaits `plane:0`; the note itself says
"Underground plane is still 0", i.e. the condition is already true before
the click. Identical mechanism to H-5. A missed ladder click surfaces as a
misattributed step-15 GOTO timeout while standing on the surface.
**Fix:** await the underground landing instead, e.g.
`"location:3117,9852"`-area coords (verify exact ladder-bottom tile).

### M-4. `routines/combat/hill_giants_restock.yaml:82-122` — 300 ms withdraw pacing contradicts the sibling's measured requirement
All six BANK_WITHDRAWs use `delay_after_ms: 300`, while
`hill_giants_resupply.yaml:75` documents "Each withdraw needs ~4 second
delay for reliability". Worse, quantities 25 and 21 (steps 8, 10) route
through the Withdraw-X typed dialog, which cannot round-trip in 300 ms —
short withdrawals silently produce a wrong loadout (missing food/runes) that
only fails deep in the dungeon.
**Fix:** either bump delays to match the sibling's proven 4000 ms, or better,
replace delays with `await_condition: "has_item:<item>"` per withdrawal
(and use `inventory_count:>=27` before leaving).

### M-5. `routines/combat/hill_giants_travel.yaml:50-66` — 4-hour kill loop started with zero arrival verification
Steps 2-3 (door open, ladder climb-down) have only fixed delays — no awaits
— and there is no GOTO to the defined-but-unused `hill_giants_dungeon`
location (:37-40) before step 4 launches `KILL_LOOP Hill_Giant Swordfish
500` with a 4h ceiling. If the door (needs Brass key — also never checked
via `has_item:Brass key`) or ladder click missed, the kill loop hunts for
Hill Giants on the surface. Also note steps use lowercase `"door"`/
`"ladder"` args — verify the interaction matcher is case-insensitive.
**Fix:** add `await_condition` on an underground coordinate after step 3, a
`has_item:Brass key` gate before step 2, and a GOTO to `3116 9851` before
the KILL_LOOP.

### M-6. `routines/combat/hill_giants_resupply.yaml:20-70` — no deposit step, fire-and-hope banking
The routine opens the bank and starts withdrawing into whatever inventory
the previous trip left (header assumes it's empty). A part-full inventory
overflows silently mid-withdraw and the loadout comes out wrong. All steps
rely on fixed delays with no `has_item:` verification.
**Fix:** add `BANK_DEPOSIT_ALL` after step 1; add `has_item:` awaits on key
withdrawals (Brass key, Swordfish).

### M-7. Quest corpus systemic — no file uses the canonical dialogue-drain pattern
Not one of the 5 quest files uses `CLICK_CONTINUE` + `repeat_until:
"no_dialogue"` (§i's canonical pattern) anywhere; every drain is a single
unconditional continue or a blind `repeat: N`. Beyond the HIGH entries:
- `imp_catcher.yaml:108-118` — blind `repeat: 5` before `CLICK_DIALOGUE "Yes"`.
- `restless_ghost.yaml:123-136` — blind `repeat: 5` before the swamp GOTO.
- `restless_ghost.yaml:201-208` — `repeat: 10` where the file's own header
  (:38) says "About 10+ continues total" — under-count risk acknowledged and
  shipped anyway.
- `cooks_assistant.yaml:111-136` — three consecutive `CLICK_DIALOGUE` option
  clicks with zero interleaved continues; if any intermediate narrative page
  appears, the next option click silently no-ops and the quest-accept never
  registers (everything downstream then runs pointlessly).
- `cooks_assistant.yaml:166-172, 213-217, 231-236, 248-253` — milk/flour/
  turn-in steps carry no `has_item:`/`no_item:` verification at all.
**Fix:** one conversion pass across `routines/quests/*.yaml`: every drain →
`repeat_until: "no_dialogue"` + `max_iterations`; add the missing
`has_item:` gates listed above.

### M-8. Tutorial 02-05 systemic — blind fixed-count `KEY_PRESS Space` dialogue drains
`02_gielinor_guide.yaml:31-53, 69-85`; `03_survival_expert.yaml:51-67,
91-101`; `04_woodcutting_firemaking.yaml:21-43`; `05_cooking.yaml:27-49` all
hardcode 2-4 Space presses before the next real action, with no exhaustion
check. The corpus's own newer bridge file had to raise its blind count to 12
for one NPC — direct evidence these small hand-tuned counts are fragile.
Under-count ⇒ the next widget/object click is swallowed by the open modal.
**Fix:** generously-sized blind `repeat:` (over-pressing is inert) or
`repeat_until: "no_dialogue"` where DEFECT-6 inter-page misreport doesn't
bite (short exchanges).

### M-9. `routines/tutorial_island/05_cooking.yaml:16-19` — ambiguous "Door" as the very first step
Step 1 `INTERACT_OBJECT "Door Open"` with no preceding GOTO/pin; the
handoff from 04 doesn't enforce the assumed start tile, and the file's own
pitfall note (:97-101) confirms a WRONG exit door exists nearby ("leads to
complex maze area"). Exact §(i) "Rocks" pattern.
**Fix:** add GOTO + `location:` await pinning next to the cooking-building
door before step 1.

### M-10. `routines/tutorial_island/09_banking.yaml:67-72` — DEFECT-11 door, unprotected at the section boundary
Step 1 opens "Door" with no position pin, immediately after 08's ladder
climb — while the file's own header (:32-36) documents DEFECT-11
(action-blind door matching can lock onto the wrong/open door) and step 9
(:133-140) adds a pin for the *same* reason ("multiple doors nearby!").
**Fix:** mirror step 9's `GOTO` + `location:` await before step 1.

### M-11. `routines/tutorial_island/08_combat.yaml:158-174, 247-252` — unverified combat and a self-admitted unconfirmed gate coord
Steps 14/25 (`INTERACT_NPC "Giant_rat Attack"`) fire one attack action with
no completion signal; the following GOTOs can interrupt combat and waste the
kill. No Grammar-1 atom exists for "target dead" — use a several-second
`delay_after_ms` as a stopgap. Step 13's rat-cage gate carries a TODO
(:163-167) admitting its coordinate was never confirmed as a world position
and has no GOTO pin (the exit gate at 16-17 is pinned).
**Fix:** add post-attack delays; pin step 13 like steps 16-17 once the tile
is confirmed live.

### M-12. `routines/skilling/superheat_mining_guild.yaml:119-125` — unverified guild ladder descent
Step 7 (`Ladder Climb-down`) has only `delay_after_ms: 2000`; every sibling
file pins the resulting location. A slow transition feeds step 8's GOTO
(already broken per H-3) from an unverified position.
**Fix:** `await_condition: "location:3019,9737"` (the file's own
`mining_guild_underground` coords), `timeout_ms: 10000`.

### M-13. `routines/skilling/flour_milling.yaml:65-72` — `idle` await on a stationary interaction
Step 4 (`Hopper controls Operate`) awaits `idle`, but the player is already
stationary next to the controls, so it passes instantly without the operate
animation having run — nothing verifies the grind before climbing down. No
inventory signal exists (flour lands in the bin).
**Fix:** replace with a calibrated `delay_after_ms` of a few seconds.

### M-14. `routines/utility/death_escape.yaml:58-127` — blind Space-count paging through Death's dialogue
Steps 3/5/7/9/11 page with fixed `repeat:` counts (5/3/3/3/2) and no
exhaustion check; a documented workaround (CLICK_CONTINUE doesn't work in
this zone), but any change in Death's dialogue depth silently desyncs the
following `CLICK_DIALOGUE` topic picks. Known fragility to monitor, not a
mechanical fix today.

### M-15. `routines/tutorial_island/10_prayer_magic.yaml:431-437` — trailer comments teach the two broken patterns
Line 435 recommends `CLICK_DIALOGUE "<option>"` "works even when options[]
is empty" — contradicting the file's own fix at :321-324 (must use
CLICK_CHILD_WIDGET here). Line 436 recommends `CAST_SPELL_NPC Wind_Strike` —
contradicting pitfall #6 (:418-420) and steps 25a-25c (broken on this jar;
manual CLICK_WIDGET 14286859 + CLICK_NPC is the fix). Comments only, but
they invite a future editor to reintroduce both regressions.
**Fix:** delete/correct the two trailer lines.

### M-16. `routines/skilling/fishing_karamja_{lobster,harpoon}.yaml:~155-165` — deposit-box open unverified
Step 12 (`Bank_deposit_box Deposit`) relies on a 2.5s delay before step
13's `BANK_DEPOSIT_ITEM` (which does have a real await). A slow UI open
makes step 13 time out with the root cause misattributed. **Fix:** await a
deposit-interface signal or lengthen the delay.

---

## LOW — cosmetic, doc drift, or contained risks

- **L-1.** `routines/combat/chicken_killer_loop.yaml:19-20` — comment claims the GOTO
  "reuses the identical / same coordinates" as `chicken_killer_training.yaml`
  step 1, but they differ (3180,3288 vs 3235,3295 — two different chicken
  farms). Both work; the comment lies. Fix the comment.
- **L-2.** `routines/combat/chicken_killer_loop.yaml:54-55` — `stop_conditions:
  ["inventory_full"]` is effectively unreachable for `Chicken none N` (bones
  are buried, default loot is runes chickens don't drop), so the loop is in
  practice bounded only by `--loops`. Harmless belt-and-braces; document it.
- **L-3.** `routines/combat/hill_giants_loot.yaml:35` — step ids jump 1→3 (comment
  says "Step 2"). Legal (ids may be non-sequential) but confusing; renumber.
- **L-4.** `routines/skilling/mine_iron_ore.yaml:220-222` — dead `notes:` key
  nested inside `loop.outer` (validator only checks top-level `loop:` keys —
  see V-4). Harmless; move to the top-level notes block.
- **L-5.** `routines/skilling/cooking_lumbridge.yaml:20` — `config.cooked_food`
  defined but never referenced by any `${...}`. Dead value; remove or use.
- **L-6.** `routines/skilling/mining_falador_iron.yaml:72-76` — door open with
  no verification; masked by step 3's generous GOTO timeout.
- **L-7.** `routines/skilling/flour_milling.yaml:40-46` — first step interacts
  with nearest "Ladder", no start-position pin; `locations.mill_outside`
  defined but unused. Add an opening GOTO.
- **L-8.** `routines/skilling/fishing_karamja_{lobster,harpoon}.yaml` — ferry
  `INTERACT_NPC ... Travel` steps unverified (fixed 5s delay); masked by the
  next GOTO's real await, costs wall-clock only.
- **L-9.** `routines/tutorial_island/07_mining_smithing.yaml:285-293` — final
  gate-open has no local completion check; relies on 08's defensive GOTO
  (documented cross-file dependency). Note: the §(i) tin/copper "Rocks" fix
  was verified present and correct for BOTH ore pins (:96-112, :124-140).
- **L-10.** `routines/tutorial_island/08_combat.yaml:126-131, 139-143, 223-227,
  235-239` — redundant inventory-tab re-clicks before equips (obsoleted by
  the DEFECT-29 equip_item fix; harmless). `:64` `locations.exit_ladder`
  y=9526 vs step 27's actual 9525 — doc-only 1-tile drift.
- **L-11.** `routines/tutorial_island/06_quest_guide.yaml:22-32, 114-118, 125` —
  unpinned GOTO/door race, unpinned ladder, and a stale comment claiming
  await_condition/repeat_until "cause timeouts" (they don't — newer files use
  both successfully).
- **L-12.** `routines/tutorial_island/widget_reference.yaml:82` — reference file
  still teaches the raw-widget-ID continue pattern predating DEFECT-24's
  canonical CLICK_CONTINUE guidance; add a pointer note.
- **L-13.** `routines/utility/death_escape.yaml:45` — dead step-level
  `location: death_npc` key. Also note the file IS executable (12 real steps)
  despite the validator's `non_executable: true` — see V-2.
- **L-14.** `routines/common_actions.yaml` — correctly non-runnable snippet
  library; note there is NO include/import mechanism in this schema, so its
  patterns can only ever be hand-copied (an `include:` key would silently
  no-op).
- **L-15.** `routines/test/basic_test_routine.yaml`,
  `routines/generated/test_scorpion_attack_1769492259.yaml` — cosmetic dead
  keys only; generated stub is self-labeled "review before use". No action.
- **L-16.** `routines/tutorial_island/07_mining_smithing.yaml` steps 5/8 —
  `repeat_until: "has_item:<ore>"` is check-first: a `--start-step` resume
  with leftover ore silently skips mining. Inherent to the semantics; noted
  for operators.

---

## V — validator (`manny_tools.py`) defects surfaced by this triage

These are tool bugs, not routine bugs — listed because they distort triage.

- **V-1 (HIGH).** `manny_tools.py:2889-2895` — GOTO arg check rejects the
  legal optional 4th `exact` token. `GotoCommand.java:59-83` explicitly
  parses/strips trailing `"exact"` (DEFECT-23 opt-in exact arrival). Result:
  the ONLY "failing" file in the corpus,
  `tutorial_island/05_cooking_to_quest_guide.yaml` (7 steps, e.g. :52
  `args: "3073 3090 0 exact"`), is a false positive — the routine is
  correct and live-validated. **Fix:** accept `len(parts) in (3,4)` with the
  4th token constrained to `exact`.
- **V-2 (MED).** `manny_tools.py:2739-2740` — `_routine_is_non_executable`
  returns True on `"manual_steps" in routine` without checking whether a
  real `steps:` list coexists. `utility/death_escape.yaml` (12 real steps)
  is thereby mislabeled `non_executable: true`, inviting triage to write off
  the one genuinely runnable death-recovery routine. **Fix:** require
  `"steps" not in routine` too.
- **V-3 (LOW, known).** `manny_tools.py:2495` — `_KNOWN_MCP_TOOLS` omits
  `click_text`, which the engine dispatches fine (routine.py:1632-1636).
  Already documented in ROUTINE_SCHEMA.md §(g); no corpus file currently
  trips it.
- **V-4 (LOW).** Unknown-key linting doesn't descend into
  `loop.inner`/`loop.outer` (caught top-level `loop.notes` in two files but
  missed `loop.outer.notes` in `mine_iron_ore.yaml`). **Fix:** recurse the
  key check into the nested blocks.

---

## Clean files (manual review found nothing beyond validator output)

`combat/hill_giants_travel.yaml` (beyond M-5), `skilling/fishing_draynor.yaml`,
`skilling/superheat_steel_bars.yaml` (the reference-correct mine+superheat
file — its troubleshooting notes exposed H-3), `skilling/mine_iron_ore.yaml`
(beyond L-4), `tutorial_island/00_master.yaml` (chain list verified: all 11
files exist, order matches its documented 06-skip rationale),
`01_character_creation.yaml`, `01_experience_selection.yaml`,
`quests/restless_ghost.yaml` structure (door/ladder pins all correct),
`combat/chicken_killer_loop.yaml` structure (post-hardening; DEFECT-26
terminal-KILL_LOOP shape correct).

## Suggested fix order

1. H-1 (death recovery is a landmine), H-2/H-3 (silently useless grinds),
   H-6/H-7 (unmanaged combat), V-1/V-2 (validator lies distort everything else).
2. The two systemic dialogue passes: M-7 (quests) and M-8 (tutorial), which
   also close H-8..H-12.
3. H-13..H-15 tutorial status/DEFECT-24 cleanup, then the MED awaits/pins.
