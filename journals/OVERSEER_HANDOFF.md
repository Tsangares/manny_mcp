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
| 5 | **diort migration** (thermal-stable run host) | 🔄 staging IN FLIGHT; **cred/login = USER-APPROVED ("go on diort")**, do it after thermal probe | DIORT_MIGRATION_PLAN.md |
| 6 | **Machine-agnostic remote-client** | 🔄 DESIGN in flight (generalizes #5 to any host) | REMOTE_CLIENT_ARCHITECTURE.md (being written) |

### Why the pivot to #5/#6 (the crux)
The whole software campaign (#1–#4) is essentially DONE. The ONLY blocker to the end-goal (an unattended
money-maker grind) is **thermal**: this laptop's RuneLite client pins a CPU core on GPU-less Xvfb software
rendering → package hits **90°C within ~2 min** every live run → crash risk. No software fix. So we're
moving the client to **diort** (LAN 10.0.0.13, a desktop-class 2011 iMac, idle 50°C, **home/residential
IP = no ban risk, no proxy needed**), and generalizing that into a host-agnostic capability so any machine works.

---

## IN-FLIGHT AGENTS (background; resume via SendMessage to the ID)
- `a0bb6c2bc4c3ccdc9` — **diort staging + no-creds thermal probe**: installs jdk21, rsyncs jar+code, venv,
  replicates low-CPU render config, launches client to LOGIN SCREEN (no creds) and measures diort temp under
  load. **Its thermal reading gates whether we commit the account to diort.** Cred/login is NOT delegated to it.
- `af40999aacfb04bec` — **remote-client architecture design**: writes REMOTE_CLIENT_ARCHITECTURE.md + a
  prototype (hosts.yaml + a `mannyctl`-style ssh launcher in NEW files; does NOT touch existing client.sh/run_routine.py).
- `a6237f80b1def8a38` — **blog-ready session journal** → journals/2026-07-18_multiproject_session.md.
(When each notifies completion, fold results into the relevant doc + commit. Their output files are in the
session tasks dir; do NOT tail them raw.)

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

**Open defect queue (fix+gate on diort):** GameEngine off-thread remnants (isTileWalkable/getEmptyTile/
combat-scan ~5594/5787/5998/6097/camera ~7907/8099/8220). Everything else is fixed.

**Delegation:** heavy work goes to subagents to protect overseer context; author self-contained prompts
(subagents don't share context). Model tiers: opus=deep Java/design, sonnet=well-specified, haiku=mechanical.
