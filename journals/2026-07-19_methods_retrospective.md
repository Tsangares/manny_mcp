# 2026-07-19 — Methods retrospective: how we've been working, and how we should

**Author:** overseer fork (reflection pass, no execution). **Scope:** the whole plot — environment
revival → architecture review → 7-wave refactor → diort migration → Close-the-Loop milestone
(tutorial automation, defect loops, nav stage-2, two-lane operation). This is about *how* we work,
not what we built; the what lives in the stage journals. Audience: the user, and every future
overseer session that should inherit better methods rather than just more state.

---

## The single most important observation

Step back far enough and the entire campaign has one governing variable: **truth extracted per
live-client-hour.** The live client is the only oracle for an entire class of bugs — stale-tile
clicks, dialogue false-closes, login-screen internals, loop-thread races — and there is a hard,
small budget of live hours (one lane for most of the campaign, two now, capped at 8h per client).

Every method that worked, worked because it raised truth-per-live-hour. Every burn, burned because
it wasted live hours extracting one bit of truth ("this step fails") when the same hour could have
yielded thousands (full event logs, shadow comparisons, recorded state streams). This lens should
be the standing test for any proposed process change: *does it increase what we learn per live hour,
or does it spend live hours to learn what we could have learned at a desk?*

---

## What worked, and why it worked mechanically

**Offline-first construction (nav stage-2).** The entire replacement navigation engine — vendored
collision data, A*, transport execution — was built and verified with 90 offline assertions across
three stacked branches before a single live minute was spent. Deployment then cost one merge and
zero surprises. Mechanically: the work was decomposed so that everything *provable at a desk* was
proven at a desk, and the live client was reserved for the residue that genuinely needs it.

**Shadow mode.** Rather than gambling a live gate on the new engine, it rides along silently,
logging one comparison line per navigation. Live risk: zero. Live data yield: continuous. This is
the purest example of raising truth-per-live-hour — the grind that trains defence is
*simultaneously* soaking the nav engine. Every future subsystem replacement should ship a shadow
mode first; the pattern is now proven twice over (it also told us the engine loads in 168ms and
5MB, retiring a hardware risk without a test).

**Unconditional diagnostics (the post-22b doctrine).** DEFECT-22b's live gate failed *blind* — the
only logging lived inside the branch that never executed, so a full deploy window taught us almost
nothing. The fix ("log the check unconditionally, every pass") turned the next window into a
definitive answer (ban text isn't in String fields at all). Blind gates are the single most
expensive failure mode we have; a diagnostic line costs nothing and is the difference between a
window that answers a question and a window that raises one.

**Batched deployment windows.** Rebuild + provision + restart + re-login costs real time and burns
account/session continuity, so batching several defect gates per window amortized it well. Window
#3 gated four DEFECT-26 behaviors, restarted a lane, launched a second lane, and ran a thermal
probe in one restart cycle.

**Canonical-path convergence.** DEFECT-25 (the pacing-NPC click race) was not a missing feature —
the correct in-flight hull-tracking click had existed since the refactor. The bug was a *variant*:
a private static-point click that bypassed it. The user's standing rule ("fix the canonical path,
never add variants") is the cheapest bug-prevention method we have, and it was proven right in the
most literal way possible: the fix was deleting a workaround, and it passed live on attempt one.

**The handoff doc as the only durable state.** This session has been compacted multiple times and
delegated to a dozen-plus agents; `OVERSEER_HANDOFF.md` is why nothing was lost. The mechanical
insight: agent context is *ephemeral by design*, so anything that must survive gets written to the
repo within minutes of being learned, and the doc is aggressively curated (appended per window,
with compaction notes naming in-flight agents and resume pointers).

**The user as a cheap oracle.** Twice, one sentence from the user collapsed hours of
investigation: the hull-click prior art tip, and "seems like your str is high" (which exposed that
the grind had been training the wrong stat for its whole run). The method implication: surface
observable state to the user early (the mjpeg viewers earned their keep the same day they were
built) and treat their domain memory as a first-class diagnostic source.

**Watchdog + run ledger on every run.** Since the doctrine landed, no run is a mystery. The ledger
even became a *diagnostic instrument*: the "completed after 60s" signature is how DEFECT-26 is
detected operationally.

---

## Where we burned time that better methods would have saved

**Defects were discovered one per live collision instead of harvested in sweeps.** DEFECT-22, -24,
-25, -26, -27 were each discovered by a live run failing, then diagnosed, then fixed, then
re-gated — roughly 1–2 hours per loop, strictly serialized. But look at what discovered them:
almost always a *missing log line*. A deliberate "instrument everything" pass early in the
campaign — dialogue state transitions, widget open/close, login index changes, click
target-vs-actual, nav decisions, loop thread lifecycle — would have cost one deploy window and made
most of these bugs visible in the *first* live run's logs rather than in the fifth live failure.
We arrived at this doctrine incrementally (each defect added its own unconditional line); we should
have adopted it wholesale after the first blind gate.

**The second lane came late.** The thermal probe showed two-client headroom well before lane-2
plumbing existed. Live bandwidth was the campaign's scarcest resource, and doubling it was
achievable earlier for about a day of namespacing work. The general lesson: when a resource is the
known bottleneck, capacity work on it outranks feature work almost automatically — we sequenced it
behind several defect fixes that then had to queue on the single lane they could have shared.

**Desk-verified routines rarely survived first live contact — and that was a primitives problem,
not an authoring problem.** Tutorial sections were transcribed carefully, validated, coordinate-
checked against wiki pins — and still failed live, over and over, for the same few reasons: GOTO
silently tolerated 3-tile misses, dialogue state lied mid-monologue, clicks aimed at stale tiles,
and (discovered today) even `exact` mode could report success while off-target. Authors were
writing correct routines against dishonest primitives. Once the primitives were made honest (exact
arrival, live-hull click, blind-repeat dialogue exhaustion, DEFECT-27's honest failure), routine
fixes became one-line recipe adjustments instead of investigations. **First-contact survival is a
function of primitive honesty.** The corollary: any primitive that can fail silently is a standing
tax on every routine ever written against it.

**Agent-coordination incidents: our rules treat symptoms.** The dual-driver ghost (a "finished"
agent silently resuming and driving the account in parallel) and the branch collision (two agents
sharing one working tree) each cost real cleanup time. We responded with memory rules —
one-tree-one-agent, verify-predecessor-dead — which work, but only as long as every future session
remembers them. The structural fixes are cheap and mechanical: per-agent git worktrees (the harness
supports isolation natively), and an *ownership lockfile* — a small on-disk record naming which
agent currently owns each contended resource (account, display, working tree), checked by tooling
rather than by prompt discipline. Rules that live in tooling don't need to be remembered.

**Supervision semantics had to be nudged in.** The lane-1 supervisor twice ended its turn believing
monitoring would continue by itself. Fire-and-forget delegation is the wrong shape for open-ended
supervision; the working pattern (an on-host watcher process that exits on trigger conditions,
re-invoking the agent, plus a heartbeat) had to be corrected into place mid-flight. This should be
a standing template in the delegation playbook, not something each supervisor rediscovers.

**Small operational losses from missing checklists.** ~830 feathers evaporated in a client restart
because "harvest/bank inventory before restart" wasn't on the window checklist. Trivial individually;
the class (state lost at lifecycle boundaries) is worth a standing checklist item per window.

---

## Are we measuring the right things?

Mostly no. We track defects (well) and gates (well), but not the *economics*: cost per defect in
live-hours and agent-tokens, deploy-window cadence, xp/hr against plan, or the most decision-
relevant number we have — **first-contact survival rate of desk-verified routines**. That last one
is the direct measure of whether the MAKE half of the prime directive is getting easier, which is
the whole point of the milestone. Today we know it anecdotally ("rarely, but improving since exact
mode"). A one-line-per-run record — routine, first live attempt pass/fail, failure class — would
turn the campaign's central question into a chart. All the raw material already exists in run
ledgers and journals; nothing aggregates it.

---

## The routine-authoring loop: shortest path to first-contact success

The end state is an LLM authoring routines that mostly work on first live contact. Ranked by
leverage per unit cost:

1. **Honest primitives everywhere** (mostly done, keep going): exact arrival, hull clicks, honest
   GOTO failure, blind-repeat dialogue. Each honest primitive retires a whole failure class for
   every current and future routine.
2. **Recipe reuse over recipe copying:** the validated multi-step recipes (chapel exit, ladder
   gate, furnace seating) currently live as YAML fragments that get re-derived or copy-pasted.
   Promoting them to named, parameterized macros in the schema means an authoring LLM composes
   proven blocks instead of re-earning them live.
3. **Replay lint — dry-run routines against recorded state:** the validator catches structural
   bugs; the live client catches world-state bugs; nothing in between. A mode that executes a
   routine's control flow against *recorded* state-JSON streams (which every run already produces)
   would catch await-conditions referencing absent fields, conditions that can never fire, and
   loop-exit mismatches — at a desk, against real data. This is the biggest remaining gap; a
   full simulator is absurd, but replaying our own recordings is not.
4. **More validator checks** — real but diminishing returns; the 7-check upgrade already caught the
   structural classes it can see.

---

## Delegation economics: the standing pattern

What the campaign has converged on, stated explicitly so future sessions inherit it:

- **Overseer stays thin.** Orchestration, state curation, dispatch, and synthesis only; all
  execution delegated. This is why the session has survived repeated compaction without losing the
  campaign thread — the thread lives in the handoff doc, not in context.
- **Self-contained agent prompts** (~1–2k words: mission, evidence, constraints, report shape)
  have needed remarkably few corrections. The corrections that *were* needed clustered in one
  place: turn-holding semantics for supervisors. Template that pattern.
- **Tier by judgment density, not difficulty:** live driving and deep Java diagnosis → top tier;
  well-specified builds → mid tier; mechanical sweeps → low tier. The one mis-tier signal so far:
  open-ended *supervision* has more judgment density than its task description suggests.
- **Fire-and-forget for bounded tasks; watcher + heartbeat for open-ended ones; forks for
  reflection** that needs full campaign context (this document).
- **One contended resource, one owner, verified dead before succession** — soon to be enforced by
  lockfile rather than memory, per above.

---

## Risk posture, honestly

**Behavioral detection is demonstrated, not hypothetical.** GrimmsFairly was banned for "serious
rule breaking" on a residential IP — the detection was behavioral. Our current click/timing
patterns are therefore a *standing* risk to the two remaining accounts, and Track G is deliberately
our longest unattended exposure yet. The 8h session cap and the canvas-level event dispatch help
incidentally, but nothing in the stack currently randomizes inter-action timing, click-point
distribution within hulls, breaks, or camera/idle behavior. The pragmatic position: run Track G as
planned (one bounded 4h proof), but treat a humanization pass as a *prerequisite for making long
unattended grinds routine* — the prime directive is an LLM that runs routines continuously, and
continuously-run robotic patterns on a fresh account is exactly the profile that got the last
account banned.

**Thermal method is a quiet success story:** probe before commit, live measurement over assumption
(taxi was contraindicated by a 2-minute measurement, not a guess; diort's two-client headroom was
probed before the second lane launched; every window reports a temp table). Nothing to change.

**The 8h cap** is user-imposed and costs little (lanes alternate), and doubles as mild ban-risk
hygiene. Keep enforcing it in scheduling (Track G must start early enough in a client window).

---

## The shortlist: next 5 method changes worth their cost

1. **Ownership lockfile for contended resources** — *adopt now; ~1 hour.* A small on-disk record
   (account, display, git tree → owning agent + timestamp), written at dispatch, cleared at
   completion, *checked by mannyctl and run tooling* before any lifecycle or run operation.
   Converts two memory-rules (one-tree-one-agent, verify-predecessor-dead) into mechanical
   impossibilities. Add per-agent git worktrees for code trees at the same time.
2. **Formalize instrument-everything as a window checklist item** — *adopt now; near-zero cost.*
   Before any deploy window closes, ask: "what question could the next live failure pose that
   current logs can't answer?" and add the unconditional line. Retroactively this collapses the
   discovery time of at least four defects; prospectively it makes every live hour a data harvest.
   Include the lifecycle checklist (bank/harvest inventory before restart).
3. **Metrics ledger** — *adopt now; ~30 minutes.* One CSV row per deploy window and per
   routine-first-contact: date, live-hours spent, defects gated, first-contact pass/fail + failure
   class. The first-contact survival rate *is* the milestone's progress bar; start recording it.
4. **Replay lint (dry-run against recorded state)** — *post-milestone (or next quiet window);
   1–2 days.* Validator mode that executes routine control flow against recorded state-JSON
   streams from real runs. Fills the desk-to-live gap that produces most first-contact failures
   not already killed by honest primitives. Pairs naturally with recipe macros.
5. **Humanization pass before unattended grinds become routine** — *post-Track-G, before scaling;
   a few days of Java.* Inter-action timing jitter from sampled distributions, click-point
   variance within hulls, scheduled micro-breaks integrated with the watchdog, occasional camera
   drift. Justified by an actual ban, not paranoia; sequenced after the milestone proof so it
   doesn't block the campaign's definition of done.

---

*Written by an overseer fork during the defence grind, 2026-07-19, while three execution agents
ran in parallel — which is itself the method working: reflection no longer costs execution time.*
