# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is an MCP (Model Context Protocol) server that enables Claude Code to autonomously build, deploy, run, and debug RuneLite plugins. The server provides tools for the full development feedback loop: build → run → observe → iterate.

The linked `manny_src` directory points to the manny RuneLite plugin at `/home/wil/Desktop/manny`.

## Autonomy Guidelines ⚡

**Be autonomous and decisive.** Don't ask for approval on technical decisions.

**You decide:** Implementation approach, architecture, refactoring, wrappers, edge cases.
**Ask user only about:** Fundamental requirement ambiguities, external system decisions.

**Pattern:** Analyze → Check existing patterns → Make decision → Implement → Document briefly.

For complex architectural decisions, use the `decision-maker` subagent instead of `AskUserQuestion`.

## Command Debugging Workflow ⚡

**When a command doesn't work as expected, follow this pattern:**

```python
# 1. CHECK LOGS IMMEDIATELY (not screenshots, not workarounds)
get_logs(level="ALL", since_seconds=30, grep="BANK")  # or relevant command

# 2. If format unclear, CHECK EXAMPLES
get_command_examples(command="BANK_WITHDRAW")

# 3. Then retry with correct format
```

**Why this matters:** Commands return `{"sent": true}` even if they parse arguments incorrectly. The logs show exactly what the plugin parsed. Don't assume the command format - verify it.

**Anti-pattern (wastes 10+ tool calls):**
```python
send_command("BANK_WITHDRAW 27 Raw lobster")  # Wrong order!
# Sees nothing happen...
find_widget("lobster")  # ❌ Rabbit hole
click_text("All")       # ❌ More rabbit holes
send_input(click, x, y) # ❌ Even more rabbit holes
```

**Correct pattern (2-3 tool calls):**
```python
send_command("BANK_WITHDRAW 27 Raw lobster")  # Wrong order
# Sees nothing happen...
get_logs(grep="BANK")  # Shows: "Item name: '27 Raw lobster'" - AH!
get_command_examples(command="BANK_WITHDRAW")  # Shows correct format
send_command("BANK_WITHDRAW Raw lobster 27")  # Fixed!
```

## Widget Clicking (CRITICAL) ⚡

**ALWAYS use `CLICK_WIDGET <container_id> "<action>"` for clicking UI buttons.**

This finds the child widget by action text and clicks it atomically. Works reliably on Wayland + UI scaling.

```python
# ✅ CORRECT - atomic child widget click
send_command('CLICK_WIDGET 30474266 "+10"')      # GE quantity +10
send_command('CLICK_WIDGET 30474266 "+5%"')      # GE price +5%
send_command('CLICK_WIDGET 30474264 "Collect-item"')  # Collect from GE

# ❌ WRONG - coordinate clicking is unreliable
send_command("MOUSE_MOVE 92 212")   # Commands race
send_command("MOUSE_CLICK left")    # Click lands elsewhere

# ❌ WRONG - clickWidgetWithParam clicks parent center, not button
# (internal method issue - don't use for GE buttons)
```

**Why this matters:** Separate MOUSE_MOVE + MOUSE_CLICK commands race and cancel each other. Coordinate-based clicking is unreliable on Wayland with UI scaling. The `CLICK_WIDGET` command handles everything atomically.

## Widget Discovery ⚡

Use lightweight tools first: `find_widget(text="...")` and `click_text("...")` are fast (~100ms). Only use `scan_widgets` as a last resort via Haiku subagent (returns ~35k tokens). **Never use `--deep` flag** - times out.

## Working with Manny Plugin Code

**IMPORTANT:** Always use the `manny_src` symlink for accessing plugin code:

```python
# ✅ GOOD - Relative paths via symlink
Read("manny_src/utility/PlayerHelpers.java")
Edit(file_path="manny_src/CLAUDE.md", ...)
Glob("manny_src/**/*.java")

# ❌ AVOID - Absolute paths
Read("/home/wil/Desktop/manny/utility/PlayerHelpers.java")
```

**Quick navigation:** See `.claude/workspace-nav.md` for common paths and workflows.

**Context access:** The manny plugin has its own CLAUDE.md at `manny_src/CLAUDE.md`. When making code changes:
- Read it directly: `Read("manny_src/CLAUDE.md")`
- Use `prepare_code_change()` which auto-includes condensed guidelines

## Performance Optimizations ⚡

This MCP server has been optimized for production use:

- **10x faster builds** - Incremental compilation (30s vs 5min)
- **500x faster commands** - Event-driven file monitoring
- **1,000x faster searches** - Indexed code navigation
- **938x faster queries** - LRU caching
- **90% less I/O** - Smart state change detection
- **99% smaller context** - Intelligent file sectioning

All optimizations are automatic. No configuration needed.

**Documentation:** See `OPTIMIZATION_QUICK_REFERENCE.md` (start here!) and `OPTIMIZATIONS.md`.

**Quick monitoring:**
```bash
./monitor.py --metric all      # Show all performance metrics
./monitor.py --watch           # Live monitoring mode
```

## Available Skills

This project has specialized skills for autonomous Claude Code sessions:

### diagnose-performance
Proactively check performance health and suggest optimizations.

**Use when:** Performance issues, after implementing features, periodically during long sessions.

### fix-manny-plugin
Fix bugs and issues in the manny plugin codebase.

**Use when:** Code changes needed to fix observed bugs or add features.

## Architecture

```
┌─────────────────┐     stdio/http      ┌──────────────────────┐
│   Claude Code   │ ◄─────────────────► │   RuneLite MCP       │
└─────────────────┘                     │   Server (Python)    │
                                        └──────────┬───────────┘
                                                   │
                    ┌──────────────────────────────┼──────────────────────────────┐
                    │                              │                              │
                    ▼                              ▼                              ▼
            ┌───────────────┐            ┌─────────────────┐            ┌─────────────────┐
            │  Maven Build  │            │ RuneLite Process│            │  Session State  │
            │  (subprocess) │            │ (managed proc)  │            │  (JSON file)    │
            └───────────────┘            └─────────────────┘            └─────────────────┘
```

## Available MCP Tools

### Core Tools
- **build_plugin**: Compile the manny plugin
- **start_runelite**: Launch RuneLite on display :2
- **stop_runelite**: Stop the managed RuneLite process
- **get_logs**: Get filtered logs (by level, time, grep, plugin_only)
- **runelite_status**: Check if RuneLite is running
- **send_command**: Write command to `/tmp/manny_command.txt`
- **get_game_state**: Read game state from `/tmp/manny_state.json` (supports `fields` parameter)
- **get_screenshot**: Capture RuneLite window screenshot
- **analyze_screenshot**: Use Gemini AI to analyze game screenshot
- **check_health**: Verify process, state file, and window health
- **is_alive**: Fast crash check (<1 second) - use for quick polling
- **auto_reconnect**: Automatically handle disconnection (click OK, wait for reconnect)

**Detecting Plugin Freeze:**

The state file (`/tmp/manny_state.json`) is updated every GameTick (~600ms). If it becomes stale, the plugin has frozen.

```python
health = check_health()
stale_seconds = health["state_file"]["age_seconds"]

if stale_seconds > 30:
    # Plugin frozen - restart required
    start_runelite()
```

**Staleness thresholds:**
- < 5 seconds: Normal
- 5-30 seconds: Possible lag or loading screen
- > 30 seconds: Plugin frozen, restart needed

**Filtered Game State (Token Optimization):**

Use the `fields` parameter to request only specific data and reduce token usage by 80-90%:

```python
# Just check position (~3 lines instead of ~400)
get_game_state(fields=["location"])
# Returns: {"state": {"location": {"x": 3250, "y": 3194, "plane": 0}}}

# Quest automation common case (~30 lines)
get_game_state(fields=["location", "inventory", "dialogue"])

# Compact inventory (names only, not full item details)
get_game_state(fields=["inventory"])
# Returns: {"state": {"inventory": {"used": 12, "items": ["Law rune x288", "Air rune x91", ...]}}}
```

**Available fields:** `location`, `inventory` (compact), `inventory_full`, `equipment`, `skills`, `dialogue`, `nearby`, `combat`, `health`, `scenario`

### State-Aware Waiting Tools ⚡

Use `send_and_await(command, await_condition)` instead of `send_command` + `sleep` + `get_game_state`. Reduces tool calls by 70%.

**Conditions:** `plane:N`, `has_item:Name`, `no_item:Name`, `inventory_count:<=N`, `location:X,Y`, `idle`

### Code Change Tools
- **prepare_code_change**: Gather context for code-fixing subagent (auto-includes CLAUDE.md guidelines)
- **validate_code_change**: Compile to verify changes work
- **deploy_code_change**: Real build + restart signal
- **backup_files**: Create backups before modifications
- **rollback_code_change**: Restore files from backup if fix fails
- **diagnose_issues**: Analyze logs and game state to detect issues

### Manny Plugin Navigation Tools
- **get_plugin_context**: Get architectural context (architecture, wrappers, commands)
- **get_section**: Navigate large files by section markers
- **find_command**: Find command's switch case AND handler method
- **find_pattern**: Search for patterns (command, wrapper, thread, anti_pattern, custom)
- **find_relevant_files**: Search plugin source by class name, search term, or error message
- **generate_command_template**: Generate skeleton command handler
- **check_anti_patterns**: Scan code for known anti-patterns
- **get_manny_guidelines**: Get development guidelines (full/condensed/section modes)

### Code Intelligence Tools
IDE-like features for navigating and understanding code:

- **find_usages**: Find all usages of a symbol (method, class, field) with context
- **find_definition**: Jump to definition of a symbol (class, method, field)
- **get_call_graph**: Show what a method calls and what calls it (call graph analysis)
- **run_tests**: Execute Maven tests with pattern matching

Examples:
```python
# Find where a method is used
find_usages(symbol="interactWithNPC", context_lines=3)

# Jump to a class definition
find_definition(symbol="GameEngine", symbol_type="class")

# Analyze method dependencies
get_call_graph(method="handleBankOpen", depth=2)

# Run specific tests
run_tests(pattern="PathingManagerTest")
```

### Routine Building Tools
Discover game state, find interactable elements, and verify actions:

- **list_available_commands**: Discover all 90 commands instantly
- **get_command_examples**: Learn from existing routines
- **validate_routine_deep**: Pre-flight error checking with typo suggestions
- **scan_widgets**: Scan all visible widgets (IDs, text, bounds)
- **get_dialogue**: Check if dialogue is open, get options (optimized: ~15 lines, not ~800)
- **click_text**: Find a widget by text and click it
- **click_continue**: Click "Click here to continue" in dialogues
- **query_nearby**: Get nearby NPCs, objects, and ground items with available actions
- **get_transitions**: Find all navigable transitions (doors, stairs, ladders, etc.) with open/closed state
- **get_command_response**: Read last response from plugin
- **equip_item**: Equip an item from inventory (auto-detects Wear/Wield action)

### Ground Item Interaction
To pick up items on the ground (including items on tables/shelves which are TileItems):

1. **Discover ground items:**
   ```python
   query_nearby(include_ground_items=True)
   # Or use scan_tile_objects for detailed info:
   scan_tile_objects(object_name="Bucket")
   ```

2. **Pick up the item:**
   ```python
   send_and_await(
       command="PICK_UP_ITEM Bucket",
       await_condition="has_item:Bucket",
       timeout_ms=10000
   )
   ```

**Note:** Items displayed on tables (like buckets in Lumbridge cellar) appear as GroundItems with "Take" action. Use `PICK_UP_ITEM <itemName>` to collect them.

## Routine Building

**Quick workflow:** Use new MCP tools for 12x faster routine creation (5 min vs 55 min) with 90% error prevention.

```python
# 1. Discover (30 sec)
list_available_commands(search="FISH")

# 2. Learn (1 min)
get_command_examples(command="FISH_DRAYNOR_LOOP")

# 3. Create (3 min) - Write your_routine.yaml

# 4. Validate (30 sec)
validate_routine_deep(routine_path="your_routine.yaml")
```

**Documentation:** See `TOOLS_USAGE_GUIDE.md`, `COMMAND_REFERENCE.md`, and `ROUTINE_CATALOG.md`.

**Pattern: Discover → Act → Verify**

```python
# 1. DISCOVER: What's available?
query_nearby(name_filter="Cook")
find_widget(text="What's wrong")  # Lightweight alternative to scan_widgets
get_dialogue()

# 2. ACT: Do something
send_command("INTERACT_NPC Cook Talk-to")
click_text("What's wrong?")
click_continue()

# 3. VERIFY: Did it work?
get_dialogue()
get_command_response()
```

**Key Principles:**
1. Always verify - Check responses and game state
2. Use game data, not positions - Prefer `click_text("...")` over `send_input(click, x, y)`
3. Scan before acting - Use `query_nearby` and `find_widget()` first
4. Handle failures - If `click_text` fails, use `find_widget()` or delegate `scan_widgets` to Haiku subagent (see "High-Token MCP Tools" section)

## Session Recording (Create Routines from Manual Play) ⚡

**Commands are ALWAYS logged** to `/tmp/manny_sessions/commands_YYYY-MM-DD.yaml`. Use `get_command_history()` to review.

**For full state tracking** (inventory, location, dialogue deltas), use explicit session recording:

1. `start_session_recording(goal="Complete quest X")` - Begin recording
2. Execute commands manually (auto-recorded with state deltas)
3. `add_session_marker(label="Phase 2")` - Add checkpoints (optional)
4. `stop_session_recording()` - Save to YAML file
5. `session_to_routine(session_path="...")` - Convert to routine

**When to use:** First time doing a quest, debugging failed runs, creating new routines faster than writing YAML from scratch.

## Quest Automation (YAML Hybrid Approach) ⚡

1. **Research** - Look up quest on OSRS wiki (`WebFetch` the quick guide)
2. **Create YAML** - Write `routines/quests/<quest_name>.yaml` with items, locations, steps
3. **Execute + Revise** - Run steps, fix YAML as you discover issues
4. **Document pitfalls** - Add comments about what went wrong

**Key tips:**
- Use `dialogue.hint` from game state (not screenshots) to decide `click_continue()` vs `click_text("option")`
- Mark coordinates `validated: true` after confirming they work
- Use underscores for multi-word object names in commands

**Reference:** See `routines/quests/sheep_shearer.yaml` for a validated example.

## Indoor Navigation Protocol

**CRITICAL:** Indoor navigation requires spatial awareness. NEVER naively click toward a destination inside buildings.

### The Problem

Inside buildings (castles, houses, dungeons):
- Walls block direct paths
- Multiple doors may exist - wrong door = trapped in wrong room
- Object names vary ("Door" vs "Large_door" vs "Trapdoor")

### The Protocol

**BEFORE any indoor navigation:**

```python
# 1. SCAN: Find all transitions (preferred - more efficient)
transitions = get_transitions(radius=15)
# Returns: categorized doors/stairs/ladders with open/closed state and direction
# Example response:
# {
#   "summary": "Found 2 doors, 1 stair nearby. 1 door closed.",
#   "transitions": {
#     "doors": [{"name": "Large_door", "direction": "north", "state": "closed", ...}],
#     "stairs": [{"name": "Staircase", "direction": "east", "actions": ["Climb-up"], ...}]
#   }
# }

# Alternative: Use scan_environment for full context (NPCs, objects of interest)
env = scan_environment(radius=15)
# Returns: player position, doors with directions, objects of interest

# 2. UNDERSTAND: Build mental model
# - "I am at (3211, 3218)"
# - "Target (Cooking range) is south at (3212, 3215)"
# - "Doors: Large_door (north), Door (west)"
# - "Wall blocks direct path to target"

# 3. PLAN: Route through doors
# - "To reach range (south), exit via Large_door (north) first"
# - "Walk around to kitchen entrance"

# 4. EXECUTE: Step by step
send_command("INTERACT_OBJECT Large_door Open")  # Open correct door
get_game_state()  # Verify door opened
send_and_await("GOTO 3212 3216 0", "location:3212,3216")  # Walk to destination
```

### Object Naming Rules (CRITICAL FOR INTERACT_OBJECT) ⚡

**ALWAYS use underscores for multi-word object names in INTERACT_OBJECT commands!**

| Type | Convention | Example |
|------|------------|---------|
| Objects | Underscores for multi-word | `Large_door`, `Cooking_range`, `Spinning_wheel` |
| Items | Spaces | `Raw shrimps`, `Pot of flour` |

**Before sending INTERACT_OBJECT, ALWAYS review the object name for spaces:**
```python
# ❌ WRONG - spaces cause parsing errors
send_command("INTERACT_OBJECT Spinning wheel Spin")  # Parses as object="Spinning", action="wheel Spin"

# ✅ CORRECT - underscores for multi-word objects
send_command("INTERACT_OBJECT Spinning_wheel Spin")  # Parses correctly
send_command("INTERACT_OBJECT Large_door Open")
send_command("INTERACT_OBJECT Cooking_range Cook")
```

**ALWAYS scan first** to get exact names:
```python
scan_tile_objects("door")  # Find: "Large_door", "Door", "Trapdoor"
scan_tile_objects("range")  # Find: "Cooking range" (exact name)
```

### Anti-Patterns (NEVER DO)

```python
# ❌ BAD: Click toward destination through walls
send_command("GOTO 3212 3215 0")  # Fails - wall in the way

# ❌ BAD: Open "nearest door" without checking
send_command("INTERACT_OBJECT Door Open")  # Might be wrong door!

# ❌ BAD: Assume object names
send_command("INTERACT_OBJECT Range Cook")  # Wrong - it's "Cooking_range"
```

### Correct Pattern

```python
# ✅ GOOD: Scan → Plan → Execute → Verify
transitions = get_transitions()  # Preferred for finding doors/stairs
# Response: {"summary": "Found 1 door, 1 stair. Door is closed (north).", ...}

# Plan: Exit north, walk around, enter kitchen
send_command("INTERACT_OBJECT Large_door Open")
get_game_state()  # Verify position changed

send_and_await("GOTO 3212 3220 0", "location:3212,3220")  # Walk to hallway
send_and_await("GOTO 3212 3216 0", "location:3212,3216")  # Walk to kitchen
send_command("INTERACT_OBJECT Cooking_range Cook")
```

### Location Knowledge

Pre-defined locations are available via `get_location_info()`:
```python
get_location_info(area="lumbridge_castle", room="kitchen")
# Returns: center coords, key objects, nearby doors, connections
```

See `data/locations/lumbridge.yaml` for defined locations.

## Code Fix Workflow

When you observe a bug requiring code changes to the manny plugin:

### Quick Steps

1. **Identify the problem**
   ```
   get_logs(level="ERROR", since_seconds=60)
   get_game_state()
   ```

2. **Backup files** (for rollback if needed)
   ```
   backup_files(file_paths=["/path/to/File.java"])
   ```

3. **Gather context** (auto-includes CLAUDE.md!)
   ```
   prepare_code_change(
     problem_description="Player gets stuck when pathfinding...",
     relevant_files=["src/.../PathingManager.java"],
     logs="<error logs>",
     game_state={...},
     compact=True  # For large files - subagent uses Read tool
   )
   ```

4. **Spawn subagent** to implement the fix
   ```
   Task(
     prompt="Fix this issue in the manny plugin.
             CRITICAL:
             1. Read /home/wil/Desktop/manny/CLAUDE.md for complete guidelines
             2. Use check_anti_patterns to validate changes BEFORE responding
             3. Make minimal, targeted changes

             Context: {result from step 3}",
     subagent_type="general-purpose"
   )
   ```

5. **Validate** → **Deploy** → **Test**
   ```
   validate_code_change(modified_files=["File.java"])
   check_anti_patterns(file_path="/path/to/File.java")
   deploy_code_change(restart_after=True)
   # Test by observing game behavior
   ```

### Why This Workflow?

- **Rich context**: `prepare_code_change` auto-includes CLAUDE.md, architecture, wrappers
- **Safety net**: `backup_files` + `rollback_code_change` let you undo broken fixes
- **Automated validation**: `check_anti_patterns` catches common mistakes before deployment

## Common Pitfalls

The `check_anti_patterns` tool detects these automatically:

1. **Using smartClick() for NPCs** → Use `interactionSystem.interactWithNPC(name, action)`
2. **Manual GameObject boilerplate** → Use `interactionSystem.interactWithGameObject(name, action, radius)`
3. **F-key usage for tab switching** → Use tab widget IDs instead
4. **Missing interrupt checks in loops** → Add `shouldInterrupt` check in loop body
5. **Forgetting ResponseWriter** → Always call `responseWriter.writeSuccess/writeFailure`
6. **Manual CountDownLatch** → Use `helper.readFromClient(() -> ...)`
7. **Manual menu verification for widgets** → Use `playerHelpers.smartMoveToWidget(widgetId, expectedTarget)` - auto-verifies hover and corrects with movePrecisely if Bezier misses

**See examples:** Read manny_src/CLAUDE.md for detailed examples and fixes.

**Update this registry:** When you discover new recurring mistakes, add them to manny_src/CLAUDE.md and update the `check_anti_patterns` tool.

## Efficient Subagent Usage

MCP tools can return large responses. Use "compact" and "summary" modes for subagents:

| Tool | Option | Effect |
|------|--------|--------|
| `prepare_code_change` | `compact=true` | Returns file metadata only. Subagent uses Read tool. |
| `find_command` | `summary_only=true` | Returns line numbers and signatures only. |
| `get_section` | `summary_only=true` | Returns line ranges only. |

**Pattern:**
```python
# Compact context for subagent
context = prepare_code_change(..., compact=True)

# Subagent uses Read tool to fetch only what it needs
Task(prompt=f"Context: {context}. Use Read tool for file contents.")
```

**When to use compact mode:**
- Files are large (>500 lines)
- Multiple files needed
- Subagent only modifies small section

## Model Selection & Large Outputs

| Task Type | Model |
|-----------|-------|
| Code fixes, architecture decisions | `opus` or `sonnet` |
| Log filtering, state summarization, finding files | `haiku` |
| Writing routines, debugging | `sonnet` |
| **`scan_widgets` calls** | **`haiku` (MANDATORY)** |

**REMINDER:** See "High-Token MCP Tools (MANDATORY)" section at top of this file. Never call `scan_widgets` directly - always delegate to Haiku subagent.

## Setup

Dependencies are in a venv:

```bash
# Already done - venv exists at ./venv/
./venv/bin/pip install -r requirements.txt
```

## Configuration

Edit `config.yaml` to customize paths. Key settings:

- `runelite_root`: RuneLite repo path (for Maven builds)
- `display`: X11 display for RuneLite (default `:2`)
- `command_file`: Where to write commands (`/tmp/manny_command.txt`)
- `state_file`: Where plugin writes state (`/tmp/manny_state.json`)

## Multi-Account Management

The MCP supports multiple OSRS accounts with automatic credential management, display allocation, and playtime tracking.

### Configured Accounts

| Alias | Display Name | Role |
|-------|--------------|------|
| `aux` | LOSTimposter | Secondary account |
| `main` | ArmAndALegs | Primary account (default) |

### Credentials

Credentials are stored in `~/.manny/credentials.yaml`. Only identity fields are needed (NOT tokens):
- `jx_character_id` - Account identifier
- `jx_session_id` - Session identifier
- `display_name` - In-game name

**To add a new account:**
1. Log into the account via Bolt launcher
2. Run: `import_credentials(alias="name", display_name="InGameName", set_default=True)`

### Multi-Display Support

Each client runs on a separate X display to avoid mouse conflicts:
- Display pool: `:2`, `:3`, `:4`, `:5` (4 concurrent max)
- Auto-allocated when starting: `start_runelite(account_id="aux")`
- Or specify manually: `start_runelite(account_id="aux", display=":3")`

### CRITICAL: Stopping Clients Safely ⚠️

**NEVER use `pkill` or broad kill commands that affect all RuneLite clients!**

```python
# ❌ DANGEROUS - Kills ALL RuneLite clients (including main!)
Bash("pkill -f runelite")  # NEVER DO THIS
Bash("pkill -f RuneLite")  # NEVER DO THIS
Bash('pkill -f "runelite-client.*RuneLite"')  # NEVER DO THIS

# ✅ CORRECT - Kill specific PID only
Bash("kill 12345")  # Kill specific process by PID

# ✅ BEST - Use MCP tool
stop_runelite(account_id="aux")  # Stops only the specified account
```

**Why this matters:** Multiple accounts run simultaneously on different displays. A broad `pkill` kills ALL clients, disrupting other accounts the user may be actively using.

### Playtime Tracking

**12-hour limit per 24-hour window** per account to prevent excessive play.

- Tracked automatically in `~/.manny/sessions.yaml`
- Check with: `get_playtime(account_id="aux")`
- View all: `get_available_accounts()`

If an account exceeds the limit, `start_runelite` will refuse to start until playtime resets.

## Prerequisites

Run `./start_screen.sh` first to start a virtual display on `:2`. RuneLite runs on this display to avoid blocking the laptop's main screen.

**CRITICAL: ALWAYS use MCP `start_runelite` to launch RuneLite!**

```python
# ✅ CORRECT - Use MCP tool to start RuneLite
start_runelite()  # Manages process, enables commands, tracks state

# ❌ WRONG - Never start RuneLite manually or via Bash
# Bash("cd /path/to/runelite && mvn exec:java...")  # Won't be managed!
```

**Why this matters:**
- MCP-managed RuneLite enables command execution via `/tmp/manny_command.txt`
- Screenshots via `get_screenshot()` only work with MCP-managed processes
- State tracking and health checks require MCP management
- Manual starts result in commands being ignored

**Signs commands aren't executing:**
- `send_command()` returns success but nothing happens in-game
- State file exists but isn't updating
- No log activity after commands
- Screenshots fail with "Can't open X display"

## Dashboard

Start or restart the web dashboard:

```bash
./start_dashboard.sh
```

The dashboard runs on `http://0.0.0.0:8080` with live video stream, game state, MCP activity log, and player stats.

## Related Paths

- RuneLite source: `/home/wil/Desktop/runelite`
- Manny plugin source: `/home/wil/Desktop/manny` (symlinked as `manny_src`)

## Screenshots and Video Capture

**Window Dimensions:** 1592x1006

**Screenshots:** Use ImageMagick (works with Weston/XWayland)
```bash
DISPLAY=:2 import -window $(xdotool search --name "RuneLite" | head -1) output.png
```

**Screenshot Modes:**
- **Viewport Mode (892x1006)**: Game viewport only (3D world + chatbox)
- **Fullscreen Mode**: Complete RuneLite window with all UI elements (better for AI analysis)

MCP tools (`get_screenshot`, `analyze_screenshot`) use fullscreen by default for better context.

**UI Scaling Note:**

RuneLite runs with `-Dsun.java2d.uiScale=2.0`. This affects coordinate calculations:
- Widget bounds are in **logical pixels** (pre-scaled)
- Screen measurements are in **physical pixels** (2x logical)
- A 24px screen measurement = 12 logical pixels in code

When debugging coordinate issues, remember to divide visual measurements by 2.

## Discovering Manny Plugin Commands

### Method 1: Use MCP tools
```python
list_available_commands(search="FISH")  # Discover all 90 commands
get_command_examples(command="BANK_OPEN")  # See real usage
```

### Method 2: Search source code
```bash
grep -n 'case "' manny_src/utility/PlayerHelpers.java | head -50
```

### Method 3: Check documentation
Read `COMMAND_REFERENCE.md` for all 90 commands organized by category.

## Session Journals

Write journals to capture **lessons for future agents**, not activity logs.

**Template:** See `journals/TEMPLATE.md` for structure and examples.

**When to write:**
- Discovered a bug with non-obvious root cause
- Found a pattern that works after significant debugging
- Identified an interface gap (MCP↔Plugin↔Game)

**Don't write:** Session stats, level progress, play-by-play, routine successful runs.

**Focus on:**
- Root cause analysis with code references
- BAD vs GOOD patterns with examples
- Debugging techniques that helped
- Interface boundaries and gaps

**Naming:** `<problem>_lessons_<date>.md` (e.g., `deposit_box_lessons_2025-01-08.md`)

## Effective Routine Monitoring

You are a **monitor**, not the executor. Poll `get_game_state()` every 30-60 seconds. Only check logs when state indicates a problem.

**Intervene if:** Idle but task incomplete, stuck >60 seconds, 3+ consecutive errors.
**Don't intervene for:** Click retries, brief pauses, duplicate thread logs.

Use `send_and_await` for discrete actions. Use periodic polling for long-running loops.
