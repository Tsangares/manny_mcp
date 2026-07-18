---
description: Validate a routine YAML file (e.g., /validate routines/skilling/my_routine.yaml)
---

Validate this routine using the validate_routine_deep MCP tool: **{{arg1}}**

Check for:
- YAML syntax errors
- Unknown commands
- Invalid coordinates (must be 0-15000, plane 0-3)
- Missing required fields
- Logic flow issues

Show results with:
- ✅ or ❌ status
- Error count with details
- Suggested fixes for typos (fuzzy matching)
- Routine statistics

If valid, confirm it's ready to run and show command to load it.
If errors, explain each one clearly and suggest fixes.

Example output:
```
🔍 Validating: routines/skilling/fishing_draynor.yaml

✅ VALID - Ready to run!

📊 Statistics:
  • Steps: 6
  • Locations: 2
  • Commands: 5 unique
  • Phases: 2 (preparation, fishing)

🚀 To run:
   ./run_routine.py routines/skilling/fishing_draynor.yaml --account main
```
