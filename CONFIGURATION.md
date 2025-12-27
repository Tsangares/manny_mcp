# Manny MCP Configuration Guide

**Version:** 1.0.0
**Date:** 2025-12-26
**Related:** See OPTIMIZATIONS.md for performance details

## Overview

This document describes all configurable optimization settings in the Manny MCP server. Use this guide to tune performance for your specific hardware and workload.

---

## Build Settings

### Location
`server.py:364-381` - `build_plugin()` function

### Parameters

```python
def build_plugin(clean: bool = False) -> dict:
    """
    Compile the manny RuneLite plugin.

    Args:
        clean: If True, run 'mvn clean' first (slower but safer)
    """
```

#### `clean` Parameter

**Default:** `False` (incremental builds)

**When to change:**
- Set to `True` after major refactors
- Set to `True` after dependency changes (pom.xml)
- Set to `True` after Maven errors
- Set to `True` on first build after pulling changes

**Impact:**
- `clean=False`: 25-35s builds (10x faster)
- `clean=True`: 30-40s builds (slower but guaranteed fresh state)

### Maven Arguments

#### Thread Count (`-T 2`)

**Current:** 2 threads
**Location:** `server.py:377`

**Tuning guide:**
```
CPU Cores    Recommended -T    Build Time Impact
─────────────────────────────────────────────────
2            1                 Baseline
4            2 (current)       1.5x faster
8            4                 2x faster
16+          8                 2.5x faster

WARNING: Don't set -T higher than your core count!
```

**How to change:**
```python
# Line 377 in server.py
cmd.extend([
    "compile",
    "-pl", "runelite-client",
    "-T", "4",  # Change this number
    "-DskipTests",
    "-o"
])
```

#### Offline Mode (`-o`)

**Current:** Enabled
**Location:** `server.py:379`

**Purpose:** Skip remote dependency checks (faster builds)

**When to disable:**
- First build after cloning repo
- After changing dependencies in pom.xml
- After long periods without pulling

**How to disable:**
```python
# Line 379 in server.py - remove "-o"
cmd.extend([
    "compile",
    "-pl", "runelite-client",
    "-T", "2",
    "-DskipTests"
    # Remove: "-o"
])
```

---

## Cache Settings

### Location
`cache_layer.py:151-159` - Global cache instance

### Parameters

```python
_tool_cache = LRUCache(
    max_size=100,       # Maximum entries
    default_ttl=300     # 5 minutes
)
```

#### `max_size` Parameter

**Default:** 100 entries

**Tuning guide:**
```
Workload               Recommended max_size    Memory Impact
──────────────────────────────────────────────────────────────
Light (single user)    50                      ~1 MB
Normal (current)       100                     ~2 MB
Heavy (multi-agent)    200                     ~4 MB
Extreme (batch ops)    500                     ~10 MB
```

**How to change:**
```python
# Line 158 in cache_layer.py
_tool_cache = LRUCache(max_size=200, default_ttl=300)
```

#### `default_ttl` Parameter

**Default:** 300 seconds (5 minutes)

**Tuning guide:**
```
Cache Type              Recommended TTL    Reason
────────────────────────────────────────────────────
Code searches           600s (10 min)      Code rarely changes
File metadata           300s (5 min)       Balance
Game state queries      60s (1 min)        Game state changes fast
Widget scans            30s (30 sec)       UI changes frequently
```

**Per-function TTL overrides:**

Located in `manny_tools.py`:

```python
# Line 858 - Class summary cache
@cached_tool(ttl=300)  # 5 minutes
def get_class_summary(...):
    pass

# Line 2125 - Command list cache
@cached_tool(ttl=600)  # 10 minutes
def list_available_commands(...):
    pass
```

**How to tune:**
```python
# Increase if code rarely changes:
@cached_tool(ttl=1800)  # 30 minutes

# Decrease if getting stale data:
@cached_tool(ttl=120)   # 2 minutes
```

### Cache Invalidation

**Manual invalidation:**
```python
from cache_layer import get_tool_cache

cache = get_tool_cache()

# Clear entire cache
cache.invalidate()

# Clear specific function
cache.invalidate("list_available")  # Matches all keys containing this
```

**Automatic invalidation:**

Cache entries expire after TTL automatically. No manual intervention needed.

---

## Search Engine Settings

### Location
`search_engine.py:205-221` - Global index instance

### Index Build

**Build trigger:** Lazy initialization on first access

**Build time:** ~0.3s for 40 Java files

**Index size:** ~1,260 keys (commands, classes, methods, sections)

### Force Rebuild

**When needed:**
- After adding new commands
- After major code refactors
- After file renames/moves

**How to force rebuild:**

```python
from search_engine import get_search_index

# Option 1: Delete and recreate
import search_engine
search_engine._search_index = None
index = get_search_index("/home/wil/Desktop/manny")  # Rebuilds

# Option 2: Restart MCP server (index rebuilds on startup)
```

**Automatic rebuild:** Not implemented yet (planned for future)

---

## File Monitoring Settings

### Location
`server.py:108-227` - `ResponseFileMonitor` class

### Parameters

#### Polling Fallback

**Trigger:** Watchdog library not installed

**Behavior:** Falls back to 50ms polling loop

**How to enable event-driven mode:**
```bash
./venv/bin/pip install watchdog>=3.0.0
```

#### Timeout Settings

**Location:** Various tool functions in `server.py`

**Example:**
```python
# Line 1663-1676 - wait_for_command_with_timeout()
async def wait_for_command_with_timeout(timeout_sec: float = 5.0):
    if _response_monitor:
        success = await _response_monitor.wait_for_change(timeout_sec)
    else:
        # Fallback polling
        success = await poll_for_change(timeout_sec)
```

**Tuning guide:**
```
Command Type          Recommended Timeout    Reason
───────────────────────────────────────────────────────
Simple (BANK_OPEN)    3-5s                   Fast ops
Navigation (GOTO)     10-30s                 Walking takes time
Dialogue (NPC)        5-10s                  Multi-step
Combat                60s+                   May take multiple ticks
```

**How to change default:**
```python
# In server.py, find the tool function and modify timeout parameter:
@server.tool()
async def send_command(command: str, timeout_ms: int = 5000):
    timeout_sec = timeout_ms / 1000
    await wait_for_command_with_timeout(timeout_sec)
```

---

## State Export Settings

### Location
`/home/wil/Desktop/manny/utility/GameEngine.java:4600-4785`

### Parameters

#### `unchangedTicks` Threshold

**Current:** 10 ticks (6 seconds)

**Purpose:** Force heartbeat write even if state unchanged

**Tuning guide:**
```
Heartbeat Interval    Write Frequency    Risk of Stale State
────────────────────────────────────────────────────────────
5 ticks (3s)          More frequent      Very low
10 ticks (6s)         Balanced           Low (current)
20 ticks (12s)        Less frequent      Medium
Never                 Only on changes    High (not recommended)
```

**How to change:**
```java
// Line 4611 in GameEngine.java
private int unchangedTicks = 0;

public void onGameTick() {
    // ...

    // Change this threshold:
    if (unchangedTicks >= 20) {  // Was 10, now 20 (12 seconds)
        executors.getBackgroundExecutor().execute(() -> {
            writeStateFile(state);
        });
        previousState = state;
        unchangedTicks = 0;
    }
}
```

#### Change Detection Sensitivity

**Location:** `hasSignificantChange()` method (Lines 4620-4680)

**Current checks:**
- Position (x, y, plane)
- Health (current HP)
- Prayer (current points)
- Inventory (used slots, item IDs)
- Combat state (in combat flag)
- Animation (current animation ID)

**How to add custom checks:**
```java
// Add to hasSignificantChange() method
private boolean hasSignificantChange(MannyState current, MannyState previous) {
    if (previous == null) return true;

    // Existing checks...

    // Add custom check (example: XP change)
    if (!current.player.skills.equals(previous.player.skills)) {
        return true;  // XP changed
    }

    return false;
}
```

---

## Smart Sectioning Settings

### Location
`request_code_change.py:20-110` - `prepare_code_change()` function

### Parameters

#### `smart_sectioning` Flag

**Default:** `True`

**Purpose:** Extract only relevant command handlers from PlayerHelpers.java

**How it works:**
1. Parses problem description and logs
2. Extracts mentioned command names (e.g., "BANK_OPEN")
3. Uses search engine to find those commands
4. Returns only those handlers (2-4KB vs 720KB)

**When to disable:**
```python
# If you need full file context for complex multi-command interactions
context = prepare_code_change(
    problem_description="...",
    relevant_files=["PlayerHelpers.java"],
    smart_sectioning=False  # Returns full file
)
```

#### `compact` Flag

**Default:** `False`

**Purpose:** Return only file metadata, not contents (for subagent efficiency)

**When to enable:**
```python
# When spawning subagents that will use Read tool
context = prepare_code_change(
    problem_description="...",
    relevant_files=["PlayerHelpers.java"],
    compact=True  # Returns metadata only
)
```

#### `max_file_lines` Parameter

**Default:** 0 (unlimited)

**Purpose:** Truncate files to reduce context size

**Tuning guide:**
```
File Size       Recommended max_file_lines    Context Saved
─────────────────────────────────────────────────────────────
<500 lines      0 (no limit)                  N/A
500-2000        500                           ~50%
2000-10000      1000                          ~75%
10000+ (huge)   200-500                       ~90%
```

**How to use:**
```python
context = prepare_code_change(
    problem_description="...",
    relevant_files=["VeryLargeFile.java"],
    max_file_lines=500  # Truncate to first 500 lines
)
```

---

## Anti-Pattern Scanning Settings

### Location
`manny_tools.py:597-772` - `ANTI_PATTERNS` list and `check_anti_patterns()` function

### Pre-compiled Regexes

**Build time:** Module load (one-time cost)

**Regex count:** 11 patterns

**How to add custom patterns:**

```python
# In manny_tools.py, add to ANTI_PATTERNS list (around line 600)
ANTI_PATTERNS = [
    # Existing patterns...

    # Add your custom pattern:
    {
        "pattern": r"myAntiPattern\(",
        "severity": "medium",
        "message": "Avoid using myAntiPattern, use betterPattern instead",
        "fix_template": "Use betterPattern() instead"
    }
]
```

**Regex will be pre-compiled automatically on next import.**

---

## Performance Monitoring

### Using the Monitor Tool

**Basic usage:**
```bash
# Show all metrics
./monitor.py --metric all

# Show specific metric
./monitor.py --metric builds
./monitor.py --metric cache
./monitor.py --metric search
./monitor.py --metric state
./monitor.py --metric commands

# Live monitoring (refreshes every 30s)
./monitor.py --watch

# Custom refresh interval
./monitor.py --watch --interval 10  # Refresh every 10 seconds
```

### Alert Thresholds

**Location:** `monitor.py:30-40` - `BASELINES` dictionary

**Current thresholds:**
```python
BASELINES = {
    "build_time_incremental": {"expected": 30, "alert_threshold": 60},
    "build_time_clean": {"expected": 35, "alert_threshold": 70},
    "command_response": {"expected": 10, "alert_threshold": 100},
    "search_lookup": {"expected": 1, "alert_threshold": 10},
    "cache_hit_rate": {"expected": 50, "alert_threshold": 30},
    "state_writes_per_min": {"expected": 8, "alert_threshold": 20},
    "index_build_time": {"expected": 1, "alert_threshold": 5}
}
```

**How to tune:**

Adjust thresholds based on your hardware:

```python
# For slower hardware (e.g., laptop):
BASELINES = {
    "build_time_incremental": {"expected": 40, "alert_threshold": 80},
    # ...
}

# For faster hardware (e.g., desktop):
BASELINES = {
    "build_time_incremental": {"expected": 20, "alert_threshold": 40},
    # ...
}
```

---

## Recommended Settings by Hardware

### Laptop (4 cores, 8 GB RAM)

```python
# server.py - Build settings
"-T", "2"                    # 2 threads

# cache_layer.py - Cache settings
max_size=50                  # Smaller cache
default_ttl=300              # 5 minutes

# monitor.py - Baselines
build_time_incremental: 40s  # Slower threshold
```

### Desktop (8+ cores, 16+ GB RAM)

```python
# server.py - Build settings
"-T", "4"                    # 4 threads

# cache_layer.py - Cache settings
max_size=200                 # Larger cache
default_ttl=600              # 10 minutes

# monitor.py - Baselines
build_time_incremental: 20s  # Faster threshold
```

### Server (16+ cores, 32+ GB RAM)

```python
# server.py - Build settings
"-T", "8"                    # 8 threads

# cache_layer.py - Cache settings
max_size=500                 # Very large cache
default_ttl=1800             # 30 minutes

# monitor.py - Baselines
build_time_incremental: 15s  # Very fast threshold
```

---

## Troubleshooting

### High Memory Usage

**Symptoms:** Python process using >500 MB RAM

**Likely cause:** Cache too large

**Fix:**
```python
# Reduce cache size in cache_layer.py
_tool_cache = LRUCache(max_size=50, default_ttl=300)
```

### Slow Builds Despite Optimizations

**Symptoms:** Builds taking >60s even with `clean=False`

**Checks:**
1. Verify offline mode is enabled (`-o` flag)
2. Check thread count matches your CPU
3. Ensure SSD storage (not HDD)
4. Clear `.m2` cache if corrupted

**Fix:**
```bash
# Clear Maven cache
rm -rf ~/.m2/repository

# Force clean build once
./venv/bin/python -c "from server import build_plugin; build_plugin(clean=True)"
```

### Stale Cache Data

**Symptoms:** Old data returned by tools despite code changes

**Fix:**
```python
# Clear cache manually
from cache_layer import get_tool_cache
get_tool_cache().invalidate()
```

Or reduce TTL:
```python
# In manny_tools.py
@cached_tool(ttl=60)  # Reduce from 300 to 60 seconds
```

### Search Engine Missing New Commands

**Symptoms:** `find_command()` returns empty for newly added commands

**Fix:**
```python
# Force index rebuild
import search_engine
search_engine._search_index = None
```

Or restart MCP server.

---

## Configuration Checklist

Before deploying optimizations, verify:

- [ ] Maven thread count (`-T`) matches your CPU cores (max 8)
- [ ] Cache size fits your memory constraints (100 = ~2 MB)
- [ ] TTL values match your code change frequency
- [ ] Alert thresholds in monitor.py match your hardware
- [ ] Watchdog library installed for event-driven monitoring
- [ ] Baseline metrics recorded with `monitor.py --metric all`

---

## See Also

- **OPTIMIZATIONS.md** - Performance improvements and architecture
- **CLAUDE.md** - Main guidance for Claude Code
- **monitor.py** - Performance monitoring tool
