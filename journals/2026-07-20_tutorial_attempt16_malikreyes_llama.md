# Tutorial attempt #16 — malikreyes/llama — CERTIFICATION retry

**Verdict: DEFECT HARVESTED, not certified this window — but the fix under
test (`fbde0cc`) is VALIDATED with a clean movement receipt.** The 9b
Account Guide door crossing (through-walk retargeted from `(3126,3124)`,
2 tiles, to `(3128,3124)`, 4 tiles) worked exactly as designed: a real
minimap click was issued, the player physically moved through the door, and
varp 281 advanced 525 → 530 — section `09_banking_to_account_guide.yaml`
(9b) passed cleanly for the first time ever. The chain then advanced into
`10_prayer_magic.yaml` (section 10) for the first time this campaign and hit
a **new, distinct instance of the exact same no-op bug class fbde0cc just
fixed**: that file's own step 3 (`GOTO 3126 3124 0`, plain through-walk) is
only 1–2 tiles from the position it starts at, falls inside `GotoCommand
.java`'s plain-mode no-op radius, and reported success without moving the
player. The Account Guide `Talk-to` click that followed appeared to succeed
at the interaction layer (menu verified, "clicked") but never opened
dialogue in-game — the honest `tutorial_progress:>=531` gate caught the
desync and aborted the chain cleanly. Zero hand-driven game actions were
sent.

## Fix-under-test verdict

### fbde0cc — 9b door-crossing retarget (3126,3124 → 3128,3124): **VALIDATED**

Client log receipt (`/tmp/runelite_malikreyes.log`, 22:45:24–22:45:30 PDT):

```
22:45:24 [INTERACT_OBJECT] Successfully performed Open on Door
22:45:24 Received command: GOTO 3128 3124 0
22:45:25 [GOTO] Start: (3124, 3125, 0) -> Target: (3128, 3124, 0)
22:45:25 [GOTO] Distance: 4 tiles
22:45:27 [GOTO] Exact-arrival mode: false
22:45:27 [NAV-METHOD] Using SIMPLE directional navigation (distance: 3 tiles, clear LOS)
22:45:28 [smartMinimapClick] Target (3128, 3124) not visible on minimap
22:45:28 [NAV-DIRECT] falling back to bounds check method
22:45:30 [NAV-DIRECT] ✓ Arrived at destination
22:45:30 [GOTO] Successfully reached target (within 1 tile)
22:45:30 Command executed successfully: GOTO 3128 3124 0
```

This is the load-bearing contrast with attempt #15's failure: attempt #15's
old target (3126,3124, distance 2) logged the no-op tell **"Already at
destination (distance: 2 tiles)"** with no click. This run's new target
(3128,3124, distance 4) instead logs a full navigation attempt — minimap
click computed, fallback bounds-check engaged, and **"NAV-DIRECT ✓ Arrived
at destination"** — unambiguous evidence a real click was issued and the
player actually walked. Section `09_banking_to_account_guide.yaml` finished
`[OK]` and varp 281 climbed 525 → 530 (confirmed by the chain's own gate and
the subsequent state poll). **fbde0cc is validated and should be considered
the permanent fix for this specific step.**

### 7f6475d — absorbed transient failures in bounded inner retry loop: **NOT EXERCISED**
No `[LOOP] absorbed N transient failure(s)` line appeared in either log this
window.

## NEW DEFECT — 10_prayer_magic.yaml step 3 no-ops at short distance (same class as the just-fixed 09b defect)

`10_prayer_magic.yaml` defensively re-seats at `(3124,3124)` and re-opens the
same door before talking to the Account Guide (documented, intentional
redundancy — doors auto-close). This is the section's own step sequence:

1. **Step 1** (`GOTO 3124 3124 0 exact`, re-seat) — eventually PASS after
   multiple internal exact-mode hop retries (the log shows several
   `"Menu is empty — cannot click option 'Walk here'"` / `"Stuck at
   (3125,3124), 1 tiles from target"` cycles before the player made it back
   to the seat; the auto-close race the door-crossing-v2 doctrine warns
   about was live here too, just eventually won by retry).
2. **Step 2** (`INTERACT_OBJECT Door Open 3125 3124`) — PASS. Log:
   `Command executed successfully: INTERACT_OBJECT Door Open 3125 3124`,
   22:46:27 PDT.
3. **Step 3** (`GOTO 3126 3124 0`, plain through-walk) — **reported PASS but
   never moved the player.** Log, 22:46:27 PDT, immediately after the door
   open:
   ```
   [GOTO] Executing command
   [GOTO] Already at destination (distance: 1 tiles)
   [GOTO] Command succeeded
   ```
   Same no-op tell as attempt #15's 9b failure and the exact bug class
   fbde0cc just fixed one file over — this file's own step 3 was never
   given the equivalent retarget.
4. **Step 4** (`INTERACT_NPC Account_Guide Talk-to`) — reported PASS at the
   interaction layer: `[INTERACT-NPC] Found 'Account Guide' ... at distance
   4`, menu verified `'Talk-to'`, `"✓ Successfully clicked 'Account Guide'"`,
   `Command executed successfully: INTERACT_NPC Account_Guide Talk-to`. The
   click landed and was menu-verified, but the player was still on the near
   side of a door that had just re-opened (or was already re-closing) — no
   dialogue actually opened in-game.
5. **Step 5** (`KEY_PRESS space`) — PASS at the command layer (space was
   pressed); no-op in-game since no dialogue was open to advance.
6. **Step 6** (`WAIT tutorial_progress:>=531`) — **honest timeout, FAIL.**
   varp stayed at 530. `strict_steps: true` marked section 13 FAILED; chain
   stopped: `Aborting run: Step 6 (WAIT) failed: failed`.

**Player never crossed into the Account Guide room this second time** —
final resting position (3124,3124,0), the seat tile, not the interior tile
the routine's step-3 through-walk was supposed to deliver. This is a clean,
textbook demonstration of the doctrine's #1 defect class (the false-pass):
the click-verification layer ("clicked", "menu matched") reported success
while nothing changed in-game, and only the ground-truth varp gate caught
it — exactly the mechanism it exists for.

Screenshot at the abort point (residential IP overlay redacted with a local
Pillow black-rectangle pass before saving to this repo; raw copy deleted
from both the laptop scratch path and the llama host):
`journals/images/2026-07-20_malikreyes_attempt16_10prayer_step3_noop_abort.png`.
The chat/dialogue panel shows the Account Guide's static "Account
Management" examine-style tooltip text, not an active Talk-to dialogue —
visually consistent with the log-derived diagnosis that the conversation
never actually started.

**Fix direction (not applied this window, per hands-off doctrine — do not
fix routines live):** `10_prayer_magic.yaml` step 3's through-walk target
`(3126,3124)` needs the same treatment fbde0cc gave 9b's step 3 — retarget
to a tile more than 3 Chebyshev tiles from wherever the re-seat step lands
(the file's own `account_guide_npc`/`through_walk_target` locations already
document the 09b geometry; the same `(3128,3124)` or similar tile deep in
the room would clear the no-op radius here too). Longer term, this is the
second live instance of the identical bug class in adjacent files — strong
signal for the durable Java-side "force movement regardless of distance for
door-crossing GOTOs" primitive already flagged in `MANNY_OVERSEER.md` §4
(mirrors the deleted `GateAction` prior art), rather than continuing to
patch each occurrence one file at a time.

## Timeline

- **~05:44Z** — Preflight: `git log --oneline -1` confirmed HEAD `0375a22`,
  `fbde0cc` confirmed an ancestor via `git merge-base --is-ancestor`.
  `./run_routine.py --dry-run routines/tutorial_island/00_master.yaml`
  PASSED (53 steps simulated, RESULT: PASS).
- **05:45:16Z (launch)** — `mannyctl llama window malikreyes
  routines/tutorial_island/00_master.yaml` — all 6 gates PASS:
  predecessor-dead, credentials (`default: punitpun`, malikreyes not
  banned), display `:9`, provision (stash/pop/verify clean,
  jar_sha=421c03e91ff9e82b), login gate (LOGGED_IN in 21s at
  `(3124,3124,0)`, login_index 10 — matches the parked position exactly),
  run+watchdog detached (`run_id 20260720T054516Z_malikreyes`).
- **~22:44:58 PDT (client boot)** — one benign
  `NullPointerException: Cannot read field "am" because "xz.ch" is null` at
  `client.getTopLevelInterfaceId` / `UITools$WidgetInspectorTool` during
  `Game State: STARTING` — identical signature to prior attempts' known
  false-positive crash class (widget-tree debug panel racing client boot).
  Not a real crash; client process stayed alive throughout; no intervention
  taken.
- **~05:45:18Z–05:45:19Z** — chain replayed sections 1–11
  (character creation through `09_banking`), all instantly skipped via the
  `tutorial_progress >= gate` resume logic (account parked at varp 525, past
  all 11 of those gates). Zero live commands sent for these.
- **~22:45:22–22:45:30 PDT** — section 12/13,
  `09_banking_to_account_guide.yaml` ("Section 9b"), **fbde0cc under live
  test**:
  - Step 1 (seat `GOTO 3124 3124 0 exact`) — PASS.
  - Step 2 (`INTERACT_OBJECT Door Open 3125 3124`, coordinate-qualified) —
    PASS.
  - Step 3 (`GOTO 3128 3124 0`, plain through-walk, **the fix**) — **PASS,
    real movement confirmed** (`Distance: 4 tiles` → `NAV-DIRECT ✓ Arrived
    at destination` → `Successfully reached target`).
  - Step 4 (`WAIT tutorial_progress:>=530`) — PASS. Section 12: **`[OK]`**.
    **New furthest progress: varp 525 → 530, first-ever clean pass of 9b.**
- **~22:45:31–22:46:x PDT** — section 13/13, `10_prayer_magic.yaml`
  ("Section 10: Prayer + Magic"), first-ever live execution reached this
  campaign:
  - Step 1 (re-seat `GOTO 3124 3124 0 exact`) — eventually PASS after
    several internal exact-mode hop retries (auto-closed-door "Walk here"
    blocked-menu cycles, self-recovered).
  - Step 2 (door re-open, coordinate-qualified) — PASS.
  - Step 3 (`GOTO 3126 3124 0`, plain through-walk) — **reported PASS, no
    movement** (`Already at destination (distance: 1 tiles)`) — the new
    defect, same class as fbde0cc just fixed one file over.
  - Step 4 (`INTERACT_NPC Account_Guide Talk-to`) — reported PASS at the
    click-verification layer; no dialogue actually opened.
  - Step 5 (`KEY_PRESS space`) — PASS at the command layer, no-op in-game.
  - Step 6 (`WAIT tutorial_progress:>=531`) — **honest timeout, FAIL.**
  - `strict_steps: true` marked section 13 FAILED; chain stopped:
    `Aborting run: Step 6 (WAIT) failed: failed`.
- **~05:47:18Z** — watchdog observed run pid 942493 gone, marked run
  `status: completed` (the `run_routine.py` process exiting normally after
  the chain's own honest-abort logic — a clean process exit, not a crash or
  forced kill).
- **~05:47–05:52Z** — investigation: pulled the full command timeline from
  `/tmp/runelite_malikreyes.log` and `/tmp/manny_run_malikreyes.log`, read
  `09_banking_to_account_guide.yaml` and `10_prayer_magic.yaml` source to
  confirm the step sequence and geometry. Screenshot captured via
  `DISPLAY=:9`, `scrot -o` — **the raw capture exposed the host's
  residential IP in an on-screen overlay**; redacted (black rectangle over
  the overlay region) with a local Pillow pass before being copied into this
  repo. The raw unredacted file was deleted from both the llama host and the
  local scratch path, never staged.
- **~05:52Z** — `mannyctl llama stop malikreyes` — clean scoped SIGTERM stop
  (pid 942213; run process had already exited on its own before this call).

## Final state
- varp-281 = **530** (up from the parked 525 — new furthest progress).
- Position: **(3124, 3124, 0)** — the section-9b/10 door-threshold seat
  tile, the second crossing never completed.
- Account healthy, no ban signals, client cleanly stopped via scoped
  `mannyctl stop` (never `pkill java`).

## Hand-driven game actions: **0**
No clicks, walks, interactions, dialogue, or camera commands were sent by
the supervisor. All supervisor actions were infra-only: preflight (git log,
dry-run), launch (`mannyctl window`), read-only log/state polling via
`mannyctl exec` + direct state-file reads, one passive screenshot capture
(redacted before use), and the terminal stop.

## Open items / next fix direction
- **fbde0cc is VALIDATED** for `09_banking_to_account_guide.yaml` step 3 —
  keep as the permanent fix for that step.
- **New defect (DEFECT-7-class instance #2):**
  `10_prayer_magic.yaml` step 3's plain-mode through-walk target
  (3126,3124) is only 1–2 tiles from wherever step 1's re-seat lands, inside
  `GotoCommand.java`'s plain-mode no-op radius (`distance <= 3`) — the exact
  bug class fbde0cc just fixed in the adjacent file. The step reports
  success without moving the player, so the Account Guide `Talk-to` fires
  from out of range and never opens dialogue; the honest
  `tutorial_progress:>=531` gate correctly aborts the section. Do not resume
  live testing past section 10's Account Guide phase until this is fixed at
  the desk — retarget the through-walk to a tile >3 Chebyshev tiles from the
  re-seat (mirror fbde0cc's `(3128,3124)` choice, or equivalent), or (durable
  fix) give door-crossing GOTOs a distance-independent forced-movement
  primitive so this bug class stops needing a one-off patch per file.
- Section 1's re-seat (step 1) also surfaced a secondary, softer symptom:
  several rounds of exact-mode "Walk here" blocked-menu retries before it
  self-recovered — consistent with the door-crossing-v2 doctrine's
  documented auto-close race, but on a *re-seat* step rather than a
  *crossing* step. Worth watching if it ever fails to self-recover within
  budget on a future attempt.
- 7f6475d (absorbed-failure bookkeeping fix) remains unexercised — no
  bounded inner retry loop has been hit yet in this stretch of the chain.
- Campaign furthest progress is now varp 530 (was 525) — one door crossing
  closer to the mainland. Only the Account Guide talk/tab (531/532/540),
  east door (550), Brace (570), prayer (610), chapel exit (620), magic
  (650), wind strike (670), ironman decline (671), final dialogue (680), and
  mainland (1000) remain, contingent on the step-3 no-op fix above.
