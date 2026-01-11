---
description: Discover OSRS commands by keyword (e.g., /discover FISH)
---

Use the list_available_commands MCP tool to find commands matching: **{{arg1}}**

Show results in a clean table with:
- Command name
- Handler function
- Line number in source

Then suggest:
- Related commands in the same category
- Specialized commands that might be better (e.g., FISH_DRAYNOR_LOOP vs FISH)
- Next step: use `/examples <COMMAND>` to see usage

Example output format:
```
🔍 Found 3 commands matching "FISH":

┌─────────────────────┬──────────────────┬──────┐
│ Command             │ Handler          │ Line │
├─────────────────────┼──────────────────┼──────┤
│ FISH                │ handleFish       │ 9123 │
│ FISH_DROP           │ handleFishDrop   │ 9126 │
│ FISH_DRAYNOR_LOOP   │ handleFishLoop   │ 9129 │
└─────────────────────┴──────────────────┴──────┘

💡 FISH_DRAYNOR_LOOP is specialized - handles fishing + banking automatically!

📚 Next: /examples FISH_DRAYNOR_LOOP
```
