# 2026-07-18 — diort bring-up + 4-track parallel stage (the thermal fix, proven)

> **See also `2026-07-18_parallel_stage_and_orchestration_lessons.md`** — the authoritative consolidated
> account. It completes this entry (GameEngine DEFECT-20, do_run detach, auto-play resolution) and CORRECTS
> two things below: (1) the "two grinds" collision was two *sessions on one account*, not a user fork vs me;
> (2) the "competing auto-play scenario" was a misdiagnosis — the scenario is a no-op; the stray commands
> were normal grind byproducts (level-up auto-equip + KILL_LOOP bone-bury).

**Session role:** overseer driving a deliberately-parallel stage. One critical path held locally
(the diort bring-up, because it touches credentials) + three forked/delegated tracks running
concurrently. This entry is blog-ready: what was built, the exact commands, the issues hit, and how
each resolved.

## The one-line story
The manny software campaign (refactor, off-thread defects, navigation) was already done. The single
blocker to the north-star — an *unattended money-maker grind* — was **thermal**: the dev laptop's
GPU-less RuneLite client pins a CPU core on software rendering and hits **90 °C within ~2 min → crash**.
Today we moved the client to **diort** (a LAN 2011 iMac, desktop cooling, residential IP) and **proved
it end-to-end**: remote launch, login, navigation, and a sustained chicken grind that held a **~70 °C
plateau** indefinitely. The thermal crash is solved.

## Parallel track structure
Launched together, meshed as they landed:

| Track | Owner | Outcome |
|---|---|---|
| A — diort bring-up | overseer (creds never delegated) | ✅ proven end-to-end |
| B — GameEngine collision/tile off-thread wraps | `fork` (opus) | in flight (compile-gate; live gate deferred to diort) |
| C — mannyctl live-TODO validation vs diort | agent | ✅ fixed a critical SSH-quoting bug + confirmed thermal guard |
| D — routine corpus audit + tutorial 05/06 | agent | ✅ documented; no blockers to the grind |

## Track C — the bug that would have broken everything
diort's login shell is **fish**. `mannyctl`/`provision.sh` shipped remote commands via bare
`ssh "$H_SSH" "$cmd"`, so they ran under fish and died `exit 127` on the bash env-prefix / `printf %q`
/ `${var@Q}` ANSI-C quoting the tooling relies on. **Every remote subcommand would have silently
failed.** Fix (commit `16b410e`, manny_mcp):

```sh
# run_on_host (mannyctl) and onhost (provision.sh):
ssh -o BatchMode=yes "$H_SSH" "bash -lc $(printf %q "$cmd")"
```

Also validated live on diort: CPU package temp reads real via `x86_pkg_temp` (thermal_zone0) — so the
thermal guard in `client_remote.sh` won't silently disable — Python 3.14 venv/pip OK, and launch uses
the configured jdk21 path (diort's *default* java is 26; jdk21 is installed but not default).

## Track A — the bring-up (all remote, via mannyctl)
```sh
cd /home/wil/Desktop/manny_mcp/scripts/remote
printf 'yes\n' | bash mannyctl diort push-creds     # typed-yes gate; scp ONLY credentials.yaml, chmod 600
bash mannyctl diort provision                        # rsync jar->runelite_libs, repo, venv, perf-config
bash mannyctl diort start new                         # -> "READY: 'new' logged in in 26s"; thermal ok 59C
bash mannyctl diort cmd new "GOTO 3235 3295 0"        # nav gate
bash mannyctl diort cmd new "KILL_LOOP Chicken 60"    # grind
```
- **Login:** logged in in 26 s on Xvfb :2 (client_remote.sh auto-starts the display), reniced 15.
- **Navigation:** on diort the **osrspathfinder.com Pathfinder API is reachable** (residential net) →
  `[Pathfinder API] Path found in 7ms: 20 waypoints`, no sandbox Global-A* stall. Full 41-tile walk to
  the coop, arrived within DEFECT-7 tolerance.
- **Combat / grind:** `KillLoopCommand` killed chickens ~20 s apart — `Kill N/100 complete (HP 10/10,
  Loot, Bones buried)` — zero damage taken.
- **Thermal (the whole point):** a 20 s-interval sampler on diort logged a **68–74 °C plateau over
  5+ min under nav+combat**, still ~70 °C at 30+ kills / ~13 min. Laptop reference: 90 °C / 2 min /
  crash. Margin to the 88 °C refuse threshold: ~16 °C.

## Issues hit & resolved
1. **fish vs bash heredocs/loops** — several inline `ssh diort '<bash>'` strings broke (`for…do…done`,
   `cat <<EOF`, unmatched `for`). Resolution: write scripts locally + `scp`, and keep remote strings to
   simple `;`-separated commands; the tooling itself uses `bash -lc $(printf %q …)`.
2. **Jar path mismatch** — `hosts.yaml` `runelite_libs` (`~/Desktop/runelite-client-libs`) was empty; the
   staged jar sat at `~/manny/`. `provision` step-2 rsync reconciles it to the configured path.
3. **provision step-5 (perf config) fish parse error** — the multi-line payload, `printf %q`'d, becomes a
   bash `$'…'` literal that fish can't parse. Non-fatal here (GPU-off perf keys were already applied to
   diort's profile: `runelite.gpuplugin=false`, `fpscontrol.maxFps=30`). Latent tooling bug for
   multi-line remote payloads → prefer a stdin-heredoc form later.
4. **A grind got cancelled by a stray `GOTO 3222 3218` (rid `navgate<ts>`)** — investigated to ground
   truth: **not** a plugin watchdog (no such code; MCP rids are 8-hex uuids). It was an
   **orchestration-side stray write** to `/tmp/manny_new_command.txt` by a *concurrent agent validating
   the command path while the grind ran on the same account*. Lesson: never issue commands / touch the
   command file for an account another routine is grinding. Guard: `STOP_PROCESSOR` / `START_PROCESSOR`
   makes the plugin ignore the command file during a grind.

## Open items (next phase = grind robustness, not infra)
- **Nav-follower stall:** the minimap-click waypoint-follower physically stalls on obstacles on some long
  routes → A*-recovery fails on uncached tiles (DEFECT-19 class, follower-side). `KILL_LOOP`'s short-hop
  approach still reaches the coop, so grinds self-navigate; long single GOTOs are unreliable. (task #21)
- **Track B** GameEngine collision/tile off-thread wraps: compile-gated locally, owes a live cooking/mining
  gate on diort.
- **Tutorial 05/06 double-run** (real overlap) + 6 fire-and-forget GOTOs — need one live tutorial pass on
  a fresh account to fix safely (see ROUTINE_AUDIT_2026-07-18.md).
- **do_run doesn't detach:** a long unattended grind should launch `run_routine.py` via setsid so a
  dropped SSH doesn't kill it.

## Versions / environment
diort: Arch, 4-core i5 (2011 iMac), jdk21-openjdk 21.0.11 (`/usr/lib/jvm/java-21-openjdk`), Python 3.14.4,
Xvfb :2 1600x1000x24, fish login shell, Tailscale + LAN 10.0.0.13, passwordless sudo.
Jar: `client-1.12.34-SNAPSHOT-shaded.jar` (39 MB, DEFECT-19b build). Commits: manny_mcp `16b410e`
(tooling), `654313e` (routine audit).
