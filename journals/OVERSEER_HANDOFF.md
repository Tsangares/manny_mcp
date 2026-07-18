# OVERSEER HANDOFF — manny (multi-project) — READ THIS FIRST

**Updated:** 2026-07-18 ~15:15. Author: Claude (overseer). This is the top-level entry point after
compaction. It indexes the now-several parallel projects and how to resume each. For deep detail on any
one, open the doc named in its row.

**Read order:** this file → the specific project doc you're resuming. The old
`REFACTOR_CAMPAIGN_HANDOFF.md` is now the REFACTOR-detail archive (huge; read only for refactor history).

---

## THE PROJECTS (I am the overseer; these run in parallel)

| # | Project | Status | Resume doc |
|---|---|---|---|
| 1 | **manny refactor** (decompose PlayerHelpers) | ✅ **COMPLETE** — 23,683 → **3,484 lines** (85%), all phases live-gated | REFACTOR_CAMPAIGN_HANDOFF.md |
| 2 | **Off-thread defect cluster** (DEFECT-3 class) | ✅ **DONE** — DEFECT-15/16/17/18 fixed+gated; **remnants** queued for diort | REFACTOR_CAMPAIGN_LESSONS.md |
| 3 | **Navigation** (DEFECT-19/19b) | ✅ code FIXED (char walks); **full-walk live gate owed on diort** | manny/journals/DEFECT19_NAVIGATION_DIAGNOSIS.md |
| 4 | **Routines phase** | 🔄 groundwork DONE; **live grind proof blocked on a cool host** | GRIND_ROUTINE_READINESS_*.md, ROUTINE_CORPUS_HARDENING_*.md |
| 5 | **diort migration** (thermal-stable run host) | ✅ **STAGED + thermally GREEN**; only **cred/login + gate** remains (USER-approved "go") | DIORT_MIGRATION_PLAN.md + §DIORT BRING-UP below |
| 6 | **Machine-agnostic remote-client** | ✅ **PROTOTYPE done** — `scripts/remote/mannyctl` + hosts.yaml + provision.sh (Phase 1 = use it to bring up diort) | REMOTE_CLIENT_ARCHITECTURE.md |

### Why the pivot to #5/#6 (the crux)
The whole software campaign (#1–#4) is essentially DONE. The ONLY blocker to the end-goal (an unattended
money-maker grind) is **thermal**: this laptop's RuneLite client pins a CPU core on GPU-less Xvfb software
rendering → package hits **90°C within ~2 min** every live run → crash risk. No software fix. So we're
moving the client to **diort** (LAN 10.0.0.13, a desktop-class 2011 iMac, idle 50°C, **home/residential
IP = no ban risk, no proxy needed**), and generalizing that into a host-agnostic capability so any machine works.

---

## PARALLEL EXECUTION STAGE — 2026-07-18 ~16:00 (LIVE; supersedes the older in-flight list below)
Overseer launched a 4-track parallel stage to finish the diort bring-up + adjacent code work. Plan file:
`~/.claude/plans/kind-snuggling-turtle.md`. Live status:
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

## ⭐ DIORT BRING-UP — this is projects #5+#6 converging (USER approved "go on diort") ⭐
diort is staged (jdk21 + jar + code + venv + perf config) and thermally green. Use the NEW `scripts/remote/mannyctl`
tool (project #6) to finish — it codifies all the steps. ORCHESTRATOR/FORK runs this; creds are NOT delegated
to a subagent and JX tokens are never printed. First validate mannyctl's flagged live-TODOs as you go (SSH
`${var@Q}` quoting across the hop, whether the shipped `config.yaml` has laptop-only paths that break
`ServerConfig.load()` on diort, and diort temp reads via the coretemp hwmon fallback).
1. **`mannyctl diort provision`** — idempotent re-stage (safe; confirms jdk21/jar/code/venv/perf-config).
2. **`mannyctl diort push-creds`** — typed-`yes` gate; scp ONLY credentials.yaml, chmod 600. (The one account-affecting step.)
3. **`mannyctl diort start new`** — launches client on diort:2; watch `/tmp/runelite.log` for `Game state is now LOGGED_IN` + temp.
4. **[DEFECT-19b full gate]** `mannyctl diort cmd new "GOTO 3235 3295 0"` — must walk the FULL 76 tiles; expect
   `[NAV-API] ...LINE OF SIGHT CLEAR - directional walk` and NO `[Global A*]` churn. (Live gate owed from project #3.)
5. **[grind proof]** `mannyctl diort run routines/combat/chicken_killer_training.yaml --loops 3 --account new` —
   monitor diort temp throughout: the REAL gameplay-load thermal test + first unattended money-maker proof.
6. Then on diort: fix+gate GameEngine off-thread remnants; tutorial-04 + disconnect-recovery verify; add a 2nd host (should be zero-code).
NOTE: if mannyctl hits a live snag, fall back to the manual steps in DIORT_MIGRATION_PLAN.md (cred scp, config.yaml
java_path→jdk21 + display→:2, jar at `~/manny/client-...jar`). Phase 2 later collapses client_remote.sh into client.sh.

---

## IMMEDIATE NEXT ACTIONS (post-compaction)
1. **Collect the 3 in-flight agents** (above). Commit the journal + REMOTE_CLIENT_ARCHITECTURE + prototype
   (scoped). Read the diort **thermal probe** result — it's the go/no-go on committing the account to diort.
2. **If diort is thermally viable → do the diort account bring-up (USER already said "go on diort"):**
   copy creds to diort (ORCHESTRATOR does this, NOT a subagent — never delegate/print JX tokens), first login,
   then live-gate **DEFECT-19b** (GOTO 3235 3295 0 must walk the FULL 76 tiles) + run the first grind
   (`chicken_killer_training`, then `woodcutting_lumbridge` — verify axe EQUIPPED first). Drive via SSH.
3. **Then on diort (gate-capable host):** fix+gate the **GameEngine off-thread remnants** (DEFECT-18 agent's
   deferred list: collision/combat-scan/camera methods — relevant to grind stability); verify tutorial-04
   cook fix + engine disconnect-recovery on newbakshesh; capture the 3 tutorial TODO coords.
4. **User plans to FORK this process** to run the diort/remote session as a dedicated project overseer while
   the main continues. A fork inherits this context — point it at project #5/#6 + this handoff.

---

## OPERATIONAL ESSENTIALS
**Git (per repo, both):** author MUST be `Tsangares <Tsangares@gmail.com>`; **NO Co-Authored-By / Claude
lines**; prefix every git cmd with explicit `cd /home/wil/Desktop/<repo> &&`. CLAUDE.md is gitignored.
Current HEADs: manny=`1403107`, manny_mcp=`e4c27d1`. Both pushed to origin.

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

**Open defect queue (fix+gate on diort):** GameEngine off-thread remnants — SCOPE CORRECTED
2026-07-18: the real unguarded off-thread reads are the COLLISION/TILE cluster (isTileWalkable ~3106,
getEmptyTile ~3058, isPlayerTileEmpty ~3047, scanAndCacheCollisionData ~3169/3253), called off-thread
from CookingFiremakingSupport/PowerMineCommand/LightFireCommand → real crash risks. Track B (fork) is
fixing these now. The old queue's "combat-scan ~5594/camera ~7907" entries were MISDIAGNOSED — those are
StateExporter methods already on the client thread via onGameTick (in-code comment confirms); NOT defects,
do not wrap. Everything else is fixed.

**Delegation:** heavy work goes to subagents to protect overseer context; author self-contained prompts
(subagents don't share context). Model tiers: opus=deep Java/design, sonnet=well-specified, haiku=mechanical.
