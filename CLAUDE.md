# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is an MCP (Model Context Protocol) server that enables Claude Code to autonomously build, deploy, run, and debug RuneLite plugins. The server provides tools for the full development feedback loop: build → run → observe → iterate.

The linked `manny_src` directory points to the manny RuneLite plugin at `/home/wil/Desktop/manny`.

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

- **build_plugin**: Compile the manny plugin (`mvn compile -pl runelite-client`)
- **start_runelite**: Launch RuneLite on display :2 via `mvn exec:java`
- **stop_runelite**: Stop the managed RuneLite process
- **get_logs**: Get filtered logs from RuneLite (by level, time, grep, plugin_only)
- **runelite_status**: Check if RuneLite is running
- **send_command**: Write command to `/tmp/manny_command.txt` for the manny plugin
- **get_game_state**: Read game state from `/tmp/manny_state.json`
- **get_screenshot**: Capture RuneLite window screenshot (fullscreen by default)
- **analyze_screenshot**: Use Gemini AI to analyze game screenshot (always fullscreen for better context)
- **check_health**: Verify process, state file, and window health

### Code Change Tools

- **prepare_code_change**: Gather file contents, logs, game state, AND manny guidelines for a code-fixing subagent. Auto-includes CLAUDE.md, architecture summary, and wrapper reference.
- **validate_code_change**: Compile to verify changes work. Use with backup_files/rollback_code_change for safety.
- **deploy_code_change**: Real build + restart signal
- **backup_files**: Create backups before modifications (for rollback)
- **rollback_code_change**: Restore files from backup if fix fails
- **diagnose_issues**: Analyze logs and game state to detect issues needing code fixes

### Manny Plugin Navigation Tools

- **get_plugin_context**: Get architectural context (architecture summary, available wrappers, command reference)
- **get_section**: Navigate large files by section markers. PlayerHelpers.java has sections like "SECTION 4: SKILLING OPERATIONS"
- **find_command**: Find a command's switch case AND handler method in PlayerHelpers.java
- **find_pattern**: Search for patterns: "command", "wrapper", "thread", "anti_pattern", or "custom"
- **find_relevant_files**: Search plugin source by class name, search term, or error message

### Code Generation Tools

- **generate_command_template**: Generate skeleton command handler following project patterns
- **check_anti_patterns**: Scan code for known anti-patterns (CountDownLatch, smartClick for NPCs, etc.)

### Routine Building Tools

These tools help you discover game state, find interactable elements, and verify actions worked:

- **scan_widgets**: Scan all visible widgets (returns IDs, text, bounds). Use `filter_text` to find specific elements.
- **get_dialogue**: Check if dialogue is open, get available options and their widget IDs.
- **click_text**: Find a widget by text and click it. Returns success/failure.
- **click_continue**: Click "Click here to continue" in dialogues.
- **query_nearby**: Get nearby NPCs and objects with their available actions.
- **get_command_response**: Read the last response from `/tmp/manny_response.json`.

## Routine Building Workflow

When building routines (multi-step automations), follow this pattern:

### 1. Discover → 2. Act → 3. Verify

```
# 1. DISCOVER: What's available?
query_nearby(name_filter="Cook")           → Find NPCs/objects
scan_widgets(filter_text="What's wrong")   → Find UI elements
get_dialogue()                              → Check dialogue state

# 2. ACT: Do something
send_command("INTERACT_NPC Cook Talk-to")  → Interact with game
click_text("What's wrong?")                 → Click dialogue option
click_continue()                            → Advance dialogue

# 3. VERIFY: Did it work?
get_dialogue()                              → Check new state
get_command_response()                      → Check last command result
```

### Example: Quest Dialogue

```
1. send_command("INTERACT_NPC Cook Talk-to")
2. Wait briefly, then get_dialogue()
   → {"dialogue_open": true, "has_continue": true}
3. click_continue()
   → {"success": true}
4. get_dialogue()
   → {"dialogue_open": true, "options": [{"text": "What's wrong?", ...}]}
5. click_text("What's wrong?")
   → {"success": true, "clicked": "What's wrong?"}
6. Repeat until quest started
```

### Key Principles

1. **Always verify** - Don't assume commands worked. Check the response or game state.
2. **Use game data, not positions** - Prefer `click_text("What's wrong?")` over `send_input(click, x=450, y=670)`.
3. **Scan before acting** - Use `query_nearby` and `scan_widgets` to discover what's available.
4. **Handle failures** - If `click_text` fails, try `scan_widgets` to see what text is actually visible.

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
- `runelite_args`: CLI args passed to RuneLite
- `command_file`: Where to write commands (`/tmp/manny_command.txt`)
- `state_file`: Where plugin writes state (`/tmp/manny_state.json`)

## Prerequisites

Run `./start_screen.sh` first to start a virtual display on `:2`. RuneLite runs on this display to avoid blocking the laptop's main screen.

## Dashboard

To start or restart the web dashboard:

```bash
./start_dashboard.sh
```

The dashboard runs on `http://0.0.0.0:8080` and provides:
- Live video stream of the game viewport (FFmpeg-based)
- Real-time game state display
- MCP activity log
- Player stats and health monitoring

## Related Paths

- RuneLite source: `/home/wil/Desktop/runelite`
- Manny plugin source: `/home/wil/Desktop/manny` (symlinked as `manny_src`)

## Capture Methods (Weston/XWayland Display :2)

**Current Window Dimensions:** 1592x1006

### Screenshots
- **Tool:** ImageMagick `import -window <window_id>`
- **Why:** Works with Weston/XWayland compositing (FFmpeg x11grab shows black)
- **Command:** `DISPLAY=:2 import -window $(xdotool search --name "RuneLite" | head -1) output.png`

### Video Capture
- **Issue:** FFmpeg x11grab doesn't work with Weston (captures black screen)
- **Workaround:** Capture frames with ImageMagick, encode with FFmpeg
- **Example:**
  ```bash
  # Capture frames in parallel
  window_id=$(DISPLAY=:2 xdotool search --name "RuneLite" | head -1)
  for i in $(seq 1 60); do
    DISPLAY=:2 import -window "$window_id" "frame_$(printf %04d $i).png" &
  done
  wait
  # Encode to video
  ffmpeg -framerate 20 -i frame_%04d.png -c:v libx264 -pix_fmt yuv420p output.mp4
  ```

### Viewport Crop (Game Area Only)
To crop to just the game viewport (3D world + chatbox, excluding minimap/inventory):
- **Dimensions:** 892x1006
- **Offset:** +0+0 (top-left)
- **Crop command:** `magick <input> -crop 892x1006+0+0 +repage <output>`

## Screenshot Modes

The MCP server supports two screenshot modes:

### Viewport Mode (892x1006 cropped)
- Captures only the game viewport (3D world + chatbox)
- Excludes minimap, inventory, stats, and right sidebar
- Coordinates: 892x1006+0+0
- Used by: Dashboard (when cropping enabled)

### Fullscreen Mode (entire window)
- Captures the complete RuneLite window with all UI elements
- Includes minimap, inventory, stats, chatbox, and all panels
- Used by: MCP tools (`get_screenshot`, `analyze_screenshot`)
- Better for AI analysis - provides full context

### Usage

**Dashboard**: Uses FFmpeg to capture viewport directly from X11 display
**get_screenshot**: Returns fullscreen by default (can be changed to viewport mode in future)
**analyze_screenshot**: Always uses fullscreen for better Gemini analysis context

The `take_screenshot()` function in `server.py` supports both modes via the `mode` parameter:
- `mode="fullscreen"` (default): Entire RuneLite window
- `mode="viewport"`: Cropped to game viewport using coordinates 1020x666+200+8

## Code Fix Workflow

When you observe a bug or issue that requires code changes to the manny plugin, follow this workflow. This keeps the controller Claude focused on testing while a subagent handles the actual code modifications.

### Architecture

```
┌─────────────────────────────────────┐
│  Controller Claude Code             │  ← You (uses MCP, monitors game)
│  - Observes game behavior           │
│  - Identifies issues                │
│  - Tests fixes                      │
└──────────────┬──────────────────────┘
               │
               │ prepare_code_change → context
               ▼
┌─────────────────────────────────────┐
│  Code-writing Subagent (Task tool)  │  ← Fresh context, edits files
│  - Analyzes problem                 │
│  - Makes targeted code changes      │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  Controller Claude Code             │
│  - validate_code_change (safe)      │  ← Compiles in temp dir
│  - deploy_code_change (rebuild)     │  ← Real build when ready
│  - Restart and test                 │
└─────────────────────────────────────┘
```

### Step-by-Step

1. **Identify the problem** via logs, game state, or observation
   ```
   get_logs(level="ERROR", since_seconds=60)
   get_game_state()
   ```

2. **Gather context** for the code-fixing subagent (now auto-includes CLAUDE.md!)
   ```
   prepare_code_change(
     problem_description="Player gets stuck when pathfinding near obstacles...",
     relevant_files=["src/main/java/.../PathingManager.java"],
     logs="<error logs here>",
     game_state={...}
   )
   ```

   This now automatically includes:
   - Full CLAUDE.md content (guidelines, anti-patterns, wrappers)
   - Architecture summary (READ/WRITE separation, thread safety)
   - Available wrappers reference

3. **Spawn a Task subagent** to implement the fix

   The context now includes all guidelines, so a simple prompt works:
   ```
   Task(
     prompt="Fix this issue in the manny plugin.

             The context includes manny_guidelines (CLAUDE.md), architecture_summary,
             and available_wrappers. Follow these patterns carefully.

             Context: {result from step 2}.
             Make minimal, targeted changes. Edit the files directly.",
     subagent_type="general-purpose"
   )
   ```

4. **Backup and validate** the changes
   ```
   backup_files(file_paths=["/path/to/modified/File.java"])
   validate_code_change(modified_files=["PathingManager.java"])
   ```
   - If errors: go back to step 3 with the error details
   - If success: proceed to deploy
   - If fix doesn't work: `rollback_code_change()` to restore originals

5. **Deploy and restart**
   ```
   deploy_code_change(restart_after=True)
   stop_runelite()
   start_runelite()
   ```

6. **Test the fix** by observing game behavior

### Why This Workflow?

- **Rich context**: `prepare_code_change` auto-includes CLAUDE.md, architecture summary, and wrappers
- **Safety net**: `backup_files` + `rollback_code_change` let you undo broken fixes
- **Clean context**: The subagent gets only the relevant code, not your entire monitoring context
- **Separation of concerns**: Controller stays focused on testing, subagent focuses on code

## Efficient Subagent Usage

**Problem**: MCP tools can return very large responses (full file contents, 100+ line methods, full guidelines). When passed to a subagent via the Task tool, this can overwhelm the subagent's context, causing:
- Context overflow and lost information
- Slow processing
- Incomplete fixes

**Solution**: Use the "compact" and "summary" modes for MCP tools when spawning subagents.

### MCP Tool Options for Subagents

| Tool | Option | Effect |
|------|--------|--------|
| `prepare_code_change` | `compact=true` | Returns file metadata (not contents), ultra-condensed guidelines. Subagent uses Read tool for files. |
| `prepare_code_change` | `max_file_lines=100` | Truncates each file to 100 lines |
| `find_command` | `summary_only=true` | Returns only line numbers and signatures. Subagent uses Read tool for code. |
| `find_command` | `max_handler_lines=30` | Truncates handler method to 30 lines |
| `get_section` | `summary_only=true` | Returns only line ranges. Subagent uses Read tool for content. |
| `get_section` | `max_lines=100` | Truncates section to 100 lines |

### Subagent Workflow Pattern

```python
# Step 1: Get compact context (small response for subagent prompt)
context = prepare_code_change(
    problem_description="...",
    relevant_files=["PlayerHelpers.java"],
    compact=True  # <-- KEY: Only returns file metadata
)

# Step 2: Spawn subagent with compact context
Task(
    prompt=f"""Fix this manny plugin issue.

    Context: {context}

    IMPORTANT: Use Read tool to access file contents.
    File paths are in file_paths list. Use offset/limit for large files.

    Make minimal, targeted changes.""",
    subagent_type="general-purpose"
)
```

The subagent will:
1. Receive the compact problem description and file metadata
2. Use the Read tool to fetch only the specific file sections it needs
3. Make targeted edits using the Edit tool

### When to Use Compact Mode

**USE compact mode when:**
- Files are large (>500 lines)
- You need to include multiple files
- The subagent only needs to modify a small section

**DON'T use compact mode when:**
- Files are small (<200 lines)
- The subagent needs full context to understand the issue
- You're debugging a complex multi-file interaction

## Discovering Manny Plugin Commands

The manny plugin accepts commands via `/tmp/manny_command.txt`. To discover available commands:

### Method 1: manny-cli help
```bash
# The manny plugin has a CLI with help options
manny-cli --help
```

### Method 2: Search source code
```bash
# Find command handlers in PlayerHelpers.java
grep -n 'case "' /home/wil/Desktop/manny/utility/PlayerHelpers.java | head -50

# Or search for specific command patterns
grep -rn "handleCommand\|case \"[A-Z]" /home/wil/Desktop/manny/utility/
```

### Method 3: Check CommandProcessor documentation
The file `/home/wil/Desktop/manny/utility/CommandProcessor.java` has a docstring listing supported commands at the top of the file.

**Note**: Don't store actual command lists here as they change frequently. Always use the methods above to get current commands.

## Session Journals

When running the manny client for extended periods (1+ hours), maintain session journals in the `journals/` directory.

### Purpose
Track high-level observations, fixes, and issues discovered during bot operation. This helps maintain institutional knowledge about:
- What works well
- What doesn't work and needs fixing
- Workarounds discovered
- Patterns observed

### Journal Format
Create journals named `<activity>_<date>.md` (e.g., `fishing_2025-12-19.md`).

Include:
- **Session goal**: What you're trying to accomplish
- **Current progress**: Levels, XP, location
- **High-level observations**: Navigation issues, interaction problems, timing issues
- **Things that work well**: Reliable patterns and commands
- **Things to fix**: Documented bugs and potential improvements
- **Session stats**: Trips completed, levels gained, etc.

### When to Update
- After discovering a significant issue or workaround
- After completing major milestones
- Before ending a long session
- When switching to a different activity

### Example
```markdown
# Fishing Session - 2025-12-19

## Navigation Issues
- Bank exit stuck detection triggers too often
- Workaround: Use intermediate waypoints

## Things To Fix
1. CountDownLatch blocking causing UI lag
2. Fishing spot click fails when >13 tiles away
```

## Effective Routine Monitoring

You are a **monitor**, not the executor. The manny plugin runs autonomously - your role is to observe, detect failures, and issue high-level commands.

### Token-Efficient Monitoring

- **Poll sparingly**: Check `get_game_state()` every 30-60 seconds during stable operation
- **Only dive into logs on failure**: Use `get_logs()` when state indicates a problem, not continuously
- **Trust the routine**: Don't analyze every "[FISH] Caught 1 fish" message - wait for meaningful state changes

### When to Intervene

**DO intervene:**
- Scenario shows "Idle" but task isn't complete
- Same position for >60 seconds with no progress
- 3+ consecutive errors in logs

**DON'T intervene:**
- Multiple threads logging the same action (normal thread contention)
- Occasional click retries (2/3 or 3/3 attempts is fine)
- Brief pauses between actions (natural RNG)

### Known Issues to Expect

1. **Thread contention**: 4 background threads compete for the same command. Causes duplicate logs and occasional click failures. The routine still works - just noisier.
2. **Navigation oscillation**: Distance may hover at same value before converging. Give it time.
3. **Click verification failures**: First attempt often fails, retry usually succeeds. This is normal.

### Effective Pattern

```
1. send_command("FISH_DRAYNOR_LOOP 45")
2. Wait 30-60 seconds
3. get_game_state() - check inventory, XP, location
4. If state changed meaningfully → log progress
5. If stuck/idle unexpectedly → check logs, restart if needed
6. Repeat until goal reached
```
