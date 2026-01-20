# VPS Discord Bot Setup - Lessons Learned

**Date:** 2026-01-20
**Context:** Setting up Discord bot to control RuneLite on a 4GB RAM VPS

## Critical Issue: Systemd Memory Cgroup Limits

**Problem:** RuneLite kept freezing at plugin 52-98/131 during startup.

**Root Cause:** The `discord-bot.service` had `MemoryMax=512M`. When the bot spawned RuneLite as a child process, **both processes shared the 512MB limit**:
- Discord bot: ~100-200MB
- RuneLite/Java: ~400-500MB
- Combined: exceeded 512MB → OOM kill

**Evidence from dmesg:**
```
oom_memcg=/user.slice/user-1000.slice/user@1000.service/app.slice/discord-bot.service
Memory cgroup out of memory: Killed process 7606 (java)
```

**Fix:** Increase `MemoryMax` to accommodate both processes:
```ini
MemoryMax=2G
MemoryHigh=1800M
```

**Lesson:** Systemd memory limits apply to the entire cgroup, including all child processes spawned by the service.

---

## Issue: Subprocess PIPE Deadlock

**Problem:** RuneLite would sometimes freeze during plugin loading even with adequate memory.

**Root Cause:** The `runelite_manager.py` used `stdout=subprocess.PIPE` which can deadlock if:
- The subprocess outputs faster than the pipe is drained
- The capture thread isn't running or is blocked

**BAD:**
```python
self.process = subprocess.Popen(
    cmd,
    stdout=subprocess.PIPE,  # Can deadlock!
    stderr=subprocess.STDOUT,
    ...
)
```

**GOOD:**
```python
self.log_file = open(f"/tmp/runelite_{account_id}.log", "w")
self.process = subprocess.Popen(
    cmd,
    stdout=self.log_file,  # File output, never blocks
    stderr=subprocess.STDOUT,
    ...
)
```

**Lesson:** For long-running subprocesses with heavy output, redirect to file instead of PIPE.

---

## Issue: Large PNG Blocking Startup

**Problem:** RuneLite startup was slow, main thread blocked for 30+ seconds.

**Root Cause:** The manny plugin loads a **6.7MB world_map.png** during initialization via `ImageIO.read()`. PNG decompression is CPU-intensive.

**Evidence from thread dump:**
```
"main" #1 prio=5 ... RUNNABLE
    at java.util.zip.Inflater.inflateBytesBytes(Native Method)
    at javax.imageio.ImageIO.read(ImageIO.java:1466)
    at net.runelite.client.plugins.manny.utility.WorldMapData.<init>(WorldMapData.java:62)
```

**Lesson:** Large resource loading during plugin init blocks the entire startup. Consider lazy loading or background threads for heavy resources.

---

## VNC Configuration

**View-only mode:** Remove `-viewonly` flag to enable mouse/keyboard interaction:
```ini
# Before (view-only)
ExecStart=/usr/bin/x11vnc -display :2 -forever -viewonly -passwd manny123 -rfbport 5902

# After (interactive)
ExecStart=/usr/bin/x11vnc -display :2 -forever -passwd manny123 -rfbport 5902
```

---

## Screenshot/GIF Viewport Cropping

**Game viewport coordinates:** (120, 137) to (872, 636) = 752x499 pixels

**PIL crop (screenshot):**
```python
cropped = img.crop((120, 137, 872, 636))
```

**FFmpeg crop filter (GIF):**
```
-vf "crop=752:499:120:137"
```

Format: `crop=width:height:x:y`

---

## Service Configuration Summary

**discord-bot.service:**
```ini
[Service]
MemoryMax=2G
MemoryHigh=1800M
```

**x11vnc.service:**
```ini
ExecStart=/usr/bin/x11vnc -display :2 -forever -passwd manny123 -rfbport 5902
```

**Java heap (in runelite_manager.py):**
```python
env["_JAVA_OPTIONS"] = "-Xmx768m -XX:MaxMetaspaceSize=128m"
```

---

## Quick Debugging Commands

```bash
# Check memory cgroup limits
systemctl --user status discord-bot | grep Memory

# Check for OOM kills
dmesg | grep -i "oom\|kill"

# Get Java thread dump
kill -3 <pid>  # Outputs to stdout/log file

# Check process tree under service
systemctl --user status discord-bot  # Shows CGroup tree
```
