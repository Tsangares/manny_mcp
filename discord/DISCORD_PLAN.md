# Discord Remote Control - Implementation Plan

**Last Updated:** 2026-01-21

## Overview

Remote OSRS client control via Discord with LLM-powered natural language interface. Supports task queuing with conditional execution (level-based triggers, inventory conditions, etc.).

## Architecture

```
Phone/Desktop Discord
        │
        ▼
   Discord Bot (Python)
        │
        ├──► Task Manager ──► Task Queue (conditional execution)
        │         │
        │         ▼
        │    Capability Registry (dynamic command discovery)
        │
        ▼
   LLM Client
   ├─ Primary: Ollama (qwen2.5:14b-multi via WireGuard)
   └─ Fallback: Gemini (gemini-2.0-flash-lite)
        │
        ▼
   MCP Tools ──────► Tool calls
        │
        ▼
   RuneLite (Xvfb :2)
        │
        ▼
   VNC (x11vnc :5902)
```

## Current Status

### Completed
- [x] Basic slash commands (/status, /screenshot, /stop, etc.)
- [x] Natural language via LLM (Ollama primary, Gemini fallback)
- [x] Screenshot capture (ImageMagick import)
- [x] GIF recording (ffmpeg)
- [x] Conversation history/memory
- [x] Multi-account support
- [x] Task queue with conditional execution
- [x] Combat rotation scheduling
- [x] Capability registry (dynamic command discovery)
- [x] Training data collection for fine-tuning
- [x] WireGuard VPN to local LLM server

### In Progress
- [ ] Fine-tuning smaller model (7B) for reliable tool calling
- [ ] Claude Code session parser for training data

### Future
- [ ] Video streaming
- [ ] Permission system (owner only)
- [ ] Web dashboard integration

## LLM Configuration

### Primary: Ollama (Local via WireGuard)
```bash
# WireGuard connects to 10.66.66.10 (local server with GPU)
OLLAMA_HOST=http://10.66.66.10:11434
OLLAMA_MODEL=qwen2.5:14b-multi
```

### Fallback: Gemini
```bash
GEMINI_API_KEY=your_key
# Model: gemini-2.0-flash-lite
```

The bot automatically falls back to Gemini if Ollama is unavailable.

## Slash Commands

### Status & Info
| Command | Description |
|---------|-------------|
| `/status` | Bot status, location, health, inventory |
| `/screenshot` | Capture game screenshot |
| `/gif [duration]` | Record GIF (default 5s, max 15s) |
| `/accounts` | List available accounts |
| `/help` | Show all commands |

### Control
| Command | Description |
|---------|-------------|
| `/stop` | Stop current activity |
| `/kill` | Kill all RuneLite instances |
| `/restart` | Kill and restart RuneLite |
| `/switch <account>` | Switch OSRS account |
| `/run <routine> [loops]` | Run automation routine |
| `/routines` | List available routines |

### Task Queue
| Command | Description |
|---------|-------------|
| `/queue` | Show queued tasks and status |
| `/queue_task <command>` | Queue a command for execution |
| `/queue_on_level <skill> <level> <command>` | Queue for level condition |
| `/queue_rotation` | Set up combat style rotation |
| `/clear_queue` | Clear all pending tasks |
| `/capabilities [category] [keyword]` | List available commands |

### Natural Language (DM)
Just type naturally:
- "Did the client crash?"
- "What's in my inventory?"
- "Go fish at draynor"
- "When I hit 40 strength, switch to defence"
- "Set up combat rotation to 40 all melee stats"

## Task Queue System

### Conditional Execution
The task queue monitors game state and triggers actions when conditions are met:

```python
# Queue a style switch for when strength hits 40
/queue_on_level strength 40 SET_ATTACK_STYLE defensive

# Set up full combat rotation
/queue_rotation str_until:40 att_until:40 def_until:40
```

### Condition Types
| Condition | Description |
|-----------|-------------|
| `level_reached` | Skill reaches target level |
| `level_up` | Any level up in a skill |
| `inventory_full` | Inventory at capacity |
| `inventory_has` | Has specific item |
| `health_below` | HP below threshold |
| `task_completed` | Another task finished |
| `idle` | Player is idle |

### Capability Registry
Commands are dynamically discovered and categorized:
- **Combat:** KILL_LOOP, ATTACK_NPC, SET_ATTACK_STYLE
- **Skilling:** FISH_DRAYNOR_LOOP, COOK_ALL
- **Banking:** BANK_OPEN, BANK_DEPOSIT_ALL, BANK_WITHDRAW
- **Navigation:** GOTO
- **System:** STOP, KILL, WAIT

## Training Data Collection

### Purpose
Collect interaction data to fine-tune a smaller model (7B) that reliably executes tools instead of describing them.

### Data Locations
| Source | Location | Format |
|--------|----------|--------|
| Discord interactions | `~/.manny/training_data/training_YYYY-MM-DD.jsonl` | JSONL |
| Raw commands | `/tmp/manny_sessions/commands_YYYY-MM-DD.yaml` | YAML |
| Conversation logs | `~/manny-mcp/logs/conversations/` | JSONL |
| Claude Code sessions | `~/.claude/projects/-home-wil-manny-mcp/*.jsonl` | JSONL |

### Training Data Format
```json
{
  "input": {
    "user_message": "Kill 300 giant frogs",
    "task_type": "loop_command",
    "game_state": {"location": [3200, 3170, 0], "health": [35, 35]}
  },
  "expected_actions": [
    {"tool": "send_command", "args": {"command": "KILL_LOOP Giant_frog none 300"}}
  ],
  "quality": {
    "success": true,
    "described_instead_of_executed": false
  }
}
```

See `plans/FINE_TUNING_PLAN.md` for full details.

## Files Structure

```
discord_bot/
├── bot.py                  # Main Discord bot
├── llm_client.py           # LLM abstraction (Ollama/Gemini)
├── agent_brain.py          # Task classification, context enrichment
├── task_manager.py         # High-level task orchestration
├── task_queue.py           # Conditional task execution
├── capability_registry.py  # Dynamic command discovery
├── training_logger.py      # Training data collection
├── conversation_logger.py  # Conversation logging
├── locations.py            # Location database
└── CONTEXT.md              # System prompt for LLM
```

## Systemd Services

Location: `~/.config/systemd/user/`

| Service | Purpose | Status |
|---------|---------|--------|
| `xvfb.service` | Virtual display :2 | Optional (local has real display) |
| `x11vnc.service` | VNC on :5902 | Optional |
| `discord-bot.service` | Discord bot | Active |

### discord-bot.service
```ini
[Unit]
Description=OSRS Discord Bot
After=network.target

[Service]
Type=simple
WorkingDirectory=/home/wil/manny-mcp
ExecStart=/home/wil/manny-mcp/venv/bin/python /home/wil/manny-mcp/run_discord.py --account aux --provider ollama
Restart=always
RestartSec=10
MemoryHigh=1.7G
MemoryMax=2G

[Install]
WantedBy=default.target
```

### Commands
```bash
systemctl --user daemon-reload
systemctl --user restart discord-bot
systemctl --user status discord-bot
journalctl --user -u discord-bot -f
```

## Configuration

### ~/manny-mcp/.env
```bash
# Ollama (via WireGuard)
OLLAMA_HOST=http://10.66.66.10:11434
OLLAMA_MODEL=qwen2.5:14b-multi

# Gemini fallback
GEMINI_API_KEY=your_key

# Discord
DISCORD_TOKEN=your_token
DISCORD_GUILD_ID=your_guild_id  # Optional: for instant command sync
```

### ~/.manny/credentials.yaml
```yaml
default_account: aux
accounts:
  aux:
    jx_character_id: "..."
    jx_session_id: "..."
    display_name: "LOSTimposter"
  main:
    jx_character_id: "..."
    jx_session_id: "..."
    display_name: "ArmAndALegs"
```

## Troubleshooting

### LLM describes tools instead of executing them
This is the main issue driving the fine-tuning effort. Current mitigations:
1. Explicit instructions in CONTEXT.md
2. Training data collection for fine-tuning
3. Gemini fallback (sometimes more reliable)

### Bot OOM killed
```bash
# Check memory usage
systemctl --user status discord-bot

# Service has MemoryMax=2G limit
# If still OOM, reduce conversation history or add swap
```

### Slash commands not appearing
- Global commands take up to 1 hour to propagate
- Set `DISCORD_GUILD_ID` for instant guild-specific sync
- Restart bot: `systemctl --user restart discord-bot`

### Ollama connection failed
```bash
# Check WireGuard
wg show

# Check Ollama reachable
curl http://10.66.66.10:11434/api/tags

# Bot will auto-fallback to Gemini
```

### Task queue not executing
```bash
# Check logs for task manager
journalctl --user -u discord-bot | grep -i task

# Verify queue status
# In Discord: /queue
```

## Next Steps

1. **Collect ~2000 training examples** via normal Discord usage
2. **Build Claude Code session parser** for additional training data
3. **Fine-tune Qwen2.5-7B** with QLoRA
4. **Evaluate** tool execution rate, accuracy
5. **Deploy** fine-tuned model to Ollama
