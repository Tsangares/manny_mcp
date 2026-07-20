# Tutorial Island attempt #12 — malikreyes / llama :9 (2026-07-20, ~04:22–04:42 UTC)

## HEADLINE

**HAND-DRIVEN GAME ACTIONS: 0 (target 0)** — fifth consecutive fully hands-off measurement
run. Every game action across all three run windows was chain-driven; the supervisor's only
actions were infrastructure (launch, scoped stop, one sanctioned relaunch).

Attempt #12 banked, in one night:

1. **THE RANGED KILL — e695cdf VERDICT: PASS.** The attempt-#11 fix (reposition GOTO to the
   receipted shooting tile + bounded [reposition → attack → verify] inner retry loop) worked
   exactly as designed: it absorbed one rat-wander miss and landed the kill on pass 2.
   varp 480 → 500 (kill) → 510 (combat-area exit ladder). Furthest chain progress yet.
2. **New engine defect: strict_steps kills the chain even when the inner retry loop
   self-heals** (bookkeeping, not gameplay — engine fix already in progress at the desk).
3. **s09a first-contact harvest: the AMBIGUOUS-NAME TRAP, door edition** — entry door
   resolved to the wrong "Door" object; deterministic, honest abort at the real fault.
   Desk fix dispatched (coordinate-qualified INTERACT_OBJECT; receipts below are load-bearing).
4. **New jar's modal export validated on its first live window** — `[MODAL-BLOCK]` +
   `dialogue.modal_text` caught a queued "I can't reach that!" modal mid-interaction,
   precisely the receipt class it was built for.

Zero hand-driven actions stands across the whole attempt series (#9–#12).

Account parked healthy: (3123,3125,0), varp-281 = 510, 10/10 HP, no ban signals, zero
java/python processes verified via `ps -eo pid,args` after each stop.

## Jar deviation (deliberate, coordinator-approved)

The brief pinned jar `d0668f58` for this window. Gate-4 provisioning shipped
`421c03e91ff9e82b` instead — the canonical build path on llama already contained the newer
jar (manny `7f42b54`: group-162 chatbox-modal export, honest CLICK_CHILD_WIDGET,
INTERACT_OBJECT optional [x y] coords), staged there by the earlier Java fix-window agent.
No `d0668f58` copy existed anywhere to restore. Supervisor caught the sha mismatch ~30s
after run 1 started, aborted the run (~4 min in, varp 480→490 — contaminated data point,
discarded), and escalated. **Coordinator ruling: option (b)** — 421c03e9 is the official
go-forward jar; certification runs on it, logged here as a deliberate deviation. Both
subsequent runs (and, it turns out, run 1 too) ran the same jar, so the night's dataset is
internally consistent.

Follow-ups from the ruling, both done:
- Backup created on llama: `client-1.12.34-SNAPSHOT-shaded.jar.backup-421c03e9` — never
  again zero copies of a deployed artifact.
- Pipeline gap ticketed (coordinator side): gate 4 gets an expected-sha pin check.

## Run windows

| Run | run_id | Window | Outcome |
|---|---|---|---|
| 1 | 20260720T042229Z_malikreyes | 04:22–04:27 | Supervisor-aborted on jar-pin discrepancy. varp 480→490 (attack registered). Data discarded as contaminated; later ruled same-jar anyway. |
| 2 | 20260720T043011Z_malikreyes | 04:30–04:34 | **Ranged verdict PASS** (below). Chain halted by strict_steps bookkeeping at 10/13 despite in-game success. varp 490→510. |
| 3 | 20260720T043800Z_malikreyes | 04:38–04:40 | Sanctioned single chain-restart at novel state (varp 510, surface). Skip-gated 10 sections cleanly, s09a first contact → honest FAIL at entry door. |

Launch path: `mannyctl llama window malikreyes routines/tutorial_island/00_master.yaml` —
all 6 WINDOW_GATEs PASS on every launch (gate 1 correctly refused once when the prior
window's client was still up; scoped stop, relaunch). One known-benign boot NPE during
STARTING logged by the watchdog each run, as expected.

## Verdict 1 — the ranged kill (e695cdf acceptance: PASS)

Receipts (client log, PDT timestamps; run 2):

- Pass 1: reposition GOTO → (3104,9509) seated; `INTERACT_NPC Giant_rat Attack` at
  21:32:00, `[MENU-VERIFY] ✓ Click verified: 'Attack' on attempt 1`, rat at tile
  (3099,9513). Step-28 varp verify (`tutorial_progress:>=500`, 45s) **timed out** — the
  exact rat-wander variance the fix anticipates.
- Inner loop fired: `Inner loop step 28 failed (1/3). Restarting from step 25b.`
- Pass 2: re-walked to (3104,9509); attack at 21:33:04 — `Found 'Giant rat' with action
  'Attack' at distance 3`, `[MENU-MATCH] ... => match=true via strict`, click verified.
  Kill registered → varp 500.
- Exit: GOTO (3111,9525) → `Climb-up` on Ladder at 21:33:35 → varp 510, player surfaced
  at (3111,3127,0). Step 31's abort-gated `tutorial_progress:>=510` verify passed.

The bounded retry loop did precisely its job: one full [reposition → attack → verify]
re-pass instead of a single shot from wherever the bow-handover dialogue left the player.

## Verdict 2 — NEW DEFECT: strict_steps vs. inner-retry-loop bookkeeping (chain-autonomy blocker)

Despite every in-game objective of s08b completing (kill, varp 500, ladder, varp 510), the
section reported **FAIL — 1 step error(s)** and the master chain stopped at 10/13 with
`continue_on_error: False`. Root cause is documented-by-design in
`08_combat_sword_ranged.yaml` (step-28 notes): "strict_steps still flags the SECTION failed
the moment any pass fails." So a transient the inner loop is explicitly built to absorb —
and DID absorb — still ends the run.

For start→mainland autonomy this is blocker-class: any single self-healed variance kills
the chain. Desk direction (engine fix in progress per coordinator): inner-loop-absorbed
failures should not count toward strict_steps when the loop ultimately exits via success;
a 3x-exhausted give-up must still fail the section honestly. No false-pass surface is
opened by this: the loop's own exit path already requires the honest Grammar-1 varp verify
to succeed.

## Verdict 3 — s09a first contact: AMBIGUOUS-NAME TRAP, door edition (honest FAIL)

s09a (`09_banking.yaml`) had never run before tonight — every prior attempt died earlier.
First contact failed in ~2 minutes at the section entrance, with the chain stopping
honestly at the real fault. Receipts (client log, run 3 — **load-bearing for the fix
agent, coordinates verbatim**):

- Step 1 `INTERACT_OBJECT Door Open`:
  - `[GameEngine] Found 0 GameObjects matching 'Door' within 15 tiles`
  - `[GameEngine] Found 5 TileObjects matching 'Door' within 15 tiles (includes WallObjects, DecorativeObjects, GroundObjects)`
  - `[INTERACT-OBJECT] Found TileObject 'Door' as fl at WorldPoint(x=3118, y=3124, plane=0)` —
    **the WRONG door**. The routine's documented entry door is at **(3124,3126)** (file
    header + step-1 notes). Name-only nearest-match resolved to the decoy at **(3118,3124)**.
  - `[NAV-DIRECT] Failed to reach target` → `[INTERACT_OBJECT] Command failed`. The correct
    door was never opened.
- Step 1b `GOTO 3123 3127 0 exact` (the ladder seat): start (3118,3124) → target
  (3123,3127) unreachable through the still-closed correct door. `[NAV-EXACT]` exhausted
  8 hops, `DEFECT-27: refinement exhausted off-target ... one full re-path + refinement
  retry`, 8 more hops, never arrived. Player stuck at **(3123,3125)**.
- Step 2 `INTERACT_OBJECT Ladder Climb-up` from the stuck tile: ladder found at distance 3
  ("already within interaction range"), attempt 1 clicked at 21:39:17 — path blocked, game
  queued the modal. Attempt 2 at 21:39:28–29 fired with the **new jar's diagnostic**:

  > `WARN [MODAL-BLOCK] Interaction (option='Climb-up', target='') attempted while a
  > chatbox modal is queued ("I can't reach that!") — the game will likely register this
  > click as a silent Cancel; drain the modal with CLICK_CONTINUE before interacting`

  `plane:1` await timed out (15s), `on_failure: abort` → section FAIL (2 step errors) →
  chain stopped. `dialogue.open: true` with modal_text **"I can't reach that!"** exported
  in the state file — screenshot receipt with the modal up:
  `journals/images/2026-07-20_malikreyes_s09a_wrong_door_modal.png`.

Root cause: the s09a **entry door is un-pinned and name-ambiguous** — the same
location-is-identity defect class this very file already fixed for its ladder (step-1b
exact seat, attempt #8) and that door-pinning doctrine (9ade455) fixed elsewhere. Step 1
simply predates both. Fix (desk-dispatched): pin the entry door — coordinate-qualified
`INTERACT_OBJECT` ([x y] form, new in jar 421c03e9) targeting **(3124,3126)**, with an
exact seat if the qualifier alone proves insufficient.

Why no restart: deterministic routine defect — a chain restart replays step 1 into the
identical wrong-door resolution. The restart budget was spent once, legitimately, at the
novel varp-510 state (run 2→3); doctrine forbids restarting into a reproducible defect.
Honest abort = successful measurement.

## Also validated tonight (quietly)

- **Master-chain resume/skip-gating, 3 more times over**: run 2 skipped 9 sections at
  varp 490; run 3 skipped 10 at varp 510 including s08b at its own 510 gate — the split
  sections + progress gates compose exactly as designed for mid-island resumes.
- **s08b replay-against-done-objectives**: the expected equip_item replay failures at
  re-entry (run 1: steps 6, 23) retried and marched on per design — the blind drains and
  already-worn handling held.
- **WINDOW_GATE 1 predecessor-refusal**: refused to double-drive when the prior client was
  alive; forced the scoped stop. Rail worked.
- **[MENU-MATCH] logging** (jar 421c03e9): strict-match receipts on every interaction —
  materially better forensics than the prior window's logs.

## Open items handed to the desk

1. s09a entry-door pin fix (agent dispatched; receipts above).
2. strict_steps / inner-loop bookkeeping engine fix (in progress).
3. Gate-4 expected-sha pin check (ticketed).
4. Attempt #13 relaunches after (1) lands — resume point varp 510, s09a from step 1.

## Live minutes

~15 live-client minutes across three windows for: one fix verdict (PASS), one new engine
defect, one new routine defect with a complete fix prescription, and first-live validation
of the new jar's modal export. Truth-per-live-hour did well tonight.
