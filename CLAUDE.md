# CLAUDE.md

MCP server for autonomously building, deploying, running, and debugging RuneLite plugins. Plugin source is at `manny_src` (symlink to `/home/wil/Desktop/manny`).

## Autonomy Guidelines ⚡

**Be autonomous and decisive.** Don't ask for approval on technical decisions.

**You decide:** Implementation approach, architecture, refactoring, wrappers, edge cases.
**Ask user only about:** Fundamental requirement ambiguities, external system decisions.

For complex architectural decisions, use the `decision-maker` subagent instead of `AskUserQuestion`.

## Session Startup ⚡

1. Check gamescope displays: `./start_gamescopes.sh status`
2. If not running: `./start_gamescopes.sh`
3. Start RuneLite: `start_runelite(account_id="main", display=":2")`

### Display Rules (CRITICAL)

- **ALWAYS use gamescope displays** - Never raw X displays (no GPU accel, high CPU)
- **NEVER overlap accounts on the same display** - Each account gets its own display
- **User's main account** is typically on `:3` - don't use that display
- **ALWAYS use MCP `start_runelite`** - Never launch RuneLite via Bash (commands won't work)
- **NEVER `pkill` RuneLite** - Use `stop_runelite(account_id=...)` to stop specific accounts

## Command Debugging Workflow ⚡

Commands return `{"sent": true}` even if they parse arguments incorrectly. When something doesn't work:

```python
# 1. CHECK LOGS (not screenshots, not workarounds)
get_logs(level="ALL", since_seconds=30, grep="BANK")
# 2. CHECK EXAMPLES if format unclear
get_command_examples(command="BANK_WITHDRAW")
# 3. Retry with correct format
```

## Widget Clicking (CRITICAL) ⚡

**Use `CLICK_WIDGET <container_id> "<action>"` for UI buttons.** Atomic, reliable on Wayland.

```python
send_command('CLICK_WIDGET 30474266 "+10"')  # ✅ Atomic click
# ❌ NEVER: MOUSE_MOVE + MOUSE_CLICK (race condition)
```

## NEVER Use send_input Directly ⚡

`send_input` is a last-resort escape hatch. When tempted, instead:
1. Identify what command/tool failed
2. Describe the failure to the user
3. Propose fixing the underlying command/plugin code

## Routine Execution Protocol (CRITICAL) ⚡

**ALWAYS use `run_routine.py` to execute YAML routines. NEVER execute steps manually.**

### Step 1: Find an existing routine

Check `routines/` directory or see `ROUTINE_CATALOG.md`. Categories: skilling, combat, quests, utility, tutorial_island.

### Step 2: Run with `run_routine.py`

```bash
./run_routine.py routines/skilling/superheat_steel_bars.yaml --loops 10 --account main
```

Options: `--loops N`, `--start-step N`, `--account ID`, `--json`

Run in background for long routines:
```python
Bash("./run_routine.py routines/skilling/superheat_steel_bars.yaml --loops 10 --account main", run_in_background=True)
```

### Step 3: Monitor progress

```python
TaskOutput(task_id=..., block=False)
get_game_state(fields=["inventory", "location"])
```

**NEVER manually execute routine steps one-by-one** - wastes tokens, the runner handles loops/health/recovery/XP.

## Widget Discovery ⚡

| Tool | Tokens | Use Case |
|------|--------|----------|
| `find_widget(text="...")` | ~50-200 | **Primary** - search by text/name/item |
| `click_text("...")` | ~20 | Click widget by text |
| `click_widget_by_action(action="...")` | ~30 | Click by action (e.g., "Deposit inventory") |
| `scan_widgets(group=N)` | ~500-2k | Specific widget group |
| `scan_widgets()` | ~35k+ | **Last resort** - delegate to Haiku subagent |

## Working with Manny Plugin Code

Always use `manny_src` symlink: `Read("manny_src/utility/PlayerHelpers.java")`

Plugin has its own CLAUDE.md at `manny_src/CLAUDE.md`. Use `prepare_code_change()` which auto-includes guidelines.

## Available MCP Tools

### Core
`build_plugin`, `start_runelite`, `stop_runelite`, `get_logs`, `runelite_status`, `send_command`, `get_game_state`, `get_screenshot`, `analyze_screenshot`, `check_health`, `is_alive`, `auto_reconnect`

**Plugin Freeze Detection:** State file updates every ~600ms. If `check_health()` shows `age_seconds > 30`, plugin is frozen - restart needed.

**Filtered Game State:** Use `fields` parameter to reduce tokens by 80-90%:
```python
get_game_state(fields=["location"])              # Just position
get_game_state(fields=["location", "inventory"]) # Common case
```
Fields: `location`, `inventory`, `inventory_full`, `equipment`, `skills`, `dialogue`, `nearby`, `combat`, `health`, `scenario`, `gravestone`

### State-Aware Waiting
`send_and_await(command, await_condition)` replaces send_command + sleep + get_game_state.
Conditions: `plane:N`, `has_item:Name`, `no_item:Name`, `inventory_count:<=N`, `location:X,Y`, `idle`

### Code Change Tools
`prepare_code_change` → `validate_code_change` → `deploy_code_change`
Also: `backup_files`, `rollback_code_change`, `diagnose_issues`

### Plugin Navigation
`get_plugin_context`, `get_section`, `find_command`, `find_pattern`, `find_relevant_files`, `generate_command_template`, `check_anti_patterns`, `get_manny_guidelines`

### Code Intelligence
`find_usages(symbol)`, `find_definition(symbol)`, `get_call_graph(method)`, `run_tests(pattern)`

### Routine Building
`list_available_commands`, `get_command_examples`, `validate_routine_deep`, `scan_widgets`, `get_dialogue`, `click_text`, `click_continue`, `query_nearby`, `get_transitions`, `get_command_response`, `equip_item`, `scan_tile_objects`

### Ground Items
Items on tables/shelves are TileItems. Use `query_nearby(include_ground_items=True)` or `scan_tile_objects(object_name="Bucket")`, then `send_and_await("PICK_UP_ITEM Bucket", "has_item:Bucket")`.

### Death Recovery
```python
get_game_state(fields=["gravestone"])  # Check grave status
send_command("FIND_GRAVE")            # Locate gravestone
send_command("LOOT_GRAVE")            # Loot when within 15 tiles
```
Gravestones are NPCs (use `query_nearby`). Timer starts when exiting Death's Domain. See `routines/utility/death_escape.yaml` and `routines/utility/gravestone_retrieval.yaml`.

## Routine Building

```python
list_available_commands(search="FISH")        # 1. Discover
get_command_examples(command="BANK_OPEN")     # 2. Learn
# 3. Write your_routine.yaml
validate_routine_deep(routine_path="...")     # 4. Validate
```

**Pattern: Discover → Act → Verify** - Always scan (`query_nearby`, `find_widget`) before acting, verify with `get_dialogue()` / `get_command_response()` after.

Docs: `COMMAND_REFERENCE.md`, `TOOLS_USAGE_GUIDE.md`, `ROUTINE_CATALOG.md`

## Object Naming Rules (CRITICAL) ⚡

| Type | Convention | Example |
|------|------------|---------|
| Objects (INTERACT_OBJECT) | Underscores | `Large_door`, `Cooking_range`, `Spinning_wheel` |
| Items | Spaces | `Raw shrimps`, `Pot of flour` |

```python
# ❌ send_command("INTERACT_OBJECT Spinning wheel Spin")  # Parses wrong
# ✅ send_command("INTERACT_OBJECT Spinning_wheel Spin")
```

Always `scan_tile_objects("door")` first to get exact names.

## Indoor Navigation Protocol ⚡

**NEVER naively GOTO through buildings** - walls block paths, wrong doors trap you.

```python
# 1. Scan transitions
transitions = get_transitions(radius=15)  # Doors/stairs/ladders with state
# 2. Plan route through doors
# 3. Execute step by step, verify each move
send_command("INTERACT_OBJECT Large_door Open")
get_game_state()
send_and_await("GOTO 3212 3216 0", "location:3212,3216")
```

Pre-defined locations: `get_location_info(area="lumbridge_castle", room="kitchen")`

## Code Fix Workflow

1. `get_logs(level="ERROR")` + `get_game_state()` - identify problem
2. `backup_files(file_paths=[...])` - safety net
3. `prepare_code_change(problem_description=..., relevant_files=[...], compact=True)` - gather context
4. Spawn subagent with context + "Read manny_src/CLAUDE.md" + "Use check_anti_patterns"
5. `validate_code_change` → `deploy_code_change(restart_after=True)` → test

Common pitfalls detected by `check_anti_patterns`: smartClick for NPCs, manual GameObject boilerplate, F-key tab switching, missing interrupt checks, forgetting ResponseWriter, manual CountDownLatch.

## Session Recording

Commands auto-logged to `/tmp/manny_sessions/commands_YYYY-MM-DD.yaml`. Use `get_command_history()`.

For full state tracking: `start_session_recording()` → execute → `stop_session_recording()` → `session_to_routine()`.

Location history at `/tmp/manny_<account>_location_history.json` - records moves, interactions, plane changes, door/dialogue events with coordinates.

## Multi-Account Management

Accounts: `main`, `alt1`, `alt2`. Credentials in `~/.manny/credentials.yaml`.
Add new: `import_credentials(alias="name", display_name="InGameName", set_default=True)`

Display pool: `:2` through `:5` (4 concurrent max). Auto-allocated or specify with `start_runelite(display=":3")`.

**12-hour playtime limit** per 24h window. Check: `get_playtime(account_id=...)`, `get_available_accounts()`.

Proxy: `start_runelite(proxy="socks5://user:pass@host:port")` or `set_account_proxy(alias, proxy)`. Note: proxychains + Java NIO is currently broken.

## Configuration

`config.yaml` for paths. Key: `runelite_root`, `display`, `command_file`, `state_file`.
Venv at `./venv/`. Dashboard: `./start_dashboard.sh` (port 8080).

## Model Selection

| Task | Model |
|------|-------|
| Code fixes, architecture | `opus`/`sonnet` |
| Log filtering, state summary | `haiku` |
| `scan_widgets()` calls | `haiku` (MANDATORY) |

## Subagent Compact Modes

Use `compact=True` for `prepare_code_change`, `summary_only=True` for `find_command`/`get_section` when spawning subagents with large files.

## UI Scaling Note

RuneLite uses `uiScale=2.0`. Widget bounds = logical pixels. Screen measurements = physical (2x). Divide visual measurements by 2.

## Session Journals

Write journals for **lessons for future agents** only (not activity logs). Focus on root causes, BAD/GOOD patterns, debugging techniques. Template: `journals/TEMPLATE.md`.

## Routine Monitoring

You are a **monitor**, not executor. Poll `get_game_state()` every 30-60s. Intervene only if: idle >60s, 3+ consecutive errors, stuck. Don't intervene for: click retries, brief pauses.

## YAML Await Conditions

- **Blocking commands (MINE_ORE, etc.):** Remove `await_condition` - runner waits for plugin response
- **Instant commands (GOTO, INTERACT_OBJECT):** Use state checks (`location:X,Y`, `has_item:Name`)
- **NEVER use `idle` as await for blocking commands** - triggers instantly before command starts

## Related Paths

- RuneLite source: `/home/wil/Desktop/runelite`
- Manny plugin: `manny_src` → `/home/wil/Desktop/manny`
- Discord bot logs: `logs/conversations/`
- Commands reference: `COMMAND_REFERENCE.md`
