# Tutorial attempt #4 (fishibis2800/llama :6, NEW jar d0668f58) — sections 1-5 PASS clean on the new menu-matcher; 05b cook-exit FAILS again on a FRESH run, and this time the root cause is precisely isolated: the master-chain GATE-SKIPS "Section 5: Cooking" (progress ≥120 reached in sections 3-4), leaving the player OUTSIDE the cook building that 05b's exit sequence assumes it starts INSIDE — so the ladder (and s08) are still not reached

**Date:** 2026-07-19. **Author:** live supervisor agent (attempt #4).
**Account:** `fishibis2800` (fresh, first automation run), display `:6` on llama.
**Jar:** shaded sha `d0668f58…` (NEW — menu-matcher fix + BACKSPACE/DELETE keys; deployed this window, sha-pinned in llama config.yaml, old `fa059e23…` kept on-host as `.rollback-fa059e23`).
**Run:** `20260719T231115Z_fishibis2800`. **Nav:** `-Dmanny.navBackend=shadow` ON (log-only).
**Outcome:** mainland NOT reached; **ladder-descent question STILL UNANSWERED** — blocked at 05b, upstream, by a now-precisely-identified gate/positioning structural gap. No ban signals at any point (home residential IP 96.39.231.108, no proxy). No freezes (state file always fresh).

## Headline verdicts (the three the run was launched to settle)

1. **VERDICT 1 — 05b cook-exit, fresh in-corpus: FAIL.** New root-cause isolation (this was murky
   across #3/#3b): the master chain **gate-skipped "Section 5: Cooking"**
   (`~ skipping tutorial_progress 120 >= gate 120, section already complete`) because progress
   reached 120 in sections 3-4 (Survival Expert cook-shrimp + Woodcutting/Firemaking) **before** the
   standalone Cooking section ran. But `05_cooking_to_quest_guide.yaml` (05b) assumes the player is
   **INSIDE the cook building**, fresh from the cooking step, and exits WEST through the cook door up
   the x=3072 corridor. With Cooking skipped, the player is **OUTSIDE** the building. A `:6`
   framebuffer screenshot (kept in supervisor scratchpad, NOT committed — exposes the host residential
   IP, stripped per journaling rules) shows the player on the exterior grass by
   the checkered-roof cook building with the game modal **"I can't reach that!"** (DEFECT-31 class).
   05b's westward GOTOs then fail — `[NAV-DIRECT] smartMinimapClick failed … Stuck`, 4-5 tiles short
   — the minimap follower cannot cross the cook-compound fence/door from the wrong side. The player
   drifted to **(3078,3097)** — the exact walled pocket attempt #3 died in.
   - **This is NOT the exact-mode regression** (that revert, commit 070d159, is re-confirmed WORKING:
     step-1 plain `GOTO 3073 3090` accepted the 3-tile undershoot to (3076,3088) fine, and the later
     quest-guide-approach `GOTO 3080 3120` also ran in plain mode — "Exact-arrival mode: false").
   - It is a **structural GATE/POSITIONING MISMATCH**. The "fresh in-corpus from inside the building"
     precondition that verdicts 2-3 depend on is **not achievable via 00_master as currently gated** —
     the very section that would position the player inside (Cooking) is the one the gate skips.

2. **VERDICT 2 — THE LADDER DESCENT: STILL UNANSWERED (not reached).** Blocked at 05b again, ~1
   section upstream. But unlike #3 (blamed on exact-mode) and #3b (blamed on resume-from-exterior),
   attempt #4 pins the blocker cleanly on the cooking gate-skip. The campaign's blocking question is
   unchanged in status but the obstacle to reaching it is now precisely characterized.

3. **VERDICT 3 — s08 sword/shield/bow equips (DEFECT-29): STILL UNMEASURED (not reached).** Same
   upstream block. The full equip sequence remains untested on a fresh account.

## What went RIGHT — the NEW jar's menu-matcher is healthy (matcher soak PASS)

The new jar's headline change (menu-matcher: colour-strips OPTION text + gated association-fallback +
unconditional `[MENU-MATCH]` logging) was live-soaked through sections 1-5 and shows **no regression**:
- **51 `[MENU-MATCH]` lines**: **17 `match=true via strict`**, **34 `match=false via none`** (correct
  rejects, e.g. 'Cancel'/'Walk here' vs 'Open'), **0 uses of the association-fallback** path — the new
  fallback never even had to fire in early sections.
- The cook-exit **Door `Open` INTERACT itself SUCCEEDED** (`entryOption='Open' entryTarget='Door' …
  match=true via strict`). The 05b failure is nav-traversal, not menu-match. NPC/GameObject/widget
  clicks behaved correctly across char-creation, exp-select, Gielinor Guide, Survival Expert,
  Woodcutting/Firemaking. **No matcher regression observed** — the CAVEAT in the deploy brief did not
  materialize; early sections were a clean matcher soak.
- BACKSPACE/DELETE keys: not exercised by the tutorial corpus (no defect surface this run).

**Sections 1-5 first-contact: PASS on the new jar** (char-creation, exp-select, Gielinor Guide,
Survival Expert, Woodcutting/Firemaking; cooking drove progress to 130).

## Nav shadow soak (for the stage-2 cutover evidence)

Shadow was ON (client_remote.sh default `NAV_BACKEND=shadow`, and I also added
`-Dmanny.navBackend=shadow` to llama config.yaml's `runelite_args` for the run-path launcher).
Harvest: ~11+ `[NAV-SHADOW]` lines. The graph engine is healthy (graph=FOUND for most, steps 17-47,
all sub-500µs; a couple graph=NONE for targets across the fence, ~4-7ms). **But 0 door/stair
transport samples** (`transport=0(doors=0,stairs=0)` on every line) — the run never successfully
crossed a door/gate (blocked at 05b), so the door/stair transport evidence the stage-2 soak wants
still did not materialize. The follower's inability to cross the cook-compound door is precisely why.

## The operational lesson: `mannyctl <host> run` does NOT launch the client

**First run attempt FALSE-STARTED and died in <1 min at "Section 1".** `mannyctl llama run
00_master.yaml --account fishibis2800` alone does **not** start a client — `run_routine.py` only has a
crash-RESTART path (`_auto_restart_client`), which uses the **mcptools display-pool allocator (:2-:5)**,
and that pool was **exhausted with stale assignments from prior attempts** (aux:2, monkey:3,
punitpun:4, ifixifixit:5) and **never consults hosts.yaml's `fishibis2800→:6` map**. So section 1
"crashed" instantly: `No available displays. All 4 slots assigned`. **Not a jar/matcher problem.**

**FIX (the correct launch sequence): pre-start the client, THEN run.**
1. `mannyctl llama start fishibis2800` → `client_remote.sh` brings up Xvfb `:6` (hosts.yaml map),
   finds the new jar (the `.rollback-fa059e23` backup does NOT match `*shaded.jar` glob, so no
   ambiguity), launches with `navBackend=shadow`. Login took ~40s (just past client_remote.sh's
   cosmetic 30s `LOGGED_IN` wait — the "FAIL: no LOGGED_IN within 30s" print is a false alarm; the
   client logged in fine at +40s).
2. `mannyctl llama run 00_master.yaml --account fishibis2800` → drives the already-healthy client via
   the account-scoped `/tmp/manny_fishibis2800_*` IPC files; the pre-existing client passes the health
   check so no display-pool auto-restart fires.

**Reusable rule:** on any host where the mcptools display pool is stale/exhausted or the account maps
to a display outside :2-:5, you MUST `mannyctl <host> start <acct>` before `mannyctl <host> run`.
Relying on `run` to bring the client up silently fails on the display allocator. (This is also why the
watchdog's freeze-restart correctly uses `client_remote.sh`, not the mcptools manager.)

## Deploy record (new jar, this window)

- New jar `client-1.12.34-SNAPSHOT-shaded.jar` sha256 `d0668f58…` synced to llama
  `~/Desktop/runelite-client-libs/` via `mannyctl llama provision`; old `fa059e23…` preserved on-host
  as `client-1.12.34-SNAPSHOT-shaded.jar.rollback-fa059e23` (does not match the launcher's
  `*shaded.jar` glob, so it can never be picked up accidentally).
- Launch sha pin: `provision.sh` stamps the local jar's sha into the host `config.yaml`
  `runelite_jar_sha256`, verified at launch by `RuneLiteInstance.start()`
  (`mcptools/runelite_manager.py`) — refuses any other jar. Confirmed on llama: pin = `d0668f58…`.
- The 3 parked humanization paths (`mcptools/humanize.py`, `tests/test_humanize.py`,
  `mcptools/tools/routine.py`) were **git-stashed before provision and popped after**, so llama got a
  CLEAN `routine.py` (0 humanize refs, `humanize.py` absent) — no crash, no humanization activation.
  Local working tree restored (verified).
- Creds pushed to llama (`push-creds`, 600 perms, `default: punitpun`, `fishibis2800` present); every
  command passed `--account fishibis2800` explicitly.
- Confirmed on llama pre-run: 05b steps 1-8 PLAIN (only `exact` args are the ladder pins 3086,3120 &
  3088,3120); `strict_steps: true`; watchdog `freeze_detected` logic present; display map
  `fishibis2800→:6`.

## Defect / fix-loop items (report — no Java/YAML edits made live)

- **[NEW] Cooking gate vs 05b inside-building precondition mismatch (the attempt-#4 blocker).**
  `00_master` gate-skips "Section 5: Cooking" once `tutorial.progress ≥ 120`, but progress reaches 120
  in sections 3-4, and 05b (`05_cooking_to_quest_guide.yaml`) assumes the player is INSIDE the cook
  building (which the Cooking section would position). Result: on a fresh chain run, the player is
  OUTSIDE and 05b's cook-exit is unrunnable. **Fix directions (for the fix loop, pick one):** (a) raise
  05b's start to be position-independent — walk to the cook building's exterior→interior via the door
  from wherever the player is, rather than assuming an interior start; or (b) reconcile the Cooking
  skip-gate so the positioning step isn't skipped (e.g. gate 05b's entry on an INSIDE-the-building
  location check and route to the door first); or (c) make the master chain NOT skip the section that
  performs required positioning even when its progress-milestone is already met.
- **Minimap follower cannot traverse doors/gates from the exterior** (known gap, re-confirmed): the
  shadow-mode directional follower wall-sticks and the game prints "I can't reach that!" — stage-2
  transport-aware nav is the intended fix. This is the load-bearing case; the shadow soak still has 0
  door/stair transport samples precisely because of it.

## Terminal state / clean park

Chain ended **Status: FAILED, sections run 7/11** — `[OK]` 1-6 (char-creation, exp-select, Gielinor
Guide, Survival Expert, Woodcutting/Firemaking, and 05_cooking which was the gate-skipped section,
counted OK), **`[FAIL]` 7. Cooking to Quest Guide — 11 step error(s)**. `continue_on_error: False`
correctly aborted the chain at section 7 (07-10 never ran). ~29 min drive time (run started
23:11:17Z), ~30 min live (client login ~23:10:34Z).

**Ledger health:** login_index 10 / LOGGED_IN / `terminal_login_failure: false` throughout (no ban);
state_age always <6s (no freeze). One `crash` ledger event fired at boot — the known benign
obfuscated-gamepack NPE (`Cannot read field "am" because "xz.ch" is null`) — but was SURVIVED (single
java client alive + logged in + fresh state for the full 28 min); it is a crash-signature false-fire,
not an actual crash, consistent with prior attempts.

**Parked cleanly:** I let 05b run to exhaustion through its full nav-step sequence (~25 min; each of
~10 GOTO steps burning its 60s timeout while the player was physically trapped in the (3078,3097)
pocket with no possible path to the Quest Guide/ladder), confirming deterministic strict_steps
honest-fail, then stopped via `mannyctl llama stop fishibis2800` (SIGTERM pid 876454). Verified: java
gone, run_routine + watchdog both exited, chain printed its terminal FAILED block. fishibis2800 logged
out. No `pkill java`, no proxy, no Java/YAML edits.

## Metrics
Rows appended to `journals/metrics_first_contact.csv` (attempt #4, run
`20260719T231115Z_fishibis2800`).
</content>
</invoke>
