# Shop Interaction Tool Gaps - Lessons Learned
**Date:** 2025-01-12

## The Problem

Attempted to buy a mithril scimitar from Zeke's scimitar shop in Al Kharid. Despite the shop interface being open, the item being found, and the "Buy 1" menu option existing, no purchase could be completed through any available MCP tool.

## Root Cause

Multiple tool gaps compounded to make shop purchases impossible:

1. **SHOP_BUY command** - Color tag matching failure in menu option comparison
2. **click_widget** - Only supports left-click (default action), no action parameter
3. **send_input** - Coordinate system mismatch with 2x UI scaling
4. **click_text** - Doesn't scan right-click context menus

## Key Lessons

### 1. SHOP_BUY Fails Due to Color Tag Matching

**What happened:** Command found the item, found "Buy 1" in available menu entries, but failed to click it.

**Why:** The menu target includes color codes: `<col=ff9040>Mithril scimitar</col>`. The string matching compares against this colored version, not the plain text.

**Evidence from logs:**
```
[SHOP_BUY] Menu option 'Buy 1' not found for item '<col=ff9040>Mithril scimitar</col>'
[SHOP_BUY] Available menu entries (7 total):
  [5] Option='Buy 1' | Target='<col=ff9040>Mithril scimitar</col>'
```

**Solution needed:** Strip color tags before matching, or match only the Option field.

### 2. send_input Coordinates Don't Match Visual Positions

**What happened:** Clicked at (100, 100), cursor appeared at (~175, ~168) in screenshot.

**Why:** With `-Dsun.java2d.uiScale=2.0`, there's a complex relationship between:
- Widget bounds (logical pixels)
- Screenshot coordinates (physical pixels)
- send_input coordinates (unclear - not 1:1 with either)

**Pattern observed:**
```python
# Clicked (100, 100) via send_input
# Cursor appeared at approximately (175, 168) in screenshot
# Ratio: ~1.75x but inconsistent

# Widget bounds said mithril scimitar at (218, 64)
# Tried clicking (236, 80) - center of widget
# Did not land on the item
```

**Solution needed:** Document the coordinate mapping or provide a tool that translates between systems.

### 3. click_widget Only Does Left-Click (Default Action)

**What happened:** Used `click_widget(widget_id, bounds={...})` successfully - it clicked the mithril scimitar. But it triggered "Value" (the default left-click action), not "Buy 1".

**Why:** click_widget has no parameter to specify which action to perform. Shop items default to "Value" on left-click.

**What's needed:**
```python
# CURRENT - only left-clicks, triggers default action
click_widget(widget_id=19660816, bounds={...})

# NEEDED - specify action
click_widget(widget_id=19660816, bounds={...}, action="Buy 1")
# OR
right_click_widget(widget_id=19660816, bounds={...})
```

### 4. Right-Click Menu Appeared But click_text Couldn't Find Options

**What happened:** Successfully right-clicked (via send_input) to open context menu. Menu showed "Buy 1 Mithril scimitar". But `click_text("Buy 1")` returned "Option not found".

**Why:** click_text likely scans widget text, not the right-click context menu which may be rendered differently.

**Evidence:**
```python
# Menu visually showing:
# - Value Mithril scimitar
# - Buy 1 Mithril scimitar
# - Buy 5 Mithril scimitar
# - etc.

click_text("Buy 1")  # Returns: "Option not found"
```

## Anti-Patterns

1. **Don't assume send_input coordinates match screenshot pixels** - There's scaling involved
2. **Don't rely on SHOP_BUY for shops** - Color tag bug makes it fail silently after finding the item
3. **Don't expect click_text to find context menu options** - It doesn't scan those widgets

## Debugging Commands

| Command | Purpose |
|---------|---------|
| `get_logs(grep="SHOP")` | See exactly where SHOP_BUY failed |
| `find_widget(text="Mithril")` | Verify widget is found with correct bounds |
| `get_screenshot()` | Visual confirmation of what's on screen |
| `click_widget(..., bounds={...})` | Click with bounds works, but only left-click |

## Interface Gaps Identified

- [ ] **MCP needs:** SHOP_BUY to strip color tags before matching menu options
- [ ] **MCP needs:** click_widget to support `action` parameter or right-click
- [ ] **MCP needs:** Tool to click context menu options by text
- [ ] **MCP needs:** Documentation of send_input coordinate system vs widget bounds vs screenshot
- [ ] **Plugin needs:** Shop buying that handles virtual widget items properly
- [ ] **CLAUDE.md needs:** Warning about shop interaction limitations

## What Did Work

| Tool | Success |
|------|---------|
| `GOTO` | Navigation to Al Kharid worked |
| `INTERACT_OBJECT gate Pay-toll(10gp)` | Toll gate worked |
| `INTERACT_NPC Zeke Trade` | Opened shop correctly |
| `find_widget(text="Mithril scimitar")` | Found item with correct bounds |
| `get_screenshot()` | Visual debugging was essential |
| Right-click via send_input at (236, 80) | Menu did appear |

## Time Wasted

~30 minutes trying various approaches:
- SHOP_BUY command (failed)
- click_widget with bounds (wrong action)
- Manual coordinate clicking (coordinate mismatch)
- click_text on menu (didn't find options)
- Multiple screenshot/debug cycles

## Workaround That Finally Worked

Right-clicking via send_input at the click_widget reported position (236, 80) DID open the context menu. The remaining gap was clicking the menu option - attempted send_input at estimated menu position but session ended before confirming success.
