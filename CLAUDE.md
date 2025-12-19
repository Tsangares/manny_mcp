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
- **get_screenshot**: Capture RuneLite window screenshot
- **analyze_screenshot**: Use Gemini AI to analyze game screenshot
- **check_health**: Verify process, state file, and window health

### Code Change Tools (Staging Workflow)

- **prepare_code_change**: Gather file contents, logs, and game state for a code-fixing subagent
- **validate_code_change**: Compile in staging directory (safe while RuneLite is running)
- **deploy_code_change**: Real build + restart signal

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

## Related Paths

- RuneLite source: `/home/wil/Desktop/runelite`
- Manny plugin source: `/home/wil/Desktop/manny` (symlinked as `manny_src`)

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

2. **Gather context** for the code-fixing subagent
   ```
   prepare_code_change(
     problem_description="Player gets stuck when pathfinding near obstacles...",
     relevant_files=["src/main/java/.../PathingManager.java"],
     logs="<error logs here>",
     game_state={...}
   )
   ```

3. **Spawn a Task subagent** to implement the fix
   ```
   Task(
     prompt="Fix this issue in the manny plugin. Context: {result from step 2}.
             Make minimal, targeted changes. Edit the files directly.",
     subagent_type="general-purpose"
   )
   ```

4. **Validate the changes** (safe - compiles in temp directory)
   ```
   validate_code_change(modified_files=["PathingManager.java"])
   ```
   - If errors: go back to step 3 with the error details
   - If success: proceed to deploy

5. **Deploy and restart**
   ```
   deploy_code_change(restart_after=True)
   stop_runelite()
   start_runelite()
   ```

6. **Test the fix** by observing game behavior

### Why This Workflow?

- **Safe validation**: `validate_code_change` compiles in a temp directory, so the running game instance is unaffected
- **Clean context**: The subagent gets only the relevant code, not your entire monitoring context
- **Separation of concerns**: Controller stays focused on testing, subagent focuses on code
- **No API key needed**: Uses Claude Code's Task tool, works with your Max subscription
