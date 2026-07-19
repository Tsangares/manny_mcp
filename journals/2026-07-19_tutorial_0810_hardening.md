# 2026-07-19 — Tutorial Island 08–10 hardening (why the back third never cleared hands-free)

**Type:** lesson for future agents + pre-live checklist. **Scope:** offline only — audited and
hardened `08_combat`, `09_banking`, `10_prayer_magic` via dry-run + schema/journal cross-reference;
**no live client, no Java, no deploy.** Three parallel audit passes then three parallel apply passes,
each fix verified against `mcptools/tools/routine.py` before applying. All three re-dry-run green
(28 / 10 / 38 steps, 0 failures). Corpus is hands-free-proven through §07; §08–10 were the untested
stretch and are where `blast` parked (§08, 3111,9525, dagger unequipped).

## The three root-cause patterns (these recur across all three sections)

1. **DEFECT-31 modal no-op.** The tutorial's blocking modals ("I can't reach that!", "you'll be told
   how to equip later") render with `dialogue.open:false`. So a `repeat_until: no_dialogue` step is
   *already satisfied* and — because `repeat_until` is check-first — presses Space **zero** times,
   leaving a movement-blocking modal up. The very step meant to clear the modal cannot. This is the
   original "40-minute saga" mechanism. **Fix: blind `repeat: N` instead of `repeat_until:no_dialogue`.**
2. **Silent march-on past a failed precondition.** `on_failure` defaults to `continue`, so a failed
   equip / unheld kill / missed climb logs an error and marches into dependent steps, reporting
   per-step success upstream. On a gated tutorial this strands the run while looking green. **Fix:
   `on_failure: abort` (or `retry:N`) on precondition steps** — converts a silent cascade into an
   honest stop the overseer/watchdog can catch.
3. **Tolerant GOTO can't line up on hard doors.** A `location:X,Y` await has ~3-tile Chebyshev
   tolerance, so the player satisfies it while stopped short of a closed door; the follow-up
   `INTERACT_OBJECT Door Open` then hits the DEFECT-11 no-lineup condition. **Fix: `GOTO … exact`
   (DEFECT-23) so the player lands on the tile adjacent to the door.**

Note on dry-run: all three sections dry-run **PASS** both before and after these fixes. The simulator
assumes NPC-reach / widget-hit / dialogue-close postconditions, so it is **blind to every failure
mode above** (ROUTINE_SCHEMA k.1). A green dry-run here means "no schema-mechanical bug," not "safe."

## APPLIED this session (verified-safe, no live coords needed — commit below)

All keys verified present in `routine.py`: `on_failure` (`abort`/`retry:N`/`continue`),
`delay_after_ms` (1927), bare `repeat` (1664), `repeat_until_timeout_ms` (1755), step-level
`max_iterations` (1750; distinct from the dead `loop.max_iterations`), `GOTO … exact` (DEFECT-23).

**08_combat.yaml** (+22): steps 15/26 `repeat_until:no_dialogue` → blind `repeat:3`+`delay_after_ms:500`
(DEFECT-31); steps 14/25 `delay_after_ms:12000` (hold through the kill — no Grammar-1 "target dead"
atom); steps 5/9/11/22/24 `on_failure:"retry:2"` (DEFECT-29 residue: equip_item now returns honest
`success:false`, was being discarded); step 28 `delay_after_ms:3000`.

**09_banking.yaml** (+9): step 9 `GOTO "3124 3124 0" → "…exact"` (the closed Account-Guide door at
3125,3124 — journals say tolerant GOTO "could never line up on" it); step 2 `on_failure:abort`+
`timeout_ms:15000` (its `plane:0`-await successor is trivially true and masks a failed climb); step 3
`timeout_ms:15000`; steps 1/10 `delay_after_ms:1500`.

**10_prayer_magic.yaml** (+33): steps 12/15 Brother Brace (the pacing NPC that failed ~10× live)
`repeat:8`+`timeout_ms:5000`+`delay_before_ms:600`+`on_failure:abort` (repeat re-resolves his live
tile each attempt; abort stops a prayer-uncredited march into magic/mainland); new steps 25b2/25c2
re-select+re-cast Wind Strike (a miss clicks ground and DESELECTS the spell, so one `repeat` can't
recover); steps 27/30b `repeat_until_timeout_ms:4000` (+`max_iterations:20` on 30b) and new blind
step 30c `repeat:3` to outlast the DEFECT-6 inter-page dialogue gap and reach the teleport prompt.

## PRE-LIVE CHECKLIST — needs a live client to finish (NOT applied; do not guess coords)

- **08 RISK-1** step 13 entry gate: no world coord confirmed (live pass used a screen-pixel sweep).
  `scan_tile_objects("gate")`, pin an approach tile with `GOTO … exact` + a `location:` await.
- **08 RISK-2** step 28 climb: `await_condition: plane:0` is always-true (combat area is underground
  but already plane 0). Replace with the live-confirmed surface arrival tile.
- **08 RISK-3 / naming**: confirm `Gate`/`Ladder` case via `scan_tile_objects` (object names match
  lowercase, case-sensitive).
- **09 ISSUE-1** step 1 boundary door: add a `GOTO … exact` approach pin once the tile is live-confirmed.
- **10 RISK-3** steps 28/30 dialogue-child clicks (`CLICK_CHILD_WIDGET`): no encoded verify exists;
  monitor the option menu is seated before the click.
- **10 / jar-fragility**: the hardcoded widget IDs (`14286859` Wind Strike, `14286854` Home Teleport,
  `14352385` option parent, tab IDs) were live-discovered on a specific jar and can drift on a fresh
  jar — re-verify with `find_widget` on the run jar before trusting them.

## Verdict

None of §08/09/10 was hands-free-safe before this pass; each had ≥1 BLOCKER (DEFECT-31 modal, unheld
kill / unguarded equip, Brother Brace pacing). The applied fixes remove the *silent-failure* class
(now they abort honestly or retry) and encode the *known* modal/pacing/door workarounds. The
remaining risk is genuinely live-only (coords, jar-specific widget IDs, dialogue timing) and is
listed above for the first overseen punitpun run — which is where these get their real test. Single
most-likely live break points to watch: §08 steps 14→16 (kill→modal→GOTO), §09 steps 9→10 (the
closed door), §10 steps 12/15 (Brother Brace).
