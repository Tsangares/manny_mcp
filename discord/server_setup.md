# VPS Server Setup Guide

Complete setup guide for running OSRS bot on a headless VPS with Xvfb + VNC.

## Prerequisites

### VPS Specs (Minimum)
- CPU: 1 core
- RAM: 4GB (3GB free recommended)
- OS: Arch Linux (adapt commands for other distros)

### Files to Transfer from Laptop
```bash
# From laptop to VPS
rsync -avz ~/manny-mcp/ user@vps:~/manny-mcp/
scp ~/.manny/credentials.yaml user@vps:~/.manny/
scp ~/path/to/runelite-fat.jar user@vps:~/runelite.jar
```

Required files:
- `manny-mcp/` - MCP server directory
- `~/.manny/credentials.yaml` - OSRS account credentials
- `runelite.jar` - Fat jar with Manny plugin baked in

---

## Step 1: Install System Dependencies

```bash
# Arch Linux
sudo pacman -S jdk17-openjdk python python-pip xorg-server-xvfb x11vnc

# Ubuntu/Debian equivalent
# sudo apt install openjdk-17-jdk python3 python3-pip xvfb x11vnc
```

---

## Step 2: Configure manny-mcp

### Update config.yaml for VPS
Edit `~/manny-mcp/config.yaml`:

```yaml
# RuneLite MCP Server Configuration (VPS)

# Path to the runelite repository root (for building) - not available on VPS
runelite_root: null

# Path to the plugin source (manny plugin) - baked into fat jar on VPS
plugin_directory: null

# RuneLite client JAR - using fat jar on VPS
runelite_jar: /home/wil/runelite.jar

# Use mvn exec:java to run - disabled on VPS (no source)
use_exec_java: false
```

### Set up .env with account credentials
Edit `~/manny-mcp/.env`:

```bash
# Game credentials (aux account example)
JX_CHARACTER_ID=361370872
JX_DISPLAY_NAME=LOSTimposter
JX_SESSION_ID=5LRMyBHuEgwmA7EU6Xgt5s

# API keys (add as needed)
GEMINI_API_KEY=your_key_here
DISCORD_BOT_TOKEN=your_token_here
```

### Set up Python virtual environment
```bash
cd ~/manny-mcp
python -m venv venv
./venv/bin/pip install -r requirements.txt
```

---

## Step 3: Create Systemd User Services

Create directory:
```bash
mkdir -p ~/.config/systemd/user
```

### xvfb.service
`~/.config/systemd/user/xvfb.service`:
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
`~/.config/systemd/user/x11vnc.service`:
```ini
[Unit]
Description=x11vnc VNC Server for Display :2
After=xvfb.service
Requires=xvfb.service

[Service]
Type=simple
ExecStart=/usr/bin/x11vnc -display :2 -forever -viewonly -passwd manny123 -rfbport 5902
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
```

### runelite.service
`~/.config/systemd/user/runelite.service`:
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
ExecStart=/usr/bin/java -Xmx768m -XX:+UseG1GC -Dsun.java2d.opengl=false -jar /home/wil/runelite.jar
Restart=on-failure
RestartSec=10

[Install]
WantedBy=default.target
```

---

## Step 4: Enable and Start Services

```bash
# Reload systemd
systemctl --user daemon-reload

# Enable services (auto-start on boot)
systemctl --user enable xvfb x11vnc runelite

# Start services
systemctl --user start xvfb
systemctl --user start x11vnc
systemctl --user start runelite

# Check status
systemctl --user status xvfb x11vnc runelite
```

---

## Step 5: Enable Lingering (IMPORTANT)

This allows user services to run without being logged in:

```bash
sudo loginctl enable-linger $USER
```

Without this, services stop when you disconnect!

---

## Step 6: Connect via VNC

### SSH Tunnel (Secure)
```bash
# From your local machine
ssh -L 5902:localhost:5902 user@vps-ip

# Then connect VNC client to localhost:5902
# Password: manny123
```

### Direct connection (if firewall allows)
Connect to `vps-ip:5902` with password `manny123`

---

## Useful Commands

### Service Management
```bash
# Check all services
systemctl --user status xvfb x11vnc runelite

# Restart RuneLite
systemctl --user restart runelite

# Stop everything
systemctl --user stop runelite x11vnc xvfb

# View RuneLite logs
journalctl --user -u runelite -f

# View all manny logs
tail -f ~/.runelite/logs/client.log
```

### Manual Testing (without systemd)
```bash
# Start Xvfb manually
Xvfb :2 -screen 0 1024x768x24 &

# Start VNC manually
x11vnc -display :2 -forever -viewonly -passwd manny123 -rfbport 5902 &

# Start RuneLite manually
cd ~/manny-mcp
source .env
DISPLAY=:2 java -Xmx768m -XX:+UseG1GC -Dsun.java2d.opengl=false -jar ~/runelite.jar &
```

### Command Interface Testing
```bash
# Send a command
echo "GET_GAME_STATE" > /tmp/manny_command.txt

# Check response
cat /tmp/manny_response.json | python3 -m json.tool

# Check game state
cat /tmp/manny_state.json | python3 -m json.tool | head -50

# Send GOTO command
echo "GOTO 3253 3266 0" > /tmp/manny_command.txt
```

---

## File Locations

| File | Purpose |
|------|---------|
| `~/manny-mcp/` | MCP server code |
| `~/manny-mcp/.env` | Account credentials, API keys |
| `~/manny-mcp/config.yaml` | MCP configuration |
| `~/manny-mcp/routines/` | YAML automation routines |
| `~/.manny/credentials.yaml` | OSRS login credentials |
| `~/runelite.jar` | Fat jar with Manny plugin |
| `~/.runelite/logs/client.log` | RuneLite/Manny logs |
| `/tmp/manny_state.json` | Current game state |
| `/tmp/manny_command.txt` | Command input |
| `/tmp/manny_response.json` | Command responses |

---

## Troubleshooting

### RuneLite won't start
1. Check Java: `java -version` (needs 17+)
2. Check display: `echo $DISPLAY` should be `:2`
3. Check Xvfb running: `pgrep -a Xvfb`
4. Check logs: `journalctl --user -u runelite`

### VNC won't connect
1. Check x11vnc running: `pgrep -a x11vnc`
2. Check port: `ss -tlnp | grep 5902`
3. Check firewall or use SSH tunnel

### Commands not working
1. Check RuneLite is logged in: `cat /tmp/manny_state.json`
2. Check Manny plugin loaded: `grep -i manny ~/.runelite/logs/client.log`

### Services stop after logout
Run: `sudo loginctl enable-linger $USER`

---

## Memory Optimization

RuneLite JVM flags for low-memory VPS:
```bash
java -Xmx768m -XX:+UseG1GC -Dsun.java2d.opengl=false -jar runelite.jar
```

- `-Xmx768m` - Max heap 768MB
- `-XX:+UseG1GC` - G1 garbage collector (better for limited RAM)
- `-Dsun.java2d.opengl=false` - Disable OpenGL (headless)

Total expected memory usage: ~2-2.5GB with RuneLite + system

---

## Next Steps

1. Set up Discord bot in `~/manny-mcp/discord/`
2. Configure LLM integration (Gemini API key in .env)
3. Create systemd service for Discord bot
4. Test full loop: Discord -> LLM -> MCP -> Game
