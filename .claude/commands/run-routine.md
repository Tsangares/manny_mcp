---
description: Run a YAML routine (e.g., /run-routine routines/skilling/cooking_lumbridge.yaml 1)
---

Run the routine at **{{arg1}}** for **{{arg2}}** loops (default 1 if not specified).

Use the CLI script to execute:
```bash
./run_routine.py {{arg1}} --loops {{arg2}}
```

Before running:
1. Ensure RuneLite is logged in and responsive
2. Check player is in the correct starting position for the routine
3. Verify the state file is being updated (check timestamp)

After running, report:
- Success/failure status
- XP gains by skill
- Any errors that occurred
- Final player state (plane, inventory count)

If errors occur:
- Analyze which step failed and why
- Suggest fixes to the routine YAML if needed
- Offer to retry or reset player position
