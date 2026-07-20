# 2026-07-19 — The exact-mode regression: honest primitives ≠ strict primitives

**Context:** Tutorial attempt #3 (fresh account `ifixifixit`, host llama, jar `fa059e23…`).
**Outcome:** Sections 1–5 passed first-contact; the run died in 5b when the player was sealed
into a walled pocket at the cooking-exit door. Root cause was **our own fix** from the previous
attempt. This journal is the lesson, not the play-by-play (that's in
`2026-07-19_tutorial_attempt3_ifixifixit_llama.md`).

---

## What happened, in one paragraph

After attempt #2 we blanket-converted 26 tutorial GOTOs to `exact` mode (commits `363d1c4`,
`732efd7`, `c8bfdeb`), on the theory that plain GOTO's ~3-tile arrival slop was a stall source.
In attempt #3, step 1 of the cooking-exit leg (`GOTO 3073 3090 exact`) undershot to (3076,3088).
Plain mode would have called that SUCCESS (3-tile Chebyshev match) and the next hop's minimap
nudges would have self-corrected forward — which is exactly how attempt #1 walked this leg
cleanly. Exact mode instead hard-failed, the cook door re-sealed, and the retrying section
walked the player into a walled dead pocket at (3078,3097) from which **no** navigation method
(external pathfinder, global A*, direct line-of-sight stepping, single-tile nudges) could
extract it. The run was unrecoverable from that tile.

## The red herring that almost sent us the wrong way

The log screamed `A* path goes through uncached/blocked area - failing immediately`, which reads
like a collision-cache/region-data gap in the new stage-2 nav engine. It is nothing of the sort:
that string is `NavigationHelpers.java:2279`, a generic bail in the **old** greedy minimap
follower emitted whenever one off-minimap click produces zero movement. The stage-2 engine never
ran at all (backend flag defaulted to `legacy`; zero `NAV-SHADOW` lines in the whole log).

**Lesson: read the code that emits a log line before believing what the log line says.** A
five-minute grep prevented a multi-hour wild-goose chase into collision data that was never
loaded.

## The diagnostic move that settled it

`git diff 2020530..cf22ed5` — the attempt-#1 jar vs the attempt-#3 jar — showed every navigation
class **byte-identical**. The only section-relevant change between a passing run and a failing
run on the same route was the routine YAML's exact-mode conversion. When a previously-passing
leg fails, diff the *deployed artifacts* first; it instantly partitions the search space into
"code regression" vs "config/data regression."

## The actual lesson: tolerance can be load-bearing

The campaign's central thesis — **first-contact survival is a function of primitive honesty** —
remains true. Strict_steps, honest GOTO failure, and varp ground-truth each retired a real
failure class. But this incident exposes the failure mode of over-applying it:

- *Honest* means a primitive **reports what actually happened**.
- *Strict* means a primitive **demands a tighter outcome**.

We conflated them. Plain GOTO's 3-tile slop wasn't dishonesty — it was a **forgiving,
self-correcting crawl** in which each imperfect hop is repaired by the next. That tolerance was
load-bearing: it is *why* attempt #1 passed legs that thread doors and walls. Converting it to
exact turned "close enough, keep walking" into "hard fail, re-close the door, trap the player."

**The rule we now encode: strictness must be earned by a live defect.** `exact` stays only where
a specific failure proved plain mode broke something — the ladder seat at (3088,3120), where a
range-gated Climb-down genuinely requires standing on the one walkable adjacent tile. Everything
converted prophylactically ("this *might* undershoot") reverts to plain. Prophylactic hardening
without a motivating defect is how you manufacture regressions while feeling rigorous.

This is the same species as the user's canonical-path rule ("fix the canonical path, never add
variants"): both are defenses against speculative changes justified by theory instead of by an
observed failure.

## The process that made this cheap

The loop from live failure → definitive root cause → audited corpus-wide fix → validated →
committed → resume launched took about one hour of wall-clock, because the work ran as three
parallel lanes:

1. **Live supervisor** (llama) attempted bounded manual salvage — harvesting the pocket's
   geometry and proving it was a true nav sink (that's data, not wasted time).
2. **Diagnosis agent** (laptop, read-only) grepped the emitting code, diffed the jars, pulled
   the live log window, and delivered ranked fix options *while the salvage ran*.
3. **Fix agent** (laptop) applied the revert across all 10 section files with a clear decision
   rule, kept the live-earned pins, and validated every file offline (`--dry-run` all PASS,
   master chain PASS) — before the live window had even closed.

No live hours were spent learning anything a desk could answer. That is the retrospective's
doctrine working as designed.

## Concrete outcomes

- Commit `070d159`: 10 tutorial YAMLs reverted to plain GOTOs; ladder pins kept; rationale in
  the files' headers.
- Positive results banked from the same run: varp-281 progress read confirmed (1→130), master
  progress-gating confirmed (correctly skipped cooking at 130≥120), sections 1–5 first-contact
  PASS on a fresh account, zero ban signals.
- `ifixifixit` parked wall-trapped but **not** desynced; resume (attempt #3b) escapes via the
  mapped NE gate route and re-tests 5b on the reverted routines.

## CORRECTION (same day, post-attempt-#5) — the diagnosis above was half right

Attempt #5 (gates fixed, player correctly inside the kitchen) wedged on the same corridor in
**plain** mode, and the follow-up archaeology proved by commit timestamps that **attempt #1 had
passed this bridge in EXACT mode** (`402950b`), not plain. The narrative above conflated two bugs:

- The TRUE root cause of attempts #3/#4 was the **progress-gate skip** (fixed in `31504fb`):
  cooking never ran, the player started 05b *outside* the building, >5 tiles from the door seat —
  a position from which exact mode legitimately cannot refine and *no* mode can succeed. Exact's
  hard-fail was the messenger, not the disease.
- Plain mode has its own dishonesty on **positioning** steps: within 3 tiles it short-circuits to
  SUCCESS **without issuing any movement** (`GotoCommand.java:152`), and the 3-tile-tolerant
  `location:` await confirms it — a double false-pass. At (3074,3091) the player "passed"
  `GOTO 3072 3090` while never stepping onto the corridor tile, then wedged behind the wall while
  the follower obsessively re-opened an already-open door (`NavigationHelpers.java:2365` stuck-
  handler chasing the doorway WallObject red herring).

The refined doctrine, replacing "prefer plain": **match the mode to the step's intent.**
*Traversal* steps (get near X, the next hop self-corrects) want plain's tolerance. *Positioning*
steps (stand ON this tile so the next action works — door seats, ladder seats, threshold
crossings) need exact — their whole purpose defeats a 3-tile shortcut. And both of today's wrong
turns trace to one meta-error: **diagnosing a nav symptom while a state bug (the gate skip)
corrupted the experiment's premise.** Fix committed: `b5f5e61` restores exact on 05b's bridge
steps 1,3-8 (the proven `402950b` sequence), keeps tolerant awaits as confirms, keeps ladder pins.

## ADDENDUM (2026-07-20): the door-tile exception

Desk-verified with log receipts (run 20260720T003818Z): the refined doctrine above
("match the mode to the step's intent... positioning steps need exact") has exactly
one exception, and it matters. Tutorial-island doors auto-close server-side ~5-7s
after Open. `exact` is correct for SEATS (stand on the threshold approach tile so
the next Open resolves to the right door) — but it is actively HARMFUL if used for
the crossing step itself, i.e. an exact-GOTO ONTO the door tile. Exact's per-hop
refiner (`stepOntoExactTile`) right-clicks "Walk here" on each intermediate tile
including the destination; once the door re-closes under it, that click on the
door tile is BLOCKED (empty "Walk here" menu), and the step spins to a ~53s
timeout instead of failing fast. This was compounded in
`05_cooking_to_quest_guide.yaml` by a second defect: `05_cooking.yaml` independently
opened the SAME door at its own tail end, so the door was already re-closing by the
time 05b's re-seat + re-open + exact-onto-door-tile sequence ran — ~10s of redundant
ceremony spent before the crossing even attempted the doomed exact click.

The corrected pattern: exact seat on threshold → INTERACT Open → immediately
(minimal delay padding) a PLAIN GOTO to a tile PAST the threshold, never onto the
door tile. One through-click during the still-open window, instead of a refined
multi-hop approach that can get caught mid-sequence by the auto-close. Fixed in
`05_cooking.yaml` (deleted the redundant trailing door-open) and
`05_cooking_to_quest_guide.yaml` (both door crossings) on 2026-07-20; doctrine
recorded in `MANNY_OVERSEER.md` §4. Prior art for the durable fix: the deleted Java
`GateAction` (`git show 34133c5^:tutorial_island/replay/GateAction.java` in
`~/Desktop/manny`) was already state-gated — it read the gate's actual open/closed
object ID and skipped the Open click if already open. A state-aware cross-door Java
command (open only if closed, walk through only once confirmed open) would make
this whole class of timing race structurally impossible instead of YAML-timed.

## Checklist additions for future fix windows

1. Before hardening a primitive corpus-wide, name the **live defect** that motivates each site.
   No defect, no hardening.
2. When a passing leg regresses, **diff the deployed jars/routines between the passing and
   failing runs** before theorizing.
3. When a log line drives a hypothesis, **read its emitting code** first.
4. When a live run wedges, split immediately: bounded salvage on the live lane, diagnosis and
   fix as parallel desk lanes.
