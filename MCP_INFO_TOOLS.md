# MCP Information Tools for Routine Building

## Current State Analysis

### Plugin Commands Already Exist!

The plugin already has these query/scan commands:

| Command | Purpose | Handler |
|---------|---------|---------|
| `SCAN_WIDGETS` | Scan all visible widgets (id, text, bounds) | `handleScanWidgets()` |
| `CLICK_DIALOGUE` | Click dialogue option by text | `handleClickDialogue()` |
| `CLICK_CONTINUE` | Click "Click here to continue" | `handleClickContinue()` |
| `QUERY_NPCS` | Query nearby NPCs | exists |
| `QUERY_GROUND_ITEMS` | Query ground items | exists |
| `QUERY_INVENTORY` | Query inventory contents | `handleQueryInventory()` |
| `SCAN_OBJECTS` | Scan nearby objects | `handleScanObjects()` |
| `FIND_NPC` | Find specific NPC | exists |
| `LIST_OBJECTS` | List nearby objects | exists |
| `CLICK_WIDGET` | Click widget by ID | exists |

### The Gap: MCP Doesn't Read Responses!

**Plugin writes to:** `/tmp/manny_response.json`
```java
public static class ResponseWriter {
    private static final String RESPONSE_FILE = "/tmp/manny_response.json";

    public void writeSuccess(String command, Map<String, Object> result) {
        writeResponse(command, "success", result, null);
    }
}
```

**MCP only writes commands, never reads responses!**
```python
# MCP send_command just writes and returns
with open(command_file, "w") as f:
    f.write(command + "\n")
result = {"sent": True, "command": command}  # Never reads response!
```

---

## The Fix: Add Response Reading to MCP

### Option 1: Enhance send_command to read response

```python
async def send_command_with_response(command: str, timeout_ms: int = 3000):
    """Send command and wait for response."""
    command_file = "/tmp/manny_command.txt"
    response_file = "/tmp/manny_response.json"

    # Clear old response
    if os.path.exists(response_file):
        os.remove(response_file)

    # Write command
    with open(command_file, "w") as f:
        f.write(command + "\n")

    # Wait for response
    start = time.time()
    while (time.time() - start) * 1000 < timeout_ms:
        if os.path.exists(response_file):
            with open(response_file) as f:
                return json.load(f)
        await asyncio.sleep(0.05)

    return {"error": "timeout", "command": command}
```

### Option 2: Add dedicated MCP tools that use existing commands

```python
# get_widgets tool
async def get_widgets(filter_text: str = None):
    """Scan widgets via SCAN_WIDGETS command."""
    response = await send_command_with_response("SCAN_WIDGETS")
    if filter_text and response.get("result", {}).get("widgets"):
        response["result"]["widgets"] = [
            w for w in response["result"]["widgets"]
            if filter_text.lower() in (w.get("text") or "").lower()
        ]
    return response

# get_dialogue_state tool
async def get_dialogue_state():
    """Check dialogue state by scanning dialogue widget groups."""
    # Could scan specific widget groups 217, 219, 229, 231
    response = await send_command_with_response("SCAN_WIDGETS")
    # Parse for dialogue widgets
    ...

# click_text tool
async def click_text(text: str):
    """Click dialogue/widget by text via CLICK_DIALOGUE."""
    return await send_command_with_response(f'CLICK_DIALOGUE "{text}"')
```

---

## Proposed MCP Tool Additions

### 1. get_command_response (core infrastructure)

Read the latest response from `/tmp/manny_response.json`.

```json
Input: {}
Output: {
  "command": "SCAN_WIDGETS",
  "status": "success",
  "result": {"widgets": [...], "count": 15},
  "timestamp": "2025-12-21T22:30:00"
}
```

### 2. scan_widgets (wraps SCAN_WIDGETS)

```json
Input: {"filter_text": "What's wrong?"}
Output: {
  "widgets": [
    {"id": 14352385, "text": "What's wrong?", "bounds": "..."}
  ],
  "count": 1
}
```

### 3. get_dialogue (new - checks dialogue state)

```json
Input: {}
Output: {
  "open": true,
  "type": "options",
  "options": [
    {"text": "What's wrong?", "widget_id": 14352385},
    {"text": "I'm busy...", "widget_id": 14352386}
  ],
  "has_continue": false
}
```

### 4. click_text (wraps CLICK_DIALOGUE)

```json
Input: {"text": "What's wrong?"}
Output: {
  "success": true,
  "clicked": "What's wrong?",
  "widget_id": 14352385
}
```

### 5. query_nearby (wraps QUERY_NPCS + SCAN_OBJECTS)

```json
Input: {"radius": 10}
Output: {
  "npcs": [{"name": "Cook", "actions": ["Talk-to"], "distance": 1}],
  "objects": [{"name": "Range", "actions": ["Cook"], "distance": 2}]
}
```

---

## Implementation Plan

### Phase 1: Add response reading (30 min)
1. Add `get_command_response` MCP tool that reads `/tmp/manny_response.json`
2. Add `send_command_and_wait` helper that writes command and waits for response

### Phase 2: Add wrapper tools (1 hour)
1. `scan_widgets` - calls SCAN_WIDGETS, returns parsed widgets
2. `click_text` - calls CLICK_DIALOGUE, returns success/failure
3. `click_continue` - calls CLICK_CONTINUE

### Phase 3: Add composite tools (1 hour)
1. `get_dialogue` - scan dialogue widget groups, return state
2. `query_nearby` - combine QUERY_NPCS + SCAN_OBJECTS

---

## Why This Matters for Routine Building

**Before (broken):**
```
Claude: send_command("CLICK_DIALOGUE What's wrong?")
MCP: {"sent": true}  # No idea if it worked!
Claude: *takes screenshot to check*
```

**After (works):**
```
Claude: click_text("What's wrong?")
MCP: {"success": true, "clicked": "What's wrong?", "widget_id": 14352385}
Claude: *knows it worked, can proceed*
```

With proper response reading, Claude Code can:
1. **Verify** each step worked before proceeding
2. **Discover** available options (scan widgets, find text)
3. **Retry** intelligently on failure
4. **Build** reliable routines by composing validated steps
