# RuneLite Debug MCP Server

## Overview

An MCP server that enables Claude Code to autonomously build, deploy, run, and debug RuneLite plugins without human facilitation. The server exposes tools for the full development feedback loop: build → run → observe → iterate.

## Problem

Current workflow requires a human to:
1. Run the plugin in RuneLite
2. Observe behavior or copy debug output
3. Paste logs into Claude Code
4. Apply fixes
5. Repeat

This creates friction and limits Claude's ability to iterate independently. Additionally, verbose debug logs quickly bloat the context window, causing Claude to lose track of earlier attempts.

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

The MCP server runs on the same machine as RuneLite (your laptop). Claude Code connects to it and invokes tools to drive the debugging loop.

## Core Tools

### 1. `build_plugin`

Runs Maven to compile the plugin.

**Input:**
- `clean`: boolean, whether to run clean first (default: true)

**Output:**
- `success`: boolean
- `build_time_seconds`: float
- `errors`: list of compiler errors with file, line, message
- `warnings`: list of compiler warnings (truncated to first 10)

**Implementation notes:**
- Run `mvn clean package` or `mvn package` in the plugin directory
- Parse Maven output for `[ERROR]` and `[WARNING]` lines
- Extract structured error info (file path, line number, error message)
- Return structured data, not raw Maven output

### 2. `start_runelite`

Launches RuneLite with the plugin loaded, or restarts if already running.

**Input:**
- `developer_mode`: boolean, enable RuneLite developer mode (default: true)
- `plugin_config`: optional dict of plugin configuration overrides

**Output:**
- `pid`: int, process ID
- `status`: "started" | "restarted"
- `startup_logs`: first 50 lines of output (for catching immediate crashes)

**Implementation notes:**
- Kill existing RuneLite process if running (track PID in state)
- Launch RuneLite JAR with appropriate flags
- Capture stdout/stderr to a ring buffer or temp file
- Wait briefly for startup, return early logs to catch immediate failures

### 3. `stop_runelite`

Stops the managed RuneLite process.

**Output:**
- `stopped`: boolean
- `exit_code`: int or null if killed

### 4. `get_logs`

Retrieves logs from the running RuneLite process.

**Input:**
- `level`: "DEBUG" | "INFO" | "WARN" | "ERROR" | "ALL" (default: "WARN")
- `since_seconds`: float, only logs from last N seconds (default: 30)
- `grep`: optional string, filter to lines containing this substring
- `max_lines`: int (default: 100)
- `plugin_only`: boolean, filter to only manny plugin logs (default: true)

**Output:**
- `lines`: list of log lines
- `truncated`: boolean, whether output was truncated
- `total_matching`: int, how many lines matched before truncation

**Implementation notes:**
- Read from the captured stdout/stderr buffer
- Apply filters server-side to minimize data sent to Claude
- Parse log format to extract level, timestamp, source
- The `plugin_only` filter should match on the plugin's logger name

### 5. `get_screenshot`

Captures the current RuneLite window.

**Input:**
- `parse`: boolean, whether to run image analysis (default: false)
- `region`: optional, crop to specific region ("game_view" | "inventory" | "minimap" | "full")

**Output:**
- `image_base64`: string, PNG encoded (if parse is false or as fallback)
- `parsed`: optional structured data if parse is true

**Parsed output structure (when parse=true):**
```json
{
  "player_tile": [x, y],
  "visible_npcs": [{"name": "...", "tile": [x, y]}, ...],
  "visible_objects": [...],
  "path_overlay": [[x1, y1], [x2, y2], ...],
  "minimap_position": [x, y],
  "errors_visible": boolean,
  "plugin_panel_state": {...}
}
```

**Implementation notes:**
- Use system screenshot tools or Java's Robot class via a helper
- For parsing, can use a combination of:
  - OCR for text elements
  - Color detection for known UI elements
  - Claude vision API for complex interpretation
- Start with just screenshots; add parsing incrementally

### 6. `send_command`

Sends a high-level command to the manny plugin (if it exposes a control interface).

**Input:**
- `command`: string, the command to send
- `args`: optional dict of arguments

**Output:**
- `acknowledged`: boolean
- `response`: optional string

**Implementation notes:**
- This requires the manny plugin to expose a command interface
- Could be via file watching, socket, or RuneLite's built-in plugin messaging
- Start simple: write command to a file the plugin watches

### 7. `get_session`

Retrieves the current debugging session state.

**Output:**
- `attempts`: list of previous attempts with timestamps, changes made, results
- `current_hypothesis`: string or null
- `known_issues`: list of identified but unfixed issues
- `last_successful_state`: description of last known-good state

### 8. `update_session`

Updates the session state with new information.

**Input:**
- `add_attempt`: optional, record a new debugging attempt
- `set_hypothesis`: optional string
- `add_known_issue`: optional string
- `mark_resolved`: optional string, issue to mark as resolved

**Implementation notes:**
- Session state persists to a JSON file
- This helps Claude maintain context across conversation turns
- Claude should update this after each meaningful debugging step

## Configuration

The MCP server needs to know:

```yaml
# runelite-mcp-config.yaml
plugin_directory: /path/to/manny-plugin
runelite_jar: /path/to/runelite-client.jar
java_path: java  # or full path
runelite_args:
  - "--developer-mode"
  - "--debug"
log_buffer_size: 10000  # lines to keep in memory
session_file: /path/to/debug-session.json
screenshot_method: scrot  # or "maim", "import", etc.
plugin_logger_prefix: "com.manny"  # for filtering logs
```

## Implementation Phases

### Phase 1: Core Loop (Start Here)

Implement these tools first to get the basic autonomous loop working:
- `build_plugin`
- `start_runelite`
- `stop_runelite`
- `get_logs`

This is enough for Claude to: build → run → check logs → fix → repeat.

### Phase 2: Visual Feedback

Add screenshot capability:
- `get_screenshot` (without parsing initially)

Claude can use vision to interpret screenshots when logs are insufficient.

### Phase 3: Session Management

Add context management to handle long debugging sessions:
- `get_session`
- `update_session`

### Phase 4: Structured Vision

Add image parsing to `get_screenshot` so Claude gets structured data instead of raw images for common checks.

### Phase 5: Direct Control

If the manny plugin exposes a control interface:
- `send_command`

This lets Claude trigger specific behaviors for testing.

## MCP Server Skeleton (Python)

```python
#!/usr/bin/env python3
"""RuneLite Debug MCP Server"""

import subprocess
import json
import threading
import time
from collections import deque
from pathlib import Path

# MCP protocol handling (use mcp library or implement stdio protocol)
from mcp.server import Server
from mcp.types import Tool, TextContent

class RuneLiteDebugServer:
    def __init__(self, config_path: str):
        self.config = self._load_config(config_path)
        self.runelite_process = None
        self.log_buffer = deque(maxlen=self.config["log_buffer_size"])
        self.log_lock = threading.Lock()
        self.session = self._load_session()
    
    def build_plugin(self, clean: bool = True) -> dict:
        cmd = ["mvn"]
        if clean:
            cmd.append("clean")
        cmd.append("package")
        
        result = subprocess.run(
            cmd,
            cwd=self.config["plugin_directory"],
            capture_output=True,
            text=True
        )
        
        errors = self._parse_maven_errors(result.stdout + result.stderr)
        
        return {
            "success": result.returncode == 0,
            "errors": errors,
            "warnings": self._parse_maven_warnings(result.stdout)[:10]
        }
    
    def start_runelite(self, developer_mode: bool = True) -> dict:
        # Stop existing if running
        if self.runelite_process:
            self.stop_runelite()
        
        cmd = [self.config["java_path"], "-jar", self.config["runelite_jar"]]
        cmd.extend(self.config.get("runelite_args", []))
        
        self.runelite_process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True
        )
        
        # Start log capture thread
        threading.Thread(target=self._capture_logs, daemon=True).start()
        
        # Wait briefly and capture startup logs
        time.sleep(3)
        
        with self.log_lock:
            startup_logs = list(self.log_buffer)[:50]
        
        return {
            "pid": self.runelite_process.pid,
            "status": "started",
            "startup_logs": startup_logs
        }
    
    def get_logs(
        self,
        level: str = "WARN",
        since_seconds: float = 30,
        grep: str = None,
        max_lines: int = 100,
        plugin_only: bool = True
    ) -> dict:
        # Implementation: filter log_buffer by criteria
        pass
    
    def get_screenshot(self, parse: bool = False, region: str = "full") -> dict:
        # Implementation: capture window, optionally parse
        pass
    
    # ... remaining methods ...

if __name__ == "__main__":
    server = RuneLiteDebugServer("runelite-mcp-config.yaml")
    # Run MCP server loop
```

## Claude Code Configuration

Add to Claude Code's MCP config (typically `~/.config/claude-code/mcp.json` or similar):

```json
{
  "mcpServers": {
    "runelite-debug": {
      "command": "python",
      "args": ["/path/to/runelite-mcp-server.py"],
      "env": {
        "RUNELITE_MCP_CONFIG": "/path/to/runelite-mcp-config.yaml"
      }
    }
  }
}
```

## Usage Pattern

Once configured, Claude Code can autonomously:

1. Check current state: `get_logs(level="ERROR", since_seconds=60)`
2. If issues found, analyze and make code changes
3. Rebuild: `build_plugin(clean=False)`
4. If build fails, fix errors and retry
5. Restart client: `start_runelite()`
6. Check for runtime errors: `get_logs(level="WARN", since_seconds=10)`
7. If visual verification needed: `get_screenshot(parse=True)`
8. Record attempt: `update_session(add_attempt={...})`
9. Repeat until issue resolved

## Notes

- Start with Phase 1; get the basic loop working before adding complexity
- The log filtering is critical for context management; tune the defaults based on how verbose the plugin is
- Consider adding a `run_test` tool if you create offline unit tests for pathfinding or other logic
- The session state is optional but very helpful for multi-turn debugging where Claude might lose context

## Open Questions

- Does the manny plugin already log to a specific file, or only stdout?
- What's the exact Maven command to build the plugin?
- Is there an existing way to send commands to the plugin at runtime?
- What visual elements are most important to parse (player position, path overlay, error states)?
