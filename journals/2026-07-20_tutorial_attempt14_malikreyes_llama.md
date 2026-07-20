# Tutorial attempt #14 — malikreyes/llama — CERTIFICATION retry

**Verdict: DEFECT HARVESTED, not certified this window.** Chain honestly aborted
in `09_banking.yaml` at step 6 (poll booth), one step later than attempt #13.
Zero hand-driven game actions were sent — the run stayed fully hands-off from
launch to terminal stop. The BANK_CLOSE fix under test (91499ee) executed
exactly as designed and reported success on the first try (no retries needed)
— but live evidence proves its own ground-truth check, `isBankOpen()`, returned
a **false negative**: the real bank interface was still fully open on screen
when BANK_CLOSE said "already closed." This is a new, deeper defect than
attempt #13's (which was a blind, unverified `KEY_PRESS Escape`) — the
*verification* primitive itself is unreliable for this bank interface
instance, not just the close action.

## Fix-under-test verdict

### 91499ee — BANK_CLOSE ground-truth bank close: **EXERCISED, NOT VALIDATED — exposes a deeper defect**

Client log receipt (`/tmp/runelite_malikreyes.log`, 22:11:18 PDT):
```
[BANK_CLOSE] Executing command
[BANK_CLOSE] Closing bank
BankingSupport - Attempting to close bank...
BankingSupport - Bank is already closed
[BANK_CLOSE] Bank closed successfully
[BANK_CLOSE] Command succeeded
Command executed successfully: BANK_CLOSE
```
No retries were used (unlike the mission brief's anticipated "exhausts 3
retries" failure mode) — BANK_CLOSE reported success on attempt 1, because
`isBankOpen()` returned `false` immediately, before any ESC-driven close was
even needed by its own logic ("Bank is already closed", not "closed it").

The very next step (6, `INTERACT_OBJECT Poll_booth Use`) then failed 3 step
executions × 3 internal click attempts = 9 total attempts, all with the
identical signature: the poll booth object *was* found correctly (single
TileObject at the documented (3119,3121,0), distance 2 tiles, "already within
interaction range") but the right-click menu built for it contained **only
`Cancel`** — no `Use`, no `Examine`, no `Walk here` — the exact single-entry
degraded-menu signature of a modal capturing world clicks.

A screenshot taken immediately after the abort
(`journals/images/2026-07-20_malikreyes_attempt14_pollbooth_fail.png`)
settles it: **"The Bank of Gielinor (25)" is still fully rendered and open on
screen**, itemized with the 25gp starting stack, with the game's own tutorial
hint text visible underneath it: *"Poll booths — Now it's time for a quick
look at polls. Just click on the indicated poll booth to continue."* This is
visually identical to attempt #13's screenshot receipt — but this time
`BANK_CLOSE`'s own verification claimed the bank was not open at all.

**Conclusion:** `BankingSupport.isBankOpen()` (the ground-truth check
`BANK_CLOSE` relies on, `PlayerHelpers.java:2619` / `BankingSupport.java:672`)
does not correctly detect this bank interface instance's open state — likely
because the tutorial-island bank widget uses a different widget group/child
than whatever `isBankOpen()` actually inspects, or because the check reads a
flag that isn't set on this code path. The ESC dispatch may or may not have
fired at all (moot either way, since the check downstream of it is the one
that's wrong). This is a **new candidate defect** (call it DEFECT-33 pending
triage) one layer beneath 91499ee: the fix correctly *added* ground-truth
verification in place of a blind keypress, but the ground-truth oracle itself
is unreliable for tutorial-island banks specifically. Do not conflate this
with attempt #13's defect — that one was "no verification at all"; this one is
"verification present, but reading the wrong signal."

### 7f6475d — absorbed transient failures in bounded inner retry loop: **NOT EXERCISED**
No `[LOOP] absorbed N transient failure(s)` line appeared in either the run
log or the client log this window. Section 09a has no bounded inner retry
loop of the class this fix targets.

## Timeline

- **~04:47Z** — Preflight: `git log` confirmed HEAD at `91499ee`. `./run_routine.py
  --dry-run routines/tutorial_island/00_master.yaml` PASSED (53 steps
  simulated, RESULT: PASS).
- **05:10:50Z (launch)** — `mannyctl llama window malikreyes 00_master.yaml` —
  all 6 gates PASS. Predecessor-dead, credentials (`default: punitpun`,
  malikreyes not banned), display `:9`, provision (stash/pop/verify clean,
  jar_sha=421c03e91ff9e82b), login gate (LOGGED_IN in 21s at (3120,3123,0),
  login_index 10 — matches the parked position exactly), run+watchdog
  detached (run_id `20260720T051050Z_malikreyes`).
- **~05:10:51Z** — client boot logs one benign `NullPointerException: Cannot
  read field "am" because "xz.ch" is null` at `UITools$WidgetInspectorTool`
  during `Game State: STARTING` (client.java:25197, widget-tree refresh
  debug tool). Matched the watchdog's `mcptools` crash signature (known
  false-positive class, same as attempt #13) — client process (pid 935378)
  stayed alive and running for the entire window, confirmed via `pgrep`
  post-abort. Not a real crash; no intervention taken.
- **~05:10:51Z–~05:11:16Z** — chain replayed sections 1–10 (character creation
  through `08_combat_sword_ranged`), all instantly skipped via the
  `tutorial_progress >= gate` resume logic (account parked at varp 520, past
  all 10 of those gates). Zero live commands sent for these — pure gate
  arithmetic.
- **~05:11:16Z** — section 11/13, `09_banking.yaml` ("Section 9a: Banking"),
  begins live execution — the only section that actually ran this window.
  - Steps 1/1a/1b (entry door seat/open/through-walk) — PASS, no-ops (player
    resumed already past the door, inside the bank room).
  - Steps 2/3 (ladder climb up/down, coordinate-qualified) — PASS (22:11:12
    PDT, `Climb-down` menu-verified and clicked correctly on attempt 1).
  - Step 4 (`Bank_booth Use`) — reported PASS (22:11:16–18 PDT):
    menu-verified `Use` click on the correctly-named `Bank booth` object
    (disambiguated from a co-located `Closed bank booth` decoy visible in the
    same menu scan — name-matching worked correctly here).
  - Step 5 (`BANK_CLOSE`) — reported PASS on first try, 22:11:18 PDT — but
    per the fix-verdict above, its own ground truth was wrong: the bank was
    visibly still open.
  - Step 6 (`INTERACT_OBJECT Poll_booth Use`) — **FAILED**, 3 total step
    executions (22:11:20, 22:11:28, 22:11:36 PDT) × 3 internal click attempts
    each = 9 total menu-click attempts, all identical: object found correctly,
    menu built with only `Cancel`. `on_failure: retry:2` exhausted.
  - `strict_steps: true` marked section 11 FAILED; chain stopped honestly at
    "Aborting run: Step 6 (INTERACT_OBJECT) failed after 2 retries: Could not
    find or interact with Poll booth."
- **~05:11:51Z** — watchdog observed run pid 935652 gone, marked run
  `status: dead` (this is the `run_routine.py` process exiting normally after
  the chain's own honest-abort logic, not a crash — client process 935378
  stayed up throughout).
- **~05:12–05:14Z** — investigation: full log windows pulled from both
  `/tmp/manny_run_malikreyes.log` (chain-level) and `/tmp/runelite_malikreyes.log`
  (client-level, `BANK_CLOSE`/`MENU-MATCH`/`Poll booth` context). Screenshot
  captured via `DISPLAY=:9 import -window root` (no mannyctl/MCP screenshot
  tool registered in this session) and copied to
  `journals/images/2026-07-20_malikreyes_attempt14_pollbooth_fail.png`.
- **~05:15Z** — `mannyctl llama stop malikreyes` — clean scoped SIGTERM stop
  (pid 935378).

## Final state
- varp-281 = **520** (unchanged from the parked value; poll booth was never
  successfully used).
- Position: **(3120, 3123, 0)** — the bank_booth tile, unchanged from login.
- Account healthy, no ban signals, client cleanly stopped, single process
  verified throughout (no dual-driver risk).

## Hand-driven game actions: **0**
No clicks, walks, interactions, dialogue, or camera commands were sent by the
supervisor. All supervisor actions were infra-only: launch (`mannyctl window`),
read-only log/state polling, one passive screenshot capture, and the terminal
stop.

## Open items / next fix direction
- **DEFECT-33 candidate (Java, `BankingSupport.isBankOpen()`):** returns
  `false` for a bank interface that is visibly open on the tutorial-island
  bank variant. Needs a desk read of `BankingSupport.java:672` and
  `PlayerHelpers.java:2619` against the actual widget group/child the
  tutorial bank renders under (likely differs from the standard "Bank of
  Gielinor" interface's usual group id, or the check tests a state flag this
  code path never sets). Until fixed, any `BANK_CLOSE`-gated step on tutorial
  island first-contacts this same false-negative.
- Do not resume live testing on this section until DEFECT-33 is fixed and
  desk-verified (`validate_routine_deep` + `--dry-run` do not catch this
  class — it is a live widget-state bug, invisible to both).
- 09_banking.yaml's own step 5 notes (residual risk section) already flagged
  a widget-click fallback as the "durable fix" if ESC alone proved
  insufficient — this run shows the fix needs to go one level deeper, into
  the verification check itself, not just the close mechanism.
