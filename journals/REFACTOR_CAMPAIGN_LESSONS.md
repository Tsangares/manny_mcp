# The Manny Refactor Campaign — Lessons Learned
**Date:** 2026-07-17 to 2026-07-18

## The Problem

By mid-2026-07-17, `manny` (the RuneLite plugin) and `manny_mcp` (its Python IPC/MCP layer) had
outgrown their own documentation. A four-way architecture review found the plugin's central
god-class, `PlayerHelpers.java`, had grown to **23,683 lines** (519 methods, 111 inline command
handlers, a 212-case dispatch switch, a 90-field constructor) — 8k lines larger than it was after
its *last* refactor plan, because every prior refactor built a new home next to the old code and
never demolished the old code. The Python side had a parallel problem: 105 MCP tools where ~40
would do, 4 different command-sender implementations, 12 stale backup files sitting in git. None
of this was a crash or a broken feature — it was accreted debt that made the codebase unsafe to
build new automation (routines) on top of.

Full campaign: `journals/REFACTOR_CAMPAIGN_HANDOFF.md` (the live, blow-by-blow record — 800+
lines, phase by phase). This journal distills the durable lessons out of it.

## Root Cause

Two independent root causes drove most of the pain in this campaign, and neither was the one
first suspected:

1. **The machine kept hard-stopping, and it was blamed on power/hardware for most of the
   campaign.** The real cause, found only late: the RuneLite client, running headless on Xvfb
   with no GPU, does **software rendering of every frame continuously**, even when the character
   is completely idle — pinning ~79% of one CPU core nonstop. Sustained load pushed the CPU
   package to 77°C+ and the machine hard-stopped. This is a thermal problem, not a software bug,
   and no amount of debugging the Java or Python would have found it — it only showed up as
   "the box died again," repeatedly, for most of the campaign.

2. **A recurring off-client-thread bug class, introduced (or exposed) piecemeal across many
   refactor phases**, because "read game state" methods were being extracted and moved without
   anyone auditing *which thread calls them*. RuneLite's API throws `IllegalStateException("must
   be called on client thread")` for scene/camera/perspective reads made from any thread other
   than the client's own — but `manny`'s command dispatch runs handler bodies on a background
   thread pool, so any refactor that moved a "just build a Map<String,Object> from the current
   game state" method verbatim was liable to carry this landmine with it.

## Key Lessons

### 1. Thermal is the crash root cause — not software, not OOM

**What happened:** The session absorbed roughly five hard-stop events. For most of the campaign
these were treated as unexplained hardware/power flakiness, with the stated strategy being "no
software fix, just fast recovery." Partway through 2026-07-18, someone actually measured it.

**Why:** RuneLite on a GPU-less Xvfb display renders every frame in software (llvmpipe), even
with nothing happening on screen. That's a fixed, continuous CPU cost independent of what the
character is doing. Measured directly: killing an idle client dropped the CPU package temperature
77°C → 72°C and load average 1.45 → 0.81 within seconds — proof the client itself was the thermal
driver, not incidental background load.

**Solution — policy, not a code fix** (there is no code fix for "software rendering costs CPU"):
```
# BAD — client left running through hours of Java/Python source editing
# (compiling, extracting classes, and writing docs never need a live client)
start_runelite(...)
# ... six hours of Java refactor work with the client idling in the background ...

# GOOD — client OFF during source phases, ON only to gate, then killed again
scripts/client.sh stop                  # before any source-only phase
# ... edit, compile, extract classes ...
scripts/client.sh start new             # only now, to live-gate
renice 15 <pid>                          # low priority even while it's up
# ... run the specific gate: smoke test + the one behavior that changed ...
scripts/client.sh stop                  # kill it again immediately after
```
Also: don't stack multiple concurrent subagents *while* the client is running — client + heavy
agent parallelism together is the hot combination. Source-phase agents with the client off are
fine to parallelize freely.

**The other half of this lesson: durable-state + fast-recovery beats root-causing, until you
actually find the root cause.** Every crash before the thermal finding still cost only minutes,
not hours, because of two disciplines kept up the whole campaign:
- **Commit-per-unit for crash-cheap work** (source edits, docs) — a crash mid-phase loses nothing,
  `git log` shows exactly where things stood, resume for free.
- **Journal-per-section for crash-expensive work** (live client drives, routine tests) — a driver
  agent walking Tutorial Island wrote its defect findings to a journal file *as it went*, so a
  crash mid-drive resumed at the last passed section instead of from character creation.
- A single always-current "live handoff" doc (`REFACTOR_CAMPAIGN_HANDOFF.md`) was the one source
  of truth for "where are we, what's next" — every agent read it first and updated it before
  finishing. This is what made a Claude Code process restart (which killed the client, Xvfb, and
  the in-flight driver agent all at once) a non-event: the next session picked the doc back up
  and kept going within minutes.

### 2. The off-client-thread bug cluster — and the canonical fix

**What happened:** Across the campaign, at least six distinct defects (DEFECT-1, 3, 15, 16, 17,
18) were the *same underlying bug*, discovered independently at different points because each one
lived in a different method: `IllegalStateException: must be called on client thread`. Culprits
included `Player/TileObject.getWorldLocation()`, `LocalPoint.fromWorld(...)`, `Perspective.*`,
`CameraSystem.*`, and `GameEngine.getDistanceTo`/`findGameObjectsByName` — all client-thread-only
accessors, all called from result-building or scene-read methods running on manny's
background command-dispatch thread.

**Why:** `manny`'s `CommandBase.executeCommand` runs handler logic off the client's own game
thread (so command dispatch doesn't block the game tick). Any method that reads live scene state
— building a result map, computing a camera angle, checking a distance — has to explicitly hop
onto the client thread to do it. Code that was originally written (or later *moved*, verbatim, by
an extraction phase) without that hop worked fine until the exact tick it got called off-thread,
then threw. Several of these (15, 16, 17, 18) were **pre-existing bugs that had nothing to do with
the refactor phase that "found" them** — they were moved verbatim by an extraction and only then
got exercised by a live gate for the first time.

**Solution — the canonical fix pattern, applied every time this bug class showed up:**
```java
// BAD — reads a client-thread-only accessor unconditionally; throws when called
// from the manny-background command-dispatch thread (which is most of the time)
WorldPoint loc = player.getWorldLocation();

// GOOD — fast-path on the client thread, safe-hop otherwise; ONE hop for everything
// the method needs, not one hop per field (multiple readFromClientSafe calls in the
// same method serialize onto the client thread N times instead of once)
WorldPoint loc = client.isClientThread()
    ? player.getWorldLocation()
    : helper.readFromClientSafe(() -> player.getWorldLocation());
```
`readFromClientSafe` (over `readFromClient`/`readBatchFromClient`/`executeOnClient`) matters
specifically because it **returns `null` on timeout instead of throwing** — callers must handle
that null by failing safe (return a "not available" result, don't NPE on it), not by assuming the
read always succeeds. See `journals/DEFECT3_FIX_SPEC.md` for a fully worked example (SCAN_TILEOBJECTS).

**Practical implication for any future extraction/move of scene-reading code:** don't just check
that it compiles and that a *happy-path* live gate passes — specifically exercise the path where
the command handler runs asynchronously relative to the game tick (a rapid-fire command battery is
a good forcing function; it's what actually surfaced DEFECT-17's residual timeout behavior).
A **recommended follow-up not yet done**: one dedicated "GameEngine off-thread read audit" pass
that batch-fixes the whole remaining cluster (`findGameObjectsByName`, `rotateToNPC`,
`rotateToObject`, `prepareToViewTarget`, `findAllNearbyObjects`, the scene-scan methods) in one
gate, instead of continuing to fix them one-by-one every time a new extraction phase trips over
the next instance.

**Caution — not everything found in the same defect batch is this bug class.** DEFECT-11
(`TILE` NPE) was a dependency-injection wiring bug (`tileMarkerManager` field null because a
`@Inject` constructor param was added without fixing the wiring), DEFECT-13 was a hardcoded wrong
widget ID, and DEFECT-14 was a coordinate-space validation bug. All three got fixed in the same
"Phase A" defect batch as the thread bugs, but they are unrelated root causes — don't assume every
"IllegalStateException"-adjacent bug found near a thread bug is the same class; check the actual
stack trace.

### 3. Single-writer discipline is what made an 85% decomposition safe

**What happened:** `PlayerHelpers.java` went from 23,683 lines to 3,484 lines (85% reduction)
across eight sequential phases (a defect batch, then J2-4 through J2-8), each moving a coherent
slice — navigation, UI/item/animation, inventory/bank, mining/world/cooking, spell/equip/GE/
smithing — into its own `utility/` support class. Zero merge conflicts, zero lost work, across a
file that was being edited by many different agents over roughly 24 hours including three
mid-session crashes.

**Why:** Exactly one agent was ever allowed to hold write access to `PlayerHelpers.java` (and
separately, `MannyPlugin.java`) at a time. Every other file in the repo — Python tooling, docs,
independent Java classes, the GE dedup work, the input-handling fixes — was explicitly
parallelized across multiple concurrent agents, because those files had no shared-state risk.
The rule was stated once and enforced every phase: *"PlayerHelpers.java (~30k lines) and
MannyPlugin.java — only ONE agent edits either per sub-phase. Everything else parallelizes."*

**Solution — the pattern to replicate on any future god-class decomposition:**
```
# BAD — dispatch three agents at once to split different sections of the same
# giant file "because they don't logically overlap" — they still race on git,
# and worse, on each other's *understanding* of the file's current line numbers
agent_A: extract nav methods from PlayerHelpers.java
agent_B: extract UI methods from PlayerHelpers.java     # SAME FILE, CONCURRENT
agent_C: extract banking methods from PlayerHelpers.java # SAME FILE, CONCURRENT

# GOOD — strictly sequential single-writer phases on the hot file; anything
# that doesn't touch it runs in parallel alongside
agent_A: extract nav methods from PlayerHelpers.java     # only writer this phase
(parallel, no PlayerHelpers.java): agent_B fixes Keyboard.java
(parallel, no PlayerHelpers.java): agent_C dedupes GE widget code
# ... A finishes, compiles, live-gates, commits ...
agent_D: extract UI methods from PlayerHelpers.java      # next phase, now sole writer
```
Every extraction phase also left identical-signature delegating wrappers in
`CommandProcessor` for every moved public method, so the 12 stateful command classes that call
into `PlayerHelpers` never had to change across any of the eight phases — the internal
reorganization was invisible to callers.

### 4. The client-detection trap: `pgrep -f` self-matches your own command

**What happened:** More than once, an agent trying to find/kill the running RuneLite process used
`pgrep -f 'java -jar.*shaded.jar'` — and it matched the agent's *own bash tool-call command line*
(which contains the literal string `shaded.jar` because it's describing what to launch), not just
the actual java process. This produced false positives (killing the wrong thing, or believing a
client was running when only the detection command itself matched).

**Solution:**
```bash
# BAD — self-matches any bash command that happens to mention "shaded.jar",
# including the pgrep/kill command's own argv
pgrep -f 'java -jar.*shaded.jar'

# GOOD — match on the exact process name, then disambiguate by environment
for p in $(pgrep -x java); do
  grep -q '^MANNY_ACCOUNT_ID=' /proc/$p/environ && echo "$p is a manny client"
done
```
This was significant enough to get called out explicitly in the campaign handoff as an "OPS
LESSON" after it caused real confusion (three orphaned clients accumulating from a launch recipe
that didn't clean up before relaunching, two of which shared a session token and got one JVM
killed by Jagex's duplicate-login detection).

### 5. Map by symbol, not by line number — split plans go stale fast

**What happened:** A dedicated planning pass (`journals/W6J2_SPLIT_PLAN.md`) mapped out the entire
remaining `PlayerHelpers.java` decomposition with specific line-number ranges for each method to
extract. By the time the third extraction phase ran, the file had already shrunk from ~19,764 to
~16,075 lines from the two phases before it — every line-number reference in the plan for methods
below roughly line 10,000 was now pointing at the wrong code.

**Solution:** every extraction agent, from J2-3 onward, was explicitly instructed to **locate
target methods by name (grep) rather than by the plan's line numbers**, treating the split plan as
a list of *what* to move and *why*, never as a literal line-range diff to apply. The plan's
architectural analysis (which methods, which support class they belong in, what they depend on)
stayed valid the whole campaign; its line numbers were stale after the very next phase.

### 6. The blocking-command routine trap: missing `timeout_ms` abandons the client mid-grind

**What happened:** Several `manny` commands (`KILL_LOOP`, `CHOP_TREE`, `FISH_DRAYNOR_LOOP`) are
**fully synchronous on the Java side** — the handler runs its own internal `while` loop and only
calls `writeSuccess(...)` once the whole task finishes (max kills reached, inventory full, target
level hit). That can take many minutes. But `run_routine.py`'s step executor defaults `timeout_ms`
to 30000 (30s) when a routine step doesn't set one, and it uses that value as the wait budget for
the plugin's response. Nine `routines/*.yaml` files were auditing-and-fixed for this in the
grind-routine readiness pass.

**Why this is dangerous, not just an inconvenience:** when the 30s wait elapses, `run_routine.py`
gives up waiting and moves the runner state on — but the Java side's `while` loop **keeps
running**, because it was never told to stop; the runner just stopped listening for its response.
The result is a client left grinding a combat/skilling loop completely unsupervised, with nothing
watching health, position, or interrupt conditions, for however long the loop actually takes.

**Solution:**
```yaml
# BAD — no timeout_ms on a command that's fully synchronous and can run for
# many minutes; run_routine.py silently abandons it at the 30s default and
# the client keeps grinding, unwatched
- action: KILL_LOOP
  args: "Chicken 200"

# GOOD — timeout_ms set generously above the command's real expected duration,
# so the runner stays attached (and therefore supervising) for the whole grind
- action: KILL_LOOP
  args: "Chicken 200"
  timeout_ms: 3600000   # 1hr — real duration for a 200-kill loop
```
General rule for any future routine step: if the underlying Java command is a blocking loop
(check the handler source, don't guess from the command name), its `timeout_ms` must exceed the
loop's real worst-case duration, not the default.

### 7. Verify-then-fix delegation avoids churn on already-fixed bugs

**What happened:** A routines-phase groundwork pass was dispatched to fix three previously-flagged
Python engine bugs: an rid-correlation bug in command sending, a `no_item_in_bank:` condition stub
that always returned `False`, and a `restless_ghost.yaml` routine step using an unrecognized
`action: MCP_TOOL` shape. When the agent went to fix them, all three turned out to already be
fixed in prior commits (verified against source, not assumed) — the bug reports were stale.

**Why this mattered:** the agent had been instructed to *confirm the bug still exists before
touching code*, not to blindly re-apply a fix. Because of that instruction, it returned a clean
"already fixed, verified, no change needed" report instead of re-touching working code, silently
introducing a regression, or writing a redundant duplicate fix.

**Solution — the pattern to reuse:** when dispatching a bug-fix agent against a bug list that's
more than a few hours old (especially spanning a crash/restart boundary where other agents may
have independently touched the same area), instruct it explicitly to **verify against current
source first, report "already fixed" as a valid and complete outcome, and only then proceed to
fix** anything actually still broken. Treat a no-op "confirmed already fixed" result as success,
not as the agent failing to find work to do.

## Anti-Patterns

1. **Don't** detect a running process with `pgrep -f <substring that appears in your own launch
   command>` — it self-matches. Use `pgrep -x <exact-name>` plus an environment/argv
   disambiguator.
2. **Don't** let multiple agents write to the same god-class file concurrently, even if their
   target method ranges look non-overlapping on paper — enforce single-writer per hot file,
   parallelize everything else.
3. **Don't** trust a split/refactor plan's line numbers past the very next commit to the file it
   describes — locate targets by symbol/name every time.
4. **Don't** move or write a "just read some scene/game state and build a result" method without
   checking which thread it runs on — client-thread-only accessors throw unconditionally off-
   thread, and this bug class recurs every time such code is copied or moved verbatim.
5. **Don't** leave a step targeting a fully-synchronous, long-running command without an explicit
   `timeout_ms` well above its real duration — the runner will silently detach and leave the
   client running unsupervised.
6. **Don't** re-apply a fix to a bug without checking current source first — verify, then fix;
   treat "already fixed" as a valid, useful outcome, not a failure to find work.
7. **Don't** assume every hard-stop/crash in a long-running headless-client session is
   power/hardware-inherent — measure (temperature, load) before writing off a root cause as
   undiagnosable.

## Debugging Commands

| Command | Purpose |
|---------|---------|
| `for p in $(pgrep -x java); do grep -q '^MANNY_ACCOUNT_ID=' /proc/$p/environ && echo $p; done` | Find the real manny client PID without `pgrep -f` self-matching |
| `scripts/client.sh {status,start,stop,restart} <account>` | Clean client lifecycle for gates — no ad-hoc process juggling |
| `sensors` / package temp read, then `scripts/client.sh stop` and re-check | Confirm/rule out thermal as a crash cause before blaming power |
| `grep -rn "getWorldLocation\|LocalPoint.fromWorld\|Perspective\.\|cameraSystem\." <file>` | Find candidate off-client-thread reads in a method being extracted/moved |
| `./gradlew :client:compileJava -x checkstyleMain -x pmdMain --console=plain` | Fast Java compile gate (skip lint) before the full shadowJar build |
| `./scripts/ipc_smoke.sh <account>` | 5-check smoke gate: process alive, round-trip latency, burst no-loss, KILL interrupts WAIT, state freshness |
| `WAIT 30000` then `KILL` mid-flight | Reusable live "KILL gate" — the interrupt seam is the single scariest bug class in a refactor of this dispatch system |

## Interface Gaps Identified

- [x] Plugin needed: thread-safe read pattern for scene/camera state from background-thread
  command handlers — now standardized as `client.isClientThread() ? direct() :
  helper.readFromClientSafe(() -> direct())`, but not yet swept across the whole codebase
  (DEFECT-18 and the broader GameEngine off-thread cluster are still open).
- [ ] Routine engine needs: a way to mark a routine step's underlying command as
  "fully-synchronous/blocking" so the runner can pick a sane default timeout automatically,
  instead of relying on every routine author remembering to set `timeout_ms` by hand.
- [ ] CLAUDE.md needs (done this campaign, worth re-verifying periodically): keep the "claimed vs
  actual" scale of the codebase honest — this campaign started because documentation claimed "24
  files" against an actual 137 files / ~93,000 lines, and that gap is exactly what let the debt
  hide for so long.

## Files Modified (campaign-wide highlights; not exhaustive — see `REFACTOR_CAMPAIGN_HANDOFF.md`)

| File | Change |
|------|--------|
| `manny/utility/PlayerHelpers.java` | 23,683 → 3,484 lines (85% reduction) across 8 sequential single-writer phases |
| `manny/utility/NavigationHelpers.java`, `PathfindingHelpers.java` | New, extracted from PlayerHelpers (J2-4) |
| `manny/utility/UiHelpers.java`, `ItemUseHelpers.java`, `AnimationHelpers.java` | New, extracted from PlayerHelpers (J2-5) |
| `manny/utility/ItemQuerySupport.java`, `InventoryActionSupport.java`, `BankingSupport.java` | New/expanded, extracted from PlayerHelpers (J2-6) |
| `manny/utility/WorldActionSupport.java`, `CookingFiremakingSupport.java`, `MiningWorkflowSupport.java` | New, extracted from PlayerHelpers (J2-7) |
| `manny/utility/SpellCombatSupport.java`, `EquipmentSupport.java`, `GEInterfaceSupport.java`, `SmithingSupport.java` | New, extracted from PlayerHelpers (J2-8) |
| `manny/actions/*` (deleted) | ~8,344 lines removed — dead Actions.java, NavigationSystem, GameEngine.BehaviorExecutor, replay-retirement (W6-J1) |
| `manny_mcp/scripts/client.sh` | New — client lifecycle helper (status/start/stop/restart), thermal-aware |
| `manny_mcp/COMMAND_REFERENCE.md`, `ROUTINE_CATALOG.md`, `TOOLS_USAGE_GUIDE.md` | Regenerated from the live 131-command registry (Wave 7) |
| `manny_mcp/routines/skilling/*.yaml`, `routines/combat/*.yaml` | 9 files fixed for missing `timeout_ms` and other executor-vocabulary mismatches |
| `manny_mcp/routines/tutorial_island/*.yaml` | Sections 07-10 transcribed with live-captured coordinates; `00_master.yaml` chains 01→10 |
