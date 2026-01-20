# Discord Remote Control - Implementation Plan

## Overview

Remote OSRS client control via Discord with LLM-powered natural language interface.

## Architecture

```
Phone/Desktop Discord
        │
        ▼
   Discord Bot (Python)
        │
        ▼
   LLM (Gemini) ──────► Tool calls
        │
        ▼
   MCP Server
        │
        ▼
   RuneLite (Xvfb :2)
        │
        ▼
   VNC (x11vnc :5902)
```

## Required System Packages

### Arch Linux
```bash
sudo pacman -S \
    jdk17-openjdk \
    python \
    python-pip \
    xorg-server-xvfb \
    x11vnc \
    xdotool \
    scrot \
    ffmpeg
```

### Ubuntu/Debian
```bash
sudo apt install \
    openjdk-17-jdk \
    python3 \
    python3-pip \
    xvfb \
    x11vnc \
    xdotool \
    scrot \
    ffmpeg
```

### Package Purposes
| Package | Purpose |
|---------|---------|
| `jdk17-openjdk` | Run RuneLite (Java 17) |
| `python` | MCP server, Discord bot |
| `xorg-server-xvfb` | Virtual display for headless RuneLite |
| `x11vnc` | VNC server for remote viewing |
| `xdotool` | Find window IDs for screenshots |
| `scrot` | Screenshot capture |
| `ffmpeg` | GIF/video recording |

## Python Dependencies

```bash
cd ~/manny-mcp
python -m venv venv
./venv/bin/pip install -r requirements.txt
```

Key packages: `discord.py`, `google-generativeai`, `pyyaml`, `mcp`

## Files to Transfer

From laptop to VPS:
```bash
rsync -avz ~/manny-mcp/ user@vps:~/manny-mcp/
scp ~/.manny/credentials.yaml user@vps:~/.manny/
scp ~/path/to/runelite-fat.jar user@vps:~/runelite.jar
```

## Systemd Services

Location: `~/.config/systemd/user/`

| Service | Purpose | After |
|---------|---------|-------|
| `xvfb.service` | Virtual display :2 | - |
| `x11vnc.service` | VNC on :5902 | xvfb |
| `runelite.service` | Game client | xvfb |
| `discord-bot.service` | Discord bot | runelite |

### Commands
```bash
systemctl --user daemon-reload
systemctl --user enable xvfb x11vnc runelite discord-bot
systemctl --user start xvfb x11vnc runelite discord-bot
systemctl --user status xvfb x11vnc runelite discord-bot
journalctl --user -u discord-bot -f
```

**Important:** Enable lingering for services to survive logout:
```bash
sudo loginctl enable-linger $USER
```

## Configuration Files

### ~/manny-mcp/config.yaml
```yaml
runelite_root: null
plugin_directory: null
runelite_jar: /home/wil/runelite.jar
use_exec_java: false
```

### ~/manny-mcp/.env
```bash
JX_CHARACTER_ID=your_id
JX_DISPLAY_NAME=your_name
JX_SESSION_ID=your_session
GEMINI_API_KEY=your_key
DISCORD_TOKEN=your_token
```

## Discord Bot Features

### Slash Commands
| Command | Description |
|---------|-------------|
| `/status` | Bot status, location, health |
| `/screenshot` | Capture game screenshot |
| `/gif [duration]` | Record GIF (default 5s, max 15s) |
| `/stop` | Stop current activity |
| `/run <routine> [loops]` | Run automation routine |
| `/routines` | List available routines |
| `/switch <account>` | Switch OSRS account |
| `/accounts` | List accounts |
| `/help` | Show help |

### Natural Language (DM)
Just type naturally:
- "Did the client crash?"
- "What's in my inventory?"
- "Go fish at draynor"
- "Start the hill giants routine"

## TODO

- [x] Basic slash commands
- [x] Natural language via Gemini
- [x] Screenshot capture (scrot)
- [x] Conversation history/memory
- [x] GIF recording (ffmpeg)
- [ ] Video streaming?
- [ ] Multiple account support in Discord
- [ ] Permission system (owner only)

## Troubleshooting

### Screenshots fail with BadDrawable
- Fixed: Use `scrot -o` instead of window-specific capture
- Xvfb doesn't support focused window capture well

### Bot OOM killed
- Add swap: `sudo fallocate -l 2G /swapfile && sudo mkswap /swapfile && sudo swapon /swapfile`
- Or add `MemoryMax=512M` to discord-bot.service

### Commands not working
1. Check RuneLite running: `systemctl --user status runelite`
2. Check state file: `cat /tmp/manny_state.json | head`
3. Check logs: `journalctl --user -u runelite -f`

### Slash commands not appearing
- Global commands take up to 1 hour to propagate
- Check bot has `applications.commands` scope
- Restart bot: `systemctl --user restart discord-bot`
