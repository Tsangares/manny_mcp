# 2026-07-19 — "Close the Loop" stage 3: the loop closes on us

**Author:** overseer (Fable session, orchestration-only). Continues `2026-07-19_close_the_loop_stage2.md`.
**Span:** ~06:00Z–10:00Z (≈4 h). **Read-first state doc:** `journals/OVERSEER_HANDOFF.md`.
**Companion piece:** `journals/2026-07-19_newbakshesh_ban_and_pivot.md` (the ban incident in full detail),
`journals/2026-07-19_methods_retrospective.md` (written *before* the ban; aged remarkably well).

## One-line story
The morning everything worked — and then the anti-cheat reminded us who the real adversary is.
Deployment window #3 closed DEFECT-26 with four green gates, two clients ran concurrently for the
first time, a defect blitz fixed six primitive-honesty bugs in one sitting, and then **NewBakshesh was
banned mid-grind at 07:58Z** — the second behavioral-detection ban in two days. The campaign pivoted
inside an hour: humanization went from "post-milestone nice-to-have" to prerequisite, and phases 1–2
of it were designed, built, tested (25/25), and pushed before this journal was written.

## Deployment window #3 (~06:20–07:00Z): DEFECT-26 closed, two lanes proven
All four gates passed live: `run_routine` blocks for the full KILL_LOOP batch (the 60-second
false-completion class is dead), STOP halts within one iteration, dual launches are rejected by the
`kill_loop_active` guard, and SWITCH_COMBAT_STYLE clicks the real stance widget. Two bonus findings:
the feared auto-equip stance reset is a no-op when the weapon is already optimal, and the style
switcher needs an explicit `TAB_OPEN Combat` first (now in the routine). Both clients ran together
06:40–06:58Z peaking at 76°C — far under the 84°C abort line. The user's stat correction (the old
stance had been training *strength*, not attack) was applied and XP-verified: Block stance, defence
climbing, everything else frozen.

## The supervised grind, and the rotation that never got to matter
A supervisor agent ran lane 1 with 10-minute polls and an event watcher on the host: defence 1→14 at
~2,120 xp/hr across 52 minutes, 2,720 feathers accumulated. At 07:54Z run 1's step-timeout elapsed
and exposed **DEFECT-30**: the runner exited *leaving the Java kill loop running unmanaged* instead of
stopping it. The supervisor cleaned up properly (STOP, verified release), rotated the stance to Stab,
relaunched, and XP-verified the rotation on the first kill — a textbook operation. Thirty-two seconds
into the new run, Jagex force-disconnected the session. The ban screen surfaced once the ghost
session cleared: "serious rule breaking." Full forensics in the ban journal; the short version is
that the infrastructure passed every test and the *behavioral signature* failed the only one that
counts.

## The lane-2 arc: tutorial corpus hardened by fire
Blast (lane 2, fresh account) became the corpus regression vehicle and paid off enormously:
- **05→06 bridge fixed** (`363d1c4`): the tolerant GOTO seated the player 2 tiles east of the
  west-edge corridor (DEFECT-7 short-circuit) and every north hop then wall-blocked. The fix was to
  rewrite the whole bridge crossing as `exact`-arrival GOTOs — seat `x=3072` first, *then* go north —
  so the follower steps onto each tile instead of parking a tolerance short of it.
- **Quest Guide ladder gate encoded** (`402950b`): the ladder unlocks only after re-talking to the
  Quest Guide *once the journal is open*, and the monologue had to be exhausted with a blind
  `repeat: 12` press-space (not `repeat_until: no_dialogue` — DEFECT-24's mid-monologue false-close
  breaks that loop). Two live-validated recipes, both now in the corpus.
- **Section 07 (mining/smithing) — the "tin" collision** (`dbba4c3`, `3b59347`): `USE_ITEM_ON_OBJECT`
  ore→Furnace never seated, and the obvious read was a nav-seating bug. It wasn't. The real cause was
  the item-name matcher: `"tin"` substring-matched **Tinderbox** (`Target: "Tinderbox -> Furnace"`),
  so the routine tried to smelt the tinderbox forever. Fixed by spelling out full item names in the
  YAML (`"Tin ore"`, `"Bronze bar"`), selecting the smith product by stable `widget_id 20447241`, and
  splitting the gate into an explicit GOTO + INTERACT. That surfaced the underlying primitive bug,
  filed as **DEFECT-28**: `findItemIdByNameUnsafe` uses `.contains()` and returns the first inventory
  item containing the string — `"tin"`→Tinderbox, `"bronze"`→Bronze axe. With 07 fixed, sections 01–07
  now run hands-free end-to-end on a fresh account.
- **DEFECT-29 — the equip that walked the player** (`ba8efd3`, `cba886e`): section 08 needs the dagger
  equipped, and it never was. `handle_click_widget` (text/action modes) and `handle_equip_item` were
  issuing `CLICK_AT` on interface-*relative* scan bounds as if they were screen-absolute — so the click
  landed out in the game world and the player *walked* instead of equipping, while the tool still
  reported success. The Combat Instructor then withheld weapons and the whole chain stalled. Fixed on
  the canonical Python path: `equip_item` now opens the inventory tab, guards its bounds, and — the
  important part — **verifies the outcome** (did the item actually move to the equipment slot?) instead
  of trusting a fire-and-forget click. Honest verified-outcome semantics, documented in
  `ROUTINE_SCHEMA.md`. Plain `CLICK_WIDGET <id>` was already the proven-safe form; the bug lived only
  in the relative-bounds click paths.
- **Blast parked at section 08.** With DEFECT-29 fixed Python-side but no live re-run (the ban froze all
  live contact hours later — see below), blast sits cleanly stopped at the section-08 combat area
  (3111,9525), dagger in inventory, unequipped, 8h clock reset. Section 08 is also where the tutorial's
  modal messages live — "I can't reach that!", "You'll be told how to equip items later" — the old
  DEFECT-8 modal-block saga. Today it got a proper name: **DEFECT-31**, filed when we noticed these
  modals render with `dialogue.open:false`, so any `repeat_until` step gated on dialogue state no-ops
  against them instead of detecting the modal. That's the next thing standing between blast and a
  hands-free section 08.

## The desk blitz: five fixes, zero live hours
While the live lane ground (and then died), a parallel desk pass turned the live-discovered defects into
committed fixes without spending a single live minute — the methods retrospective's thesis in miniature:
- **DEFECT-27** (manny `873eec7`): `exact`-arrival GOTO could exhaust its hop budget *off-target* and
  still report `"Successfully reached target (exact tile)"`. An honest primitive that lies about
  success is worse than one that fails loudly — fixed so a false arrival is reported as a failure.
- **DEFECT-22 loginIndex diagnostic** (manny `70fac7a`): the ban-detection reflection approach kept
  missing because `loginIndex` had drifted (10→14) and the ban text isn't in any scannable String
  field. Added an unconditional loginIndex-transition diagnostic + a provisional ban signature, so the
  *next* login attempt on a banned account answers the question definitively instead of blind.
- **DEFECT-28** (manny `bc186eb`) and **DEFECT-28b** (manny `00f0069`): the `"tin"`→Tinderbox class,
  fixed at the root. A canonical **`ItemNameMatcher`** now resolves names in tiers — exact match, then
  word-boundary, then substring, logging ambiguity — and `28b` converged the *remaining* scattered
  item-name matchers onto that one class so there's a single honest matcher, not five copies drifting.
  40/40 offline assertions. This is the "fix the canonical path, never add variants" rule applied
  literally.
- **Nav Stage-2 WP6** (manny `81bd912`): vendored-data refresh tooling for the pathfinder package, so
  the Skretzo collision map / transport TSVs can be re-pulled and re-packed reproducibly rather than
  hand-vendored.
- **Shadow-soak verdict** (manny_mcp `f467d47`, `journals/NAV_SHADOW_SOAK_2026-07-19.md`): 22
  `[NAV-SHADOW]` comparison lines harvested read-only across both lanes. The engine is healthy —
  median 373µs, zero mainland `graph=NONE`, no engine drift across restarts — but the WP5
  retire-legacy gate stays **closed**: 0 transport (door/stair) samples and only 9 thin mainland
  lines. The one thing that would *prove* graph-mode beats legacy (a route legacy literally can't
  solve) hasn't been exercised yet. E2's bridge/bank crossing is exactly the missing sample; until
  then WP5 waits.

## The retrospective aged an hour
`journals/2026-07-19_methods_retrospective.md` was written *before* the ban, by an overseer fork during
the defence grind, on the thesis that the whole campaign has one governing variable: **truth extracted
per live-client-hour.** The live client is the only oracle for a whole class of bugs, and the live-hour
budget is small and hard-capped. Every method that worked (offline-first nav, shadow mode, unconditional
diagnostics, canonical-path convergence) worked because it raised truth-per-live-hour; every burn wasted
a live hour learning one bit we could have learned at a desk.

Its risk section flagged, as item #5, that behavioral detection was *demonstrated, not hypothetical*
(GrimmsFairly, a day earlier), that nothing in the stack randomized timing/click-point/breaks, and that
running Track G's long unattended grind on robotic patterns "is exactly the profile that got the last
account banned." It sequenced humanization as post-Track-G, before scaling.

The ban proved the thesis inside the hour — and inverted the sequencing. The retrospective's own logic
(truth per live hour, the live client as the only oracle for a bug class you can't see at a desk) is
exactly what the ban was: the single most expensive bit of truth the campaign has bought, and it could
only have come from a live hour. The infrastructure passed; the behavioral signature — the one thing the
infrastructure was never built to address — failed. Risk item #5 stopped being a risk item and became the
next milestone.

## Humanization, phases 1 and 2 (Java): built, tested, pushed before this journal
The pivot moved from decision to committed code within the hour. In the `manny` tree:
- **Design doc** (`630796b`, `HUMANIZATION.md`): a survey of the input pipeline ranking the metronomic
  signatures that got two accounts banned in 48h. The offenders, ranked: the **constant 1000 ms
  inter-kill gap** (`KillLoopCommand`'s `sleepChecked(1000)` — a perfect metronome), **exact-centroid
  clicks** (every tracked/pacing NPC click landed on the *identical* pixel — the DEFECT-25 hull-tracking
  fix made clicks correct but also made them pixel-perfect-repeatable), and **zero-tick reactions** (the
  post-kill routine fired on the same tick with 0 ms of human reaction). One honest finding kept us from
  over-building: the **mouse *paths* are already human** — Bézier/wind-mouse curves that are actually
  observed on the canvas dispatch — so path-shaping was already largely satisfied and phase work went to
  timing and endpoints instead.
- **Phases 1–2** (`e56ba40`): `HumanTiming` (phase 1) draws right-skewed shifted-log-normal delays
  (`reactionDelay`/`scaledDelay`/`hesitate`) from a per-session player profile — a speed multiplier +
  hesitancy seeded off `-Dmanny.humanize.seed`. `HumanPoint` (phase 2) samples a center-weighted
  gaussian over the target's real hull shape, rejection-clamped inside it, and never returns the same
  pixel twice in a row. Both are routed at the **canonical chokepoints** with zero routine changes:
  `Mouse.move`/`moveToMovingTarget` sample via `HumanPoint` instead of driving to the centroid, and
  `KillLoopCommand`'s constant inter-kill sleep becomes `scaledDelay(1000)` with a `reactionDelay()`
  before the post-kill routine and an occasional `hesitate()` micro-break. Like `ItemNameMatcher`, both
  classes are pure logic (no client classpath), so the `HumanizeVerify` offline harness could assert
  distribution shape, `OFF==legacy` byte-for-byte, determinism, profile variation, and HumanPoint's
  in-shape/no-repeat/center-weighting: **25/25 PASS.** `-Dmanny.humanize=off` reproduces legacy behaviour
  exactly; default is ON. Cost estimate ~8–15% throughput — cheap insurance against the thing that just
  cost two accounts.

Phase 3 (camera drift + scheduled breaks) and the Python-side items (relaunch pacing, session-length
variance, break scheduler, DEFECT-30's loop-stop-on-timeout) are the next tranche, in flight as this is
written.

## State at write time, and what's next
- **Zero live clients are being driven.** The banned `newbakshesh` client is left UP at the ban screen
  on `:2` as appeal evidence — do not touch it. `blast` is cleanly stopped at section 08, dagger
  unequipped, 8h clock reset. `punitpun` is a fresh spare, reserved and unburned until humanization is
  proven.
- **Window #4 payload is staged and undeployed** (no Java rebuild since window #3): DEFECT-27
  (`873eec7`), DEFECT-22 loginIndex (`70fac7a`), DEFECT-28 (`bc186eb`), DEFECT-28b (`00f0069`),
  humanization phases 1–2 (`630796b`/`e56ba40`), plus whatever phase-3 lands — and DEFECT-29 is already
  fixed + deployed Python-side (`ba8efd3`/`cba886e`). Its gates need no grinding: a banned-account login
  probe (DEFECT-22, zero risk), DEFECT-27/28 log checks, and a DEFECT-31 modal check.
- **Two open defect candidates from the ban window:** DEFECT-30 (`run_routine.py` must `STOP` a
  blocking loop it owns when its own step-timeout elapses, not exit and orphan it — the `unmanaged_loop`
  the watchdog caught mid-incident) and DEFECT-31 (tutorial modals invisible to dialogue state).
- **The next live-contact decision belongs to the USER,** not to any agent. Humanization must be proven
  first, and IP posture is the open question: route through mat + the dataimpulse proxy first
  (recommended), run `blast` on the already-flagged residential IP, or spin a fresh throwaway. No live
  resumption happens until that call is made. Standing hazard to re-check first: credential re-imports
  have twice reset `default:` to a banned alias — verify it before trusting it.
- **Track G is deferred, not cancelled.** The milestone's flagship 4-hour unattended proof is the single
  worst place to discover robotic timing; it waits until the primitives it would exercise are humanized
  and proven on an expendable account.

The morning's one-line story holds: everything worked, and then the adversary reminded us what "working"
has to mean. The loop closed on us — and the campaign's answer, within the hour, was to make the machine
move a little more like a person.

---
*Overseer session, orchestration-only. Companion pieces: `2026-07-19_newbakshesh_ban_and_pivot.md`
(the incident in full), `2026-07-19_methods_retrospective.md` (written before the ban, aged an hour),
`NAV_SHADOW_SOAK_2026-07-19.md` (WP5 soak). Read-first state: `OVERSEER_HANDOFF.md`.*