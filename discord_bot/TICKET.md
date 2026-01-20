# Discord Bot for OSRS Automation Control

## Overview

This Discord bot provides a chat interface to control the OSRS automation system remotely. Users DM the bot to check status, run routines, and give natural language commands that an LLM interprets.

## Goal

Replace the need for Claude Code / terminal access for routine bot management. User should be able to:
- Check bot status from phone
- Start/stop routines
- Get screenshots
- Ask natural language questions ("go fish", "what's my inventory?")
- Receive alerts when something goes wrong

## Architecture

```
User (Discord DM)
       ↓
Discord Bot (bot.py)
       ↓
LLM Client (llm_client.py) ←→ Gemini Flash API
       ↓
MCP Tools (direct Python import)
       ↓
RuneLite + Manny Plugin
```

The Discord bot runs on the same VPS as RuneLite. It imports MCP tools directly (no protocol overhead).

## Current Implementation

### Files Created

```
manny-mcp/
├── discord_bot/
│   ├── bot.py          # Discord client, command handlers, tool executor
│   ├── llm_client.py   # Gemini/Claude/OpenAI wrapper with function calling
│   ├── CONTEXT.md      # LLM system prompt (edit to customize behavior)
│   └── TICKET.md       # This file
├── run_discord.py      # Entry point
└── .env                # Tokens (gitignored)
```

### Working Features

- [x] Discord connection and DM handling
- [x] Prefix commands: `!status`, `!screenshot`, `!stop`, `!run`, `!routines`
- [x] LLM client with Gemini 2.5 Flash Lite
- [x] Natural language message handling (sends to LLM)
- [x] Owner restriction (optional)
- [x] Conversation history per user
- [x] Multi-account switching: `!switch`, `!accounts`
- [x] Help command: `!help`
- [x] **LLM Function Calling** - Gemini can directly invoke MCP tools
- [x] **CONTEXT.md** - Configurable system prompt for LLM

### LLM Tools Available

The LLM can use these tools via function calling:
- `get_game_state` - Player location, inventory, health
- `get_screenshot` - Capture game screenshot
- `check_health` - Client health check
- `send_command` - Send plugin commands
- `start_runelite` / `stop_runelite` / `restart_runelite` - Client control
- `auto_reconnect` - Handle disconnections
- `run_routine` / `list_routines` - Routine management
- `get_logs` - Plugin logs for debugging
- `switch_account` / `list_accounts` - Account management

### Not Yet Tested / May Need Work

- [ ] Screenshot sending via Discord (xdotool required)
- [ ] Routine execution through bot
- [ ] Error handling and recovery
- [ ] Proactive alerts (bot messages user when something breaks)

## Configuration

### Environment Variables (.env)

```bash
DISCORD_TOKEN=xxx        # Discord bot token
GEMINI_API_KEY=xxx       # Gemini API key
BOT_OWNER_ID=xxx         # Optional: restrict to one Discord user
```

### Command Line

```bash
python run_discord.py --account aux --provider gemini
```

- `--account`: Which OSRS account to control (default: aux)
- `--provider`: LLM provider - gemini/claude/openai (default: gemini)
- `--owner`: Discord user ID to restrict access

## MCP Tool Integration

The bot imports tools from `mcptools.tools`:

```python
from mcptools.tools import monitoring, commands, routine
```

Key functions to call:
- `monitoring.handle_check_health({"account_id": "aux"})` - Health check
- `monitoring.handle_get_game_state({"account_id": "aux", "fields": [...]})` - Game state
- `monitoring.handle_get_screenshot({"account_id": "aux"})` - Screenshot
- `commands.handle_send_command({"command": "STOP", "account_id": "aux"})` - Send command
- `routine.handle_execute_routine({"routine_path": "...", "account_id": "aux"})` - Run routine

### Dependency Initialization

Tools need dependencies set before use:

```python
from mcptools.config import ServerConfig
from mcptools.runelite_manager import MultiRuneLiteManager

config = ServerConfig.load()
manager = MultiRuneLiteManager(config)

monitoring.set_dependencies(manager, config)
commands.set_dependencies(manager, config)
routine.set_dependencies(manager, config)
```

This happens in `bot._load_tools()` - may need debugging.

## LLM Behavior

The LLM (Gemini Flash) receives:
1. System prompt with available routines and actions
2. Current game state summary (location, health, inventory)
3. User's message
4. Conversation history

It should respond conversationally and optionally suggest actions like:
- `run_routine combat/hill_giants.yaml 5`
- `!stop`

The bot parses these and auto-executes if found.

## Commands Reference

| Command | Description |
|---------|-------------|
| `!help` | Show all available commands |
| `!status` | Get bot status, location, health, inventory |
| `!screenshot` | Send a screenshot of the game |
| `!accounts` | List available accounts |
| `!switch <account>` | Switch to a different account (e.g., `!switch main`) |
| `!stop` | Stop current activity |
| `!run <routine> [loops]` | Run a routine (e.g., `!run combat/hill_giants 5`) |
| `!routines` | List available routines |
| (natural text) | Sent to LLM for interpretation |

## Future Enhancements

1. **Proactive Alerts** - Bot DMs user when:
   - Bot dies
   - Bot gets stuck
   - Routine completes
   - Disconnection detected

2. **Status Embeds** - Rich Discord embeds with:
   - Health bar
   - Inventory summary
   - Mini-map or location

3. ~~**Multi-Account** - Switch accounts mid-conversation:~~ ✅ DONE
   - `!switch main` - switches active account
   - `!accounts` - lists available accounts

4. **Scheduled Routines** - Run routines on a schedule:
   - `!schedule fishing 2h`
   - `!schedule stop 23:00`

5. **Ollama Support** - Local LLM option for free operation

## Testing Checklist

1. [ ] Bot responds to `!status`
2. [ ] Bot responds to natural language
3. [ ] `!screenshot` sends image
4. [ ] `!run` starts a routine
5. [ ] `!stop` stops activity
6. [ ] LLM correctly summarizes game state
7. [ ] LLM suggests appropriate routines
8. [ ] Error messages are helpful
9. [ ] `!help` shows all commands
10. [ ] `!accounts` lists available accounts
11. [ ] `!switch` changes active account

## Known Issues / Debugging

### If tools fail to load:
Check that `config.yaml` exists and is valid. The ServerConfig needs:
- `runelite_root` or `runelite_jar` path
- `display` setting
- Account configurations

### If bot doesn't respond to DMs:
- Ensure "Message Content Intent" is enabled in Discord Developer Portal
- Check bot is actually online (green dot)
- Check logs for errors

### If Gemini fails:
- Verify `GEMINI_API_KEY` is set
- Check API quota at https://makersuite.google.com/

## Contact

This bot was scaffolded to work with the manny-mcp OSRS automation system. See main `CLAUDE.md` for full system documentation.
