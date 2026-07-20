# Tutorial attempt #5 (karldakilla / llama :7, jar d0668f58) — the cooking gate-skip killer is DEAD: cooking RAN and completed on a fresh account, and for the FIRST TIME a healthy fresh run reached THE LADDER and clicked Climb-down. It did not descend — but the blocker is now two clean layers deeper than #3/#4, and both are precisely characterized

**Date:** 2026-07-19. **Author:** live supervisor agent (attempt #5).
**Account:** `karldakilla` (fresh, first automation run), display `:7` on llama, home residential IP.
**Jar:** shaded sha `d0668f58…` (same as #4; matcher stayed clean). **Nav:** `-Dmanny.navBackend=shadow` (log-only, via `client_remote.sh` `NAV_BACKEND` default).
**Run:** `20260719T234922Z_karldakilla`. **Chain:** `Status FAILED, 7/11`. **Live:** ~31 min (login 23:48:51Z → stop ~00:20Z; drive 23:49:24Z → 00:18:26Z). No ban, no freeze, run+watchdog exited clean, ledger `status=completed` / `terminal_login_failure=None`.

## The headline: the gate fix (commit 31504fb) WORKS. The #3/#4 killer is retired.

`[OK] 6. Tutorial Island - Cooking` in the terminal chain block. This is the single most important line of the run. On a FRESH account, the master chain did **NOT** gate-skip the Master Chef cooking section:

- `tut_progress` climbed **120 → 200**, passing the Master Chef exit gate (170). That value is *only* reachable by executing the cooking section; a wrong gate-skip would have left progress ~130.
- Client log proves the physical cook: `16:52:40 [INTERACT-NPC] ✓ clicked 'Master Chef' Talk-to`; `16:52:54 USE_ITEM_ON_OBJECT dough Range` → `Successfully used dough on Range` (baking bread).
- NO skip line anywhere (attempt #4's `skipping tutorial_progress 120 >= gate 120, section already complete` is ABSENT).

So the section-04 gate 80→120 and section-05 Cooking gate 120→170 corrections did exactly what they were designed to do: cooking ran, positioned the player INSIDE the Master Chef kitchen, and 5b's cook-exit began FROM INSIDE as designed. **Sections 1-6 first-contact PASS on a fresh account.** No matcher regression (the d0668f58 menu-matcher stayed healthy — strict matches throughout, incl. the Door `Open` and the Ladder `Climb-down`).

## What newly blocked us — TWO stacked root causes, both upstream of the descent

Attempt #5 is the first run where cooking ran on a fresh chain, so it is the first to expose what lies *beyond* the gate-skip. Two real defects, in sequence:

### Root cause 1 — the COOK-EXIT DOOR nav stall (legacy follower door-traversal gap)

After cooking, 5b step 1 (`GOTO 3073 3090`) landed the player near the cook door; step 2 (`INTERACT_OBJECT Door Open`) **succeeded** (`16:53:17 Successfully performed Open on Door`). Then the **legacy minimap follower wedged for ~16 minutes** at `(3074,3091)` — 2 tiles EAST of the `x=3072` northward corridor. Every northward `GOTO` (3072,3096 / 3106 / 3112 / 3080,3120) failed with:

```
[WAYPOINT-WAIT] Gates found: Door (WallObject) at (3072,3090) dist=2.0
[NAV-LOOKAHEAD] Player didn't move after minimap click (stuck at 3074, 3091) - path blocked by wall/obstacle
[GOTO] Navigation failed - stuck or timeout: ended at (3074,3091,0)
```

This is the **known follower door/gate-traversal gap (DEFECT-19 class)** — the same wall-stick that ended #3/#4, but this time reached from the *correct* (inside-exit) side. The door was open; the greedy minimap follower simply cannot thread it northward and drifts into the compound corner. It is NOT the exact-mode regression (the revert holds: all the failing corridor GOTOs logged `Exact-arrival mode: false`), and NOT the gate-skip.

**Strong stage-2 cutover signal (harvest this):** 17 of 20 `[NAV-SHADOW]` lines report `graph=FOUND` (steps 20/27/57, sub-1.1ms) for *exactly* the crossings the legacy follower failed — e.g. `from=(3074,3091,0) to=(3072,3112,0) graph=FOUND steps=27 walk=27 … legacy=api/globalAStar`. The graph route exists; only the legacy follower (which drives in shadow mode) can't execute it. This is the cleanest live evidence yet that the stage-2 transport-aware follower would clear this leg. **Transport samples remain 0** (`transport=0(doors=0,stairs=0)` on every line): the door + ladder are `INTERACT`s, and the graph routes walk-only *around* obstacles rather than through them as transports — so the door/stair transport soak the stage-2 gate wants STILL did not materialize. The follower's inability to actually cross is precisely why.

### Root cause 2 — QUEST-GUIDE ARM SEQUENCING DESYNC (why the ladder didn't descend even after we reached it)

This is the new, subtle one. 5b arms the ladder by talking to the Quest Guide (varp 230→240→250) *before* the ladder-seat GOTOs. But those arm steps fire on a **fixed sequence**, not on proximity to the guide. The 16-minute door stall pushed the `INTERACT_NPC Quest_Guide Talk-to` steps to fire **4× at 17:08–17:10 while the player was still wedged 30 tiles south** at the cook door — all failed `Failed to find 'Quest Guide' within 15 tiles`. The arming was spent on empty air.

Then — notably — the later **ladder-seat exact GOTOs** (`3086 3120 exact`, `3088 3120 exact`) *did* finally deliver the player north to the ladder (they crossed where the plain corridor GOTOs had wedged — the exact stepper's short single-tile hops, and/or a door cycle, got through after the follower had drifted). So:

- **THE LADDER WAS PHYSICALLY REACHED — first ever.** Final position `(3088,3118)`, 1 tile from the ladder at `(3088,3119)`.
- **The `Ladder Climb-down` primitive is HEALTHY.** `[MENU-MATCH] entryOption='Climb-down' entryTarget='Ladder' … match=true via strict`, `[MENU-VERIFY] ✓`, `Successfully performed Climb-down on Ladder` — clicked cleanly 3×.
- **But the player never descended:** stayed `plane 0`, `progress 200`. The ladder was **UN-ARMED** — a *silent* no-op (no modal at all; DEFECT-31's modal export had nothing to catch because the game emits no message for an unarmed-ladder click). Descent → progress 250 never happened.

## Verdicts (the five this run was launched to settle)

1. **Cooking actually RUNS on a fresh account — ✅ PASS.** Gate fix proven. `[OK] 6. Cooking`, progress 120→200, physical cook logged. The killer of #3/#4 is retired.
2. **05b cook-exit from inside — PARTIAL.** Cooking positioned the player inside and the cook door opened; but the follower stalled 16 min crossing it northward (root cause 1). The section eventually delivered the player to the ladder via the exact seat-GOTOs, so it is no longer a hard "trapped in a pocket" — it's a slow, non-deterministic crawl that desyncs the arming.
3. **THE LADDER — REACHED, did NOT descend.** varp never reached 230/240/250 (arming missed). Seat `(3088,3120)` exact reached to within 1 tile. Climb-down primitive healthy but no-opped on an un-armed ladder. First healthy fresh account to physically stand at the ladder and click it.
4. **s08 equips (DEFECT-29 full test) — NOT REACHED.** Chain aborted at 7.
5. **Mainland (varp 1000) — NOT REACHED.**

## Fix directions for the loop (report-only; no Java/YAML edits made live)

- **[Primary] Root cause 1 — cook-exit door traversal.** This is the load-bearing blocker and the stage-2 nav's exact purpose. The shadow graph already FINDS the route (17/20 `graph=FOUND`); the gate to cut the legacy follower over on this leg is the follower's inability to execute door crossings. This single fix would remove the 16-min stall, which in turn removes the sequencing desync (root cause 2) for free.
- **[Secondary] Root cause 2 — arm-step sequencing.** Independently of nav, make 5b's `Quest_Guide Talk-to` arm steps robust to a slow approach: gate them on being within interaction range of the guide (retry-until-in-range), or re-order so arming is confirmed (dialogue opened / varp advanced) *after* the player is verified at the guide, not on a blind fixed sequence. As written, any upstream slowness silently burns the arming and strands a physically-arrived player at a dead ladder.
- **[Data] Door/stair transport samples still 0.** The stage-2 transport soak needs a real door/stair *crossing* logged as a transport; INTERACT-driven door/ladder use plus walk-only graph routing never produces one. Consider whether the shadow harness should also sample the INTERACT-crossing path, or the soak must wait for the transport-aware follower to actually traverse.

## Operational notes (confirming / extending #4's lessons)

- **Launch sequence held:** `mannyctl llama start karldakilla` (client_remote.sh, Xvfb :7, jar d0668f58, `navBackend=shadow`; clean login 21s) → `mannyctl llama run … --account karldakilla` (drove the pre-existing healthy client; no display-pool auto-restart). The #4 "run does not launch a client" rule is correct and necessary.
- **Provision discipline held:** stashed the 3 parked humanize paths (`mcptools/humanize.py`, `tests/test_humanize.py`, `mcptools/tools/routine.py`) → `provision` → pop. Verified on-host post-provision: routine.py 0 humanize refs, humanize.py absent, gates 120/170/250, jar sha pin d0668f58, 05b corridor GOTOs plain + only ladder pins exact. Local tree restored.
- **config.yaml `runelite_args` is a red herring for shadow mode on this path.** `provision` rewrites the host `config.yaml` (java_path/jar/sha/root) and the repo rsync resets `runelite_args` to `[]`, wiping #4's hand-added `-Dmanny.navBackend=shadow`. It does not matter: `client_remote.sh` does NOT read `runelite_args`; it applies shadow via `NAV_BACKEND="${NAV_BACKEND:-shadow}"` → `-Dmanny.navBackend="$NAV_BACKEND"` at launch (verified in the launch log: `navBackend=shadow`). Shadow is guaranteed for both `start` and watchdog-restart regardless of config.yaml. Do not bother re-adding the flag; verify shadow from the launch log line instead.
- **pgrep self-match trap (cost me two false "STILL ALIVE" readings at park).** `pgrep -f 'manny.navBackend'` matches the *checking* shell's own command line (which contains that literal). Confirm the client is dead with `ps -eo pid,comm,args | grep -w java | grep shaded` (comm=java), never a pattern your own command contains. The client was in fact cleanly dead after the first `mannyctl llama stop`.

## Terminal state / clean park
`mannyctl llama stop karldakilla` (SIGTERM pid 880718). Verified: no java-on-shaded-jar process, run + watchdog exited, chain printed its `Status FAILED, 7/11` block. karldakilla logged out. No `pkill java`, no proxy, no Java/YAML edits. Parked accounts (ifixifixit, fishibis2800, punitpun) untouched. Metrics rows appended to `journals/metrics_first_contact.csv`.
