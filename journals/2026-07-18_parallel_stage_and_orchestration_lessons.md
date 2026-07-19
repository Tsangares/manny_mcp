# 2026-07-18 — Parallel stage: diort proven + orchestration lessons

**Author:** overseer (main session). **Companion doc:** `2026-07-18_diort_bringup_parallel.md` covers the
mechanical bring-up in detail; THIS entry is the authoritative consolidated account + the reusable lessons,
and it corrects two things the earlier journal (written mid-stage) got wrong. Blog-ready.

---

## One-line story
The manny software campaign was already done; the only thing standing between us and an **unattended
money-maker grind** was **thermal** — the dev laptop's GPU-less RuneLite client pins a CPU core on software
rendering and hits **90 °C / crash within ~2 min**. Today we ran a 4-track parallel stage that moved the
client to **diort** (LAN 2011 iMac, residential IP) and **proved the whole thing end-to-end**: remote launch,
auto-login, navigation, and a chicken grind that held a **70–74 °C plateau**. The thermal crash is solved.

## What ran in parallel
| Track | Owner | Outcome | Commit |
|---|---|---|---|
| A — diort bring-up | overseer (creds never delegated) | ✅ proven: login 29 s, 20/20 chickens, +248 atk XP | — |
| B — GameEngine off-thread collision/tile wraps | agent | ✅ DEFECT-20 | `a6da377` (manny) |
| C — mannyctl↔diort validation | agent | ✅ fixed fish SSH-quoting (would've broken every remote cmd) | `16b410e` |
| D — routine corpus audit | agent | ✅ tutorial 05/06 double-run fix + GOTO awaits | `654313e`,`e17123a` |
| + | overseer | proxy stored+verified; provision.sh fish fix; do_run detach | `fd60cf6`,`0eefb5f` |

**Final HEADs:** manny `a6da377`, manny_mcp `b887919` — both pushed.

## The diort bring-up recipe (works, repeatable)
```sh
cd /home/wil/Desktop/manny_mcp
# creds: scp ONLY credentials.yaml, chmod 600 (overseer-only, never delegated, tokens never printed)
ssh diort 'mkdir -p ~/.manny; chmod 700 ~/.manny'; scp -q ~/.manny/credentials.yaml diort:.manny/credentials.yaml; ssh diort 'chmod 600 ~/.manny/credentials.yaml'
bash scripts/remote/mannyctl diort provision     # reconciles hand-staged ~/manny* -> canonical ~/Desktop/...; jar->runelite_libs; venv; perf-config
bash scripts/remote/mannyctl diort start new      # -> "READY: 'new' logged in in 29s"; thermal ok 68C
# nav: fire GOTO via command file, poll /tmp/manny_new_state.json for arrival (GOTO only responds on arrival)
# grind: KILL_LOOP Chicken N  (KILL_LOOP blocks in-plugin until N kills)
bash scripts/remote/mannyctl diort stop           # when done
```
**Thermal (the whole point):** steady **70–74 °C** across nav+combat; peak 74 °C; crit is 86 °C, refuse
threshold 88 °C — ~12–16 °C margin, indefinitely. Laptop reference: 90 °C / 2 min / crash. diort idle ~54 °C.

**Grind proof:** attack XP 60→308 (+248), HP 1169→1250 (+81) over 20 kills / ~6 min, ~8 s/kill, zero damage.

---

## LESSON 1 — `fork` vs `general-purpose` for delegation (the big one)
The Agent tool's `fork` subagent type **inherits the parent's entire context**. I spawned "Track B" (a
narrow GameEngine off-thread fix) as a `fork`. Because it inherited the full overseer context, it did **not**
behave as a focused worker — it acted as a **second overseer**: it ran its *own* diort bring-up, wrote the
journal/handoff/memory, and treated its assigned code fix as "someone else's, still in flight." The actual
GameEngine fix simply **never got done** until I noticed the repo was still at the old HEAD.

- **BAD:** `fork` for a narrow, well-specified task. Context inheritance invites scope-drift into overseer work.
- **GOOD:** scoped `general-purpose` agents with a self-contained prompt and explicit boundaries
  ("edit ONLY this file; do NOT act as overseer; do NOT touch diort/other repos; commit; report the hash").
  Every general-purpose agent I dispatched afterward (GameEngine redo, do_run detach, auto-play investigation)
  behaved perfectly.
- **Corollary — clean-tree guard saved us:** when two agents ended up assigned the same fix, the second one
  found the commit already landed and *verified instead of duplicating*. Tell agents to check for existing
  work before committing.
- **Corollary — pinging a completed agent re-tasks it:** a SendMessage "do X or tell me where you are" made
  the stalled fork actually do X. Don't ALSO spawn a fresh agent for the same X (I did — harmless here only
  because of the clean-tree guard).

## LESSON 2 — never drive one game account from two sessions
The "collision" above meant two overseer-minded agents both wrote `/tmp/manny_new_command.txt` and both ran
KILL_LOOP on account `new`. Symptoms: **two combat threads**, mutual command cancellation (one's `GOTO`
cancelled the other's grind), and `start` on one side SIGTERM'd the other's client. Rid style was the tell:
mannyctl uses **uuid** request_ids; hand-labeled `navgate/tocoop/grind<ts>` rids were the shell one-liners.
**Rule:** one session owns the live client for an account. Others coordinate via the handoff/memory and must
not fire commands at an account being grinded. Runtime guard: `STOP_PROCESSOR` makes the plugin ignore the
command file during a grind.

## LESSON 3 — the "competing auto-play scenario" was a MISDIAGNOSIS
Mid-stage I blamed stray `EQUIP_BEST_MELEE`/`BURY_ALL` commands on an auto-play scenario. Read-only
investigation proved otherwise:
- `autoPlayScenarioOnLogin` defaults to `"Play_Game"` (`MannyConfig.java:91`) but the scenario **file is
  absent** → login auto-play is a **no-op** (`ScenarioEngine.java:720` logs "not found," plays nothing).
- The stray commands are **normal grind byproducts**: the Attack level-up auto-equip (`LevelUp-AutoEquip`
  thread, `MannyPlugin.java:1199`, hardcoded, no toggle) fires `EQUIP_BEST_MELEE`; `KILL_LOOP` buries bones
  (`KillLoopCommand.java:723`). They carry their own request_ids because they route through the in-process
  command processor.
- **Debugging lesson:** before blaming an external actor for "stray" commands, check *which thread* issues
  them and whether the named subsystem actually ran. The "two threads" were Lesson 2, not a scenario.
- Optional formal disable (already a no-op): `SET_CONFIG autoPlayScenarioOnLogin=` (empty).

## LESSON 4 — remote exec through a fish login shell
diort's login shell is **fish**. `printf %q` (bash) emits `$'...\n...'` ANSI-C quoting for any multi-line or
special-char command; **fish rejects `$'...'`** ("Expected a variable name after this $"). This silently
broke `provision.sh` step 5 (perf config) and is the same class of bug Track C fixed in mannyctl.
- **GOOD pattern:** pipe the script to the remote bash via **stdin** — `ssh host bash -s <<<"$script"` — so
  the login shell never parses it (it just runs `bash -s`). Exit codes still propagate. Used this for the
  `onhost()` fix (`provision.sh`, `fd60cf6`) and for every ad-hoc monitor script this session.
- Single-line commands survive `bash -lc $(printf %q ...)` (no `$'...'`); multi-line do not. Prefer `bash -s`.

## LESSON 5 — DEFECT-19b validated cool; DEFECT-21 discovered
- **DEFECT-19b (progress-aware nav timeout) works as intended on diort:** a route that hit an obstacle
  **failed fast at a steady 70 °C** — `[NAV-LOOKAHEAD] didn't move after minimap click ... failing
  immediately` — instead of the old infinite hot-A\* churn that cooked the laptop. Anti-hang confirmed.
- **DEFECT-21 (NEW, next phase):** routes **crossing the Lumbridge river** mis-route through water instead
  of the bridge (the waypoint path veered west off the bridge line and stalled at the bank). North-side
  grinds (chicken coop) are unaffected; KILL_LOOP's short-hop navigation reaches the coop fine.
- **Bonus:** on diort's residential net the **osrspathfinder.com Pathfinder API is reachable** (7 ms paths) —
  the sandbox was the only reason A\* ever fell back and stalled. So nav is fundamentally healthier on diort.

---

## Open items (project #7 = grind robustness; needs live diort iteration)
- DEFECT-20 (GameEngine collision/tile wraps) owes a **live cooking/mining gate** on diort (its off-thread
  callers are PowerMine/LightFire/cooking).
- **DEFECT-21** river-crossing route quality.
- Tutorial 05/06 double-run fix needs one clean live tutorial pass on a fresh account to confirm.
- Longer hands-off runs now that `do_run` detaches (`0eefb5f`).

## Environment / versions
diort: Arch, 4-core i5 (2011 iMac), jdk21-openjdk 21.0.11 (`/usr/lib/jvm/java-21-openjdk`; default java is
26), Python 3.14.4, Xvfb :2, **fish login shell**, LAN 10.0.0.13 / Tailscale, passwordless sudo, idle ~54 °C.
Jar: `client-1.12.34-SNAPSHOT-shaded.jar` (39 MB, DEFECT-19b build; DEFECT-20 needs a rebuild for its gate).
Proxy: dataimpulse residential SOCKS5/HTTP stored in `~/.manny/credentials.yaml` (`proxies.dataimpulse`),
verified exit `167.60.124.153` — for server-IP hosts (mat); diort doesn't need it.
