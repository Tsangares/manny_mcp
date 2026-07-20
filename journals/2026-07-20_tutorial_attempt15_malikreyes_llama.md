# Tutorial attempt #15 — malikreyes/llama — CERTIFICATION retry

**Verdict: DEFECT HARVESTED, not certified this window — but the fix under
test is VALIDATED.** `1f91a80` (movement-close workaround for the still-
undeployed DEFECT-33 `isBankOpen()` false negative) worked exactly as
designed: the bank was closed by real movement, and the poll booth succeeded
on the first attempt for the first time in four consecutive attempts (#12–15).
Section `09_banking.yaml` (9a) passed cleanly end to end, varp 281 520 → 525.
The chain then advanced into `09_banking_to_account_guide.yaml` (9b) for the
first time ever (previously always unreached, NR, because 9a never passed)
and hit a **new, distinct defect**: the door-crossing through-walk step is a
plain `GOTO` whose target is only 2 tiles from the seat, which falls inside
`GotoCommand.java`'s own plain-mode no-op radius (`distance <= 3`) — the step
reported "success" without ever moving the player. The honest
`tutorial_progress:>=530` gate caught it and the chain stopped cleanly. Zero
hand-driven game actions were sent.

## Fix-under-test verdict

### 1f91a80 — close the bank by MOVEMENT (step 5a, exact GOTO to 3120,3121): **VALIDATED**

Client log receipt (`/tmp/runelite_malikreyes.log`, 22:25:34–22:25:43 PDT):

```
22:25:34 [BANK_CLOSE] Closing bank
22:25:34 BankingSupport - Attempting to close bank...
22:25:34 BankingSupport - Bank is already closed          <- DEFECT-33 oracle still lying, as expected (jar unchanged)
22:25:34 [BANK_CLOSE] Bank closed successfully              (no-op false pass, belt-and-suspenders per design)
22:25:35 Received command: GOTO 3120 3121 0 exact
22:25:36 [GOTO] Start: (3120, 3123, 0) -> Target: (3120, 3121, 0)
22:25:36 [GOTO] Distance: 2 tiles
22:25:38 [GOTO] Exact-arrival mode: true
22:25:40 [GOTO] Successfully reached target (exact tile)   <- REAL movement, position confirmed changed
22:25:40 [GOTO] Command succeeded
22:25:41 Received command: INTERACT_OBJECT Poll_booth Use
22:25:41 [INTERACT-OBJECT] Found TileObject 'Poll booth' as fd at WorldPoint(3119,3121,0)
22:25:42 [MENU-MATCH] entryOption='Use' entryTarget='Poll booth' vs option='Use' ... match=true via strict
22:25:43 [INTERACT-OBJECT] Successfully performed Use on Poll booth
22:25:43 Command executed successfully: INTERACT_OBJECT Poll_booth Use
```

Step 5's `BANK_CLOSE` behaved exactly as attempts #13/#14 diagnosed: DEFECT-33
(`isBankOpen()` false negative) is still live on jar `421c03e91ff9e82b` — it
reported "already closed" as a harmless no-op, per design (belt-and-suspenders,
becomes the honest close only once DEFECT-33 ships). The actual close was
delivered by step 5a: `GOTO 3120 3121 0 exact`, distance 2 tiles from the
bank-booth tile, exact mode forced real per-tile movement (does not no-op
below distance 3 the way plain mode does — only at distance 0, DEFECT-23) —
log confirms `Start: (3120,3123,0) -> Target: (3120,3121,0)` then
`Successfully reached target (exact tile)`. The very next command, the
poll-booth `INTERACT_OBJECT ... Use`, built a menu with `Use` offered (not the
`Cancel`-only degraded menu that killed attempts #13/#14 nine times total) and
**succeeded on the first attempt** — no retries needed. Poll credit registered
(varp 520 → 525, confirmed by the section-9a `[OK]` chain result and the
subsequent state poll).

**Conclusion: 1f91a80's movement-close hypothesis is proven correct on the
live client.** Walking away from the bank-booth tile does close the bank
interface as a game-engine side effect, independent of the lying
`isBankOpen()` oracle, and the (3120,3121) poll-booth seat is confirmed
walkable and in-range. This is the first clean pass of `09_banking.yaml`
across four consecutive live attempts (#12, #13, #14, #15).

### 7f6475d — absorbed transient failures in bounded inner retry loop: **NOT EXERCISED**
No `[LOOP] absorbed N transient failure(s)` line appeared in either log this
window. No bounded inner retry loop of that class was hit.

## NEW DEFECT — 09b door-crossing through-walk no-ops at distance 2 (DEFECT-7 class)

`09_banking_to_account_guide.yaml` ran live for the first time ever this
attempt (previously always `NR` because section 9a had never passed). Its
three action steps:

1. **Step 1** (`GOTO 3124 3124 0 exact`, seat) — PASS. Log:
   `[GOTO] Successfully reached target (exact tile)`, 22:25:59 PDT.
2. **Step 2** (`INTERACT_OBJECT Door Open 3125 3124`, coordinate-qualified) —
   PASS. Log: `[MENU-MATCH] INTERACT_OBJECT 'Door' resolved to TileObject
   nearest (3125,3124) as fl at (3125,3124) (dist 0) among 6 candidate(s)` →
   `✓ Successfully clicked fl 'Door' with action 'Open'`, 22:26:03 PDT. The
   coordinate qualifier correctly picked the right door among 6 candidates.
3. **Step 3** (`GOTO 3126 3124 0`, plain through-walk past the threshold) —
   **reported PASS but never moved the player.** Log, 22:26:03 PDT:
   ```
   [GOTO] Executing command
   [GOTO] Already at destination (distance: 2 tiles)
   [GOTO] Command succeeded
   ```
   This is the exact short-circuit this file's own header documents as
   **DEFECT-7** ("GOTO tolerance no-ops at distance <=3 tiles") and
   `GotoCommand.java:152`'s own logic
   (`distance == 0 || (!exact && distance <= 3)`): the seat (3124,3124) to the
   through-walk target (3126,3124) is only 2 tiles, so the plain-mode
   short-circuit fired with **no click issued and no movement** — the same
   defect class the door-crossing-v2 doctrine explicitly discusses (and
   correctly avoids by never using `exact` mode on the door tile), but the
   authors did not check the *plain*-mode distance against DEFECT-7's own
   no-op radius when picking `3126,3124` as the through-walk target — it is
   only 2 tiles from the seat, squarely inside the no-op zone.
4. **Step 4** (`WAIT tutorial_progress:>=530`) — honestly timed out at 15s;
   varp stayed at 525. `strict_steps: true` marked section 9b FAILED; chain
   stopped cleanly with `Aborting run: Step 4 (WAIT) failed: failed`.

**Player never crossed the threshold** — final position (3124,3124,0), the
step-1 seat tile, not (3126,3124) as the routine's own "after this routine"
note expects. The door itself DID open successfully (confirmed by the
`MENU-MATCH`/`✓ Successfully clicked` log lines); the failure is isolated to
the through-walk GOTO's no-op, not the door open, not object resolution, and
not the auto-close race the door-crossing-v2 doctrine was built to avoid.

Screenshot at the abort point (residential IP overlay redacted before saving
to this repo — see safety note below):
`journals/images/2026-07-20_malikreyes_attempt15_9b_door_nomove.png`. The chat
panel shows the standard poll-booth "Moving on... move on through the door
indicated" system text (persistent chat log entry, not a blocking modal —
`dialogue.open:false` confirmed by state poll at the same moment), consistent
with the honest-abort diagnosis above and ruling out a lingering-modal
explanation.

**Fix direction (not applied this window, per hands-off doctrine — do not fix
routines live):** either (a) change step 3's through-walk target to a tile
more than 3 Chebyshev tiles from the seat so plain GOTO's own movement click
fires, or (b) verify arrival via `await_condition` alone (already done) but
issue the through-walk as `exact` mode restricted to *not* the door tile
itself (per door-crossing-v2, exact mode is fine on non-door tiles) — e.g.
seat further back so the crossing distance exceeds 3, or add a Java-side
"force movement regardless of distance for door-crossing GOTOs" primitive
(mirrors the state-aware `GateAction` prior art already cited in
`MANNY_OVERSEER.md` §4 for the durable long-term fix).

## Timeline

- **~05:20Z** — Preflight: `git log --oneline -2` confirmed HEAD at `1f91a80`.
  `./run_routine.py --dry-run routines/tutorial_island/00_master.yaml` PASSED
  (53 steps simulated, RESULT: PASS, exit 0).
- **05:24:59Z (launch)** — `mannyctl llama window malikreyes
  routines/tutorial_island/00_master.yaml` — all 6 gates PASS:
  predecessor-dead, credentials (`default: punitpun`, malikreyes not banned),
  display `:9`, provision (stash/pop/verify clean, jar_sha=421c03e91ff9e82b),
  login gate (LOGGED_IN in 20s at (3120,3123,0), login_index 10 — matches the
  parked position exactly), run+watchdog detached
  (`run_id 20260720T052459Z_malikreyes`).
- **~05:25:01Z / 22:24:41 PDT** — client boot logs one benign
  `NullPointerException: Cannot read field "am" because "xz.ch" is null` at
  `client.getTopLevelInterfaceId` / `UITools$WidgetInspectorTool` during
  `Game State: STARTING` — identical signature to attempts #13/#14's known
  false-positive crash class (widget-tree debug panel racing client boot).
  Not a real crash; no intervention taken.
- **~05:25:01Z–05:25:20Z** — chain replayed sections 1–10 (character creation
  through `08_combat_sword_ranged`), all instantly skipped via the
  `tutorial_progress >= gate` resume logic (account parked at varp 520, past
  all 10 of those gates). Zero live commands sent for these.
- **~22:25:20–22:25:44 PDT** — section 11/13, `09_banking.yaml` ("Section 9a:
  Banking"), the only section with real replay work this window:
  - Ladder climb-down (coordinate-qualified) — PASS.
  - Step 4 (`Bank_booth Use`) — PASS (22:25:30–33 PDT).
  - Step 5 (`BANK_CLOSE`) — PASS but a harmless no-op ("Bank is already
    closed" — DEFECT-33 oracle unchanged, expected).
  - **Step 5a (`GOTO 3120 3121 0 exact`) — PASS, real movement confirmed** —
    the fix under test.
  - Step 6 (`Poll_booth Use`) — **PASS on first attempt** (no retries) — the
    fix's payoff, contrasted with attempts #13/#14's 9/9 Cancel-only fails.
  - Step 7 (space drain) / Step 8 (Escape) — PASS.
  - Step 9 (`WAIT tutorial_progress:>=525`) — PASS. Section 9a: **`[OK]`**.
- **~22:25:54–22:26:03 PDT** — section 12/13,
  `09_banking_to_account_guide.yaml` ("Section 9b"), first-ever live
  execution:
  - Step 1 (seat GOTO exact) — PASS.
  - Step 2 (door open, coordinate-qualified) — PASS.
  - Step 3 (through-walk plain GOTO) — **reported PASS, no movement** (DEFECT-7
    no-op at distance 2).
  - Step 4 (`WAIT tutorial_progress:>=530`) — **honest timeout, FAIL**.
  - `strict_steps: true` marked section 12 FAILED; chain stopped: `Aborting
    run: Step 4 (WAIT) failed: failed`.
- **~05:27:01Z** — watchdog observed run pid 938584 gone, marked run
  `status: completed` (the `run_routine.py` process exiting normally after
  the chain's own honest-abort logic — a clean process exit, not a crash or
  forced kill).
- **~05:27–05:30Z** — investigation: pulled the full command timeline from
  `/tmp/runelite_malikreyes.log` (BANK_CLOSE / GOTO / INTERACT_OBJECT
  context) and `/tmp/manny_run_malikreyes.log` (chain-level result).
  Screenshot captured via `DISPLAY=:9`, `import -window <RuneLite window id>`
  (xdotool window search failed under the wrapped remote shell, `scrot -o`
  fallback succeeded) — **the raw capture exposed the host's residential IP
  in an on-screen overlay**; it was redacted (black rectangle over the
  overlay region) with a local Pillow pass before being copied into this
  repo, per the standing safety rule never to commit a screenshot exposing a
  residential IP. The raw unredacted file was never staged.
- **~05:30Z** — `mannyctl llama stop malikreyes` — clean scoped SIGTERM stop
  (pid 938308).

## Final state
- varp-281 = **525** (up from the parked 520 — new furthest progress).
- Position: **(3124, 3124, 0)** — the section-9b door-threshold seat tile,
  never crossed.
- Account healthy, no ban signals, client cleanly stopped via scoped
  `mannyctl stop` (never `pkill java`).

## Hand-driven game actions: **0**
No clicks, walks, interactions, dialogue, or camera commands were sent by the
supervisor. All supervisor actions were infra-only: launch (`mannyctl
window`), read-only log/state polling via a background monitor script,
one passive screenshot capture (redacted before use), and the terminal stop.

## Open items / next fix direction
- **New defect (unnamed, DEFECT-7 instance):**
  `09_banking_to_account_guide.yaml` step 3's plain-mode through-walk target
  (3126,3124) is only 2 Chebyshev tiles from its own step-1 seat (3124,3124),
  inside `GotoCommand.java`'s plain-mode no-op radius (`distance <= 3`, same
  file `:152` cited by this very routine's own comments for a different step).
  The step reports success without moving the player, so the door is never
  actually crossed and the honest `tutorial_progress:>=530` gate correctly
  aborts the section. Do not resume live testing on section 9b until this is
  fixed at the desk — either retarget the through-walk to a tile >3 tiles from
  the seat, or give door-crossing GOTOs a distance-independent forced-movement
  primitive (durable fix, mirrors the deleted Java `GateAction` prior art
  already cited in `MANNY_OVERSEER.md` §4).
- **1f91a80 is VALIDATED and should be considered the permanent fix** for the
  s09a bank-close defect chain (attempts #13/#14) until DEFECT-33
  (`isBankOpen()` false negative) itself ships — at which point step 5's
  `BANK_CLOSE` becomes the honest primary close and step 5a becomes pure
  belt-and-suspenders, per the routine's own design intent.
- DEFECT-33 (`isBankOpen()` false negative) itself remains **unfixed and
  unowned by this window** — still returns "Bank is already closed" for a
  visibly-open tutorial bank. Not blocking (1f91a80 routes around it), but
  still a latent defect for any other `BANK_CLOSE`-gated step elsewhere in the
  corpus.
- 7f6475d (absorbed-failure bookkeeping fix) remains unexercised across
  attempts #14 and #15 — no bounded inner retry loop has been hit yet in this
  stretch of the chain.
