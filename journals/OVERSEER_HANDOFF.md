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

**Build gate (JDK21):** `cd /home/wil/Desktop/runelite && ./gradlew :client:compileJava [:client:shadowJar]
-x checkstyleMain -x pmdMain --console=plain`. JDK 21 pinned via ~/.gradle (JDK 26 breaks gradle 8.8).

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
during the incident (was diverging: repo had `3600000`/stance `Stab`, diort had `14400000`/stance
`Stab`). Stance is left at `Block` (current defence-catch-up phase) — only the timeout was reconciled,
so the next `provision` doesn't silently downgrade the live host's timeout back to 1h. DEFECT-30 (above)
is the real fix; the timeout bump was a stopgap.

Humanization track is in flight in the `manny` Java tree (out of scope for this agent's git tree —
tracked here for continuity). Deploy-window discipline: see `DEPLOY_WINDOW_CHECKLIST.md` (new this pass)
before closing window #4 or any future window. Delegation note: agents should claim a working tree via
`scripts/tree_lock.sh claim <tree> <agent>` before committing (advisory, see script header) — the
branch-collision lesson from earlier this campaign is exactly what this is for.
