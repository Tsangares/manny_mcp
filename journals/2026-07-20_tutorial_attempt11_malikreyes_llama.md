# Tutorial Island attempt #11 — malikreyes on llama :9 (hands-free measurement, continued)

**HAND-DRIVEN GAME ACTIONS: 0 (target 0).** The hands-free discipline held for the full run.

**Run:** `20260720T035248Z_malikreyes` · routine `routines/tutorial_island/00_master.yaml` ·
HEAD `db8db72` (anvil modal-drain + inner-loop redesign) · jar `d0668f58` (pinned, verified by
gate 4) · nav=shadow · duration ~6 min (03:52:49Z → 03:58:50Z) · launched via `mannyctl llama
window` — all 6 gates PASS (predecessor-dead, creds, display, provision, launch, run+watchdog).

**Outcome: db8db72 anvil fix PASSED clean, but the chain progressed further and honestly
aborted at a NEW gate — s08b's ranged-attack verify (step 28), varp stuck at 480.** This is the
furthest any attempt has gotten past the anvil: mining/smithing (s07), equip (s08a), and the
melee half of combat (s08b) all completed; only the ranged-kill leg failed. Per doctrine the
honest abort at strict_steps IS the successful measurement.

## Verdict on db8db72 (the anvil acceptance test): PASS

Client log receipts (`/tmp/runelite_malikreyes.log`, llama):
- `20:54:29 PDT` — `USE_ITEM_ON_OBJECT Bronze bar Anvil` → `Successfully used Bronze bar on
  Anvil` (20:54:31).
- `20:54:32 PDT` — Smith interface opened with option `"Smith" | Target: "Bronze dagger"`.
- By `20:55:38 PDT` the routine was already scanning inventory widgets and found `Wield` on
  Bronze dagger — i.e. the dagger was crafted and the routine moved on to s08a on the **first**
  pass through the inner loop; no repeated drain/anvil/dagger-click cycles were needed this run.

The mine/smelt-already-done replay from the parked progress=340 (Bronze bar + Hammer already in
inventory) chewed through the redundant "Nothing interesting happens" mesboxes via the blind
Space drains exactly as designed — no stuck loops observed.

## New defect surfaced: s08b ranged-attack step fires without repositioning

Progress climbed 340 → 470 → 480 fast (anvil, s08a equip, s08b melee leg all clean), then
plateaued at 480 for the remainder of the run. Section 8b's own final verdict:

```
[ROUTINE] Aborting run: Step 28 (WAIT) failed: failed
  ! section failed, stopping chain: Section 8b: Combat (sword/shield, melee, bow, ranged, exit)
Status: FAILED — Sections run: 10/13
  [OK ] 8. Tutorial Island - Mining & Smithing
  [OK ] 9. Tutorial Island - Combat (equipment interface + dagger)
  [FAIL] 10. Tutorial Island - Combat (sword/shield + ranged)  - 1 step error(s)
```

Root-cause chain, all receipt-backed:

1. **Equip was NOT the problem.** `player.equipment` in the live state JSON confirmed
   `weapon: Shortbow`, `ammo: Bronze arrow qty=50` — both correctly wielded before the attack
   (`routines/tutorial_island/08_combat_sword_ranged.yaml` steps 22-25 all succeeded; widget
   scans at 20:57:15/20 PDT found `Wield` on both items, and later state confirms they moved
   from inventory into equipment slots).
2. **The `INTERACT_NPC Giant_rat Attack` click (step 26) "succeeded" at the input level** —
   `Successfully performed Attack on Giant rat` logged at 20:57:25 PDT, menu-matcher found
   `Attack | Giant rat (level-3)` and clicked it — **but the player's location at that moment was
   (3104,9509)**, which is the `combat_area_entrance` / Combat Instructor's own tile per the
   routine's own `locations:`/`npcs:` blocks, **not** the fence-adjacent tile the step's comment
   assumes ("Stay outside the cage, attack through the fence"). The engine's own NPC search
   log shows the rat found at distances **13, 8, and 7 tiles** away.
3. **There is no GOTO step between the bow-handover dialogue (steps 19-21, which end back at
   Vannaka after re-entering/exiting the cage) and the ranged attack (step 26)** in
   `08_combat_sword_ranged.yaml`. The melee leg (steps 12-15) explicitly walks the player INTO
   the cage first; the ranged leg has no equivalent repositioning back to a valid attack tile —
   it just fires from wherever the dialogue left the player.
4. **Step 28** (`WAIT tutorial_progress:>=500`, 45s timeout, `on_failure: abort`) never saw the
   varp move past 480 and aborted honestly at strict_steps — no false-pass, no march-on.
5. This is the **same false-pass class** documented for attempt #10's anvil defect: a command
   reports success (click dispatched, menu option matched) while the actual game-side
   interaction (combat engagement / line-of-sight into the cage) never happened. The 45s WAIT
   plus `delay_after_ms: 12000` on step 26 gave ample time for a real kill if combat had actually
   started — it never did (no hitsplat/varp movement of any kind after the click).

## What the run proved (positives banked)

- `mannyctl window`: 6/6 gates PASS again, including internal parked-file stash/restore.
- Varp stage-skip gates: sections 1-6 skipped cleanly at progress 340; chain resumed exactly at
  s07 — fourth consecutive run this mechanism has worked.
- **db8db72 anvil redesign: PASS, no retries needed** — closes the s07 blocker that stopped
  attempts #9 and #10.
- s08a (equipment interface + dagger) and the melee half of s08b (sword/shield equip, cage
  entry, melee kill 420→470) both ran clean, hands-free, first try.
- strict_steps + WAIT-gate honesty held again: no false-pass cascade past the real fault.
- Known-benign boot NPE (`xz.ch is null`) appeared once during STARTING, as documented; no other
  client faults; no ban signals; account remained healthy 10/10 HP throughout.
- Post-run the client idle-logged-out on its own ("You were disconnected from the server",
  screenshot below) — this happened **after** the chain had already terminated (watchdog exit at
  03:58:50Z; screenshot taken ~04:03Z), so it is unrelated to the ranged-attack defect and did
  not require a relog since the run was already at its terminal state.

## Park state

- Account `malikreyes`: varp 281 = **480**, position (3104,9509,0) — combat area, at/near the
  Combat Instructor. Inventory + equipment: Shortbow and Bronze arrow (x50) equipped; Bronze
  dagger, Bronze sword, Wooden shield, Bronze pickaxe, Hammer, Tin/Copper ore, and the earlier
  s03-06 items all still in inventory. No ban signals, 10/10 HP.
- Client stopped via `mannyctl llama stop malikreyes` (SIGTERM pid 920967); watchdog and
  run_routine.py had already exited on their own (ledger `status: completed`, `run pid 921238
  gone` at 03:58:50Z). Verified **zero** java/python processes for the account on llama
  (`ps -eo pid,args` scan, not pgrep).

## Receipts index

- Ledger: `/tmp/manny_runs/20260720T035248Z_malikreyes.json` (llama)
- Run log: `/tmp/manny_run_malikreyes.log` (llama)
- Client log windows: `/tmp/runelite_malikreyes.log` lines ~779-820 (anvil/dagger), ~1706-2262
  (melee + ranged attack sequence) (llama)
- Screenshot: `journals/images/2026-07-20_malikreyes_s08b_ranged_kill_stall.png` (post-terminal
  idle-logout state, captured during park verification — not a mid-combat screenshot; the
  ranged-attack failure itself is evidenced by log timestamps + state JSON, not a screenshot)
- Metrics: `journals/metrics_first_contact.csv` rows dated 2026-07-20, run
  `20260720T035248Z_malikreyes` (07 P, 08a P, 08b F, 09/10 NR, TUTORIAL_COMPLETE NR,
  HANDS_FREE_RUN P)

## Open item handed to the desk

`08_combat_sword_ranged.yaml` step 26 needs a repositioning `GOTO` (to a fence-adjacent tile
with confirmed line-of-sight into the rat cage, analogous to the melee leg's cage-entry walk)
inserted between step 21 (bow/arrow handover verify) and step 26 (ranged attack) — and ideally a
ground-truth check (e.g. `combat.state` or a distance/LOS precondition) before trusting the
`INTERACT_NPC ... Attack` "success" response, since that response only confirms the client-side
click/menu-match, not that the game engine accepted the interaction. Until fixed, s08b's ranged
leg is the new terminal blocker for the tutorial chain; s09/s10 (banking, ladder pin, poll booth,
prayer, magic, wind strike, ironman/mainland menus, boat) remain unmeasured.
