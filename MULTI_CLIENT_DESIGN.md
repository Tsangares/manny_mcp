# Multi-Client Architecture Design

## Overview

This document describes how to run multiple OSRS accounts simultaneously with the manny MCP system.

## Current Single-Client Architecture

```
┌─────────────┐     /tmp/manny_command.txt     ┌──────────────────┐
│  MCP Server │ ────────────────────────────►  │   RuneLite       │
│  (Python)   │                                │   + Manny Plugin │
│             │ ◄────────────────────────────  │   (Display :2)   │
└─────────────┘     /tmp/manny_state.json      └──────────────────┘
                    /tmp/manny_response.json
```

**Hardcoded paths:**
- Command file: `/tmp/manny_command.txt`
- State file: `/tmp/manny_state.json`
- Response file: `/tmp/manny_response.json`

**Single credentials via env vars:**
- `JX_CHARACTER_ID`
- `JX_DISPLAY_NAME`
- `JX_SESSION_ID`

## Multi-Client Architecture

```
┌─────────────┐     /tmp/manny_account1_command.txt     ┌──────────────────┐
│  MCP Server │ ──────────────────────────────────────► │   RuneLite #1    │
│  (Python)   │                                         │   Account: main  │
│             │ ◄────────────────────────────────────── │   (Display :2)   │
│             │     /tmp/manny_account1_state.json      └──────────────────┘
│             │
│             │     /tmp/manny_account2_command.txt     ┌──────────────────┐
│             │ ──────────────────────────────────────► │   RuneLite #2    │
│             │                                         │   Account: alt   │
│             │ ◄────────────────────────────────────── │   (Display :3)   │
└─────────────┘     /tmp/manny_account2_state.json      └──────────────────┘
```

## Implementation Plan

### 1. Configuration Changes (`config.yaml`)

```yaml
# Multi-account configuration
accounts:
  main:
    display: ":2"
    jx_character_id: "..."
    jx_display_name: "MainAccount"
    jx_session_id: "..."

  alt:
    display: ":3"
    jx_character_id: "..."
    jx_display_name: "AltAccount"
    jx_session_id: "..."

# Default account (for backwards compatibility)
default_account: main

# File path templates (use {account_id} placeholder)
command_file_template: /tmp/manny_{account_id}_command.txt
state_file_template: /tmp/manny_{account_id}_state.json
response_file_template: /tmp/manny_{account_id}_response.json
```

Credentials can also be stored in `.env` files per account:
```
# .env.main
JX_CHARACTER_ID_MAIN=...
JX_DISPLAY_NAME_MAIN=...
JX_SESSION_ID_MAIN=...

# .env.alt
JX_CHARACTER_ID_ALT=...
JX_DISPLAY_NAME_ALT=...
JX_SESSION_ID_ALT=...
```

### 2. RuneLiteManager Updates

**New MultiRuneLiteManager class:**

```python
class MultiRuneLiteManager:
    """Manages multiple RuneLite instances."""

    def __init__(self, config: ServerConfig):
        self.config = config
        self.instances: Dict[str, RuneLiteInstance] = {}

    def start_instance(self, account_id: str) -> Dict[str, Any]:
        """Start a RuneLite instance for the given account."""
        account_config = self.config.accounts[account_id]

        # Create instance with account-specific paths
        instance = RuneLiteInstance(
            account_id=account_id,
            display=account_config['display'],
            command_file=f"/tmp/manny_{account_id}_command.txt",
            state_file=f"/tmp/manny_{account_id}_state.json",
            credentials={
                'JX_CHARACTER_ID': account_config['jx_character_id'],
                'JX_DISPLAY_NAME': account_config['jx_display_name'],
                'JX_SESSION_ID': account_config['jx_session_id'],
            }
        )

        instance.start()
        self.instances[account_id] = instance
        return {"account_id": account_id, "pid": instance.pid}

    def stop_instance(self, account_id: str) -> Dict[str, Any]:
        """Stop a specific instance."""
        if account_id in self.instances:
            return self.instances[account_id].stop()
        return {"error": f"No instance for account: {account_id}"}

    def get_instance(self, account_id: str) -> Optional[RuneLiteInstance]:
        """Get instance by account ID."""
        return self.instances.get(account_id)

    def list_instances(self) -> List[Dict[str, Any]]:
        """List all running instances."""
        return [
            {"account_id": aid, "pid": inst.pid, "running": inst.is_running()}
            for aid, inst in self.instances.items()
        ]
```

### 3. MCP Tool Updates

Add optional `account_id` parameter to all client-specific tools:

```python
# Before (single client)
async def send_command(command: str) -> Dict[str, Any]:
    with open("/tmp/manny_command.txt", "w") as f:
        f.write(command)

# After (multi-client with backward compatibility)
async def send_command(command: str, account_id: str = None) -> Dict[str, Any]:
    # Use default account if not specified
    account_id = account_id or config.default_account

    command_file = f"/tmp/manny_{account_id}_command.txt"
    with open(command_file, "w") as f:
        f.write(command)
```

**Tools that need `account_id` parameter:**
- `send_command`
- `get_game_state`
- `get_command_response`
- `get_logs`
- `get_screenshot`
- `analyze_screenshot`
- `check_health`
- `start_runelite`
- `stop_runelite`
- `runelite_status`
- `scan_widgets`
- `get_dialogue`
- `click_text`
- `click_continue`
- `query_nearby`
- `send_input`

### 4. Plugin Changes (Java)

Make file paths configurable via environment variables:

```java
// CommandProcessor.java
public class CommandProcessor {
    private final String commandFile;

    public CommandProcessor() {
        // Use env var if set, otherwise default
        String accountId = System.getenv("MANNY_ACCOUNT_ID");
        if (accountId != null && !accountId.isEmpty()) {
            this.commandFile = "/tmp/manny_" + accountId + "_command.txt";
        } else {
            this.commandFile = "/tmp/manny_command.txt";  // Backward compatible
        }
    }
}

// ResponseWriter.java
public class ResponseWriter {
    private final String responseFile;

    public ResponseWriter() {
        String accountId = System.getenv("MANNY_ACCOUNT_ID");
        if (accountId != null && !accountId.isEmpty()) {
            this.responseFile = "/tmp/manny_" + accountId + "_response.json";
        } else {
            this.responseFile = "/tmp/manny_response.json";
        }
    }
}

// GameStateWriter (wherever state is written)
// Similar pattern for state file
```

### 5. Display Setup

Each client needs its own X11 display. Options:

**Option A: Multiple Weston instances**
```bash
# Display :2 for account 1
weston --socket=wayland-2 --xwayland &

# Display :3 for account 2
weston --socket=wayland-3 --xwayland &
```

**Option B: Multiple Xvfb instances**
```bash
Xvfb :2 -screen 0 1920x1080x24 &
Xvfb :3 -screen 0 1920x1080x24 &
```

**Option C: Xpra for remote viewing**
```bash
xpra start :2 --start=runelite-account1
xpra start :3 --start=runelite-account2
```

### 6. Dashboard Updates

The dashboard needs to support viewing multiple clients:

- Tab or dropdown to select active client
- Split view option to see multiple clients
- Per-client state display
- Aggregate stats across all clients

## Usage Examples

### Starting Multiple Clients

```python
# Via MCP tools
start_runelite(account_id="main")
start_runelite(account_id="alt")

# Check status
list_runelite_instances()
# Returns: [
#   {"account_id": "main", "pid": 12345, "running": true},
#   {"account_id": "alt", "pid": 12346, "running": true}
# ]
```

### Sending Commands to Specific Clients

```python
# Fish on main account
send_command("FISH_DRAYNOR_LOOP 20", account_id="main")

# Mine on alt account
send_command("MINE_ORE Copper", account_id="alt")

# Check states
get_game_state(account_id="main")
get_game_state(account_id="alt")
```

### Coordinated Multi-Account Actions

```python
# Trade between accounts
# 1. Navigate both to same location
send_command("GOTO 3200 3200 0", account_id="main")
send_command("GOTO 3200 3201 0", account_id="alt")

# 2. Wait for both to arrive
while True:
    main_state = get_game_state(account_id="main")
    alt_state = get_game_state(account_id="alt")
    if main_state['arrived'] and alt_state['arrived']:
        break
    sleep(1)

# 3. Initiate trade
send_command("TRADE_PLAYER AltAccount", account_id="main")
```

## Migration Path

1. **Phase 1**: Add multi-client support with backward compatibility
   - Default to "default" account if no account_id specified
   - Existing single-client setups continue to work

2. **Phase 2**: Update dashboard for multi-client
   - Add client selector
   - Support viewing multiple streams

3. **Phase 3**: Add coordination features
   - Cross-account commands
   - Synchronized actions
   - Account groups for batch operations

## File Structure After Implementation

```
manny-mcp/
├── config.yaml              # Now includes accounts section
├── .env.main                # Main account credentials
├── .env.alt                 # Alt account credentials
├── mcptools/
│   ├── multi_manager.py     # NEW: MultiRuneLiteManager
│   ├── runelite_manager.py  # Updated: RuneLiteInstance class
│   └── ...
├── server.py                # Updated: Use MultiRuneLiteManager
└── ...

/tmp/
├── manny_main_command.txt
├── manny_main_state.json
├── manny_main_response.json
├── manny_alt_command.txt
├── manny_alt_state.json
└── manny_alt_response.json
```
