# Validate Routine

Validate a YAML routine file for errors before execution.

## Arguments
- `$ARGUMENTS` - path to the routine YAML file (e.g., `routines/quests/cooks_assistant.yaml`)

## Instructions

1. Read the routine file at `$ARGUMENTS` (use full path: `/home/wil/manny-mcp/$ARGUMENTS` if relative)
2. Spawn a Haiku subagent to validate:

```
Task(
    prompt=f"""Validate this OSRS routine YAML. Check for:

1. **Required fields**: each step needs 'action' and 'description'
2. **Valid actions**: GOTO, INTERACT_NPC, INTERACT_OBJECT, BANK_OPEN, BANK_DEPOSIT_ALL, BANK_WITHDRAW, BANK_CLOSE, PICKUP_ITEM, USE_ITEM_ON_NPC, USE_ITEM_ON_OBJECT, DIALOGUE, CLIMB_LADDER_UP, CLIMB_LADDER_DOWN
3. **Coordinates**: x/y should be 0-15000, plane should be 0-3
4. **GOTO format**: args should be "x y plane" (three space-separated integers)
5. **Location refs**: should have x, y, plane fields

Return JSON:
{{
  "valid": true/false,
  "errors": ["error 1", "error 2"],
  "warnings": ["warning 1"],
  "step_count": N
}}

Routine:
{routine_content}""",
    subagent_type="general-purpose",
    model="haiku"
)
```

3. Report validation results to the user
