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
- **W6-P1 ✅ COMMITTED `c8da7db`:** driver in-process via new mcptools/bootstrap.py (no second
  server spawn); command index fixed (13 w/ 3 false positives → 133, validate_routine_deep
  works again); repeat:N implemented (await_condition short-circuits; 6 tests). pytest 82.
- **USER DECISIONS (2026-07-17 ~20:00):** Q1 = YES, retire ScenarioEngine replay (routines are the
  only execution format; recorder survives feeding routine drafts). Q2 = GO, tutorial test started
  agent-first. Q5 REFRAMED into the project philosophy (saved to orchestrator memory as
  project_manny_automation_philosophy): no final state; routines ARE the product; an LLM driver
  either runs/monitors a routine or builds one; transitions must be unambiguous; atomic compound
  commands (GOTO-style) good; combat not a priority. Build better routine-authoring tools.
- **CRASH-REBOOT 2026-07-17 20:07:** machine crashed ~5 min after the three agents launched.
  /tmp wiped (agent transcripts unrecoverable — they were freshly started, zero durable work
  lost; both repos clean/pushed). Recovery recipe that worked: `setsid Xvfb :2 -screen 0
  1600x1000x24 > /tmp/xvfb2.log 2>&1 < /dev/null &` (verify via /tmp/.X11-unix/X2, xdpyinfo not
  installed), then standard client launch → login 12s (tokens SURVIVED the crash), smoke 5/5.
  All three agents relaunched fresh ~20:12. LESSON: /tmp transcripts + session-only crons die
  with the box; this handoff doc is the only durable state — keep it current.
- **IN FLIGHT (2026-07-17 ~20:12 post-crash relaunch): DEPLOYMENT FREEZE — tutorial driver owns
  the client on :2; Java work gates compile-only until the run ends.**
  1. Tutorial driver (fable fork): agent-first through Tutorial Island on jar `5bd303e`,
     repairing routines/tutorial_island/*.yaml as sections pass; defects are the product.
  2. W6-J1 (fable fork) ✅ DONE (2026-07-17 ~20:35, compile ×2 green + independently verified,
     UNCOMMITTED — full live gate + commit AFTER driver finishes/freeze lifts): net −8,344 lines.
     DELETED: actions/ (Actions.java −5,372, Action, package-info, ActionContext), 
     NavigationSystem (−291, zero callers), GameEngine.BehaviorExecutor (−208, zero callers),
     LoadScenario/LoadCmdlogCommand. Commands REMOVED: LOAD_SCENARIO, LOAD_CMDLOG (133→131);
     PAUSE/RESUME survive (skilling-resume). ScenarioEngine 2,293→1,332; PH −759 (→23,683);
     CoreUtils −114. NEW: automation/replay/ScenarioExporter.java (recorder half extracted
     verbatim, artifact formats unchanged — Python funnel input intact; UNTRACKED, git add it).
     ScenarioPlayer kept at FQN as retirement stub (MannyPlugin locked + injects it; playScenario
     logs [REPLAY-RETIRED]). MannyPlugin manifest notes: remove auto-play block :798-830 + 3
     scenario imports/fields + :1959 callback when unlocked. NOTE: old KILL-gate recipe used
     LOAD_CMDLOG — use `WAIT 30000` + KILL now. W6-J2 candidate: GameEngine private
     matchesMenuEntry copy.
  3. Viewer agent (sonnet) ✅ DONE (2026-07-17 ~20:40): MJPEG viewer shipped as systemd USER
     unit `mjpeg-viewer.service` (enabled, linger=yes → reboot-persistent), port 8787 on
     0.0.0.0. Pixel URL: http://100.83.247.91:8787/ (picker) or
     /view?display=:2&fps=5. Rewritten scripts/mjpeg_viewer.py: multi-display :2–:5
     (lazy grabbers, 0 CPU unwatched), fps 1–15, phone /view page w/ auto-reconnect,
     view-only (no input APIs). ~21% of one core per client @5fps (ImageMagick import).
     VNC skipped: x11vnc not installed + no passwordless sudo; upgrade one-liner documented
     in docs/GAME_VIEWING_OPTIONS.md. UNCOMMITTED (mjpeg_viewer.py + docs) — fold into next
     manny_mcp commit.
- **IN FLIGHT (added ~21:00, all disjoint from driver):**
  4. Viewer-crop agent (opus, user-requested): mjpeg_viewer.py crop-to-RuneLite-window
     (auto-detect geometry, ?crop=off fallback), service restart + verify; view-only.
  5. W6-J2 planning agent (fable, read-only code): full PlayerHelpers map + split design →
     journals/W6J2_SPLIT_PLAN.md (execution contract for the post-freeze J2 fleet).
  6. Routine-engine hardening agent (fable) ✅ DONE (~21:30): proposal at
     journals/ROUTINE_ENGINE_HARDENING_2026-07-17.md (UNCOMMITTED). Core: unify the TWO
     divergent condition dialects (monitoring.py:521-624 awaits vs routine.py:1485-1545 loop
     exits) into one conditions.py; add hp:/hp_pct:/skill:/equipped:/dialogue_open/in_combat
     atoms + only_if/skip_if step guards (single condition string, no boolean algebra); EAT
     case = `only_if: "hp_pct:<50"`. Zero Java needed — state file already has all fields.
     Per-step JSONL events + status snapshot + get_routine_status; on_fail: continue|retry:N|
     goto:id|abort. First slice ~1 day. 6 open questions for USER in doc §(end).
     **3 LATENT BUGS found (QUEUED post-freeze — do NOT hot-fix mcptools while driver runs,
     fresh subprocess invocations would pick up mid-run code changes):**
     (a) routine.py:1531 `no_item_in_bank:` stub always returns False;
     (b) commands.py:402-411 handle_send_and_await writes command file RAW, bypassing
         rid-correlated transport;
     (c) routines/quests/restless_ghost.yaml:154 `action: MCP_TOOL` unrecognized by executor —
         sends literal "MCP_TOOL Ghostspeak amulet" (needs proper EQUIP step or guard slice).
- **SESSION LIMIT HIT (~22:0x 2026-07-17, reset 22:50 PT):** tutorial driver + J2 planner
  terminated mid-flight (client SURVIVED, no reboot — transcripts intact this time). J2
  planner's three research sub-agents delivered full reports post-mortem → preserved in
  **journals/W6J2_CALL_EDGES.md** (Report A external consumers, B commands edges, C latch
  classification: 77 sites = 75 CONVERT / 1 KEEP @6109 / 1 REVIEW @21685). Driver died right
  after root-causing **DEFECT-1** (write-up lost); orchestrator re-derived it from
  /tmp/runelite.log → **journals/TUTORIAL_TEST_DEFECTS_2026-07-17.md**: INTERACT_OBJECT →
  IllegalStateException "must be called on client thread" — CameraSystem.getYawToPoint:1064
  calls TileObject.getWorldLocation() on manny-background thread, via
  InteractionSystem.clickTileObjectSafe:766 → pointCameraAt:1141 (5 hits; Wave 5/6a
  regression). Driver workaround validated: GOTO through doors (pathfinding opens them).
  Recovery ~23:10: J1 committed (compile-gated; live gate still owed at freeze lift —
  committed early to protect −8.3k-line change + unblock separate DEFECT-1 fix commit),
  driver + planner resumed via SendMessage (transcripts intact), opus fix agent dispatched
  for DEFECT-1 (compile-only). LESSON: session limit is a second hard-stop class like the
  crash — same durability rule (journal docs survive, transcripts might not).
- **IN FLIGHT post-recovery (~23:15-23:30):** driver v2 (fable fork, fresh with salvaged
  context — owns client + routines/tutorial_island/ + defect journal appends), J2 planner
  (resumed, finishing W6J2_SPLIT_PLAN.md from W6J2_CALL_EDGES.md, read-only), routine
  validation sweep ✅ DONE (~23:50 → journals/ROUTINE_VALIDATION_SWEEP_2026-07-17.md): 42
  routines = 33 clean, 1 REAL defect FIXED (restless_ghost.yaml step 9: bogus `action:
  MCP_TOOL` → proper `mcp_tool: equip_item` + args map, pattern matched from validated
  tutorial routines), 8 validator FALSE POSITIVES = validator bugs for the post-freeze queue:
  (d) validate_routine_deep doesn't recognize the supported `mcp_tool:` step shape
  (routine.py:1371-1477) — flags "Missing 'action'"; (e) flags 5 non-executable
  reference/config YAMLs for missing `steps` — needs an exemption convention.
  Judgment items: sheep_shearer.yaml:86 dead `skip_if:` key (engine doesn't implement —
  converges with hardening proposal), hill_giants/cow_killer_no_bones look like superseded
  design docs (archive?), 05_cooking_to_quest_guide.yaml missing `plane` on 5 locations
  (driver's turf).
- **DEFECT-1 FIX ✅ COMMITTED `73c7256` (~23:45, compile ×2, DEPLOY DEFERRED to freeze lift):**
  real culprit was the PLAYER read (not the target): getYawToPoint read
  player.getWorldLocation() on manny-background. Fix = thread-aware
  CameraSystem.readPlayerWorldLocation() (isClientThread ? direct : readFromClient —
  unconditional wrap would DEADLOCK overlay callers UIOverlays:3310/3421), applied in
  getYawToPoint + calculateYawToPoint; clickTileObjectSafe target read wrapped too.
  AUDIT FLAGGED unfixed (whole-method batch reads needed — fold into W6-J2 as a thread-audit
  phase): rotateToNPC (1484 + getConvexHull), rotateToObject (1394), prepareToViewTarget
  (2052), findAllNearbyObjects (860), scene scan ~1270-1299, getVisibleTiles/isNPCTileVisible/
  logViewportDiagnostics (652/617/2262 — primary combat caller already wraps, risk only if
  called off-thread elsewhere).
- **Driver v2 findings so far (from defect journal):** client HAD disconnected to red login
  screen during the idle gap; LOGIN command does NOT handle the "You were disconnected" Ok
  dialog (coords miss it — LoginHandlers gap, logged; driver dismissed via CLICK_AT 383 301
  then LOGIN worked). CHEF SECTION had PASSED before the disconnect (bread baked) — driver #1's
  door workaround + dough + range all validated. Resumed at: exit chef building → emotes/run →
  Quest Guide.
- **W6-J2 PLAN ✅ COMPLETE (committed `30335cc`):** journals/W6J2_SPLIT_PLAN.md, 12 phases.
  Headlines: ~3,950 LOC dead handleX bodies (§1.7 delete list = phase J2-1);
  CommandProcessor = 13,428-line nested class (57% of file), PH-proper only ~9k;
  7 un-nests + 5 domain files + 10 CP support classes → PH ends ~2,600, all <5k;
  TileMarkerManager/RandomEventHandler/CommandProcessor CANNOT move (MannyPlugin pins them);
  no context object — Wave-6a-style ctor injection; latches 75 CONVERT/1 KEEP/1 REVIEW
  (net 67 after dead purge); 13 sign-off flags in §6 (stats merge, BURY_ALL registry —
  now shown low-risk/cosmetic default, borderline public deletes, ActionVerifier semantics).
- **J2-1 ✅ COMMITTED `bc4838c` (~00:15 07-18):** PlayerHelpers 23,683→19,764 (−3,919).
  ~45 dead handleX bodies in 21 blocks deleted, each proven dead by tree-wide grep first;
  keepers verified (handleBuryAll, handleGotoCommand, handleBankOpen, handleMineOre etc.);
  4 orphaned imports out; compile ×2. NOTE: J2-1 shifted PlayerHelpers line numbers —
  W6J2_SPLIT_PLAN/CALL_EDGES ranges for PH are now stale below ~10385 (locate by NAME).
- **J2-9 ✅ COMMITTED `4080b11` (~00:25):** last matchesMenuEntry duplicate gone — body
  promoted to static InteractionSystem.matchesMenuEntryLoose; IS public 3-arg + GameEngine
  ActionVerifier both delegate; zero behavior change; plugin-wide grep = no copies left.
- **J2-2 ✅ COMMITTED `ebeb3c0` (~01:50 07-18):** 83/90 latches → ClientThreadHelper.
  CORRECTION: Report C undercounted by 21 (grep missed fully-qualified
  `new java.util.concurrent.CountDownLatch`). 7 survivors: KEEP ×2 (useItemOnItem +
  handleBuryItem — 2nd executor barrier newly found), DEFERRED ×4 (Conditions → J2-3),
  REVIEW ×1 (clickWidgetWithParam mutation, §6.12 comment, needs runOnClient in J2-8).
  TileMarkerManager gained ClientThreadHelper @Inject ctor param; PlayerHelpers gained
  public getClientThreadHelper() (MiningHelper routes via back-ref). **DEFECT-1 AUDIT
  TABLE (~10 methods with off-thread scene/client reads, REPORTED not fixed — thread-audit
  phase input): handlePickUpItem (getCameraPitch 11603; tile reads ~11527-35),
  handleCastSpellOnGroundItem (~11289-305), chopNearestOakTree (13772/13930/13888),
  handleMineOre (14683-4), handleSmeltBronze (16292), pickUpLootAt (~15516/15562),
  MiningHelper.selectNextRock (18476+stream), isNearLocation (~16412, bonus).**
  NOTE: source level is Java 11 — NO records in J2 phases. Git tag `pre-j2` = 73c7256.
- **J2-3 ✅ COMMITTED `2fcb602` (~02:30 07-18):** 7 new utility/ files (EquipmentSystem
  1,105 / ControlSystem 507 / MiningHelper 466 / CombatStyleSystem 247 / CommandStateManager
  177 / PathfindingStateManager 169 / LocationManager 155); PH 18,830→16,075 (−2,755);
  Condition interface → ClientThreadHelper + 4 Conditions latches converted; GameEngine
  dead import gone; repo-wide re-point (26 files) zero residual. Latch residual VERIFIED 3:
  KEEP useItemOnItem:6115 + handleBuryItem:9600, REVIEW clickWidgetWithParam:15063 (agent
  said 2 — its grep missed the fully-qualified site; orchestrator verified intact).
  ORCHESTRATOR NEAR-MISS during commit: ran `git add -A && commit` from the runelite repo
  (committed the symlink to manny-integration branch; push failed on https creds) and the
  follow-up `reset HEAD~1` landed in manny, silently undoing the J2-2 commit locally.
  Recovered (mixed reset preserves working tree; `git reset ebeb3c0` + runelite reset).
  **LESSON: in multi-repo sessions, prefix EVERY git command with an explicit
  `cd /home/wil/Desktop/<repo> &&` — never rely on inherited cwd.**
- **JAVA PAUSE POINT (~02:35): J2-4 (nav extraction) is next but is the highest-risk
  semantic move and carries its own GATE-LIVE — deliberately HELD until the driver finishes
  and the freeze lifts. Sequence at freeze lift: rebuild jar from committed 2fcb602 →
  relaunch → login → smoke 5/5 → live-gate J1+fix+J2-1/2/3/9 as a batch → then dispatch
  J2-4 with its own live gate. Do NOT stack J2-4 on the un-live-tested pile.
- **HARNESS RESTART (~01:20 07-18): FREEZE LIFTED BY EVENT.** The Claude Code process
  restarted; driver v2's agent, the RuneLite client (PID 4833), and Xvfb :2 ALL died with it
  (session tokens should still be valid — they survived the 20:07 crash too). Driver v2's
  last checkpoint: COMBAT PASSED (~00:40), next = exit ladder (~3111,9526) → banking (09).
  10 defects logged total (see TUTORIAL_TEST_DEFECTS; priority for tutorial driving:
  DEFECT-8 modal CLICK_CONTINUE > DEFECT-7 GOTO exact > DEFECT-1 fixed-awaiting-deploy).
  **FREEZE-LIFT ✅ EXECUTED (~01:25-01:30):** Xvfb :2 restarted; shadowJar rebuilt from
  clean 2fcb602 (0 stale sources); client launched, login 12s (tokens survived crash #3
  too); smoke 5/5; **LIVE GATE GREEN: INTERACT_OBJECT Door Open → success, 0 client-thread
  exceptions in new log — DEFECT-1 fix VALIDATED LIVE.** The banked batch (J1 `c01219c` +
  fix `73c7256` + J2-1 `bc4838c` + J2-9 `4080b11` + J2-2 `ebeb3c0` + J2-3 `2fcb602`) is
  deployed and live-gated. Journals committed through `747cccd`.
- **IN FLIGHT (~01:30 07-18): driver v3 (fable fork)** — finishing the island on the NEW
  jar: banking (09) → prayer/magic (10) → advisor → Lumbridge. Doubles as regression check:
  uses INTERACT_OBJECT normally (failure = critical defect), re-tests DEFECT-2/7/8 repro.
  Appends "Driver #3 (new jar 2fcb602)" sections to TUTORIAL_TEST_DEFECTS. OWNS the client —
  freeze rules apply again until it finishes. AFTER island: dispatch J2-4 (nav extraction,
  own live gate), then the unblocked post-freeze Python queue (bugs a/b/c, validator
  mcp_tool+reference-file fixes, DEFECT-8/7 command fixes per driver priority).
  Hourly cron nudge = job `2aa5788b` (:23, session-only — RECREATE after any restart;
  prompt includes freeze rules + post-driver sequence + "use subagents to parallelize").
- **REMAINING (ALL user-gated or sequenced):** W6-J1 Actions retirement (fable; NEEDS user
  answer on strategy Q1 — ScenarioEngine replay retire vs keep), W6-J2 PlayerHelpers split
  (fable, after J1; 115 latches + full helper extraction + stats-tracker merge + BURY_ALL
  registry default), EAT threshold design gap (needs user), Wave 7 docs+journal (last),
  Tutorial Island test run (awaiting user "go"; strategy Q2 rec: agent-first, orchestrator
  recommended testing BEFORE J1/J2 surgery to bank a behavioral baseline).
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
     ALSO for Wave 7 doc regen (post-J1 removals, verified by grep 2026-07-17 ~21:20): purge
     LOAD_SCENARIO/LOAD_CMDLOG from COMMAND_REFERENCE.md:701-708, ROUTINE_CATALOG.md:334,
     TOOLS_USAGE_GUIDE.md:436, .claude/commands/validate.md:36 (ticket/ files are historical,
     leave). No .py code references either command — docs only.
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

---
## POST-FREEZE QUEUE — DEFECT-3 Java fix (added 2026-07-18, spec ready)
SCAN_TILEOBJECTS crashes off-thread (getWorldLocation on manny-background). Full ready-to-apply
patch spec at `journals/DEFECT3_FIX_SPEC.md`. Fix = wrap result-building in
`helper.readFromClientSafe(buildResults(...))` with an `isClientThread()` fast-path guard
(mirrors DEFECT-1 CameraSystem pattern). Requires injecting ClientThreadHelper into
ScanTileObjectsCommand via constructor (it has none today) — pattern copy from
SwitchCombatStyleCommand; wire from PlayerHelpers.java ~7207 in-scope `helper` field.
Apply AFTER freeze lifts (driver done), then build+smoke+live SCAN_TILEOBJECTS gate. Same bug
class likely lurks in other result-building command paths — audit during J2-5 (UI/item/anim).

## POST-FREEZE QUEUE — DEFECT-11 (regression, added 2026-07-18 during Driver #4)
`TILE <object> <color>` command throws `NullPointerException: this.tileMarkerManager is null`
(PlayerHelpers$CommandProcessor, seen 01:49:42 in /tmp/runelite.log). TileMarkerManager gained a
ClientThreadHelper @Inject ctor param during J2-2 latch conversion — the field is now null at TILE
command time, so DI/instantiation wiring broke. NOT progression-critical (TILE is debug tile-marking;
driver unblocked, core commands fine) but a clear J2-2 regression. Post-freeze: trace where
tileMarkerManager is constructed/assigned (nested class, MannyPlugin-pinned — manifest note only, do
not edit MannyPlugin) and restore the wiring; add a smoke check for TILE. Likely a quick fix.

## FREEZE LIFTED 2026-07-18 ~11:10 — Tutorial Island COMPLETE (Driver #5, Lumbridge 3221,3218)
End-to-end acceptance test PASSED on jar 2fcb602. All sections cleared across Drivers #2-#5.
Two new defects to the post-freeze queue:
- DEFECT-13: TELEPORT_HOME / CAST_SPELL hardcodes widget 14286855 (Minigame Teleport) — correct
  Lumbridge Home Teleport is 14286854. Worked around live via CLICK_WIDGET 14286854. Fix: correct
  the hardcoded widget id (and/or make it spell-name driven). Java (post-freeze).
- DEFECT-14: MOUSE_MOVE rejects sidebar/off-viewport coordinates as "Invalid coordinates" — clamps
  to game viewport only, so tab/inventory-region moves fail. Java (post-freeze).
Full re-test matrix + 9-item priority list in journals/TUTORIAL_TEST_DEFECTS_2026-07-17.md
(Driver #5 — ISLAND COMPLETE section). Verdict: viable NOW as LLM-driven; fix DEFECT-8/7/13 for
blind (unattended) replay.
Client is LIVE on 2fcb602, logged in, character in Lumbridge — ideal state for grind-loop routine
tests (chicken_killer_training, woodcutting_lumbridge). NEXT: after engine agent lands routine.py
changes, run grind tests on this Lumbridge character, THEN Java post-freeze fixes + J2-4 (rebuild).

## OPS LESSON 2026-07-18 — kill stale clients before relaunch (duplicate-login JVM kill)
Found THREE shaded.jar clients running at once (two 'new' + one newbakshesh) — the setsid/disown
launch recipe accumulates orphans if the prior client isn't killed first. Two clients sharing the
SAME account session token get one JVM killed by Jagex (duplicate login) — this is the likely cause
of the unexplained 11:17 client death. BEFORE any relaunch: `pgrep -f 'java -jar.*shaded.jar'` and
kill stale pids (verify account via `tr '\0' '\n' < /proc/<pid>/environ | grep MANNY_ACCOUNT_ID`),
leave exactly ONE client. Per-account IPC is namespaced (/tmp/manny_<acct>_command.txt) so different
accounts don't collide on files, but they DO collide on Xvfb :2 render + the shared token if same acct.
Accounts: main / new (tutorial DONE, in Lumbridge) / newbakshesh (on Tutorial Island, token still valid
as of 11:25 — this is the tutorial-ROUTINE test bed).

================================================================================
## ★ NORTH STAR + PLAN (decided 2026-07-18, user-confirmed) — READ THIS FIRST ★
================================================================================
GOAL (3 levels):
- North star: LLM-driven OSRS automation — a library of unattended ROUTINES (YAML step-seqs over
  atomic commands); LLM drivers run/monitor/build them. Fresh account -> money-makers. No final state.
- This campaign: (1) finish the manny refactor (maintainable codebase), (2) prove the stack unattended
  — Tutorial Island as the first hands-off routine (00_master), then grind-loop money-makers.
- Priority (USER-CHOSEN 2026-07-18): **FINISH THE REFACTOR FIRST.** Then routines/grind tests.

CRASH REALITY: cause is POWER (hardware) — NOT software/OOM. No software fix. Strategy = fast
recovery + durable state, NOT root-causing. Classify work by crash cost:
  - crash-cheap (Python/Java source, docs, refactor phases): commit+push per unit, resumes from git ~free.
  - crash-expensive (live client drives/routine tests): journal per SECTION so we resume at last
    checkpoint, not the start.
PARKED INITIATIVE (not now): migrate the client to `diort` (LAN 10.0.0.x -> residential IP, NO
datacenter ban risk, unlike a cloud server) IF it is more power-stable. Would end the crash cycle
without the proxy headache. Revisit after refactor.

REFACTOR-COMPLETION SEQUENCE (execute in order; PlayerHelpers.java is SINGLE-WRITER so these serialize):
  A. Java defect batch (DEFECT-3/11/13/14) — specs in DEFECT3_FIX_SPEC.md + DEFECT_11_13_14_FIX_SPECS.md.
     Apply source edits (can do now, does NOT need client), compileJava-check, commit. Then rebuild +
     relaunch + LIVE-GATE all 4 (SCAN_TILEOBJECTS ok, TILE ok, TELEPORT_HOME->14286854, MOUSE_MOVE sidebar).
  B. J2-4 nav extraction — pre-flight in J2-4_PREFLIGHT.md (~4,840 lines -> PathfindingHelpers +
     NavigationHelpers). Own rebuild + GATE: GOTO round-trip + ipc_smoke 5/5 + KILL-during-GOTO (the
     shouldCancelNavigation volatile seam is the risk). Keep handleGotoCommand in CP shell.
  C. J2-5 (UI/item/anim + clearUseMode), J2-6/7/8 (CP shell/wrappers) per W6J2_SPLIT_PLAN.md; 13 §6 flags.
  D. Wave 7: regen COMMAND_REFERENCE/ROUTINE_CATALOG/TOOLS_USAGE from registry; finalize campaign journal.
THEN (routines phase): transcribe tutorial coords into sections 07-10 (needs A done for DEFECT-7/8/11),
run 00_master end-to-end on newbakshesh; then grind-loop money-makers on 'new' in Lumbridge.
Engine is READY (commit 1c63c42: repeat_until/dialogue/click_text/chain).
================================================================================

## PHASE A COMPLETE — Java defect batch LIVE-GATED GREEN (2026-07-18 ~11:55)
Rebuilt shadowJar (11:49, 0 stale sources) with manny 124a2c1; relaunched 'new' in Lumbridge; gated:
- DEFECT-3 PASS: SCAN_TILEOBJECTS ran clean, 0 new "client thread" errors.
- DEFECT-11 PASS: TILE Tree red -> "Marked 412 tiles", no tileMarkerManager NPE.
- DEFECT-13 PASS: TELEPORT_HOME used widget 14286854 (Lumbridge), NOT 14286855 (Minigame); "Teleport complete".
- DEFECT-14 PASS: MOUSE_MOVE sidebar coords accepted, both space "700 350" and comma "690,340" forms.
Defect fixes are DEPLOYED + verified. NEXT = Phase B: J2-4 nav extraction (pre-flight J2-4_PREFLIGHT.md).
OPS LESSON: never detect the client with `pgrep -f 'java -jar.*shaded.jar'` — the pattern self-matches
your own bash command line. Use `pgrep -x java` + check /proc/<pid>/environ for MANNY_ACCOUNT_ID.

## ★ THERMAL POLICY (2026-07-18) — heat causes the crashes; MANAGE IT ★
ROOT CAUSE of crashes = HEAT. The RuneLite client pins ~79% of a CPU core CONTINUOUSLY (GPU-less
software rendering on Xvfb — renders every frame even when the character is idle). Sustained load
-> package hits 77°C+ -> thermal/power crash. Measured 2026-07-18: killing the idle client dropped
package 77->72°C and load 1.45->0.81 within seconds.
POLICY:
1. CLIENT OFF during source-refactor phases (J2-4/5/6/7/8, doc work, Python). It is NOT needed to
   edit/compile Java — only for live gates, routine tests, tutorial drives. Kill it when idle:
   `for p in $(pgrep -x java); do grep -q '^MANNY_ACCOUNT_ID=' /proc/$p/environ && kill $p; done`
2. CLIENT ON only for the duration of a gate/test, then kill again.
3. When it MUST run, renice it low priority right after launch: `renice 15 <pid>` (renice available;
   cpulimit NOT installed). For LONG routine-test sessions, monitor temp and pause if package >88°C.
4. Don't stack many concurrent subagents WHILE the client runs — agents + client together is the
   hot combination. Source-phase agents (client off) are fine.
This is the real fix until the `diort` LAN-host migration (parked) or better cooling.

## PHASE B (J2-4) COMPLETE — nav extraction LIVE-GATED GREEN (2026-07-18 ~12:24)
manny ad288ab: PathfindingHelpers.java (1,372) + NavigationHelpers.java (3,662) extracted;
PlayerHelpers 16,076 -> 11,302 lines (campaign start was 23,683). Rebuilt shadowJar (12:19),
gated on 'new' in Lumbridge via scripts/client.sh (reniced, thermal-guarded):
- Smoke 5/5.
- Navigation FUNCTIONS from extracted NavigationHelpers (walked ~35 tiles to targets; A*/waypoint/
  minimap all fire from the new class).
- KILL-during-GOTO PASS: walked 8 tiles, KILL halted it 22 tiles short of target; [NAV-CANCEL] fired
  from NavigationHelpers -> shouldCancelNavigation seam works on the live single instance.
- Note: GOTO arrival precision / east-Lumbridge "stuck" = pre-existing DEFECT-7 (not a regression);
  isMoving state field is unreliable (reports False while walking) — detect movement via location delta.
Client STOPPED after gate to cool. NEXT = Phase C: J2-5 (UI/item/anim + clearUseMode) per W6J2_SPLIT_PLAN.md.

## POST-FREEZE/DEFECT QUEUE — DEFECT-15 (found during J2-5, pre-existing, moved verbatim)
UiHelpers.getHull / getMinimap call client-thread-only accessors (Perspective.getCanvasTilePoly,
getClickbox, getConvexHull, getLocalLocation) OFF the client thread — sole caller PlayerHelpers.moveMouse
runs on manny-background. Same class as DEFECT-3. Fix = wrap those bodies with readFromClientSafe +
isClientThread() guard (mirror DEFECT-3 CameraSystem pattern). Not a J2-5 regression (moved verbatim).
Details in journals/J2-5_PREFLIGHT.md §5. Batch with the next Java defect pass.

## PHASE C (J2-5) COMPLETE — UI/item/anim extraction gated (2026-07-18 ~12:44)
manny bf83463: UiHelpers.java (574) + ItemUseHelpers.java (404) + AnimationHelpers.java (479);
PlayerHelpers 11,302 -> 10,118 lines. clearUseMode seam = client-singleton-owned (setWidgetSelected),
NOT a stranded-instance risk — structurally safe. Rebuilt shadowJar (12:xx), gated on 'new' Lumbridge:
- Smoke 5/5. TAB_OPEN Magic OK. TELEPORT_HOME via UiHelpers smartMoveToWidget -> Lumbridge OK.
  GOTO/NavigationHelpers OK. Only log error = benign login-time WidgetInspectorTool NPE (xz.ch null,
  ClientThread, 12:43:21 startup) — NOT a regression.
- PARTIAL gate: item-on-item (LIGHT_FIRE/COOK) + skilling-anim paths NOT tested here ('new' has empty
  inventory). Deferred to routines-phase tutorial-04 live-verify on newbakshesh (section 04 = firemaking/
  cooking naturally exercises ItemUseHelpers.useItemOnItem/lightFire/cookOnFire + AnimationHelpers waits).
- NEW: DEFECT-15 queued (UiHelpers.getHull/getMinimap off-thread, pre-existing/verbatim; batch next Java pass).
Client STOPPED to cool. NEXT = Phase D: J2-6/7/8 (CP shell/wrappers) per W6J2_SPLIT_PLAN.md.

═══════════════════════════════════════════════════════════════════════════════
## ⭐ COMPACTION CHECKPOINT 2026-07-18 ~12:55 — RESUME HERE FIRST ⭐
═══════════════════════════════════════════════════════════════════════════════
REFACTOR STATUS — PlayerHelpers.java: 23,683 (campaign start) -> 8,719 lines (and shrinking in J2-6).
  Phase A  defect batch DEFECT-3/11/13/14 ...... DONE, live-gated GREEN (manny 124a2c1)
  Phase B  J2-4 nav extraction ................. DONE, live-gated GREEN incl KILL-during-GOTO (manny ad288ab)
  Phase C  J2-5 UI/item/anim ................... DONE, gated (UI/spell/nav green; item/anim deferred) (manny bf83463)
  Phase D  J2-6 CP shell/wrappers ............. ⚠️ IN FLIGHT, UNCOMMITTED. Agent id ae7a4735f77a5d8cd.
      manny working tree: NEW utility/InventoryActionSupport.java + utility/ItemQuerySupport.java;
      MODIFIED PlayerHelpers.java (8,719) + BankingSupport.java. compileJava NOT yet confirmed.
      manny HEAD still bf83463 (J2-6 not committed). Plan in journals/J2-6_PREFLIGHT.md.

>>> ON RESUME (do this first):
1. Is J2-6 agent (ae7a4735f77a5d8cd) alive/finished? Check `cd /home/wil/Desktop/manny && git -c core.pager=cat log --oneline -2`.
   - If a NEW commit past bf83463 exists (J2-6 committed): rebuild shadowJar, then GATE via
     `scripts/client.sh start new` -> test the commands its report named
     (inventory/bank/item-query wrappers) -> `scripts/client.sh stop`. Record in handoff, continue.
   - If ORPHANED (no new commit, dirty tree): `cd /home/wil/Desktop/manny && git status` + run
     `cd /home/wil/Desktop/runelite && ./gradlew :client:compileJava -x checkstyleMain -x pmdMain --console=plain`.
     If GREEN + coherent -> commit as J2-6 (author Tsangares, no co-author). If broken/partial ->
     `cd /home/wil/Desktop/manny && git checkout -- . && git clean -f utility/InventoryActionSupport.java utility/ItemQuerySupport.java`
     to reset, then RE-DISPATCH J2-6 fresh (opus, single-writer PlayerHelpers, read J2-6_PREFLIGHT.md).
2. Remaining refactor: J2-7/8 (unless J2-6 folded them in — check its report) -> Wave 7 (regen COMMAND_REFERENCE/
   ROUTINE_CATALOG/TOOLS_USAGE from registry; finalize journals/2026-07-18_progress.md + campaign journal, drop DRAFT).
3. THEN routines phase (user priority is REFACTOR FIRST): live-verify on newbakshesh (still on Tutorial Island
   ~section 04, early-saved token still valid as of 11:25) the tutorial-04 cook fix (manny_mcp 40f213d) +
   engine disconnect-recovery (manny_mcp 1a4b5da); run grind-loop tests (chicken_killer_training, woodcutting_lumbridge
   on 'new' in Lumbridge); transcribe tutorial 07-10 coords from TUTORIAL_TEST_DEFECTS journal into the section YAMLs.

OPEN DEFECT QUEUE (batch into next Java defect pass): DEFECT-15 (UiHelpers.getHull/getMinimap off-thread, DEFECT-3 class).
THERMAL: HEAT = crash root cause. Client OFF during source phases; only up (reniced, via scripts/client.sh) for gates.
  Client is OFF now, pkg ~49°C. Long-term fix = migrate client to LAN host `diort` (residential IP, no bans) — parked.
CRON: 92415571 (:13,:43) session-only — RE-ARM after any restart. Accounts: new (tutorial done, Lumbridge) /
  newbakshesh (on Tutorial Island, ROUTINE test bed) / main. Detect client via `pgrep -x java`+environ, NOT pgrep -f.
═══════════════════════════════════════════════════════════════════════════════

── UPDATE (right after checkpoint): J2-6 COMPLETED + COMMITTED ──
Phase D J2-6 is NO LONGER in flight — it committed as manny `069b71d` (compileJava GREEN):
  NEW utility/ItemQuerySupport.java (221) + utility/InventoryActionSupport.java (1005);
  BankingSupport.java 742->1129; PlayerHelpers 10,118 -> 8,719 lines. CommandProcessor stays
  MannyPlugin-pinned with thin wrappers. J2-7 and J2-8 deliberately NOT combined (kept separate).
>>> ON RESUME step 1 is now: GATE J2-6 (it is committed, not orphaned): rebuild shadowJar ->
    `scripts/client.sh start new` -> exercise PICK_UP_ITEM, BURY_ITEM, BURY_ALL, DROP_ALL,
    BANK_DEPOSIT_ITEM, BANK_WITHDRAW (+ wrapper cmds: SMELT_BAR, KILL_LOOP dropall, BURY_ALL,
    BUY_GE withdraw). NOTE: 'new' has EMPTY inventory + likely nothing banked -> bank/pickup/bury
    tests may need items; consider gating item-free paths + deferring item paths to routines-phase
    tutorial/grind verify (as done for J2-5). -> `scripts/client.sh stop`. Record + continue.
Then remaining refactor: J2-7 (MINE_ORE — highest Group-C risk, OWN live gate) -> J2-8 (spell/equip/
    GE/smithing) -> Wave 7. Both plans/boundaries: re-derive by symbol (PlayerHelpers now 8,719).
NEW DEFECT-16 (queue with DEFECT-15 for next Java defect pass): handlePickUpItem's background task
    calls LocalPoint.fromWorld / cameraSystem.isTileVisible / prepareToViewTarget on the background
    executor (DEFECT-3 class, off-thread). Pre-existing, moved verbatim in J2-6, NOT introduced by it.

═══════════════════════════════════════════════════════════════════════════════
## ★ BATCH GATE GREEN 2026-07-18 ~13:53 — J2-7 + DEFECT-15/16 + J2-6 deployed ★
═══════════════════════════════════════════════════════════════════════════════
REFACTOR STATUS — PlayerHelpers.java: 23,683 (campaign start) -> **5,604 lines** (−76%).
  Phase A/B/C (124a2c1/ad288ab/bf83463) + J2-6 (069b71d) all prior.
  J2-7 committed **ee525e1**: WorldActionSupport (991) + CookingFiremakingSupport (1635) +
    MiningWorkflowSupport (786). Enum FQNs (WorkflowLocation/InventoryOreType) + public fields
    (lastDepositedOre/nextOreToMine) moved to MiningWorkflowSupport; CollectLumbridgeTinCopperCommand
    rewired; CP keeps 11 thin wrappers.
  DEFECT-15/16 committed **5d3b7a1**: UiHelpers.getHull/getMinimap + InventoryActionSupport
    .handlePickUpItem off-thread reads wrapped (readFromClientSafe + isClientThread guard).
Both pushed to origin/master. Rebuilt shadowJar 13:48 (0 stale). Gated on 'new' in Lumbridge:
- Smoke 5/5.
- J2-7 dispatch VERIFIED: MINE_ORE ("Pickaxe verified" then KILL-interrupt clean), COLLECT_LUMBRIDGE_
  TIN_COPPER (workflow started), LIGHT_FIRE (client-thread ground check ran), COOK_ALL (inventory
  search ran), SCAN_TILEOBJECTS (clean scan) — all extracted classes load + dispatch + reach real
  logic; "failed" outcomes are expected (empty inv / nothing nearby), not crashes.
- DEFECT-16 VERIFIED: PICK_UP_ITEM Jug -> "Command succeeded", no client-thread exception.
- DEFECT-15 VERIFIED: MOUSE_MOVE -> "Command succeeded" (exercises moveMouse->getHull/getMinimap),
  no client-thread exception.
- Zero NEW client-thread/NPE exceptions from any tested command. Only log exceptions: (a) benign
  startup WidgetInspectorTool NPE (xz.ch null, known, not a regression); (b) DEFECT-17 below.
Client STOPPED after gate, pkg ~61C.

**NEW DEFECT-17 (queue for next Java defect pass, DEFECT-3 class, PRE-EXISTING not a J2-7 regression):**
  COLLECT_LUMBRIDGE_TIN_COPPER workflow throws IllegalStateException "must be called on client thread"
  at GameEngine$GameHelpers.getDistanceTo(GameEngine.java:2964) -> getWorldLocation() off the
  manny-background thread (hit when the char is NOT at the mine, so the distance-calc branch runs).
  GameEngine untouched by J2-7 (verbatim handler move); flagged in the old DEFECT-1 audit as deferred.
  Fix = wrap getDistanceTo's getWorldLocation read (readFromClientSafe) OR guard the caller in
  MiningWorkflowSupport.detectCurrentLocation. Batch with DEFECT-17 whenever the mining money-maker
  routine is built (needed for COLLECT/MINE workflows to run unattended).

>>> ON RESUME: J2-7 + defects are DEPLOYED + gated. NEXT = **J2-8** (final PH split phase): C7
    SpellCombatSupport + C8 EquipmentSupport + C9 GEInterfaceSupport + C10 SmithingSupport (incl.
    BarTypeInfo FQN update in SmeltBarsCommand). Files: PlayerHelpers.java + 4 new + SmeltBarsCommand.
    Map by SYMBOL (plan line numbers stale; PH now 5,604). Then Wave 7 (doc regen DONE below; just
    finalize journal). Then routines phase.
WAVE 7 DOC REGEN ✅ (this session): COMMAND_REFERENCE.md regenerated to 131 real commands (121
    register() + 10 legacy-switch: PING/PAUSE/RESUME/CAMERA_RESET/BURY_ALL/LIGHT_FIRE/LOGIN/
    LIST_OBJECTS/INTERACT_OBJECT/LIST_COMMANDS); bogus ATTACK/STRENGTH/BALANCED removed (they are
    handleEquipBestMelee arg values, not commands); LOAD_SCENARIO/LOAD_CMDLOG confirmed absent.
    ROUTINE_CATALOG.md ATTACK-redirect claims fixed + count 90->131. TOOLS_USAGE_GUIDE clean.
═══════════════════════════════════════════════════════════════════════════════

███████████████████████████████████████████████████████████████████████████████
## ★★★ REFACTOR COMPLETE 2026-07-18 ~14:15 — PlayerHelpers 23,683 -> 3,484 (85% off) ★★★
███████████████████████████████████████████████████████████████████████████████
J2-8 (final PH split) committed **059cdb2** + DEFECT-17 fix **fd97462**, both pushed. Rebuilt
shadowJar (14:12, 0 stale), gated on 'new' in Lumbridge:
- Smoke 5/5.
- J2-8 dispatch VERIFIED GREEN: TELEPORT_HOME -> full success (widget 14286854, Teleport complete);
  EQUIP_BEST_MELEE -> ran full weapon-scoring (found Bronze sword), failed only on bounds (UI/tab,
  not refactor); SMELT_BAR -> resolved bar types incl. "Use SMELT_BRONZE_BARS for bronze" (BarTypeInfo
  FQN seam WORKS); CAST_SPELL -> succeeded; GE_OPEN -> dispatched. All four extracted support classes
  load+dispatch+reach real logic. No J2-8-introduced regression.
- DEFECT-17 VERIFIED FIXED: COLLECT no longer throws getDistanceTo IllegalStateException; it now
  progresses PAST it to getInventoryOreType (which hit a transient 5s client-thread timeout under my
  rapid-fire 7-cmd battery — a LOAD artifact of test method, not an off-thread violation; a real
  one-command-at-a-time routine won't do this).
Client STOPPED, pkg ~62C.

REFACTOR SCORECARD — PlayerHelpers.java decomposition, all live-gated:
  23,683 (start) -> J2-1 19,764 -> ... -> J2-6 8,719 -> J2-7 5,604 -> **J2-8 3,484**. 85% reduction.
  ~20 focused utility/ support classes now hold what one file did. CommandProcessor = thin dispatch
  shell + delegating wrappers. This is the "codebase an LLM can author routines against" goal MET.

**NEW DEFECT-18 (GameEngine off-thread read cluster — batch with DEFECT-17-style pass):** SMELT_BRONZE
  throws "must be called on client thread" at GameEngine$GameHelpers.findGameObjectsByName:1971 ->
  getWorldLocation() off the manny-background thread (from SmeltBronzeCommand:77). PRE-EXISTING (in the
  DEFECT-1 audit; GameEngine untouched by J2-7/J2-8; handleSmeltBronze moved verbatim). Same fix pattern
  as DEFECT-17. RECOMMENDED next Java pass: one "GameEngine off-thread read audit" that batch-fixes
  findGameObjectsByName + the DEFECT-1-audit-table remnants (rotateToNPC/rotateToObject/prepareToViewTarget/
  findAllNearbyObjects/scene-scan) with the isClientThread+readFromClientSafe guard, one gate.

## ROUTINES PHASE — GROUNDWORK DONE (2026-07-18), ready for first live grind test
- Tutorial Island 07-10 transcribed w/ real coords (c513ecd); DEFECT-13 fixed in-routine. 3 TODO coords
  need live capture. Full 01->10 chain in 00_master.
- Python engine bugs (rid-correlation, no_item_in_bank, restless_ghost MCP_TOOL) ALL already fixed
  (verified: e5f00d3 + validation sweep). 154 tests pass. Engine queue CLEAR.
- Grind routines audited+fixed (journals/GRIND_ROUTINE_READINESS_2026-07-18.md). CRITICAL FIX: blocking
  commands (KILL_LOOP/CHOP_TREE/FISH_DRAYNOR_LOOP) had no timeout_ms -> run_routine.py abandoned them
  after 30s default, leaving the client grinding UNSUPERVISED. 9 files fixed.
- RANKED first-live-test shortlist: (1) combat/chicken_killer_training.yaml [safest, timeout-fixed],
  (2) combat/chicken_killer_loop.yaml, (3) skilling/woodcutting_lumbridge.yaml [VERIFY axe EQUIPPED not
  just banked before running - step 3 would otherwise bank it].
>>> NEXT (routines phase, refactor now DONE): run the shortlist grind test on 'new' in Lumbridge
    (client on, reniced, thermal-watch), monitor as supervisor, fix what breaks. Then tutorial 00_master
    end-to-end on newbakshesh. Wave 7 journal finalize (drop DRAFT) is the last refactor-side chore.
███████████████████████████████████████████████████████████████████████████████

## FIRST GRIND TEST 2026-07-18 ~14:25 — pipeline PROVEN, hit nav blocker (DEFECT-19)
Ran chicken_killer_training on 'new' via run_routine.py. RESULTS:
- ✅ PIPELINE WORKS: run_routine.py loaded the routine, dispatched, produced a STRUCTURED result
  (status/errors/final-state). The supervisor/runner layer is functional — the "LLM monitors routines"
  infra is real.
- 🐞 ROUTINE BUG (FIXED): step 1 GOTO coord was 3180,3288 (WEST, across the river Lum — wrong); real
  Lumbridge coop is ~3235,3295 (east). Also step 1 had no await + 30s default < a 76-tile walk. FIXED
  chicken_killer_training.yaml: coord -> 3235 3295, added await_condition location:3235,3295 + timeout_ms
  120000. (Grind-audit fixed KILL_LOOP timeout but missed the long initial GOTO — same class of bug.)
- 🚫 DEFECT-19 (NAV BLOCKER, likely pre-existing, needs client-off code fix + live gate): GOTO 76 tiles
  logged "[NAV-METHOD] Using PATHFINDER API" -> immediately "[NAV-API] Pathfinder API failed or
  unavailable, falling back to Global A* (PNG-based)" -> THEN NOTHING. Character never moved (loc
  unchanged over 45s across two GOTO attempts). The Global A* (PNG) fallback silently produces no path
  execution / no minimap walk on this route. J2-4 gate walked a shorter ~35-tile route fine, so short
  hops / pathfinder-API path work; the A*-fallback-on-long-route path is broken. This blocks ALL
  travel-based grind routines. Diagnosis dispatched -> journals/DEFECT19_NAVIGATION_DIAGNOSIS.md.
  Fix must be live-gated (GOTO 70+ tiles must actually walk). Until fixed, grind routines that need a
  long initial travel will stall at step 1; short-range routines (already at the resource) are unaffected.
███████████████████████████████████████████████████████████████████████████████

## DEFECT-19 FIX (v2) + ROUTINE HARDENING 2026-07-18 ~14:45 — PENDING LIVE GATE
ROOT CAUSE (agent diag, manny/journals/DEFECT19_NAVIGATION_DIAGNOSIS.md): "Pathfinder API" is an
EXTERNAL http service (osrspathfinder.com) — unreachable in this sandbox -> falls back to Global A*;
A* uses CollisionMapCache.canMove which treats UNCACHED tiles as blocked, so a 76-tile route (mostly
unvisited, 10201-tile cache @0% hit) churns toward maxIterations=50000 and HANGS >51s. gotoPositionSafe
then never reaches its giveup branch.
- v1 fix (38cfb5e) put the LOS->directional fallback in the giveup branch = AFTER the hanging A*.
  LIVE GATE FAILED: no movement, no new log line (never reached the branch). Also thermal spiked to 90C
  (the A* churn is itself CPU-heavy, compounding client render load).
- **v2 fix (a5069a0, COMPILE-GREEN, PENDING LIVE GATE):** moved the shortcut BEFORE the slow A* at the
  API-fallback point (~NavigationHelpers:1436): when pathfinder API returns no path AND hasLineOfSight,
  go straight to simpleDirectionalNavigation, skipping A*. New log line: "[NAV-API] Pathfinder API
  unavailable but LINE OF SIGHT CLEAR - directional walk, skipping slow A*". LOS-blocked routes keep the
  A*/smart-door path. Bonus: skipping the A* churn should also REDUCE the thermal load for this route.
  >>> LIVE GATE (careful, thermal): rebuild done (jar fresh). GOTO 3235 3295 0 must (1) log the new line,
      (2) NOT show [Global A*] churn, (3) actually WALK and arrive. Keep gate SHORT (stop as soon as loc
      changes = proven), abort at 84C. If green: chain KILL_LOOP Chicken to prove the grind end-to-end.
ROUTINE CORPUS HARDENING (agent, journals/ROUTINE_CORPUS_HARDENING_2026-07-18.md): applied the DEFECT-19
  lesson corpus-wide — 60 GOTO steps across 17 files got await_condition location:X,Y + distance-scaled
  timeout_ms (60s <=20 tiles, 120s longer). quests/utility audited (fixed death_escape delay_ms no-op).
  Flagged config-only sidecars w/o steps: (gravestone_retrieval, hill_giants) + cooks_assistant missing
  start-GOTO + tutorial 06_quest_guide (superseded dup of 05, awaits documented to cause timeouts there).
  All 43 routines parse clean.
███████████████████████████████████████████████████████████████████████████████
