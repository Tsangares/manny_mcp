# Tutorial attempt #13 — malikreyes/llama — CERTIFICATION run

**Verdict: DEFECT HARVESTED, not certified this window.** Chain honestly aborted in
section `09_banking.yaml` at step 6 (poll booth). Zero hand-driven game actions
were sent — the run stayed fully hands-off from launch to terminal stop. The
entry-door fix under test (5b21af0) PASSED live; a new, previously-undiscovered
defect (bank interface not actually closed by `KEY_PRESS Escape`) blocked
progress past varp 520.

## Fixes-under-test verdicts

### 5b21af0 — s09a entry door pin: **PASS**
Player resumed at (3123,3125,0) — exactly the pinned seat from step 1. The
coordinate-qualified `INTERACT_OBJECT Door Open 3124 3126` (step 1a) and the
plain through-walk to (3123,3127) (step 1b) worked: the chain proceeded through
ladder climb-up/down and reached the bank booth, using it successfully (varp
510 → 520, confirmed by state read `tutorial.progress: 520` and by the
screenshot showing "The Bank of Gielinor (25)" open). This is the first live
confirmation that the coordinate-qualified door interact resolves the correct
door among the 5 decoy "Door" objects in range — attempt #12's wrong-door
regression did not recur.

### 7f6475d — absorbed transient failures in bounded inner retry loop: **NOT EXERCISED**
Section 09a has no bounded inner retry loop of the kind this fix targets (that
pattern lives in 08b's ranged-attack reposition loop). No `[LOOP] absorbed N
transient failure(s)` log line appeared this run. This fix rode along
unexercised — no verdict either way from this window.

## Timeline

- **04:53:22Z (launch)** — `mannyctl llama window malikreyes 00_master.yaml` — all
  6 gates PASS. Predecessor-dead, credentials (`default: punitpun`, malikreyes
  not banned), display `:9`, provision (stash/pop/verify clean), login gate
  (LOGGED_IN in 20s at 3123,3125,0, login_index 10), run+watchdog detached
  (run_id `20260720T045320Z_malikreyes`).
- **~04:53:22Z** — client boot logs one `NullPointerException: Cannot read
  field "am" because "xz.ch" is null` at `UITools$WidgetInspectorTool` during
  `Game State: STARTING`. This is a benign widget-inspector-tool NPE at boot
  (matched by the watchdog's `mcptools` crash signature, which is a known
  false-positive class for this exact string) — client process stayed alive
  (pid 932096, confirmed running throughout), state file kept updating. Not a
  real crash; no intervention taken.
- **04:53:22Z–~04:53:47Z** — chain replayed sections 1–10 (`01_character_creation`
  through `08_combat_sword_ranged`), all instantly skipped via the
  `tutorial_progress >= gate` resume logic since the account was already
  parked past all of them (varp 510). Zero live commands sent for these.
- **~04:53:47Z** — section 11/13, `09_banking.yaml` ("Section 9a: Banking"),
  begins live execution (first section to actually run this window, since
  malikreyes resumed at exactly the 09a starting varp).
  - Step 1 (seat 3123,3125 exact) — already satisfied at login position, no-op.
  - Step 1a (coordinate-qualified door open 3124,3126) — PASS (5b21af0 fix).
  - Step 1b (through-walk to 3123,3127) — PASS.
  - Step 2/3 (ladder climb up/down, coordinate-qualified 3123,3128) — PASS.
  - Step 4 (Bank_booth Use) — PASS, bank interface opened (25gp, confirmed by
    screenshot).
  - Step 5 (KEY_PRESS Escape, 800ms settle) — reported success but **did NOT
    actually close the bank interface** (see defect below).
  - Step 6 (INTERACT_OBJECT Poll_booth Use) — **FAILED**, 3 internal
    click-attempts per try × 2 `on_failure: retry` outer attempts = 3 total
    step executions (21:53:48–21:53:52, 21:53:53–21:54:00, 21:54:02–21:54:08
    PDT), all failing identically. `strict_steps: true` marked the section
    FAILED after exhausting retries.
- **04:54:22Z** — watchdog observed `run_pid 932366` gone, marked run `status:
  dead`. Chain summary: `Status: FAILED`, 11/13 sections attempted, section 11
  (`Tutorial Island - Banking`) the sole failure, 10/11 prior/skipped sections
  `[OK]`.
- **~04:56Z** — investigation: screenshot captured via `DISPLAY=:9 import
  -window root` (no mannyctl/MCP screenshot tool available on this host; ad-hoc
  ImageMagick capture used instead) — see below. Client log grepped for
  `MENU-MATCH`/`Poll`/`INTERACT_OBJECT` around the failure window.
- **~04:57Z** — `mannyctl llama stop malikreyes` — clean scoped SIGTERM stop.

## Defect harvested: bank interface not actually closed before poll-booth interact

Root cause, confirmed by screenshot (`malikreyes_pollbooth_fail.png`): at the
moment of every poll-booth interact failure, **the bank interface
("The Bank of Gielinor (25)") was still open on screen**, with the game's own
tutorial hint text visible underneath: *"To continue, close the bank and click
on the indicated poll booth."* — i.e. the game itself was telling the player
exactly what step 6 needed but step 5 hadn't delivered.

Client log confirms the mechanism of the resulting failure, not just the
symptom:
```
[GameEngine] Found 1 TileObjects matching 'Poll booth' within 15 tiles
[INTERACT-OBJECT] Found TileObject 'Poll booth' as fd at WorldPoint(x=3119, y=3121, plane=0)
[INTERACT-TILEOBJECT] Attempt N/3 to click fd 'Poll booth' with action 'Use'
[INTERACT-TILEOBJECT] Orienting camera toward 'Poll booth' at (3119, 3121)
[MENU-MATCH] entryOption='Cancel' entryTarget='' vs option='Use' target='' => match=false via none (optionMatch=false targetMatch=true assocPresent=false exactMatch=false)
[INTERACT-TILEOBJECT] Menu option 'Use' not found for fd 'Poll booth'
...
[INTERACT-OBJECT] Failed to interact with TileObject 'Poll booth' after 3 attempts
```
Object resolution was correct (single, correct TileObject found at the
documented (3119,3121,0) tile, 2 tiles away, "already within interaction
range"). The failure is entirely at menu-build time: every right-click on the
poll booth built a context menu whose *only* entry was `Cancel` — never `Use`
— for all 3×3 = 9 total click attempts across the 3 step executions. This is
consistent with the bank modal still being open and consuming/altering menu
construction for world-object right-clicks, rather than any coordinate,
naming, or targeting problem with the poll booth itself (unlike the door
defect this window's fix addressed).

**This is a new, previously undocumented defect** — the 09_banking.yaml header
comments call step 5's Escape approach "proven" from a prior live pass
(judeaislam/llama probe, 2026-07-20 attempt #8), but this run shows it is not
reliable: `KEY_PRESS Escape` either didn't register, or the 800ms
`delay_after_ms` settle window elapsed before the bank interface actually
closed client-side (a timing race), or the tutorial mode's bank-tutorial modal
requires a different close action than a normal bank session. The routine has
no state check on "bank interface actually closed" — it only trusts the
key-press command's own return, which is exactly the false-pass class this
project's doctrine warns about (dialogue/interface closing ≠ objective
complete).

**Fix direction (not applied this window — live minutes are scarce, hands-off
doctrine in force):** replace step 5's blind `KEY_PRESS Escape` + fixed delay
with a state-gated close: verify no bank/interface widget is open before
proceeding to step 6 (e.g. an `await_condition` on an "interface closed"
signal, or a bounded retry of Escape + widget-state check), mirroring the
poll-booth's own step 9 pattern (ground-truth WAIT gate, not a trusted command
return). A `CLICK_WIDGET <bank-close-button-id> "Close"` as the close action
(canonical UI-close path per this repo's own doctrine — "never
MOUSE_MOVE+MOUSE_CLICK, atomic CLICK_WIDGET") is also worth trying instead of
a keypress, since KEY_PRESS Escape has no engine-level confirmation of receipt
by the correct interface.

## Hand-driven game actions: 0

No gameplay command (click, walk, interact, dialogue, camera) was sent by the
supervisor. All in-game actions came from `run_routine.py` executing
`00_master.yaml`. Supervisor-issued commands were infra-only: the `window`
launch ceremony, read-only status/log/state polling, one ad-hoc `GET_SCREENSHOT`/
`SCREENSHOT` probe (both rejected as unknown commands, non-gameplay, harmless),
an `import -window root` screenshot capture (host-level, not a game command),
and the final scoped `mannyctl llama stop malikreyes`.

## Final state

- Player left at (3120,3123,0), plane 0, inside the bank room, bank interface
  still open (per screenshot), 10/10 HP, no combat, no ban signals
  (`login_index: 10`, `terminal_login_failure: false` throughout).
- varp-281 tutorial progress: **520** (bank booth used; poll booth not yet
  credited — gate 525 not reached).
- Client stopped cleanly via `mannyctl llama stop malikreyes` (scoped SIGTERM,
  pid 932096).
- Run ledger: `/tmp/manny_runs/20260720T045320Z_malikreyes.json`, final status
  `dead` (clean exit, not a watchdog-forced kill).

## Screenshot

`malikreyes_pollbooth_fail.png` (scratchpad; not committed — captured via
ad-hoc host-level `import`, not the project's own screenshot tooling, since no
screenshot command/MCP tool was registered for this host in this session).
Shows the open bank interface with the tutorial's own "close the bank and
click on the indicated poll booth" hint text, which is the direct visual
confirmation of the root cause above.

## Next steps

1. Fix `09_banking.yaml` step 5 to be state-gated (verify bank interface
   actually closed) instead of a blind Escape + fixed delay.
2. Re-run attempt #14 from the same resume point (varp 520, malikreyes is
   parked past the door and bank booth already) — should reach the poll booth
   in well under a minute once step 5 is fixed, keeping the rest of the
   ladder (525 → 1000) as the remaining certification surface.
3. 7f6475d (absorbed-failure fix) still awaits a live exercise — none of this
   window's live commands hit a bounded inner retry loop. Its gate rides
   forward to the next window that reaches 08b or an equivalent loop.
