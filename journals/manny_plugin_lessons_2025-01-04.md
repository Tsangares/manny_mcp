# Manny Plugin Development Lessons
**Date:** 2025-01-04

## Key Insights

### 1. When Disconnected, Plugin Commands Don't Work

The manny plugin processes commands from `/tmp/manny_command.txt` on GameTick events. **When disconnected, there are no GameTicks**, so commands written to the file are never processed.

**Solution:** For reconnection/login flows, use external input methods like `xdotool` that interact directly with the X11 window, bypassing the plugin entirely.

```python
# BAD - doesn't work when disconnected
with open(command_file, "w") as f:
    f.write("MOUSE_CLICK left\n")

# GOOD - works regardless of game state
subprocess.run(["xdotool", "mousemove", "--window", window_id, str(x), str(y), "click", "1"])
```

### 2. Document UI Coordinates in Code

Login screen coordinates were wrong and kept getting forgotten. **Document coordinates directly in the code** where they're used, with:
- Bounds (top-left and bottom-right)
- Center point
- Date documented
- What dialog/screen they're for

```python
# DOCUMENTED COORDINATES (2025-01-04):
#   Ok button bounds: top-left (640, 575), bottom-right (900, 633)
#   Center: (770, 604)
# NOTE: These are for "You were disconnected" dialog
```

### 3. OSRS Item Names Have Quirks

Item names in OSRS often differ from what you'd expect:
- "Raw shrimps" (plural, not "Raw shrimp")
- "Pot of flour" (not "Flour pot")
- Case variations

**Best practice:** Add fallback matching for item searches:
1. First: exact match (case-insensitive)
2. Fallback: contains match

Use `SCAN_BANK` to discover exact item names when unsure.

### 4. Widget Child Indices Vary

Widgets in RuneLite are organized as `Group.Child.NestedChild`. The "Click here to continue" button was at child index 5, not 0.

**Best practice:** When searching for widgets by text, iterate through children 0-20 rather than checking a single hardcoded index.

```java
// BAD - only checks child 0
Widget widget = client.getWidget(group, 0);

// GOOD - searches all children
for (int childIdx = 0; childIdx <= 20; childIdx++) {
    Widget widget = client.getWidget(group, childIdx);
    // check widget text...
}
```

### 5. Bank Widget Container ID

The bank item container widget ID is `786445` (BANK_ITEM_CONTAINER). Use `getDynamicChildren()` to iterate items.

### 6. Restart as Fallback

When automated recovery (clicking through dialogs) fails, restarting the RuneLite client is a valid fallback. The `auto_reconnect` tool now has `restart_on_timeout=true` by default.

## Commands to Remember

| Command | Purpose |
|---------|---------|
| `SCAN_BANK` | List all items in bank with exact names |
| `BANK_CHECK <itemId>` | Check quantity of item by ID |
| `SCAN_WIDGETS [filterText]` | Find visible UI widgets |
| `query_nearby` | Find NPCs, objects, ground items |

## Testing Checklist

Before deploying plugin changes:
- [ ] Build compiles without errors
- [ ] Test with exact item names
- [ ] Test with partial/fuzzy item names
- [ ] Test when bank is on different tabs
- [ ] Test recovery from disconnect

## Anti-Patterns to Avoid

1. **Don't assume widget positions** - Always search/iterate
2. **Don't use hardcoded item names** - Support fuzzy matching
3. **Don't rely on plugin commands during disconnect** - Use external tools
4. **Don't forget to document coordinates** - They WILL be forgotten
5. **Don't skip the second pass** - Fallback matching saves debugging time

## Future Improvements to Consider

1. **Bank tab awareness** - Currently only searches visible items. Could add tab switching or search functionality.
2. **Item name normalization** - Strip plurals, handle common variations automatically
3. **Coordinate auto-detection** - Use image recognition instead of hardcoded positions for login dialogs
4. **Health check integration** - auto_reconnect could be triggered automatically by health monitoring
