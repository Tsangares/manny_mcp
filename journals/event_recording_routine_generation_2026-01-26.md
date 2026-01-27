# Event Recording for Routine Generation - Lessons Learned
**Date:** 2026-01-26

## The Problem

Wanted to implement "Play a quest once → Generate a replayable routine" but the LocationHistory ring buffer only captured positions (x, y, plane, timestamp), not what the player was doing. Session recordings existed but weren't correlated with location data.

## Root Cause

The plugin's `LocationEntry` class in `GameEngine.java:7075-7085` was designed for movement tracking only. It had no fields to capture:
- What command was executed
- What NPC/object was interacted with
- What dialogue option was selected
- What inventory changes occurred

Additionally, command handlers didn't call back to LocationHistory when executing.

## Key Lessons

### 1. Empty Java Files Cause Cascading "Cannot Find Symbol" Errors

**What happened:** Build failed with "cannot find symbol class LocationHistory" but LocationHistory was clearly defined. Spent time checking imports, class visibility, package structure.

**Why:** An unrelated file (`GotoCommand.java`) was corrupted to 0 bytes. Java compiler failed to process it, which caused cascading failures in classes that imported it, masking the real error.

**Solution:**
```bash
# BAD - Debugging the wrong error message
# Looking at LocationHistory imports, class visibility, etc.

# GOOD - Check for empty/corrupted files first
ls -la /path/to/commands/*.java | grep "^.* 0 "  # Find 0-byte files
git checkout HEAD -- corrupted_file.java  # Restore from git
```

### 2. Setter Injection for Circular Dependencies

**What happened:** Needed LocationHistory in PlayerHelpers and InteractionSystem, but they're created before LocationHistory is initialized.

**Why:** Guice constructor injection happens at startup. LocationHistory starts later (after `startUp()`). Can't inject something that doesn't exist yet.

**Solution:**
```java
// BAD - Constructor injection (fails for late-initialized objects)
public PlayerHelpers(LocationHistory locationHistory) {
    this.locationHistory = locationHistory;  // NPE at startup
}

// GOOD - Setter injection after initialization
private LocationHistory locationHistory;

public void setLocationHistory(LocationHistory locationHistory) {
    this.locationHistory = locationHistory;
    if (this.interactionSystem != null) {
        this.interactionSystem.setLocationHistory(locationHistory);
    }
}

// In MannyPlugin.startUp():
locationHistory.start();
playerHelpers.setLocationHistory(locationHistory);
```

### 3. Event Recording Must Be Non-Blocking

**What happened:** Added event recording in interaction handlers. Needed to ensure recording failures don't break gameplay.

**Why:** LocationHistory writes to disk periodically. If recording throws, it could interrupt NPC interactions.

**Solution:**
```java
// BAD - Recording failure breaks interaction
locationHistory.recordInteraction(npcName, action, x, y, command);
return true;  // Never reached if recording throws

// GOOD - Wrap in try-catch, log and continue
if (locationHistory != null) {
    try {
        locationHistory.recordInteraction(npcName, action, x, y, command);
    } catch (Exception e) {
        log.debug("[INTERACT] Failed to record event: {}", e.getMessage());
    }
}
return true;
```

### 4. Event Data Schema Design

**What happened:** Needed to decide what fields to add to LocationEntry for routine generation.

**Why:** Too few fields = can't generate useful routines. Too many = bloated ring buffer, complex code.

**Solution:** Added exactly what's needed for YAML routine generation:
```java
@Data
public static class LocationEntry {
    // Existing
    public long ts;
    public int x, y, plane;
    public String cmd;

    // NEW: Event context
    public String eventType;      // "move", "interact", "dialogue", "inventory", "door"
    public String command;        // Full command (e.g., "INTERACT_NPC Guard Talk-to")
    public String target;         // NPC/object name
    public String action;         // "Talk-to", "Open", "Shear"
    public Integer targetX, targetY;  // Where target was
    public String dialogueOption; // Selected option text
    public String inventoryDelta; // "+Wool", "-Grain"
}
```

## Anti-Patterns

1. **Don't** assume "cannot find symbol" means the symbol doesn't exist - Check for corrupted files first
2. **Don't** use constructor injection for objects initialized after startup - Use setter injection
3. **Don't** let recording failures interrupt gameplay - Always wrap in try-catch
4. **Don't** add fields "just in case" - Only what's needed for the use case

## Debugging Commands

| Command | Purpose |
|---------|---------|
| `ls -la *.java \| grep " 0 "` | Find empty/corrupted Java files |
| `git show HEAD:path/to/file.java` | Check git for original content |
| `git checkout HEAD -- file.java` | Restore file from git |
| `mvn compile 2>&1 \| grep manny` | Filter build errors to plugin only |
| `get_event_history(last_minutes=5)` | Verify events are being captured |

## Interface Gaps Identified

- [x] Plugin needs: Event recording hooks in command handlers (IMPLEMENTED)
- [x] Plugin needs: Extended LocationEntry with event fields (IMPLEMENTED)
- [x] MCP needs: `get_event_history` tool to extract events (IMPLEMENTED)
- [x] MCP needs: `generate_routine` tool to create YAML (IMPLEMENTED)
- [ ] Plugin needs: Inventory change tracking (not yet hooked - requires ItemContainerChanged event)
- [ ] MCP needs: Routine validation against generated output

## Files Modified

| File | Change |
|------|--------|
| `manny_src/utility/GameEngine.java` | Extended LocationEntry with event fields, added recordXxx() methods |
| `manny_src/utility/PlayerHelpers.java` | Added LocationHistory field/setter, hooked dialogue recording |
| `manny_src/utility/InteractionSystem.java` | Added LocationHistory field/setter, hooked NPC/object recording |
| `manny_src/MannyPlugin.java` | Wired LocationHistory to PlayerHelpers after startup |
| `mcptools/tools/location_history.py` | Added `get_event_history` tool |
| `mcptools/tools/routine_generator.py` | NEW: `generate_routine` tool |
| `server.py` | Registered routine_generator module |

## New MCP Tools Created

### get_event_history
```python
get_event_history(last_minutes=15, include_suggestions=True)
# Returns:
# - events grouped by type (interactions, dialogues, inventory_changes, doors)
# - suggested await_conditions for each event
```

### generate_routine
```python
generate_routine(
    routine_name="Sheep Shearing",
    time_range_minutes=15,
    output_path="routines/generated/sheep_shearing.yaml"
)
# Generates:
# - YAML routine with steps, locations, phases
# - Inferred await_conditions
# - Ready for review and testing
```

## Testing Workflow

1. Rebuild plugin: `build_plugin()`
2. Start RuneLite: `start_runelite(account_id="main", display=":2")`
3. Do some interactions manually (talk to NPC, open door, etc.)
4. Check events: `get_event_history(last_minutes=5)`
5. Generate routine: `generate_routine(routine_name="Test")`
6. Review output YAML, fix object names (add underscores)
7. Test: `execute_routine(routine_path="routines/generated/test_XXX.yaml")`
