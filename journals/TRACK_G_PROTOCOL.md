# Track G Protocol — the "Close the Loop" milestone final exam

**Status:** NOT YET RUN. Gated on: live lane (tutorial→E1 stat grind) done, DEFECT-26 deployed + 4-gate
passed, Java deployment window landed + live gates passed, E2 attended gate passed. See
`journals/OVERSEER_HANDOFF.md` → "Sequence" for exact ordering. Do not start Track G before all of these
are checked off.

**Two-lane note:** as of the 2026-07-19 refresh, Track G runs on **lane 1 (`newbakshesh`) only**.
**⚠️ `newbakshesh` banned 2026-07-19 — account undecided pending user.** Do not start Track G on
`newbakshesh` until a replacement account is chosen. Lane 2
(`blast`) may be mid tutorial-regression concurrently on a separate display — that is expected and does
not block Track G. The fresh session's starting prompt must make explicit that it owns ONLY the
`newbakshesh` account/lane; it must not touch `blast`.

## Purpose

Prove an LLM session can **MAKE and RUN a money-maker given only the on-ramp** — not given the corpus,
not given the defect history, not given a human coaching it through failures. This is the definition of
done for the whole "Close the Loop" milestone.

**Definition of done (from the plan):** a fresh LLM session, given ONLY `ROUTINE_SCHEMA.md` +
`validate_routine_deep` + the `manny-diort` MCP endpoint, authors/refines a cowhide-grind variant and
runs it **4+ hours unattended on diort** with the watchdog ledger showing clean completion or correct
intervention.

If the on-ramp is sufficient, this session should need nothing else. Every point where it stalls and
needs something outside the on-ramp is itself a finding — see "Observation rules" below.

---

## Preconditions checklist

Check ALL of these before launching the fresh session. If any box is unchecked, Track G is not ready —
go finish that item first, do not proceed "just to see."

- [x] Tutorial Island complete on `newbakshesh` (07→10→mainland verified, `36d5443`)
- [ ] E1 stat-training grind complete: att/str/def ≈ 20/20/20 via combat-style rotation
      (`SWITCH_COMBAT_STYLE` now works via a combat-tab widget click, per the DEFECT-26 Java fix — the old
      F1-keybind approach was a silent no-op, so a pre-DEFECT-26 grind may have trained only one stat). The
      830-feather run exposed DEFECT-26 before the stat target was reached cleanly — redo as a managed run
      once DEFECT-26 is deployed, rotating style each pass so all three of att/str/def actually advance
- [ ] **DEFECT-26 deployed + 4-gate passed** (blocking, `STOP` halts a running loop, dual-launch is
      rejected, combat style switch works via widget click) — this is a **blocking** precondition, not
      optional; Track G's own monitor-not-executor doctrine depends on `STOP`/loop-blocking actually working
- [ ] Java deployment window landed: jar with DEFECT-20/21/22/22b/23/24/25/26 provisioned to diort
      (nav-stack + 24/25/shadow-mode deployed in window #2; DEFECT-26 deploying in window #3)
- [ ] Deployment live gates passed: DEFECT-25 (live-hull NPC click), DEFECT-24 (multi-page monologue),
      shadow-mode (zero behavior change) — all PASS as of window #2; DEFECT-22c is PARTIAL/deprioritized,
      not a Track G blocker
- [ ] E2 attended gate passed: `cowhide_banking.yaml` run attended, ≥2 consecutive kill→bank cycles,
      **including both directions of the bridge crossing** (this also closes out DEFECT-21's live gate)
- [ ] **Watchdog ledger shows `running` for the full batch duration on a test run** — i.e. before trusting
      Track G's own multi-hour ledger, confirm on a short attended run that the ledger doesn't report
      `completed` early (the old 60s-completed lie was itself a DEFECT-26 symptom)
- [ ] Account confirmed: `newbakshesh` (never `main`, never the banned `new`; never `blast` — that's lane 2)
- [ ] No other driver session holds the `newbakshesh` client — verify ALL THREE (lane 2 / `blast` activity
      on its own display is fine and does not need to be checked here):
  - [ ] `/tasks` (Claude Code tool) — no other agent/task shown running or recently-active against this repo
  - [ ] `mannyctl diort runs` — no ledger entry with `status: running` for `newbakshesh`
  - [ ] `pgrep -f run_routine.py` on diort (`ssh diort 'pgrep -f run_routine.py'`) — empty, or only a
        `blast`-scoped process

If the `pgrep`/`/tasks`/`runs` checks disagree (e.g. a process is running but no ledger, or a ledger says
running but no process) — STOP. That mismatch is exactly the dual-driver failure mode from the mystery
run `20260719T014238Z` (see `OVERSEER_HANDOFF.md`). Resolve it before launching Track G.

---

## The exact starting prompt

Give the fresh session ONLY this. Do not add context, do not pre-answer questions, do not paste in
history from this milestone. Copy-paste verbatim:

```
You are driving the manny-diort MCP endpoint to author and run a money-making
routine for an OSRS-style game client on a remote host called diort.

What you may read:
- ROUTINE_SCHEMA.md (the authoring reference for the routine YAML format)
- the validate_routine_deep tool (validates a routine file and reports errors)
- the manny-diort MCP server's tool list (call it to see what's available —
  game-state queries, command sends, routine run/monitor tools)

What you must NOT read:
- anything under journals/
- git log / git blame / commit history for this repo or the manny plugin repo
- any existing routine's revision history or the corpus-fix history
The point of this exercise is to prove the schema doc and the validator are a
sufficient on-ramp on their own. If you find yourself needing to read source
code or git history to succeed, note exactly what question you couldn't
answer from the schema doc alone and say so explicitly before proceeding.

Your task:
1. There is an existing money-maker routine at
   routines/money_making/cowhide_banking.yaml (kills cows in a field, loots
   hides, banks them in a loop). Author a VARIANT of it — change something
   concrete, e.g. different waypoint spacing on the travel legs, a different
   kill-batch size, or a different loot/bank threshold. Do not just copy the
   file unchanged.
2. Validate your variant with validate_routine_deep until it reports 0
   errors.
3. Launch it via mannyctl on diort as a DETACHED run (mannyctl diort run
   <your_routine.yaml> --account newbakshesh), so it has a watchdog + run
   ledger.
4. Monitor it — you are a MONITOR, not an executor. Poll the run ledger and
   get_game_state at sensible intervals (e.g. every 5-15 minutes for a
   multi-hour run, not continuously). Only intervene if something is
   genuinely stuck (idle with no progress for a long window, repeated
   errors, a crash) — not for normal retries or brief pauses. This is the
   monitor-not-executor doctrine.
5. Let it run for at least 4 hours of wall-clock time.

Evidence to produce at the end:
- the run_id
- the final watchdog ledger JSON (status, events, temp history) — the ledger's `running`→`completed`
  transition must match the actual grind duration (elapsed time close to the real multi-hour run); a
  ledger reporting `completed` after ~60s while the routine kept running live is a FAIL signal (this was
  the exact DEFECT-26 symptom, now fixed — treat a recurrence as a regression, not a quirk)
- `active_loop` visibly advancing across successive `get_game_state`/state-snapshot polls during the run
  (confirms the loop-blocking fix is actually in effect for this run, not just deployed)
- XP and gold-piece deltas over the run
- count of cowhides banked
- any interventions you made, and your reasoning for each

Work autonomously. If you get stuck on something the schema doc and
validator don't answer, say exactly what's missing and what you tried
before falling back to reading anything outside the allowed set.
```

---

## Pass/fail rubric

**PASS** requires ALL of:
- 4+ hours wall-clock run time
- Ledger status = `completed`, OR a justified intervention (documented reasoning, not a panic-stop)
- Hides visibly accumulating in the bank across the run (not stuck at zero, not draining)
- No dual-driver events (no second process/ledger touching the same account mid-run)
- Temps stayed ≤ the diort plateau (~70-74°C observed historically; treat a sustained climb toward the
  88°C watchdog refuse threshold as a near-fail even if the watchdog caught it correctly)

**FAIL modes — record which one, and file it as a defect against the on-ramp, not against the session:**
- **Schema-doc gap** — the session had to read source code or git history to proceed. This is an on-ramp
  defect: something `ROUTINE_SCHEMA.md` should have said but doesn't. File it.
- **Validator miss** — `validate_routine_deep` passed a routine that then broke live. File the missed
  check class against the validator (mirrors how the 7 corpus-bug classes were found).
- **Nav stall** — the follower got stuck (bridge, door, uncached tile) despite DEFECT-21/23 landing. Note
  whether Nav Stage-2 (`NAV_STAGE2_PLAN_2026-07-18.md`) would have prevented it.
- **Thermal** — watchdog SIGTERM'd on temp before 4 hours elapsed. Not itself an on-ramp defect, but
  record it (diort thermal budget under sustained load may be tighter than the smoke-test data showed).

A FAIL is not a failed milestone — it's a found defect. Re-run after the defect is fixed.

---

## Observation rules for the overseer

The overseer (you, running this protocol) watches. Do not help.

- **Watch, don't help.** Do not answer the fresh session's questions, do not nudge it toward the right
  waypoint spacing, do not pre-empt a mistake you can see coming. If it asks something and there's no
  channel back to you, that silence is the test.
- **Every question the fresh session would need answered = a documentation defect to log.** If, watching
  its transcript/tool calls, you can tell it's about to ask "what does `stop_conditions` do again" or
  "how do I know if this loop is flat or nested" — and the schema doc already covers that — good, no
  defect. If it's NOT covered and the session stumbles, that's the defect, write it down verbatim (what
  it needed to know, where in the schema doc it should have been but wasn't).
- **Log interventions it takes on its own, not ones you make.** Track G measures the session's judgment,
  not the overseer's. If you intervene, the run is disqualified from PASS and becomes a FAIL with cause
  "overseer intervention" — note why you broke the no-help rule (e.g. genuine safety issue like account
  risk) so it's distinguishable from a session failure.
- **Journal the result** in `journals/` (new dated entry) regardless of PASS/FAIL, per the global
  journaling convention — this is the milestone's capstone artifact.
