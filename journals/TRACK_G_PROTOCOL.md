# Track G Protocol — the "Close the Loop" milestone final exam

**Status:** NOT YET RUN. Gated on: live lane (tutorial→E1 stat grind) done, Java deployment window
landed + 3 live gates passed, E2 attended gate passed. See `journals/OVERSEER_HANDOFF.md` → "Sequence"
for exact ordering. Do not start Track G before all three are checked off.

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

- [ ] Tutorial Island complete on `newbakshesh` (07→10→mainland verified)
- [ ] E1 stat-training grind complete: att/str/def ≈ 20/20/20
- [ ] Java deployment window landed: jar rebuilt with DEFECT-20/21/22/22b/23/24, provisioned to diort
- [ ] 3 deployment live gates passed: DEFECT-22b (banned `new` login), DEFECT-23 (exact-arrival GOTO),
      DEFECT-24 (multi-page monologue)
- [ ] E2 attended gate passed: `cowhide_banking.yaml` run attended, ≥2 consecutive kill→bank cycles,
      **including both directions of the bridge crossing** (this also closes out DEFECT-21's live gate)
- [ ] Account confirmed: `newbakshesh` (never `main`, never the banned `new`)
- [ ] No other driver session holds the client — verify ALL THREE:
  - [ ] `/tasks` (Claude Code tool) — no other agent/task shown running or recently-active against this repo
  - [ ] `mannyctl diort runs` — no ledger entry with `status: running` for `newbakshesh`
  - [ ] `pgrep -f run_routine.py` on diort (`ssh diort 'pgrep -f run_routine.py'`) — empty

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
- the final watchdog ledger JSON (status, events, temp history)
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
