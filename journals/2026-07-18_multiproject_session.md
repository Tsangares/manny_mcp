# 2026-07-18 — The Day PlayerHelpers.java Stopped Being a God-Class

## Headline

One 23,683-line file (`PlayerHelpers.java`, the manny RuneLite plugin's command-processing
core) went into today at ~16,075 lines carried over from yesterday's waves, and came out the
other side at **3,484 lines** — an 85% cut off the campaign-start size — split across roughly
twenty small, single-purpose `utility/` classes, every single phase live-gated against a
running client before the next one started. Along the way: four more off-client-thread crash
defects found and fixed, a two-attempt navigation saga that ended with the bot able to walk
farther than a screen's width for the first time, a first real grind-loop test that proved the
routine-runner pipeline works end-to-end, and — the twist ending — a thermal ceiling that makes
this laptop structurally unable to run a full unattended grind, which pushed the project's
next chapter onto a different machine entirely.

This is the story of that day, in order.

---

## Act 1: Finishing the refactor

The teardown of `PlayerHelpers.java` had been running since the previous session (Waves 0-6,
phases J2-1/2/3/9), already down from 23,683 to 16,075 lines by the time today started. Today
ran the rest of the `W6J2_SPLIT_PLAN.md` split plan to completion under one hard rule:
**single-writer discipline** — `PlayerHelpers.java` (and `MannyPlugin.java`) can only be edited
by one agent/phase at a time, full stop. Everything else — Python, docs, unrelated Java files —
parallelizes freely, but the god-class itself serializes strictly phase by phase, each one
compiled, and where it touched command-dispatch code, live-gated against the running client
before the next phase was allowed to start.

The other operational habit that made this survivable: **map by symbol, not by line number.**
Every extraction phase shifts every line number below the cut, so pre-flight docs and split
plans that said "PlayerHelpers.java:14683" were stale within one commit. Phases were planned
against method/class *names*, and re-derived against the live file at dispatch time rather than
trusting a plan document's line numbers from an hour ago.

Each phase left identical-signature delegating wrappers behind in `CommandProcessor` for every
method it moved out — so the 12 stateful command classes (`KILL_LOOP`, `SMELT_BAR`, `BUY_GE`,
etc.) never had to change at all, even as their backing implementation moved three or four
files away.

| Phase | What moved out | manny commit | PlayerHelpers before → after |
|---|---|---|---|
| A — Defect batch | DEFECT-3/11/13/14 source fixes (blocking, not an extraction) | `124a2c1` | — |
| J2-4 — Nav extraction | `PathfindingHelpers.java` (1,372) + `NavigationHelpers.java` (3,662) | `ad288ab` | 16,076 → 11,302 |
| J2-5 — UI/item/anim | `UiHelpers.java` (574) + `ItemUseHelpers.java` (404) + `AnimationHelpers.java` (479) | `bf83463` | 11,302 → 10,118 |
| J2-6 — CP inventory/query/bank | `ItemQuerySupport.java` (221) + `InventoryActionSupport.java` (1,005); `BankingSupport.java` absorbed deposit/withdraw | `069b71d` | 10,118 → 8,719 |
| J2-7 — Mining/world/cooking | `WorldActionSupport.java` (991) + `CookingFiremakingSupport.java` (1,635) + `MiningWorkflowSupport.java` (786) | `ee525e1` | 8,719 → 5,604 |
| J2-8 — Spell/equip/GE/smithing | `SpellCombatSupport`, `EquipmentSupport`, `GEInterfaceSupport`, `SmithingSupport` (+ `BarTypeInfo` FQN fix in `SmeltBarsCommand`) | `059cdb2` | 5,604 → **3,484** |

The build gate used throughout the day (JDK 21 pinned, checkstyle/pmd skipped for speed):

```bash
cd /home/wil/Desktop/runelite && \
  ./gradlew :client:compileJava -x checkstyleMain -x pmdMain --console=plain 2>&1 | grep -E 'error:|BUILD'
./gradlew :client:shadowJar -x checkstyleMain -x pmdMain --console=plain 2>&1 | grep -E 'error:|BUILD'
```

Every phase's live gate followed the same recipe: rebuild the shaded jar, relaunch account
`new` (parked in Lumbridge after yesterday's Tutorial Island clear), run `ipc_smoke.sh` (5/5),
then exercise the specific commands that phase's extracted classes now serve — MINE_ORE and
COLLECT_LUMBRIDGE_TIN_COPPER for J2-7, TELEPORT_HOME/EQUIP_BEST_MELEE/SMELT_BAR/CAST_SPELL/
GE_OPEN for J2-8, and so on — watching for anything that would only show up with the real
client attached: dispatch failures, missing wiring, or new exceptions in `/tmp/runelite.log`.
Every phase came back green; the riskiest single seam (KILL-during-GOTO, which depends on a
`shouldCancelNavigation` volatile surviving a class split) was explicitly gated in J2-4 and
passed — a walk was halted 22 tiles short of target with `[NAV-CANCEL]` firing correctly.

Wave 7 (regenerating `COMMAND_REFERENCE.md` / `ROUTINE_CATALOG.md` / `TOOLS_USAGE_GUIDE.md`
from the *live* command registry, not from stale hand-written lists) also landed today:
`COMMAND_REFERENCE.md` now lists the real 131 commands (121 `register()` calls + 10
legacy-switch survivors), and bogus entries like a standalone `ATTACK` command — which turned
out to be an argument value to `handleEquipBestMelee`, not a command at all — were removed.

The scorecard, restated because it's worth restating: **23,683 → 3,484 lines, 85% off, all
eight phases live-gated GREEN.** Roughly twenty focused `utility/` classes now hold what one
file used to.

---

## Act 2: The off-thread defect cluster

Every extraction phase's live gate turned up at least one crash of the exact same shape:

```
IllegalStateException: must be called on client thread
```

RuneLite's game-state accessors (`getWorldLocation()`, `Perspective.getCanvasTilePoly`,
`getConvexHull`, `getLocalLocation`, `getClickbox`, `findGameObjectsByName`, `getDistanceTo`,
etc.) are only safe to call from RuneLite's client thread. The manny plugin dispatches most
command logic on a separate `manny-background` executor thread for responsiveness — but a
handful of call sites, scattered across the codebase and mostly pre-existing (moved verbatim
during extraction, not introduced by it), called these accessors directly from that background
thread. Four instances of this same defect class turned up today alone:

- **DEFECT-15** — `UiHelpers.getHull`/`getMinimap`, sole caller `moveMouse`, hit during the
  J2-5 gate. Fixed + live-gated `5d3b7a1`.
- **DEFECT-16** — `InventoryActionSupport.handlePickUpItem`'s background task called
  `LocalPoint.fromWorld`/`cameraSystem.isTileVisible`/`prepareToViewTarget` off-thread, found
  during the J2-6→J2-7 gate window. Fixed + live-gated `5d3b7a1`.
- **DEFECT-17** — `GameEngine$GameHelpers.getDistanceTo`, tripped by
  `COLLECT_LUMBRIDGE_TIN_COPPER`'s distance-calc branch when the character isn't at the mine.
  Fixed + live-gated `fd97462`.
- **DEFECT-18** — `GameEngine$GameHelpers.findGameObjectsByName`, tripped by `SMELT_BRONZE`.
  Fixed `bb99171`.

The canonical fix, repeated four times today (and once yesterday for the original
DEFECT-1/DEFECT-3 instances), is a thread-aware guard:

```java
private WorldPoint readWorldLocationSafe()
{
    if (client.isClientThread())
    {
        return target.getWorldLocation();          // already on the right thread — direct call
    }
    return helper.readFromClientSafe(() -> target.getWorldLocation());  // hop over, safely
}
```

`isClientThread() ? direct-call : readFromClientSafe(...)` — the `isClientThread()` branch
matters because an *unconditional* wrap deadlocks any caller that's already running as an
overlay/render callback on the client thread itself (this bit the very first fix, DEFECT-1's
`CameraSystem.getYawToPoint`, which is called both from background command dispatch and from
`UIOverlays`). By the fourth occurrence of this pattern today, it stopped being a one-off
investigation and became a known bug class with a known fix — see
`REFACTOR_CAMPAIGN_LESSONS.md` for the canonical write-up. A further batch of GameEngine
off-thread reads (`isTileWalkable`/`getEmptyTile`/collision/combat-scan/camera methods) is
still open and explicitly queued rather than fixed blind, because these are hot paths that
need a live gate to verify, not a client-off source edit.

---

## Act 3: The navigation saga (DEFECT-19 and DEFECT-19b)

This is the best debugging story of the day. `PlayerHelpers.java`'s decomposition was done,
routines groundwork was in place, and the very first real grind-loop test — `GOTO 3235 3295 0`,
a 76-tile walk from spawn to the Lumbridge chicken coop — just... didn't move the character.
The log tail:

```
[GOTO] Distance: 76 tiles
[NAV-HYBRID] Initial distance: 76 tiles
[NAV-HYBRID] Line of sight clear: true
[NAV-METHOD] Using PATHFINDER API (distance: 76 tiles)
[NAV-API] Pathfinder API failed or unavailable, falling back to Global A* (PNG-based)
```

...and then nothing. Two attempts, 45 seconds, zero movement.

**Root cause, half 1:** "Pathfinder API" turned out to be an *external HTTP service* —
`https://osrspathfinder.com/find-path`, called via `java.net.http.HttpClient` with a 5s
timeout and two retries (`utility/PathfinderApiClient.java`). It's unreachable from this
sandbox, so it fails every time — by design, that's supposed to just fall back cleanly.

**Root cause, half 2, the actual bug:** the fallback is `PathfindingHelpers.findPathGlobalAStar`,
a global A* search whose per-tile walkability check goes through `CollisionMapCache.canMove()`
— a *live* cache populated only from tiles the player has physically visited. Its miss
behavior:

```java
// CollisionMapCache.java — canMove()
// CONSERVATIVE: If either tile is not cached, assume blocked
if (fromData == null || toData == null) { return false; }
```

For a fresh 76-tile route the cache coverage was ~0%, so A* treated nearly the entire map as
solid wall and returned no path almost instantly. Back in `gotoPositionSafe`, with `path ==
null` and `initialDistance >= 15`, the code hit a deliberate early-out:

```java
if (initialDistance >= 15)
{
    log.error("[NAV-UNIFIED-A*] ... is UNREACHABLE");
    log.error("[NAV-UNIFIED-A*] NOT falling back to Phase 1 ...");
    return false;   // <- character never moves
}
```

The maddening part: the log line right above the failure said `Line of sight clear: true` —
the information needed to just walk there in a straight line was already in hand, and got
thrown away because the method-selection logic only used the cheap directional-walk shortcut
for routes under 15 tiles.

**Fix v1** (`38cfb5e`) added a LOS-based directional-walk shortcut, but placed it in the
*giveup branch*, i.e. after `findPathGlobalAStar` had already run. Live gate #1 failed: no
movement, no new log line at all. Turned out the slow A* wasn't failing fast — on the
uncached 76-tile route it churned the ~10,201-tile blocked grid all the way to
`maxIterations = 50000` and **hung for over 51 seconds**, so the giveup branch never even got
reached. Bonus finding: that churn was itself a heat source, spiking the package to 90°C during
the failed gate.

**Fix v2** (`a5069a0`) moved the shortcut *before* the slow A* call, right at the
API-fallback point: if the external API fails and line-of-sight is clear, skip A* entirely and
go straight to `simpleDirectionalNavigation`. LOS-blocked routes still take the real
A*/smart-door path unchanged. Live gate #2 (2026-07-18 ~14:48) was green: the new log line

```
[NAV-API] Pathfinder API unavailable but LINE OF SIGHT CLEAR - directional walk, skipping slow A*
```

fired, no `[Global A*]` churn appeared, temperature stayed calm (~77°C — confirming the A*
churn itself was a heat contributor), and the character actually walked: 3221,3219 →
3232,3254, roughly 35 tiles, distance decreasing 51 → 49 tiles across multi-click minimap
navigation.

**DEFECT-19b**, found in that same gate: `simpleDirectionalNavigationMultiClick` used an
*absolute* 30-second wall-clock timeout, and a 76-tile walk at ~8 tiles per click simply takes
longer than that — the timeout fired mid-progress, while distance was still actively
decreasing, and aborted a walk that was working. Fix (`1403107`): make the timeout
progress-aware — track `bestDistance`/`lastProgressTime`, reset the no-progress clock on every
step of real improvement, fail only after 20 seconds with *zero* improvement, and keep a
generous 180-second absolute backstop so a genuinely oscillating walk still can't loop forever.
Compile-green; the full 76-tile live walk with this fix applied was deferred to a
thermally-stable host (see Act 5) rather than risked on this laptop.

---

## Act 4: The first live grind test

With the refactor complete and the routine engine's known bugs cleared (154 passing tests,
`ruff` clean), it was time to actually run something end-to-end: `chicken_killer_training.yaml`
via the standard runner:

```bash
./run_routine.py routines/combat/chicken_killer_training.yaml --loops N --account new
```

Two findings, one good, one a bug:

- **The pipeline itself works.** `run_routine.py` loaded the YAML, dispatched commands,
  produced a structured result (status/errors/final-state). This was the first real proof that
  the "LLM supervises a routine" layer isn't just aspirational — it's functioning
  infrastructure.
- **The routine itself was wrong.** Step 1's `GOTO` coordinate was `3180,3288` — west, across
  the river Lum, nowhere near the chicken coop — when the real coop sits around `3235,3295`
  (east side). Compounding it, that step had no `await_condition` and inherited the 30-second
  default timeout for what should be a 76-tile walk. Both fixed in
  `chicken_killer_training.yaml`: corrected coordinate, `await_condition location:3235,3295`,
  `timeout_ms 120000`.

That second bug turned out not to be a one-off — a prior audit pass had already fixed missing
timeouts on *blocking* commands (`KILL_LOOP`/`CHOP_TREE`/`FISH_DRAYNOR_LOOP`) but had missed
that a routine's opening long-distance `GOTO` needs the same treatment. A follow-up hardening
pass applied the lesson corpus-wide: **60 `GOTO` steps across 17 routine files** got
`await_condition location:X,Y` plus a distance-scaled timeout (60s for ≤20 tiles, 120s beyond
that). All 43 routines still parse clean after the pass.

---

## Act 5: The thermal wall, and the pivot to a different machine

Three separate live gates today measured the same thing: this laptop's CPU package hits
**90°C within about two minutes** of the manny client running, every time. The root cause,
nailed down mid-session: the client pins roughly 79% of one CPU core *continuously*, because
RuneLite is doing GPU-less software rendering on Xvfb (`:2`, headless, no GPU passthrough) —
it renders every frame at full rate even while the character stands still idle. Killing an
idle client dropped package temperature from 77°C to 72°C and load average from 1.45 to 0.81
within seconds — a clean, reproducible signal that heat, not power delivery, was the actual
constraint (earlier crash cycles this campaign had been chalked up, without proof, to "power
instability").

The mitigations already in place — `renice 15` on launch, a `client.sh` lifecycle helper that
refuses to start above 88°C and warns above 80°C, and a strict "client off during all
source-editing phases, on only for the duration of a gate" discipline — kept every individual
gate safe. But they don't solve the actual goal: a real unattended grind loop (a 76-tile walk
plus a 200-kill combat loop) runs for many minutes continuously, well past this machine's
2-minute thermal window. Components are proven in short bursts — the nav fix walks, the kill
loop dispatches, the runner pipeline produces structured results — but a *sustained* grind
cannot be safely proven here.

That finding drove a genuine strategic pivot, documented in `journals/DIORT_MIGRATION_PLAN.md`:
move the client to **`diort`**, a spare desktop-class machine on the user's own LAN (a 2011
21.5" iMac, Intel i5-2400S, 4 cores, dedicated AMD GPU, real Apple SMC-driven active fan
cooling) reachable both on LAN (`10.0.0.13`) and over Tailscale (`100.91.42.96`). The pitch:
idle package temp on diort reads **50°C** against an 80°C/86°C high/critical threshold — a huge
margin compared to the laptop's 90°C-in-two-minutes — and, just as importantly, it sits on a
**residential IP**, which sidesteps the datacenter-IP ban risk a cloud VM would carry for an
OSRS bot. The recon (read-only, nothing executed) confirmed: Arch Linux, same distro family as
the laptop so the known-good build recipe transfers directly; JDK 21 not installed but a
single official-repo package (`jdk21-openjdk`) away, matching the laptop's pinned toolchain
exactly (JDK 17 is too old for the shaded jar's class version, JDK 26 is present but untested
for RuneLite's AWT/Swing reflective-access needs); Xvfb, x11vnc, vncserver, ffmpeg, git, rsync
all already present; passwordless sudo; working internet and Tailscale. Verdict: **GO**, with
one deliberately-not-taken step — copying live Jagex session credentials to a second machine
and triggering a first login from a new IP/device fingerprint — flagged as the single
consequential, account-affecting decision that needs the user's explicit go-ahead in the
moment, not autonomous action.

The plan's design for *how* the laptop keeps driving diort is the seed of a more general
**machine-agnostic remote-run architecture**, still in design rather than built: because the
manny plugin's IPC is entirely local-file-based (`/tmp/manny_<acct>_command.txt`,
`_response.json`, `_state.json` — no network transport today), the cleanest shape is to run
*both* the RuneLite client and the routine runner / MCP server on whichever host has the
client, and have the orchestrating Claude Code session on the laptop drive it purely over SSH
(or, longer-term, have the MCP server itself run on the remote host with the laptop's session
connecting to it as if it were the dev box for this project). The explicit anti-pattern ruled
out in the plan: don't try to share `/tmp/manny_*` over the network (sshfs/NFS) — it would add
latency and failure modes to a control loop that's already timing-sensitive, per the DEFECT-19b
timeout tuning above. Keep IPC local to wherever the client lives; make *driving* it
location-independent instead.

---

## Tools and versions touched today

- **JDK 21** (`java-21-openjdk`) — pinned for both build and run via
  `~/.gradle/gradle.properties` (`org.gradle.java.home=...`); the system default JDK 26 breaks
  Gradle 8.8 outright, and the shaded jar's class files are major version 65 (Java 21 target),
  which rules out JDK 17 as a runtime on any future host.
- **Gradle 8.8** via `./gradlew :client:compileJava` / `:client:shadowJar` (checkstyle/pmd
  skipped during iteration for speed).
- **Xvfb `:2`** — headless X server hosting the client's canvas; no GPU passthrough, which is
  itself the root cause of today's thermal saga.
- **`ruff` + `pytest`** — Python side stayed green all day: ruff-clean `mcptools/`, 154 tests
  passing.
- **File-based IPC** — `/tmp/manny_<acct>_command.txt` / `_response.json` / `_state.json` /
  `_location_history.json`, namespaced per account; this is the mechanism the remote-run design
  discussion above is built around keeping local-only.
- **`scripts/client.sh`** (commit `b91762c`, manny_mcp) — the lifecycle helper (status/stop/
  start/restart) that operationalized the thermal policy: refuses to launch ≥88°C, warns ≥80°C,
  reniced launch, IPC-safe process detection via `pgrep -x java` + `/proc/<pid>/environ` (not
  `pgrep -f`, which self-matches the launching bash command).

---

## Open items, going into the next session

1. **diort credentials + login (user-gated).** Everything up to copying
   `~/.manny/credentials.yaml` and doing a first watched login is planned and ready
   (`journals/DIORT_MIGRATION_PLAN.md`); this single step needs explicit user approval in the
   moment, not autonomous execution.
2. **DEFECT-19b full-walk live gate.** The progress-aware timeout fix is compile-green and
   committed (`1403107`) but the actual full 76-tile unattended walk to the chicken coop still
   needs a live gate — deliberately deferred to a thermally-stable host rather than risked here.
3. **GameEngine off-thread read remnants.** DEFECT-18's fix pattern needs to be applied to the
   rest of the flagged cluster (`isTileWalkable`/`getEmptyTile`/collision/combat-scan/camera
   methods) — these are hot paths exercised by `KILL_LOOP` grinds, so relevant to grind
   stability, and explicitly queued for a host that can live-gate them rather than a blind
   client-off patch.
4. **Tutorial 05/06 double-run content decision.** `00_master.yaml` currently chains both
   `05_cooking_to_quest_guide.yaml` and `06_quest_guide.yaml`, which look like they may run the
   Quest Guide dialogue sequence twice — flagged, not yet resolved, needs a content call rather
   than a code fix.
5. **The remote-run architecture itself.** Only the design/plan exists so far (colocate client
   + runner + MCP server on whichever host has the client; drive over SSH/Tailscale from the
   laptop; never share `/tmp/manny_*` over the network). Nothing beyond diort recon has been
   built yet.
6. **tutorial-04 cook fix + engine disconnect-recovery** (`40f213d`, `1a4b5da`) — both
   spec-complete and committed, still owed a live-verify on `newbakshesh`, which is parked
   mid-Tutorial-Island specifically as that test bed.
