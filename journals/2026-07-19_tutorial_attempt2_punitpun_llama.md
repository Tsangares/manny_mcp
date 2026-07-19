# 2026-07-19 — Tutorial Island attempt #2: `punitpun` on llama — the fix-loop honesty gate WORKS, but the ladder is a game-side tutorial desync no routine can clear

**Author:** live supervisor agent (overseer-tutorial umbrella). **Account:** `punitpun`,
display auto-allocated `:4` on llama (hosts.yaml maps it to `:5`; the `run` path allocated
`:4` — see lesson below). **Jar:** shaded sha `b2b7a92a…` (sha-pinned in config.yaml).
**Run:** `20260719T204118Z_punitpun`, T0 20:41:17Z, harvested ~20:59Z (~19 live minutes).
**Outcome:** mainland NOT reached; could not descend the Quest-Guide-house ladder. No ban
signals at any point (LOGGED_IN, `terminal_login_failure` false throughout, residential IP
96.39.231.108). The attempt's core question — did strict_steps + the varbit gate + the ladder
pin actually work — is answered decisively below.

## The three core-question verdicts (this is the headline)

1. **`strict_steps` WORKS — honest failure achieved.** The 05b resume ran and reported
   `Status: FAILED` with `Step 12b (INTERACT_NPC): failed`. In attempt #1 the *identical*
   ladder situation exited runner-status SUCCESS and let the chain march into 42 blind minutes.
   Now the section fails honestly and the chain would stop. This is the single most important
   fix and it is confirmed live. Keep it.

2. **The varbit tutorial-progress gate is INERT — namespace bug makes it permanently 0.** The
   state export now carries `tutorial.progress` (the Java export landed with the new jar), but
   it reads **0** on-island at every poll while the player is unambiguously mid-tutorial. Root
   cause (overseer-confirmed): Tutorial Island's counter is **VarPlayer 281**, but the shipped
   Java calls `client.getVarbitValue(281)` — wrong namespace → permanent 0. Consequence for the
   chain: `run_chain`'s stage-gate is `if progress >= gate: skip`. With progress stuck at 0,
   `0 >= gate` is false for every gate, so **nothing is ever skipped**. This is not merely
   "gating doesn't help" — it is an active hazard: **running `00_master.yaml` this attempt would
   NOT skip 01–05b, it would start at section 01 (character creation) on an already-created
   mid-island character** and fail there. The master chain is UNSAFE until the varp read is
   fixed. The one-line fix is `getVarpValue(281)` (or `VarPlayer`), then progress reads true and
   the gate skips correctly. **Verified the gate fails safe otherwise** (unreadable → don't skip),
   so it never *wrongly* skips — it just never *helpfully* skips at 0.

3. **The ladder position pin (step 12d `GOTO 3088 3119 0 exact`) does NOT work — and the real
   blocker is deeper than geometry.** Two layered problems:
   - **Geometry (fixable, but the pin targets the wrong tile):** the ladder object is at
     (3088,3119) with `BLOCK_MOVEMENT_FULL` — you cannot stand on it, and 12d pins the player
     *onto* it. The only walkable tile adjacent to the ladder is **(3088,3120)** (directly
     north, inside the house). All other neighbours are walls (collision-verified). The player
     had been ejected *outside* the house's south wall at (3088,3118) — the same
     stood-outside-the-wall failure as attempt #1 #4. I manually routed the player around the
     house → through the north door (3086,3126) → to (3088,3120), the perfect tile.
   - **Game-side tutorial desync (NOT fixable by routine/nav):** even from (3088,3120), with the
     correct `Climb-down` menu option clicked (plugin log-verified: "Location (3088,3119)
     clicked", "[MENU-VERIFY] ✓"), OSRS itself returns **"I can't reach that!"** and the player
     does not descend. Talking to the Quest Guide opens **no dialogue** (exhausted). So the
     account sits in an inconsistent tutorial state: the Quest-Guide conversation registers as
     complete, but the ladder-descent trigger never armed. The ladder is tutorial-*gated/disabled*
     game-side — and we can't read the true varp to prove the stage because of bug #2. This is
     the attempt-#1 section-06 desync lineage, now cornered: **the parked account is
     unrecoverable at the Quest-Guide→ladder handoff.**

## Secondary defects found (all live-confirmed)

- **`GOTO` default tolerance is ~3 tiles and reports "Already at …":** `GOTO 3086 3121 0`
  returned `"Already at (3086,3121) - distance: 3 tiles"` and did **not** move the player. Any
  routine relying on plain `GOTO` for a precise tile silently under-shoots by up to 3 tiles. The
  `exact` keyword is mandatory for tile-precise placement (12d already uses it — good — but the
  gate-opener legs don't). This tolerance would defeat even a *corrected* ladder pin unless
  `exact` is used.
- **`GOTO … exact` blocks longer than the 10s command-response window:** a legit around-the-house
  walk returned `timeout No response received within 10000ms` yet the player *did* arrive
  (verified by re-reading state after). Supervisors must treat a GOTO-exact "timeout" as
  "check state" not "failed" — the plugin response window is shorter than a multi-tile walk.
- **Premature "Client crash detected (attempt 1/3)" fired on first boot again** (unchanged from
  attempt #1 #6). BUT the fix-3 kill-then-spawn held: only **one** java process existed the whole
  run (verified repeatedly) — no double-client, no IPC poisoning. The crash-detect false-fire is
  cosmetic now, but it did inject an `Auto-restarted client (attempt 1)` error into the ledger
  and likely disrupted step 12b's first execution.
- **`mannyctl run` allocates a display independent of hosts.yaml:** hosts.yaml maps punitpun→`:5`
  on llama, but the client launched on `:4` (Xvfb :4 was already up; the run path took it).
  Screenshots must resolve the *actual* `DISPLAY` from the client process environ
  (`/proc/<pid>/environ`), not trust the hosts.yaml mapping.

## Debugging technique that cracked the ladder (reusable)

`DUMP_COLLISION` → parse `/tmp/manny_<acct>_collision.json` (a 104×104 flag grid, index
`flags[worldX - scene_base.x][worldY - scene_base.y]`, `16777215`=void, `0x2/0x8/0x20/0x80`=
N/E/S/W movement blocks, `0x100`=full-block object). This turned "I can't reach that!" from a
mystery into a proof: the player was walled off (N-block on his tile), the ladder tile is
full-blocked, and (3088,3120) is the sole legal approach. Pair it with `QUERY_TRANSITIONS`
(doors/ladders/stairs with state+direction) and `SCAN_TILEOBJECTS <name>`. Note the correct
command names: `SCAN_TILEOBJECTS` (not SCAN_TILE_OBJECTS), `QUERY_NPCS` (not QUERY_NEARBY),
`CLICK_CONTINUE` (not CONTINUE/GET_DIALOGUE), `CLIMB_LADDER_DOWN` exists but is also game-rejected
here (same tutorial gate).

## What this means for attempt #3 (recommended next fixes, ranked)

1. **Fix the varp read first (Java, one line): `getVarpValue(281)`.** Until this lands, (a) the
   `tutorial.progress` field is worse than useless — it's a 0 that makes the master chain unsafe,
   and (b) nobody can distinguish "ladder desynced" from "ladder just needs one more dialogue."
   This single fix unblocks both the gate and the diagnosis.
2. **Do not attempt to salvage this parked `punitpun`.** It is desynced at the Quest-Guide→ladder
   handoff with no dialogue path forward and no routine/nav lever left. Start attempt #3 on a
   **fresh account** and run the chain from **01** — the whole point of the varp gate is that a
   fresh run needs no resume surgery. (This also means the 07–10 / DEFECT-29-equip first-contact
   data remains unobtained; it is gated behind a clean descent, which needs a clean account.)
3. **Re-pin the ladder to the interior tile:** step 12d should seat the player at **(3088,3120)
   `exact`** (north of the ladder, inside), not (3088,3119) (the ladder tile itself). And the
   approach must come from *inside* the house — the routine needs the door-open + interior-entry
   legs, because a straight `GOTO` to the ladder from the quest-guide-talk position ejects the
   player outside the south wall. On a correctly-synced fresh account this pin should then let
   `INTERACT_OBJECT Ladder Climb-down` succeed (the game gate will be armed).
4. **Make plain `GOTO` default to tight tolerance (or forbid non-`exact` GOTO in tutorial
   routines):** the 3-tile "already at" default is a silent mis-placement trap.

## What went RIGHT (do not lose)

- strict_steps honest-fail (verdict #1) — the fix loop's #1 goal, confirmed.
- kill-then-spawn held: single client all run, no double-client despite the premature crash-fire.
- Credentials guard caught the Bolt reset again (`default: new` → fixed to `punitpun`, banned
  guards ensured, rsynced byte-identical to llama).
- Jar sha gate: config sha-pinned `b2b7a92a…`, launch would refuse a mismatch. Provisioning is
  now host-correct (java_path `/usr/bin/java`, no stale-jar fallback).
- No ban signals, no thermal issues (loadavg ~0), clean account-scoped stop.

## Artifacts

Supervisor scratchpad `attempt2/`: `ledger_20260719T204118Z_punitpun.json`, `hv_runner.log`,
`hv_client_tail.log` (300 lines incl. the log-verified ladder click), `hv_collision.json`,
`hv_state.json`, `hv_lochist.json`, and 4 screenshots (`01_early_ladder` … `04_final_ladder_block`
showing the quest tab open + hint arrow on the ladder + "I can't reach that!"). Metrics rows
appended to `journals/metrics_first_contact.csv` (05b_ladder_resume=F reach-fail-ladder-
tutorial-desync; 07–10 = NR not-reached-ladder-blocked).
