# Tutorial attempt #17 — malikreyes/llama — CERTIFICATION retry

**Verdict: DEFECT HARVESTED, not certified this window — but the fix under
test (`489840b`) is VALIDATED with a clean movement receipt, and the chain
reached the deepest live point of the entire campaign (varp 281 = 550) before
an honest abort inside `10_prayer_magic.yaml`'s own Brother Brace phase.**
Section 10's step 3 through-walk (retargeted `(3124,3124)`→`(3128,3124)`,
distance 4 tiles, clearing the plain-GOTO no-op radius) worked exactly as
designed and cleared the Account Guide talk/tab/east-door ladder (531 → 532/540
→ 550) in one clean live pass — all first-ever live clears for those
sub-phases in this run. The chain then hit two further issues in the same
file, both harvested honestly by the routine's own ground-truth gates: (1) a
**third instance of the same no-op-GOTO bug class** the fix under test had
just retired at step 3, this time at step 17 (walk to chapel), and (2) the
file's own documented **Brother Brace pacing OPEN BLOCKER**, compounded by a
new observation — a pacing-induced menu-miss can misfire as an accidental
"Walk here" click and drag the player off-target — followed by an
apparently-successful `Talk-to` click that still never credited
`tutorial_progress:>=570` within the 15s gate. Zero hand-driven game actions
were sent.

## Fix-under-test verdict

### 489840b — 10_prayer_magic.yaml step 3 through-walk retarget (3126,3124 → 3128,3124): **VALIDATED**

This is the same bug class `fbde0cc` fixed one file over (`09_banking_to_
account_guide.yaml`) in attempt #16, now applied to `10_prayer_magic.yaml`'s
own step 3, which attempt #16 found broken (no-op at distance 1–2, false-pass
Talk-to, honest abort at varp 530).

Client log receipt (`/tmp/runelite_malikreyes.log`, 22:57:23–22:57:27 PDT):

```
[GOTO] Start: (3124, 3124, 0) -> Target: (3128, 3124, 0)
[GOTO] Distance: 4 tiles
[GOTO] Zooming out 5 scrolls for better pathfinding visibility
[GOTO] Exact-arrival mode: false
[GOTO] Successfully reached target (within 1 tile)
[GOTO] Command succeeded
```

Cross-confirmed by the on-host location-history export
(`/tmp/manny_malikreyes_location_history.json`), which shows real per-tile
movement `(3124,3124) → (3125,3124) → (3127,3124) → (3128,3124)` in the same
window — unambiguous evidence of a real click and real movement, not the
"Already at destination" no-op tell that falsified attempt #16's belief about
the NPC-interact masking the old 2-tile target. **489840b is validated.**

Downstream of the fix, the section continued cleanly through the rest of the
Account Guide ladder — all first-ever live clears in this campaign:
- Step 4–6: `Talk-to` Account Guide + dialogue drain → **varp 530→531 PASS**.
- Step 7–8: Account Management tab click (`mcp_tool: click_widget action:
  "Account Management"`, the 63fa2b5 fix) → **varp 531→532 PASS**.
- Step 9–11: second Account Guide talk + 16-page drain → **varp 532→540 PASS**.
- Step 12–15: east-door seat/open/through-walk (`3134,3124`) → **varp
  540→550 PASS**.

This is the deepest section-10 progress the campaign has made live —
previously the furthest live contact with this file was varp 530 (attempt
#16's abort point, one step into the file). This run cleared the entire
Account Guide phase (Phase 1–4 of `10_prayer_magic.yaml`) in a single pass.

### 7f6475d — absorbed transient failures in bounded inner retry loop: **NOT EXERCISED**
No `[LOOP] absorbed N transient failure(s)` line appeared in either log this
window.

## NEW DEFECT #1 — 10_prayer_magic.yaml step 17 no-ops (same bug class, third live instance)

Step 16 (`GOTO 3128 3110 0`) landed the player correctly (log: `Start:
(3134, 3124, 0) -> Target: (3128, 3110, 0)`, `Distance: 14 tiles`,
`Successfully reached target (within 1 tile)`, 22:58:26–22:58:38 PDT).

Step 17 (`GOTO 3130 3107 0`, walk to Brother Brace's chapel) immediately
no-op'd, 22:58:39 PDT:
```
[GOTO] Executing command
[GOTO] Already at destination (distance: 3 tiles)
[GOTO] Command succeeded
```
Chebyshev distance from `(3128,3110)` to `(3130,3107)` is exactly 3 — inside
plain GOTO's `distance <= 3` no-op short-circuit (`GotoCommand.java:152`),
the same mechanism `fbde0cc` and `489840b` just retired for two other steps.
This is the **third live instance of this exact bug class** in this section
alone. The step reported success but the player never moved toward Brace
from `(3128,3110)`.

## NEW DEFECT #2 (harvest against the documented OPEN BLOCKER) — Brother Brace pacing causes a misclick-driven walk, then an apparently-successful Talk-to still fails to credit varp

`10_prayer_magic.yaml`'s own header already documents Brother Brace (id 3319)
as a pacing NPC with an "OPEN BLOCKER" ("I can't reach that!" misses). This
run adds two new pieces of evidence:

1. **A menu-miss can misfire as an accidental "Walk here" click.** Log,
   22:58:41–22:58:43 PDT: `attempt=1` clicked but the menu had shifted
   (`[MENU-VERIFY] Expected: 'Talk-to', Actual: 'Walk here'`), then a
   re-open found no 'Talk-to' entry at all (`attempt=2 outcome=menu-miss`),
   then `attempt=3 outcome=paced-away-retry`. The on-host location-history
   export shows the player physically drifting during this exact window —
   `(3128,3110) → (3126,3110) → (3125,3110) → (3124,3109) → (3124,3107) →
   (3124,3105)`, timestamps 22:58:38.6–22:58:48.3 PDT — consistent with one
   or more of those misclicks landing on "Walk here" and issuing an
   unintended ground-click walk. This is a previously undocumented failure
   mode of the pacing blocker: it doesn't just fail to talk, it can actively
   relocate the player away from the NPC, compounding subsequent attempts.
2. **The eventual "successful" click still didn't credit the gate.** A
   second routine-level `INTERACT_NPC` attempt at 22:58:45–22:58:46 PDT found
   Brace at distance 6, closed to distance ~1 (`tile=3124,3104` vs. player
   `3124,3105`), menu-verified `Talk-to`, and logged `✓ Successfully clicked
   'Brother Brace'` / `Command executed successfully`. Step 18's own
   `await_condition: dialogue` was satisfied (command layer reports success).
   But step 18b (`WAIT tutorial_progress:>=570`, 15s timeout, `on_failure:
   abort`) timed out — **varp stayed at 550.** A state-file poll taken ~2
   minutes after the chain had already exited (no further driver commands
   sent) still showed `dialogue: {open: true}` with varp still 550 — a
   dialogue window was genuinely open in-game, yet the tutorial progress
   counter never ticked. This contradicts the file's own header receipt
   ("attempt #8: opening dialogue with Brother Brace advances varp 281 from
   550 to 570" — i.e., on open, not on advance). Two candidate root causes
   for the desk, not decided here (hands-off doctrine — no live
   investigation attempted): (a) the varp only advances after the dialogue
   is actually advanced past its first page, not merely opened, and this run
   never got to press space because step 18b sits before step 19's
   `KEY_PRESS`; or (b) the multiple prior misclick/drift cycles left the game
   in an atypical dialogue state (e.g., static examine-style text rather than
   the tutorial-triggering conversation branch) that never was going to
   credit the counter regardless of timeout length.

`strict_steps: true` + the honest `tutorial_progress:>=570` gate did exactly
what they're for: `Aborting run: Step 18b (WAIT) failed: failed`; section 13
marked FAILED; chain stopped cleanly at varp 550 instead of marching a
desynced game forward.

No screenshot tool was available for this host in this environment (no
`manny-llama` MCP registered, `mannyctl` has no `screenshot`/`cmd
GET_SCREENSHOT` path proven for llama this session) — this journal relies on
log + location-history receipts only, per doctrine's "logs > screenshots >
theories" ordering.

## Timeline

- **~05:56Z** — Preflight: `git log --oneline -1` confirmed HEAD `489840b`.
  `./run_routine.py --dry-run routines/tutorial_island/00_master.yaml`
  PASSED (53 steps simulated, RESULT: PASS).
- **05:57:16Z (launch)** — `mannyctl llama window malikreyes
  routines/tutorial_island/00_master.yaml` — all 6 gates PASS:
  predecessor-dead, credentials (`default: punitpun`, malikreyes not
  banned), display `:9`, provision (stash/pop/verify clean,
  jar_sha=421c03e91ff9e82b), login gate (LOGGED_IN in 19s at
  `(3124,3124,0)`, login_index 10 — matches the parked position exactly),
  run+watchdog detached (`run_id 20260720T055716Z_malikreyes`).
- **~22:56:59 PDT (client boot)** — one benign
  `NullPointerException: Cannot read field "am" because "xz.ch" is null` at
  `client.getTopLevelInterfaceId` / `UITools$WidgetInspectorTool` during
  `Game State: STARTING` — identical signature to prior attempts' known
  false-positive crash class (widget-tree debug panel racing client boot,
  before login). Not a real crash; client process (pid 945175) stayed alive
  throughout; no intervention taken.
- **~05:57:17Z–05:57:19Z** — chain replayed sections 1–12 (character
  creation through `09_banking_to_account_guide`), all instantly skipped via
  the `tutorial_progress >= gate` resume logic (account parked at varp 530,
  past all 12 of those gates — 09b was fixed and validated in attempt #16).
  Zero live commands sent for these.
- **~22:57:23–22:58:38 PDT** — section 13/13, `10_prayer_magic.yaml`,
  Phases 1–4, **489840b under live test**: step 1 (re-seat, PASS), step 2
  (door open, PASS), step 3 (**the fix**, retargeted through-walk, PASS with
  real-movement receipt), steps 4–6 (AG talk 1, varp 530→531 PASS), steps
  7–8 (Account Management tab, varp 531→532 PASS), steps 9–11 (AG talk 2,
  varp 532→540 PASS), steps 12–15 (east door crossing, varp 540→550 PASS),
  step 16 (walk to chapel outdoor waypoint, PASS).
- **22:58:39 PDT** — step 17 (`GOTO 3130 3107 0`) no-ops: **NEW DEFECT #1**
  (third live instance of the plain-GOTO ≤3-tile no-op class).
- **22:58:41–22:58:46 PDT** — step 18 (`INTERACT_NPC Brother_Brace Talk-to`,
  pacing-NPC repeat): attempt 1 menu-miss/misclick (**NEW DEFECT #2a**,
  incidental drift `3128,3110`→`3124,3105`), attempt 2 menu-miss, attempt 3
  paced-away-retry, then a fresh `INTERACT_NPC` call at 22:58:45–22:58:46
  reports a menu-verified successful click. Step 18's `dialogue` await
  satisfied.
- **22:58:46–~22:59:01 PDT** — step 18b (`WAIT tutorial_progress:>=570`,
  15s timeout) times out: **NEW DEFECT #2b** — varp never advances past 550
  despite the apparently-successful Talk-to and a persisting open dialogue
  state. `strict_steps` marks section 13 FAILED: `Aborting run: Step 18b
  (WAIT) failed: failed`.
- **~05:59:18Z** — watchdog observed run pid 945442 gone, marked run
  `status: completed` (the `run_routine.py` process exiting normally after
  the chain's own honest-abort logic — a clean process exit, not a crash or
  forced kill).
- **~06:00–06:01Z** — investigation: pulled `/tmp/runelite_malikreyes.log`,
  `/tmp/manny_run_malikreyes.log`, `/tmp/manny_malikreyes_location_history.json`,
  and two state-file polls (05:58Z and 06:00Z, both varp 550, both
  `dialogue.open: true`, confirming the stuck-dialogue observation was not a
  one-off poll glitch). Read `10_prayer_magic.yaml` source to confirm the
  step sequence and geometry. No screenshot tool available for this host in
  this session — relied on log + location-history receipts.
- **~06:02Z** — `mannyctl llama stop malikreyes` — clean scoped SIGTERM stop
  (pid 945175; run process had already exited on its own before this call).

## Final state
- varp-281 = **550** (up from the parked 530 — new furthest-ever live
  progress, past the entire Account Guide phase of section 10).
- Position: **(3124, 3105, 0)** — a few tiles off from Brother Brace's chapel
  approach, reached via pacing-induced drift during the failed talk attempts.
- Account healthy, no ban signals, client cleanly stopped via scoped
  `mannyctl stop` (never `pkill java`).

## Hand-driven game actions: **0**
No clicks, walks, interactions, dialogue, or camera commands were sent by the
supervisor. All supervisor actions were infra-only: preflight (git log,
dry-run), launch (`mannyctl window`), read-only log/state polling via
`mannyctl exec` + direct state-file/location-history reads, and the terminal
stop.

## Open items / next fix direction
- **489840b is VALIDATED** for `10_prayer_magic.yaml` step 3 — keep as the
  permanent fix for that step.
- **NEW DEFECT #1 (DEFECT-7-class instance #3):** `10_prayer_magic.yaml`
  step 17's plain-mode through-walk target `(3130,3107)` is exactly 3
  Chebyshev tiles from step 16's landing tile `(3128,3110)` — inside
  `GotoCommand.java`'s plain-mode no-op radius. Retarget to a tile >3 tiles
  away (mirroring the 489840b/fbde0cc pattern), or apply the durable
  distance-independent forced-movement primitive for door/approach-crossing
  GOTOs already flagged in `MANNY_OVERSEER.md` §4 — this is now the third
  live occurrence of the identical bug class in this same short ladder.
- **NEW DEFECT #2 (Brother Brace, extends the file's own documented OPEN
  BLOCKER):** (a) a pacing-induced menu-miss can misfire as an accidental
  "Walk here" ground click, dragging the player away from the NPC — not
  previously documented; and (b) even a click that clears menu-verification
  and reports command success does not reliably credit
  `tutorial_progress:>=570` within 15s — contradicts the file's own header
  receipt that dialogue-*open* alone credits the varp. Needs desk
  investigation: does the varp actually require advancing past the first
  dialogue page (i.e., is step 19's `KEY_PRESS` a precondition, not just
  step 18's `Talk-to`)? If so, step 18b's gate is mis-ordered relative to
  step 19 and should either move after an initial dialogue-advance, or the
  timeout should be lengthened and paired with a diagnostic space-press
  before the strict check.
- No screenshot capability was available for the `llama` host in this
  session (no registered manny MCP server, no `mannyctl screenshot`
  subcommand) — future attempts on this host should either wire one up or
  accept log/location-history-only receipts as sufficient (this journal
  demonstrates they are, for this class of defect).
- 7f6475d (absorbed-failure bookkeeping fix) remains unexercised — no
  bounded inner retry loop has been hit yet in this stretch of the chain.
- Campaign furthest progress is now varp 550 (was 530) — the entire Account
  Guide phase of section 10 is now live-proven. Remaining ladder: Brace talk
  1 (570, blocked by NEW DEFECT #1 stranding the player 3 tiles short, then
  NEW DEFECT #2's pacing/varp-credit issue), prayer tab + talk 2 (610),
  chapel exit (620), magic instructor (650), wind strike (670 — still
  fragile per the known-fragile-territory note), ironman decline (671),
  final dialogue (680), mainland (1000).
