# Tab Widget Finding Not Working

## Problem
`find_and_click_widget` and `find_widget` cannot find game tab widgets like "Worn Equipment" or "Equipment".

Previously, this worked for Quest tabs (per user), but now it's not finding the Equipment tab on Tutorial Island.

## Observed Behavior
```python
find_and_click_widget(text="Worn Equipment")  # Returns: No widget found
find_and_click_widget(text="Equipment")       # Returns: No widget found
find_widget(text="Worn")                      # Returns: 0 results, 0 widgets scanned
scan_widgets(filter_text="equipment")         # Returns: 0 results
```

## Expected Behavior
Should find the equipment tab widget and be able to click it.

## Context
- Tutorial Island combat section requires clicking the equipment tab (flashing icon)
- The tab is visually present with yellow/gold border indicating it should be clicked
- `scan_widgets()` without filter returns 194 widgets but none related to the tab icons
- Tab icons appear to be in a widget group that's not being scanned

## Widget Scan Results
The scan found:
- Group 149: Inventory items
- Group 162: Chat tabs
- Group 163: Game viewport
- Group 548: Main interface

Missing: The tab icon row (Combat, Skills, Quest, Inventory, Equipment, Prayer, Magic tabs)

## Workaround Attempts
1. `send_input(click, x, y)` - Coordinates don't work reliably
2. `MOUSE_MOVE` + `MOUSE_CLICK` commands - Not clicking correct location
3. `xdotool` with doubled coordinates for UI scale - Wrong position
4. `TAB_OPEN equipment` command - Didn't open the tab
5. `KEY_PRESS F4` - Didn't work
6. `click_widget(35913734)` - Widget at similar position, unclear if correct

## Questions
1. What widget group are the tab icons in?
2. Did something change in the widget scanning logic?
3. Is there a known widget ID for the Equipment tab?

## Priority
Medium-High - Blocks Tutorial Island automation and any task requiring tab switching

## Date
2026-01-18
