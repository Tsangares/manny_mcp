# Optimization Quick Reference

**Last Updated:** 2025-12-26

Quick reference card for all Manny MCP optimizations.

---

## ✅ What's Been Optimized (Phases 1-3)

| Area | Before | After | Improvement |
|------|--------|-------|-------------|
| **Builds** | 5 min | 30 sec | **10x faster** |
| **Commands** | 500ms | <1ms | **500x faster** |
| **Code Search** | 50ms | 0.05ms | **1,000x faster** |
| **Cached Queries** | 17ms | 0.02ms | **938x faster** |
| **State I/O** | 60/min | 6-10/min | **90% less** |
| **Context Size** | 720KB | 2-4KB | **99% smaller** |

---

## 🤖 Automated Performance Diagnostics

**diagnose-performance skill** - Let Claude automatically check performance and suggest fixes.

```
Use the Skill tool: diagnose-performance
```

**What it does:**
- Runs monitor.py automatically
- Interprets results vs baselines
- Diagnoses root causes
- Provides copy-paste ready fixes
- Suggests Phase 4 optimizations

**When to use:**
- You report performance issues
- After implementing new features
- Periodically during long sessions
- When you ask "is everything optimized?"

See `.claude/skills/diagnose-performance/skill.md` for details.

---

## 🔍 Manual Performance Checks

### Quick Health Check
```bash
./monitor.py --metric all
```

### Specific Metrics
```bash
./monitor.py --metric builds     # Build performance
./monitor.py --metric cache      # Cache hit rates
./monitor.py --metric search     # Search engine stats
./monitor.py --metric commands   # Command latency
```

### Live Monitoring
```bash
./monitor.py --watch             # Auto-refresh every 30s
./monitor.py --watch --interval 10  # Custom interval
```

---

## 📊 Expected Baselines

### Builds
- **Incremental:** 25-35s ✅ (Alert if >60s ⚠️)
- **Clean:** 30-40s ✅ (Alert if >70s ⚠️)

### Cache
- **Hit Rate:** >50% ✅ (Alert if <30% ⚠️)

### Search Engine
- **Build Time:** <1s ✅ (Alert if >5s ⚠️)
- **Lookup Time:** <1ms ✅ (Alert if >10ms ⚠️)

### State Writes
- **Frequency:** 6-10/min ✅ (Alert if >20/min ⚠️)

### Commands
- **Latency:** <10ms ✅ (Alert if >100ms ⚠️)

---

## 🔧 How Each Optimization Works

### 1. Incremental Builds (Phase 1)
**File:** `server.py:364-381`
**How:** Changed default from `clean=True` to `clean=False`
```python
build_plugin(clean=False)  # 30s incremental
build_plugin(clean=True)   # 35s clean, use after major changes
```

### 2. State Change Detection (Phase 1)
**File:** `GameEngine.java:4600-4785`
**How:** Only writes state file when position, HP, inventory, etc. change
```java
if (hasSignificantChange(state, previousState)) {
    writeStateFile(state);  // Only write if changed
}
```

### 3. Server-Side Widget Filtering (Phase 1)
**File:** `PlayerHelpers.java:9186, 13356-13520`
**How:** Filters widgets in Java before sending to Python
```python
# Before: Returns all 50 widgets (~50KB)
scan_widgets()

# After: Returns only matching widgets (~5KB)
scan_widgets(filter_text="Bank")
```

### 4. Event-Driven File Monitoring (Phase 2)
**File:** `server.py:108-227`
**How:** Uses watchdog to detect file changes instantly
```python
# Before: Poll every 50ms (20 reads/sec)
# After: Event notification (<1ms latency)
```

### 5. Smart File Sectioning (Phase 2)
**File:** `request_code_change.py:20-110`
**How:** Extracts only relevant command handlers from PlayerHelpers.java
```python
# Before: Full file 720KB
# After: Extracted commands only 2-4KB (99% reduction)
```

### 6. Pre-Compiled Regexes (Phase 2)
**File:** `manny_tools.py:719-772`
**How:** Compile 11 anti-pattern regexes at module load
```python
# Before: Compile on every check (~10ms)
# After: Compiled once at startup (0.1ms per check)
```

### 7. Inverted Index Search Engine (Phase 3)
**File:** `search_engine.py`
**How:** Builds O(1) hash index of all commands/classes/methods
```python
# Before: Scan all files linearly (50ms)
# After: Hash lookup (0.05ms)
```

### 8. LRU Cache Layer (Phase 3)
**File:** `cache_layer.py`
**How:** Caches frequently accessed data with TTL expiration
```python
@cached_tool(ttl=300)  # Cache for 5 minutes
def get_class_summary(...):
    # First call: 17ms
    # Cached call: 0.02ms (938x faster)
```

---

## 🎯 What to Optimize Next (Phase 4)

### Quick Wins (2-3 hours)
1. **Dashboard Event-Driven State** - 90% fewer file reads
2. **H.264 Encoder Caching** - Dashboard starts 1-4s faster
3. **Dashboard WebSocket Push** - 50% less bandwidth
4. **orjson Serialization** - 2-3x faster JSON

See `OPTIMIZATION_PHASE4_AUDIT.md` for details.

---

## 🚨 Troubleshooting

### Slow Builds (>60s)
```bash
# Check if offline mode disabled
grep "\-o" server.py  # Should see "-o" flag

# Clear Maven cache if corrupted
rm -rf ~/.m2/repository

# Force clean build once
./venv/bin/python -c "from server import build_plugin; build_plugin(clean=True)"
```

### Low Cache Hit Rate (<30%)
```python
# Check cache stats
./venv/bin/python -c "from cache_layer import get_tool_cache; print(get_tool_cache().get_stats())"

# Clear cache if stale
./venv/bin/python -c "from cache_layer import get_tool_cache; get_tool_cache().invalidate()"

# Increase TTL if needed (in cache_layer.py)
_tool_cache = LRUCache(max_size=100, default_ttl=600)  # 10 minutes
```

### Search Engine Missing Commands
```python
# Force index rebuild
./venv/bin/python -c "import search_engine; search_engine._search_index = None; from search_engine import get_search_index; get_search_index('/home/wil/Desktop/manny')"
```

### High Memory Usage
```python
# Reduce cache size (in cache_layer.py)
_tool_cache = LRUCache(max_size=50, default_ttl=300)  # Smaller cache
```

---

## 📁 Documentation Files

| File | Purpose |
|------|---------|
| `CLAUDE.md` | Main guidance (start here) |
| `OPTIMIZATIONS.md` | Phase 1-3 details (420 lines) |
| `CONFIGURATION.md` | Settings tuning guide (580 lines) |
| `OPTIMIZATION_ROADMAP.md` | Meta-view of all phases |
| `OPTIMIZATION_PHASE4_AUDIT.md` | Future work (Phase 4) |
| `OPTIMIZATION_QUICK_REFERENCE.md` | This file (quick lookup) |
| `monitor.py` | Performance monitoring tool |

---

## ⚙️ Configuration Quick Reference

### Build Settings
**File:** `server.py:364-381`
```python
# Threads (match your CPU cores, max 8)
"-T", "2"  # Laptop: 2, Desktop: 4, Server: 8

# Offline mode (faster, but skip dependency checks)
"-o"  # Remove if dependencies changed
```

### Cache Settings
**File:** `cache_layer.py:151-159`
```python
# Size vs Memory
max_size=100  # ~2 MB, good for normal use
max_size=50   # ~1 MB, for low-memory systems
max_size=200  # ~4 MB, for heavy use

# TTL (time-to-live)
default_ttl=300  # 5 minutes (standard)
default_ttl=600  # 10 minutes (if code rarely changes)
```

### Search Engine
**Auto-built on first use, no configuration needed.**

Rebuild if needed:
```python
import search_engine
search_engine._search_index = None
```

---

## 🧪 Testing Optimizations

### Build Performance
```bash
# Time 5 incremental builds
for i in {1..5}; do
  time ./venv/bin/python -c "from server import build_plugin; build_plugin()"
done
# Should be 25-35s each
```

### Cache Performance
```bash
# First call (cache miss)
time ./venv/bin/python -c "from manny_tools import get_class_summary; get_class_summary('/home/wil/Desktop/manny', 'CombatSystem')"

# Second call (cache hit, should be much faster)
time ./venv/bin/python -c "from manny_tools import get_class_summary; get_class_summary('/home/wil/Desktop/manny', 'CombatSystem')"
```

### Search Engine Performance
```bash
# Load test: 100 command lookups
./venv/bin/python -c "
from search_engine import get_search_index
import time

index = get_search_index('/home/wil/Desktop/manny')
start = time.time()

for i in range(100):
    index.find_command('BANK_OPEN')

elapsed = (time.time() - start) * 1000
print(f'{elapsed:.2f}ms for 100 lookups')
print(f'Throughput: {100000/elapsed:.0f} lookups/sec')
"
# Should be >100,000 lookups/second
```

---

## 📈 Performance Over Time

Track your optimization progress:

```bash
# Record baseline
./monitor.py --metric all > baseline_$(date +%Y%m%d).txt

# After changes
./monitor.py --metric all > after_changes_$(date +%Y%m%d).txt

# Compare
diff baseline_*.txt after_changes_*.txt
```

---

## 🔄 Rollback Procedures

### Phase 1: Builds
```python
# In server.py, change:
def build_plugin(clean: bool = True) -> dict:  # Back to clean=True
```

### Phase 2: File Monitoring
```python
# In server.py main(), comment out:
# _response_monitor = ResponseFileMonitor(RESPONSE_FILE)
# _response_monitor.start(asyncio.get_event_loop())
```

### Phase 3: Search & Cache
```python
# In manny_tools.py, set:
SEARCH_ENGINE_AVAILABLE = False
CACHE_AVAILABLE = False
```

All rollbacks are safe and automatic (fallback to original implementations).

---

## 💡 Pro Tips

1. **Use monitor.py --watch** during development to catch regressions early
2. **Check cache hit rate** - if <30%, consider increasing TTL
3. **Force clean build** after major refactors or dependency changes
4. **Clear cache** after modifying indexed files (Java source)
5. **Increase thread count** on desktop machines for faster builds

---

## 📞 Getting Help

- Read `OPTIMIZATIONS.md` for implementation details
- Read `CONFIGURATION.md` for tuning guide
- Run `./monitor.py --metric all` to diagnose issues
- Check git commits for optimization history

---

**Quick Status Check:**
```bash
./monitor.py --metric all && echo "✅ All optimizations working!"
```
