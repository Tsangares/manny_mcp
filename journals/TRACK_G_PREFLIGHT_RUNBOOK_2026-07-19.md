# Track G Pre-Flight Runbook — the 4h+ Unattended Cowhide Proof on diort

**Date:** 2026-07-19  **Status:** RUNBOOK (read-only synthesis; nothing here executed).
**Audience:** the future overseer session that attempts Track G.
**Read alongside:** `journals/TRACK_G_PROTOCOL.md` (the exam rubric + verbatim fresh-session
prompt — this runbook is the *operational* half; the protocol is the *scoring* half),
`journals/OVERSEER_HANDOFF.md` (durable state; note its `STATUS NOTE — 2026-07-19`),
`DEPLOY_WINDOW_CHECKLIST.md`, `ROUTINE_SCHEMA.md`.

Track G = a *fresh* LLM session, given ONLY `ROUTINE_SCHEMA.md` + `validate_routine_deep` +
the `manny-diort` MCP endpoint, authors/refines a cowhide-grind variant and runs it **4+
hours unattended on diort**, watchdog ledger showing clean completion OR correct
intervention. It is the LAST item in the milestone sequence — do not start it early.

> **CURRENT REALITY (read first).** Track G is **DEFERRED, not ready.** Per
> `OVERSEER_HANDOFF.md` → `BAN PIVOT` and `STATUS NOTE — 2026-07-19`: two fresh F2P accounts
> were behaviorally banned two days running on diort's residential IP (`new`/GrimmsFairly
> 07-18; `newbakshesh` 07-19, 32s after a KILL_LOOP relaunch). All grinding — attended and
> unattended — is halted campaign-wide. An unattended cowhide grind is exactly the
> metronomic-KILL_LOOP shape that got detected. Track G stays parked until (a) the USER
> settles IP/account posture and (b) humanization is proven on an expendable account. The
> humanization layer itself is OUT OF SCOPE for the overseer session (STATUS NOTE boundary);
> Track G resumes only once someone else has landed and proven it.

---

## 1. HARD BLOCKERS — every one must clear before any attempt

Listed in execution order. Each has a verify step. Do NOT proceed past an unverified box.

### B1 — USER decision on proxy/IP + account (NEVER the overseer's call)
Both prior fresh-account grinds died on diort's **residential IP with no proxy**
(`OVERSEER_HANDOFF.md` ACCOUNT STATUS + BAN PIVOT). IP alone is not a defense against
behavioral detection. Resumption options the handoff records: (a) route through **mat + the
`dataimpulse` proxy — RECOMMENDED**; (b) run on diort's flagged residential IP; (c) fresh
throwaway. This is a **USER** decision — the overseer must not pick.
- **Verify:** the user has stated, in-session, the IP path AND the account alias to use.
  `dataimpulse` lives in `~/.manny/credentials.yaml` under `proxies.dataimpulse` (stored,
  not wired). Confirm humanization is proven on an expendable account FIRST (BAN PIVOT makes
  it a *prerequisite* for any sustained/unattended contact).
- **Account note (contradiction — see §6):** `TRACK_G_PROTOCOL.md` still says "lane 1
  (`newbakshesh`) only", but `newbakshesh` is BANNED. The Track G account is now UNDECIDED.
  `punitpun` is a clean reserved spare; `blast` is parked at tutorial section 08. Neither may
  be used pre-humanization. `main` is the user's real account — **hard off-limits.**

### B2 — DEFECT-21 bridge-crossing live gate  *(PENDING — task #25)*
The `b40838a` fix (`validateAgainstLocalCollision` in the nav follower) is landed but never
live-crossed the Lumbridge river.
**UPDATE (later 2026-07-19): the waypoint-coordinate risk is now RESOLVED offline.** The new
route-lint harness (manny `pathfinder/RouteLintVerify.java`, commits `5590802`/`4536b91`)
proved against the vendored collision map that the ORIGINAL bridge pins (`3247,3228` /
`3244,3227` / `3239,3228`) sat in the River Lum and the staircase pin `3205,3208` was
blocked on all planes. Both were CORRECTED in `cowhide_banking.yaml` (`786c52e`): bridge
deck pins now `3247,3226` / `3244,3226` / `3239,3226`, staircase `3205,3209` — every hop in
the route is now harness-verified walkable and graph-connected in BOTH directions
(RouteLintVerify 71/71, zero skips). What remains live-only: the FOLLOWER's real click
behavior on those verified waypoints (the original DEFECT-21 failure mode) and the possible
door near `(3218,3217)` on the courtyard→stair line.
- **Verify:** a round-trip cow-field⇄bank crossing on diort in BOTH directions, per E2 (B5).
  The E2 attended gate *is* DEFECT-21's live gate (`OVERSEER_HANDOFF.md` Sequence step 5).

### B3 — DEFECT-22b Python ban chain landed + zero-risk login gate  *(PENDING — task #49, narrowed)*
Ban DETECTION redesign (`journals/BAN_DETECTION_REDESIGN_2026-07-19.md`): the ban text is
rasterised — unreadable by widget scan, reflection (len=0 at live gate), or `loginIndex`
number. Java half is LANDED (`manny 93dae33` — persistence heuristic on non-{2,4} login
states + `login` section exported to state; verified in manny git log). The **Python half is
now also LANDED** (`manny_mcp 89f33ff` — `stuck_detector.py` login-stuck signal + the driver
calling `analyze_screenshot` with the ban-classification prompt and STOPping, per §4c of the
redesign; 288 tests passing). Both halves of DEFECT-22b are offline-complete — **only the
zero-risk live login gate below remains** before B3 can be checked off.
- **Verify:** run the **zero-risk login gate** of `BAN_DETECTION_REDESIGN_2026-07-19.md` §5
  on an ALREADY-BANNED alias (`new` or `newbakshesh`; NEVER a live/spare account, NEVER
  `main`): one login attempt on display `:4`, `STOP_PROCESSOR`, capture
  `get_logs(grep="[LOGIN]")` + `get_game_state(fields=["login"])` +
  `analyze_screenshot`, then `stop_runelite`. Pass = vision returns BANNED and the plugin
  latches `terminal_login_failure=true` without 5 world-hops. Risk is zero (a banned account
  cannot log in).

### B4 — Deploy pending manny commits to diort (rebuild + provision)
diort's live jar predates the current manny HEAD. Undeployed payload (manny git log
verified): `be87b99` (WP6 runtime integrity guard — landed per
`NAV_WP6_DATA_REFRESH_SCOPE_2026-07-19.md`), `93dae33` (DEFECT-22b ban detection, B3),
`ad86afa` (DEFECT-31 modal-aware dialogue), `873eec7`/`bc186eb`/`00f0069`
(DEFECT-27/28/28b), `e56ba40` (humanization phases 1-2), `21468c0` (nav WP6: `--verify`
auto-runs the offline harness on `--apply` and reverts on failure — current manny HEAD, also
undeployed). manny_mcp side already has DEFECT-30 (`a6e6191`) + engine `on_failure`
(`475977f`) + bank-leg resilience (`7a47812`).
- **⚠️ BUILD HAZARD — PROCEDURE (verified current, supersedes prior stash-`c9350e6` note):**
  the parked half-written humanization edits are **uncommitted in the working tree**, not
  stashed (`c9350e6` was a transient snapshot from an earlier session and no longer exists —
  `git stash list` is empty as of this refresh). Current working tree has exactly: modified
  `utility/HumanizeVerify.java`, modified `utility/commands/KillLoopCommand.java`, untracked
  `utility/CameraDrift.java`. `CameraDrift` is missing helpers `KillLoopCommand` already
  calls, so a tree with them present does not compile.
  **Before any Java build:**
  1. `cd /home/wil/Desktop/manny && git stash push -u -m "parked camera-drift edits" utility/CameraDrift.java utility/commands/KillLoopCommand.java utility/HumanizeVerify.java`
  2. Build/deploy (see below).
  3. `git stash pop` to restore the parked edits.
  These edits are **user-owned — never commit them**, and never build with them applied.
- **Build/provision:** run `manny/scripts/install_pathfinder_resources.sh` FIRST if pathfinder
  resources changed (they did — `be87b99`), then
  `cd /home/wil/Desktop/runelite && ./gradlew :client:compileJava :client:shadowJar
  -x checkstyleMain -x pmdMain --console=plain` (JDK21 pinned), then ship the jar and run
  `mannyctl diort provision`. **Provision hazard:** it reconciles diort to `hosts.yaml`
  layout — the `KEY DISCOVERY` in the handoff (diort was hand-staged at non-canonical paths).
  Also reconcile any hand-patch divergence per `DEPLOY_WINDOW_CHECKLIST.md` (e): the repo
  already reconciled `chicken_feathers.yaml` timeout to `14400000` (`a97aa7f`); check nothing
  else diverged. Close the window through `DEPLOY_WINDOW_CHECKLIST.md` (a)-(f).
- **Jar PRE-BUILT 2026-07-19 (rebuilt same day at HEAD `d553977`):** the shaded jar is built
  clean using the stash procedure above:
  `/home/wil/Desktop/runelite/runelite-client/build/libs/client-1.12.34-SNAPSHOT-shaded.jar`,
  40,094,707 bytes, sha256
  `a74bed081c20bc0f59260f11401b3f088b68d11316e6aa392c4b15241af37a65`.
  Spot-checked: manny plugin classes present; pathfinder resources
  (`collision-map.zip`, `transports/transports.tsv`, `data.fingerprint`) present;
  `CameraDrift` class **ABSENT** (parked code not shipped). If manny HEAD is still
  `d553977` at deploy time, skip the rebuild — verify this sha256 and provision this
  artifact. Any newer HEAD ⇒ rebuild per the procedure. Provisioning to diort was NOT done
  (user approval pending).
- **Heuristic HARDENED post-review (late 2026-07-19):** an adversarial review of the day's
  diff found no confirmed bugs but three plausible FALSE-LATCH paths (healthy login declared
  banned). All fixed: plugin streak now requires the SAME stable non-{2,4} index on
  consecutive observations and restarts after a >120s observation gap, with `[LOGIN][SHADOW]
  index-sample` diagnostics logging every sampled index for this live gate (manny `d553977`);
  driver backstop requires a stable unchanged index ≥120s OR the plugin latch, and the
  plugin-latch path still stops immediately (manny_mcp `22247ce`, 321 tests). The B3 live
  gate should ALSO confirm the shadow log shows the resting login screen's actual index.
- **Verify:** jar provenance/fingerprint (see §2), and the DEFECT-26 4-gate is already PASS
  (`OVERSEER_HANDOFF.md` WINDOW #3 RESULT) — do not re-litigate it.

### B5 — E1 feathers attended smoke + E2 attended cowhide cycles  *(PENDING — task #26)*
- **E1 (feathers):** smoke test PASS already (`36d5443` era). The sustained stat grind was NOT
  clean (exposed DEFECT-26, then the account was banned) — but E1 is a *stat-training*
  sub-milestone, and its account is gone. Re-scope to whatever B1 account the user picks.
  Note `configs/chicken_feathers.json` sets `kills:1000` vs the YAML description's "100"
  (audit MED finding) — reconcile before relying on it.
- **E2 (cowhides — the actual Track G routine):** `cowhide_banking.yaml` run **attended**,
  ≥2 consecutive kill→fill→bank→return cycles, **including both bridge-crossing directions**.
  This closes B2/DEFECT-21. Post-fix the routine is hardened (`7a47812`): bank steps carry
  `on_failure: retry:2`/`abort`, `BANK_DEPOSIT_ALL` gated on `inventory_count:<=0`, symmetric
  return hops (step `23b` added). Do NOT run E2 unattended before this attended gate passes.
- **Verify:** on a short attended run, confirm the watchdog ledger shows `running` for the
  full batch (not a premature `completed` — the old DEFECT-26 "60s-completed lie"), and
  `active_loop` advances across polls.

---

## 2. PRE-FLIGHT CHECKLIST — immediately before launch (all B1-B5 clear)

- [ ] **Routine validates deep-clean.** `validate_routine_deep(routine_path=<variant>)` → 0
      errors. The nested-inner-loop KILL_LOOP false positive is fixed (`71e004b`) and the
      `GOTO exact` arg is accepted (`8a8d3e9`), so a correctly-structured cowhide variant
      should be clean. (Track G's fresh session authors the *variant*; the overseer validates
      the corpus base is clean first.)
- [ ] **Jar provenance / fingerprint.** Confirm diort's running jar is the one built in B4 —
      compare the deployed jar's checksum/mtime against the build output; confirm the pathfinder
      `data.fingerprint` integrity line logs `integrity=ok` at client start (the WP6 `be87b99`
      guard; `NAV_WP6…` §3.1). A stale jar silently ships old nav data.
- [ ] **Watchdog armed + ledger writable.** `mannyctl diort run` auto-attaches `watchdog.py`
      setsid-detached against the run pid (`scripts/remote/mannyctl:237`) and writes
      `/tmp/manny_runs/<run_id>.json`. Confirm `/tmp/manny_runs/` is writable and the host has
      the repo on `sys.path` so the watchdog imports the canonical `CRASH_PATTERNS`
      (`crash_source: mcptools` in the ledger, not `vendored`).
- [ ] **Thermal thresholds.** Watchdog auto-SIGTERMs the run (then client) on **2 consecutive
      checks ≥ refuse (88°C)** and records `status: thermal_kill` (`watchdog.py:337-358`;
      refuse from `hosts.yaml` diort `temp_refuse_c: 88`, `warn 80`, forwarded via mannyctl
      `--temp-refuse`). Overseer DOCTRINE: manually abort at **≥84°C sustained** (the
      `OPERATIONAL ESSENTIALS` abort number; the two-lane probe peaked 76°C "well under 84
      abort"). diort's historical plateau is ~70-74°C — treat a sustained climb toward 88 as a
      near-fail even if the watchdog catches it.
- [ ] **Session caps (user rule, STATUS NOTE + `DEPLOY_WINDOW_CHECKLIST.md` (c)).** No client
      runs > ~8h continuous; at 8h stop/log-out, rest ~2h (resume at start+10h). A 4h proof
      fits one 8h window — **schedule the start so the 8h cap isn't hit mid-proof** (don't
      start a 4h run at hour 6). Record start time (`ps -o lstart= -p <pid>` or ledger
      `started_at`) and its 8h/10h deadlines.
- [ ] **Account alias + credentials default.** Select the B1-approved alias EXPLICITLY.
      **KNOWN HAZARD:** credential re-imports (Bolt) have reset `default:` in
      `~/.manny/credentials.yaml` to a BANNED alias THREE times (was `new`, then
      `newbakshesh`). Re-verify `default:` points at a live account before trusting it; the
      banned entries carry `# BANNED` comments — never launch one except the B3 login gate.
- [ ] **Displays per CLAUDE.md.** Use gamescope displays via MCP `start_runelite` (never raw X,
      never Bash-launched). One account per display; `main` is typically `:3` — do not touch.
      Per `hosts.yaml account_displays`: `newbakshesh`→`:2`, `blast`→`:3`. Track G's account
      gets its own display; mjpeg viewer for it (e.g. `http://diort:8787` for `:2`).
- [ ] **No other agent/driver owns the live lane** (`TRACK_G_PROTOCOL.md` — verify ALL THREE):
      `/tasks` shows no other agent active against this repo; `mannyctl diort runs` shows no
      `status: running` entry for the chosen account; `ssh diort 'pgrep -f run_routine.py'` is
      empty (or only a `blast`/lane-2 process). If the three disagree, STOP — that is the
      dual-driver ghost (mystery run `20260719T014238Z`); resolve before launch.

---

## 3. LAUNCH + MONITORING

**Launch (detached, watchdog-attached — the ONLY supported form for an unattended run):**
```
mannyctl diort run routines/money_making/<your_cowhide_variant>.yaml --account <alias> --loops <N>
```
mannyctl setsids the run `</dev/null` and setsid-attaches `watchdog.py` against its pid, then
prints `MANNY_RUN_ID <run_id>` and `mannyctl diort runs <run_id>` (`mannyctl:237-247`). The
`run_id` is `<UTCstamp>_<alias>`. A dropped SSH does NOT kill the run (setsid). Do NOT launch
via a foreground `do_run`/`run_routine.py` over SSH for a multi-hour grind.

**Monitor cadence (CLAUDE.md monitoring doctrine — you are a MONITOR, not an executor):**
- Poll the **ledger** (`mannyctl diort runs <run_id>`) and `get_game_state` every **5-15 min**
  for a multi-hour run — not continuously.
- Watch that `active_loop` advances across polls (kills/iteration climbing) — this confirms the
  DEFECT-26 loop-blocking fix is live for THIS run, not just deployed. Frozen counters for
  >5 min trip the watchdog's stall detector (`stall_ms=300000`).
- Watch the ledger `status`, `temp_c`, `state_age_s`, and `events[]`. `state_age_s > 30`
  (CLAUDE.md) or the watchdog's `stale` event (>120s, `watchdog.py:44`) = frozen plugin.
- The B3 login/ban chain surfaces via `get_game_state(fields=["login"])`
  (`terminal_login_failure`) and, on a suspected stuck login, an `analyze_screenshot` verdict.

**Intervene ONLY for** (CLAUDE.md "Routine Monitoring"): idle >60s with no progress, 3+
consecutive errors, a genuine stall/crash, `status: needs_attention`/`unmanaged_loop`, OR any
**suspected ban** (§4). **Leave alone:** click retries, brief pauses, single-step
`on_failure: retry` recoveries, normal travel-leg re-hops. Every intervention you make
disqualifies the run from PASS (`TRACK_G_PROTOCOL.md` observation rules) — record why.

---

## 4. ABORT / RECOVERY PLAYBOOK

- **Thermal.** Watchdog auto-SIGTERMs at 88°C×2 → `status: thermal_kill`. If you see ≥84°C
  sustained before the watchdog fires, manually `stop_runelite(account_id=<alias>)`. Record
  temp history; a thermal kill before 4h is a recorded FAIL cause (not an on-ramp defect) —
  diort's sustained budget may be tighter than smoke data.
- **Stuck / desync (nav stall).** Follower wedged at a bridge/door/uncached tile despite
  DEFECT-21/23. Do NOT hand-drive it (that's an executor intervention). Stop the run, record
  the tile + which leg, note whether Nav Stage-2 (`NAV_STAGE2_PLAN_2026-07-18.md`) would have
  prevented it. This is a FAIL with cause "nav stall".
- **Suspected ban — STOP IMMEDIATELY, NEVER RETRY.** If `terminal_login_failure=true`, a
  persistent non-{2,4} login screen, or `analyze_screenshot` returns BANNED/serious-rule-
  breaking: `stop_runelite`, mark the account BANNED in the ledger + `~/.manny/credentials.yaml`
  (add `# BANNED <date>`), do NOT world-hop, do NOT relaunch, do NOT touch another account.
  Leave the client UP at the ban screen as appeal evidence (as was done for `newbakshesh`).
- **Disconnect.** Watchdog records `client_dead`/`stale`; it does NOT self-heal (`watchdog.py`
  docstring). Decide: a clean reconnect on a healthy account is acceptable recovery; repeated
  disconnects → stop and record.
- **Death (gravestone flow).** Cows are low-risk, but if it happens:
  `get_game_state(fields=["gravestone"])` → `FIND_GRAVE` → `LOOT_GRAVE` within 15 tiles
  (CLAUDE.md Death Recovery; `routines/utility/gravestone_retrieval.yaml`). Record it.
- **Always record afterward:** the final ledger JSON (`mannyctl diort runs <run_id>`), the
  abort cause, and a dated journal entry (§5). Verify no orphaned processes/watchers remain
  (`DEPLOY_WINDOW_CHECKLIST.md` (f): `pgrep -f run_routine.py`, `ps ... watchdog`, any
  `unmanaged_loop`/`stale` ledger).

---

## 5. SUCCESS CRITERIA + evidence for the milestone journal

**PASS requires ALL** (`TRACK_G_PROTOCOL.md` rubric):
- 4+ hours wall-clock run time.
- Ledger `status: completed` OR a justified, documented intervention (not a panic-stop).
- Hides visibly accumulating in the bank across the run (not stuck at zero).
- No dual-driver events (no second process/ledger on the account mid-run).
- Temps ≤ diort plateau (~70-74°C); sustained climb toward 88 = near-fail even if caught.

**Evidence to capture** (feeds a new dated `journals/` entry — the milestone capstone):
- the `run_id`; the final watchdog ledger JSON (status, `events[]`, `temp_c` history).
- the ledger `running`→`completed` transition matches actual grind duration (a `completed`
  after ~60s while the run continued = DEFECT-26 regression, hard FAIL signal).
- `active_loop` advancing across successive polls (loop-blocking fix in effect).
- XP + gold-piece deltas; count of cowhides banked; every intervention + its reasoning.
- FAIL is not a failed milestone — it is a found defect (schema-gap / validator-miss /
  nav-stall / thermal). File it against the on-ramp, not the session, and re-run after fixing.

---

## 6. Contradictions / stale references found in the source docs (flag for the overseer)

1. **Account: `newbakshesh` is named as the Track G account but is BANNED.**
   `TRACK_G_PROTOCOL.md` (lines 8-11, precondition line 53) and `OVERSEER_HANDOFF.md`
   Sequence step 6 both say "lane 1 (`newbakshesh`) only" — but the same handoff's BAN PIVOT /
   STATUS NOTE record `newbakshesh` banned 2026-07-19. The Track G account is therefore
   **undecided**, folded into blocker B1. The protocol doc is stale here.
2. **`chicken_feathers.json` `kills:1000` vs the YAML/description "100"** (audit MED finding) —
   only matters if E1 feathers is re-run for stat training; reconcile the config to the tuned
   value before relying on it.
3. **Parked camera-drift/humanization edits: verified 2026-07-19 to be uncommitted in the
   working tree (`git stash list` empty; no `c9350e6`).** `git status --short` shows exactly
   modified `utility/HumanizeVerify.java`, modified `utility/commands/KillLoopCommand.java`,
   untracked `utility/CameraDrift.java`. Do not build with them applied; do not commit or
   advance them. Use the B4 stash-before-build procedure (stash the three paths, build, pop
   after) rather than relying on the tree happening to be clean.
