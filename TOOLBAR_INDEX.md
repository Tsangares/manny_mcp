# Game Toolbar Widgets - Documentation Index

Complete widget mapping for OSRS RuneLite game interface tabs and toolbars.

## Quick Start

**3 Game Tabs You Can Click:**

```python
# Skills tab (opens skill levels)
send_command('CLICK_WIDGET 35913793 "Skills"')

# Quest tab (opens quest log)
send_command('CLICK_WIDGET 35913794 "Quest List"')

# Inventory tab (opens backpack)
send_command('CLICK_WIDGET 35913795 "Inventory"')
```

---

## Documentation Files

### 1. **TOOLBAR_FINDINGS_SUMMARY.md** ⭐ START HERE
   - **Purpose:** Complete overview of the discovery
   - **Contents:**
     - Executive summary of what was found
     - All discovered widgets with IDs
     - Technical details and widget format explanation
     - Practical usage examples
     - Troubleshooting guide
   - **Best for:** Understanding the full picture and getting started

### 2. **TOOLBAR_QUICK_REFERENCE.txt** ⚡ QUICK LOOKUP
   - **Purpose:** Fast reference for copying commands
   - **Contents:**
     - Tab ID lookup table
     - Copy-paste ready command examples
     - Key facts summary
   - **Best for:** Quick reference while coding, finding widget IDs fast

### 3. **TOOLBAR_WIDGETS_REFERENCE.md** 📚 COMPREHENSIVE GUIDE
   - **Purpose:** Detailed technical reference
   - **Contents:**
     - Complete widget specifications
     - Widget group and format explanation
     - Scanning instructions
     - Use cases with full code examples
     - Widget data in JSON format
     - Appendices with raw data
   - **Best for:** Deep understanding, implementing complex interactions

### 4. **TOOLBAR_VISUAL_LAYOUT.txt** 🎨 VISUAL REFERENCE
   - **Purpose:** Visual representation of interface layout
   - **Contents:**
     - ASCII diagrams of button positions
     - Screen coordinate reference
     - Layout breakdown by section
     - Visual representation of widget hierarchy
     - Debugging workflow diagram
   - **Best for:** Understanding spatial relationships, debugging positioning issues

---

## Widget Summary Table

### Game Interface Tabs (Top-Right, y=168)

| Name | Widget ID | Format | X Pos | Action |
|------|-----------|--------|-------|--------|
| Skills | 35913793 | 548:63:3001 | 560 | "Skills" |
| Quests | 35913794 | 548:63:3002 | 593 | "Quest List" |
| Inventory | 35913795 | 548:63:3003 | 626 | "Inventory" |

### Chat Tabs (Bottom-Left, y=480)

| Name | Widget ID | Format | X Pos | Action |
|------|-----------|--------|-------|--------|
| All | 10616836 | 162:1:3001 | 5 | "Switch tab" |
| Game | 10616839 | 162:1:3002 | 67 | "Switch tab" |
| Public | 10616843 | 162:1:3003 | 129 | "Switch tab" |
| Private | 10616847 | 162:1:3004 | 191 | "Switch tab" |
| Channel | 10616851 | 162:1:3005 | 253 | "Switch tab" |
| Clan | 10616855 | 162:1:3006 | 315 | "Switch tab" |
| Trade | 10616859 | 162:1:3007 | 377 | "Switch tab" |

---

## How to Use

### For New Developers

1. Read **TOOLBAR_FINDINGS_SUMMARY.md** for complete context
2. Refer to **TOOLBAR_QUICK_REFERENCE.txt** while coding
3. Use copy-paste examples from the quick reference

### For Complex Tasks

1. Consult **TOOLBAR_WIDGETS_REFERENCE.md** for detailed specs
2. Use **TOOLBAR_VISUAL_LAYOUT.txt** to understand positioning
3. Reference raw JSON data in the comprehensive guide appendix

### For Debugging

1. Check **TOOLBAR_VISUAL_LAYOUT.txt** troubleshooting section
2. Use the debugging tips to verify widget positions
3. Cross-reference widget IDs from the quick reference

---

## Common Commands

### Open Game Interface Tabs

```python
# Open Skills
send_command('CLICK_WIDGET 35913793 "Skills"')

# Open Quests
send_command('CLICK_WIDGET 35913794 "Quest List"')

# Open Inventory
send_command('CLICK_WIDGET 35913795 "Inventory"')
```

### Switch Chat Tabs

```python
# Game chat
send_command('CLICK_WIDGET 10616839 "Switch tab"')

# Clan chat
send_command('CLICK_WIDGET 10616855 "Switch tab"')

# Trade
send_command('CLICK_WIDGET 10616859 "Switch tab"')
```

### With State Verification

```python
# Open Inventory and verify it loaded
send_and_await(
    command='CLICK_WIDGET 35913795 "Inventory"',
    await_condition="inventory_count:<=28",
    timeout_ms=5000
)
```

### Get Game State After Tab Switch

```python
# After clicking a tab, get state
get_game_state(fields=["inventory", "equipment", "skills"])
```

---

## Key Concepts

### Widget Format: `group:child:nested`

- **Group 548:** Main game interface (contains Skills, Quests, Inventory tabs)
- **Group 162:** Chat interface (contains 7 chat mode tabs)
- **Child:** Position within group
- **Nested:** Specific element index

Example: `548:63:3002` means:
- Group 548 (main interface)
- Child 63 (tab buttons row)
- Nested 3002 (second tab = Quests)

### Action Strings

Each widget has specific action strings that appear in right-click menus:
- Game tabs: "Skills", "Quest List", "Inventory"
- Chat tabs: "Switch tab" (same for all)

### Coordinates

All coordinates are in **logical pixels** (internal game units):
- Physical screen = 1592×1006 pixels
- Logical space = 796×503 pixels
- Conversion: logical = physical ÷ 2

---

## Practical Examples

### Example 1: Check Inventory Size

```python
send_command('CLICK_WIDGET 35913795 "Inventory"')
await_state_change(condition="idle", timeout_ms=2000)
state = get_game_state(fields=["inventory"])
print(f"Carrying {state['state']['inventory']['used']} items")
```

### Example 2: Monitor Skills During Training

```python
send_command('CLICK_WIDGET 35913793 "Skills"')
await_state_change(condition="idle", timeout_ms=2000)
skills = get_game_state(fields=["skills"])
attack_level = skills['state']['skills']['Attack']['level']
print(f"Attack level: {attack_level}")
```

### Example 3: Check Quest Progress

```python
send_command('CLICK_WIDGET 35913794 "Quest List"')
# Take screenshot or parse dialogue
get_screenshot()
```

### Example 4: Filter Chat

```python
# Switch to Game chat to see game messages only
send_command('CLICK_WIDGET 10616839 "Switch tab"')
```

---

## Discovery Details

- **Method:** Widget scanning with manny plugin
- **Tool:** `scan_widgets(account_id="aux", deep=True)`
- **Date:** 2026-01-18
- **Account:** aux (LOSTimposter)
- **Verification:** All widgets tested and working

---

## Troubleshooting

### Widget not found?

```python
# Verify widget exists
find_widget(text="Skills")
find_widget(text="Inventory")

# Full scan if needed
scan_widgets(filter_text="Skills", timeout_ms=5000)
```

### Command not executing?

```python
# Check if plugin is running
runelite_status()

# View recent logs
get_logs(grep="CLICK_WIDGET", level="ALL")

# Take screenshot
get_screenshot()
```

### Coordinates seem off?

- Remember coordinates are in logical pixels
- Multiply by 2 to get physical screen coordinates
- Use `get_screenshot()` to verify visually

---

## Related Documentation

- **CLAUDE.md** - Development guidelines and best practices
- **Widget Clicking (CRITICAL)** section in CLAUDE.md - Why CLICK_WIDGET is reliable
- **Routine Building** in CLAUDE.md - Creating automations using these tabs
- **Game State** in CLAUDE.md - Using get_game_state for inventory/equipment/skills

---

## Next Steps

1. **For automation:** Use these widgets in routines for task automation
2. **For monitoring:** Query game state after clicking tabs
3. **For debugging:** Use visual layout reference to understand interface structure
4. **For discovery:** Follow the same scan_widgets pattern to find other widgets

---

## Files in This Collection

```
/home/wil/manny-mcp/
├── TOOLBAR_INDEX.md                    (this file - overview & navigation)
├── TOOLBAR_FINDINGS_SUMMARY.md         (complete discovery summary)
├── TOOLBAR_WIDGETS_REFERENCE.md        (detailed technical reference)
├── TOOLBAR_QUICK_REFERENCE.txt         (quick lookup table)
└── TOOLBAR_VISUAL_LAYOUT.txt           (ASCII diagrams & layout)
```

---

## Quick Links by Use Case

**I need to...**

- **Click a tab:** See TOOLBAR_QUICK_REFERENCE.txt (copy-paste ready)
- **Understand widget structure:** Read TOOLBAR_FINDINGS_SUMMARY.md
- **Find a specific widget ID:** Use TOOLBAR_QUICK_REFERENCE.txt lookup table
- **See interface layout:** View TOOLBAR_VISUAL_LAYOUT.txt diagrams
- **Deep dive into details:** Consult TOOLBAR_WIDGETS_REFERENCE.md
- **Debug positioning issues:** Check TOOLBAR_VISUAL_LAYOUT.txt troubleshooting

---

**Last Updated:** 2026-01-18
**Discovery Status:** Complete ✓
**All Widgets Verified:** Yes ✓
