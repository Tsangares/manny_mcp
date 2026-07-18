# Manny Refactor Campaign — Live Handoff (for post-compaction continuation)

**Last updated:** 2026-07-17, mid-Wave-3. Author: Claude (orchestrator).
**Canonical plan:** `/home/wil/.claude/plans/can-you-search-around-giggly-globe.md`
**Architecture review (the "why"):** `manny_mcp/journals/architecture_review_2026-07-17.md`

This doc = "what to do next." Read the plan file for full wave detail; read this for
current position, operational commands, and decisions made mid-flight.

---

## WHERE WE ARE

| Wave | Status | Notes |
|---|---|---|
| 0 Baseline & hygiene | ✅ DONE, pushed | 16 backups deleted, ruff/pytest wired, stale paths fixed, smoke harness built |
| 1 Phase-0 bug fixes | ✅ DONE, pushed | 9 fixes; live smoke 5/5. Watchdog un-inverted, get_logs revived, KILL/STOP fixed |
| 2 Transport & paths | ✅ DONE, pushed | MannyPaths (Java), transport.py (Python), read-only lane. Non-preemption proven live |
| 3 Registry + interrupts | ✅ DONE, pushed | 3a registry; 3b `2f916a9` (23 handlers); 3c `1e747c5` (interrupt system + 5 skilling loops + KILL-flag-preservation fix). Live-gated: KILL aborts WAIT in ~0.5s AND a detached cmdlog sleepChecked loop within 200ms |
| 4 Dedup & consolidation | 🔄 IN PROGRESS | Phase A (3 sonnet agents, parallel, no PlayerHelpers): GE dedup→GeWidgetSupport, GameEngine self-copy deletion, Keyboard/Mouse/login fixes. Phase B (sequential, opus, after A): InteractionSystem click authority, banking-helper extraction + 12 stateful handler migration, ListCommandsCommand from registry |
| 5 Python modernization | ⬜ pending | tool pruning 105→40, de-async-block, latch migration, deps split |

**MCP decision (2026-07-17, user-confirmed):** KEEP the MCP server but prune hard (~25-40 thin
tools over transport.py). Rationale: Claude Code sessions do NOT need MCP — they drive the bot via
direct file IPC with Bash (as this whole campaign has); no need to restart sessions in manny_mcp/
to load the server. MCP is kept only as optionality for non-terminal clients (claude.ai app/phone,
desktop). Direct IPC is the documented PRIMARY interface; Wave 7's CLAUDE.md regeneration must say
this explicitly.
| 6 Phase 3 core | ⬜ pending | Actions retirement, PlayerHelpers split, driver control-plane |
| 7 Docs + final verify | ⬜ pending | regenerate both CLAUDE.md from reality; testing phase after |

**Task board:** tasks #1-8 map to Waves 0-7. Update as waves complete.

---

## WAVE 4 IN-FLIGHT DETAIL (resume here)

Wave 3 finished 2026-07-17 evening (`1e747c5`). Key 3c facts for later waves:
- CommandBase now has `checkInterrupt()`/`sleepChecked(ms)`/`isInterruptRequested()`; the
  processor wires `setInterruptSupplier(() -> shouldInterrupt)` on every `register(...)`.
- **KILL-flag preservation fix (mine, found during the live gate):** `executeCommand`'s finally
  block no longer clears `shouldInterrupt` when the completing command is KILL/STOP/
  EMERGENCY_STOP — previously the flag KILL set survived only milliseconds, so detached loops
  (cmdlog executor thread) polling via sleepChecked NEVER saw it. Pre-dispatch reset in
  processCommands() still makes each new command start clean. Do not "simplify" this away.
- GEBuy/GESlowBuy setQuantity/adjustPrice had empty `catch (InterruptedException) {}` loops —
  fixed (restore interrupt, writeFailure("Interrupted"), return false).
- Some pre-3c command classes still carry their own vestigial `private volatile boolean
  shouldInterrupt` fields (ChopTree, Fish, FishDraynorLoop, LoadCmdlog) — dead weight, clean up
  opportunistically in Wave 4/6.
- `GeWidgetSupport` had raw sleep loops (not a CommandBase) → assigned to the Wave-4 GE agent.
- Orphans left by 3c: `PlayerHelpers.dropAllItems(int)` (public, callers deleted);
  `handleDropAll`/`handleMineOre` KEPT (still called by retained handleKillLoop/
  cookRawMeatRoutine/handleAtMine — dissolve in Wave 4 with the 12 stateful handlers).
- Live KILL gate recipe (reusable): `LOAD_CMDLOG <file>` with a `60000 PING` line in
  `~/osrs_scenarios/<file>.cmdlog`, KILL 4s later → expect "Cmdlog execution interrupted during
  delay" within ~200ms. Plus WAIT 30000 + KILL → "sleep interrupted" failure in <1s.

**Wave 4 running now** — Phase A dispatched (3 parallel sonnet agents, none touch
PlayerHelpers/MannyPlugin):
1. ✅ GE agent DONE: findWidgetWithAction 4 copies + isGEOpen 4 copies → static canonical
   methods on GeWidgetSupport (static because GEOpenCommand ctor is called from PlayerHelpers
   with no Mouse); clickWidget gained BooleanSupplier shouldAbort overload (wired
   this::isInterruptRequested in GECancel/GEConfirm — new cooperative cancel); GeWidgetSupport
   helpers no longer swallow InterruptedException (restore+return); 5 latch sites →
   readFromClient in GEBuy/GESell. Behavior notes: GECollect/GEAbort now use the richer
   Buy/Sell matching variant (color-tag strip, bounds check). LEFT for Phase B (ctors called
   from PlayerHelpers, couldn't add ClientThreadHelper): 12 raw latches across GESlowBuy(6)/
   GEAbort(2)/GECollect/GEClickSlot/GESellItem/GESelectItem. Pre-existing bug flagged:
   GESlowBuyCommand.clickQuantityButton/collectItems are empty stubs. Build green ×2.
2. ✅ GameEngine agent DONE: ResourceFinder + BankingHelper were 100% DEAD CODE (getters never
   called) — deleted entirely, 1,285 lines (10,895→9,610), zero call-site changes, build green ×2.
   Write-method manifest persisted to `manny/docs/GAMEENGINE_WRITE_MANIFEST.md` (Phase B input:
   5 banking clickers + waitForBankOpen → PlayerHelpers, 8 TabSwitcher methods → InteractionSystem,
   4 SkillingHelper item-use methods → PlayerHelpers). Deferred: ActivityStatistics/
   FarmingStatsTracker ~340-line twin left alone (log-text differs = behavioral; Wave 6 candidate).
3. ✅ Input agent DONE: Keyboard.type() — 9 wrong keycodes fixed (worst: `~`→VK_TAB and
   `` ` ``→VK_ENTER were typing control chars; `@#$&_?!` all off-by-one-row) + 9 unhandled
   symbols added (`^*+{}:"<>`— previously NPE'd via null AWTKeyStroke); unshifted `'` still
   NPEs, flagged not fixed. Mouse: @Slf4j, 18 printlns→log.debug/warn, click()/shiftClick()
   RNG routed through injected field, 3c replay() fixes preserved. LoginHandlers: Login/
   TryAgainButtonClicker now widget-first (widget 24772680 = WELCOME_SCREEN 378:40 — an
   INFERENCE from the deprecated LOGIN_CLICK_TO_PLAY alias, NOT live-verified; null widget
   falls through to coordinate fallback, now scaled from 765×503). Build green.
   → GATE MUST VERIFY AUTO-LOGIN END-TO-END (watch which path logs: widget or fallback).
**Phase A GATED + COMMITTED as `fa96e09` "Wave 4a"** (net −1,415 lines): compile+shadowJar
green, relaunch on :2, auto-login end-to-end LOGGED_IN in 12s (took the SCALED COORDINATE
FALLBACK — "Play button widget not found or hidden" — so the widget-ID 24772680 inference is
unconfirmed for the login screen; fallback = old behavior at 765×503, works), smoke 5/5.
Launch-recipe correction learned during the gate: creds API is
`from mcptools.credentials import credential_manager; credential_manager.get_account('new')`
with keys `jx_character_id`/`jx_session_id` (NOT mcptools.credentials.credential_manager
module / character_id keys — that silent failure cost a relaunch cycle).

**Phase B split in two sequential opus agents (both single-writer on PlayerHelpers):**
- 🔄 B1 DISPATCHED (~17:50): (1) InteractionSystem single click authority — clickMenuEntrySafe/
  smartClick moved in, setPlayerHelpers back-ref killed, CombatSystem.clickNPC/verifyAndClickNPC
  retired, 3× clickbox-shrink tracker deduped; (2) apply docs/GAMEENGINE_WRITE_MANIFEST.md
  (TabSwitcher→InteractionSystem, banking clickers→NEW utility/BankingSupport.java,
  SkillingHelper item-use→PlayerHelpers or ItemUseSupport); (3) extract shared handler helpers
  (handleBankOpen/Close/Deposit/Withdraw→BankingSupport, handleGotoCommand/handleSmeltBar/
  handleBuryItem→support classes; inline handlers become thin wrappers, still work);
  (4) finish GE latch conversion (add ClientThreadHelper to 6 GE ctors in PlayerHelpers,
  12 raw latches→readFromClient); (5) delete vestigial shouldInterrupt fields (ChopTree/Fish/
  FishDraynorLoop/LoadCmdlog). Compile gate only; no commit; MannyPlugin locked.
- ✅ B1 GATED + COMMITTED as `b065e9a` "Wave 4b": BankingSupport.java NEW (bank clickers out of
  GameEngine; handleBankOpen/Close/DepositAll now thin wrappers); TabSwitcher 8 write methods →
  InteractionSystem (reads stay; TAB_OPEN fails gracefully at char-creator screen — game-state,
  widgets absent, NOT a regression); SkillingHelper write dupes deleted (PlayerHelpers canonical);
  all 12 GE latches → readFromClient (ClientThreadHelper added to 6 GE ctors; NOTE: 2s→5s +
  throw-on-timeout semantics change; GEAbort.findAbortButton kept its 13th latch, not in scope);
  clickbox-shrink 3× → one param'd helper; vestigial fields gone. DEFERRED TO WAVE 6 (agent
  findings): clickMenuEntrySafe/smartClick cluster CANNOT move piecemeal (fed by locked
  MannyPlugin.onMenuOptionClicked:1130 state + strongly connected to staying clickTarget/
  moveMouse/smartMove) — move as a unit in the W6 split; CombatSystem.clickNPC/verifyAndClickNPC
  retirement (feasible verbatim move, needs InteractionSystem in CombatSystem ctor);
  setPlayerHelpers back-ref CANNOT be removed (used for findAndPrepareGameObjectPublic/
  gotoPositionSafe, non-click); handleBankWithdraw/DepositItem/handleGotoCommand/handleSmeltBar/
  handleBuryItem full extraction also deferred.
- 🔄 B2 DISPATCHED (~18:30, opus): migrate the 12 stateful handlers (#11 TELEPORT,
  #12 TELEGRAB_WINE_LOOP, #15 BURY_ALL, #17 KILL_LOOP, #18 KILL_LOOP_CONFIG, #19 KILL_COW,
  #20 KILL_COW_GET_HIDES, #21 IMP_HUNT, #24 COLLECT_LUMBRIDGE_TIN_COPPER, #29 SMELT_BRONZE_BARS,
  #30 SMELT_BAR, #31 BUY_GE) — ACCESS RULE: shared helpers (handleGotoCommand etc.) made PUBLIC
  on PlayerHelpers + injected, NOT extracted (extraction = Wave 6); dissolve handleDropAll/
  handleMineOre/cookRawMeatRoutine/dropAllItems(int) orphans if callers gone; LIST_COMMANDS from
  commandRegistry.keySet() + legacy-switch remainder.
Gate per phase: compile+shadowJar → relaunch on :2 → smoke 5/5 → auto-login check → commit+push.
SIDE TASK ✅ 2026-07-17: new Bolt account cached — alias `newbakshesh` (OSRS char NewBakshesh,
Jagex login backsheesh#7282) added to ~/.manny/credentials.yaml alongside main/new (default
still `new`). Bolt flatpak cred sources: session list at
~/.var/app/com.adamcake.Bolt/data/bolt-launcher/creds, selected-account mapping in
.../config/bolt-launcher/launcher.json, char display names in .../data/bolt-launcher/.runelite/
profiles2/$rsprofile--1.properties. JX_CHARACTER_ID (not session_id) is the per-character
discriminator. Tokens rotate — if login fails, relaunch via Bolt once or re-import.

## WAVE 3 DETAIL (historical)

Wave 3 was split into sub-phases because it's the riskiest (all on PlayerHelpers.java, single-writer):

- **3a ✅ committed** (`manny` commit "Wave 3a: command registry"): built `commandRegistry`
  `Map<String,CommandBase>` in `PlayerHelpers$CommandProcessor`, moved 84 class-based switch
  cases into it via explicit `register("NAME", field)`, deleted dead `utility/CommandProcessor.java`
  stub, wrote `manny/docs/INLINE_HANDLER_MANIFEST.md` (all 40 remaining inline handlers).
  Registry dispatch verified live (GET_GAME_STATE/QUERY_NPCS via registry, PING via switch → all success).
- **3b ✅ DONE, pushed** (`manny` commit `2f916a9`): 23 simple handlers → `utility/commands/`
  classes + 2 shared helpers (SpellWidgetHelper, GeWidgetSupport); 23 cases removed, 17 inline
  methods deleted, 6 KEPT (still called by retained handlers `handleTeleport`/`handleKillLoop`/
  `handleImpHunt`/`handleTelegrabWineLoop`/cookRawMeatRoutine — they dissolve in Wave 4).
  Bonus fixes: DUMP_COLLISION off-client-thread getWorldLocation (pre-existing, copied verbatim,
  now fixed in the new class); MannyPlugin startup log now prints MannyPaths truthfully.
- **3c 🔄 AGENT RUNNING** (opus, dispatched 2026-07-17 ~17:05): CommandBase gets
  `checkInterrupt()`/`sleepChecked()` + BooleanSupplier setter wired in `register(...)`;
  Mouse.replay() InterruptedException + hz=0 fixes; sleepChecked adoption in ~17 sleep-loop
  command classes; migrate 5 skilling handlers (#14 DROP_ALL, #22 POWER_MINE, #23 MINE_ORE,
  #25 FISH_DROP, #26 POWER_CHOP). Agent runs its own compile gate; does NOT commit.
  → When it returns: shadowJar, relaunch (Xvfb :2!), live gate: start POWER_MINE or WAIT-loop,
    send KILL mid-flight → must abort promptly with "Interrupted" failure response; smoke 5/5;
    commit "Wave 3c" + push. Wave 3 then DONE.
- **ALSO IN FLIGHT**: opus agent researching game-viewing (report → docs/GAME_VIEWING_OPTIONS.md,
  zero-install MJPEG prototype on :8787, tailscale-based remote view; taxi=100.83.247.91).
- **Wave 6 addition (proposed 2026-07-17)**: append-only `manny_<acct>_events.jsonl` push channel
  (plugin writes command lifecycle + game events; fixes single-slot response overwrite + no-push).

### DECISION MADE MID-WAVE (important, propagate to plan):
The manifest's 40 inline handlers were split by risk, NOT migrated all-at-once:
- 23 simple → Wave 3b (in progress)
- 5 skilling loops (only `shouldInterrupt`) → Wave 3c (with interrupts)
- **12 stateful/cross-calling → DEFERRED TO WAVE 4** (#11,12,15,17,18,19,20,21,24,29,30,31:
  TELEPORT, TELEGRAB_WINE_LOOP, BURY_ALL, KILL_LOOP, KILL_LOOP_CONFIG, KILL_COW,
  KILL_COW_GET_HIDES, IMP_HUNT, COLLECT_LUMBRIDGE_TIN_COPPER, SMELT_BRONZE_BARS, SMELT_BAR, BUY_GE).
  Reason: they depend on shared private helpers (`handleBankOpen`, `handleGotoCommand`,
  `handleSmeltBar`, `handleBuryItem`) that Wave 4 extracts into GEInterfaceHelper / banking
  helpers anyway. Migrating them there converts cleanly instead of dangerously. Same end-state
  (single command generation), better dependency order.
→ Wave 4 scope now also includes: extract shared banking/GE helpers into proper classes, THEN
  migrate these 12 handlers onto them. Add this to Wave 4's agent prompts.

---

## OPERATIONAL RUNBOOK (exact commands — reuse verbatim)

### Build gate (after every Java wave)
```
cd /home/wil/Desktop/runelite && ./gradlew :client:compileJava -x checkstyleMain -x pmdMain --console=plain 2>&1 | grep -E 'error:|BUILD'
# then full jar:
./gradlew :client:shadowJar -x checkstyleMain -x pmdMain --console=plain 2>&1 | grep -E 'error:|BUILD'
```
JDK 21 pinned via `~/.gradle/gradle.properties` (org.gradle.java.home=/usr/lib/jvm/java-21-openjdk).
System default is JDK 26 which BREAKS gradle 8.8 — do not change it.

### Launch the client (CLEAN — avoid the pkill-in-compound-command trap, exit 144)
**Client runs on Xvfb :2 as of 2026-07-17 (user-requested input isolation).** Mouse/Keyboard
dispatch synthetic AWT events to the canvas (no Robot), so ANY X server works headless; Xvfb
isolates the window from the user's Wayland desktop (no focus stealing, no real-cursor
interference). Ensure Xvfb is up first (check with `ps -eo pid,comm | awk '$2=="Xvfb"'` —
pgrep/pkill match your own bash wrapper, don't use them):
```
setsid Xvfb :2 -screen 0 1600x1000x24 > /tmp/xvfb2.log 2>&1 < /dev/null &
```
Screenshots: `DISPLAY=:2 import -window root /path/out.png` (ImageMagick). Live view for the
user: install x11vnc (not yet installed). NOTE: no WM on :2 — RuneLite places itself at its
remembered position (bottom-right); harmless for canvas-dispatch clicks.
**GPU plugin is DISABLED** (was rendering via llvmpipe on Xvfb → 374% CPU / hot laptop; CPU
renderer + fps cap 30 → ~46% CPU). Set in `~/.runelite/profiles2/default-7785192106142.properties`:
`runelite.gpuplugin=false`, `fpscontrol.limitFps=true`, `fpscontrol.maxFps=30`,
`fpscontrol.drawFps=false` (backup: same path `.bak-gpu`). Do NOT re-enable GPU plugin while on
Xvfb. If GPU-accelerated + isolated is ever wanted: rootful Xwayland (`Xwayland :2 -geometry ...`)
gets real GPU via the GNOME compositor, or VirtualGL EGL backend.

Do kill and launch as SEPARATE Bash calls. To launch (DISPLAY=:2 now, NOT :0):
```
creds=$(/home/wil/Desktop/manny_mcp/venv/bin/python -c "import sys;sys.path.insert(0,'/home/wil/Desktop/manny_mcp');from mcptools.credentials import credential_manager as m;c=m.get_account('new');print(c['jx_character_id'],c['jx_session_id'])")
CHAR=$(echo $creds|cut -d' ' -f1); SESS=$(echo $creds|cut -d' ' -f2)
DISPLAY=:2 _JAVA_OPTIONS="-Xmx1536m -XX:MaxMetaspaceSize=192m" MANNY_ACCOUNT_ID=new JX_CHARACTER_ID=$CHAR JX_SESSION_ID=$SESS \
  setsid /usr/lib/jvm/java-21-openjdk/bin/java -jar /home/wil/Desktop/runelite/runelite-client/build/libs/client-1.12.34-SNAPSHOT-shaded.jar > /tmp/runelite.log 2>&1 < /dev/null &
disown
```
Wait for readiness: `grep -q 'Command processor started' /tmp/runelite.log` (takes ~15s: world map load).
To KILL first (separate call): `ps -eo pid,comm,args | awk '$2=="java" && /shaded.jar/ {print $1}' | xargs -r kill -9`
  (matching `$2=="java"` avoids killing your own bash tool-calls that contain "shaded.jar").

### Smoke gate
```
cd /home/wil/Desktop/manny_mcp && ./scripts/ipc_smoke.sh new
```
5 checks: process alive, GET_GAME_STATE rid round-trip <1500ms, burst-3 no-loss, STOP interrupts WAIT,
state freshness. Check 4 (read-only lane) is informational in the harness; verify non-preemption
explicitly with the WAIT+QUERY test (see below).

### Non-preemption test (Wave 2+ regression guard)
Send `WAIT 8000 --rid=X`, sleep 1.5s, send a read-only cmd `--rid=Y`, confirm the WAIT still
runs its full 8s to "Command succeeded" in /tmp/runelite.log (query must NOT cancel it).

### Manual command / state peek
```
echo "GET_GAME_STATE --rid=chk" > /tmp/manny_new_command.txt; sleep 1.5
python3 -c "import json;d=json.load(open('/tmp/manny_new_response.json'));print(d.get('status'), d.get('result'))"
```
NOTE: account is "new" → files are `/tmp/manny_new_*` (namespaced). The un-suffixed
`/tmp/manny_*` is NOT what the running client reads.

### Python gate
```
cd /home/wil/Desktop/manny_mcp && ./venv/bin/ruff check mcptools/ && ./venv/bin/pytest -q
```
Known-baseline failures (NOT regressions, Wave 5 fixes): 4 in tests/test_registry.py
(`TestToolExecution::*`) — they need pytest-asyncio which isn't installed. Everything else must pass.

### Git commit protocol (per wave, both repos)
```
cd /home/wil/Desktop/manny   && git add -A && git -c user.name=Tsangares -c user.email=Tsangares@gmail.com commit -q --author="Tsangares <Tsangares@gmail.com>" -m "Wave N ..." && git push -q origin HEAD
cd /home/wil/Desktop/manny_mcp && git add -A && git -c user.name=Tsangares -c user.email=Tsangares@gmail.com commit -q --author="Tsangares <Tsangares@gmail.com>" -m "Wave N ..." && git push -q origin HEAD
```
Author MUST be Tsangares <Tsangares@gmail.com>. NO Co-Authored-By lines. CLAUDE.md is gitignored.
Rollback points: tag `pre-refactor` in both repos + per-wave commits.

---

## ORCHESTRATION RULES

- **Model tiers:** opus = deep multi-file Java / design-heavy; sonnet = well-specified extraction/
  Python; haiku = mechanical (deletes, path fixes, docs).
- **Single-writer rule:** `PlayerHelpers.java` (~30k lines) and `MannyPlugin.java` — only ONE agent
  edits either per sub-phase. Everything else parallelizes. Java + Python tracks always concurrent.
- **Agent prompts must be self-contained** — subagents don't share my context; embed exact
  file:line specs, the CommandBase template pattern, and constraints in every prompt.
- **Failure handling:** agent output failing its gate → fix-up agent (same model) with the error →
  two failures → do it myself.

---

## KEY ENVIRONMENT FACTS

- Working game account: alias `new` in `~/.manny/credentials.yaml` = character **GrimmsFairly**
  (char id 369444598), on Tutorial Island. Session-ID model (JX_SESSION_ID; access/refresh empty).
- Auto-login: our client auto-clicks "Play". Character IDLE-LOGS-OUT after ~25min on Tutorial Island
  → this is NORMAL, not a bug. Auto-login recovers it in ~1min. `gameState: LOGIN_SCREEN` after
  idle ≠ code regression. The command channel works even logged-out (PING/GET_GAME_STATE respond).
- Re-login needs the character FREE: can't run our client + Bolt's client on the same char (they
  fight; one gets booted). Kill Bolt's game client before relaunching ours.
- Bolt launcher: `flatpak run com.adamcake.Bolt` (installed via user flathub). Its client's env has
  JX_* creds; capture script at `scratchpad/capture_jx.py` (mostly obsolete now — creds are stored).
- `QUERY_INVENTORY` fails at the very start of Tutorial Island ("Inventory not available") — game
  state, not a bug. Same for SCAN_OBJECTS when nothing's around.
- RuneLite source at `/home/wil/Desktop/runelite` on branch `manny-integration` (local); the plugin
  is symlinked into `runelite-client/src/main/java/net/runelite/client/plugins/manny`.
  snakeyaml dep + verification-metadata + world_map.png resource were added for the build.

---

## WAVE 5 PYTHON TRACK — STARTED EARLY (2026-07-17 evening, while W4-B2 still running)

The Python repo is disjoint from B2's Java files, so two Wave-5 agents were dispatched in parallel:
- **W5-P1 (opus) 🔄**: MCP tool pruning 105→25-40. Owns `server.py`, `mcptools/`, `discord_bot/`,
  `manny_driver/`; produces `TOOL_RENAME_MAP.md`. One-canonical-tool rule applied to merges
  (5 widget-click variants, routine trio, discovery trio, anti-pattern duo, session domain unify,
  drop execute_routine tool but keep run_routine.py working).
- **W5-P4 (sonnet) 🔄**: `pyproject.toml` extras split ([discord]/[driver]/[dashboard], +Pillow,
  dedupe google SDK); flock on sessions.yaml writes (session_manager.py); _kill_all_runelite →
  managed PIDs only (runelite_manager.py); check_health pgrep fix (monitoring.py); pytest-asyncio
  added → full pytest green (fixes the 4 baseline test_registry failures).
- File-ownership split is strict (P1 vs P4 lists above); cross-file needs are reported, not edited.
- **WAVE 4 COMPLETE** (2026-07-17 ~19:00): B2 landed — 12 stateful handlers → registry command
  classes (BURY_ALL stays on legacy switch: "Bones" exact-match default would change under registry
  dispatch); ~45 CommandProcessor helpers private→public with processor injected (full extraction =
  Wave 6); LIST_COMMANDS from commandRegistry.keySet() ∪ LEGACY_SWITCH_COMMANDS (133 total);
  dropAllItems(int) orphan deleted. Gate: build green, relaunch, login 12s, smoke 5/5,
  LIST_COMMANDS rid round-trip verified (send syntax is `--rid=`, not `rid=`).
  Commit `f8ac79f` "Wave 4c" pushed. Wave-6 additions from B2: consider registering BURY_ALL with
  an explicit "Bones" default arg; KILL_LOOP_CONFIG/KILL_COW exceptions now report under
  "KILL_LOOP" (accepted nuance).
- **W5-P3 ✅ committed `7a651c8` (2026-07-17 ~19:20):** 112 latches → ClientThreadHelper across
  38 command classes + WidgetClickHelper + Actions.java (−899 net lines). Baseline was 234
  latches, not ~75: PlayerHelpers holds 115 (DEFERRED → Wave 6 split scope), ClientThreadHelper
  3 (the impl), 4 intentionally kept (GEAbort findAbortButton + 3 executor-completion barriers
  in BuryItem/DropItem/UseItemOnItem — NOT client reads, do not convert). Timeout semantics now
  5s throw-on-timeout everywhere converted (CookAll's old 12s scan now 5s — watch for flakiness).
  Live gate green: relaunch, login 12s, smoke 5/5, QUERY_INVENTORY on converted path = same
  clean "Inventory not available" failure at character creator.
- **W5-P1 ✅ + W5-P4 ✅ COMMITTED `e09d5ba` (2026-07-17 ~19:45) and pushed.** Tool surface now 39
  (was 78 registered/~105 defined); see TOOL_RENAME_MAP.md for every old→new mapping. click_widget
  is the single click tool (atomic CLICK_AT — the old bounds path's MOUSE_MOVE+CLICK race is gone).
  P1 flag verified stale: monitoring.py already uses stop_instance/start_instance (P4 fixed it).
  Dead-Gemini imports now raise a clear RuntimeError (not migrated); server.py still uses
  deprecated google.generativeai for analyze_screenshot → Wave 7 candidate. Possible later merges:
  check_health/is_alive and auto_reconnect/restart_if_frozen (39→37).
- **W5-P2 (sonnet) 🔄 dispatched** after P1 freed mcptools/: async-blocking sweep
  (subprocess/time.sleep → asyncio.to_thread at the boundary), fresh inventory (old line numbers
  dead post-P1), tool surface must stay 39, routines/ and discord_bot/ and manny_driver/ excluded.
  Commit separately when green → completes Wave 5 with the Java latch commit `7a651c8`.
- **WAVE 5 COMPLETE (2026-07-17 ~19:35):** P2 committed `e43c868` (async handlers wrapped in
  asyncio.to_thread at boundaries; standalone CLIs untouched; ruff 224, pytest 76, 39 tools).
- **WAVE 6a COMMITTED `5bd303e`:** InteractionSystem = single click authority.
  clickMenuEntrySafe/smartClick cluster + menu-verify state + click stats moved in (PH keeps thin
  delegates; MannyPlugin needed ZERO edits — it only calls the onMenuOptionClicked forwarder);
  CombatSystem.clickNPC/verifyAndClickNPC moved intact (combat click genuinely differs — do not
  merge onto clickNPCSafe). PH −707, CS −340, IS +1076. Live-gated (login exercises moved path).
  Note for W6-J1 Actions retirement: Actions.java has FOUR private matchesMenuEntry copies that
  collapse onto now-public InteractionSystem.matchesMenuEntry.
- **REMAINING:** W6-J1 Actions retirement (fable; NEEDS user answer on strategy Q1 —
  ScenarioEngine replay retire vs keep), W6-J2 PlayerHelpers split (fable; includes its 115
  latches + full helper extraction), W6-P1 driver control-plane (sonnet, free now), follow-ups
  (validator static index, repeat:N no-op, EAT threshold gap), Wave 7 docs+journal, then/or
  Tutorial Island test run (strategy Q2: agent-first recommended).
- **Routine repairs ✅ committed `6cb7ac7`:** DIALOGUE_CONTINUE→CLICK_CONTINUE,
  DIALOGUE_SELECT→CLICK_DIALOGUE, EAT_FOOD→EAT in the 4 broken routines. NEW FOLLOW-UPS
  from that agent (queue after W5-P2 frees mcptools/tools/):
  1. `validate_routine_deep`/`list_available_commands` static index is SYSTEMICALLY stale —
     it regex-scans PlayerHelpers `case "X":` labels, but post-Wave-3/4 nearly everything lives
     in commandRegistry.put(); validator flags even GOTO as unknown. Fix = parse register()
     calls + LEGACY_SWITCH_COMMANDS (or query live plugin). Wave 7 candidate at latest.
  2. `repeat: N` field in routine YAML is NEVER read by the executor (_execute_single_step) —
     silent no-op used by quest routines. Real bug: implement or strip.
  3. ROUTINE_CATALOG.md lists bare `ATTACK` which doesn't exist (docs-only, Wave 7 regen).
  4. EAT has no HP-threshold gating (old EAT_FOOD "25" semantics unrepresentable in YAML —
     no HP-based await/skip condition exists). Design gap for the routine engine.
- **W5-P4 ✅ (2026-07-17 ~19:20, uncommitted — commit with P1 as Wave 5):** pyproject.toml created
  (core deps + extras [discord]/[driver]/[dashboard]/[dev]; Pillow declared; google-genai dupe
  dropped, google-generativeai kept); sessions.yaml writes under reentrant flock
  (`~/.manny/sessions.lock`, atomic os.replace saves); _kill_all_runelite now managed-PIDs-only
  via /proc verification (no pgrep/pkill anywhere; method had zero callers — landmine defused);
  check_health/is_alive use verified PIDs; BONUS: monitoring restart paths called nonexistent
  stop()/start() → fixed to stop_instance/start_instance + pid check; pytest 76 passed
  (was 4 failed/58 passed; pytest-asyncio strict mode); new tests/test_process_safety.py (14 tests).
  FLAG relayed to P1: manny_driver/discord_bot llm_client.py `from google import genai` imports
  were always-dead (package never installed) — P1 decides migrate vs remove.
- **Routine strategy doc** (fable study, user-requested): `journals/ROUTINE_STRATEGY_2026-07-17.md`
  — 5 decision questions pending user. Q4 ANSWERED empirically: juno backup has only an EMPTY
  `osrs_scenarios/` dir (nothing dotted, no manny_sessions, no scenario yaml/json anywhere in
  backup home) — no old recordings to salvage.
- **Dispatched 2026-07-17 ~19:30 (20-min /loop nudge active, cron */20):**
  W6 click-authority consolidation (fable fork; owns PlayerHelpers/InteractionSystem/CombatSystem;
  clickMenuEntrySafe/smartClick cluster move as a unit, CombatSystem.clickNPC retirement;
  MannyPlugin locked) + routine repair agent (sonnet; fix 4 routines using dead
  DIALOGUE_CONTINUE/DIALOGUE_SELECT/EAT_FOOD, verify replacements against Java registry).
- No commits from agents; orchestrator gates then commits manny_mcp as Wave 5 (author Tsangares).
- A 30-min recurring cron nudge is active in the orchestrator session (user request): check agents,
  dispatch any unblocked parallel work. Session-only — recreate after a restart if still wanted.

---

## AFTER THE CAMPAIGN → TESTING PHASE
Drive GrimmsFairly through Tutorial Island end-to-end with the refactored stack as the acceptance
test, then continue development. Write a journal entry (lessons format, see journals/TEMPLATE.md)
at the end of Wave 7.
