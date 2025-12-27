# Manny MCP Phase 4 Optimization Opportunities

**Date:** 2025-12-26
**Status:** Audit & Planning
**Prerequisites:** Phases 1-3 completed

## Overview

This document identifies additional optimization opportunities discovered during a comprehensive deep audit of the Manny MCP codebase. These optimizations are categorized by effort level and potential impact.

---

## Quick Wins (1-2 hours)

### 1. Dashboard State Polling → Event-Driven

**Current:** `dashboard.py:904-914`
```python
def _poll_game_state(self):
    """Poll manny_state.json every 600ms."""
    while self.running:
        try:
            if os.path.exists(state_file):
                with open(state_file) as f:
                    state = json.load(f)
                STATE.update_game_state(state)
        except Exception as e:
            STATE.add_log(f"State poll error: {e}")
        time.sleep(0.6)
```

**Issue:**
- Polls state file every 600ms regardless of changes
- ~100 reads/minute, most are redundant (state changes 6-10x/min)
- Wastes CPU and disk I/O

**Solution:**
Use watchdog like we did in server.py for response file monitoring:

```python
def _poll_game_state(self):
    """Event-driven state file monitoring."""
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler

    class StateFileHandler(FileSystemEventHandler):
        def on_modified(self, event):
            if event.src_path == state_file:
                try:
                    with open(state_file) as f:
                        state = json.load(f)
                    STATE.update_game_state(state)
                except Exception as e:
                    STATE.add_log(f"State update error: {e}")

    observer = Observer()
    observer.schedule(StateFileHandler(), os.path.dirname(state_file))
    observer.start()

    while self.running:
        time.sleep(1)  # Just keep thread alive

    observer.stop()
```

**Impact:**
- **90% reduction in file reads** (100/min → 10/min)
- **<10ms latency** vs 0-600ms polling latency
- Lower CPU usage

**Effort:** 30 minutes

---

### 2. H.264 Encoder Detection Caching

**Current:** `dashboard.py:643-682`
```python
def _detect_h264_encoder(self) -> str:
    """Test encoders in priority order, return first working one."""
    encoders = ['h264_nvenc', 'h264_vaapi', 'h264_amf', 'libx264']

    for encoder in encoders:
        # Run 1-second test for each encoder
        # Takes 1-4 seconds total on dashboard start
```

**Issue:**
- Runs on every dashboard start
- Tests 1-4 encoders sequentially (1s each)
- Same hardware always has same encoder available

**Solution:**
Cache encoder detection result to `/tmp/manny_h264_encoder.txt`:

```python
def _detect_h264_encoder(self) -> str:
    """Test encoders (cached)."""
    cache_file = Path("/tmp/manny_h264_encoder.txt")

    # Check cache (valid for 24 hours)
    if cache_file.exists():
        age = time.time() - cache_file.stat().st_mtime
        if age < 86400:  # 24 hours
            encoder = cache_file.read_text().strip()
            STATE.add_log(f"Using cached encoder: {encoder}")
            return encoder

    # Cache miss - detect and cache
    encoder = self._detect_h264_encoder_internal()
    cache_file.write_text(encoder)
    return encoder
```

**Impact:**
- **Dashboard starts 1-4s faster** (after first run)
- No repeated testing on same hardware

**Effort:** 15 minutes

---

### 3. Dashboard HTTP Polling → WebSocket Push

**Current:** `dashboard.py:548-621` (JavaScript)
```javascript
function updateDashboard() {
    fetch('/api/state')
        .then(r => r.json())
        .then(state => {
            // Update UI...
        });
}

setInterval(updateDashboard, 500);  // Polls every 500ms
```

**Issue:**
- HTTP request every 500ms = 120 requests/min
- Most responses are identical (state unchanged)
- Wastes bandwidth and server CPU

**Solution:**
Use Server-Sent Events (SSE) or enhance existing WebSocket:

**Option A: SSE (simpler)**
```python
# In dashboard.py
@app.get("/api/state/stream")
async def stream_state():
    """Server-Sent Events stream for state updates."""
    async def event_generator():
        last_state = None
        while True:
            current_state = STATE.to_dict()
            if current_state != last_state:
                yield f"data: {json.dumps(current_state)}\n\n"
                last_state = current_state
            await asyncio.sleep(0.5)

    return StreamingResponse(event_generator(), media_type="text/event-stream")
```

```javascript
// In dashboard HTML
const eventSource = new EventSource('/api/state/stream');
eventSource.onmessage = (event) => {
    const state = JSON.parse(event.data);
    updateDashboard(state);  // No more polling!
};
```

**Impact:**
- **Server only sends when state changes** (vs 120 requests/min)
- **Lower latency** - updates pushed immediately
- **50% less bandwidth** (no request headers/overhead)

**Effort:** 45 minutes

---

### 4. JSON Serialization → orjson

**Current:** Uses standard library `json.dumps()` / `json.loads()` throughout

**Issue:**
- Python's json module is pure Python (slow)
- State file is written 6-10x/min
- Dashboard serializes state 120x/min (before SSE optimization)

**Solution:**
Replace with orjson (C extension, 2-3x faster):

```python
# Add to requirements.txt
orjson>=3.9.0

# In dashboard.py, server.py, request_code_change.py
import orjson

# Replace:
json.dumps(data)
# With:
orjson.dumps(data).decode()

# Replace:
json.loads(text)
# With:
orjson.loads(text)
```

**Impact:**
- **2-3x faster JSON serialization**
- **Lower CPU usage** during state writes
- **Faster dashboard responses**

**Effort:** 30 minutes (search & replace + testing)

---

## Medium Effort (1-2 days)

### 5. Lazy Module Imports

**Current:** `server.py:1-80`
```python
# All imports at top of file
from request_code_change import (...)  # 8 functions, 8 tool definitions
from manny_tools import (...)  # 20 functions, 20 tool definitions
import google.generativeai as genai  # Heavy dependency
```

**Issue:**
- Loads 50+ functions and tool definitions on startup
- Imports heavy dependencies (Gemini API) even if never used
- Slower MCP server startup

**Solution:**
Lazy import rarely-used tools:

```python
# At top of file - only import what's always needed
from mcp.server import Server
from mcptools.config import ServerConfig

# Lazy import heavy dependencies
_genai = None
def get_genai():
    global _genai
    if _genai is None:
        import google.generativeai as genai
        genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))
        _genai = genai
    return _genai

# Lazy import tool modules
_manny_tools = None
def get_manny_tools():
    global _manny_tools
    if _manny_tools is None:
        from manny_tools import (...)
        _manny_tools = {...}
    return _manny_tools
```

**Impact:**
- **Faster server startup** (200-500ms saved)
- **Lower memory footprint** when tools not used

**Effort:** 3-4 hours (requires careful refactoring)

---

### 6. Build Artifact Caching

**Current:** Every incremental build recompiles unchanged files

**Issue:**
- Maven's incremental compilation helps but isn't perfect
- Some unchanged files get recompiled
- Build times vary: 25-35s

**Solution:**
Use ccache for C/C++ or Maven's built-in caching:

```python
# In server.py - build_plugin()
cmd.extend([
    "compile",
    "-Dmaven.compiler.useIncrementalCompilation=true",
    "-Dmaven.compiler.incremental=true",
    "-pl", "runelite-client",
    "-T", "2",
    "-DskipTests",
    "-o"
])
```

Also configure Maven cache in `~/.m2/settings.xml`:
```xml
<settings>
  <localRepository>${user.home}/.m2/repository</localRepository>
  <buildCache>
    <enabled>true</enabled>
  </buildCache>
</settings>
```

**Impact:**
- **5-10% faster builds** (25s → 22-23s)
- **More consistent build times**

**Effort:** 2 hours (configuration + testing)

---

### 7. Widget Scanning: Incremental vs Full Scan

**Current:** `SCAN_WIDGETS` command always scans all widgets

**Issue:**
- UI can have 50-100+ widgets visible
- Full scan returns all data even if only checking for specific widget
- Server-side filtering helps but still processes all widgets

**Solution:**
Add incremental scanning modes:

```java
// In PlayerHelpers.java
case "SCAN_WIDGETS_FAST":
    // Only scan for widget existence, return boolean
    return handleScanWidgetsFast(parts[1]);

case "SCAN_WIDGETS_CHANGED":
    // Return only widgets that changed since last scan
    return handleScanWidgetsChanged();
```

**Impact:**
- **50-80% faster** for existence checks (just boolean)
- **Smaller response payloads**

**Effort:** 4-6 hours (Java changes + testing)

---

## Major Refactors (1 week)

### 8. Protobuf State Format

**Current:** State file is JSON (~50KB typical)

**Issue:**
- JSON is text-based, verbose
- Parsing overhead on every read
- 6-10 writes/min = 300-500KB/min of JSON serialization

**Solution:**
Replace with Protocol Buffers (binary format):

**State.proto:**
```protobuf
syntax = "proto3";

message MannyState {
  message Player {
    message Location {
      int32 x = 1;
      int32 y = 2;
      int32 plane = 3;
    }
    Location location = 1;
    int32 health = 2;
    // ... other fields
  }
  Player player = 1;
  repeated InventoryItem inventory = 2;
  // ... other fields
}
```

**Impact:**
- **5x smaller files** (50KB → 10KB)
- **2-3x faster serialization**
- **Significant CPU/disk I/O savings**

**Effort:** 1-2 weeks (requires changes in both Java and Python, migration path)

---

### 9. Command Batching API

**Current:** Each command is sent individually via file write

**Issue:**
- Dialogue interactions require 5-10 sequential commands
- Each command has ~10ms overhead (write file, wait for read, wait for response)
- Total: 50-100ms for dialogue sequence

**Solution:**
Batch API for executing multiple commands atomically:

```
Command file format:
BATCH_START
INTERACT_NPC Cook Talk-to
WAIT_DIALOGUE
CLICK_CONTINUE
CLICK_OPTION What's wrong?
BATCH_END
```

Java processes as single batch, returns all results:
```json
{
  "results": [
    {"command": "INTERACT_NPC", "success": true},
    {"command": "WAIT_DIALOGUE", "success": true},
    {"command": "CLICK_CONTINUE", "success": true},
    {"command": "CLICK_OPTION", "success": true}
  ],
  "batch_time_ms": 45
}
```

**Impact:**
- **3-5x faster dialogue sequences** (100ms → 20-30ms)
- **Simpler routine code** (one batch vs multiple sends)

**Effort:** 1 week (requires significant Java changes + Python wrapper)

---

### 10. Memory-Mapped State File

**Current:** State file read via `open()` / `json.load()`

**Issue:**
- File is opened, read fully, parsed on every access
- Dashboard accesses state 100x/min (before SSE optimization)
- Kernel overhead for file operations

**Solution:**
Use memory-mapped I/O for zero-copy reads:

```python
import mmap

class MemoryMappedState:
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.fd = None
        self.mmap = None

    def read(self) -> dict:
        """Read state with zero-copy."""
        if self.fd is None:
            self.fd = os.open(self.file_path, os.O_RDONLY)
            self.mmap = mmap.mmap(self.fd, 0, access=mmap.ACCESS_READ)

        # Re-map if file changed size
        stat = os.fstat(self.fd)
        if stat.st_size != self.mmap.size():
            self.mmap.close()
            self.mmap = mmap.mmap(self.fd, 0, access=mmap.ACCESS_READ)

        # Zero-copy read
        data = self.mmap[:stat.st_size]
        return orjson.loads(data)
```

**Impact:**
- **30-50% faster state reads** (no kernel copying)
- **Lower CPU usage**

**Effort:** 4-5 days (requires careful handling of file updates)

---

## Optimization Opportunities Summary

| Optimization | Effort | Impact | Priority |
|--------------|--------|--------|----------|
| Dashboard event-driven state | 30min | 90% fewer reads | **HIGH** |
| H.264 encoder caching | 15min | 1-4s faster start | **HIGH** |
| Dashboard WebSocket push | 45min | 50% less bandwidth | **HIGH** |
| orjson serialization | 30min | 2-3x faster JSON | **HIGH** |
| Lazy module imports | 4hrs | Faster startup | MEDIUM |
| Build artifact caching | 2hrs | 5-10% faster builds | MEDIUM |
| Widget scanning modes | 6hrs | 50-80% faster checks | MEDIUM |
| Protobuf state format | 2wks | 5x compression | LOW |
| Command batching API | 1wk | 3-5x faster dialogues | LOW |
| Memory-mapped state | 5d | 30-50% faster reads | LOW |

---

## Recommended Implementation Order

### Phase 4A: Quick Wins (2-3 hours total)
1. Dashboard event-driven state monitoring
2. H.264 encoder caching
3. Dashboard WebSocket push
4. orjson serialization

**Total impact:** ~95% reduction in polling overhead, 2-3x faster serialization

### Phase 4B: Medium Effort (1-2 days)
5. Lazy module imports
6. Build artifact caching
7. Widget scanning modes

**Total impact:** Faster startup, 5-10% faster builds, 50%+ faster widget operations

### Phase 4C: Major Refactors (optional, 2-4 weeks)
8. Protobuf state format
9. Command batching API
10. Memory-mapped state

**Total impact:** 5x file compression, 3-5x faster dialogues, 30-50% faster reads

---

## Additional Research Needed

### 1. Profile-Guided Optimization (PGO) for Java

**Question:** Can we use Java's JIT profiling to optimize hotpaths?

**Research:**
- Identify hot methods in manny plugin (which methods are called most?)
- Use Java Flight Recorder to profile
- Apply PGO compiler hints

**Potential:** 10-20% JVM performance improvement

---

### 2. HTTP/2 or gRPC for MCP Protocol

**Question:** Is the MCP stdio protocol optimal for high-throughput?

**Current:** JSON-RPC over stdio (text protocol)

**Alternative:** gRPC (binary protocol, HTTP/2 multiplexing)

**Potential:** 2-3x lower latency for tool calls

**Caveat:** Requires upstream MCP protocol changes

---

### 3. Rust Rewrite of Hot Paths

**Question:** Should Python hot paths be rewritten in Rust?

**Candidates:**
- JSON parsing (already solved with orjson)
- Search engine indexing
- Anti-pattern regex matching

**Potential:** 5-10x speedup for indexing

**Effort:** Very high (weeks)

---

## Metrics & Monitoring

After implementing Phase 4 optimizations, add to `monitor.py`:

```python
# New metrics to track
BASELINES["dashboard_state_reads_per_min"] = {"expected": 10, "alert_threshold": 50}
BASELINES["dashboard_encoder_detect_time"] = {"expected": 0.01, "alert_threshold": 2.0}
BASELINES["json_serialize_ms"] = {"expected": 0.5, "alert_threshold": 5.0}
BASELINES["module_import_time"] = {"expected": 0.2, "alert_threshold": 1.0}
```

---

## Rollback Procedures

### Dashboard Event-Driven Monitoring
```python
# Disable in dashboard.py
USE_EVENT_DRIVEN_STATE = False  # Fallback to polling
```

### orjson Serialization
```python
# Fallback to standard json
try:
    import orjson
    dumps = lambda x: orjson.dumps(x).decode()
    loads = orjson.loads
except ImportError:
    import json
    dumps = json.dumps
    loads = json.loads
```

### WebSocket Push
```javascript
// Dashboard can gracefully fallback to HTTP polling if SSE fails
if (!window.EventSource) {
    // Use old setInterval polling
}
```

---

## Performance Projections

### Current State (Post-Phase 3)
- Build time: 30s
- Command latency: <1ms
- Search lookup: 0.05ms
- State reads: 100/min (dashboard polling)
- JSON serialization: 6-10/min

### After Phase 4A (Quick Wins)
- Build time: 30s (unchanged)
- Command latency: <1ms (unchanged)
- Search lookup: 0.05ms (unchanged)
- State reads: **10/min** (90% reduction)
- JSON serialization: **2-3x faster** (orjson)
- Dashboard latency: **<100ms push** (vs 0-500ms polling)

### After Phase 4B (Medium Effort)
- Build time: **27s** (10% improvement)
- Startup time: **0.3s faster**
- Widget scans: **50% faster**

### After Phase 4C (Major Refactors)
- State file size: **10KB** (5x smaller)
- Dialogue sequences: **25ms** (4x faster)
- State reads: **40% faster** (mmap)

---

## See Also

- **OPTIMIZATIONS.md** - Phases 1-3 completed optimizations
- **CONFIGURATION.md** - Settings tuning guide
- **monitor.py** - Performance monitoring tool
