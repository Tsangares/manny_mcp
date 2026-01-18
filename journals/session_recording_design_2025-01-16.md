# Session Recording Design - Lessons Learned
**Date:** 2025-01-16

## The Problem

Debugging failed autonomous sessions was painful. When a quest failed or a routine broke, there was no way to see:
- What commands were sent in what order
- What state changes occurred
- Where exactly things went wrong

Manual reconstruction required grepping logs and correlating timestamps - tedious and error-prone.

## Root Cause

No observability layer existed between Claude Code and the plugin. Commands went into `/tmp/manny_command.txt` and state came out of `/tmp/manny_state.json`, but nothing recorded the causal chain.

## Key Lessons

### 1. MCP-Side Recording is Sufficient (No Plugin Changes Needed)

**What happened:** Initial proposal suggested plugin-side (Java) recording as "recommended" with MCP-side as "fallback."

**Why MCP-side is actually better:**
- Plugin already writes state every tick - adding more I/O risks contention
- YAML serialization in Java requires SnakeYAML dependency or manual string building
- Thread safety is complex (commands from file watcher, state from game tick)
- **Most importantly:** Claude's reasoning, goal descriptions, and context only exist at MCP level

**Solution:**
```python
# MCP-side captures everything we need:
# 1. Commands (via send_command wrapper)
# 2. State changes (via get_game_state wrapper)
# 3. Claude's descriptions and reasoning (MCP-only context)

# Plugin-side would miss #3 entirely and complicate #1-2 with threading
```

### 2. Delta-Only State Recording (Critical for File Size)

**What happened:** Full state snapshots would create massive session files (~2500 tokens per snapshot).

**Why:** Game state includes 28 inventory slots, 23 skills, 11 equipment slots, combat info, etc. Recording this on every `get_game_state` call would explode file size.

**Solution:**
```python
# BAD - Full state every time
- type: state
  inventory: [... 28 items ...]
  skills: [... 23 skills ...]
  # ~100 lines per event

# GOOD - Delta only (what changed)
- type: state_delta
  changes:
    location: {x: 3243, y: 3208}
    inventory_added: ["Ghostspeak amulet"]
    # ~5 lines per event
```

Implementation tracks `last_state` and computes diff:
```python
def _compute_delta(self, old: dict, new: dict) -> dict:
    delta = {}
    # Only record what changed
    if old.get("location") != new.get("location"):
        delta["location"] = new.get("location")
    # ... similar for inventory, equipment, dialogue, etc.
    return delta  # Empty dict if nothing changed
```

### 3. Hybrid: Always-On Commands + Explicit Sessions

**What happened:** Initially rejected always-on, but realized a hybrid approach works best.

**Why hybrid:**
- Commands alone are lightweight (~50 bytes each) - safe to always log
- State deltas are heavier - only needed for full session recording
- Daily files auto-rotate - no unbounded growth
- You can always look back even if you forgot to start recording

**Solution:**
```python
# ALWAYS happening (lightweight):
# /tmp/manny_sessions/commands_2025-01-16.yaml
# Every send_command() appends: timestamp + command

# EXPLICIT session (full tracking):
start_session_recording(goal="Complete The Restless Ghost quest")
# ... commands + state deltas recorded ...
add_session_marker(label="Phase 2: Get amulet")  # Optional checkpoints
# ... more commands ...
stop_session_recording()  # Returns filepath

# Forgot to start? No problem:
get_command_history(last_n=100)  # See recent commands anyway
```

### 4. Lazy Imports to Avoid Circular Dependencies

**What happened:** Session module needs to be imported by commands.py and monitoring.py, but session.py also uses the registry.

**Why:** Python circular import errors would crash the server.

**Solution:**
```python
# In commands.py and monitoring.py:
_session_recorder = None

def _get_recorder():
    """Lazy import session recorder."""
    global _session_recorder
    if _session_recorder is None:
        from .session import recorder
        _session_recorder = recorder
    return _session_recorder
```

## Anti-Patterns

1. **Don't record full state** - Delta-only keeps files manageable
2. **Don't always-on record state deltas** - Too heavy; commands-only is fine for always-on
3. **Don't put recording in plugin** - MCP layer has all the context needed
4. **Don't forget the goal** - `start_session_recording(goal=...)` makes sessions meaningful

## Architecture Summary

```
┌─────────────────────────────────────────────────────────┐
│  CommandLog (always-on, lightweight)                    │
├─────────────────────────────────────────────────────────┤
│  - Every send_command() → append to daily file          │
│  - Output: /tmp/manny_sessions/commands_YYYY-MM-DD.yaml │
│  - Auto-rotates daily, no unbounded growth              │
└─────────────────────────────────────────────────────────┘
                          +
┌─────────────────────────────────────────────────────────┐
│  SessionRecorder (explicit, full tracking)              │
├─────────────────────────────────────────────────────────┤
│  - Activated via start_session_recording()              │
│  - Tracks commands + state deltas + markers             │
│  - Output: /tmp/manny_sessions/session_<ts>.yaml        │
└─────────────────────────────────────────────────────────┘
```

## MCP Tools Added

| Tool | Purpose |
|------|---------|
| `get_command_history(last_n, date)` | **Always available** - Get commands from daily log |
| `start_session_recording(goal)` | Begin full recording with context |
| `stop_session_recording()` | Stop and return filepath |
| `add_session_marker(label, note)` | Add checkpoint during recording |
| `get_session_events(last_n)` | Peek at recent events without stopping |
| `is_session_recording()` | Check if recording is active |
| `session_to_routine(session_path)` | Convert session → routine YAML |

## Files Modified

| File | Change |
|------|--------|
| `mcptools/tools/session.py` | New file - SessionRecorder class + 6 MCP tools |
| `mcptools/tools/commands.py` | Added `record_command()` call in `send_command` |
| `mcptools/tools/monitoring.py` | Added `record_state_delta()` call in `get_game_state` |
| `server.py` | Import session module |
| `CLAUDE.md` | Documentation section for session recording |

## Future Improvements

- [ ] Session diff tool - Compare two sessions to find divergence points
- [ ] Auto-tag errors - Hook into MCP error handling to auto-record failures
- [ ] Session replay validation - Compare recorded session against expected routine
