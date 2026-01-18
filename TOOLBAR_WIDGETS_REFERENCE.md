# OSRS RuneLite Game Toolbar/Tabs Widget Reference

## Overview

This document provides the complete widget ID mapping for the OSRS RuneLite game interface toolbar buttons, including the main game tabs (Skills, Quests, Inventory) and chat tabs.

**Screenshot Context:**
- Window dimensions: 1592 x 1006 pixels (physical)
- UI Scale: 2.0 (so logical pixels = physical / 2)
- Logical size: 796 x 503 pixels

---

## 1. Game Interface Tab Buttons (Top-Right)

These are the main buttons in the top-right sidebar to switch between different game panels.

### Location: Top-Right Corner (around y=168)

All three tabs are in **Widget Group 548** and can be clicked using the `CLICK_WIDGET` command.

| Tab | Widget ID | Format | Position | Size | Actions | Notes |
|-----|-----------|--------|----------|------|---------|-------|
| **SKILLS** | 35913793 | 548:63:3001 | x=560, y=168 | 33×36 | `['Skills']` | Opens the Skills panel showing all skill levels and XP |
| **QUEST LIST** | 35913794 | 548:63:3002 | x=593, y=168 | 38×36 | `['Quest List', 'Character Summary', 'Achievement Diaries']` | Opens Quest Log with sub-tabs for quests, character info, and achievement diaries |
| **INVENTORY** | 35913795 | 548:63:3003 | x=626, y=168 | 33×36 | `['Inventory']` | Opens the Inventory panel showing carried items |

### Widget ID Format Explanation

Widget IDs are encoded as: `group:child:nested`

- **Group 548**: Main game interface container
- **Child 63**: The toolbar area containing the tab buttons
- **Nested values**: 3001, 3002, 3003 represent individual tabs from left to right

### Usage Examples

```python
# Click on the Skills tab
send_command('CLICK_WIDGET 35913793 "Skills"')

# Click on the Quest List tab
send_command('CLICK_WIDGET 35913794 "Quest List"')

# Click on the Inventory tab
send_command('CLICK_WIDGET 35913795 "Inventory"')

# Alternative: use the child:nested format
send_command('CLICK_WIDGET 548:63:3001 "Skills"')
```

---

## 2. Chat Tab Buttons (Bottom of Chatbox)

These are the chat mode tabs at the bottom of the chat interface for filtering chat messages.

### Location: Bottom-Left (y=480, width=56-79 pixels each)

All chat tabs are in **Widget Group 162**.

| Tab | Widget ID | Format | X Position | Size | Actions | Notes |
|-----|-----------|--------|------------|------|---------|-------|
| **All** | 10616836 | 162:1:3001 | 5 | 56×23 | `['Switch tab', 'Set chat mode: Public (/@p)', ...]` | Shows all chat messages |
| **Game** | 10616839 | 162:1:3002 | 67 | 56×23 | `['Switch tab', 'Filter']` | Shows game messages only |
| **Public** | 10616843 | 162:1:3003 | 129 | 56×23 | `['Switch tab', 'Show autochat']` | Shows public chat |
| **Private** | 10616847 | 162:1:3004 | 191 | 56×23 | `['Switch tab', 'Show all']` | Shows private messages |
| **Channel** | 10616851 | 162:1:3005 | 253 | 56×23 | `['Switch tab', 'Show all']` | Shows channel chat |
| **Clan** | 10616855 | 162:1:3006 | 315 | 56×23 | `['Switch tab', 'Show all']` | Shows clan chat |
| **Trade** | 10616859 | 162:1:3007 | 377 | 56×23 | `['Switch tab', 'Show all']` | Shows trade requests |

### Usage Examples

```python
# Click on the "Game" chat tab
send_command('CLICK_WIDGET 10616839 "Switch tab"')

# Click on the "Public" chat tab
send_command('CLICK_WIDGET 10616843 "Switch tab"')

# Click on the "Clan" chat tab
send_command('CLICK_WIDGET 10616855 "Switch tab"')
```

---

## 3. Widget Group Reference

### Important Groups for Interface Tabs

| Group | Purpose | Contains |
|-------|---------|----------|
| **548** | Main game interface container | Game tabs (Skills, Quests, Inventory) and main viewport |
| **162** | Chat interface container | Chat tabs and chatbox content |
| **63-67** | Child containers within Group 548 | Individual content panels |

---

## 4. Clicking Strategy with CLICK_WIDGET Command

### Command Format

```
CLICK_WIDGET <widget_id> "<action>"
```

Where:
- `widget_id` is the numeric ID (e.g., `35913793`) or the format string (e.g., `548:63:3001`)
- `action` is one of the available actions from the widget (e.g., `"Skills"`, `"Quest List"`, `"Inventory"`)

### Why Use CLICK_WIDGET?

The `CLICK_WIDGET` command is the reliable way to interact with game tabs because it:
1. **Finds the widget by action text** - Automatically locates the child widget with the specified action
2. **Gets fresh bounds at click time** - Avoids stale coordinate issues
3. **Clicks atomically** - Works reliably on Wayland and with UI scaling
4. **Handles virtual/dynamic widgets** - Works for tab buttons that may shift positions

---

## 5. Scanning for Widgets

If you need to find widgets programmatically:

```python
# Find all widgets with text "Skills"
find_widget(text="Skills")

# Click any widget by its action text
click_text("Skills")

# Scan for widgets in the main interface area
scan_widgets(filter_text="Skills", timeout_ms=5000)
```

### Scan Results Format

Widget information returned includes:
- **widget_id**: Numeric ID for use with `CLICK_WIDGET`
- **bounds**: `{x, y, width, height}` in logical pixels
- **actions**: Available right-click actions
- **text**: Widget label/text content

---

## 6. UI Coordinate System

**Important:** All coordinates in the widget data are in **logical pixels** (pre-scaled).

- Physical pixels (what you see): Up to 1592×1006
- Logical pixels (in widget bounds): Up to 796×503
- Conversion: `logical_pixels = physical_pixels / 2` (because UI scale is 2.0)

When you need screen coordinates for manual clicking (which you shouldn't do), remember to multiply logical pixels by 2.

---

## 7. Practical Use Cases

### Example 1: Check Inventory
```python
# Open inventory, wait for it to load
send_and_await(
    command='CLICK_WIDGET 35913795 "Inventory"',
    await_condition="inventory_count:<=28",
    timeout_ms=5000
)

# Check what you're carrying
state = get_game_state(fields=["inventory"])
```

### Example 2: Check Quests
```python
# Open quest log
send_command('CLICK_WIDGET 35913794 "Quest List"')

# Wait a moment for panel to appear
await_state_change(condition="idle", timeout_ms=2000)

# Take a screenshot to see quest status
get_screenshot()
```

### Example 3: View Skills
```python
# Open skills panel
send_command('CLICK_WIDGET 35913793 "Skills"')

# Get skill levels
state = get_game_state(fields=["skills"])
print(f"Attack: {state['skills']['Attack']['level']}")
print(f"Defense: {state['skills']['Defense']['level']}")
```

---

## 8. Troubleshooting

### Widget Not Clickable
- Ensure the widget is visible on screen
- Verify you're using the correct widget ID
- Check if the action name matches exactly (case-sensitive)

### Widgets Not Found
- Make sure RuneLite is running: `runelite_status()`
- Scan again: `scan_widgets(filter_text="Skills", timeout_ms=5000)`
- Check if the interface has changed (check screenshot)

### Commands Not Executing
- Verify the manny plugin is loaded and responsive
- Check logs: `get_logs(grep="CLICK_WIDGET", level="ALL")`
- Ensure player is logged in and not in a menu

---

## 9. Related Documentation

- **CLAUDE.md** - Full development guidelines for Claude Code
- **Command reference** - Complete command syntax guide
- **Widget clicking patterns** - Best practices for reliable UI interaction

---

## Appendix: Full Widget Data

### Game Tab Buttons (Raw Data)

```json
{
  "Skills": {
    "widget_id": 35913793,
    "group": 548,
    "child": 63,
    "nested": 3001,
    "bounds": {"x": 560, "y": 168, "width": 33, "height": 36},
    "actions": ["Skills"]
  },
  "Quest List": {
    "widget_id": 35913794,
    "group": 548,
    "child": 63,
    "nested": 3002,
    "bounds": {"x": 593, "y": 168, "width": 38, "height": 36},
    "actions": ["Quest List", "Character Summary", "Achievement Diaries"]
  },
  "Inventory": {
    "widget_id": 35913795,
    "group": 548,
    "child": 63,
    "nested": 3003,
    "bounds": {"x": 626, "y": 168, "width": 33, "height": 36},
    "actions": ["Inventory"]
  }
}
```

### Chat Tab Buttons (Raw Data)

```json
{
  "All": {"widget_id": 10616836, "format": "162:1:3001", "x": 5},
  "Game": {"widget_id": 10616839, "format": "162:1:3002", "x": 67},
  "Public": {"widget_id": 10616843, "format": "162:1:3003", "x": 129},
  "Private": {"widget_id": 10616847, "format": "162:1:3004", "x": 191},
  "Channel": {"widget_id": 10616851, "format": "162:1:3005", "x": 253},
  "Clan": {"widget_id": 10616855, "format": "162:1:3006", "x": 315},
  "Trade": {"widget_id": 10616859, "format": "162:1:3007", "x": 377}
}
```

---

**Last Updated:** 2026-01-18
**Source:** RuneLite widget scan from account 'aux'
