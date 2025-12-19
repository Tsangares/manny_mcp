# Starting and Stopping RuneLite

## Configuration

RuneLite runs on display `:2` with the following environment variables:

| Variable | Value | Purpose |
|----------|-------|---------|
| `DISPLAY` | `:2` | X11 display for headless/secondary monitor |
| `JX_CHARACTER_ID` | `358245984` | Character identifier |
| `JX_DISPLAY_NAME` | `ArmAndALegs` | Character display name |
| `JX_SESSION_ID` | `2XSuLfYEu7ommL3XG7rg6f` | Session identifier |

## Starting RuneLite

### Quick Start (One-liner)

```bash
cd /home/wil/Desktop/runelite && \
DISPLAY=:2 \
JX_CHARACTER_ID=358245984 \
JX_DISPLAY_NAME=ArmAndALegs \
JX_SESSION_ID=2XSuLfYEu7ommL3XG7rg6f \
mvn exec:java -pl runelite-client \
  -Dexec.mainClass="net.runelite.client.RuneLite" \
  -Dsun.java2d.uiScale=2.0 &
```

### With Logging to File

```bash
cd /home/wil/Desktop/runelite && \
DISPLAY=:2 \
JX_CHARACTER_ID=358245984 \
JX_DISPLAY_NAME=ArmAndALegs \
JX_SESSION_ID=2XSuLfYEu7ommL3XG7rg6f \
mvn exec:java -pl runelite-client \
  -Dexec.mainClass="net.runelite.client.RuneLite" \
  -Dsun.java2d.uiScale=2.0 \
  2>&1 | tee /tmp/runelite_launch.log &
```

## Stopping RuneLite

### Graceful Stop

```bash
pkill -f "net.runelite.client.RuneLite"
```

### Force Stop (if graceful doesn't work)

```bash
pkill -9 -f "net.runelite.client.RuneLite"
pkill -9 -f "mvn.*runelite"
```

### Verify Stopped

```bash
pgrep -f "net.runelite.client.RuneLite" || echo "RuneLite is not running"
```

## Building Before Running

If you've made code changes, compile first:

```bash
cd /home/wil/Desktop/runelite
mvn compile -pl runelite-client -T 1C -DskipTests
```

## Monitoring

### Watch Logs in Real-Time

```bash
tail -f ~/.runelite/logs/client.log
```

### Filter for Errors

```bash
tail -f ~/.runelite/logs/client.log | grep -i "error\|exception\|warn"
```

### Filter for Manny Plugin

```bash
tail -f ~/.runelite/logs/client.log | grep "manny"
```

## Troubleshooting

### Client won't start
1. Check if display :2 is running: `DISPLAY=:2 xdpyinfo`
2. Kill any zombie processes: `pkill -9 -f runelite`
3. Check for build errors: `mvn compile -pl runelite-client`

### World busy errors
The Manny plugin auto-selects F2P worlds. If all are busy, manually select a world or wait.

### No game client visible
Ensure display :2 has a window manager or VNC server running.

## Reference

Configuration source: `/home/wil/Desktop/runelite/manny_test/RuneLite Client.run.xml`
