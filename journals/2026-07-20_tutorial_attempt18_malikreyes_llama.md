# Tutorial attempt #18 — malikreyes/llama — CERTIFICATION retry

**Verdict: DEFECT HARVESTED, not certified this window — and neither fix
under test was reached.** The run aborted honestly at the very first step of
`10_prayer_magic.yaml`: the Phase-1 defensive re-seat (`GOTO 3124 3124 0
exact`, the Account Guide west-door threshold) is **unreachable from the
varp-550 park position** near the chapel. This is the first run ever to
*start* section 10 at varp 550 (attempts #16/#17 entered it at 530 and
advanced through 550 within the run), so this is genuine first-contact with a
mid-section resume — and it exposed that **section 10 is not
resume-idempotent**: its Phase 1–4 steps (Account Guide ceremony, already
credited at varp 531/532/540/550) re-run unconditionally on restart, and the
re-seat geometry assumes the player is still inside/west of the building.
Zero hand-driven game actions were sent. The jar-pin gate (first live pass of
the new gate 4) **PASSED**.

## Run facts

- Run ID: `20260720T060923Z_malikreyes` · ledger `/tmp/manny_runs/20260720T060923Z_malikreyes.json` (llama)
- Launch: `mannyctl llama window malikreyes routines/tutorial_island/00_master.yaml`
  — all 6 gates PASS. Gate 4 (provision) now includes the **jar-pin
  verification** (bdc55b0, task #25): reported `jar_sha=421c03e91ff9e82b` =
  the pin. First live exercise of the gate: **PASS** (no `--accept-new-jar`
  needed, no deviation).
- Preflight: HEAD = `bdc55b0`; `--dry-run` PASS (53 steps);
  `validate_routine_deep` valid, 0 errors/warnings.
- Login: LOGGED_IN in 21s at (3124,3105,0) — exactly the attempt-#17 park.
- Sections 1–12 of the chain: all skipped correctly on varp gates
  (tutorial_progress 550).
- Section 13 (`10_prayer_magic.yaml`): step 1 failed 3× (initial + retry:2),
  strict_steps abort: `Aborting run: Step 1 (GOTO) failed after 2 retries` →
  `CHAIN RESULTS: FAILED, [FAIL] 13 … 1 step error(s)`.
- Timeline (UTC): 06:09:24 run start → 06:09:30–40 walk to wedge point →
  06:14:14 attempt-1 GOTO fail → 06:17:15 attempt-3 (retry 2/2) GOTO fail →
  ~06:18:25 chain abort, run pid exited cleanly (watchdog observed, not
  killed) → 06:21 `mannyctl llama stop malikreyes` (SIGTERM pid 947799,
  scoped). ~9 live minutes.
- Hand-driven game actions: **0 of target 0.** No relog, no stall-protocol
  restart, no rescue. Watchdog independently logged `stall_detected` at
  06:13:25 (180s) and `stall_continuing` at 300s/421s — no intervention.
- Ban signals: none. One boot-phase NPE in the ledger
  (`Cannot read field "am" because "xz.ch" is null`) — the known-benign boot
  signature seen on every recent attempt; client pid 947799 stayed alive and
  exporting state throughout.

## Fix-under-test verdicts

### 52a2f76 fix 1 — step 17 chapel walk `GOTO 3130 3107 0 exact`: **NOT REACHED**
The run died at step 1; step 17 never executed. No verdict this window.

### 52a2f76 fix 2 — Brace verify-after-drain reorder (talk → drain → WAIT >=570): **NOT REACHED**
Same — no verdict this window.

### bdc55b0 gate-4 jar-pin verification: **VALIDATED (pass path)**
First live launch through the gate. Build-path jar sha matched the pin
(`421c03e91ff9e82b`), gate 4 PASS, provision proceeded with stash discipline
verified. The fail path remains untested (would require a mismatched jar).

### 7f6475d absorbed-failure bookkeeping: **NOT EXERCISED**
No `[LOOP] absorbed N transient failure(s)` line; no bounded inner retry loop
ran before the abort.

## The harvested defect — section 10 is not resume-idempotent (NEW class for this file)

**What happened, with receipts:**

Step 1 is the Phase-1 "defensive re-seat" at the Account Guide **west** door
threshold: `GOTO 3124 3124 0 exact`. It was written for the 09b→10 handoff,
where the player stands inside the bank building at ~(3124,3124) already
(attempt #16's CSV row: the re-seat passed trivially; attempt #17: passed
after internal hop retries). This run started instead from the varp-550 park
at (3124,3105) — **outside, south of the building, past the east door** —
because attempt #17 aborted mid-section after crossing it.

Location-history receipt (`/tmp/manny_malikreyes_location_history.json`,
06:09:30–40Z): the pathfinder walked north up the **east** side —
(3125,3106) → (3129,3107) → (3131,3113) → (3134,3116) → **through the
east-door landing tile (3134,3124)** → (3134,3128) → then west along the
y=3129 row: (3133,3129) → (3131,3129) → **(3127,3129), wedged**. That is 5
tiles Chebyshev from the target (3124,3124), with the bank building's north
wall between them.

Client-log receipt (`/tmp/runelite_malikreyes.log`), repeated across all 8
exact-mode hops of all 3 attempts:

```
[NAV-DIRECT] Stuck at (3127, 3129), 5 tiles from target
[NAV-EXACT] Hop 8/8: 5 tile(s) to exact target tile
  Screen Click: (630, 104) | Option: "Cancel" | Action: CANCEL (ID: 1006)
[NAV-EXACT] Exhausted 8 exact-arrival hops, still not on target tile
[NAV-EXACT] DEFECT-27: still off exact target tile after re-path - reporting exact-arrival FAILURE
[GOTO] Exact-arrival GOTO failed (partial): ended at (3127, 3129, 0), 5 tile(s) from target (3124, 3124, 0)
```

Every refiner right-click on the target tile produced an **empty menu**
("Cancel", widget 0) — the blocked-tile signature from the door-crossing
doctrine: (3124,3124) is not click-reachable from the north side of the wall.
The greedy minimap follower had already gone as far as it could; retries
produced zero further movement (position pinned at (3127,3129) for 8+
minutes). DEFECT-27's honest exact-arrival failure reporting worked exactly
as designed, as did `on_failure: retry:2` → strict_steps abort. **The
primitives were honest; the routine's resume geometry is the defect.**

Screenshot (IP overlay redacted, raws deleted on both hosts):
`journals/images/2026-07-20_malikreyes_attempt18_s10_step1_reseat_wedge.png`
— player visibly wedged on the north side of the bank building, minimap
confirming position; inventory/session normal.

**Defect statement:** `10_prayer_magic.yaml` re-runs its Phase 1–4 Account
Guide ceremony (steps 1–15) unconditionally, even when `tutorial_progress`
proves those phases are already credited (531/532/540/550 all ≤ current varp
550). The master chain gates *sections* on varp but nothing gates *phases
within* this section. On any mid-section resume past the east door, step 1
walks the player to an unreachable seat and burns the whole run.

**Fix direction for the next desk window (NOT applied this run — hands-off
doctrine):** phase-level varp skip-gates inside section 10, mirroring the
master chain's section gates — e.g. skip the Phase 1–4 steps when
`tutorial_progress >= 550` and enter directly at the chapel phase (step 16+).
This is the same resume-idempotency pattern the master chain already proved
13 times over at section granularity. Alternative/complement: make the
defensive re-seat conditional on varp < 550 rather than positional.

Worth noting: had the resume skipped to the chapel phase, this run would have
delivered verdicts on both 52a2f76 fixes — the certification blocker is now
purely this resume gap plus the two untested fixes.

## Account state at wrap

`malikreyes` parked at (3127,3129,0), varp-281 = 550, plane 0, healthy, no
ban signals, single client process throughout, stopped scoped via
`mannyctl llama stop malikreyes`. The park position moved from the chapel
side to the north side of the bank building — the next attempt's resume will
start from (3127,3129), which the phase-gate fix must tolerate (it does:
chapel GOTO from there is plain-mode open ground).

## Varp timeline

| time (UTC) | varp 281 | position | event |
|---|---|---|---|
| 06:09:24 | 550 | (3124,3105) | launch, all 6 gates PASS (jar-pin first live PASS) |
| 06:09:40 | 550 | (3127,3129) | step-1 walk wedges on north wall |
| 06:14:14 | 550 | (3127,3129) | GOTO attempt 1 honest fail (DEFECT-27 path) |
| 06:17:15 | 550 | (3127,3129) | GOTO attempt 3 (retry 2/2) honest fail |
| 06:18:25 | 550 | (3127,3129) | strict_steps chain abort — terminal |
| 06:21 | 550 | (3127,3129) | client stopped, scoped |

Certification streak: eleven consecutive runs with zero hand-driven game
actions (this run included). The chain remains uncertified only because varp
1000 has not yet been reached hands-free on this account.
