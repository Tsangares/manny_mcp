# Manny MCP Optimization Roadmap

**Status:** Phase 3 Complete, Phase 4 Planned
**Last Updated:** 2025-12-26

## Overview

This roadmap tracks all optimization phases for the Manny MCP server, from initial audit through future enhancements.

---

## Phase 1: Quick Wins ✅ COMPLETE

**Effort:** 1-2 hours
**Status:** Deployed to production
**Date:** 2025-12-26

### Optimizations
1. Incremental builds by default (clean=False)
2. State change detection in GameEngine.java
3. Server-side widget filtering

### Results
- **10x faster builds** (5min → 30s)
- **90% fewer state writes** (60/min → 6-10/min)
- **10x less data transfer** for filtered widget scans

### Documentation
- `OPTIMIZATIONS.md` lines 21-51

---

## Phase 2: Medium Effort ✅ COMPLETE

**Effort:** 1-2 days
**Status:** Deployed to production
**Date:** 2025-12-26

### Optimizations
1. Event-driven file monitoring with watchdog
2. Smart file sectioning for prepare_code_change
3. Pre-compiled anti-pattern regexes

### Results
- **500x faster commands** (<1ms latency vs 50ms polling)
- **99% smaller context** (720KB → 2-4KB for PlayerHelpers.java)
- **100x faster anti-pattern scans** (0.1ms vs 10ms)

### Documentation
- `OPTIMIZATIONS.md` lines 54-82

---

## Phase 3: Major Refactors ✅ COMPLETE

**Effort:** 1 week
**Status:** Deployed to production
**Date:** 2025-12-26

### Optimizations
1. Unified search engine with inverted index
2. LRU cache layer with TTL expiration
3. Integration into manny_tools.py

### Results
- **1,000x faster searches** (0.05ms vs 50ms)
- **938x faster cached queries**
- **O(1) code lookups** vs O(n) file scans

### Documentation
- `OPTIMIZATIONS.md` lines 86-117

---

## Phase 4: Additional Optimizations 🔄 PLANNED

**Effort:** 2-3 days total
**Status:** Audited, ready for implementation

### Phase 4A: Quick Wins (2-3 hours)

| Optimization | Effort | Impact | File |
|--------------|--------|--------|------|
| Dashboard event-driven state | 30min | 90% fewer reads | dashboard.py:904-914 |
| H.264 encoder caching | 15min | 1-4s faster start | dashboard.py:643-682 |
| Dashboard WebSocket push | 45min | 50% less bandwidth | dashboard.py:548-621 |
| orjson serialization | 30min | 2-3x faster JSON | All Python files |

**Projected Results:**
- 90% reduction in dashboard state file reads
- Dashboard starts 1-4s faster (after first run)
- 50% reduction in HTTP request overhead
- 2-3x faster JSON serialization across all tools

### Phase 4B: Medium Effort (1-2 days)

| Optimization | Effort | Impact | File |
|--------------|--------|--------|------|
| Lazy module imports | 4hrs | Faster startup | server.py:1-80 |
| Build artifact caching | 2hrs | 5-10% faster builds | server.py:364-381 |
| Widget scanning modes | 6hrs | 50-80% faster checks | PlayerHelpers.java |

**Projected Results:**
- 200-500ms faster MCP server startup
- Build times: 30s → 27s
- Widget existence checks 50-80% faster

### Phase 4C: Major Refactors (optional, 2-4 weeks)

These are lower priority, high-effort optimizations:

| Optimization | Effort | Impact | Notes |
|--------------|--------|--------|-------|
| Protobuf state format | 2wks | 5x compression | Requires Java+Python migration |
| Command batching API | 1wk | 3-5x faster dialogues | Requires Java protocol changes |
| Memory-mapped state | 5d | 30-50% faster reads | Complex concurrency handling |

### Documentation
- `OPTIMIZATION_PHASE4_AUDIT.md` (full details)

---

## Cumulative Performance Improvements

### Baseline (Before Optimizations)
- Build time: 5 minutes (clean)
- Command latency: 500ms average
- Code searches: 50ms per search
- State writes: 60/min
- Context size: 720KB (full PlayerHelpers.java)

### After Phase 3 (Current)
- Build time: **30s** (10x improvement)
- Command latency: **<1ms** (500x improvement)
- Code searches: **0.05ms** (1,000x improvement)
- Cached queries: **0.02ms** (938x improvement)
- State writes: **6-10/min** (90% reduction)
- Context size: **2-4KB** (99% reduction)

### After Phase 4A (Projected)
All Phase 3 benefits, plus:
- Dashboard state reads: **10/min** (90% reduction from 100/min)
- JSON operations: **2-3x faster**
- Dashboard latency: **<100ms** push (vs 0-500ms polling)

### After Phase 4B (Projected)
All Phase 3 + 4A benefits, plus:
- Build time: **27s** (additional 10% improvement)
- Server startup: **0.3s faster**
- Widget scans: **50% faster**

---

## Implementation Priority

### High Priority (Recommended Next)
✅ **Phase 1-3:** Complete

🎯 **Phase 4A Quick Wins:**
- Minimal risk, high impact
- 2-3 hours total effort
- Immediate user-visible improvements
- All optimizations are backward compatible with rollback

### Medium Priority
🔄 **Phase 4B Medium Effort:**
- Moderate risk, good ROI
- 1-2 days effort
- Incremental improvements to existing metrics
- Consider after 4A deployed and validated

### Low Priority (Optional)
⏸️ **Phase 4C Major Refactors:**
- High risk, high effort
- 2-4 weeks total
- Diminishing returns (most gains already captured)
- Only pursue if specific use case demands it

---

## Risk Assessment

### Phase 4A Risks: LOW
- All changes have simple rollback procedures
- Event-driven monitoring has polling fallback
- orjson has json fallback
- WebSocket push has HTTP polling fallback
- No protocol changes required

### Phase 4B Risks: MEDIUM
- Lazy imports could introduce import errors at runtime
- Widget scanning changes require Java recompilation
- Build caching could cause stale artifact issues

### Phase 4C Risks: HIGH
- Protobuf requires migration path for existing deployments
- Command batching changes plugin protocol
- Memory-mapped I/O has complex concurrency edge cases

---

## Testing Strategy

### Phase 4A Testing
1. **Dashboard Event-Driven State**
   - Start dashboard, verify state updates appear
   - Stop RuneLite, verify dashboard shows staleness
   - Measure state file read count (should be ~10/min)

2. **H.264 Encoder Caching**
   - First dashboard start: measure encoder detection time
   - Restart dashboard: verify cache hit (<10ms)
   - Delete cache, verify detection runs again

3. **Dashboard WebSocket Push**
   - Open dashboard, verify updates without HTTP polling
   - Check browser network tab: should see SSE connection, no polling
   - Measure bandwidth usage (should be 50% lower)

4. **orjson Serialization**
   - Run monitor.py, check JSON operation speed
   - Compare with baseline (should be 2-3x faster)
   - Verify all JSON operations still produce correct output

### Phase 4B Testing
1. **Lazy Module Imports**
   - Cold start MCP server, measure startup time
   - Use tool from each module, verify no import errors
   - Profile memory usage (should be lower)

2. **Build Artifact Caching**
   - Run 5 incremental builds, measure times
   - Should be more consistent (25-27s range vs 25-35s)

3. **Widget Scanning Modes**
   - Test SCAN_WIDGETS_FAST for existence check
   - Measure latency vs full SCAN_WIDGETS
   - Verify accuracy (no false negatives)

---

## Monitoring Additions

### New Metrics for Phase 4

Add to `monitor.py`:

```python
BASELINES["dashboard_state_reads_per_min"] = {
    "expected": 10,
    "alert_threshold": 50
}

BASELINES["json_serialize_ms"] = {
    "expected": 0.5,
    "alert_threshold": 5.0
}

BASELINES["server_startup_time"] = {
    "expected": 0.8,
    "alert_threshold": 2.0
}

BASELINES["widget_scan_fast_ms"] = {
    "expected": 5,
    "alert_threshold": 20
}
```

---

## Configuration Changes

### Phase 4A Config

```python
# dashboard.py
USE_EVENT_DRIVEN_STATE = True  # Set to False to disable
CACHE_H264_ENCODER = True      # Set to False for re-detection
USE_WEBSOCKET_PUSH = True      # Set to False for HTTP polling

# All Python files
USE_ORJSON = True  # Automatic fallback if orjson not installed
```

### Phase 4B Config

```python
# server.py
LAZY_IMPORTS = True  # Set to False to eager load all modules

# Build settings
cmd.extend([
    "-Dmaven.compiler.useIncrementalCompilation=true",
    "-Dmaven.compiler.incremental=true",
])
```

---

## Success Criteria

### Phase 4A Success Criteria
- [ ] Dashboard state file reads: <20/min (target: 10/min)
- [ ] Dashboard startup: <2s after first run (target: <1s)
- [ ] Dashboard HTTP requests: <10/min (target: 0, WebSocket only)
- [ ] JSON serialization: <2ms per call (target: 0.5ms)
- [ ] No regressions in existing metrics
- [ ] All tests pass

### Phase 4B Success Criteria
- [ ] Server startup: <1s (target: 0.5s)
- [ ] Build time: <28s average (target: 27s)
- [ ] Widget fast scan: <10ms (target: 5ms)
- [ ] No import errors after lazy loading
- [ ] No regressions in existing metrics

---

## Future Research

### Beyond Phase 4

1. **Profile-Guided Optimization (PGO)**
   - Use Java Flight Recorder to profile manny plugin
   - Identify hot methods for optimization
   - Potential: 10-20% JVM performance improvement

2. **HTTP/2 or gRPC for MCP**
   - Evaluate binary protocol vs JSON-RPC
   - Potential: 2-3x lower tool call latency
   - Caveat: Requires upstream MCP protocol changes

3. **Rust Rewrite of Hot Paths**
   - Candidates: indexing, regex matching
   - Potential: 5-10x speedup
   - Effort: Very high (weeks)

4. **Distributed Caching**
   - Share cache across multiple Claude Code instances
   - Redis or memcached backend
   - Benefit: Team-wide cache hits

---

## Documentation Structure

```
/home/wil/manny-mcp/
├── CLAUDE.md                              # Main guidance (Phase 1-3 summary)
├── OPTIMIZATIONS.md                       # Phase 1-3 details and architecture
├── CONFIGURATION.md                       # Settings tuning guide
├── OPTIMIZATION_PHASE4_AUDIT.md          # Phase 4 detailed audit
├── OPTIMIZATION_ROADMAP.md               # This file (meta-view)
├── monitor.py                             # Performance monitoring tool
├── cache_layer.py                         # Phase 3: LRU cache
├── search_engine.py                       # Phase 3: Inverted index
└── ...

Documentation Hierarchy:
1. CLAUDE.md - Read first (quick overview)
2. OPTIMIZATIONS.md - Phase 1-3 implementation details
3. CONFIGURATION.md - Tuning guide for your hardware
4. OPTIMIZATION_ROADMAP.md - Meta view of all phases
5. OPTIMIZATION_PHASE4_AUDIT.md - Deep dive into future work
```

---

## Timeline

| Phase | Effort | Status | Date |
|-------|--------|--------|------|
| Phase 1 | 2 hrs | ✅ Complete | 2025-12-26 |
| Phase 2 | 2 days | ✅ Complete | 2025-12-26 |
| Phase 3 | 1 week | ✅ Complete | 2025-12-26 |
| Phase 4A | 3 hrs | 🔄 Planned | TBD |
| Phase 4B | 2 days | 🔄 Planned | TBD |
| Phase 4C | 4 weeks | ⏸️ Optional | TBD |

---

## Questions & Decisions

### Should we implement Phase 4A?
**Recommendation:** YES
- Low risk, high reward
- 2-3 hours total effort
- Immediate impact on dashboard UX
- All changes have rollback

### Should we implement Phase 4B?
**Recommendation:** MAYBE
- Medium risk, medium reward
- Consider after Phase 4A validated
- Build caching has most value if builds are a bottleneck

### Should we implement Phase 4C?
**Recommendation:** NO (unless specific need)
- High risk, high effort
- Diminishing returns (most gains already captured)
- Only pursue if:
  - State file size becomes a problem (>100KB)
  - Dialogue automation becomes bottleneck
  - Memory-mapped I/O needed for concurrency

---

## Contacts & Support

For questions about optimizations:
- See OPTIMIZATIONS.md for implementation details
- See CONFIGURATION.md for tuning guide
- Use `monitor.py --metric all` to check current performance
- Check git history for optimization commits

---

## Changelog

**2025-12-26:**
- Phase 1-3 completed and documented
- Phase 4 audited and planned
- Roadmap created
