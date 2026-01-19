# Gamescope Multi-Instance & Process Management - Lessons Learned
**Date:** 2026-01-18

## The Problem

Two issues surfaced:
1. Additional displays (`:3`, `:4`) used plain Xwayland instead of gamescope
2. Killing "duplicate" RuneLite processes killed the wrong ones - main instead of aux

## Root Cause

### Display Setup
`start_screen.sh` used gamescope only for the primary display (`:2`), falling back to plain Xwayland for additional displays because "gamescope picks its own display number."

### Process Management
The MCP only tracks processes it started. Processes started manually or from previous sessions appear "unmanaged" even if they're actively being used. Blindly killing unmanaged processes kills legitimate sessions.

## Key Lessons

### 1. Gamescope Supports Multiple Instances

**What happened:** Assumed gamescope couldn't run multiple instances.
**Why wrong:** Gamescope handles this gracefully - second instance becomes `gamescope-1` and picks the next available display.

**Evidence:**
```
[gamescope] [wlserver:] unable to lock lockfile /run/user/1000/gamescope-0.lock
[gamescope] [wlserver:] Running compositor on wayland display 'gamescope-1'
[gamescope] [wlserver:] [xwayland/server.c:107] Starting Xwayland on :4
```

### 2. Don't Kill Processes Without Verification

**What happened:** Saw 3 RuneLite processes, MCP showed only 1 managed (aux). Killed the other 2 assuming they were duplicates.
**Result:** Killed main (user's active session).

**Solution:** Before killing any process, verify what's actually running on each:
```bash
# Check windows on a display
DISPLAY=:3 xdotool search --name "." | head -5

# Or check which account's state file is updating
ls -la /tmp/manny_*_state.json
```

### 3. MCP Process Tracking Gap

**What happened:** Main was running but MCP's `runelite_status(list_all=True)` only showed aux.
**Why:** Main was started outside MCP management (manually or previous session).

**Interface gap:** Need a way to detect ALL RuneLite processes and map them to accounts, not just MCP-managed ones.

## Anti-Patterns

1. **Don't** kill unmanaged processes assuming they're orphans - verify first
2. **Don't** restart killed processes without asking - takes over management unexpectedly
3. **Don't** assume gamescope can only run one instance

## Debugging Commands

| Command | Purpose |
|---------|---------|
| `ps aux \| grep runelite` | Find ALL RuneLite processes |
| `runelite_status(list_all=True)` | Only shows MCP-managed processes |
| `DISPLAY=:N xdotool search --name "."` | Check if display has windows |
| `ls /tmp/.X11-unix/` | See all active X displays |

## Interface Gaps Identified

- [x] `start_screen.sh` now uses gamescope for all displays
- [ ] MCP needs: Detection of unmanaged RuneLite processes with account identification
- [ ] MCP needs: `list_all_runelite_processes()` that shows managed AND unmanaged
- [ ] CLAUDE.md needs: Warning about killing processes without verification

## Files Modified

| File | Change |
|------|--------|
| `start_screen.sh` | Additional displays (`:3`, `:4`, etc.) now use gamescope instead of plain Xwayland |

## Additional Context

**Why gamescope is better than plain Xwayland:**
- Better input handling (important for game automation)
- GPU compositing built-in
- Designed for gaming workloads
- `--force-windows-fullscreen` makes X11 apps behave correctly
