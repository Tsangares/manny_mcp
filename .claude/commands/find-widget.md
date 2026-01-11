---
description: Find a clickable widget by text (e.g., /find-widget shrimp)
---

Use a **Haiku subagent** to find widgets matching: **{{arg1}}**

Spawn a Task with model="haiku" and subagent_type="general-purpose":

```
Task(
  prompt="""Find widgets matching '{{arg1}}' in the game UI.

  1. Call scan_widgets() MCP tool to get all visible widgets
  2. Search for '{{arg1}}' in:
     - text field (case-insensitive)
     - name field (often contains item names like 'Raw shrimps')
     - actions array (e.g., 'Cook', 'Bank')
  3. Return ONLY matching widgets in this format:

  Found N widget(s) matching "{{arg1}}":

  1. widget_id: [ID]
     text/name: [text]
     actions: [actions]
     center: (x, y)

  To click: CLICK_WIDGET [widget_id]

  If no matches, suggest checking if the interface is open.""",
  model="haiku",
  subagent_type="general-purpose"
)
```

After getting results, show them to user and suggest:
- `send_command("CLICK_WIDGET <id>")` to click the widget
- Or use the new `click_widget(widget_id=<id>)` MCP tool
