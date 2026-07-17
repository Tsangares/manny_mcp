# Manny Stack — Full Architecture Review

Four parallel deep-reviews (plugin core · plugin subsystems · Python/MCP server · IPC protocol) of the complete stack: `manny` (Java RuneLite plugin, ~93k lines) + `manny_mcp` (Python MCP server, ~30k lines). 2026-07-17.

---

## Verdict: **Refactor, don't rewrite.**

All four reviewers converged independently on the same diagnosis:

> **The newest code in every layer is good. The debt is unfinished migrations — every refactor built a new home next to the old one, and the old one never got demolished.**

What's genuinely well-designed and must be kept: `CommandBase` (all 91 commands use it, zero bypasses), `ClientThreadHelper`, `InteractionSystem`, `StateExporter` (change-detection + atomic writes), `ResponseWriter`, `ScenarioModels`/the three-layer routine architecture, `Mouse.java`'s velocity-profile movement model (better than its "Bezier" label), the mcptools registry pattern, and the per-account file-namespacing scheme.

What's rotten is never the *idea* — it's that three generations of each idea run simultaneously.

## Scale reality check

| Claimed (docs) | Actual |
|---|---|
| "24 files" | **137 Java files, ~93,000 lines** |
| PlayerHelpers "large" | **30,129 lines**, 519 methods, 111 inline handlers, 39 nested classes — grew **8k lines after** its own refactor plan was written |
| — | GameEngine 10,914 lines (~800 verbatim self-duplicated) |
| — | **212-case dispatch switch** + 90-field hand-wired constructor |
| — | **12 backup files (5 MB)** tracked beside a working git repo |
| — | **105 MCP tools** (~40 would do) across 15 modules |
| — | **5 control planes**, 4 different sender implementations |

---

## Live bugs found (all verified with file:line evidence)

### Safety / stop paths — the scariest cluster
1. **`KILL` cannot stop most commands.** Only 5 of 91 commands check `shouldInterrupt`; 17 run uninterruptible sleep-loops (GE buys, shop loops). `Mouse.replay()` *swallows* `InterruptedException` — an in-flight mouse move is unstoppable.
2. **`STOP_PROCESSOR` is a no-op** — sets a flag the poll loop never reads.
3. **`KILL`'s task-cancel is dead code** — snapshots a null `Future` into an array at construction; always reports "no command task running."
4. **Stale interrupt flag** — after a `STOP` with nothing running, the *next* legitimate command instantly self-aborts.
5. **Every command is an implicit KILL** — `QUERY_INVENTORY` sent mid-`KILL_LOOP` cancels the combat loop. No read-only lane exists.

### Dispatch & lifecycle
6. **Switch fall-through:** `COLLECT_LUMBRIDGE_TIN_COPPER` has no body and falls into `FISH`.
7. **Plugin toggle bricks everything:** `shutDown()` terminates singleton executors that `startUp()` never recreates → next enable throws `RejectedExecutionException`; no commands, no state file, until client restart.
8. **Command file deleted on every region load** — `clearCommandFile()` runs on *every* `LOGGED_IN` transition (RuneLite fires it after each `LOADING`), silently eating any command in the 500ms poll window.

### IPC transport
9. **The MCP's "fast" response watcher never fires** — it listens for file-*modified* events but the plugin publishes via atomic *rename* (a *moved* event). Every awaited command burns its full 3s timeout even when answered in 200ms. The "50× latency optimization" runs permanently inverted.
10. **Single-slot mailbox:** two sends within a 500ms poll window → first command silently truncated. Known-and-documented as *agent folklore* ("Commands overwrite each other if sent too fast" — manny_driver/context.py:113) instead of fixed.
11. **Default-account schizophrenia:** `start_runelite` resolves default via `credentials.yaml` (→ namespaced `/tmp/manny_main_*`) while every tool resolves via `config.yaml` (→ un-namespaced `/tmp/manny_*`). Commands sent to a mailbox nobody reads; `send_command` still reports `dispatched: true`.
12. **Plugin-internal writers bypass namespacing** — level-up auto-equip, the STOP overlay, and widget inspectors write hardcoded `/tmp/manny_command.txt`: dead letters in namespaced mode, **cross-account command injection** otherwise (a mis-routed `EMERGENCY_STOP` in either direction).
13. **`run_routine.py` reads the previous command's response** — sleeps 100ms then reads, but the plugin polls at 500ms; masked by a bare `except`.

### Python server
14. **`get_logs` returns nothing, ever** — capture thread created but never started; stdout goes to a file nothing tails. The documented "#1 debugging step" has been dead since the PIPE→file swap.
15. **Duplicate method definition** shadows the real `cleanup_stale_sessions` (a one-line `ruff` catch; no linter configured).
16. **`time.sleep(3)` + 19 blocking `subprocess.run` calls inside async handlers** freeze the whole MCP server mid-tool-call.
17. **Dashboard streams live game video on `0.0.0.0:8080` with zero auth.**
18. `_kill_all_runelite` pkills by pattern — violating the project's own "NEVER pkill" rule (TODO in code admits it).

### Smaller landmines
- `Keyboard.java` shifted-symbol keycodes wrong across the number row (`'@'→VK_1`…) — silent because OSRS reads the typed char.
- `Mouse.hz` Gaussian can sample 0 → `ArithmeticException` on `1000/hz`.
- `CollisionDataLoader` "LRU" evicts an arbitrary map entry; `isWalkable` pessimistic-false vs `canWalkBetween` optimistic-true for the same unknown tile.
- `data/collision/` contains only a README on this machine — the extracted-cache pathfinding tier is empty (and unpopulatable elsewhere: hardcoded `/home/wil` path).
- `NavigationSystem` façade throws `UnsupportedOperationException` from both public methods.
- ScenarioEngine records every run as success in `finally` — failure statistics are dead data.

---

## The five structural themes

### 1 · Three generations of everything
- **Command dispatch:** 111 inline `handle*` methods (Gen 1) + 91 `CommandBase` classes (Gen 2) + a dead stub `CommandProcessor.java` (Gen 3) — all wired through one 212-case switch.
- **NPC clicking:** `Actions.NPCInteractionAction` vs `CombatSystem.clickNPC` vs `InteractionSystem.interactWithNPC` — three drifting implementations of the same idea (InteractionSystem's own comment admits it was copied from CombatSystem; the original was never retired).
- **Threading:** 139 raw `CountDownLatch` in PlayerHelpers + 75 in commands, despite `ClientThreadHelper` being the project's own #1 rule. Self-reported migration status ("76% complete") contradicts the live count.
- **Login state:** a `LoginState` enum that is written but never read; control flow still runs on six deprecated booleans.

### 2 · The IPC is fine as a *medium*, broken as *implemented*
File IPC with atomic renames, per-account namespacing, and rid correlation is genuinely adequate for an LLM-paced control loop — and `echo GOTO … > file` debuggability is load-bearing. But: single-slot mailbox, five writers with four sender implementations (one correlated, three "latest-wins"), the never-firing watchdog, and a namespace scheme that plugin-internal code itself bypasses. **The transport doesn't need replacing; it needs one implementation instead of five.**

### 3 · Silent failure as house style
`dispatched: true` unconditionally; bare `except:` masking IPC failures; 159 catch-log-continue in PlayerHelpers; command deleted with no NACK; dead poller with no heartbeat; `get_logs` returning `[]` indistinguishable from "no errors". The dominant failure class is *silent, unattributable loss* — which is uniquely poisonous when the operator is an AI agent that burns tokens re-diagnosing its own tools.

### 4 · Duplication clusters
GameEngine duplicates itself (~800 lines: `findNearestNPC` ×3, banking ×2); the GE command family (~4,400 lines, `findWidgetWithAction` ×4, "is GE open" ×7); the `MANNY_ACCOUNT_ID` resolution block copy-pasted in **6 places** and *omitted* in 5 others; scene→world conversion pasted per action type; ScenarioEngine's import block literally pasted three times; widget-scan implemented twice.

### 5 · Documentation actively misleads agents
"24 files" (137), "GameEngine = read-only" (it clicks and types), "add to switch" (steers agents into Gen-1 patterns), "CHECK LOGS first" (get_logs is dead), "state updates every ~600ms" (change-detection + 6s heartbeat), command reference missing dozens of implemented commands. For an AI-driven codebase, stale CLAUDE.md is not cosmetic — it is a live steering error.

---

## The plan

### Phase 0 — Stop the bleeding (a day; do before anything else)
Surgical fixes, no design changes:
1. Watchdog: handle `on_moved`/`dest_path` (`server.py:71-75`) → instantly un-inverts all awaited-command latency
2. `clearCommandFile` only on *first* login, not every region load (`MannyPlugin.java:696-703`)
3. Recreate executors in `startUp()` → plugin toggle survivable
4. Fix switch fall-through, `STOP_PROCESSOR` gate, `KILL` future (AtomicReference), stale-interrupt reset
5. `get_logs` → tail `self.log_file_path`
6. Single default-account resolver shared by config paths + instance lookup
7. `send_command` verifies delivery (file consumed) instead of unconditional `dispatched: true`
8. Delete the 12 backup files; fix stale `/home/wil/manny-mcp` shebangs + broken `LOCATIONS_DIR`; add `ruff` (catches the duplicate-method class forever)
9. Bind dashboard to localhost

### Phase 1 — One transport, one path scheme (2–3 days)
- **Java:** one `MannyPaths` class — base dir + account suffix in exactly one place; kills the 6 copy-pasted env blocks, the 3 `/home/wil` constants, and the internal-writer bypasses (level-up/STOP overlay call `executeCommand()` directly instead of looping through `/tmp`)
- **Python:** one `mcptools/transport.py` — atomic tmp+rename writes, rid correlation, per-account paths, delivery verification; MCP tools, `run_routine.py`, discord bot, and manny_driver all import it. The wire layer becomes singular; the policy layer stays plural.
- **Read-only command lane:** classify queries (GET_*, QUERY_*, SCAN_*) so they stop killing in-flight automation — precondition for "agent reads state while bot works," which is the whole premise.

### Phase 2 — Demolish the old homes (1–2 weeks, incremental)
- Command registry: `Map<String, CommandBase>` replaces the 212-case switch + 90-field constructor; migrate the 39 remaining inline handlers to `CommandBase`; delete the dead `CommandProcessor.java`; auto-generate LIST_COMMANDS + the command reference doc from the registry
- Interrupt support in `CommandBase` (`checkInterrupt()` helper) + fix `Mouse.replay()` interrupt swallowing → `KILL` actually kills
- `InteractionSystem` becomes the single click authority (retire `CombatSystem.clickNPC`, PlayerHelpers duplicates, the 3× pasted clickbox tracker)
- GameEngine: delete internal duplicates, move write-methods out → the documented read-only contract becomes true
- `GEInterfaceHelper` extraction (~4,400 → ~2,000 lines)
- MCP tool pruning 105 → ~40; de-async-block the server (`asyncio.to_thread`); dependency split into extras
- Regenerate both CLAUDE.mds from reality

### Phase 3 — Only when pulled by need
- **Actions retirement:** ScenarioEngine executes recorded *command strings* (recorder already emits COMMANDS mode); `Actions.java`'s 5,563 legacy-latch lines shrink to thin adapters
- **PlayerHelpers split** — becomes mechanical once Phases 1–2 hollow it out
- **One control plane:** driver/bot/CLI connect to a single long-lived server instead of spawning parallel ones
- **Unix-socket transport** — only if a trigger fires: >2 accounts routinely concurrent, measured command loss after Phase 1, or a sub-second-reaction feature. Keep the file channel compiled in as debug path forever.
- **Skip entirely:** HTTP (awkward for minutes-long blocking commands), WebSocket (solves a push problem nothing has)

---

## Rewrite-vs-refactor, explicitly

| Candidate | Verdict |
|---|---|
| Whole plugin | **No rewrite.** Sound skeleton, three unfinished migrations to complete |
| Transport | **No replacement yet** — harden files behind one sender; socket is a contained ~200-line Java acceptor *if* triggered |
| PlayerHelpers | Not rewritten — *evacuated*, then split mechanically |
| Actions layer | The one true rewrite-by-deletion candidate (Phase 3) |
| MCP server | Keep; fix transport + process ownership; prune tools |
| Docs | Full regeneration from code (auto-generate where possible) |

## MCP connection recommendation
Don't move sessions into `manny_mcp/`. Register user-scoped instead (`claude mcp add --scope user runelite-debug …`) so every session gets the tools — or keep driving via the file protocol from anywhere, which after Phase 1 is exactly as reliable as the MCP path (same transport class). The 105→40 tool pruning matters here: every session currently pays context for all 105 schemas.

---

*Full per-slice reports with complete file:line evidence available in the session; lessons journal at `manny_mcp/journals/`. Companion doc: [auto-login research](./manny-autologin-research.md).*
