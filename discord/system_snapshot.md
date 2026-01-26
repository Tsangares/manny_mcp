# System Snapshot (VPS)

Captured: 2026-01-26 | System Age: ~6 days (since Jan 20)

## Overview

Minimal Arch Linux VPS running headless OSRS automation stack with Discord bot integration.

---

## User Systemd Services

Located in `~/.config/systemd/user/`

### xvfb.service
Virtual X display for headless graphics.

```ini
[Unit]
Description=Xvfb Virtual Display :2

[Service]
Type=simple
ExecStart=/usr/bin/Xvfb :2 -screen 0 1024x768x24
Restart=always
RestartSec=5

[Install]
WantedBy=default.target
```

### x11vnc.service
VNC server attached to virtual display for remote viewing.

```ini
[Unit]
Description=x11vnc VNC Server for Display :2
After=xvfb.service
Requires=xvfb.service

[Service]
Type=simple
ExecStart=/usr/bin/x11vnc -display :2 -forever -passwd manny123 -rfbport 5902
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
```

### runelite.service
RuneLite game client with memory constraints.

```ini
[Unit]
Description=RuneLite OSRS Client
After=xvfb.service
Requires=xvfb.service

[Service]
Type=simple
Environment=DISPLAY=:2
EnvironmentFile=/home/wil/manny-mcp/.env
WorkingDirectory=/home/wil/manny-mcp
ExecStart=/usr/bin/java -Xmx512m -Xms256m -XX:+UseG1GC -XX:MaxMetaspaceSize=128m -Dsun.java2d.opengl=false -jar /home/wil/runelite.jar
Restart=on-failure
RestartSec=10
MemoryMax=800M
MemoryHigh=700M

[Install]
WantedBy=default.target
```

### discord-bot.service
Discord bot using ollama for LLM responses.

```ini
[Unit]
Description=OSRS Discord Bot
After=xvfb.service
Wants=xvfb.service

[Service]
Type=simple
EnvironmentFile=/home/wil/manny-mcp/.env
WorkingDirectory=/home/wil/manny-mcp
ExecStart=/home/wil/manny-mcp/venv/bin/python /home/wil/manny-mcp/run_discord.py --account aux --provider ollama
Restart=on-failure
RestartSec=10
MemoryMax=2G
MemoryHigh=1800M

[Install]
WantedBy=default.target
```

---

## System Services (Enabled)

From `/etc/systemd/system/multi-user.target.wants/`:
- `sshd.service` - SSH daemon
- `nginx.service` - Web server (for dashboard)
- `wg-quick@wg0.service` - WireGuard VPN
- `cronie.service` - Cron daemon
- `systemd-networkd.service` - Network management
- `haveged.service` - Entropy daemon

---

## Packages Installed Post-Setup

### Jan 22 (Day 2)
- `gemini-cli` - Google Gemini CLI
- `nodejs` - Node.js runtime (dependency)

### Jan 23 (Day 3)
- `claude-code` - Claude Code CLI
- `vi` - Text editor

### Jan 24 (Day 4)
- `jq` - JSON processor

### Jan 25 (Day 5)
- `maven` - Java build tool (for plugin development)

---

## Base Installation (Day 0 - Jan 20)

### Core System
- `base`, `linux`, `linux-firmware`
- `zsh`, `openssh`, `sudo`
- `wget`, `curl`, `git`

### Python Stack
- `python`, `python-pip`

### Java Stack
- `jdk17-openjdk`

### Headless Display
- `xorg-server-xvfb` - Virtual framebuffer
- `x11vnc` - VNC server
- `xdotool` - X11 automation

### Networking
- `wireguard-tools` - VPN
- `nginx` - Web server

### AUR Helper
- `yay` - AUR package manager

### Media (ffmpeg deps)
- `ffmpeg`, `x264`, `x265`, `zeromq`, etc.

---

## Directory Structure

```
~/
├── manny-mcp/           # MCP server (git tracked)
│   ├── discord/         # Discord bot config
│   ├── discord_bot/     # Bot implementation
│   ├── routines/        # YAML automation scripts
│   └── venv/            # Python virtualenv
├── desktop/manny/manny  # Manny plugin (git tracked, symlinked)
├── runelite.jar         # Fat JAR (temporary, not tracked)
├── .runelite/           # RuneLite config (temporary)
└── .manny/              # Credentials
```

---

## Service Management

```bash
# Enable lingering (services run without login)
sudo loginctl enable-linger wil

# Reload after changes
systemctl --user daemon-reload

# Start all
systemctl --user start xvfb x11vnc runelite discord-bot

# Check status
systemctl --user status xvfb x11vnc runelite discord-bot

# View logs
journalctl --user -u discord-bot -f
```

---

## VNC Access

```bash
# SSH tunnel (secure)
ssh -L 5902:localhost:5902 wil@vps-ip

# Connect VNC client to localhost:5902
# Password: manny123
```

---

## Notes

- System created via ansible playbook (not included)
- `~/runelite.jar` and `~/.runelite/` are temporary/regenerable
- Credentials in `~/.manny/` and `~/manny-mcp/.env` are sensitive
