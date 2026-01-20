# External Widget Inspector - Lessons Learned
**Date:** 2026-01-18

## The Problem

External Widget Inspector was built to run on display `:0` while RuneLite runs on `:2`, using file-based IPC. Two issues emerged:
1. Bounding box highlighting in-game didn't work after file selection
2. Toolbar tabs (Inventory, Quest, Skills) weren't appearing in widget scans

## Root Cause

### Issue 1: Wrong Overlay Class Modified

MannyPlugin uses **two different** widget inspector overlays:
- `UIOverlays.WidgetInspectorOverlay` - Unused legacy overlay
- `WidgetInspectorTool.Overlay` in `UITools.java` - **Actually registered and rendered**

I modified the wrong one. The correct overlay is in `manny_src/ui/UITools.java` starting at line 2034.

**Discovery method:**
```bash
grep -n "widgetInspectorOverlay" manny_src/MannyPlugin.java
# Shows: overlayManager.add(widgetInspectorTool.getOverlay());
```

### Issue 2: Child Scan Range Too Small

`ScanWidgetsCommand.java` scanned children 0-50, but toolbar tabs are at indices 63-67:
- 548:63 - Toolbar header widget
- 548:63:3001 - Skills tab (static nested child)
- 548:63:3002 - Quest List tab
- 548:63:3003 - Inventory tab

Expanded range from `childIdx <= 50` to `childIdx <= 100`.

## Key Lessons

### 1. MannyPlugin Has Two Widget Inspector Overlays

**What happened:** File-based selection worked (file written, file read) but no bounding box appeared.
**Why:** Modified `UIOverlays.WidgetInspectorOverlay` but MannyPlugin registers `WidgetInspectorTool.Overlay`.
**Solution:**
```java
// WRONG - This overlay is NOT used by MannyPlugin
UIOverlays.java -> class WidgetInspectorOverlay

// CORRECT - This is what MannyPlugin actually uses
UITools.java -> class WidgetInspectorTool.Overlay (line 2034)
```

### 2. Widget Nested Child Index Encoding

**What happened:** Clicking toolbar tabs in inspector didn't highlight because they share parent ID.
**Why:** Nested children don't have unique packed IDs - need `group:child:nested` format.
**Solution:**
```python
# BAD - All toolbar tabs resolve to same widget
widget_id = 35913791  # (548 << 16) | 63 - parent only

# GOOD - Include nested index
selection = "548:63:3001"  # Skills tab
selection = "548:63:3002"  # Quest List tab
selection = "548:63:3003"  # Inventory tab
```

### 3. Nested Child Index Ranges

| Type | Index Range | Example |
|------|-------------|---------|
| Dynamic children | 1000-2999 | `widget.getDynamicChildren()[idx]` → nested 1000+idx |
| Static children | 3000-3999 | `widget.getStaticChildren()[idx]` → nested 3000+idx |
| Nested children | 4000+ | `widget.getNestedChildren()[idx]` → nested 4000+idx |

Lookup code in `UITools.java`:
```java
private Widget getExternalWidget() {
    Widget parent = client.getWidget(externalGroupId, externalChildId);
    if (externalNestedIdx >= 4000) {
        Widget[] nested = parent.getNestedChildren();
        return nested[externalNestedIdx - 4000];
    } else if (externalNestedIdx >= 3000) {
        Widget[] staticChildren = parent.getStaticChildren();
        return staticChildren[externalNestedIdx - 3000];
    } else if (externalNestedIdx >= 1000) {
        Widget[] dynamic = parent.getDynamicChildren();
        return dynamic[externalNestedIdx - 1000];
    }
    return parent;
}
```

### 4. Toolbar Tab Widget IDs for Common Actions

| Tab | Widget Reference | Click Command |
|-----|------------------|---------------|
| Skills | 548:63:3001 | `CLICK_WIDGET 35913791 "Skills"` |
| Quest List | 548:63:3002 | `CLICK_WIDGET 35913791 "Quest List"` |
| Inventory | 548:63:3003 | `CLICK_WIDGET 35913791 "Inventory"` |

**Key insight:** Use `CLICK_WIDGET <container_id> "<action>"` to click by action text. The container ID is the parent (35913791), and the action matches the nested child.

## Anti-Patterns

1. **Don't** assume overlay class names match usage - Always grep for the variable registration
2. **Don't** hardcode widget scan ranges - Widget children can be at any index
3. **Don't** use packed ID alone for nested children - Need `group:child:nested` format

## Debugging Commands

| Command | Purpose |
|---------|---------|
| `grep -n "widgetInspectorOverlay" MannyPlugin.java` | Find which overlay class is registered |
| `find_widget(text="Inventory")` | Discover toolbar tab widgets |
| `scan_widgets(filter_text="Quest")` | Full widget scan with filter |

## Interface Gaps Identified

- [x] Plugin needs: File watcher in correct overlay (UITools.java) - **Fixed**
- [x] Plugin needs: Nested child support in overlay rendering - **Fixed**
- [x] Plugin needs: Expanded child scan range (100 vs 50) - **Fixed**
- [x] MCP needs: `find_and_click_widget` tool - **Added**
- [x] MCP needs: `clear_widget_overlay` tool - **Added**

## Files Modified

| File | Change |
|------|--------|
| `manny_src/ui/UITools.java` | Added file-watching and nested child lookup to WidgetInspectorTool.Overlay |
| `manny_src/utility/commands/ScanWidgetsCommand.java` | Expanded child scan range from 50 to 100 |
| `mcptools/tools/routine.py` | Added `find_and_click_widget` and `clear_widget_overlay` tools |
| `CLAUDE.md` | Updated widget discovery priority: find_widget first, avoid deep scan |
