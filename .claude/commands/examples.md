---
description: Show real usage examples of a command (e.g., /examples BANK_WITHDRAW)
---

Find real usage examples of **{{arg1}}** using get_command_examples MCP tool.

Show:
- How many times it's used across all routines
- Which routines use it
- The args format with real examples
- Description/context for each use
- Common patterns

Then suggest:
- Related commands to check out
- Link to full command reference if needed

Example output:
```
📚 Examples of BANK_WITHDRAW

Found 3 uses across 2 routines:

1. routines/quests/cooks_assistant.yaml (step 3)
   Args: "Bucket 1"
   Context: Withdraw bucket for milk

2. routines/quests/cooks_assistant.yaml (step 4)
   Args: "Pot 1"
   Context: Withdraw pot for flour

3. routines/skilling/fishing_draynor.yaml (step 4)
   Args: "Small fishing net 1"
   Context: Withdraw fishing net

📋 Args format: "<item_name> <quantity>"

💡 Related commands: BANK_OPEN, BANK_DEPOSIT_ALL, BANK_CLOSE
```
