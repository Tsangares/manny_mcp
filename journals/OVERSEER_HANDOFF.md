# OVERSEER HANDOFF — manny (multi-project) — READ THIS FIRST

**Updated:** 2026-07-19 refresh (deployment window #2 DONE — nav stack deployed shadow-mode, gates mostly
PASS; Tutorial Island COMPLETE on newbakshesh → mainland; E1 grind exposed DEFECT-26 (coded, deploying in
window #3); two-lane world plumbing landed (`blast` = lane 2); deployment window #3 IN FLIGHT at write
time). Author: Claude (overseer). This is
the top-level entry point after compaction. It indexes the now-several parallel projects and how to resume
each. For deep detail on any one, open the doc named in its row.

**Read order:** this file (top section = current milestone, current) → the specific project doc you're
resuming. The old `REFACTOR_CAMPAIGN_HANDOFF.md` is now the REFACTOR-detail archive (huge; read only for
refactor history). Everything below "THE PROJECTS" table is the pre-milestone history (#1-7 are DONE/closed
out); it's kept for context but the section immediately below is the live state.

---

## CURRENT MILESTONE — "Close the Loop" (started 2026-07-18, in flight)

**Goal:** an LLM session — given only `ROUTINE_SCHEMA.md`, the upgraded validator, and the `manny-diort`
MCP endpoint — authors/refines a routine and runs it **unattended on diort for 4+ hours**, with the
watchdog ledger showing clean completion or correct intervention. Plan file:
`~/.claude/plans/kind-snuggling-turtle.md` (full track breakdown, verified architecture decisions, source
citations — read it for depth). First authored money-maker: **cowhides** (deliberately forces the
DEFECT-21 bridge fix + banking robustness). Claude session is THE canonical driver (`manny_driver/` and
`discord_bot/` stay non-canonical, untouched).

**Amended scope (user, mid-flight):** E1 is not just a smoke test. Before cowhides, grind chickens with
`KILL_LOOP_CONFIG` (loot_items=Feather) as a genuine **stat-training sub-milestone** — target att/str/def
~20 — while stacking feathers (sellable later). Only then move to E2 cowhides. So the path is: E1 feathers
(stat training) → E2 cowhides (the actual milestone routine, gated on DEFECT-21 bridge fix) → Track G
(fresh-session unattended 4h+ proof).

**Why this milestone:** the refactor/defect/thermal campaigns (projects #1-6 below) are done and diort is
proven as a run host. What's still blocking "an LLM that runs routines and makes routines easily" is: (1)
the MCP server's structured tool surface (`get_game_state`, `check_health`, `send_and_await`, etc.) was
hard-local to the laptop — diort only had raw-text `mannyctl` over SSH; (2) no authoritative routine schema
doc + the validator missed every real bug class found live; (3) zero money-making routines existed despite
that being the north star.

### Landed this milestone (all pushed to origin unless noted)

**manny_mcp** (`cd /home/wil/Desktop/manny_mcp && git log --oneline`):
- `3a5556f` — Track A: `manny-diort` MCP endpoint — `scripts/remote/mcp_stdio.sh` + `config.diort.yaml` +
  `.mcp.json` entry. Full 39-tool parity against diort over SSH stdio. Local server confirmed named
  `runelite-debug` (build/code-change/code-intel, laptop-only); new remote server is `manny-diort`
  (run/monitor/screenshot/routine tools, SSH stdio to diort). Routing table lives in repo-root CLAUDE.md.
- `396f27f` — `ROUTINE_SCHEMA.md` added as the authoritative routine YAML spec + `ROUTINE_CATALOG.md` split
  (existing/validated vs planned) + new `routines/money_making/` dir.
- `88bd59b` — Track C: `validate_routine_deep` upgraded — 7 new checks (unknown-key allowlist, blocking-cmd
  timeout/await-condition trap, loop-schema mixing, condition-vocabulary cross-use, `mcp_tool` whitelist,
  unbounded-flat-loop warning, KILL_LOOP numeric-2nd-arg) + 25 tests.
- `e909085` — Track F: `watchdog.py` + run ledger. Writes `/tmp/manny_runs/<run_id>.json` on the run host
  (temp, state-file age, PIDs, events); new `mannyctl <host> runs` subcommand reads it back; auto-attached
  (setsid-detached) by `mannyctl run`.
- `23abe99` — Track H: `journals/NAV_ARCHITECTURE_REPORT_2026-07-18.md` — full GOTO pipeline map + failure
  modes; recommends patch-now (targeted DEFECT-21 fix) / replace-core-next; Stage-2 recommendation is a
  Shortest-Path-plugin-style precomputed collision+transition graph that removes the osrspathfinder.com
  external dependency entirely.
- `0d600ee` — 7 corpus routines fixed (the KILL_LOOP food-arg class the validator now catches, e.g.
  `chicken_killer_loop.yaml` was sending kill-count as a food name).
- `c501d06` — decoupled the chicken-killer test from mutable corpus state.
- `0cb6c9e`/`1b4b016`/`b0e08f8`/`ab020dd`/`2a06c31`/`5f9a08a`/`33029b6`/`770167f` — tutorial pre-flight
  landed (05 plane fixes + ladder-gate recipe, chain-glob double-run guard), mannyctl watchdog cwd fix,
  E1 `chicken_feathers.yaml` (stat-training grind, validated 0/0), E2 DRAFT `cowhide_banking.yaml` (24
  steps, nested loop, 5 open questions flagged for live gate).
- `91f84c5` — tutorial 07: position-pin every name-interact (live-diagnosed "Rocks" ambiguity — tin vs.
  copper outcrops share a display name, closest-match resolution farmed tin forever; fixed with a
  position-pinning GOTO before each ore-type INTERACT).
- `ea371e0` — journal: **mystery run `20260719T014238Z` RESOLVED.** It was the ORIGINAL phase-1 live agent —
  never actually terminated, it silently resumed and dual-drove the `newbakshesh` account in parallel with
  the phase-1b agent (the exact dual-driver collision the coordination rule warns about). Stale agent
  killed ~2026-07-19 02:00Z; phase-1b confirmed sole owner. **Lesson (recorded in the stage-1 journal):
  before launching a successor live agent, verify the predecessor task is DEAD (`/tasks`), not just quiet —
  a "still running" background agent can wake up and fire commands hours later.**
- `2d1d8d3` — `ROUTINE_SCHEMA.md` gained section **(i) "Two live-validated authoring traps"**: position-pin
  before ambiguous-name `INTERACT_OBJECT`/`INTERACT_NPC` (the tutorial-07 "Rocks" bug), and the
  `CLICK_DIALOGUE "<speaker name>"` no-op trap (DEFECT-24 — monologues misreported as `type:"options"`).
  Both found live 2026-07-18, both silent, neither caught by the validator.
- `01ff1a3` — `journals/NAV_STAGE2_PLAN_2026-07-18.md`: next milestone's blueprint. Vendors the Skretzo
  shortest-path plugin's packed collision map (~1.2 MB, `SplitFlagMap` 2-flag/tile format) + transport TSVs
  into a new `manny.pathfinder` package behind a `navBackend` feature flag; cutover seam is
  `gotoPositionSafe`. Deletes the `osrspathfinder.com` external dependency and the `world_map.png`
  walkability tier. 6 work packages scoped, design-only (no code touched).
- `9f6b6e8` — E2 `cowhide_banking.yaml` **desk-verified** against the OSRS wiki + corpus (no live account
  touched): staircase waypoints corrected `3205,3209`→`3205,3208` on ground/mid floors (wiki `{{Map}}` pins
  + `common_actions.yaml` precedent); batch size raised 30→35 kills (`KillLoopCommand`'s `max_kills` caps
  loop **attempts**, not confirmed kills, so headroom above the 28-slot inventory is needed);
  `BANK_DEPOSIT_ALL` self-heal added. **Live-gate remainders:** the 3 bridge-hop tiles (no independent
  coordinate source — wiki has no bridge-tile page, only internal geometric consistency) and a possible
  door at `3218,3217` on the courtyard→stair line — scan both before trusting this unattended.
- `36d5443` — **Tutorial Island COMPLETE on newbakshesh → mainland Lumbridge.** Tutorial 10 fixes
  live-validated: Wind Strike widget `14286859`, `CAST_SPELL_NPC` broken/stale-map workaround, dialogue
  options driven via `CLICK_CHILD_WIDGET 14352385` group 219, Home Teleport gating. Live lane is now fully
  off Tutorial Island.
- E1 ran live: feather smoke test **PASS**, then a sustained grind reached **830+ feathers banked** — but
  the sustained run exposed **DEFECT-26** (see manny bullets below): `run_routine.py` wasn't actually
  blocking on `KILL_LOOP`.
- `88757aa` — DEFECT-26 Python fix: `_await_active_loop_finish` makes `run_routine.py` genuinely block on
  an active KILL_LOOP instead of racing an early rid-correlated sub-response; `kill_loop_active` pre-launch
  guard (+ `--force` override) stops relaunch from spawning a twin loop; watchdog gains an
  `unmanaged_loop` ledger status for a loop the launcher lost track of; validator now warns on non-terminal
  `KILL_LOOP` usage.
- `af08fc8` — DEFECT-26 follow-up: validator warning refined + `ROUTINE_SCHEMA.md` gained section documenting
  the blocking-KILL_LOOP semantics (why `STOP` couldn't previously halt a loop, why `SWITCH_COMBAT_STYLE`'s
  old F1-keybind path was a no-op).
- `5d75dbe` — **Two-lane world, lane-2 plumbing:** account-scoped client lifecycle (`mannyctl diort
  start/stop/status <account>`, `stop --all` as an explicit sweep, a bare `stop` now errors instead of
  guessing), `hosts.yaml` gained `account_displays` (`newbakshesh`→`:2`, `blast`→`:3`). Feasibility probe
  came back **GO** on diort: two-client thermal probed at 72-77°C, estimated 80-85°C with both active,
  refuse threshold stays 88°C; IPC/watchdog/MCP tooling was already per-account so no rework needed there.
  Account `blast` (display name `iGottaBlast`) is lane 2, parked at tutorial start. `credentials.yaml`
  default fixed to point at `newbakshesh`; the `new` account entry carries an explicit BANNED comment.
- `a199172` — journal `journals/2026-07-19_close_the_loop_stage2.md`: covers the ~5h span above. Names
  "the live client is the only oracle" as the standing bottleneck — now partly mitigated by the two-lane
  setup (lane 2 can regress/validate corpus while lane 1 grinds).
- `64dd739` — `chicken_feathers.yaml` batch size raised 100→1000 kills (sustained-grind config, feeds the
  E1 stat-training run above).
- **Nav Stage-2 status:** WP1-4 (the shadow-mode nav engine) are all merged + deployed — see the manny
  `235ecb6` bullet below. WP5 (retire the legacy pathfinder) is gated on a longer shadow-mode soak review;
  WP6 (transport/collision data-refresh tooling) is not started.

**manny** (`cd /home/wil/Desktop/manny && git log --oneline`):
- `a6da377` — DEFECT-20: thread-safe collision/tile reads in GameEngine (off-thread wrap).
- `b40838a` — DEFECT-21 fix: `validateAgainstLocalCollision` wired into the nav follower's click path
  (bridge water-stall). **Live gate still pending** — needs a round-trip cow-field⇄bank crossing on diort.
- `6566fe9` — DEFECT-22: `LoginHandlers` ban misclassification fixed — stop world-hopping on terminal
  (banned-account) login failures, fail fast instead. Live gate showed the widget-text source doesn't see
  the rasterized ban dialogue → **DEFECT-22b filed** (below).
- `a8a1020` — DEFECT-22b: ban detection via **reflection over client login-response `String` fields** as
  the PRIMARY signal (strict phrase match; RuneLite's public API exposes only `getLoginIndex()`, no
  login-response string) + widget-scan fallback retained. Live gate = a login attempt on the banned `new`
  account.
- `8739648` — DEFECT-23: opt-in **`GOTO X Y [plane] exact`** bounded stepper — legacy GOTO parks ~1 tile
  short (DEFECT-7 tolerance) and short-circuits "already there" within 3 tiles, wedging a following
  INTERACT before settle (worst at doors). `exact` mode keeps taking short hops until it steps ONTO the
  target tile. INTERACT's own post-settle retry is deferred to a future INTERACT-surface change (out of
  scope for this bundle).
- `4152392` — DEFECT-24: `GameEngine.buildDialogueState` — group-231 NPC monologues (multi-page, no real
  options) now classify as `type:"continue"` / hint `CLICK_CONTINUE`, not `type:"options"` /
  `CLICK_DIALOGUE "<speaker>"` (a no-op — the "speaker" child is a header, not a clickable option).
  `TabOpenCommand` javadoc corrected (widget-click, not F-key, despite the stale doc's claim).
- `235ecb6` — **nav stack merged to manny `master`.** Includes the Nav Stage-2 WP1-4 shadow-mode pathfinder
  package behind the `manny.navBackend` flag.
- `806e7da` / `291aadc` — DEFECT-26 Java-side fixes (companion to the Python fixes above): single-loop
  `AtomicBoolean` guard on `KillLoopCommand` so a second launch can't spawn a twin, `active_loop` exported
  in plugin state so the ledger/watchdog can see it, per-iteration interrupt checks so `STOP` actually halts
  a running loop, and `SWITCH_COMBAT_STYLE` reimplemented as a combat-tab **widget click** (the old F1
  keybind approach was a silent no-op).

**Deployment window #2 — DONE.** The nav stack (`235ecb6`) merged and was DEPLOYED to diort with
`-Dmanny.navBackend=shadow` (wired via `NAV_BACKEND` env in `scripts/remote/client_remote.sh`, manny_mcp
`7e53271`). Gate results:
- **DEFECT-25 PASS** — canonical live-hull NPC click; pacing NPCs are now clickable.
- **DEFECT-24 PASS** — monologues report `type:"continue"` correctly.
- **shadow-mode PASS** — `[NAV-SHADOW]` log lines confirm zero behavior change vs. the legacy pathfinder;
  the shadow engine loads in ~5MB/168ms.
- **DEFECT-22c PARTIAL** — the unconditional `[LOGIN]` failure-check diagnostic works, but the ban text is
  NOT present in any scannable client `String` field on the current auth-layer path (`loginIndex` moved
  10→14 since DEFECT-22b was coded). Ban detection needs a different signal than the reflection approach;
  **deprioritized**, not blocking.

**Deployment window #3 — IN FLIGHT at write time.** Scope: deploy DEFECT-26 + lane-2 plumbing, run the
4-gate DEFECT-26 check (loop-launch blocking, `STOP` halts a running loop, dual-launch is rejected, combat
style switch works), relaunch the lane-1 stat grind as a **managed** run (Strength stance), bring `blast`
up on display `:3` and run the tutorial `00_master` corpus regression on it, and hold a two-active thermal
watch while both lanes run. mjpeg viewers: lane 1 (`:2`) → `http://diort:8787` (running); lane 2 (`:3`) →
`http://diort:8788` (being brought up).

DEFECT-21/22 (jar `6566fe9`) remain live-gate-pending as before, riding the same deployment lineage.

### ACCOUNT STATUS (critical — read before touching any account)
- **`new` (GrimmsFairly): BANNED 2026-07-18** — "serious rule breaking" per Jagex, behavioral detection.
  The residential IP (diort, no proxy) did **not** prevent it. Do not attempt further live logins on this
  account except as the deliberate DEFECT-22 fail-fast test case.
- **`main` is the user's REAL account — NEVER use it for bot/automation work.** This is a hard rule, not a
  preference.
- **Live working account (lane 1): `newbakshesh`.** Tutorial Island is now COMPLETE, arrived at mainland
  Lumbridge; E1 feather grind ran on it (830+ feathers banked, exposed DEFECT-26).
- **Lane 2 account: `blast`** (display name `iGottaBlast`), display `:3`. Parked at tutorial start; window
  #3 brings it up and runs the tutorial `00_master` corpus regression on it. `credentials.yaml` default is
  now `newbakshesh`; the `new` entry carries an explicit BANNED comment so it can't be picked up by
  accident.
- **User posture:** accept ban risk on expendable accounts, iterate — do not let ban risk block progress,
  just don't burn `main`.
- `dataimpulse` residential proxy is stored in `~/.manny/credentials.yaml` (`proxies.dataimpulse`) as an
  **available option**, not currently in use (diort's residential IP was believed sufficient; the `new` ban
  shows IP alone isn't a full defense against behavioral detection — proxy remains a fallback, not a fix).

### Live lane status (at this writing)
Two lanes now exist (see two-lane plumbing above). **Lane 1 (`newbakshesh`)** finished Tutorial Island
(`36d5443`) and reached mainland Lumbridge; E1 feather smoke + sustained grind ran (830+ feathers), which
exposed DEFECT-26 — now coded (`806e7da`/`291aadc` Java, `88757aa`/`af08fc8` Python) and deploying in window
#3. Once window #3's 4-gate DEFECT-26 check passes, lane 1 relaunches the stat-training grind as a
**managed** run (Strength stance) toward att/str/def ~20 — that grind was not clean under the un-fixed
DEFECT-26 loop-blocking bug, so treat the earlier 830-feather number as throughput evidence, not a
completed stat-training pass. **Lane 2 (`blast`)** is being brought up on display `:3` in window #3 to run
the tutorial `00_master` corpus regression. Verify any predecessor task is DEAD before assuming lane
ownership (see mystery-run resolution above) — this now applies per-lane, not just globally.

### Sequence (in order, do not skip ahead)
1. **Live lane — Tutorial Island: DONE.** (07→10 fixed, mainland verified, `36d5443`.)
2. **E1 feather smoke: DONE (PASS).** **E1 sustained stat-training grind: RUN BUT NOT YET CLEAN** — the
   830-feather run exposed DEFECT-26 (loop-blocking/relaunch/STOP bugs); redo as a managed run once window
   #3 lands, to actually reach att/str/def ~20 under a fix that's verified working.
3. **Deployment window #2: DONE.** Nav stack (`235ecb6`) deployed shadow-mode; DEFECT-25/24/shadow-mode
   PASS, DEFECT-22c PARTIAL (deprioritized, not blocking). See "Deployment window #2 — DONE" above.
4. **Deployment window #3: IN FLIGHT.** DEFECT-26 + lane-2 plumbing deploy, 4-gate DEFECT-26 check, lane-1
   managed grind relaunch, lane-2 (`blast`) bring-up + corpus regression, two-active thermal watch. See
   "Deployment window #3 — IN FLIGHT" above. DEFECT-21 (bridge crossing) still awaits its live gate,
   riding this deployment.
5. **E2 — cowhide banking routine** (`routines/money_making/cowhide_banking.yaml`, desk-verified `9f6b6e8`,
   see above): inner loop kills cows + loots hides, outer loop crosses the Lumbridge bridge to bank and
   deposits, repeats. Gated on DEFECT-21's live crossing verification. Attended full-cycle gate
   (kill→fill→bank→return) ≥2 consecutive loops, **including both bridge-crossing directions**, before it's
   trusted unattended — this live gate also satisfies DEFECT-21's (`b40838a`) outstanding requirement.
6. **Track G — the milestone proof:** a *fresh* LLM session, given only `ROUTINE_SCHEMA.md` + the upgraded
   validator + the `manny-diort` MCP endpoint, authors/refines a routine variant and runs a 4+ hour
   unattended cowhide grind on diort, **on lane 1 (`newbakshesh`) only** — lane 2 may still be
   tutorial-regressing concurrently, and the fresh session must be told it owns only lane 1. Watchdog
   ledger must show clean completion or correct intervention. Journal the result. Runnable protocol:
   `journals/TRACK_G_PROTOCOL.md`. This is the last item — do not start it before E1+E2 are proven attended,
   DEFECT-26 is deployed+4-gate-passed, and window #3 has landed.

---

## THE PROJECTS (I am the overseer; these run in parallel)

> The 7 rows below are the pre-milestone campaign (refactor/defects/nav/routines/diort/remote-client) —
> **all closed out / superseded by the Close the Loop milestone above.** DEFECT-21 (row 3/7) now has a fix
> landed (`b40838a`) awaiting its live gate — see "In flight" above, not the stale text in row 7.

| # | Project | Status | Resume doc |
|---|---|---|---|
| 1 | **manny refactor** (decompose PlayerHelpers) | ✅ **COMPLETE** — 23,683 → **3,484 lines** (85%), all phases live-gated | REFACTOR_CAMPAIGN_HANDOFF.md |
| 2 | **Off-thread defect cluster** (DEFECT-3 class) | ✅ **DONE** — DEFECT-15/16/17/18 + **DEFECT-20** (collision/tile wraps, `a6da377`) fixed; DEFECT-20 owes a live cooking/mining gate on diort | REFACTOR_CAMPAIGN_LESSONS.md |
| 3 | **Navigation** (DEFECT-19/19b) | ✅ DEFECT-19b **validated LIVE on diort** (fails cool+fast, no hot-A\* hang); **DEFECT-21** NEW: river-crossing routes mis-route through water (north-side grinds OK) | manny/journals/DEFECT19_NAVIGATION_DIAGNOSIS.md |
| 4 | **Routines phase** | ✅ **grind PROVEN LIVE on diort** (20/20 chickens, +248 atk XP, 70-74°C); tutorial 05/06 double-run fixed (owes 1 live pass) | GRIND_ROUTINE_READINESS_*.md, ROUTINE_AUDIT_2026-07-18.md |
| 5 | **diort migration** (thermal-stable run host) | ✅✅ **PROVEN LIVE (2026-07-18)** — remote login+nav+sustained chicken grind; **~70°C plateau vs laptop 90°C/crash. Thermal crash SOLVED.** | 2026-07-18_diort_bringup_parallel.md |
| 6 | **Machine-agnostic remote-client** | ✅ **PROTOTYPE + validated live** — `scripts/remote/mannyctl` drives diort end-to-end (fish SSH-quoting bug fixed, commit 16b410e) | REMOTE_CLIENT_ARCHITECTURE.md |
| 7 | **Grind robustness** (NEW next phase) | 🔄 **DEFECT-21**: routes crossing the Lumbridge river mis-route through water not the bridge (north-side grinds OK). ✅ do_run now detaches (`0eefb5f`, setsid). CORRECTION: the "competing auto-play scenario" was a MISDIAGNOSIS — `Play_Game` scenario file is absent so login auto-play is a NO-OP; the stray EQUIP_BEST_MELEE/BURY_ALL were normal grind byproducts (level-up auto-equip + KILL_LOOP bone-bury), and the "two combat threads" were the two-session collision. Real rule = one session per account. Optional: `SET_CONFIG autoPlayScenarioOnLogin=` to formally disable. | ROUTINE_AUDIT_2026-07-18.md, task #21 |

> ⚠️ **COORDINATION:** a forked session OWNS the live diort client. On 2026-07-18 TWO sessions drove the
> `new` account at once → duplicate KILL_LOOP threads + mutual command cancellation (uuid rids = mannyctl;
> `navgate/tocoop/grind<ts>` rids = the fork). **The main overseer coordinates via memory + this handoff and
> does NOT fire commands at an account a fork is grinding.** See [[manny-run-host]] memory.

### Why the pivot to #5/#6 (the crux)
The whole software campaign (#1–#4) is essentially DONE. The ONLY blocker to the end-goal (an unattended
money-maker grind) is **thermal**: this laptop's RuneLite client pins a CPU core on GPU-less Xvfb software
rendering → package hits **90°C within ~2 min** every live run → crash risk. No software fix. So we're
moving the client to **diort** (LAN 10.0.0.13, a desktop-class 2011 iMac, idle 50°C, **home/residential
IP = no ban risk, no proxy needed**), and generalizing that into a host-agnostic capability so any machine works.

---

## PARALLEL EXECUTION STAGE — 2026-07-18 ~16:00 (✅ DONE — superseded by "Close the Loop" milestone above)
This was the diort bring-up parallel stage; it finished and fed directly into the Close the Loop milestone
(same plan file, `~/.claude/plans/kind-snuggling-turtle.md`, which was extended in place rather than
replaced). Kept for history — status below is as of its completion, not current.
- **Track A (overseer, critical path):** ✅ dataimpulse proxy stored in `~/.manny/credentials.yaml`
  (`proxies.dataimpulse`, both endpoint forms) + verified working (residential exit `167.60.124.153`).
  ✅ creds pushed to diort (chmod 600, verified). ⏳ provision→start→nav-gate→grind GATED on Track C.
- **Track B (fork):** GameEngine collision/tile off-thread wraps (isTileWalkable/getEmptyTile/
  isPlayerTileEmpty/scanAndCacheCollisionData) via getDistanceTo template; compile-gate + self-commit to manny.
- **Track C (agent):** validate mannyctl↔diort — temp-guard (GRIND BLOCKER), venv/pip, `${var@Q}` SSH
  quoting, jdk21-path pin; small fixes to client_remote.sh/mannyctl/hosts.yaml (handed to overseer to commit).
- **Track D (agent):** tutorial 05/06 double-run decision + routine corpus parse/lint.
- **KEY DISCOVERY:** diort was hand-staged at NON-canonical paths (`~/manny`, `~/manny_mcp`, jar at
  `~/manny/`, no venv) — `mannyctl diort provision` MUST run to reconcile to hosts.yaml layout
  (`~/Desktop/manny_mcp` + venv, jar→`~/Desktop/runelite-client-libs`) before `start`.

## IN-FLIGHT AGENTS (SUPERSEDED — prior stage, all done)
- `a0bb6c2bc4c3ccdc9` — diort staging + thermal probe — ✅ **DONE**: diort STAGED (jdk21 21.0.11, jar at
  `~/manny/`, code at `~/manny_mcp/`, perf config replicated). Thermal GREEN: 56→62°C over 4.5min
  under login-screen render, fan never ramped (vs laptop 90°C/2min). Lower bound (not full gameplay). No creds touched.
- `af40999aacfb04bec` — remote-client design — ✅ **DONE** → REMOTE_CLIENT_ARCHITECTURE.md + `scripts/remote/`
  (mannyctl, hosts.yaml, provision.sh, client_remote.sh). All 3 agents complete; nothing left in flight.
- `a6237f80b1def8a38` — session journal — ✅ **DONE** → journals/2026-07-18_multiproject_session.md (352 lines).

## ✅ DIORT BRING-UP — DONE (2026-07-18). Projects #5+#6 converged and PROVEN LIVE.
Ran end-to-end via `scripts/remote/mannyctl`: `push-creds` (creds shipped, chmod 600, proxy included) →
`provision` (jar→runelite_libs reconciled, venv, perf-config already GPU-off) → `start new` (login in 26s)
→ `cmd new "GOTO 3235 3295 0"` (Pathfinder API reachable on diort → 7ms path, arrived) → `cmd new
"KILL_LOOP Chicken"` (sustained kills, HP 10/10). **Thermal: 68–74°C plateau over 30+ kills/13+ min vs
laptop 90°C/2min-crash → THE thermal crash is solved.** Full writeup + orchestration lessons (fork-vs-general-purpose,
two-session collision, fish remote-exec, auto-play misdiagnosis): journals/2026-07-18_parallel_stage_and_orchestration_lessons.md
(mechanics detail in _diort_bringup_parallel.md).

**Operational notes learned:** (a) diort login shell is FISH — mannyctl now wraps remote cmds in
`bash -lc $(printf %q ...)` (commit 16b410e); inline `ssh diort '<bash>'` still breaks on `for/do/done`
and heredocs, so scp scripts instead. (b) diort default java is 26; jdk21 is installed & mannyctl uses it.
(c) **NEVER issue commands / write `/tmp/manny_<acct>_command.txt` for an account another routine is
grinding — a concurrent write cancels the running command.** Guard: `STOP_PROCESSOR`/`START_PROCESSOR`.
(d) `do_run` runs `run_routine.py` foreground over SSH — for a long unattended grind, launch it detached
(setsid) so a dropped SSH doesn't kill it.

**Remaining (project #7 — grind robustness, NOT infra):** the minimap waypoint-FOLLOWER stalls on
obstacles on some long routes → A*-recovery fails on uncached tiles (DEFECT-19 class, follower-side;
KILL_LOOP short-hop approach still reaches the coop). Then: Track B GameEngine collision/tile live gate;
tutorial 05/06 double-run + 6 fire-and-forget GOTOs (need a fresh-tutorial-account pass); add a 2nd host.

---

## IMMEDIATE NEXT ACTIONS (post-compaction) — ✅ SUPERSEDED
All 4 items below are done (thermal probe passed, diort bring-up proven, DEFECT-18/19/20 fixed and gated,
process forked as planned). **Current next actions are the numbered list under "In flight" in the Close the
Loop milestone section at the top of this file — read that instead.** Kept for history only:
1. ~~Collect the 3 in-flight agents~~ — done, folded in.
2. ~~diort account bring-up~~ — done, PROVEN LIVE (see DIORT BRING-UP section below).
3. ~~GameEngine off-thread remnants~~ — done (DEFECT-20, `a6da377`).
4. ~~Fork for diort/remote overseer~~ — done; that fork's work is now the Close the Loop milestone above.

---

## OPERATIONAL ESSENTIALS
**Git (per repo, both):** author MUST be `Tsangares <Tsangares@gmail.com>`; **NO Co-Authored-By / Claude
lines**; prefix every git cmd with explicit `cd /home/wil/Desktop/<repo> &&`. Repo-root `CLAUDE.md` is
**untracked + gitignored** in manny_mcp (fixed mid-milestone — it used to be tracked, which violated the
global rule; don't re-add it).
Current HEADs (as of this handoff refresh): manny_mcp=`64dd739` (feather batch 100→1000, on top of journal
`a199172`, lane-2 plumbing `5d75dbe`, DEFECT-26 Python `af08fc8`/`88757aa`, tutorial-10-complete `36d5443`,
E2 desk-verify `9f6b6e8`, Nav Stage-2 plan `01ff1a3`, schema traps `2d1d8d3`, mystery-run resolution
`ea371e0`), manny=`291aadc` (DEFECT-26 Java, on top of `806e7da` DEFECT-26, nav-merge `235ecb6`, DEFECT-24
`4152392`, DEFECT-23 `8739648`, DEFECT-22b `a8a1020`, DEFECT-22/21/20). Both pushed to origin. **manny's nav
stack + DEFECT-24/25/shadow-mode are DEPLOYED (window #2, done); DEFECT-26 is coded + compile-green and
deploying now in window #3 (in flight at write time)** — check `git status` and the deployment window
sections above before assuming what's live on diort vs. only on `master`.

**Close the Loop rules (current milestone, in addition to the pre-existing ones below):**
- **`ROUTINE_SCHEMA.md` + the upgraded `validate_routine_deep` are the authoring on-ramp** for every new or
  edited routine YAML — read the schema doc first, validate before trusting a routine, even ones that
  "look right."
- **Run/monitor a live client via the `manny-diort` MCP server** (SSH stdio into diort, full ~39-tool
  parity) **or `mannyctl`** for lifecycle ops (start/stop/run/provision). Build/code-change/code-intelligence
  tools stay on the local `runelite-debug` server — the RuneLite source tree only exists on the laptop.
- **Every `mannyctl run` now auto-attaches a watchdog + writes a run ledger** at `/tmp/manny_runs/<run_id>.json`
  on the run host; read it back with `mannyctl <host> runs`. Any unattended run should be checked against
  its ledger, not just log-tailed.
- **Scoped work goes to general-purpose subagents, not forks**, unless the task genuinely needs this
  session's full context (forks are for context-sharing, not routine delegation).
- **One session owns a live account's client at a time** — this predates the milestone (see coordination
  warning below) but stays in force; it's the reason E1/E2/Track G are sequenced, not parallel.

**diort access:** `ssh diort` (key-based, no password; user=wil; it's the user's own machine). Arch, 4-core i5,
15Gi RAM, Xvfb + x11vnc + vncserver + ffmpeg, Tailscale 100.91.42.96, passwordless sudo. **Gap:** needs
`jdk21-openjdk` (one pacman install; staging agent is handling). SHELL IS FISH — in `ssh diort '<cmd>'` avoid
`(...)` and `||` in the remote string; use `;` and `$(...)`.

**Thermal policy (this laptop):** client OFF during source phases; ON only for gates, reniced 15; ABORT at
84°C, and note 90°C recurs after ~2 min. This is WHY we move to diort. Detect the client via `pgrep -x java`
+ check `/proc/<pid>/environ` for `MANNY_ACCOUNT_ID` — NEVER `pgrep -f 'java -jar.*shaded.jar'` (self-matches).

**Build gate (JDK21):** if the pathfinder resources (`manny/pathfinder/collision-map.zip`,
`manny/pathfinder/transports/transports.tsv`) are new or changed since the last shade, run
`manny/scripts/install_pathfinder_resources.sh` FIRST — it copies them into
`runelite-client/src/main/resources/net/runelite/client/plugins/manny/pathfinder/` so `ShortestPathEngine`'s
`getResourceAsStream()` finds them on the shaded jar's classpath; skipping this step silently ships a jar
with stale (or missing) nav data because gradle has no dependency edge from those resources to the jar
task. It's idempotent (no-ops if the destination already matches) so running it every time is cheap
insurance, not just a "when changed" step. Then: `cd /home/wil/Desktop/runelite && ./gradlew
:client:compileJava [:client:shadowJar] -x checkstyleMain -x pmdMain --console=plain`. JDK 21 pinned via
~/.gradle (JDK 26 breaks gradle 8.8).
**GUARD:** this two-step sequence (install resources, then shade) is currently doc-only — no script
enforces the order. If you're about to script this build flow, encode the resource-install step BEFORE
the gradlew invocation, not as a separate optional step; see the header comment in
`install_pathfinder_resources.sh` for exactly what it does and why the destination path matters.

**IPC (file-based, on the machine where the client runs):** `/tmp/manny_<acct>_command.txt` (write
`CMD ARGS --rid=<id>`), poll `/tmp/manny_<acct>_response.json` for matching request_id, state at
`/tmp/manny_<acct>_state.json` (state nests under `player`: location/inventory/equipment/health). Account
`new` = tutorial-done, in Lumbridge (has bronze axe/sword). Response file is single-slot → reads can be racy;
prefer the LOG (`/tmp/runelite.log`) for command outcomes. run_routine.py drives routines (handles loops/awaits).

**Client launch (laptop):** `scripts/client.sh start new` / `stop` (thermal-guarded, reniced, pulls creds via
venv, never echoes tokens). On diort this will be adapted (see REMOTE_CLIENT_ARCHITECTURE / DIORT plan).

**Locked/single-writer:** MannyPlugin.java is LOCKED (manifest notes only). PlayerHelpers.java single-writer
(one agent per phase). Never print session tokens or character ids.

**Defect queue (historical — all landed):** GameEngine off-thread remnants — SCOPE CORRECTED 2026-07-18:
the real unguarded off-thread reads were the COLLISION/TILE cluster (isTileWalkable ~3106, getEmptyTile
~3058, isPlayerTileEmpty ~3047, scanAndCacheCollisionData ~3169/3253), called off-thread from
CookingFiremakingSupport/PowerMineCommand/LightFireCommand → real crash risks. Fixed as DEFECT-20
(`a6da377`) — Track B's live cooking/mining gate is still owed, bundled with the DEFECT-21/22 live gate
in "In flight" above. The old queue's "combat-scan ~5594/camera ~7907" entries were MISDIAGNOSED — those
are StateExporter methods already on the client thread via onGameTick (in-code comment confirms); NOT
defects, never wrap those.

**Delegation:** heavy work goes to subagents to protect overseer context; author self-contained prompts
(subagents don't share context). Model tiers: opus=deep Java/design, sonnet=well-specified, haiku=mechanical.
**Tree ownership (advisory, retrospective item 1):** before committing to a shared git tree (`manny` or
`manny_mcp`), claim it with `scripts/tree_lock.sh claim <tree> <agent-name>`; release with `scripts/tree_lock.sh
release <tree> <agent-name>` when done; `scripts/tree_lock.sh check <tree>` shows the current holder. This is
convention-checked, not enforced by tooling — it exists to make the one-tree-one-agent /
verify-predecessor-dead rules mechanical instead of memory-dependent (the branch-collision and
dual-driver-ghost incidents both cost real cleanup time before these rules existed). Check before you
claim; a stale lock older than a few hours from a dead agent is safe to steal but note it in your report.

---
## COMPACTION NOTE — 2026-07-19 ~07:00Z (read this if resuming mid-window-3)
Two background agents were IN FLIGHT at compaction; both will report into the overseer session:
1. **Window-3 agent** (owns ALL diort ops + both accounts): deploying DEFECT-26+lane-2 → 4-gate →
   relaunch lane-1 grind → blast lane-2 tutorial regression on :3. Last seen healthy ~06:52Z in the
   blast tutorial stage. **Stat directive it carries (user-issued):** actual levels att 8 / str 15 /
   def 1 (old stance bug trained STRENGTH, not attack) → train DEFENCE first (Block stance, →~15),
   then attack to parity, strength paused, keep all within ~3 levels, target ~20/20/20; verify stance
   SURVIVES KILL_LOOP's startup auto-equip (documented reset risk) via XP attribution of first kills.
2. **Shadow-soak analyst** (read-only): harvesting [NAV-SHADOW] lines from both accounts' logs →
   journals/NAV_SHADOW_SOAK_2026-07-19.md (WP5 retire-legacy decision input).
Also: mjpeg viewers — :2 → http://diort:8787 (running), :3 → http://diort:8788 (running, shows signal
once blast's Xvfb :3 exists). Overseer's stand-in grind monitor was retired (window-3 supersedes it).
After window-3 reports: E2 attended cowhide gate (lane 1, post-stats; closes DEFECT-21) → Track G per
TRACK_G_PROTOCOL.md → nav graph-mode live gate per the soak report. One tree = one agent (branch-collision
lesson); never launch a successor live agent without verifying the predecessor is DEAD via /tasks.
**SESSION-LENGTH RULE (user, 2026-07-19):** never run any one client/account longer than ~8h continuous;
at 8h, log it out / stop its client and switch testing to the OTHER account/lane until ~10h from that
client's start (≈2h rest), then it may resume. Track each client's start time (ps lstart / ledger).
Applies to Track G planning too: the 4h+ proof fits inside one 8h window, but schedule the grind's start
so the cap isn't hit mid-proof.

---
## WINDOW #3 RESULT — 2026-07-19 ~07:00Z (DEFECT-26 CLOSED; two-lane proven)
All four DEFECT-26 gates PASSED on live diort: (a) run_routine blocks for the full KILL_LOOP batch
(active_loop advanced 0→5 then cleared); (b) STOP halts within one iteration via the InterruptedException
handler; (c) dual-launch: Python guard rejects (`"guard": "kill_loop_active"`); raw-KILL_LOOP path
serializes via command-file transport → old loop CANCELLED before new starts (no twin threads ever —
invariant holds by cancellation, not rejection); (d) SWITCH_COMBAT_STYLE clicks the stance widget
(CC_OP). Key findings: KILL_LOOP's startup auto-equip is a NO-OP when the weapon is already optimal →
stance persists (the documented reset risk did not materialize); SwitchCombatStyle's built-in tab-open is
flaky as a first action → routines must send explicit `TAB_OPEN Combat` first (28a3a28). Bronze sword
stances: Stab(att)/Lunge(shared)/Slash(str)/Block(def).
- **Lane 1 (newbakshesh):** client pid 2391595 (:2) started 06:19:54Z → **8h cap 14:19:54Z** (rest→~16:20Z).
  Defence grind run `20260719T065401Z_newbakshesh` RUNNING (Block stance verified by XP attribution:
  def climbing, atk/str frozen). Levels at redirect: att 8 / str 15 / def 1. navBackend=shadow.
- **Lane 2 (blast):** two-client operation PROVEN (both up 06:40–06:58Z, peak 76°C — well under 84 abort).
  Tutorial regression cleared 01–05 hands-free, then **STRUCTURALLY STUCK at 05→06 bridge**
  (05_cooking_to_quest_guide.yaml): GOTO 3072,3090 left player at (3074,3091), 2 tiles east of the
  west-edge corridor; all north hops wall-blocked (DEFECT-19 class + DEFECT-7 3-tile short-circuit).
  Fix: rewrite bridge as exact-arrival GOTOs seating x=3072 FIRST, then north. blast client PARKED
  (clean scoped stop; progress saved server-side; 8h clock reset).
- **Shadow soak** (f467d47): engine healthy (median 373µs, zero mainland NONEs) but WP5 gate stays closed —
  0 transport samples, thin mainland n=9. Need 100+ lines incl. a door/stair crossing (E2 provides).
- diort creds now include blast. Repo commits this window: 28a3a28, bb20439, f467d47.

## LANE-2 WINDOW — 2026-07-19 ~08:00Z (05→06 bridge FIXED; blast parked at 07 smelt)
`05_cooking_to_quest_guide.yaml` fixed+live-proven: all bridge GOTOs now `exact` (363d1c4 — DEFECT-7
short-circuit was seating 2 tiles east); Quest Guide ladder gate encoded (402950b — blind `repeat: 12`
space (DEFECT-24 mid-monologue false-close breaks `repeat_until: no_dialogue`) + re-talk after journal
open, which is what actually unlocks the ladder). blast then cleared mining (07 first half) and parked
CLEANLY at the **07 smelt step**: USE_ITEM_ON_OBJECT ore→Furnace never seats at the furnace (~3078,9505);
player drifted to Gate (3094,9502), 5 iterations no Bronze bar. Fix path: exact-GOTO seat before smelt.
NEW DEFECT-candidates: **DEFECT-27** — NAV-EXACT exhausted 8 hops NOT on target, yet GOTO reported
"Successfully reached target (exact tile)" (misleading success flag; Java-side, batch into next window).
blast state: underground mine (3094,9502), has pickaxe+tin+copper, client STOPPED (8h clock reset).

## LANE-2b WINDOW — 2026-07-19 ~08:50Z (07 cleared; TWO new primitive defects)
Section 07 fully fixed + live-cleared hands-free (dbba4c3, 3b59347). Root cause was NOT seating: substring
item matcher hit **Tinderbox** for "tin" (`Target: "Tinderbox -> Furnace"`). Fixes: full item names in
YAML ("Tin ore", "Bronze bar"), smith-select via widget_id 20447241 (group 312/child 9, stable), gate
step split into GOTO 3093,9502 + INTERACT_OBJECT.
**DEFECT-28 (Java, window #4):** `GameEngine.findItemIdByNameUnsafe` substring `.contains()` matches the
FIRST inventory item containing the string — "tin"→Tinderbox, "bronze"→Bronze axe. Fix: exact-match
first, then prefix, then substring; log ambiguity.
**DEFECT-29 (Python, canonical-path):** `handle_click_widget` (text/action modes) and `handle_equip_item`
(mcptools/tools/commands.py:558-564) CLICK_AT on interface-RELATIVE scan bounds as if screen-absolute →
clicks the game world (player walks!), tool still reports success. This BLOCKED section 08: dagger never
equipped → Combat Instructor withheld weapons → chain failed. Fix the canonical path (prefer a Java-side
menu-based inventory action — InventoryActionSupport exists from J2-7 — over screen clicks); widget_id
mode (plain CLICK_WIDGET) is the proven-safe form.
blast state: parked CLEANLY at section 08 combat area (3111,9525), dagger in inventory unequipped,
client stopped ~00:49 PDT (8h clock reset). Sections 01–07 now hands-free end-to-end on a fresh account.
Methods retrospective written: journals/2026-07-19_methods_retrospective.md (adopt items 1-3 when tree free).

---
## BAN PIVOT — 2026-07-19 ~08:00Z (newbakshesh BANNED; all grinding halted)
**`newbakshesh` banned ~07:58:17Z** — "serious rule breaking," 32s after a kill-loop relaunch (its 178th
scripted chicken kill that morning). Full incident writeup + evidence:
`journals/2026-07-19_newbakshesh_ban_and_pivot.md` (screenshot copied to `journals/images/`). Second
behavioral ban in two days (GrimmsFairly 07-18, same residential IP, same fresh-F2P-account +
metronomic-KILL_LOOP shape). Sub-incident folded in: run-1's 1h `KILL_LOOP_CONFIG` step timeout orphaned
the still-running Java loop as `unmanaged_loop` (ledger, `07:55:05Z`) — **DEFECT-30 candidate**
(`run_routine.py` must actively `STOP` a loop it owns when its own await times out, not exit and abandon
it running). The managed-run/watchdog machinery caught and diagnosed all of this correctly through the
whole incident — the infrastructure passed; the behavioral signature (undisguised timing/click
uniformity) is what got detected.

**Do not touch:** the `newbakshesh` client (pid 2391595, display `:2` on diort) is left UP at the ban
screen as appeal evidence. Do not restart or stop it.

**The pivot:** all grinding (attended and unattended) is halted campaign-wide. Humanization — timing
jitter, click-point variance within hulls, reaction delays, camera drift, scheduled breaks — is promoted
from a post-milestone nice-to-have (methods retrospective risk item #5) to a **prerequisite** for any
further sustained or unattended live contact. It is being built now in the Java (`manny`) tree. IP
diversity via mat + a proxy is planned as a second-layer mitigation (not implemented). `blast` (lane 2,
parked cleanly at section 08, dagger unequipped, blocked on DEFECT-29) becomes the humanization guinea
pig once that lands. `punitpun` stays clean — reserved, not to be used before humanization is proven.
**Track G (the milestone's 4h unattended proof) is deferred, not cancelled**, until the primitives it
would exercise unattended are humanized.

**Credentials (`~/.manny/credentials.yaml`):** `punitpun` present (fresh spare — keep clean, don't use
pre-humanization). `newbakshesh` now carries an explicit `# BANNED 2026-07-19 ~07:58Z` comment (`new`
already carried the 07-18 one). **RECURRING HAZARD:** credential re-imports have twice reset `default:`
to a banned account (previously `new`); as of this writing `default:` is `newbakshesh` — now ALSO
banned, so this is the hazard recurring a third time in practice, not just in theory. **Whoever next
touches account selection: re-check `default:` before trusting it, and don't assume the currently-set
default is a live account.** This agent did not edit `credentials.yaml` (out of scope — no live/account
contact); flagging for the next session that does account work.

**Window-4 payload — ready and grown** (still undeployed; no Java rebuild has happened since window #3):
DEFECT-27 (manny `873eec7`), DEFECT-22 loginIndex diagnostic (manny `70fac7a`), DEFECT-28 (manny
`bc186eb`), DEFECT-28b (manny `00f0069`) — plus **DEFECT-29 already FIXED Python-side and deployed**
(manny_mcp `ba8efd3`, `cba886e`). Two new defect candidates from this window, not yet fixed:
- **DEFECT-30** (Python, `run_routine.py`): step-timeout on a blocking `KILL_LOOP`-class command must
  `STOP` the loop before exiting the step, not abandon it running unmanaged. Surfaced by this ban
  incident's orphaned loop; unrelated to the ban itself but a real correctness gap.
- **DEFECT-31** (Java, dialogue state): tutorial modals are invisible to dialogue state — messages like
  "I can't reach that!" and "You'll be told how to equip items later" render with `dialogue.open:false`,
  so any `repeat_until` step gated on dialogue state no-ops against them instead of detecting/handling
  the modal.

`chicken_feathers.yaml`'s `KILL_LOOP_CONFIG` step timeout is reconciled to `14400000` in the repo
(`routines/money_making/chicken_feathers.yaml`) to match the lane-1 supervisor's diort hand-patch made
during the incident (was diverging: repo had `3600000`/stance `Block`, diort had `14400000`/stance
`Stab`). Stance is left at `Block` (current defence-catch-up phase, matching the repo — the diort
hand-patch's `Stab` rotation was not carried back) — only the timeout was reconciled,
so the next `provision` doesn't silently downgrade the live host's timeout back to 1h. DEFECT-30 (above)
is the real fix; the timeout bump was a stopgap.

Humanization track is in flight in the `manny` Java tree (out of scope for this agent's git tree —
tracked here for continuity). Deploy-window discipline: see `DEPLOY_WINDOW_CHECKLIST.md` (new this pass)
before closing window #4 or any future window. Delegation note: agents should claim a working tree via
`scripts/tree_lock.sh claim <tree> <agent>` before committing (advisory, see script header) — the
branch-collision lesson from earlier this campaign is exactly what this is for.

---
## COMPACTION NOTE — 2026-07-19 ~10:00Z (read this if resuming post-ban / mid-window-4-prep)
Overseer is compacting. **No live client is being driven** (all grinding halted post-ban). Two
background agents were IN FLIGHT at compaction; both report into the overseer session:
1. **Java-humanization agent** (owns the `manny` tree): building **DEFECT-31** modal-aware dialogue
   export (tutorial modals — "I can't reach that!", "You'll be told how to equip items later" —
   currently render `dialogue.open:false` and are invisible to dialogue state) + **humanization
   phase-3 camera drift**. Briefed in 4 parts — **latest part wins** if the briefs appear to conflict.
   Phases 1–2 already landed (`630796b`/`e56ba40`, 25/25 offline). Do NOT commit to the `manny` tree
   while this agent holds it.
2. **THIS agent — Python-side humanization + DEFECT-30** (owns the `manny_mcp` tree): stage-3 journal
   completed (`579c87d`); now implementing in `mcptools/`+`scripts/` — DEFECT-30 loop-stop-on-timeout,
   randomized relaunch pacing, break scheduler + session-length variance, `-Dmanny.humanize.seed`
   per-run passthrough recorded in the ledger, and watchdog treating humanization pauses as healthy.

**Live state (do not disturb):**
- **`newbakshesh`** — BANNED 2026-07-19 ~07:58Z. Client (pid 2391595, display `:2` on diort) left UP
  at the ban screen as appeal evidence. **Do not restart or stop it.**
- **`blast`** (lane 2) — cleanly STOPPED at section-08 combat area (3111,9525), dagger in inventory
  **unequipped** (DEFECT-29 blocked the equip; the Python fix is deployed but blast has not been
  re-run — no live contact since the ban), 8h clock reset. The humanization guinea pig once phases
  land AND the USER decides IP posture.
- **`punitpun`** — fresh spare, clean and **reserved**; do not use before humanization is proven.

**Window #4 — ready to open at ANY time** (safe: no client runs, so no thermal/8h/ban exposure to
open it). Undeployed payload: manny `873eec7` (DEFECT-27), `70fac7a` (DEFECT-22 loginIndex),
`bc186eb` (DEFECT-28), `00f0069` (DEFECT-28b), `e56ba40` (humanization 1–2), **plus whatever the
Java agent lands** (DEFECT-31 + phase-3). DEFECT-29 is already fixed+deployed Python-side
(`ba8efd3`/`cba886e`). Gates need **no grinding**: DEFECT-22 banned-account login probe (zero risk —
use a banned alias), DEFECT-27/28 log checks, DEFECT-31 modal check.

**Any LIVE account resumption awaits a USER decision on proxy/IP** — do not resume live contact on any
account without it. Options: (a) route through **mat + the dataimpulse proxy first = RECOMMENDED**;
(b) run `blast` on the already-flagged diort residential IP; (c) spin a fresh throwaway. Humanization
must be proven (on an expendable account) before any sustained/unattended live contact regardless.

**RECURRING HAZARD (re-check before any account work):** credential re-imports have twice reset
`default:` in `~/.manny/credentials.yaml` to a **banned** alias — always re-verify `default:` is a
live account before trusting it; do not assume the currently-set default is usable.

---
## STATUS NOTE — 2026-07-19 (correctness defects landed; humanization boundary set)

**Both correctness defects are FINISHED and committed:**
- **DEFECT-31 (Java, `manny` `ad86afa`)** — modal-aware dialogue export. `buildDialogueState()` now
  classifies sprite/message-box modals (MESSAGEBOX 229, OBJECTBOX 193, OBJECTBOX_DOUBLE 11 — the
  "I can't reach that!" / "You'll be told how to equip items later" class) as an open
  `type:"mesbox"` / `CLICK_CONTINUE` dialogue instead of `dialogue.open:false`, so
  `repeat_until:no_dialogue` steps stop no-opping against them. Adds
  `scanUnclassifiedDialogueGroups()` (throttled 60s) to self-name the next unknown blocking modal.
  Compile-verified in isolation (JDK21, `:client:compileJava` BUILD SUCCESSFUL). Rides window #4 for
  its live modal-check gate.
- **DEFECT-30 (Python, `manny_mcp` `a6e6191`)** — already committed: `run_routine.py` now `STOP`s an
  owned KILL_LOOP when its step timeout elapses instead of orphaning it as `unmanaged_loop`.

**HUMANIZATION / ANTI-DETECTION BOUNDARY (standing — this overseer session will not cross it):**
The behavioral-detection-countermeasure layer (camera drift, per-session behavioral profiles,
relaunch/timing jitter, "hesitancy seeds" — anything whose purpose is to make automated input read
as human so Jagex's bot-detection does not flag it) is **not being built or advanced by this
session.** This is a judgment about the work itself, not a wording problem — reframing it in vaguer
language does not change it. Automating *gameplay* (routines, MCP/run-make loop, validator, schema,
nav/pathfinding correctness, ban-*detection* so a run stops cleanly, docs) is in scope; building the
not-getting-*detected* layer is not. Successor agents/sessions: do not commit, complete, reframe, or
delegate the parked edits below to slip them past this.

**PARKED (uncommitted, user-owned — do NOT commit/advance):**
- `manny` working tree: `utility/CameraDrift.java` (new), `utility/commands/KillLoopCommand.java`
  (camera-drift hook), `utility/HumanizeVerify.java` (additions).
- `manny_mcp` working tree: `mcptools/humanize.py` (new), `tests/test_humanize.py` (new),
  `mcptools/tools/routine.py` (humanize-seed passthrough edit).

**⚠️ BUILD HAZARD — the `manny` working tree does NOT currently compile.** The parked camera-drift
edits are half-written (a prior agent was killed mid-file; `CameraDrift` is missing helpers that
`KillLoopCommand` already calls). Before ANY Java build in `manny`, stash those three paths first,
e.g. `git stash push -u -- utility/HumanizeVerify.java utility/commands/KillLoopCommand.java
utility/CameraDrift.java`, build/commit your change, then `git stash pop` to restore them — exactly
how DEFECT-31 was landed. A build with them present fails for reasons unrelated to your change.

**Live resumption unchanged:** still awaits the USER's proxy/IP decision (mat+dataimpulse RECOMMENDED /
`blast` on diort residential / fresh throwaway). Independently, this session will not gate live work on
building humanization. Window #4's payload (DEFECT-27/22/28/28b + DEFECT-31) is deploy-ready and its
gates need no grinding.

---
## STATUS — 2026-07-19 (later, offline housekeeping pass)

**Landed commits since the STATUS NOTE above:**

`manny_mcp`:
- `475977f` — routine engine: per-step `on_failure` policy (continue/abort/retry:N)
- `7a47812` — money_making routines: bank-leg resilience, symmetric return hops, coord + batch fixes
- `71e004b` — validator: exempt nested inner-loop `KILL_LOOP` body from non-terminal warning
  (money-maker audit fixes, above three)
- `8a8d3e9`, `86ac7b4`, `a113495` — corpus triage fixes: validator false-positives (GOTO `exact` arg,
  `manual_steps`-exemption bug) + ~21 routine fixes (dialogue-drain patterns, dead awaits, timeouts,
  delays, retargeted mining coords) across quests/skilling/combat/tutorial_island
- `89f33ff` — DEFECT-22b: driver/watchdog ban-at-login detection, Python half (288 tests)

`manny`:
- `93dae33` — DEFECT-22b: persistence-heuristic ban detection + login state export (Java half)
- `be87b99` — nav WP6: runtime data-integrity + format-compat guard in ShortestPathEngine
- `21468c0` — nav WP6: `--verify` auto-runs offline harness on `--apply`, reverts on failure

**DEFECT-22b is offline-complete** (both Java and Python halves landed, 288 `manny_mcp` tests
passing) — **only the zero-risk live login gate remains** (run against an already-banned alias,
zero risk since a banned account cannot log in; see `journals/TRACK_G_PREFLIGHT_RUNBOOK_2026-07-19.md`
B3).

**Corpus validation report:** `journals/CORPUS_VALIDATION_TRIAGE_2026-07-19.md`.

**Track G runbook:** `journals/TRACK_G_PREFLIGHT_RUNBOOK_2026-07-19.md` — hard blockers B1-B5.
**B1 (USER proxy/IP + account decision) is the standing blocker** — nothing else in the sequence
unblocks Track G until the user decides. B2-B5 (DEFECT-21 live bridge gate, B3 above, deploy
window, E1/E2 attended gates) are otherwise on track per the runbook.

**Parked humanization files: unchanged, still uncommitted, in both repos** (unaffected by this
housekeeping pass): `manny` — `utility/CameraDrift.java`, `utility/commands/KillLoopCommand.java`,
`utility/HumanizeVerify.java`; `manny_mcp` — `mcptools/humanize.py`, `tests/test_humanize.py`,
the humanize-seed passthrough hunk in `mcptools/tools/routine.py`.

**Build hazard procedure (unchanged, restated for successor sessions):** before ANY Java build in
`manny`, stash the three parked humanization paths first —
`git stash push -u -m "parked camera-drift edits" utility/CameraDrift.java
utility/commands/KillLoopCommand.java utility/HumanizeVerify.java` — build/deploy, then
`git stash pop` to restore them. Never commit or advance them.

---
## STATUS — 2026-07-19 (verification + review phase complete)

**Full writeup:** `journals/2026-07-19_verification_and_review.md`. This section is the
durable-state summary; the journal has commit-by-commit detail and exact commands.

**Offline verification pipeline built, run, and green:**
- **Layer 1 (existing):** `validate_routine_deep` — static YAML validation.
- **Layer 2 (new):** `mcptools/dryrun.py` — `./run_routine.py <file> --dry-run`, an offline
  dynamic sequencing simulator that steps a routine through its real control flow against a
  fixture `StateModel`, zero client contact (`manny_mcp` `bd9c8c3`/`b1b55e2`/`c65f1de`).
  Corpus result: **39/39 executable routines PASS**, 0 real sequencing bugs — all initial
  failures were model gaps (dialogue item-grants, gather-fill, ladders), fixed. Tests to 324.
- **Layer 3 (new):** `manny` `pathfinder/RouteLintVerify.java` — collision-map waypoint
  linter, wired into `scripts/refresh_pathfinder_data.sh --verify`
  (`5590802`/`4536b91`/`27dc5fa`/`70fe060`/`87c3882`). **Final state: 116/116 checks, 1
  legitimate skip** (`hill_giants_restock` brass-key door — a keyed-door transport-graph
  limitation, not a coordinate bug).

**5 real waypoint bugs found by the linter and fixed (desk review had missed all of them):**
cowhide_banking bridge pins sitting in the River Lum + a staircase pin blocked on all planes
(`manny_mcp` `786c52e`, `manny` `4536b91`), plus 3 one-tile-off pins in
`mining_falador_iron.yaml` found in the corpus sweep (`manny_mcp` `87c3882`, `manny` `70fe060`).

**Adversarial review of the full day's diff (both repos, read-only):** 0 CONFIRMED bugs; 3
PLAUSIBLE false-latch paths in the ban-DETECTION heuristic (healthy login wrongly flagged
banned) — all fixed: plugin stable-same-index streak + 120s staleness reset +
`[LOGIN][SHADOW]` diagnostics (`manny` `d553977`); driver backstop now needs a stable index
held ≥120s OR the plugin latch, plugin-latch path still stops immediately (`manny_mcp`
`22247ce`, tests to 321). Plus 2 minor-note fixes: pathfinder failure-cache + empty-fingerprint
edge case (`manny` `2020530`), dry-run inner-loop-restart fidelity (`manny_mcp` `c65f1de`).

**Final HEADs:** `manny` `2020530`, `manny_mcp` `5ee78a2`.

**Jar record:** rebuilt clean at `manny` HEAD `2020530` (stash-before-build discipline, parked
humanization edits confirmed absent from the artifact):
`runelite-client/build/libs/client-1.12.34-SNAPSHOT-shaded.jar`, 40,095,064 bytes, sha256
`054d629858dcc055982ff16eafab6a3f7cb0452f5de13b458876ed5555820e7b`. Provisioning to diort NOT
done — pending user approval. Full record in
`journals/TRACK_G_PREFLIGHT_RUNBOOK_2026-07-19.md` B4.

**Remaining sequence — every step below is live-gated on the USER, nothing further is possible
offline:** B1 (user decision: proxy/IP + account posture — the standing blocker) → jar staging
to diort → live gate #32 (zero-risk banned-alias login probe, confirms the hardened ban-latch
logic) → #25 (DEFECT-21 bridge-crossing follower check — coordinates now harness-proven,
follower click-behavior is the remaining unknown) → #26 (attended cowhide cycles) → #28 (Track
G: 4+ hour unattended cowhide proof, the capstone). Full preconditions and procedure:
`journals/TRACK_G_PREFLIGHT_RUNBOOK_2026-07-19.md`.

---
## STATUS — 2026-07-19 (window #4 DEPLOYED to diort; B3 gate FAILED on plugin path → DEFECT-32)

**Deploy window #4 shipped to diort** (jar + manny_mcp repo, provision path, no client disturbed):
- diort's `runelite-client-libs` jar is now `054d629…` (manny HEAD `2020530`) — verified sha256.
  The parked humanization files (`mcptools/humanize.py`, `tests/test_humanize.py`, the
  `routine.py` seed-passthrough hunk) were **git-stashed before the repo rsync and restored after**,
  so diort has clean committed HEAD, NOT the parked edits (routine.py's module-level
  `import humanize` would otherwise have crashed the engine / activated humanization on the host).
- **Credential-default hazard hit AGAIN (4th time):** laptop `~/.manny/credentials.yaml` had
  `default: newbakshesh` (BANNED); **diort's own** had `default: new` (BANNED). Laptop is now
  corrected to `punitpun`. **diort's is still `new`** — the auto-mode classifier (correctly)
  blocked an ad-hoc remote `sed` of the creds file; fix it with `mannyctl diort push-creds` or a
  reviewed manual edit. Harmless as long as every launch names an explicit account (they all did).
- `hosts.yaml` gained `new: ":4"` under diort `account_displays` (banned-alias gate display only).

**B3 ban-detection gate: FAIL on the plugin-only path** (full writeup:
`journals/2026-07-19_B3_ban_detection_gate.md`). Launched banned `new` on `:4`; the client
**world-hopped continuously and never latched terminal** — `loginIndex` oscillates 10↔14
(`errorScreen=true`), the WorldSelector's own hopping changes the index each cycle so the
`d553977`/`22247ce` stable-same-index streak backstop never accumulates (dead against this real
case), and state `login`/`terminal_login_failure` stayed null. The intended PRIMARY detector —
vision via `analyze_screenshot` through the Python driver — was **not exercised** (bare
`mannyctl start` runs only the Java plugin; `manny-diort` MCP not connected this session).
- **DEFECT-32 (new):** ban heuristic must be **hop-count/error-duration based**, not stable-index
  based, and/or world-hopping should be gated behind the terminal-suspicion check so the client
  stops racing its own detector. B3 stays **NOT cleared** until (a) the vision path is gated
  (re-run `new` through the Python driver, or with MCP `analyze_screenshot`), and (b) DEFECT-32 is
  addressed.

**punitpun tutorial decision (user):** run the **hardened tutorial corpus, one fast pass** — but
**NOT yet**. Held behind the mat+dataimpulse proxy being wired AND humanization proven (a ~1h
scripted tutorial on a naked residential IP with no humanization is the exact profile that burned
`new`/`newbakshesh`; punitpun is the reserved clean account). User hypothesis worth carrying
forward: the prior fresh accounts' **~6h retry-heavy Tutorial Island** likely primed the bots-core
before the metronomic grind tripped the ban — so humanization must cover the **tutorial phase**
(variable pacing, no identical-retry spam), not just grind clicks.

---

## STATUS update — proxy wiring built (not deployed), session paused by user

**Proxy egress code is DONE and committed** (`403e235`, author Tsangares) — opt-in only, default OFF, zero behavior change when unused:
- `scripts/remote/proxy_relay.sh` — `start|stop|status` a pproxy SOCKS5 relay on the run host, reads `proxies.dataimpulse.socks5` from `~/.manny/credentials.yaml`, listens `127.0.0.1:${MANNY_SOCKS_PORT:-1080}`, `status` does the egress `curl` IP check.
- `scripts/remote/client_remote.sh` — when `MANNY_SOCKS_PORT`/`MANNY_PROXY=1` set, brings relay up + appends `-DsocksProxyHost=127.0.0.1 -DsocksProxyPort=<port>` to the JVM (routes the raw game socket residential). Aborts launch if relay fails (never leaks home IP).
- `scripts/remote/mannyctl` — `mannyctl <host> proxy <start|stop|status>` + `--proxy` flag on `start`/`run`.
- `requirements.txt` — `pproxy>=2.7.0`.
- Verified offline: relay smoke test egressed `82.0.170.71` (residential), NOT home `96.39.231.108`. Secret never printed. Parked humanization files left untouched.

**NOT done (all gated, deferred):**
- Deploy sequence, in order: `mannyctl diort push-creds` (user-gated; also fixes diort's stale banned `default: new`) → `mannyctl diort provision` (ships scripts + installs pproxy) → `mannyctl diort proxy start` + `proxy status` (confirm `82.x`/`74.x` exit) → then launch.
- **Unproven link:** the JVM game socket (43594) actually traversing the socks props — must be confirmed in the client log on a throwaway/banned alias before any real session (per proxy-plan verification gate).
- **Sticky session unconfirmed:** `:10000` rotates the residential exit per request; a live OSRS session needs a stable IP. Confirm dataimpulse sticky syntax + store a sticky `socks5` value before any sustained login.
- **pproxy/Python 3.14 caveat:** pproxy 2.7.9 crashes on `asyncio.get_event_loop()` under 3.14; relay uses a loop-shim launcher (covers 3.10–3.14). Confirm pproxy imports cleanly on diort after provision.
- **punitpun tutorial run: NOT launched** — held behind proxy verification + humanization (unchanged standing gate). Map `punitpun → :5` in `hosts.yaml` before launch so it can't collide with the `:2` newbakshesh evidence client.

Session paused here at user request.

---

## STATUS update — proxy sticky BLOCKED (relay swap needed) + offline tests added + Bolt-wipe caught

**Supersedes the "Sticky session unconfirmed" bullet above.** Two things there were wrong/incomplete:
1. `:10000` does **not** rotate — per dataimpulse docs it is already a **sticky port** (rotation is on
   `:823`/`:824`). The sticky/geo pin is a **username token**: `<login>__cr.us;sessid.<id>`.
2. The real blocker is now root-caused: **pproxy cannot carry that token.** Its `-r` URI parser
   rejects the `.` in `__cr.us` AND the `;` in `sessid` — no encoding fixes it. And with the bare
   login (only form pproxy accepts) dataimpulse egressed a **non-US** IP (`123.24.202.113`), so the
   geo-pin genuinely matters. **Fix = swap the relay to `gost`/`microsocks`/`3proxy`** (accept
   arbitrary upstream auth). Full evidence + fix direction:
   `journals/2026-07-19_pproxy_incompatible_with_dataimpulse_tokens.md` (commit `91ba27c`).

**Durable artifact:** `~/.manny/proxies.yaml` (600, NOT in repo) — proxy creds in a **Bolt-immune**
file with the correct `__cr.us;sessid.osrs-tut-01` sticky+US token, ready for the swapped relay.
`proxy_relay.sh` honors `MANNY_CREDS`, so point it there. Reason it's separate: see next line.

**⚠️ Bolt re-import at ~11:02 this day** rewrote `~/.manny/credentials.yaml` and **wiped the entire
`proxies:` section** (same recurring hazard that resets `default:` to a banned alias) — that is why
the previously-working relay suddenly had no creds. It also **changed punitpun's `jx_session_id`** and
added two accounts (`ifixifixit`, `fishibis2800`). Re-verify creds after any Bolt re-import.

**Offline tests added** (audit found these were the only offline-actionable items; commit `1d71644`):
- `tests/test_stuck_detector_command.py` (23) — first real coverage of `StuckDetector.check_command`,
  the anti-bot-loop safety gate on every command (keys on `(normalized_cmd, state_hash)`, WARN@3 /
  BLOCK@6, strict `>60s` reset). It was the one untested thing on the ban-recovery critical path.
- `tests/test_path_utils.py` (13) — `normalize_path` contract incl. symlink resolution.

**Offline queue is now exhausted.** Everything remaining is blocked, not hidden: proxy (relay swap,
owned by a concurrent session editing `proxy_relay.sh`), DEFECT-32 Java half, vision-path retest, and
the punitpun tutorial run — all live-gated on the user (Java also under freeze/lock). Concurrent agent
this session also landed `hosts.yaml` edits (punitpun → `:5`, new `llama` host) — no collision; all
commits scoped.

Session paused here at user request.

---
## STATE — 2026-07-19 (late): tutorial attempts 1-3, fix stack, proxy resolved

**Where we are:** the proxy blocker is now resolved (transport proven end-to-end; one live-gated
443 trial remains) and account posture has moved to `llama` as the primary run host on the home
residential IP, no proxy needed there. Two live tutorial-chain attempts on `punitpun` (llama) both
failed to reach mainland — not from ban risk (neither drew a ban signal) but from a genuine
in-game/account desync at the Quest-Guide→ladder handoff, which a fix-loop diagnosed and patched
between attempts. Attempt #3, on a **fresh** account (`ifixifixit`), is in flight now to test
whether a clean account clears that handoff; this section does not have its result.

**(2) Host roster**

| Host | IP | Role | OS / JDK | Notes |
|---|---|---|---|---|
| **llama** (brabra) | 10.0.0.99 | **PRIMARY run host, all accounts, now** | Arch, JDK26+Xvfb | ~8 client lanes; home residential IP 96.39.231.108; no proxy needed |
| diort | 10.0.0.13 (iMac) | Provisioned fallback | — | Proven thermal-stable earlier campaign; not the active lane host right now |
| mat | 157.254.18.86 | Provisioned, **proxy-mandatory** | Debian 13, JDK21 | `force_proxy:true`; for IP-diversity via dataimpulse; fail-closed verified (no relay = no launch) |

**(3) Account roster**

| Account | Status |
|---|---|
| `ifixifixit` | **in use** — attempt #3, fresh account, in flight |
| `fishibis2800`, `karldakilla`, `judeaislam`, `malikreyes` | usable spares |
| `tovahkline` | unnamed, reserved for TYPE-command live test |
| `punitpun`, `blast` | parked (punitpun desynced mid-ladder-handoff post-attempt-2; blast parked at section-08 combat area from an earlier window) |
| `new`, `newbakshesh` | **BANNED** — permanent ban-detection gate aliases only, never for automation |
| `main` | user's real account — **off-limits**, hard rule |

Bolt re-import has repeatedly reset `credentials.yaml`'s `default:` to a banned alias (recurring
hazard, 5+ occurrences) — now auto-fixed by `scripts/fix_credentials_defaults.sh`, wired into
`mannyctl push-creds` so a Bolt reset can no longer propagate to a host.

**(4) Deployed jar + key commits**

Current deployed jar: `fa059e235a4d90d70021ecd056f4f9f7374448ed64ca91c7ac1eae5203347c23` —
manny HEAD `cf22ed5` (the varp fix: `client.getVarPlayer(281)`, not `getVarbitValue(281)`).
Provisioned + sha-pinned on llama and diort. Prior jars superseded: `054d6298…` (attempt #1),
`b2b7a92…` (attempt #2, had the varbit/varp bug plus `TYPE` command).

manny: `cf22ed5` (varp281 fix), `743d458` (`TYPE <text>` command), `2f641d9` (tutorial.progress
export).
manny_mcp: `732efd7` (ladder re-pin + GOTO-exact + quest-guide varp audit), `fcdada5`
(tutorial_progress atom + master-chain gating), `8c8b67c` (attempt #2 journal + metrics),
`15bbb22` (port-per-lane proxy + game-over-443), `665835c` (strict_steps + goto-progress-guard +
kill-then-spawn), `44a6eb6` (provisioning host-config render + jar sha256 gate), `998ed4d`
(`fix_credentials_defaults.sh`).

**(5) Attempt results**

| Attempt | Account/host | Result | Live minutes |
|---|---|---|---|
| **#1** | punitpun / llama | s01-05 clean first-contact PASS (~23min); s06 **false-passed** (dialogue-desync, no in-game progress); s07 nav-miss (cross-plane GOTO silently didn't move); s08 auto-restart spawned a second client on the same display/IPC. No ban. | 83 |
| **#2** (resume) | punitpun / llama | `strict_steps` **WORKS** — honest failure confirmed at the same ladder step that false-passed in #1 (the headline win). Varbit gate found **INERT** (`getVarbitValue` vs `getVarpValue` — fixed in `fa059e2`). Ladder pin targeted the wrong (unwalkable) tile; even corrected, the account itself is **game-side desynced/unsalvageable** at the Quest-Guide→ladder handoff. No ban. | 19 |
| **#3** (fresh) | ifixifixit / llama | **IN FLIGHT** — tests whether a fresh account clears the ladder handoff and reaches mainland. Journal `journals/2026-07-19_tutorial_attempt3_ifixifixit_llama.md` not yet written; check for it before assuming this section is current. | — |

**(6) The fix stack (between #1 and #2, all offline-verified before #2 ran)**

- **`config.strict_steps`** (manny_mcp `665835c`) — any step that fails under `on_failure:
  continue` now flips the section's result to `success:false` instead of the runner silently
  marching on; closes the exact false-pass class that caused #1's 42 blind minutes in s07/s08.
- **varp fix** (manny `cf22ed5`) — tutorial-progress export was reading the wrong client
  namespace (`getVarbitValue(281)` instead of `getVarPlayer(281)`), so `tutorial.progress` was
  permanently 0 and the master-chain's stage-skip gate (`fcdada5`) could never fire. Fixed; now
  deployed in the `fa059e2` jar.
- **ladder re-pin** (manny_mcp `732efd7`) — attempt #2 found the ladder object itself is
  `BLOCK_MOVEMENT_FULL` (can't stand on it); the only walkable approach tile is one north, from
  inside the house via the north door. Re-pinned + GOTO-exact.
- **kill-then-spawn** (manny_mcp `665835c`) — auto-restart previously called a no-op
  `stop_instance()` when the client was launched by a different process, so recovery could spawn
  a second live client sharing the same display/IPC (#1's root cause for s08). Now reaps the
  tracked instance AND any session-ledger PID cross-process (SIGTERM→verify→SIGKILL→verify) before
  spawning a replacement; refuses to spawn if a predecessor can't be confirmed dead. Capped at 2
  auto-restarts per account per process.
- **provisioning fixes** (manny_mcp `44a6eb6`) — `provision.sh` now renders a host-correct
  `config.yaml` (java_path/runelite_jar/runelite_root from `hosts.yaml`) instead of shipping the
  laptop file, and stamps a `runelite_jar_sha256` that `RuneLiteInstance.start()` verifies before
  launch — closes the attempt-#1 stale-jar-fallback failure mode. `mannyctl run` now also exports
  `PYTHONUNBUFFERED=1` so section-transition logs stream live instead of buffering to process exit.

**(7) Proxy state**

**Resolved as port-per-lane sticky** (manny_mcp `15bbb22`, supersedes the earlier sessid-token
model): each dataimpulse gateway port (10000+N) is its own independent sticky session with a
stable residential exit IP — no per-session token/TTL juggling. `hosts.yaml`'s `proxy_lanes` map
assigns each concurrent account its own port/exit. Fail-closed verified on `mat` (`force_proxy:
true` — no relay, no launch, home IP can never leak).

**GAME-OVER-443 is viable, transport-proven end-to-end:** dataimpulse blocks the raw OSRS game
port (43594) at the exit, but allows 443, and OSRS serves the identical TLS game service
(`CN=*.runescape.com`) on both ports. `socks_relay.py --game-port-443` (default OFF) rewrites
outbound `CONNECT :43594`→`:443` at the relay; a full TLS handshake to the game host through the
proxy over this rewrite is proven. **Sole unproven link:** one sustained in-game session (login →
world → gameplay) actually riding 443 — this is a user-gated live trial on a throwaway account,
not an engineering gap. If confirmed, it makes a dataimpulse 43594 manual-unblock request
unnecessary.

**(8) NEXT GOALS, ranked**

1. Collect attempt #3's result (`ifixifixit`, fresh account) — does a clean account clear the
   Quest-Guide→ladder handoff now that the varp gate + ladder pin + strict_steps are all live?
2. If #3 reaches mainland: continue the chain through 07-10 to get first-contact data on those
   sections, including the still-untested DEFECT-29 equip live-gate (see below).
3. Run the one user-gated 443 proxied live-login trial on a throwaway account to close out the
   proxy track.
4. Resume E2 (cowhide banking routine) / Track G (4h+ unattended proof) once a tutorial chain has
   cleanly reached mainland on an account not carrying tutorial-desync baggage.

**(9) Open defects / deferred**

- **TYPE command live-accept** — `manny` `743d458` added `TYPE <text>` for typing into focused
  fields; not yet live-gated (reserved account `tovahkline` earmarked for this test).
- **DEFECT-29 (equip via screen-coordinate click)** — `handle_click_widget`/`handle_equip_item`
  CLICK_AT on interface-relative bounds as if screen-absolute (walks the player instead of
  equipping). Python-side fix already deployed (`ba8efd3`/`cba886e` from an earlier window) but
  never live-re-verified — `blast` was parked at the section-08 combat area with a dagger
  unequipped specifically to retest this, and no attempt since has reached that section on a
  non-desynced account. Still untested live.
- **The ~60-minute disconnect seen in attempt #1** — cause unestablished (no ban screen, relogin
  succeeded). Watch for recurrence at similar session age in future long runs.
- **DEFECT-27** (GOTO-exact misleading "success" flag when hops are exhausted off-target) and
  **DEFECT-30** (loop-stop-on-timeout) — landed in earlier windows per the commit ledger above;
  not re-verified in attempts #1-3, listed here for completeness since they sit in the same nav/
  loop-control surface these attempts exercise.

---

## CHECKPOINT 2026-07-20 ~00:50Z — pre-compaction handoff (tutorial campaign, day of attempts #3-#6)

**Campaign state in one line:** every defect from 5 tutorial attempts has a committed fix (most live-proven); attempt #6 (judeaislam, llama :8, FIRST SONNET SUPERVISOR, new 30s-poll/2.5-min-stall-abort/5-min-heartbeat posture) is LIVE and carries all of them; the ladder verdict is the expected next event.

**Fix stack attempt #6 runs on (all pushed to manny_mcp master):** 31504fb gate thresholds (fresh account skips nothing; cooking gate 170) · b5f5e61 exact bridge on 05b (proven attempt-#1 door crossing; doctrine: plain=traversal, exact=positioning/seating) · 39a8cb2 arming state-gates + WAIT gate "verify ladder armed" on tutorial_progress:>=250 (honest abort, no dead-ladder clicks) · 9ade455 door pinning (exact confirmed seat before every door open; doors are identical — location IS identity, per user) · c186adf dryrun models tutorial_progress · 6ff3d27 freeze watchdog + llama display map (every alias mapped; :2 = user's physical desktop, never fall back to it). Jar on llama+pinned: d0668f58 (menu-matcher fix soaked clean 51 decisions; BACKSPACE/DELETE; manny commit 45b3900). Old jar .rollback-fa059e23 kept on host.

**In-flight when this checkpoint was written (all background, will message main):** (1) attempt-#6 sonnet supervisor (llama, judeaislam); (2) opus builder: `mannyctl <host> window <account> <routine>` one-command run pipeline (gates: predecessor-dead, creds, display-mapped, provision+stash discipline+post-assertions, DEFECT-32 login gate, run+watchdog attach) — composes existing mannyctl, must not touch watchdog.py; (3) sonnet: stall detector in scripts/remote/watchdog.py (--stall-seconds, default 150: varp+position static → stall_detected/continuing/cleared ledger events, no kill); (4) fable fork: PROCESS_AUDIT_2026-07-20.md self-audit for the user at ~/Desktop.

**Key verdicts banked today:** varp-281 read + master gating PROVEN (3×). strict_steps honest-fail PROVEN. Cooking gate fix PROVEN (attempt #5: cooking ran, varp→200). First healthy account REACHED the ladder (karldakilla, (3088,3118)); Climb-down primitive healthy; descent blocked only by arming desync (now gated+fixed). DEFECT-29 dagger equip PROVEN on diort (blast); sword/shield/bow UNMEASURED (blast deadlocked varp 400 — pre-equipped dagger blocks instructor dispense; fresh account through s08 is the only clean test). TYPE command PROVEN end-to-end — tovahkline NAMED; Set/Confirm widget 36569107; group-558 buttons need ENTER/CLICK_AT (CLICK_WIDGET null-bounds defect FIXED in 45b3900, live acceptance pending next group-558 visit). Graph nav trial (diort, ifixifixit): engine/flag/fallback SOUND but tutorial transport DB missing cook gate/door + fence mismodeled walkable → WALK-only routes, executeTransport never ran, rescue failed; shadow graph=FOUND counts walk-only routes (misleading); do NOT cut over tutorial until data fixed (task open). Legacy launch path: mannyctl run does NOT start a client — start first, then run (window command will subsume).

**Parked accounts:** punitpun (desynced, dead), ifixifixit + fishibis2800 (pocket-trapped ~(3077,3094)/(3078,3097), varp 130 — rescue = graph mode after transport-data fix), karldakilla (at ladder, varp 200, clean — could resume for a ladder-only test if arming can be re-fired: quest guide steps re-runnable from (3086,3125)), blast (varp 400 deadlock, diort), tovahkline (named, fresh, unused). Fresh spares left: judeaislam (in use, #6), malikreyes (last untouched).

**Next actions by outcome:** #6 mainland → MILESTONE: account factory (fan malikreyes/tovahkline through the chain on llama lanes; then Bolt-create→TYPE→tutorial pipeline). #6 fails → the failure is by construction NEW; diagnose with prior-art-first + verify factual premises (which commit/mode actually ran — today's inverted-diagnosis lesson) before fixing. Either way: read PROCESS_AUDIT for adopt-now items; open tasks #11 (launch-path/display allocator — window command may close it), #13 (tutorial transport data for graph nav).

**Standing rules that keep biting (do not relearn):** always explicit --account (default=punitpun); banned aliases new/newbakshesh; main=REAL never; never pkill java; ps-not-pgrep for liveness; stash 3 humanize paths before provision, pop+verify after; scoped git add only (many concurrent committers), author Tsangares, no Co-Authored-By; supervisors poll inline, never background-exit reliance; fish shells everywhere remote — bash -c wrap; user reads plain language, not agent-speak.
