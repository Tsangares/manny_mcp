# Quest Status Command - Response Overwrite Lessons
**Date:** 2025-01-16

## The Problem

`GET_QUEST_STATUS f2p` command executed successfully and logs showed "Retrieved 23 quests", but the response file `/tmp/manny_response.json` only contained `{"message": "Quest status retrieved"}` instead of the full quest data.

## Root Cause

The `CommandBase.execute()` method automatically calls `writeSuccess(getSuccessMessage(args))` AFTER `executeCommand()` returns. This overwrote my detailed response:

**Flow causing the bug** (`CommandBase.java:56-71`):
```java
boolean success = executeCommand(args);  // My code calls writeSuccess(result)
if (success) {
    String successMsg = getSuccessMessage(args);
    if (successMsg != null) {
        writeSuccess(successMsg);  // OVERWRITES my result!
    }
}
```

My `executeCommand()` called `writeSuccess(result)` with the quest data, but then the base class called `writeSuccess(getSuccessMessage())` which wrote just the message string.

## Key Lessons

### 1. Commands with Structured Data Must Return null from getSuccessMessage()

**What happened:** Quest data was written correctly, then immediately overwritten by the default success message.
**Why:** CommandBase assumes simple commands only need a message string, not a data Map.
**Solution:**
```java
// BAD - default implementation returns a message that overwrites your data
@Override
protected String getSuccessMessage(String args) {
    return "Quest status retrieved";
}

// GOOD - return null to prevent base class from overwriting
@Override
protected String getSuccessMessage(String args) {
    // Return null to prevent base class from overwriting our detailed result
    return null;
}
```

### 2. ResponseWriter Has Two writeSuccess() Overloads

**What happened:** I initially tried `writeSuccess(jsonString)` thinking it would preserve the JSON.
**Why:** `writeSuccess(String)` wraps the string in `{"message": "..."}`, losing structure.
**Solution:**
```java
// BAD - wraps in message object
writeSuccess(gson.toJson(result));  // Becomes {"message": "{...escaped json...}"}

// GOOD - preserves structure
writeSuccess(result);  // Result map is serialized directly to JSON
```

### 3. Widget IDs for Tabs Are Interface-Specific

**What happened:** Added `QUEST_TAB_CHILD = 0x52` but quest tab didn't open.
**Why:** The widget ID 0x52 is for the main game interface (548), but quest list is a sub-interface. F3 key works because it opens the tab directly.
**Workaround:** Use F3 key input instead of widget ID check for quest tab.

## Anti-Patterns

1. **Don't assume writeSuccess(String) preserves JSON structure** - It wraps in a message object
2. **Don't forget to check base class behavior** - CommandBase has automatic response writing that can interfere
3. **Don't test response files during multi-command sessions** - Subsequent commands overwrite the response

## Debugging Commands

| Command | Purpose |
|---------|---------|
| `cat /tmp/manny_response.json` | Check actual response content |
| `get_logs(grep="QUEST")` | Verify command executed and data was retrieved |
| Read `CommandBase.java:56-71` | Understand automatic response writing flow |

## Interface Gaps Identified

- [x] Plugin: Added `GET_QUEST_STATUS` command with proper response handling
- [x] Plugin: Added `TAB_OPEN quest` support (F3 key)
- [ ] Documentation: Commands returning structured data MUST return null from `getSuccessMessage()`

## Files Modified

| File | Change |
|------|--------|
| `manny_src/utility/commands/GetQuestStatusCommand.java` | New command - reads all quests from RuneLite API |
| `manny_src/utility/commands/TabOpenCommand.java` | Added "quest"/"quests" case |
| `manny_src/utility/GameEngine.java` | Added QUEST_TAB_CHILD and openQuests() method |
| `manny_src/utility/PlayerHelpers.java` | Registered GET_QUEST_STATUS command |
| `mcptools/tools/quests.py` | MCP tools for quest queries |
| `server.py` | Import and wire up quests module |

## Pattern Reference

Commands returning structured data should follow this pattern:
```java
@Override
protected boolean executeCommand(String args) {
    Map<String, Object> result = new HashMap<>();
    result.put("data", complexData);
    result.put("summary", summaryData);

    writeSuccess(result);  // Use Map overload
    return true;
}

@Override
protected String getSuccessMessage(String args) {
    return null;  // CRITICAL: prevent overwrite
}
```
