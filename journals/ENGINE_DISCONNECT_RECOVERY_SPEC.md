# Engine Disconnect/Crash-Detection Recovery — Design Spec
**Date:** 2026-07-18
**Status:** DESIGN ONLY — not implemented. Companion to
`journals/TUTORIAL_ROUTINE_LIVE_TEST_2026-07-18.md` recommendation #3 ("False-positive crash
detection... lacks a relogin/recovery path").

## Summary

The routine engine's crash detector uses **state-file mtime age as its only signal**. A
disconnect (or the login/char-creation screen) makes the state file stop updating for a
legitimate, expected reason — not because the client crashed — so the detector misreports it as
a crash. The fix does **not** need a plugin change: the plugin already exposes a `GET_GAME_STATE`
command that reports live connection status over the same command channel the engine already
uses for every other command. The whole fix is a Python-side change: query that command instead
of (or before) trusting file-mtime staleness, and reuse the relogin/restart primitives that
already exist in `monitoring.py` and `runelite_manager.py` but aren't wired into the routine
execution loop.

---

## (a) Root cause of the false positive

**Detector code** — `mcptools/tools/routine.py`:

- `check_client_health()` (routine.py:1708-1746): the *only* thing it checks is
  `os.stat(state_file)` mtime age vs. `max_stale_seconds`:
  ```python
  age_seconds = time.time() - stat.st_mtime
  if age_seconds > max_stale_seconds:
      return {"alive": False, ..., "error": f"State file stale for {age_seconds:.0f}s ... client likely crashed"}
  ```
  Called from the execution loop at routine.py:1140 (start of each outer loop, `max_stale_seconds=60`)
  and routine.py:1200 (every `health_check_interval=5` steps, routine.py:1128, same 60s threshold).
  On failure it sets `results["crash_detected"] = True` (routine.py:1151, 1211) and either retries
  via `_auto_restart_client()` or aborts the routine.

- `monitoring.py`'s `_is_disconnected()` (monitoring.py:775-805) has the identical weakness at a
  lower threshold (10s): mtime age, plus a secondary check that `player.location.x/y` exist in the
  last-written JSON. Neither function ever asks the client "are you actually connected right now?"
  — both only look at how old the *last* snapshot is.

**Why staleness happens on disconnect (and is not itself a bug):** the plugin's state file writer —
`StateExporter.onGameTick()` in `manny_src/utility/GameEngine.java:5369-5422` — is driven purely by
RuneLite's `GameTick` event (subscribed unconditionally in `manny_src/MannyPlugin.java:1241-1251`,
no `GameState` guard). `StateExporter` itself has no game-state gate either — `running` is only
flipped by plugin `startUp()`/`shutDown()` (`MannyPlugin.java:482`, `552`), and even
`buildPlayerState()` writes an empty-but-valid `PlayerState` when `client.getLocalPlayer() ==
null` (`GameEngine.java:5743-5747`) rather than aborting the write.

What *does* gate the write is whether `GameTick` fires at all. RuneLite's engine posts `GAME_TICK`
from `serverTick()` (`runelite/runelite-client/.../callback/Hooks.java:227-239, 532-536`), i.e. it
is driven by ticks the game **server** sends the client — which requires an active world
connection. During `CONNECTION_LOST`/`LOGIN_SCREEN`/character-creation-pre-confirm there is no
server tick stream, so (most likely — see caveat below) `GameTick` stops firing and the state file
legitimately freezes at its last in-world snapshot. This matches the live test exactly: the
account was disconnected, its last live snapshot was Section 01 (character creation, appearance
not set), and that stale snapshot sat there looking like "no progress since step 5" once the
`check_client_health()` staleness clock ran out. `journals/TUTORIAL_ROUTINE_LIVE_TEST_2026-07-18.md`
line 91-98: `"Client crash at step 5 ... No runelite_manager available, cannot restart"` — the
trigger was exactly this stale-but-legitimate snapshot.

*Caveat:* `manny_src/utility/CombatSystem.java:1427` has a defensive
`if (client.getGameState() != GameState.LOGGED_IN) return;` guard inside its own `onGameTick()`
(called from the same dispatcher as `StateExporter.onGameTick()`), which is *some* evidence
`GameTick` can fire in non-`LOGGED_IN` states (e.g. `LOADING`, a still-connected sub-state) even if
it doesn't during a genuine `CONNECTION_LOST`. The exact mechanical trigger for the staleness isn't
100% nailed down from static reading alone — see the test plan (e) for the live check. It doesn't
change the fix design below, which treats file staleness as *never* authoritative on its own.

**Compounding bug — recovery path unreachable from the CLI entrypoint actually used:**
`_auto_restart_client()` (routine.py:1754-1792) is fully implemented and correctly calls
`runelite_manager.stop_instance`/`start_instance`. But `run_routine.py:125-127` (the script the
live test invoked directly) wires dependencies as:
```python
commands.set_dependencies(send_cmd, config)
monitoring.set_dependencies(None, config)
routine.set_dependencies(send_cmd, config)          # <-- only 2 args
```
`routine.set_dependencies(send_command_func, server_config, manager=None)` (routine.py:25) defaults
`manager` to `None` when not passed, so `routine.runelite_manager` stays `None` for the entire CLI
run, and `_auto_restart_client()`'s first line (routine.py:1760-1762) always short-circuits:
```python
if runelite_manager is None:
    _routine_logger.warning("[AUTO-RESTART] No runelite_manager available, cannot restart")
    return False
```
Compare `server.py:95`: `routine.set_dependencies(send_command_with_response, config,
runelite_manager)` — correctly wired 3-arg call. This is a one-line CLI-wiring gap, not a missing
capability, and should be fixed regardless of the discriminator work below.

---

## (b) Discriminator design: disconnect vs. genuinely stuck

**Doable in pure Python, right now, no plugin change required.** The plugin already has the
discriminator built and reachable over the existing command channel:

`manny_src/utility/commands/GetGameStateCommand.java:22-108` — the `GET_GAME_STATE` command reads
`client.getGameState()` via `helper.readFromClientSafe()` (a `ClientThread` round-trip, not gated
by `GameTick`/world-tick — the render/client thread keeps running at the login screen) and returns:

```java
info.put("gameState", gameState.toString());        // raw RuneLite enum, e.g. "LOGIN_SCREEN"
info.put("status", status);                          // "LOGGED_IN" | "LOGGING_IN" | "DISCONNECTED" | "UNKNOWN"
info.put("isConnected", isConnected);
info.put("canSendCommands", canSendCommands);         // false unless status=="LOGGED_IN" AND localPlayer != null
info.put("hasLocalPlayer", localPlayer != null);
```
(switch mapping at GetGameStateCommand.java:58-87: `LOGGED_IN`/`LOADING` → `LOGGED_IN`;
`LOGIN_SCREEN`/`LOGIN_SCREEN_AUTHENTICATOR`/`LOGGING_IN` → `LOGGING_IN`;
`CONNECTION_LOST`/`HOPPING` → `DISCONNECTED`; anything else → `UNKNOWN`.)

The response goes through the normal `ResponseWriter` IPC (`/tmp/manny_response.json`, or
per-account), the exact same channel `execute_simple_command()`/`send_command_with_response()` in
routine.py already use for every other command — no new transport needed.

**Discriminator logic** (replaces the mtime-only checks in both `check_client_health()` and
`_is_disconnected()`):

1. Send `GET_GAME_STATE` with a short timeout (e.g. 5s).
2. If it **responds**:
   - `status == "LOGGED_IN"` and `canSendCommands == true`, but state file is still stale beyond
     threshold → **genuine freeze** (world connection is fine, but something in the plugin/game
     loop is hung) → crash/restart path.
   - `status in {"LOGGING_IN", "DISCONNECTED"}` → **disconnect, not a crash** → relogin path, do
     **not** treat as a crash, do **not** count against restart-attempt budgets meant for real
     crashes.
   - `status == "UNKNOWN"` → treat conservatively as disconnect-first (attempt relogin), escalate
     to restart only if relogin doesn't resolve it.
3. If it **times out / no response at all** → the command-processing channel itself is dead → this
   is the actual "client crashed" case → restart path (this is the one case plain mtime staleness
   correctly implies "dead", so it remains a valid fallback signal when the command channel itself
   doesn't answer).

This makes state-file mtime staleness a **secondary/confirming** signal only, never sufficient by
itself to declare "crash" — exactly closing the gap the journal flagged.

**State-file field = Java/post-refactor, optional, not required for the fix.** A `connection`
block could be added to `MannyState`/`buildState()` (`GameEngine.java:6148-6160`,
`5506-5519`) mirroring `GetGameStateCommand`'s switch, e.g. `state.connection =
buildConnectionState();`. Benefits: removes the extra `GET_GAME_STATE` round trip for passive
polling, and gives a signal even if command IPC also stalls. Cost: touches `GameEngine.java` /
`MannyPlugin.java`, which are mid-refactor right now (`journals/2026-07-18_progress.md`,
`journals/REFACTOR_CAMPAIGN_HANDOFF.md` — J2-5..J2-8 splits are in flight on `PlayerHelpers`, and
`GameEngine.java`'s `StateExporter` is exactly the kind of monolith code the campaign is
extracting). **Recommendation: defer this to after the refactor lands** — the Python-only
`GET_GAME_STATE`-based discriminator above is fully sufficient today and doesn't conflict with or
block the concurrent Java work.

---

## (c) Recovery-path design

Reuse what already exists; don't add a third mechanism.

**Existing pieces (already built, just not wired into the routine loop):**

- `manny_src/utility/PlayerHelpers.java:7815-7822` — the `LOGIN` command, already dispatchable via
  `send_command("LOGIN")`: resets and clicks the Play/login button
  (`loginHandlers.getLoginButtonClicker().clickPlayButton()`). This is exactly what the live-test
  operator did by hand (`journals/TUTORIAL_ROUTINE_LIVE_TEST_2026-07-18.md` line 27: `CLICK_AT 383
  301` to dismiss the disconnect "Ok" dialog, then `LOGIN`).
- `mcptools/tools/monitoring.py:854-1088` — `auto_reconnect` (registered MCP tool
  `handle_disconnection`... entry at monitoring.py:854): already implements exactly this recipe —
  click the disconnect-dialog "Ok" button via `_xdotool_click()` (documented coordinates,
  monitoring.py:809-826), poll `_is_disconnected()` until reconnected, and only escalate to a full
  `runelite_manager.stop_instance`/`start_instance` restart if reconnection doesn't happen within
  `max_wait_seconds` (default 60, monitoring.py:869-872). It even has its own freeze-vs-disconnect
  split (`plugin_frozen = state_age > freeze_threshold_seconds`, default 60, monitoring.py:908-972).
- `mcptools/tools/monitoring.py:1090-1203` — `restart_if_frozen`: staleness-gated restart, same
  `runelite_manager` calls.
- `mcptools/runelite_manager.py` — `start_instance`/`stop_instance`: the one Python-native client
  lifecycle implementation already used by `_auto_restart_client()` (routine.py) and by
  `auto_reconnect`/`restart_if_frozen` (monitoring.py). Credentials via
  `~/.runelite/credentials.properties` (refresh/access token flow, `runelite_manager.py:549-617`).
- `scripts/client.sh` — a **separate**, ops-focused, thermal-guarded bash implementation
  (`pgrep -x java` + `/proc/<pid>/environ` detection, `JX_CHARACTER_ID`/`JX_SESSION_ID` env-based
  launch, 88C/80C thermal refuse/warn gates, `LOGIN_WAIT_SECS=30` wait for `Game state is now
  LOGGED_IN` in the log). It does **not** share code with `runelite_manager.py` — different
  credential mechanism, different process-detection strategy, invoked from the shell, not
  in-process. It was added for manual/ops use (gate testing, thermal safety), not for the engine's
  internal recovery loop.

**Gap today:** none of `auto_reconnect`/`restart_if_frozen`/`GET_GAME_STATE` are called from
`routine.py`'s execution loop (routine.py:1140, 1200) or from `_auto_restart_client()`. They're
reachable only as standalone MCP tools an agent has to invoke by hand — which is precisely why the
live test's unattended run hit "No runelite_manager available, cannot restart" and stalled instead
of self-healing.

**Design — wire a relogin-first branch into the two existing health-check call sites:**

```
health check (routine.py:1140 / 1200)
  -> query GET_GAME_STATE (new: _get_connection_status(), see (b))
       responded, status == LOGGED_IN, canSendCommands, but state file stale beyond threshold:
           -> genuine freeze -> existing _auto_restart_client() path (unchanged)
       responded, status in {LOGGING_IN, DISCONNECTED, UNKNOWN}:
           -> NEW: relogin path
                1. _xdotool_click() the disconnect "Ok" button (reuse monitoring.py:828-851,
                   coordinates monitoring.py:813-816)
                2. send_command("LOGIN")  (reuse the existing plugin command, PlayerHelpers.java:7815)
                3. poll GET_GAME_STATE (or _is_disconnected()) until status == LOGGED_IN /
                   canSendCommands, up to a bounded wait (mirror auto_reconnect's default 60s,
                   monitoring.py:869-872)
                4. if still not recovered after the wait -> escalate to _auto_restart_client()
                   (full relaunch via runelite_manager, same as the freeze path)
       no response at all (command channel dead):
           -> _auto_restart_client() path (unchanged) -- this is the one case mtime staleness
              alone is still a valid enough signal
```

In effect: fold `monitoring.py`'s `auto_reconnect` logic *into* (or call it from)
`_auto_restart_client()`'s decision point, rather than leaving it as a tool nobody calls
automatically. `scripts/client.sh` is not part of this path — it stays what it already is, a
manual ops helper — since `runelite_manager` is the mechanism already integrated in-process and
already reused by three call sites (routine.py, monitoring.py, quests.py per server.py:100).
Introducing `client.sh` as a fourth, subprocess-based relaunch path here would fragment recovery
logic further, which is exactly the kind of tool sprawl flagged in
`project_manny_click_tool_sprawl.md`.

**Resuming the routine after recovery:** routine.py's step loop already has the scaffolding —
on a successful freeze-restart it `continue`s the outer loop (routine.py:1147-1149) or `break`s
back into the same `current_step_idx` (routine.py:1206-1209). The relogin branch should do the
same, but **without** resetting `current_step_idx` on the relogin (non-restart) path, since the
character's in-world position/inventory is unaffected by a mere relogin — the routine should
simply retry the step it was on. A full restart (relaunch) *should* still resume at
`current_step_idx` too (that's what today's code already does), but it's worth a defensive
`GOTO`/state re-sync at the top of the resumed step for routines that assume a specific position,
per fix #2 in the live-test journal (recommendation to add a `GOTO` at section-start for exactly
this kind of re-entry).

---

## (d) Split: doable NOW (Python) vs. needs Java (post-refactor)

**NOW, pure Python, zero plugin edits, zero client changes:**
1. Fix `run_routine.py:127` to pass `runelite_manager` as the 3rd arg to
   `routine.set_dependencies()` (mirror server.py:95) — closes the "No runelite_manager available"
   gap outright.
2. Add a `_get_connection_status(account_id)` helper (routine.py, near `check_client_health`) that
   sends `GET_GAME_STATE` via the existing `execute_simple_command()`/`send_command_with_response`
   plumbing and returns the parsed `status`/`canSendCommands`/`isConnected`.
3. Rewrite `check_client_health()` (routine.py:1708-1746) and `_is_disconnected()`
   (monitoring.py:775-805) to consult `_get_connection_status()` first, falling back to mtime
   staleness only when the command itself doesn't respond (per (b)/(c) above).
4. Add the relogin branch (disconnect-dialog click + `LOGIN` command + bounded poll, escalate to
   `_auto_restart_client()` on timeout) at routine.py's two health-check call sites
   (routine.py:1140-1155, 1200-1215), reusing `monitoring.py`'s `_xdotool_click()` /
   `auto_reconnect` logic rather than reimplementing it.
5. Ensure the relogin branch doesn't reset `current_step_idx` (restart branch keeps its current
   behavior).

**Java / post-refactor (optional, not blocking):**
1. Add a `connection` field to `MannyState`/`buildState()` (`GameEngine.java:6148-6160`,
   `5506-5519`), populated from the same switch already written in
   `GetGameStateCommand.java:58-87`, so the *passive* state file itself carries the discriminator
   (saves the extra `GET_GAME_STATE` round trip on every health check).
2. (Separately requested, `journals/TUTORIAL_ROUTINE_LIVE_TEST_2026-07-18.md` recommendation #4,
   not part of this spec) a `tutorial_progress` varbit field for chain `progress_hint` gating —
   unrelated to disconnect detection but the same insertion point (`buildState()`), worth batching
   together if/when this Java work happens.

---

## (e) Test plan

**Mock/offline-testable now (no live client, machine stays cold):**

- `check_client_health()`/new `_get_connection_status()` unit tests: monkeypatch
  `send_command_with_response`/`execute_simple_command` to return canned `GET_GAME_STATE` payloads
  for each `status` value (`LOGGED_IN`, `LOGGING_IN`, `DISCONNECTED`, `UNKNOWN`, and a timeout/no-
  response case), crossed with fresh vs. stale state-file mtimes (`os.utime()` on a temp file).
  Assert the classification (`healthy` / `disconnect-recover` / `crash-restart`) is correct for
  all combinations — this is the core regression guard for the false-positive bug. Follows the
  existing pattern in `tests/test_bugfixes_2026_07_18.py`.
- Dependency-wiring regression test: assert `run_routine.py`'s setup ends with
  `routine.runelite_manager is not None` (or grep-assert every `routine.set_dependencies(...)`
  call site passes 3 args) — a one-line static guard against the exact CLI-wiring bug found here
  reappearing.
- Recovery branch-selection unit test: mock `_xdotool_click`, `send_command("LOGIN")`, and
  `runelite_manager.start_instance`/`stop_instance`; feed a scripted status sequence
  (`DISCONNECTED` → still `DISCONNECTED` after simulated timeout) and assert escalation to restart
  only happens after the bounded wait, never immediately.
- `current_step_idx` preservation test: assert the relogin branch does not mutate
  `current_step_idx`, distinct from the restart branch's existing (and unchanged) behavior.

**Needs a live disconnect to verify (explicitly deferred — no client launch during this task, per
thermal/heat constraint):**

- End-to-end: force a real disconnect mid-routine on a throwaway account and confirm (1) the
  engine does **not** log a false crash while `GET_GAME_STATE` reports `LOGGING_IN`/`DISCONNECTED`,
  (2) the OK-dialog click + `LOGIN` sequence resumes the same routine step without a full relaunch,
  (3) restart is only triggered if relogin doesn't recover within the bounded wait.
- Confirm the disconnect-dialog OK-button coordinates (monitoring.py:813-816, center ~(770,604))
  are still accurate on the current `client-1.12.34-SNAPSHOT-shaded.jar` / `uiScale=2.0`.
- Resolve the (e)-noted caveat from (a): empirically confirm whether `GameTick`/state-file writes
  actually stop during `CONNECTION_LOST` vs. merely slow to the ~6s heartbeat — doesn't change the
  fix's design (GET_GAME_STATE is authoritative either way) but would sharpen the "genuine freeze"
  threshold tuning.
- Confirm `GET_GAME_STATE`'s `canSendCommands`/`hasLocalPlayer` correctly distinguish the exact
  symptom from the live test: char-creation-screen-after-disconnect (should read
  `LOGGING_IN`/`DISCONNECTED`, not `LOGGED_IN`) vs. a genuine mid-routine stall while fully logged
  in (should read `LOGGED_IN`, `canSendCommands: true`).

---

## File:line index

| Component | File:line |
|---|---|
| `check_client_health()` (mtime-only) | `mcptools/tools/routine.py:1708-1746` |
| Health-check call sites in exec loop | `mcptools/tools/routine.py:1140`, `:1200` |
| `_auto_restart_client()` | `mcptools/tools/routine.py:1754-1792` |
| `routine.set_dependencies()` default `manager=None` | `mcptools/tools/routine.py:25` |
| CLI wiring gap (2-arg call) | `run_routine.py:127` |
| Correct 3-arg wiring (reference) | `server.py:95` |
| `_is_disconnected()` (mtime-only) | `mcptools/tools/monitoring.py:775-805` |
| `auto_reconnect` tool | `mcptools/tools/monitoring.py:854-1088` |
| `restart_if_frozen` tool | `mcptools/tools/monitoring.py:1090-1203` |
| Disconnect-dialog click coords + `_xdotool_click()` | `mcptools/tools/monitoring.py:809-851` |
| `GET_GAME_STATE` command (discriminator) | `manny_src/utility/commands/GetGameStateCommand.java:22-108` |
| `LOGIN` command (relogin primitive) | `manny_src/utility/PlayerHelpers.java:7815-7822` |
| `StateExporter.onGameTick()` (state-file writer) | `manny_src/utility/GameEngine.java:5369-5422` |
| `MannyState` schema (no connection field) | `manny_src/utility/GameEngine.java:6148-6160` |
| `buildState()` (insertion point for future field) | `manny_src/utility/GameEngine.java:5506-5519` |
| `runelite_manager.start_instance`/`stop_instance` | `mcptools/runelite_manager.py:620-, 750-` |
| `scripts/client.sh` (separate ops path, not reused here) | `scripts/client.sh` |
