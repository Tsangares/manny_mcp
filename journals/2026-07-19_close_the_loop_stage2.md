# 2026-07-19 — "Close the Loop" stage 2: tutorial island falls, the nav overhaul gets built in a night

**Author:** overseer (Fable session, orchestration-only). Continues `2026-07-18_close_the_loop_milestone_stage1.md`.
**Span:** ~01:30Z–05:30Z (≈5 h). **Read-first state doc:** `journals/OVERSEER_HANDOFF.md`.

## One-line story
Stage 1 built the on-ramp; stage 2 had to actually drive it. Five hours, two deployment windows, four new
defect fixes, and a complete offline build of the stage-2 navigation engine later: **tutorial island is
FINISHED on `newbakshesh`, the account is on the mainland, and the E1 chicken-feather smoke run is live**
(in flight at time of writing). The blocking discovery of the night: every real bug is invisible until the
live client hits it, and there is exactly one live client — the diagnose→Java-fix→deploy→re-gate loop is
the campaign's true clock.

## The critical path (what actually gated progress)
1. **Dual-driver ghost (resolved ~02:00Z).** The stage-1 "mystery run" unraveled: the run itself was
   phase-1b's own launch, but a *stale phase-1 agent* had silently resumed and was firing commands at the
   account in parallel (phantom bronze bar, duplicate NPC talks). Killed it; phase-1b confirmed sole owner.
   Lesson (now in memory): a "quiet" background agent is not a dead one — verify before launching successors.
2. **Deployment window #1 (~03:00Z).** Jar with DEFECT-22b/23/24 built + provisioned; client restarted.
   - **DEFECT-23 (`GOTO x y plane exact`) PASSED live** — `[NAV-EXACT]` on-tile arrivals, clean bounded
     failure when blocked. Immediately load-bearing (see 3).
   - **DEFECT-22b FAILED live**: the reflection ban-check never ran — MannyPlugin's "world busy"
     classification short-circuits first (MannyPlugin.java:990-1015, LOCKED); the banned account still
     world-hopped 5/5, and the only logging lived inside the TERMINAL branch, so the gate was blind.
   - DEFECT-24 untested (blocked upstream by 3/4).
3. **Tutorial 10's "maze" cracked.** The account-guide oscillation that stumped stage 1 was never a maze:
   one CLOSED interior door at (3125,3124) that tolerant GOTO could never line up on. With `exact` mode
   the full chapel-exit recipe validated end-to-end (commit `026f0e3`). Also fixed: 09's poll booth is
   named `Poll_booth`, not `poll` (`be85665`).
4. **NEW blocker → DEFECT-25 (pacing-NPC click race).** Brother Brace paces a 2-3 tile radius; ~10
   adjacent-tile interact attempts all returned "I can't reach that!" — the pipeline clicked the tile he
   *used to* be on. **User's prior-art tip was exactly right:** the in-flight hull-tracking click
   (`Mouse.moveToMovingTarget` re-querying `getConvexHull()`, canonical since Wave 6a) existed all along;
   `CLICK_NPC` was bypassing it with a private static-point click — the click-sprawl anti-pattern again.
   Fix (`0522135`): everything converges on one canonical live-hull click with an atomic
   hull+tile+menu snapshot at click time and bounded re-resolving retries; `[NPC-INTERACT]` per-attempt logs.
5. **DEFECT-22c (`f5243eb`)**: terminal-check now runs FIRST on every login-failure path and latches inside
   `WorldSelector.switchToF2PWorld` (the gateway every retry routes through — dodges the LOCKED MannyPlugin
   short-circuit), plus an *unconditional* `[LOGIN] failure-check:` diagnostic so no future gate is blind.
6. **Deployment window #2 (~04:30Z, in flight).** Merged the nav branch stack, rebuilt, provisioned,
   relaunched with `-Dmanny.navBackend=shadow`. As of writing the agent is PAST all gates and tutorial
   completion: **tutorial island is done, the account is on the mainland, E1 feather smoke is running**
   (snapshot #2 of the 30-min watch). Gate verdicts land in its final report → next journal.

## The parallel track: stage-2 nav engine, built offline in one night
While the live lane serialized, three stacked branch work packages (`nav-stage2-wp1`→`wp2`→`wp3`, master
untouched throughout) built the entire replacement navigation system from the NAV_STAGE2_PLAN blueprint:
- **WP1** (`7f47547`,`4cc2738`,`e4062a4`): vendored Skretzo shortest-path collision map + transports
  (BSD-2, pinned @ `7e7e5bf`), ported the packed-flag reader + a clean A*, `ShortestPathEngine` facade.
  25/25 offline assertions — including *the* assertion this milestone exists for: castle→cow-field paths
  cross the Lumbridge bridge on land tiles, and doors/stairs come out as actionable TRANSPORT steps.
  Heap ~5 MB (plan budgeted 30-50 — the 2011-iMac risk evaporates).
- **WP2**: `-Dmanny.navBackend=legacy|shadow|graph` flag; **shadow mode complete** — legacy still drives,
  every goto also queries the engine and logs one `[NAV-SHADOW]` comparison line (side-effect-free by
  design; the legacy A* couldn't be safely double-invoked, so divergence is measured against the
  straight-line model). Resources staged into runelite-client via `scripts/install_pathfinder_resources.sh`.
- **WP3+4** (`013bde4`,`24ac5ce`,`501347e`): graph mode executes transports for real — DEFECT-23 stepper
  onto the transport origin, doors/stairs via the existing `interactWithGameObject`, bounded await/retry,
  already-open-door probe, and a hard doctrine: any surprise → clean legacy fallback, never a wedge.
  Harness totals across the stack: **25+16+49 = 90/90.** Remaining: WP5 (retire legacy, post-soak), WP6
  (data refresh tooling).

## Also landed
- `ROUTINE_SCHEMA.md` §(i): the two live-validated authoring traps — position-pinning before ambiguous
  name-interacts; monologue exhaustion + the CLICK_DIALOGUE speaker-name trap (`2d1d8d3`).
- E2 `cowhide_banking.yaml` desk-verified (`9f6b6e8`): booth + staircase coords confirmed/corrected
  against wiki map pins, kills 30→35 (max_kills counts ATTEMPTS — read from KillLoopCommand), deposit-all
  self-heal. Live-gate remainders: 3 bridge-hop tiles + a possible door at (3218,3217).
- `TRACK_G_PROTOCOL.md`: the milestone's final exam, runnable (preconditions, verbatim fresh-session
  prompt, pass/fail rubric, watch-don't-help doctrine) + handoff refresh (`5d5fdc7`).
- Journal corrections `ea371e0`/`84fbef8` (mystery-run attribution).

## The holdup, named (retro)
**The live client is the only oracle, and there's one of it.** Every layer of desk verification (validator,
wiki coords, offline harnesses) passed routines that then hit *plugin*-level failure classes only
observable live: stale-tile clicks, 1-tile-short arrivals, misclassified dialogues, rasterized ban text.
Each became: live diagnosis → Java fix → deployment window → re-gate, ~1-2 h per loop, strictly
serialized on the single account/client/lane. Tutorial island consumed three such loops. Mitigations now
in place: shadow mode (live divergence data at zero risk), the exact/hull-click primitives (kill the two
biggest failure classes at the root), unconditional diagnostics (no more blind gates), and the graph
engine waiting to delete the door/bridge class entirely. Secondary holdup, self-inflicted: two agents
sharing one git working tree cross-contaminated branch state — rule now in memory: **one working tree,
one agent** (worktree-isolate or serialize).

## State at write time
- **manny master** (deployed as of window #2): `0522135` (D-25), `f5243eb` (D-22c), `4152392` (D-24),
  `8739648` (D-23), `a8a1020` (D-22b), + nav stack merge (window-#2 agent pushes the merge commit).
- **manny_mcp master**: `026f0e3` (tutorial 10 recipe) at dispatch; window-#2 agent commits 10's final
  YAML + shadow-flag launch wiring on top.
- **Account `newbakshesh`**: mainland (Lumbridge), tutorial COMPLETE, E1 feather smoke in flight under
  watchdog; diort temps healthy (61-74°C band all night).
- **Next, in order:** window-#2 final report (gate verdicts + E1) → bounded stat grind to ~20 att/str/def
  → E2 attended cowhide gate (closes DEFECT-21 with live bridge crossings + first shadow-vs-legacy data on
  the exact route) → **Track G: the 4-hour unattended proof** per TRACK_G_PROTOCOL.md.
