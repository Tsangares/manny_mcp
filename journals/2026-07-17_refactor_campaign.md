STATUS: DRAFT — final tutorial-test results pending.

# The Manny Refactor Campaign: seven waves, one night, two hard-stops

*2026-07-17. manny (RuneLite plugin, Java) + manny_mcp (Python MCP server / IPC layer). This
entry covers the refactor campaign from its architecture review through Wave 6/7 in-flight
work. Written mid-campaign — the tutorial-island acceptance test and the PlayerHelpers split
(Wave "J2") are still running. Update or supersede once both land.*

## Why: a plugin that outgrew its own refactor plans

manny automates RuneLite (OSRS) via a file-based IPC channel: an LLM agent writes a command
string to a per-account file, the plugin polls, executes, and writes a JSON response. It had
been growing since January 2026 without a demolition pass. A four-way parallel architecture
review (plugin core, plugin subsystems, Python/MCP server, IPC protocol — see
`journals/architecture_review_2026-07-17.md`) found the actual scale had quietly blown past its
own documentation:

| Claimed | Actual |
|---|---|
| "24 files" | 137 Java files, ~93,000 lines |
| PlayerHelpers "large" | 30,129 lines, 519 methods, 111 inline handlers — grew 8k lines *after* its last refactor plan |
| — | a 212-case dispatch switch + 90-field constructor |
| — | 105 MCP tools (~40 would do) |
| — | 4 different command-sender implementations, 5 control planes |
| — | 12 tracked backup files (5MB) sitting beside the git history |

The diagnosis all four reviewers converged on independently: **the newest code in every layer
is good — CommandBase, ClientThreadHelper, InteractionSystem, the mcptools registry pattern.
The debt is unfinished migrations. Every refactor built a new home next to the old one and
never demolished the old one.** Verdict: refactor, don't rewrite. The plan became a 7-wave
campaign, largely executed by parallel Claude subagents (opus for design-heavy Java, sonnet for
well-specified extraction/Python, haiku for mechanical deletes) with a live gate after every
risky wave: compile, relaunch the client, run the smoke harness, verify the specific behavior
that was touched, only then commit.

## Environment notes (versions that mattered)

- JDK 21 pinned via `~/.gradle/gradle.properties` (`org.gradle.java.home=/usr/lib/jvm/java-21-openjdk`) — the machine's system-default JDK 26 breaks Gradle 8.8, so this pin is load-bearing.
- Client runs headless on `Xvfb :2` (isolated from the user's desktop; Mouse/Keyboard dispatch synthetic AWT events to the canvas, no `Robot`, so any X server works).
- GPU plugin disabled on Xvfb (llvmpipe software rendering was pulling 374% CPU); CPU renderer + 30fps cap brought that to ~46%.
- A lightweight MJPEG viewer (`scripts/mjpeg_viewer.py`) was shipped as a systemd user unit (`mjpeg-viewer.service`, enabled + linger) on port 8787 so the client can be watched remotely over the Tailscale address, with a later pass adding auto-crop to the RuneLite window.
- Python side: `venv/`, `ruff` + `pytest` wired in as a gate (there was previously no linter — a duplicate-method definition had been silently shadowing a real function).

## The build/launch/test loop (reusable recipe)

Java build gate:
```
cd /home/wil/Desktop/runelite
./gradlew :client:compileJava -x checkstyleMain -x pmdMain --console=plain 2>&1 | grep -E 'error:|BUILD'
./gradlew :client:shadowJar   -x checkstyleMain -x pmdMain --console=plain 2>&1 | grep -E 'error:|BUILD'
```
Launch is account-namespaced (`MANNY_ACCOUNT_ID`, credentials pulled from a small credentials
module rather than hardcoded) onto `DISPLAY=:2`, with the GPU flags above baked into the
RuneLite profile. Smoke gate afterward:
```
cd /home/wil/Desktop/manny_mcp && ./scripts/ipc_smoke.sh <account>
```
five checks: process alive, round-trip latency, burst-send no-loss, STOP interrupts WAIT,
state freshness. Python gate:
```
cd /home/wil/Desktop/manny_mcp && ./venv/bin/ruff check mcptools/ && ./venv/bin/pytest -q
```
Every wave that touched interrupts got an explicit live "KILL gate": start a long WAIT or a
sleep-looping command, send KILL mid-flight, confirm it aborts within ~200ms-1s instead of
running to completion. That single test caught the single scariest bug class in the whole
campaign (below).

## What got built, wave by wave

**Wave 0 — hygiene.** Deleted 16 tracked backup files, wired ruff/pytest, fixed stale paths,
built the smoke harness. Nothing clever, but it's the reason every later wave had a gate to run.

**Wave 1 — Phase-0 bug fixes (9 fixes).** The architecture review's "stop the bleeding" list:
un-inverted the file-watchdog (it was listening for the wrong filesystem event, so every
awaited command paid its full multi-second timeout even when answered in 200ms), revived
`get_logs` (the capture thread was created but never started — the documented #1 debugging
step had been silently dead), fixed KILL's dead task-cancel path, and more.

**Wave 2 — transport & paths.** One `MannyPaths` class on the Java side and one
`transport.py` on the Python side replaced five path-construction sites and four different
command-sender implementations. A read-only command lane was introduced so that a query
(`GET_GAME_STATE`) no longer implicitly cancels an in-flight command — previously *every*
command was an implicit KILL of whatever was running. Verified live with a non-preemption test:
send a query mid-WAIT, confirm the WAIT still runs its full duration.

**Wave 3 — command registry + interrupts.** Replaced the 212-case switch with a
`Map<String, CommandBase>` registry (3a), migrated 23 simple inline handlers into their own
classes (3b), then added real interrupt support: `checkInterrupt()`/`sleepChecked(ms)` on
`CommandBase`, wired into every registered command, plus a fix to `Mouse.replay()` which had
been silently swallowing `InterruptedException` (an in-flight mouse move was previously
unstoppable).

*The KILL-flag bug.* During 3c's live gate, a genuinely nasty one turned up: `executeCommand`'s
`finally` block cleared the interrupt flag as soon as *any* command finished — including
KILL/STOP itself. That meant a KILL's flag survived only milliseconds, so a detached background
loop polling `sleepChecked` never saw it fire. Fixed by excluding KILL/STOP/EMERGENCY_STOP from
that clear (a fresh per-dispatch reset still keeps each *new* command starting clean). This is
flagged in the handoff doc as "do not simplify this away" — it's a one-line fix that's easy to
"clean up" back into the bug.

**Wave 4 — dedup & consolidation.** Ran as parallel phases: GE (Grand Exchange) widget helpers
deduplicated from 4 copies each of two methods into canonical statics; a supposedly-alive
`ResourceFinder`/`BankingHelper` pair turned out to be 1,285 lines of 100%-dead code (zero
callers) and was deleted outright; nine wrong keyboard keycodes were fixed (`~` was typing
`VK_TAB`, `` ` `` was typing `VK_ENTER` — both silent because the game only reads the
displayed character). `InteractionSystem` became the single click authority — the old
"MOUSE_MOVE + MOUSE_CLICK" pattern raced against widget state; the new atomic click path
replaces it everywhere. All twelve of the remaining "stateful" command handlers (teleport,
kill-loop, bank/smelt/buy flows) were migrated onto the registry.

**Wave 5 — Python modernization.** MCP tool surface pruned **78 → 39** registered tools (with
a full old→new rename map kept for reference), one canonical click tool instead of five
overlapping variants, `pyproject.toml` split into extras, a file lock added around session
writes, and every blocking `subprocess`/`time.sleep` call in async handlers moved to
`asyncio.to_thread` so the MCP server stops freezing mid-tool-call. Latch conversion: 112 raw
`CountDownLatch` sites across 38 command classes converted to the project's own
`ClientThreadHelper` idiom (net −899 lines), leaving 4 intentionally-kept latches that are
genuinely executor-completion barriers, not client-thread reads.

**Wave 6 — click authority, driver, and the big deletion.** `InteractionSystem` absorbed the
click-handling cluster in full (net effect: PlayerHelpers −707, CombatSystem −340,
InteractionSystem +1076 — a real move, not a wash). The Python driver was rewired to run
in-process instead of spawning a second server. Then, with the user's go-ahead, **ScenarioEngine
replay was retired** as an execution engine — see the philosophy note below — which let one
wave delete `Actions.java` (5,372 lines), `NavigationSystem` (291, zero callers),
`GameEngine.BehaviorExecutor` (208, zero callers), and the LOAD_SCENARIO/LOAD_CMDLOG commands:
**net −8,344 lines** in a single commit. The recorder half was kept and extracted separately
(`ScenarioExporter.java`) since it still feeds routine-drafting.

A subsequent dead-code purge (Wave "J2-1") found ~45 more dead `handleX` bodies — leftovers
from earlier migrations that had removed the switch *cases* but never the method *bodies* — and
deleted another 3,919 lines from PlayerHelpers (23,683 → 19,764), each one verified dead by a
repo-wide grep before deletion.

## The philosophy shift: routines are the product

A companion design document (`journals/ROUTINE_STRATEGY_2026-07-17.md`) surveyed the four (yes,
four) overlapping recording/replay pipelines that had accumulated — an always-on command log, a
session recorder, a location-history-based routine generator, and the Java-side
ScenarioEngine/recorder pair — and made the case that this was the same "unfinished migration"
disease one layer up. The recommendation, accepted by the user:

- **One execution format**: YAML routines run by `run_routine.py`. It already has loops, health
  checks, crash auto-restart, and await-conditions — the layer worth keeping.
- **Agent drives anything novel; routines run anything repeated.** Grinding is cheap in
  routines and expensive in agent-tokens; novel/dialogue-heavy content is the reverse.
- **One authoring pipeline**: play or agent-drive → capture → generate a routine draft →
  human/agent adds await-conditions → validate. The naive `session_to_routine` converter is
  deprecated in favor of the location-history-based generator, which already infers conditions.

This got written up separately as the project's standing philosophy: *there is no final state;
routines are the product.* An LLM driver's job is always either running/monitoring a routine or
building one. A follow-up hardening proposal
(`journals/ROUTINE_ENGINE_HARDENING_2026-07-17.md`) designs (not yet built) a single merged
condition grammar — `hp:`, `hp_pct:`, `skill:`, `equipped:`, `dialogue_open`, `in_combat` — plus
`only_if`/`skip_if` step guards and a small `on_fail: continue|retry:N|goto:id|abort` policy, to
replace two currently-divergent condition dialects and give routines an HP-based EAT gate the
old ad-hoc `EAT_FOOD` threshold used to have.

## The night's two hard-stops (and why the handoff doc survived them)

The campaign ran into two unrelated hard-stop events within a few hours of each other, and both
validated the same operating discipline: **a durable, continuously-updated handoff document is
the only state that survives** — agent transcripts are not.

1. **Machine crash**, roughly five minutes after three fresh agents were dispatched. `/tmp` was
   wiped, so the just-started agent transcripts were gone — but because they'd only just
   begun, zero durable work was lost, and both git repos were already clean and pushed. Recovery
   was mechanical: relaunch Xvfb, relaunch the client (session tokens survived the crash), run
   the smoke gate, redispatch the three agents fresh.
2. **API session limit hit** mid-run, a couple hours later. This one was worse: a driver agent
   had just root-caused a real defect (below) and its write-up died with the session before it
   could be saved. The orchestrator re-derived the root cause independently from the raw
   RuneLite log file and wrote it into a durable defect log
   (`journals/TUTORIAL_TEST_DEFECTS_2026-07-17.md`) rather than trusting memory. When the
   session limit reset, the driver and a planning agent were resumed from where they left off
   using the durable journals as ground truth, not from any cached transcript.

Lesson captured verbatim in the handoff doc: *"/tmp transcripts + session-only crons die with
the box; this handoff doc is the only durable state — keep it current."*

## DEFECT-1: a real threading regression, caught by actually playing the game

The acceptance test — driving the tutorial-island account through the game end-to-end on the
refactored stack — was not just smoke-testing. It caught a genuine regression that no compile
gate or unit test would have seen: every `INTERACT_OBJECT` command that triggered a
camera-orient (opening a door, using a range) started throwing
`IllegalStateException: must be called on client thread`.

Root cause, traced from the log stack straight through the call chain
(`CameraSystem.getYawToPoint` → `pointCameraAt` → `InteractionSystem.clickTileObjectSafe` →
`interactWithGameObject`): a `getWorldLocation()` read — a RuneLite API that's only legal on the
client thread — was happening directly on a background executor thread. The actual culprit
turned out to be subtler than the first read of the stack suggested: it wasn't the *target*
object's location read that was unguarded, it was the *player's own* location read inside the
same yaw calculation. The fix wrapped that specific read in the existing `ClientThreadHelper`
pattern (conditionally — an unconditional wrap would have deadlocked two other overlay call
sites that already run on the client thread). Root-caused and fixed same night; deploy was
deferred behind the tutorial-run deployment freeze (no jar rebuilds while the driver owns the
client).

The regression was almost certainly introduced by the latch-to-`ClientThreadHelper` conversion
sweep in Wave 5 or 6 — exactly the kind of thing a live gameplay test is built to catch, and a
reason the later PlayerHelpers-split plan added an explicit thread-safety audit pass rather than
assuming "latches converted" is the same thing as "thread-safe."

The driver worked around it live by routing through doors via pathfinding (`GOTO` to a tile on
the far side opens doors implicitly) rather than direct interaction, and by falling back to a
hover-and-read-the-action-text click primitive for anything that still needed direct object
interaction. Several smaller defects surfaced the same way: a coordinate-space mismatch between
one click primitive and the mouse-hover primitive in stretched display mode, a scan command that
omits wall objects (doors) entirely, and door-state reporting in the state file lagging the
actual game state.

## Routine QA sweep

Separately, a validator pass ran the deep-validation tool across all 42 routine YAML files.
Result: 33 clean, one real bug fixed (a quest routine was sending a literal, nonexistent game
command instead of the supported `mcp_tool:` step shape — corrected to match an already-proven
pattern used elsewhere in the library), and 8 "errors" that turned out to be validator false
positives — the validator doesn't yet recognize the `mcp_tool:` step shape or reference/config
files that intentionally have no `steps:` key. Those gaps are queued as validator fixes, not
routine fixes.

## Numbers, end to end (so far)

- MCP tool surface: 78 registered → 39.
- Command dispatch: 212-case switch → registry (131 live commands after dead-command removal).
- ScenarioEngine/Actions retirement: −8,344 lines in one commit.
- Dead-handler purge: another −3,919 lines.
- Latches converted to the safe client-thread helper: well over a hundred sites across two
  waves, with only a small, intentional handful left as genuine (non-client-read) barriers.
- Backup cruft removed at the very start: 16 files.

## Still open

- **Tutorial-island acceptance test is in progress**, currently past the mining/smithing
  section and approaching combat. This document will be updated once it finishes — hence the
  DRAFT status.
- **The PlayerHelpers split ("Wave J2")** has a full 12-phase execution plan written
  (`journals/W6J2_SPLIT_PLAN.md`) targeting every file under 5,000 lines (PlayerHelpers currently
  ~19.7k, down from 23.7k, with a 13,000-line nested `CommandProcessor` still inside it); phases
  are landing incrementally with compile gates between each.
- **The routine-engine hardening proposal** (merged condition grammar, step guards, structured
  run events, `on_fail` policy) is designed but not implemented — first slice estimated at about
  a day, with a few open questions parked for a decision (absolute vs. percentage HP thresholds,
  compound guard conditions, auto-abort defaults for repeated step failures).
- Documentation regeneration (both CLAUDE.md files, from the actual current code rather than
  the stale "24 files" description that started this campaign) is the last planned wave.

---

## Addendum (2026-07-18 ~01:30, written during crash-#3 recovery)

Events after the main entry was drafted:

- **W6-J2 executed four phases in one night**, each compile-gated and committed separately:
  J2-1 dead purge `bc4838c` (−3,919), J2-9 matchesMenuEntry collapse `4080b11`, J2-2 latch
  conversion `ebeb3c0` (83/90 sites; the survey grep had missed 21 fully-qualified
  `new java.util.concurrent.CountDownLatch` sites — twice, ironically: the phase agent's
  final count made the same grep mistake, caught by orchestrator verification), J2-3
  Group-A un-nest `2fcb602` (7 new utility files; PlayerHelpers 23,683 → 16,075 across the
  night). J2-4 (nav extraction) deliberately held for its own live gate.
- **Tutorial Island test reached the banking section.** Sections passed: character creation,
  Gielinor Guide, survival, chef, emotes/run, Quest Guide, mining/smithing, combat (melee +
  ranged rat kills). Ten defects logged; the big lesson is that GOTO's arrival tolerance
  (DEFECT-7) and an undismissable modal message (DEFECT-8) compounded into a 40-minute
  diagnostic loop — driver-priority fixes are those two, not the flashier threading bug.
  The validated door workaround (hover-sweep + walk-through) carried the whole run on the
  old jar.
- **DEFECT-1 was fixed and committed** (`73c7256`) same-night: the real culprit was the
  player-position read, not the target's, and the naive wrap would have deadlocked overlay
  callers — a thread-aware read (direct on client thread, hop otherwise) was the answer.
- **Crash #3 (~01:20): the harness process restart took the driver agent, the RuneLite
  client, and Xvfb :2 with it.** Third hard-stop in one campaign night (machine crash,
  session limit, harness restart). The durable-journal discipline paid off again: recovery
  is a checklist in the handoff doc, and the freeze lift turned the crash into the deploy
  window — the rebuilt jar now carries the DEFECT-1 fix, so the final tutorial sections
  double as its live validation.
