# OVERSEER HANDOFF — manny (multi-project) — READ THIS FIRST

**Updated:** 2026-07-18 (late), post Tracks A/B/C/E1-prep/F/H landing. Author: Claude (overseer). This is
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
- **Uncommitted / in progress as of this writing:** tutorial pre-flight work — `05_cooking_to_quest_guide.yaml`
  plane fixes + master-chain reconciliation via new `00_resume_from_questguide.yaml` / `00_resume_from_survival.yaml`
  + `scripts/remote/mannyctl` tweaks. Not yet a commit — pick up and land before/alongside the newbakshesh
  tutorial run.

**manny** (`cd /home/wil/Desktop/manny && git log --oneline`):
- `a6da377` — DEFECT-20: thread-safe collision/tile reads in GameEngine (off-thread wrap).
- `b40838a` — DEFECT-21 fix: `validateAgainstLocalCollision` wired into the nav follower's click path
  (bridge water-stall). **Live gate still pending** — needs a round-trip cow-field⇄bank crossing on diort.
- `6566fe9` — DEFECT-22: `LoginHandlers` ban misclassification fixed — stop world-hopping on terminal
  (banned-account) login failures, fail fast instead. **Live gate still pending** — the banned `new`
  account is the natural test case for this.

All three manny fixes are bundled in one jar rebuild that still needs to be pushed to diort and live-gated
(see "In flight" below).

### ACCOUNT STATUS (critical — read before touching any account)
- **`new` (GrimmsFairly): BANNED 2026-07-18** — "serious rule breaking" per Jagex, behavioral detection.
  The residential IP (diort, no proxy) did **not** prevent it. Do not attempt further live logins on this
  account except as the deliberate DEFECT-22 fail-fast test case.
- **`main` is the user's REAL account — NEVER use it for bot/automation work.** This is a hard rule, not a
  preference.
- **Live working account now: `newbakshesh`.** Needs a full fresh Tutorial Island run before any grind
  routine can start on it.
- **User posture:** accept ban risk on expendable accounts, iterate — do not let ban risk block progress,
  just don't burn `main`.
- `dataimpulse` residential proxy is stored in `~/.manny/credentials.yaml` (`proxies.dataimpulse`) as an
  **available option**, not currently in use (diort's residential IP was believed sufficient; the `new` ban
  shows IP alone isn't a full defense against behavioral detection — proxy remains a fallback, not a fix).

### In flight
1. **Track E phase-1 live agent on diort:** rebuild the jar with all 3 defect fixes (DEFECT-20/21/22) →
   push to diort → gate DEFECT-22 via the banned `new` account (confirms fail-fast instead of world-hop
   loop) → run `newbakshesh` through the full Tutorial Island chain (live-gating the 05/06 fixes above) →
   then run the **E1 feather routine**: `KILL_LOOP_CONFIG` at the proven chicken coop, `loot_items:["Feather"]`,
   run as a genuine stat-training grind toward att/str/def ~20, plus an initial smoke pass.
2. **E2 — cowhide banking routine** (`routines/money_making/cowhide_banking.yaml`): inner loop kills cows
   + loots hides, outer loop crosses the Lumbridge bridge to bank and deposits, repeats. Gated on the
   DEFECT-21 live crossing verification (item 1's jar). Attended full-cycle gate (kill→fill→bank→return)
   ≥2 consecutive loops before it's trusted unattended.
3. **Track G — the milestone proof:** a *fresh* LLM session, given only `ROUTINE_SCHEMA.md` + the upgraded
   validator + the `manny-diort` MCP endpoint, authors/refines a routine variant and runs a 4+ hour
   unattended cowhide grind on diort. Watchdog ledger must show clean completion or correct intervention.
   Journal the result. This is the last item — do not start it before E1+E2 are proven attended.

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
Current HEADs (as of this handoff refresh): manny_mcp=`c501d06` (test decoupling, on top of the Close the
Loop landings — Track A/B/C/E-prep/F/H), manny=`6566fe9` (DEFECT-22 ban fail-fast, on top of DEFECT-20/21).
Both pushed to origin. manny_mcp has uncommitted tutorial pre-flight work in progress (see "In flight" at
top) — check `git status` before assuming these are the only local diffs.

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
